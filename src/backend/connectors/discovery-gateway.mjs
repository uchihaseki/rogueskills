import { SOURCE_CONNECTORS } from "../../core/discovery/catalog.js";
import {
  candidateToSkillGenome,
  contentFingerprint,
  deduplicateCandidates,
  matchesFilters,
  parseSearchQuery,
  rankCandidate,
  searchLocalIndex,
} from "../../core/discovery/engine.js";

function inferKind(item) {
  const text = `${item.name} ${item.description ?? ""} ${(item.topics ?? []).join(" ")}`.toLowerCase();
  if (/\b(skill|agent skill|prompt)\b/.test(text)) return "skill";
  if (/\b(sop|runbook|playbook|procedure)\b/.test(text)) return "sop";
  if (/\b(checklist)\b/.test(text)) return "checklist";
  return "material";
}

function githubCandidate(item, connector) {
  const license = item.license?.spdx_id ?? "unknown";
  return {
    id: `${connector.id}-${item.id}`,
    name: item.full_name,
    summary: item.description || "公开 GitHub 仓库，等待拉取内容快照。",
    kind: inferKind(item),
    sourceId: connector.id,
    platform: connector.name,
    author: item.owner?.login ?? item.full_name.split("/")[0],
    license,
    updatedAt: item.updated_at,
    tags: [...new Set([...(item.topics ?? []), "github"])].slice(0, 12),
    url: item.html_url,
    fullName: item.full_name,
    defaultBranch: item.default_branch,
    content: item.description ?? "",
    signals: {
      official: Boolean(connector.official),
      completeness: item.description ? 58 : 35,
      stars: item.stargazers_count ?? 0,
      forks: item.forks_count ?? 0,
    },
    snapshot: { status: "metadata_only", fingerprint: null, artifactPaths: [] },
  };
}

