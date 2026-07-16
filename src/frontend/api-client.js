async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.error;
    const error = new Error(
      typeof detail === "object" ? detail.message : detail || `API ${response.status}`,
    );
    error.code = typeof detail === "object" ? detail.code : `HTTP_${response.status}`;
    error.retryable = Boolean(typeof detail === "object" && detail.retryable);
    error.details = typeof detail === "object" ? detail.details : {};
    throw error;
  }
  return payload;
}

export async function apiHealth() {
  return request("/api/health");
}

export async function listDiscoveryConnectors() {
  return request("/api/discovery/connectors");
}

export async function searchDiscovery(query, sourceIds) {
  return request("/api/discovery/search", {
    method: "POST",
    body: JSON.stringify({ query, sourceIds }),
  });
}

export async function importDiscoveryCandidate(candidate) {
  return request("/api/discovery/import", {
    method: "POST",
    body: JSON.stringify({ candidate }),
  });
}

export async function storeSkillGenome(genome, sourceId = "manual") {
  return request("/api/skills", {
    method: "POST",
    body: JSON.stringify({ genome, sourceId }),
  });
}

export async function convertMaterial(payload) {
  return request("/api/materials/convert", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSkills(status = null) {
  return request(`/api/skills${status ? `?status=${encodeURIComponent(status)}` : ""}`);
}

export async function listInitialSkills() {
  return request("/api/library/initial");
}

export async function benchmarkSkill(skillId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}/benchmark`, { method: "POST", body: "{}" });
}

export async function promoteSkill(skillId, evaluationId, expectedSkillVersionId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}/promote`, {
    method: "POST",
    body: JSON.stringify({ evaluationId, expectedSkillVersionId }),
  });
}

export async function deleteSkill(skillId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}`, { method: "DELETE" });
}

export async function getEvolutionCatalog() {
  return request("/api/evolution/catalog");
}

export async function createEvolutionRun({ seed, skillId, modeId }) {
  return request("/api/runs", {
    method: "POST",
    body: JSON.stringify({ seed, skillId, modeId }),
  });
}

export async function getEvolutionRun(runId) {
  return request(`/api/runs/${encodeURIComponent(runId)}`);
}

export async function selectEvolutionNode(runId, nodeId, expectedRevision) {
  return request(`/api/runs/${encodeURIComponent(runId)}/select-node`, {
    method: "POST",
    body: JSON.stringify({ nodeId, expectedRevision }),
  });
}

export async function resolveEvolutionNode(runId, expectedRevision) {
  return request(`/api/runs/${encodeURIComponent(runId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({ expectedRevision }),
  });
}

export async function chooseEvolutionMutation(runId, mutationId, expectedRevision) {
  return request(`/api/runs/${encodeURIComponent(runId)}/choose-mutation`, {
    method: "POST",
    body: JSON.stringify({ mutationId, expectedRevision }),
  });
}

export async function skipEvolutionMutation(runId, expectedRevision) {
  return request(`/api/runs/${encodeURIComponent(runId)}/skip-mutation`, {
    method: "POST",
    body: JSON.stringify({ expectedRevision }),
  });
}
