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
  sourceId: string
  state: string
  count?: number
  message?: string
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
  [key: string]: unknown
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
    mode: 'capability-simulation-v1'
    runtimeVerified: false
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
