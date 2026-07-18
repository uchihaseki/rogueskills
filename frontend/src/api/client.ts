import type {
  DiscoveryCandidate,
  EvolutionCatalog,
  NormalizerStatus,
  ProviderStatus,
  RunRecord,
  SkillGenome,
  SkillRecord,
  SourceConnector,
} from '@/types/domain'
import { ApiError } from '@/types/domain'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
const apiPath = (path: string) => {
  const suffix = path.replace(/^\/api/, '')
  return API_BASE.endsWith('/api') ? `${API_BASE}${suffix}` : `${API_BASE}/api${suffix}`
}

interface ErrorPayload {
  error?: string | {
    code?: string
    message?: string
    retryable?: boolean
    details?: Record<string, unknown>
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(apiPath(path), {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })
  const payload = await response.json().catch(() => ({})) as T & ErrorPayload
  if (!response.ok) {
    const detail = payload.error
    if (detail && typeof detail === 'object') {
      throw new ApiError(
        detail.message ?? `API ${response.status}`,
        detail.code ?? `HTTP_${response.status}`,
        Boolean(detail.retryable),
        detail.details ?? {},
      )
    }
    throw new ApiError(detail || `API ${response.status}`, `HTTP_${response.status}`)
  }
  return payload
}

export const apiHealth = () => request<{ status: string; materialNormalizer: NormalizerStatus }>('/api/health')

export const listDiscoveryConnectors = () =>
  request<{ connectors: SourceConnector[] }>('/api/discovery/connectors')

export const searchDiscovery = (query: string, sourceIds: string[]) =>
  request<{ results: DiscoveryCandidate[]; status: ProviderStatus[] }>('/api/discovery/search', {
    method: 'POST',
    body: JSON.stringify({ query, sourceIds }),
  })

export const importDiscoveryCandidate = (candidate: DiscoveryCandidate) =>
  request<{ skill: SkillRecord }>('/api/discovery/import', {
    method: 'POST',
    body: JSON.stringify({ candidate }),
  })

export const storeSkillGenome = (genome: SkillGenome, sourceId = 'manual') =>
  request<{ skill: SkillRecord }>('/api/skills', {
    method: 'POST',
    body: JSON.stringify({ genome, sourceId }),
  })

export const convertMaterial = (payload: {
  title: string
  content: string
  license: string
  source: { platform: string; author: string }
}) => request<{ genome: SkillGenome; normalization: NormalizerStatus }>('/api/materials/convert', {
  method: 'POST',
  body: JSON.stringify(payload),
})

export const listSkills = (status: string | null = null) =>
  request<{ skills: SkillRecord[] }>(`/api/skills${status ? `?status=${encodeURIComponent(status)}` : ''}`)

export const listInitialSkills = () => request<{ skills: SkillRecord[] }>('/api/library/initial')

export const benchmarkSkill = (skillId: string) =>
  request<{ result: { passed: boolean; score: number } }>(`/api/skills/${encodeURIComponent(skillId)}/benchmark`, {
    method: 'POST',
    body: '{}',
  })

export const promoteSkill = (skillId: string, evaluationId: string, expectedSkillVersionId: string) =>
  request(`/api/skills/${encodeURIComponent(skillId)}/promote`, {
    method: 'POST',
    body: JSON.stringify({ evaluationId, expectedSkillVersionId }),
  })

export const deleteSkill = (skillId: string) =>
  request(`/api/skills/${encodeURIComponent(skillId)}`, { method: 'DELETE' })

export const getEvolutionCatalog = () => request<EvolutionCatalog>('/api/evolution/catalog')

export const createEvolutionRun = (payload: { seed: string; skillId: string; modeId: string }) =>
  request<RunRecord>('/api/runs', { method: 'POST', body: JSON.stringify(payload) })

export const getEvolutionRun = (runId: string) =>
  request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}`)

export const selectEvolutionNode = (runId: string, nodeId: string, expectedRevision: number) =>
  request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/select-node`, {
    method: 'POST', body: JSON.stringify({ nodeId, expectedRevision }),
  })

export const resolveEvolutionNode = (runId: string, expectedRevision: number) =>
  request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/resolve`, {
    method: 'POST', body: JSON.stringify({ expectedRevision }),
  })

export const chooseEvolutionMutation = (
  runId: string,
  mutationId: string,
  expectedRevision: number,
) => request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/choose-mutation`, {
  method: 'POST', body: JSON.stringify({ mutationId, expectedRevision }),
})

export const skipEvolutionMutation = (runId: string, expectedRevision: number) =>
  request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/skip-mutation`, {
    method: 'POST', body: JSON.stringify({ expectedRevision }),
  })
