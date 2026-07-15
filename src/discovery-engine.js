import {
  DOMAIN_SYNONYMS,
  LOCAL_DISCOVERY_INDEX,
  SOURCE_CONNECTORS,
} from "./discovery-catalog.js";
import { clamp, hashString, round } from "./random.js";

const FILTER_PATTERN = /\b(source|type|license|tag):(?:"([^"]+)"|(\S+))/gi;
const HIGH_RISK_PATTERNS = [
  { pattern: /ignore\s+(all\s+)?previous\s+instructions?/i, reason: "包含提示注入式指令" },
  { pattern: /忽略(?:以上|之前|前面).{0,8}(?:指令|要求|规则)/i, reason: "包含提示注入式指令" },
  { pattern: /\brm\s+-rf\s+[/~*]/i, reason: "包含破坏性删除命令" },
  { pattern: /(?:curl|wget)[^\n|]{0,180}\|\s*(?:sh|bash)/i, reason: "包含远程下载并执行命令" },
  { pattern: /\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*["'][^"']{8,}/i, reason: "疑似包含明文 Secret" },
];
const MEDIUM_RISK_PATTERNS = [
  { pattern: /\bsudo\b/i, reason: "包含提权命令" },
  { pattern: /\beval\s*\(/i, reason: "包含动态代码执行" },
  { pattern: /disable.{0,20}(?:security|sandbox|guard)/i, reason: "建议关闭安全控制" },
  { pattern: /关闭.{0,12}(?:安全|沙箱|权限检查)/i, reason: "建议关闭安全控制" },
];

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

export function tokenize(value) {
  const normalized = normalizeText(value);
  if (!normalized) return [];

  const tokens = new Set(normalized.split(/\s+/).filter(Boolean));
  const cjkGroups = normalized.match(/[\p{Script=Han}]{2,}/gu) ?? [];

  for (const group of cjkGroups) {
    for (let index = 0; index < group.length - 1; index += 1) {
      tokens.add(group.slice(index, index + 2));
    }
  }

  return [...tokens];
}

export function parseSearchQuery(query) {
  const filters = { source: [], type: [], license: [], tag: [] };
  let match;

  while ((match = FILTER_PATTERN.exec(query)) !== null) {
    filters[match[1].toLowerCase()].push((match[2] ?? match[3]).toLowerCase());
  }

  return {
    text: query.replace(FILTER_PATTERN, " ").replace(/\s+/g, " ").trim(),
    filters,
  };
}

export function expandQueryTerms(query) {
  const base = tokenize(query);
  const expanded = new Set(base);

  for (const term of base) {
    for (const synonym of DOMAIN_SYNONYMS[term] ?? []) {
      tokenize(synonym).forEach((item) => expanded.add(item));
    }
  }

  return [...expanded];
}

export function scanContent(content, { license = "unknown" } = {}) {
  const reasons = [];
  let level = "low";

  for (const item of HIGH_RISK_PATTERNS) {
    if (item.pattern.test(content)) reasons.push(item.reason);
  }

  if (reasons.length) {
    level = "high";
  } else {
    for (const item of MEDIUM_RISK_PATTERNS) {
      if (item.pattern.test(content)) reasons.push(item.reason);
    }
    if (reasons.length) level = "medium";
  }

  if (!license || license === "unknown" || license === "NOASSERTION") {
    reasons.push("许可证未知，不能直接发布");
    if (level === "low") level = "medium";
  }

  return {
    level,
    reasons: [...new Set(reasons)],
    executableContent: /```(?:bash|sh|shell|powershell|python|javascript|js)\b/i.test(content),
  };
}

function calculateConvertibility(candidate) {
  const content = `${candidate.name}\n${candidate.summary}\n${candidate.content ?? ""}`;
  let score = 18;

  if (/(?:workflow|steps?|procedure|流程|步骤|操作)/i.test(content)) score += 24;
  if (/(?:goal|objective|目的|目标)/i.test(content)) score += 14;
  if (/(?:input|输入|前置条件|prerequisite)/i.test(content)) score += 10;
  if (/(?:output|结果|输出|deliverable)/i.test(content)) score += 10;
  if (/(?:constraint|must|never|安全|约束|必须|不得|禁止)/i.test(content)) score += 14;
  if (/(?:test|acceptance|example|验收|示例)/i.test(content)) score += 10;

  return clamp(score, 0, 100);
}

function calculateFreshness(updatedAt) {
  if (!updatedAt) return 35;
  const ageDays = Math.max(0, (Date.now() - new Date(updatedAt).getTime()) / 86_400_000);
  if (ageDays <= 30) return 100;
  if (ageDays <= 180) return 82;
  if (ageDays <= 365) return 66;
  if (ageDays <= 730) return 48;
  return 30;
}

function calculateRelevance(candidate, queryText) {
  const terms = expandQueryTerms(queryText);
  if (!terms.length) return 60;

  const fields = [
    [normalizeText(candidate.name), 5],
    [normalizeText((candidate.tags ?? []).join(" ")), 4],
    [normalizeText(candidate.summary), 2.5],
    [normalizeText(candidate.content ?? ""), 1],
  ];
  let matchedWeight = 0;
  let possibleWeight = 0;

  for (const term of terms) {
    const normalizedTerm = normalizeText(term);
    let best = 0;

    for (const [field, weight] of fields) {
      if (field.includes(normalizedTerm)) best = Math.max(best, weight);
    }

    matchedWeight += best;
    possibleWeight += 5;
  }

  const exactBonus = normalizeText(`${candidate.name} ${candidate.summary}`).includes(normalizeText(queryText))
    ? 18
    : 0;
  return clamp(round((matchedWeight / Math.max(1, possibleWeight)) * 92 + exactBonus), 0, 100);
}

function calculateQuality(candidate) {
  const completeness = candidate.signals?.completeness ?? calculateConvertibility(candidate);
  const stars = candidate.signals?.stars ?? 0;
  const community = clamp(Math.log10(stars + 1) * 22, 0, 100);
  const documentation = candidate.content?.length > 800 ? 90 : candidate.content?.length > 200 ? 70 : 45;
  return round(completeness * 0.55 + community * 0.2 + documentation * 0.25);
}

function calculateTrust(candidate) {
  let trust = candidate.signals?.official ? 92 : candidate.sourceId === "builtin" ? 78 : 55;
  if (candidate.license && !["unknown", "NOASSERTION"].includes(candidate.license)) trust += 6;
  if (candidate.url?.startsWith("https://")) trust += 2;
  return clamp(trust, 0, 100);
}

function matchesFilters(candidate, filters) {
  if (filters.source.length && !filters.source.includes(candidate.sourceId.toLowerCase())) return false;
  if (filters.type.length && !filters.type.includes(candidate.kind.toLowerCase())) return false;
  if (filters.license.length && !filters.license.includes(String(candidate.license).toLowerCase())) return false;
  if (
    filters.tag.length &&
    !filters.tag.every((tag) => candidate.tags?.some((candidateTag) => candidateTag.toLowerCase() === tag))
  ) {
    return false;
  }
  return true;
}

export function rankCandidate(candidate, query) {
  const parsed = parseSearchQuery(query);
  const risk = scanContent(candidate.content ?? candidate.summary ?? "", { license: candidate.license });
  const relevance = calculateRelevance(candidate, parsed.text);
  const quality = calculateQuality(candidate);
  const trust = calculateTrust(candidate);
  const convertibility = calculateConvertibility(candidate);
  const freshness = calculateFreshness(candidate.updatedAt);
  const riskPenalty = risk.level === "high" ? 38 : risk.level === "medium" ? 14 : 0;
  const total = clamp(
    round(
      relevance * 0.35 +
        quality * 0.2 +
        trust * 0.2 +
        convertibility * 0.15 +
        freshness * 0.1 -
        riskPenalty,
    ),
    0,
    100,
  );

  return {
    ...candidate,
    risk,
    ranking: { relevance, quality, trust, convertibility, freshness, riskPenalty, total },
  };
}

function canonicalKey(candidate) {
  if (candidate.url) return normalizeText(candidate.url.replace(/\/?$/, ""));
  return `${normalizeText(candidate.name)}|${normalizeText(candidate.author ?? "")}`;
}

export function deduplicateCandidates(candidates) {
  const groups = new Map();

  for (const candidate of candidates) {
    const key = canonicalKey(candidate);
    const existing = groups.get(key);
    if (!existing || (candidate.ranking?.total ?? 0) > (existing.ranking?.total ?? 0)) {
      groups.set(key, candidate);
    }
  }

  return [...groups.values()];
}

export function searchLocalIndex(query) {
  const parsed = parseSearchQuery(query);
  return LOCAL_DISCOVERY_INDEX.map((candidate) => rankCandidate(candidate, query))
    .filter((candidate) => matchesFilters(candidate, parsed.filters))
    .filter((candidate) => !parsed.text || candidate.ranking.relevance >= 12)
    .sort((left, right) => right.ranking.total - left.ranking.total);
}

function inferKind(item) {
  const text = normalizeText(`${item.name} ${item.description ?? ""} ${(item.topics ?? []).join(" ")}`);
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

export function contentFingerprint(content) {
  return hashString(String(content)).toString(16).padStart(8, "0");
}

function sectionKind(heading) {
  if (/(?:workflow|steps?|procedure|process|操作|步骤|流程|checklist|清单)/i.test(heading)) return "steps";
  if (/(?:constraint|safety|rules?|注意|约束|安全|禁止|要求)/i.test(heading)) return "constraints";
  if (/(?:input|prerequisite|输入|前置)/i.test(heading)) return "inputs";
  if (/(?:output|deliverable|输出|交付|结果)/i.test(heading)) return "outputs";
  if (/(?:goal|objective|purpose|目标|目的)/i.test(heading)) return "goal";
  if (/(?:example|示例)/i.test(heading)) return "examples";
  return "other";
}

function cleanListItem(line) {
  return line.replace(/^\s*(?:[-*+] |\d+[.)]\s*)/, "").trim();
}

function extractTools(content) {
  const knownTools = [
    "Browser",
    "Search",
    "OCR",
    "API",
    "SQL",
    "GitHub",
    "Slack",
    "Jira",
    "Python",
    "Playwright",
    "Excel",
  ];
  return knownTools.filter((tool) => new RegExp(`\\b${tool}\\b`, "i").test(content));
}

function slugify(value) {
  const ascii = String(value)
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return ascii.length >= 3 ? ascii : `skill-${contentFingerprint(value)}`;
}

function inferCapabilities(content, tools, completeness) {
  const text = String(content);
  const levels = {
    quality: 38 + completeness * 0.32,
    robustness: 34 + completeness * 0.18,
    speed: 45,
    efficiency: 45,
    security: 28,
    vision: 10,
    structure: 34,
  };
  const evidence = Object.fromEntries(Object.keys(levels).map((stat) => [stat, []]));

  if (/(?:validate|verify|校验|验证|检查)/i.test(text)) {
    levels.quality += 9;
    levels.robustness += 6;
    evidence.quality.push("材料包含验证步骤");
  }
  if (/(?:retry|fallback|rollback|重试|回退|降级|异常)/i.test(text)) {
    levels.robustness += 18;
    evidence.robustness.push("材料包含失败恢复策略");
  }
  if (/(?:parallel|cache|batch|并行|缓存|批量)/i.test(text)) {
    levels.speed += 14;
    levels.efficiency += 8;
    evidence.speed.push("材料包含吞吐优化策略");
  }
  if (/(?:budget|token|cost|limit|预算|成本|限额)/i.test(text)) {
    levels.efficiency += 16;
    evidence.efficiency.push("材料声明资源或成本限制");
  }
  if (/(?:never|must not|permission|injection|secret|不得|禁止|权限|敏感|安全)/i.test(text)) {
    levels.security += 24;
    evidence.security.push("材料包含安全或权限约束");
  }
  if (/(?:ocr|screenshot|image|vision|截图|图片|视觉)/i.test(text) || tools.includes("OCR")) {
    levels.vision += 48;
    evidence.vision.push("材料包含视觉处理能力");
  }
  if (/(?:schema|json|structured|checklist|字段|结构化|清单)/i.test(text)) {
    levels.structure += 24;
    evidence.structure.push("材料声明结构化输出或检查清单");
  }

  const labels = {
    quality: "Task Quality",
    robustness: "Robustness",
    speed: "Execution Speed",
    efficiency: "Cost Efficiency",
    security: "Safety & Permission",
    vision: "Visual Understanding",
    structure: "Structured Output",
  };

  return Object.entries(levels).map(([id, level]) => ({
    id,
    label: labels[id],
    level: round(clamp(level, 0, 100)),
    tags: [id],
    evidence: evidence[id],
  }));
}

function parseFrontmatter(content) {
  const match = String(content).match(/^---\s*\n([\s\S]*?)\n---\s*\n?/);
  if (!match) return { attributes: {}, body: String(content) };

  const attributes = {};
  for (const line of match[1].split("\n")) {
    const entry = line.match(/^([a-zA-Z][\w-]*):\s*(.+)$/);
    if (!entry) continue;
    attributes[entry[1]] = entry[2].trim().replace(/^(["'])(.*)\1$/, "$2");
  }

  return { attributes, body: String(content).slice(match[0].length) };
}

export function convertMaterialToSkill({
  title,
  content,
  source = { platform: "Manual SOP", url: null, author: "Unknown" },
  license = "unknown",
  kind = "sop",
}) {
  const document = parseFrontmatter(content ?? "");
  const effectiveLicense = document.attributes.license || license;
  const normalizedTitle =
    title?.trim() ||
    document.attributes.name ||
    document.body.match(/^#\s+(.+)$/m)?.[1]?.trim() ||
    "Untitled Skill";
  const lines = document.body.replace(/\r\n/g, "\n").split("\n");
  const sections = { steps: [], constraints: [], inputs: [], outputs: [], examples: [], goal: [] };
  let currentSection = "other";

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    const heading = line.match(/^#{1,6}\s+(.+)$/)?.[1];
    if (heading) {
      currentSection = sectionKind(heading);
      continue;
    }

    const numbered = /^\d+[.)]\s+/.test(line);
    const bullet = /^[-*+]\s+/.test(line);
    const item = cleanListItem(line);

    if (numbered || (bullet && currentSection === "steps")) {
      sections.steps.push(item);
      continue;
    }

    if (bullet && ["constraints", "inputs", "outputs", "examples"].includes(currentSection)) {
      sections[currentSection].push(item);
      continue;
    }

    if (currentSection === "goal") sections.goal.push(item);
    if (currentSection === "inputs") sections.inputs.push(item);
    if (currentSection === "outputs") sections.outputs.push(item);
    if (currentSection === "examples") sections.examples.push(item);
    if (currentSection === "constraints") sections.constraints.push(item);

    if (/(?:必须|不得|禁止|切勿|\bmust\b|\bnever\b|\bshould not\b)/i.test(item)) {
      sections.constraints.push(item);
    }
  }

  if (!sections.steps.length) {
    sections.steps = lines
      .map((line) => line.trim())
      .filter((line) => /^[-*+]\s+/.test(line))
      .map(cleanListItem)
      .slice(0, 12);
  }

  const firstParagraph = lines.find((line) => {
    const trimmed = line.trim();
    return trimmed && !trimmed.startsWith("#") && !/^[-*+\d]/.test(trimmed);
  });
  const description = (
    document.attributes.description ||
    sections.goal.join(" ") ||
    firstParagraph ||
    `由 ${kind} 材料转换的候选 Skill`
  ).slice(0, 360);
  const risk = scanContent(content, { license: effectiveLicense });
  const fingerprint = contentFingerprint(content);
  const completeness = clamp(
    20 +
      Math.min(36, sections.steps.length * 7) +
      Math.min(16, sections.constraints.length * 4) +
      (sections.goal.length || firstParagraph ? 12 : 0) +
      (sections.inputs.length ? 8 : 0) +
      (sections.outputs.length ? 8 : 0) +
      (sections.examples.length ? 6 : 0),
    0,
    100,
  );

  const tools = extractTools(content);

  return {
    schemaVersion: "1.0.0",
    id: `${slugify(normalizedTitle)}-${fingerprint.slice(0, 6)}`,
    name: normalizedTitle,
    description,
    status: "quarantine",
    metadata: {
      category: kind,
      license: effectiveLicense,
      tags: [...new Set([...tokenize(normalizedTitle).slice(0, 6), "generated-from-material"])],
      completeness,
    },
    prompt: {
      role: `You are responsible for executing the ${normalizedTitle} workflow.`,
      objective: description,
      instruction: "Follow the workflow in order, respect every constraint, and return the declared output.",
    },
    workflow: {
      steps: [...new Set(sections.steps)].slice(0, 20).map((instruction, index) => ({
        id: `step-${index + 1}`,
        order: index + 1,
        instruction,
      })),
    },
    inputs: [...new Set(sections.inputs)].slice(0, 12),
    outputs: [...new Set(sections.outputs)].slice(0, 12),
    constraints: [...new Set(sections.constraints)].slice(0, 20),
    examples: [...new Set(sections.examples)].slice(0, 8),
    tools,
    capabilities: inferCapabilities(content, tools, completeness),
    testCases: [
      { id: "happy-path", purpose: "验证标准输入下能完整执行所有步骤", status: "draft" },
      { id: "missing-input", purpose: "验证输入缺失时不会臆造关键信息", status: "draft" },
      { id: "constraint-check", purpose: "验证高风险情况下仍遵守约束", status: "draft" },
    ],
    evaluation: {
      status: "not_run",
      requiredGates: ["static-safety", "license-review", "benchmark", "human-review"],
    },
    provenance: {
      platform: source.platform ?? "Manual SOP",
      url: source.url ?? null,
      author: source.author ?? "Unknown",
      revision: source.revision ?? null,
      artifactPaths: source.artifactPaths ?? [],
      fingerprint,
      capturedAt: source.capturedAt ?? new Date().toISOString(),
    },
    risk,
  };
}

export async function ingestCandidate(candidate, { fetchImpl = globalThis.fetch } = {}) {
  const hydrated = await hydrateCandidate(candidate, { fetchImpl });
  const hasSkillArtifact = hydrated.snapshot?.artifactPaths?.some((path) => /(^|\/)skill\.md$/i.test(path));
  const genome = convertMaterialToSkill({
    title: hasSkillArtifact ? null : hydrated.name,
    content: hydrated.content || hydrated.summary,
    kind: hydrated.kind,
    license: hydrated.license,
    source: {
      platform: hydrated.platform,
      url: hydrated.url,
      author: hydrated.author,
      revision: hydrated.snapshot?.revision,
      artifactPaths: hydrated.snapshot?.artifactPaths,
      capturedAt: hydrated.snapshot?.fetchedAt,
    },
  });

  const discoveredGenome = {
    ...genome,
    discovery: {
      candidateId: hydrated.id,
      sourceId: hydrated.sourceId,
      ranking: hydrated.ranking,
      snapshot: hydrated.snapshot,
    },
  };

  return { genome: discoveredGenome, hydrated };
}

export async function candidateToSkillGenome(candidate, options = {}) {
  return (await ingestCandidate(candidate, options)).genome;
}

export function connectorById(id) {
  return SOURCE_CONNECTORS.find((connector) => connector.id === id) ?? null;
}
