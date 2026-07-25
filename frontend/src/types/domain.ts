export type Dictionary<T> = Record<string, T>

export interface ApiErrorDetails {
  [key: string]: unknown
}

export class ApiError extends Error {
  code: string
  retryable: boolean
  details: ApiErrorDetails

  constructor(message: string, code = 'API_ERROR', retryable = false, details: ApiErrorDetails = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.retryable = retryable
    this.details = details
  }
}

export interface SkillMetadata {
  category: string
  completeness: number
  license: string
  [key: string]: unknown
}

export interface WorkflowStep {
  id: string
  order: number
  instruction: string
}

export interface SkillGenome {
  id: string
  name: string
  description: string
  schemaVersion: string
  status: string
  metadata: SkillMetadata
  tools: string[]
  constraints: string[]
  workflow: { steps: WorkflowStep[] }
  evaluation: { score?: number | null; requiredGates: string[] }
  risk: { level: string; reasons?: string[] }
  provenance?: Dictionary<unknown> & {
    platform?: string
    url?: string
    fingerprint?: string
  }
  discovery?: { candidateId?: string; [key: string]: unknown }
  repository?: RepositoryMetadata
  [key: string]: unknown
}

export interface SkillEvaluation {
  id: string
  benchmarkId: string
  passed: boolean
  score: number
  [key: string]: unknown
}

export interface RepositoryMetadata {
  id: string
  status: string
  currentVersionId: string
  versions: Array<{ id: string; version: number; [key: string]: unknown }>
  evaluations: SkillEvaluation[]
  snapshots: unknown[]
}

export interface SkillRecord {
  id: string
  name?: string
  sourceId?: string
  status: string
  currentVersionId: string
  genome: SkillGenome
  versions?: RepositoryMetadata['versions']
  evaluations?: SkillEvaluation[]
  snapshots?: unknown[]
  capabilityProfile?: Dictionary<number>
}

export interface SourceConnector {
  id: string
  shortName: string
  name: string
  description: string
  status: 'live' | 'beta' | 'planned' | string
  mode: string
}

export interface ProviderStatus {
  sourceId?: string
  providerId?: string
  state: string
  count?: number
  message?: string
}

export interface SearchProvider {
  id: 'github' | 'brave' | 'tavily' | 'exa' | string
  name: string
  shortName: string
  description: string
  configured: boolean
  available: boolean
  state: string
  capabilities: string[]
}

export interface DiscoverySearchRun {
  id: string
  query: string
  state: string
  providerIds: string[]
  scopeIds: string[]
  includeLocalExamples: boolean
  revision: number
  policyVersion: string
  counts: {
    sourceHits: number
    artifacts: number
    candidates: number
    recommended: number
    blocked: number
  }
  createdAt: string
  expiresAt: string
}

export interface DiscoveryQueryPlan {
  id: string
  text: string
  intent: string
}

export interface DiscoverySourceHit {
  id: string
  kind: string
  title: string
  url: string
  canonicalUrl: string
  publisher: string
  snippet?: string
  status: string
  error?: string
  discoveredAt: string
  artifactIds?: string[]
  discoveredBy: Array<{
    providerId: string
    queryId: string
    rank?: number
    snippet?: string
  }>
}

export interface DiscoveryEvent {
  eventId: number
  runId: string
  revision: number
  timestamp: string
  type: string
  payload: Record<string, unknown>
}

export interface DiscoveryCandidate {
  id: string
  sourceId: string
  platform: string
  kind: string
  name: string
  summary: string
  author: string
  updatedAt?: string
  license: string
  url?: string
  tags?: string[]
  signals?: { official?: boolean; stars?: number; [key: string]: unknown }
  ranking: {
    total: number
    relevance: number
    quality: number
    trust: number
    convertibility: number
  }
  risk?: { level: string; reasons: string[] }
  sourceHitId?: string
  sourceHitIds?: string[]
  artifactPath?: string
  discoveredBy?: DiscoverySourceHit['discoveredBy']
  selection?: {
    eligible: boolean
    recommended: boolean
    reasonCodes: string[]
  }
  previewState?: string
  snapshot?: {
    status: string
    fingerprint?: string | null
    artifactPaths?: string[]
    revision?: string
    fetchedAt?: string
  }
  [key: string]: unknown
}

export interface DiscoverySearchSnapshot {
  run: DiscoverySearchRun
  queries: DiscoveryQueryPlan[]
  providerStatus: ProviderStatus[]
  sources: DiscoverySourceHit[]
  candidates: DiscoveryCandidate[]
  eventsUrl?: string
}

export interface DiscoveryCandidatePreview {
  candidate: DiscoveryCandidate
  source: DiscoverySourceHit
  rawContent: string
  genome: SkillGenome
}

