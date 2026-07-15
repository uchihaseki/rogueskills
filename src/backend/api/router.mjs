import { runAdmissionBenchmark, runScenarioBenchmark } from "../../core/benchmark/runner.js";
import { convertMaterialToSkill } from "../../core/discovery/engine.js";
import { validateSkillGenome } from "../../core/genome/skill-genome.js";
import { federatedSearch, ingestCandidate } from "../connectors/discovery-gateway.mjs";

function json(status, body, headers = {}) {
  return { status, body, headers: { "Content-Type": "application/json; charset=utf-8", ...headers } };
}

function routeMatch(pathname, pattern) {
  const pathParts = pathname.split("/").filter(Boolean);
  const patternParts = pattern.split("/").filter(Boolean);
  if (pathParts.length !== patternParts.length) return null;
  const params = {};

  for (let index = 0; index < patternParts.length; index += 1) {
    const expected = patternParts[index];
    const actual = pathParts[index];
    if (expected.startsWith(":")) params[expected.slice(1)] = decodeURIComponent(actual);
    else if (expected !== actual) return null;
  }
  return params;
}

export function createApiRouter({ repository, fetchImpl = globalThis.fetch, cacheTtlMs = 60_000 }) {
  const searchCache = new Map();

  return async function route({ method = "GET", url = "/", body = null }) {
    const requestUrl = new URL(url, "http://localhost");
    const pathname = requestUrl.pathname;

    try {
      if (method === "GET" && pathname === "/api/health") {
        return json(200, {
          status: "ok",
          service: "rogueskills-gateway",
          schemaVersion: "1.0.0",
          database: repository.databasePath,
        });
      }

      if (method === "POST" && pathname === "/api/discovery/search") {
        const query = String(body?.query ?? "").trim();
        const sourceIds = Array.isArray(body?.sourceIds) ? body.sourceIds : ["builtin", "github"];
        const cacheKey = JSON.stringify({ query, sourceIds });
        const cached = searchCache.get(cacheKey);
        if (cached && cached.expiresAt > Date.now()) {
          return json(200, { ...cached.value, cached: true });
        }
        const result = await federatedSearch(query, { sourceIds, fetchImpl });
        searchCache.set(cacheKey, { value: result, expiresAt: Date.now() + cacheTtlMs });
        return json(200, { ...result, cached: false });
      }

      if (method === "POST" && pathname === "/api/discovery/import") {
        if (!body?.candidate) return json(400, { error: "candidate is required" });
        const { genome, hydrated } = await ingestCandidate(body.candidate, { fetchImpl });
        const stored = repository.upsertSkill(genome, {
          sourceId: body.candidate.sourceId ?? "discovery",
          snapshotContent: hydrated.content ?? null,
        });
        return json(201, { skill: stored, validation: validateSkillGenome(genome) });
      }

      if (method === "POST" && pathname === "/api/materials/convert") {
        const genome = convertMaterialToSkill({
          title: body?.title,
          content: body?.content ?? "",
          source: body?.source,
          license: body?.license,
          kind: body?.kind,
        });
        return json(200, { genome, validation: validateSkillGenome(genome) });
      }

      if (method === "GET" && pathname === "/api/skills") {
        return json(200, { skills: repository.listSkills({ status: requestUrl.searchParams.get("status") }) });
      }

      if (method === "POST" && pathname === "/api/skills") {
        const validation = validateSkillGenome(body?.genome);
        if (!validation.valid) return json(422, { error: "Invalid Skill Genome", validation });
        const skill = repository.upsertSkill(body.genome, {
          sourceId: body.sourceId ?? "manual",
          snapshotContent: body.snapshotContent ?? null,
        });
        return json(201, { skill, validation });
      }

      if (method === "GET" && pathname === "/api/library/initial") {
        return json(200, { skills: repository.listInitialSkills() });
      }

      if (method === "POST" && pathname === "/api/benchmark/scenario") {
        return json(200, { result: runScenarioBenchmark(body) });
      }

      const skillParams = routeMatch(pathname, "/api/skills/:skillId");
      if (method === "GET" && skillParams) {
        const skill = repository.getSkill(skillParams.skillId);
        return skill ? json(200, { skill }) : json(404, { error: "Skill not found" });
      }
      if (method === "DELETE" && skillParams) {
        const deleted = repository.deleteSkill(skillParams.skillId);
        return deleted ? json(200, { deleted: true }) : json(404, { error: "Skill not found" });
      }

      const benchmarkParams = routeMatch(pathname, "/api/skills/:skillId/benchmark");
      if (method === "POST" && benchmarkParams) {
        const skill = repository.getSkill(benchmarkParams.skillId);
        if (!skill) return json(404, { error: "Skill not found" });
        const result = runAdmissionBenchmark(skill.genome);
        const evaluation = repository.recordEvaluation(
          skill.id,
          result.benchmarkId,
          result.split,
          result,
        );
        return json(200, { evaluation, result });
      }

      const promoteParams = routeMatch(pathname, "/api/skills/:skillId/promote");
      if (method === "POST" && promoteParams) {
        if (!body?.evaluationId) return json(400, { error: "evaluationId is required" });
        const skill = repository.promoteToInitial(promoteParams.skillId, body.evaluationId);
        return json(200, { skill });
      }

      const evaluationsParams = routeMatch(pathname, "/api/skills/:skillId/evaluations");
      if (method === "GET" && evaluationsParams) {
        return json(200, { evaluations: repository.listEvaluations(evaluationsParams.skillId) });
      }

      return json(404, { error: "API route not found" });
    } catch (error) {
      return json(400, { error: error.message });
    }
  };
}
