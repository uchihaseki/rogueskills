async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `API ${response.status}`);
  return payload;
}

export async function apiHealth() {
  return request("/api/health");
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

export async function listSkills(status = null) {
  return request(`/api/skills${status ? `?status=${encodeURIComponent(status)}` : ""}`);
}

export async function listInitialSkills() {
  return request("/api/library/initial");
}

export async function benchmarkSkill(skillId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}/benchmark`, { method: "POST", body: "{}" });
}

export async function promoteSkill(skillId, evaluationId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}/promote`, {
    method: "POST",
    body: JSON.stringify({ evaluationId }),
  });
}

export async function deleteSkill(skillId) {
  return request(`/api/skills/${encodeURIComponent(skillId)}`, { method: "DELETE" });
}