export interface DiscoveryImportBatch {
  batchId: string
  searchRunId: string
  summary: Record<'saved' | 'existing' | 'rejected' | 'failed', number>
  items: Array<{
    candidateId: string
    state: 'saved' | 'existing' | 'rejected' | 'failed'
    skillId?: string
    reasonCode?: string
    message?: string
  }>
  createdAt: string
}

export interface NormalizerStatus {
  configured: boolean
  model?: string
  provider?: string
  mode?: string
}

export interface Archetype {
  id: string
  name: string
  role: string
  description: string
  initialWeapons: string[]
  stats: Dictionary<number>
}

export interface RunMode {
  id: string
  name: string
  description: string
  weights: Dictionary<number>
}

export interface NodeType {
  name: string
  description: string
  symbol: string
}

export interface Monster {
  id: string
  name: string
  failureMode: string
  businessExample: string
  requirements: Dictionary<number>
  securityFloor?: number
}

export interface ScenarioMonster extends Monster {
  regionId: string
  regionName: string
}

export interface Mutation {
  id: string
  name: string
  category: string
  rarity: string
  tags: string[]
  effects: Dictionary<number>
  benefit: string
  tradeoff: string
  complexityCost: number
}

export interface Evolution {
  id: string
  name: string
  subtitle: string
  tagRequirements: Dictionary<number>
}

export interface RunNode {
  id: string
  type: string
  layer: number
  difficulty: number
  monsterId?: string | null
}

export interface RunRegion {
  act: number
  name: string
  description: string
  layers: RunNode[][]
}

export interface BenchmarkResult {
  kind?: string
  passed?: boolean
  coverage?: number
  threshold?: number
  quality?: number
  latency?: number
  computeCost?: number
  capability?: number
  difficulty?: number
  securityGatePassed?: boolean
  cases?: Array<{ label: string; score: number; passed: boolean }>
}

export interface EvolutionRun {
  id: string
  seed: string
  modeId: string
  archetypeId: string
  scenarioId?: string
  baseSkillId: string
  skillName?: string
  skillRole?: string
  skillDescription?: string
  status: string
  phase: 'choose_node' | 'encounter' | 'reward' | 'ended'
  actIndex: number
  layerIndex: number
  selectedNodeId?: string | null
  completedNodeIds: string[]
  map: RunRegion[]
  stability: number
  compute: number
  complexityUsed: number
  complexityMax: number
  stats: Dictionary<number>
  initialWeapons: string[]
  mutationIds: string[]
  evolutionIds: string[]
  currentDraft: string[]
  lastResult?: BenchmarkResult | null
  encounterHistory: Array<{ passed: boolean; [key: string]: unknown }>
  logs: Array<{ id: number; tone: string; message: string; act: number }>
  automation?: {
    status: 'running' | 'completed' | 'failed'
    stage: 'planning' | 'encounter' | 'mutation' | 'artifact' | 'ended'
    message: string
    selectedMonsterIds: string[]
    project: { name: string; description: string; scenario: string }
    completedNodes: number
    totalNodes: number
    progress: number
  }
}

export interface RunRecord {
  run: EvolutionRun
  revision: number
  baseSkillVersionId?: string
  artifact?: AgentPreset | null
}

export interface AgentPresetProject {
  name: string
  description: string
  scenario: string
}

export type AgentPresetExportTarget = 'codex' | 'claude-code' | 'universal'

export interface AgentPresetWorkflowStep {
  id: string
  order: number
  instruction: string
  tool?: string | null
  source: string
}

export interface AgentPreset {
  schemaVersion: '0.1.0'
  id: string
  version: 1
  status: 'candidate'
  createdAt: string
  project: AgentPresetProject
  sourceRun: {
    runId: string
    runRevision: number
    seed: string
    modeId: string
    baseSkillId: string
    baseSkillVersionId: string
    mutationIds: string[]
    evolutionIds: string[]
  }
  agent: { role: string; objective: string; instruction: string }
  primarySkill: {
    role: 'primary'
    skillId: string
    skillVersionId: string
    genome: SkillGenome
  }
  workflow: AgentPresetWorkflowStep[]
  tools: string[]
  rules: {
    constraints: string[]
    retry: string[]
    fallback: string[]
    outputValidation: string[]
  }
  runtimeDefaults: {
    maxTokens: number
    maxToolCalls: number
    timeoutMs: number
    priority: string
    enforceBudget: boolean
  }
  evaluationEvidence: {
    mode: 'capability-simulation-v1' | 'real-finance-case-v1'
    runtimeVerified: boolean
    sourceRunStatus: 'victory'
    objectiveScore: number
    encountersPassed: number
    encounterTotal: number
    finalStats: Dictionary<number>
    benchmarkIds: string[]
  }
  limitations: string[]
  digest: string
}

export interface FinanceBootstrapSkillResult {
  skillId?: string
  skillVersionId?: string
  name?: string
  title?: string
  sopId?: string
  status: string
  action?: string
  evaluation?: { score?: number; passed?: boolean; [key: string]: unknown } | null
  normalization?: NormalizerStatus
  candidate?: {
    id: string
    name: string
    url?: string
    license: string
    stars: number
    financeRanking?: {
      score: number
      matchedTerms: string[]
      [key: string]: unknown
    }
  }
  error?: { code: string; message: string }
}

