import type {
  AgentPreset,
  AgentPresetExportTarget,
  DiscoveryCandidate,
  DiscoveryCandidatePreview,
  DiscoveryImportBatch,
  DiscoverySearchSnapshot,
  EvolutionCatalog,
  FinanceCasePreflight,
  FinanceCaseRun,
  FinanceBootstrapResult,
  NormalizerStatus,
  ProviderStatus,
  RunRecord,
  SearchProvider,
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

export const listDiscoveryProviders = () =>
  request<{ providers: SearchProvider[] }>('/api/discovery/providers')

export const createDiscoverySearchRun = (payload: {
  query: string
  providerIds: string[]
  scopeIds?: string[]
  includeLocalExamples?: boolean
}) => request<DiscoverySearchSnapshot>('/api/discovery/search-runs', {
  method: 'POST',
  body: JSON.stringify({
    query: payload.query,
    providerIds: payload.providerIds,
    scopeIds: payload.scopeIds ?? ['all_web_skills'],
    includeLocalExamples: payload.includeLocalExamples ?? false,
    filters: {},
  }),
})

export const getDiscoverySearchRun = (runId: string) =>
  request<DiscoverySearchSnapshot>(`/api/discovery/search-runs/${encodeURIComponent(runId)}`)

export const discoveryEventsUrl = (runId: string) =>
  apiPath(`/api/discovery/search-runs/${encodeURIComponent(runId)}/events`)

export const previewDiscoveryCandidate = (candidateId: string) =>
  request<DiscoveryCandidatePreview>(`/api/discovery/candidates/${encodeURIComponent(candidateId)}/preview`)

export const importDiscoveryBatch = (payload: {
  searchRunId: string
  candidateIds: string[]
  expectedRunRevision: number
  acknowledgedWarnings: Array<{ candidateId: string; code: string }>
}) => request<DiscoveryImportBatch>('/api/discovery/import-batches', {
  method: 'POST',
  headers: { 'Idempotency-Key': crypto.randomUUID() },
  body: JSON.stringify(payload),
})

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

export const bootstrapFinanceSkills = (payload: {
  maxCommunitySkills?: number
  sopIds?: string[]
  autoPromote?: boolean
} = {}) => request<FinanceBootstrapResult>('/api/scenarios/finance/bootstrap', {
  method: 'POST',
  body: JSON.stringify({
    maxCommunitySkills: payload.maxCommunitySkills ?? 2,
    sopIds: payload.sopIds,
    autoPromote: payload.autoPromote ?? true,
  }),
})

export const storeSkillGenome = (
  genome: SkillGenome,
  sourceId = 'manual',
  snapshotContent?: string,
) =>
  request<{ skill: SkillRecord }>('/api/skills', {
    method: 'POST',
    body: JSON.stringify({ genome, sourceId, snapshotContent }),
  })

export const convertMaterial = (payload: {
  title: string
  content: string
  license: string
  kind?: string
  source: {
    platform: string
    author: string
    url?: string
    revision?: string
    artifactPaths?: string[]
    capturedAt?: string
  }
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

export const startAutomaticEvolution = (runId: string, payload: {
  expectedRevision: number
  selectedMonsterIds: string[]
  projectName: string
  projectDescription: string
  scenario: string
}) => request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/auto`, {
  method: 'POST', body: JSON.stringify(payload),
})

export const createAgentPreset = (runId: string, payload: {
  expectedRevision: number
  projectName: string
  projectDescription: string
  scenario: string
}) => request<{ preset: AgentPreset; created: boolean }>(
  `/api/runs/${encodeURIComponent(runId)}/agent-preset`,
  { method: 'POST', body: JSON.stringify(payload) },
)

export const listAgentPresets = () =>
  request<{ presets: AgentPreset[] }>('/api/agent-presets')

export const getAgentPreset = (presetId: string) =>
  request<{ preset: AgentPreset }>(`/api/agent-presets/${encodeURIComponent(presetId)}`)

export async function downloadAgentPreset(
  presetId: string,
  target: AgentPresetExportTarget,
): Promise<void> {
  const response = await fetch(
    apiPath(`/api/agent-presets/${encodeURIComponent(presetId)}/export/${encodeURIComponent(target)}`),
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as ErrorPayload
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
  const blobUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = `${presetId}-${target}.zip`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(blobUrl)
}

export const financeCasePreflight = () =>
  request<FinanceCasePreflight>('/api/finance/cases/preflight')

export const listFinanceCases = (limit = 20) =>
  request<{ cases: FinanceCaseRun[] }>(`/api/finance/cases?limit=${limit}`)

export const createFinanceCase = (payload: {
  ticker: string
  skillId: string
  asOfDate?: string
  mode?: 'live' | 'verified_replay'
  replayCaseId?: string
  autoEvolve?: boolean
}) => request<{ case: FinanceCaseRun }>('/api/finance/cases', {
  method: 'POST',
  body: JSON.stringify({
    ticker: payload.ticker,
    skillId: payload.skillId,
    asOfDate: payload.asOfDate,
    mode: payload.mode ?? 'live',
    replayCaseId: payload.replayCaseId,
    autoEvolve: payload.autoEvolve ?? true,
  }),
})

export const getFinanceCase = (caseId: string) =>
  request<{ case: FinanceCaseRun }>(`/api/finance/cases/${encodeURIComponent(caseId)}`)

export const getFinanceCaseAgentPreset = (caseId: string) =>
  request<{ preset: AgentPreset }>(`/api/finance/cases/${encodeURIComponent(caseId)}/agent-preset`)