function parseGitHubRepositoryReference(value) {
  const text = value.trim();
  const urlMatch = text.match(/^https?:\/\/github\.com\/([^/\s]+)\/([^/#?\s]+)(?:[/?#].*)?$/i);
  if (urlMatch) return `${urlMatch[1]}/${urlMatch[2].replace(/\.git$/i, "")}`;
  const shortMatch = text.match(/^([\w.-]+)\/([\w.-]+)$/);
  return shortMatch ? `${shortMatch[1]}/${shortMatch[2].replace(/\.git$/i, "")}` : null;
}

export async function searchGitHub(query, connector, { fetchImpl = globalThis.fetch, limit = 12 } = {}) {
  if (!fetchImpl) throw new Error("当前环境不支持网络请求");

  const parsed = parseSearchQuery(query);
  const terms = parsed.text || "agent skill workflow";
  const exactRepository = connector.id === "github" ? parseGitHubRepositoryReference(terms) : null;

  if (exactRepository) {
    const response = await fetchImpl(`https://api.github.com/repos/${exactRepository}`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) throw new Error(`GitHub Repository API 返回 ${response.status}`);
    const item = await response.json();
    return [rankCandidate(githubCandidate(item, connector), query)];
  }

  const skillHint = /(?:skill|sop|runbook|workflow|agent)/i.test(terms) ? "" : " skill";
  const qualifier = connector.qualifier ? ` ${connector.qualifier}` : "";
  const search = `${terms}${skillHint} in:name,description,readme${qualifier}`.trim();
  const params = new URLSearchParams({ q: search, sort: "updated", order: "desc", per_page: String(limit) });
  const response = await fetchImpl(`https://api.github.com/search/repositories?${params}`, {
    headers: { Accept: "application/vnd.github+json" },
  });

  if (!response.ok) {
    const rateLimited = response.status === 403 || response.status === 429;
    throw new Error(rateLimited ? "GitHub 公共 API 已达到速率限制" : `GitHub API 返回 ${response.status}`);
  }

  const payload = await response.json();
  return (payload.items ?? [])
    .map((item) => rankCandidate(githubCandidate(item, connector), query))
    .filter((candidate) => matchesFilters(candidate, parsed.filters));
}

export async function federatedSearch(
  query,
  { sourceIds = ["builtin", "github"], fetchImpl = globalThis.fetch, limitPerSource = 12 } = {},
) {
  const connectors = sourceIds
    .map((id) => SOURCE_CONNECTORS.find((connector) => connector.id === id))
    .filter(Boolean);
  const status = [];
  const collected = [];

  await Promise.all(
    connectors.map(async (connector) => {
      if (connector.mode === "local") {
        const results = searchLocalIndex(query);
        collected.push(...results);
        status.push({ sourceId: connector.id, state: "ok", count: results.length });
        return;
      }

      if (connector.mode !== "github") {
        status.push({ sourceId: connector.id, state: "unavailable", count: 0 });
        return;
      }

      try {
        const results = await searchGitHub(query, connector, { fetchImpl, limit: limitPerSource });
        collected.push(...results);
        status.push({ sourceId: connector.id, state: "ok", count: results.length });
      } catch (error) {
        status.push({ sourceId: connector.id, state: "error", count: 0, message: error.message });
      }
    }),
  );

  const results = deduplicateCandidates(collected).sort(
    (left, right) => right.ranking.total - left.ranking.total,
  );
  return { results, status };
}

async function fetchText(url, fetchImpl, headers = {}) {
  const response = await fetchImpl(url, { headers });
  if (!response.ok) throw new Error(`内容拉取失败：${response.status}`);
  return response.text();
}

export async function hydrateCandidate(candidate, { fetchImpl = globalThis.fetch } = {}) {
  if (!candidate.fullName || !fetchImpl) {
    const content = candidate.content ?? candidate.summary ?? "";
    return {
      ...candidate,
      snapshot: {
        status: content ? "captured" : "metadata_only",
        fingerprint: contentFingerprint(content),
        artifactPaths: [],
      },
    };
  }

  const branch = candidate.defaultBranch || "main";
  const treeUrl = `https://api.github.com/repos/${candidate.fullName}/git/trees/${encodeURIComponent(branch)}?recursive=1`;

  try {
    const treeResponse = await fetchImpl(treeUrl, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!treeResponse.ok) throw new Error(`Git Tree ${treeResponse.status}`);
    const tree = await treeResponse.json();
    const skillPaths = (tree.tree ?? [])
      .filter((item) => item.type === "blob" && /(^|\/)skill\.md$/i.test(item.path))
      .sort((left, right) => left.path.split("/").length - right.path.split("/").length)
      .slice(0, 1)
      .map((item) => item.path);
    let artifactPaths = skillPaths;
    let contents = [];

    if (skillPaths.length) {
      contents = await Promise.all(
        skillPaths.map(async (path) => {
          const rawUrl = `https://raw.githubusercontent.com/${candidate.fullName}/${branch}/${path}`;
          return fetchText(rawUrl, fetchImpl);
        }),
      );
    } else {
      const readmeUrl = `https://api.github.com/repos/${candidate.fullName}/readme`;
      const readme = await fetchText(readmeUrl, fetchImpl, { Accept: "application/vnd.github.raw+json" });
      contents = [readme];
      artifactPaths = ["README"];
    }

    const content = contents.join("\n\n---\n\n").slice(0, 120_000);
    return {
      ...candidate,
      content,
      snapshot: {
        status: "captured",
        fingerprint: contentFingerprint(content),
        artifactPaths,
        revision: branch,
        fetchedAt: new Date().toISOString(),
      },
    };
  } catch (error) {
    const content = candidate.content ?? candidate.summary ?? "";
    return {
      ...candidate,
      snapshot: {
        status: "metadata_only",
        fingerprint: contentFingerprint(content),
        artifactPaths: [],
        error: error.message,
      },
    };
  }
}

export async function ingestCandidate(candidate, { fetchImpl = globalThis.fetch } = {}) {
  const hydrated = await hydrateCandidate(candidate, { fetchImpl });
  return { genome: candidateToSkillGenome(hydrated), hydrated };
}