export interface FinanceBootstrapResult {
  scenario: { id: string; name: string; description: string }
  model: NormalizerStatus
  queries: string[]
  providerStatus: ProviderStatus[]
  summary: {
    discovered: number
    metadataSelected: number
    hydrated: number
    communityStored: number
    sopsProcessed: number
    initialSkills: number
    rejected: number
  }
  community: FinanceBootstrapSkillResult[]
  sops: FinanceBootstrapSkillResult[]
  rejected: Array<{ stage: string; candidateId?: string; name?: string; reasons: string[] }>
  initialSkillIds: string[]
}

export interface EvolutionCatalog {
  archetypes: Dictionary<Archetype>
  evolutions: Evolution[]
  monsters: Dictionary<Monster>
  scenarioMonsters: Dictionary<ScenarioMonster[]>
  mutations: Mutation[]
  nodeTypes: Dictionary<NodeType>
  runModes: Dictionary<RunMode>
  statLabels: Dictionary<string>
}

export interface FinanceCaseSource {
  id: string
  provider: string
  title: string
  url: string
  fetchedAt: string
  sha256: string
  contentType: string
}

export interface FinanceCaseFact {
  id: string
  metric: string
  label: string
  value: number
  unit: string
  periodStart?: string | null
  periodEnd: string
  form: string
  filed: string
  factName: string
  sourceEvidenceId: string
  sourceUrl: string
}

export interface FinanceDerivedMetric {
  id: string
  label: string
  value: number
  unit: string
  formula: string
  inputFactIds: string[]
  evidenceIds: string[]
}

export interface FinanceCaseEvaluation {
  evaluationId: string
  benchmarkId: 'finance-real-case-v1'
  runtimeVerified: boolean
  passed: boolean
  score: number
  hardGatesPassed: boolean
  failedCaseIds: string[]
  summary: string
  cases: Array<{
    id: string
    label: string
    score: number
    weight: number
    passed: boolean
    hardGate: boolean
    details: string
    evidenceRefs: string[]
  }>
}

export interface FinanceResearchReport {
  id: string
  caseId: string
  stage: 'baseline' | 'evolved'
  generatedAt: string
  skillId: string
  skillVersionId: string
  company: { ticker: string; name: string; cik: number; [key: string]: unknown }
  asOfDate: string
  sources: FinanceCaseSource[]
  filings: Array<{ form: string; filed: string; reportDate: string; url: string }>
  facts: FinanceCaseFact[]
  derivedMetrics: FinanceDerivedMetric[]
  valuationScenarios: Array<{
    name: 'bear' | 'base' | 'bull'
    peMultiple: number
    impliedPriceByPe?: number | null
    fcfYield: number
    impliedPriceByFcf?: number | null
  }>
  warnings: Array<{ code: string; message: string }>
  narrative: {
    summary: string
    findings: Array<{
      id: string
      kind: 'fact' | 'inference' | 'assumption'
      claim: string
      evidenceIds: string[]
    }>
    risks: Array<{ id: string; risk: string; evidenceIds: string[] }>
    dataGaps: string[]
    conclusionBoundary: string
  }
}

export interface FinanceCaseRun {
  id: string
  ticker: string
  asOfDate: string
  mode: 'live' | 'verified_replay'
  replayCaseId?: string | null
  skillId: string
  baseSkillVersionId: string
  evolvedSkillVersionId?: string | null
  financeEvolutionRunId?: string | null
  agentPreset?: AgentPreset | null
  status: 'running' | 'succeeded' | 'failed'
  phase: string
  runtimeVerified: boolean
  baseline?: { report: FinanceResearchReport; evaluation: FinanceCaseEvaluation } | null
  mutation?: {
    id: string
    name: string
    reason: string
    tradeoff: string
    status: 'testing' | 'accepted' | 'rejected'
    genomePatch: Array<{ op: string; path: string; value?: unknown }>
  } | null
  evolved?: {
    report: FinanceResearchReport
    evaluation: FinanceCaseEvaluation
    accepted: boolean
  } | null
  comparison?: {
    baselineScore: number
    evolvedScore: number
    scoreDelta: number
    accepted: boolean
    baselineFailedCaseIds: string[]
    evolvedFailedCaseIds: string[]
  } | null
  finalReport?: FinanceResearchReport | null
  finalEvaluation?: FinanceCaseEvaluation | null
  createdAt: string
  completedAt?: string | null
  error?: { code: string; message: string; retryable: boolean } | null
}

export interface FinanceCasePreflight {
  ready: boolean
  analyst: NormalizerStatus
  sources: Array<{ id: string; name: string; configured: boolean; reachable?: boolean | null; state?: string }>
  runtime: string
}
