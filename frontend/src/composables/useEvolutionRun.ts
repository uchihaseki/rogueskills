import { computed, nextTick, reactive, ref, watch } from 'vue'
import {
  chooseEvolutionMutation,
  createCaseValidation,
  createAgentPreset,
  createEvolutionRun,
  downloadAgentPreset,
  getEvolutionCatalog,
  getEvolutionRun,
  getCaseValidation,
  listCaseValidationOptions,
  listInitialSkills,
  listRunCaseValidations,
  resolveEvolutionNode,
  selectEvolutionNode,
  skipEvolutionMutation,
  startAutomaticEvolution,
} from '@/api/client'
import type {
  AgentPreset,
  AgentPresetExportTarget,
  CaseValidation,
  CaseValidationOption,
  Evolution,
  EvolutionCatalog,
  EvolutionRun,
  RunNode,
  NodeRunRecord,
  RunRecord,
  SkillRecord,
} from '@/types/domain'
import { ApiError } from '@/types/domain'
import { loadJson, saveJson } from '@/utils'

const STORAGE_KEY = 'rogueskills.prototype.run.v1'
const SAVE_VERSION = 3
export const MAX_STABILITY = 12

interface SavedRun {
  saveVersion: number
  id: string
  revision: number
  actIndex: number
  seed: string
}

const emptyCatalog: EvolutionCatalog = {
  archetypes: {}, evolutions: [], monsters: {}, scenarioMonsters: {}, mutations: [], nodeTypes: {}, runModes: {}, statLabels: {},
}

const AUTO_ADVANCE_INTERVAL_MS = 420
const AWESOME_FINANCE_SOURCE_ID = 'awesome-finance-skills'
const RECOMMENDED_DEMO_SKILL_NAME = 'alphaear-signal-tracker'

const LEGACY_RUN_COPY: Array<[string, string]> = [
  ['脏数据史莱姆', '脏数据校验'],
  ['Dirty Data Validation', '脏数据校验'],
  ['字段变形怪', '字段漂移校验'],
  ['Schema Drift Validation', '字段漂移校验'],
  ['延迟潜伏者', '异步加载校验'],
  ['Async Loading Validation', '异步加载校验'],
  ['Schema 九头蛇', '多来源结构留出集'],
  ['Multi-source Schema Holdout', '多来源结构留出集'],
  ['Canvas 幽灵', '画布内容提取校验'],
  ['Canvas Extraction Validation', '画布内容提取校验'],
  ['超时魔像', '工具超时恢复'],
  ['Tool Timeout Recovery', '工具超时恢复'],
  ['批处理虫群', '批量并发压力测试'],
  ['Batch Concurrency Stress Test', '批量并发压力测试'],
  ['视觉巨像', '动态视觉提取留出集'],
  ['Dynamic Visual Extraction Holdout', '动态视觉提取留出集'],
  ['指令模仿怪', '提示词注入防护'],
  ['Prompt Injection Defense', '提示词注入防护'],
  ['权限骑士', '工具权限边界'],
  ['Tool Permission Boundary', '工具权限边界'],
  ['分布漂移兽', '分布漂移校验'],
  ['Distribution Shift Validation', '分布漂移校验'],
  ['影子发布者', '端到端生产留出集'],
  ['End-to-end Production Holdout', '端到端生产留出集'],
  ['过期财报小鬼', '财报时效校验'],
  ['Filing Recency Check', '财报时效校验'],
  ['会计口径镜像', '会计口径标准化'],
  ['Accounting Basis Normalization', '会计口径标准化'],
  ['盈利质量吸血虫', '盈利质量校验'],
  ['Earnings Quality Check', '盈利质量校验'],
  ['财报重述九头蛇', '财报重述一致性留出集'],
  ['Restatement Consistency Holdout', '财报重述一致性留出集'],
  ['估值倍数陷阱', '可比估值倍数校验'],
  ['Comparable Multiple Validation', '可比估值倍数校验'],
  ['假设迷雾', '估值假设披露校验'],
  ['Assumption Disclosure Check', '估值假设披露校验'],
  ['现金流海市蜃楼', '现金流勾稽校验'],
  ['Cash Flow Reconciliation', '现金流勾稽校验'],
  ['估值巨像', '估值敏感性留出集'],
  ['Valuation Sensitivity Holdout', '估值敏感性留出集'],
  ['来源冲突斯芬克斯', '来源冲突处理'],
  ['Source Conflict Resolution', '来源冲突处理'],
  ['周期切换熊', '周期切换压力测试'],
  ['Regime Shift Stress Test', '周期切换压力测试'],
  ['荐股模仿怪', '投资建议边界校验'],
  ['Investment Advice Boundary', '投资建议边界校验'],
  ['影子投委会', '端到端研究留出集'],
  ['End-to-end Research Holdout', '端到端研究留出集'],
  ['静态平原', '结构化提取'],
  ['Structured Extraction', '结构化提取'],
  ['动态森林', '动态内容处理'],
  ['Dynamic Content Handling', '动态内容处理'],
  ['对抗荒地', '安全与泛化'],
  ['Safety & Generalization', '安全与泛化'],
  ['披露数据区', '财务数据质量'],
  ['Financial Data Quality', '财务数据质量'],
  ['估值实验场', '估值能力评估'],
  ['Valuation Evaluation', '估值能力评估'],
  ['风险投委会', '风险与合规'],
  ['Risk & Compliance', '风险与合规'],
  ['地图 Seed', '运行种子'],
  ['Run Seed', '运行种子'],
  ['选择路线', '选择测试'],
  ['普通遭遇', '标准评估'],
  ['精英遭遇', '压力评估'],
  ['进化实验室', '候选优化生成'],
  ['Candidate Generator', '候选优化生成'],
  ['安全节点', '预算恢复'],
  ['Budget Recovery', '预算恢复'],
  ['隐藏验收', '隐藏留出集评估'],
  ['隐藏 Boss', '隐藏留出集评估'],
  ['Hidden Holdout', '隐藏留出集评估'],
  ['Boss', '隐藏留出集评估'],
  ['Stability', '失败预算'],
  ['Failure Budget', '失败预算'],
  ['Compute Budget', '算力预算'],
  ['Complexity Budget', '复杂度预算'],
  ['武器进化', '能力组合'],
  ['Capability Bundle', '能力组合'],
  ['Mutation Draft', '候选优化项草案'],
  ['Candidate Change Draft', '候选优化项草案'],
  ['Mutation', '候选优化项'],
  ['Candidate Change', '候选优化项'],
  ['当前构筑', '当前候选配置'],
  ['Candidate 配置', '候选配置'],
  ['自动进化', '自动评估运行'],
  ['Evaluation Run', '评估运行'],
  ['Evaluation Plan', '评估计划'],
  ['目标怪物', '目标失败模式'],
  ['Failure Mode', '失败模式'],
  ['下一场遭遇', '下一个评估'],
  ['第一场遭遇', '第一个评估'],
  ['进化分支死亡', '评估运行失败'],
  ['项目产物', '候选智能体预设'],
  ['Candidate AgentPreset', '候选智能体预设'],
  ['AgentPreset', '智能体预设'],
  ['Candidate Run', '候选运行'],
  ['Benchmark', '基准评估'],
  ['Replay', '回放记录'],
  ['Coverage', '覆盖率'],
  ['Candidate', '候选'],
  ['Evaluation', '评估'],
  ['Skill', '技能'],
  ['Run', '运行'],
]

function displayRunText(value?: string | null): string {
  let normalized = value ?? ''
  for (const [legacy, current] of LEGACY_RUN_COPY) normalized = normalized.replaceAll(legacy, current)
  return normalized
    .replace(/第\s*(\d+)\s*幕/g, '阶段 $1')
    .replace(/Stage\s*(\d+)/gi, '阶段 $1')
}

const RUN_ENGLISH_NAMES: Record<string, string> = {
  结构化提取: 'Structured Extraction',
  动态内容处理: 'Dynamic Content Handling',
  安全与泛化: 'Safety & Generalization',
  财务数据质量: 'Financial Data Quality',
  估值能力评估: 'Valuation Evaluation',
  风险与合规: 'Risk & Compliance',
}

function runEnglishName(value?: string | null): string {
  return RUN_ENGLISH_NAMES[displayRunText(value)] ?? ''
}

function prioritizeDemoSkills(skills: SkillRecord[]): SkillRecord[] {
  return [...skills].sort((left, right) => {
    const leftName = left.name ?? left.genome.name
    const rightName = right.name ?? right.genome.name
    const leftRecommended = leftName === RECOMMENDED_DEMO_SKILL_NAME
    const rightRecommended = rightName === RECOMMENDED_DEMO_SKILL_NAME
    if (leftRecommended !== rightRecommended) return leftRecommended ? -1 : 1
    const leftAwesome = left.sourceId === AWESOME_FINANCE_SOURCE_ID
    const rightAwesome = right.sourceId === AWESOME_FINANCE_SOURCE_ID
    if (leftAwesome !== rightAwesome) return leftAwesome ? -1 : 1
    return 0
  })
}

export function useEvolutionRun() {
  const savedRun = ref<SavedRun | null>(loadJson<SavedRun | null>(STORAGE_KEY, null))
  if (savedRun.value?.saveVersion !== SAVE_VERSION) savedRun.value = null
  const run = ref<EvolutionRun | null>(null)
  const revision = ref<number | null>(null)
  const initialSkills = ref<SkillRecord[]>([])
  const libraryState = ref<'loading' | 'ready' | 'offline'>('loading')
  const selectedSkillId = ref<string | null>(null)
  const actionPending = ref(false)
  const loadingError = ref('')
  const seed = ref('ROGUE-0714')
  const selectedModeId = ref('')
  const selectedMonsterIds = ref<string[]>([])
  const completionVisible = ref(false)
  const mapActIndex = ref(0)
  const nodeDetailNodeId = ref<string | null>(null)
  const agentPreset = ref<AgentPreset | null>(null)
  const presetPending = ref(false)
  const presetError = ref('')
  const presetExportTarget = ref<AgentPresetExportTarget>('universal')
  const presetProjectName = ref('')
  const presetProjectDescription = ref('')
  const presetScenario = ref('')
  const presetRunId = ref('')
  const caseValidationOptions = ref<CaseValidationOption[]>([])
  const selectedReplayCaseId = ref('')
  const caseValidation = ref<CaseValidation | null>(null)
  const caseValidationPending = ref(false)
  const caseValidationError = ref('')
  const caseValidationDetailVisible = ref(false)
  const catalog = reactive<EvolutionCatalog>({ ...emptyCatalog })
  let autoAdvanceTimer: number | null = null
  let caseValidationTimer: number | null = null
  let nodeDetailReturnFocus: HTMLElement | null = null

  const selectedSkill = computed(() =>
    initialSkills.value.find((skill) => skill.id === selectedSkillId.value) ?? initialSkills.value[0] ?? null,
  )
  const selectedScenarioId = computed(() =>
    selectedSkill.value?.genome.metadata.category === 'finance' ? 'finance' : 'browser',
  )
  const availableMonsters = computed(() => catalog.scenarioMonsters[selectedScenarioId.value] ?? [])
  const currentRegion = computed(() => {
    if (!run.value) return null
    return run.value.map[run.value.actIndex] ?? run.value.map.at(-1) ?? null
  })
  const displayRegion = computed(() => {
    if (!run.value) return null
    return run.value.map[mapActIndex.value] ?? currentRegion.value
  })
  const currentLayer = computed(() => currentRegion.value?.layers[run.value?.layerIndex ?? 0] ?? [])
  const selectedNode = computed(() => {
    if (!run.value?.selectedNodeId) return null
    return currentRegion.value?.layers.flat().find((node) => node.id === run.value?.selectedNodeId) ?? null
  })
  const nodeDetailRecord = computed<NodeRunRecord | null>(() => {
    if (!run.value || !nodeDetailNodeId.value) return null
    return run.value.nodeHistory?.find((item) => item.nodeId === nodeDetailNodeId.value) ?? null
  })
  const nodeDetailNode = computed<RunNode | null>(() => {
    if (!run.value || !nodeDetailNodeId.value) return null
    for (const region of run.value.map) {
      const node = region.layers.flat().find((item) => item.id === nodeDetailNodeId.value)
      if (node) return node
    }
    return null
  })

  watch(run, (value) => {
    document.title = value
      ? `RogueSkills · ${value.seed} · 阶段 ${value.actIndex + 1}`
      : 'RogueSkills · 新建评估运行'
    if (value?.status === 'victory' && presetRunId.value !== value.id) {
      if (agentPreset.value?.sourceRun.runId !== value.id) agentPreset.value = null
      presetError.value = ''
      presetRunId.value = value.id
      presetProjectName.value = `${value.skillName ?? 'RogueSkills'} 智能体`
      presetProjectDescription.value = value.skillDescription
        ?? `基于 ${value.skillName ?? value.baseSkillId} 构建的候选业务智能体配置。`
      presetScenario.value = value.skillRole ?? 'browser-extraction'
    }
  }, { immediate: true })

  watch(() => run.value?.actIndex, (actIndex) => {
    if (typeof actIndex === 'number') mapActIndex.value = actIndex
  }, { immediate: true })

  watch([() => run.value?.id, () => agentPreset.value?.id], ([runId, presetId]) => {
    if (runId && presetId) void loadCaseValidationContext()
  })

  watch([selectedScenarioId, availableMonsters], () => {
    const availableIds = new Set(availableMonsters.value.map((monster) => monster.id))
    const current = selectedMonsterIds.value.filter((id) => availableIds.has(id))
    if (current.length) {
      selectedMonsterIds.value = current
      return
    }
    const regions = new Set<string>()
    selectedMonsterIds.value = availableMonsters.value
      .filter((monster) => {
        if (regions.has(monster.regionId)) return false
        regions.add(monster.regionId)
        return true
      })
      .map((monster) => monster.id)
  })

  function persistRun(): void {
    if (!run.value || revision.value == null) return
    savedRun.value = {
      saveVersion: SAVE_VERSION,
      id: run.value.id,
      revision: revision.value,
      actIndex: run.value.actIndex,
      seed: run.value.seed,
    }
    saveJson(STORAGE_KEY, savedRun.value)
  }

  function acceptRunRecord(record: RunRecord): void {
    if (record.artifact !== undefined) agentPreset.value = record.artifact
    run.value = record.run
    revision.value = record.revision
    persistRun()
  }

  function stopAutoAdvance(): void {
    if (autoAdvanceTimer != null) window.clearTimeout(autoAdvanceTimer)
    autoAdvanceTimer = null
  }

  function stopCaseValidationPolling(): void {
    if (caseValidationTimer != null) window.clearTimeout(caseValidationTimer)
    caseValidationTimer = null
  }

  function scheduleCaseValidationPolling(delay = 500): void {
    stopCaseValidationPolling()
    if (!caseValidation.value || !['queued', 'running'].includes(caseValidation.value.status)) return
    caseValidationTimer = window.setTimeout(() => void pollCaseValidation(), delay)
  }

  async function pollCaseValidation(): Promise<void> {
    if (!caseValidation.value) return
    try {
      const result = await getCaseValidation(caseValidation.value.id)
      caseValidation.value = result.validation
      if (['queued', 'running'].includes(result.validation.status)) scheduleCaseValidationPolling()
    } catch (error) {
      caseValidationError.value = error instanceof Error ? error.message : String(error)
      scheduleCaseValidationPolling(1200)
    }
  }

  async function loadCaseValidationContext(): Promise<void> {
    if (!run.value || !agentPreset.value) return
    caseValidationError.value = ''
    try {
      const [optionsResult, validationsResult] = await Promise.all([
        listCaseValidationOptions(run.value.id),
        listRunCaseValidations(run.value.id),
      ])
      caseValidationOptions.value = optionsResult.options
      if (!selectedReplayCaseId.value || !optionsResult.options.some((item) => item.caseId === selectedReplayCaseId.value)) {
        selectedReplayCaseId.value = optionsResult.options[0]?.caseId ?? ''
      }
      caseValidation.value = validationsResult.validations[0] ?? null
      if (caseValidation.value && ['queued', 'running'].includes(caseValidation.value.status)) {
        scheduleCaseValidationPolling()
      }
    } catch (error) {
      caseValidationError.value = error instanceof Error ? error.message : String(error)
    }
  }

  async function startCaseValidation(): Promise<void> {
    if (!run.value || !agentPreset.value || !selectedReplayCaseId.value || caseValidationPending.value) return
    const option = caseValidationOptions.value.find((item) => item.caseId === selectedReplayCaseId.value)
    if (!option) return
    caseValidationPending.value = true
    caseValidationError.value = ''
    try {
      const result = await createCaseValidation(run.value.id, {
        casePackId: option.casePackId,
        casePackVersion: option.casePackVersion,
        mode: 'verified_replay',
        replayCaseId: option.caseId,
        input: option.input,
        retryFailed: caseValidation.value?.status === 'failed'
          && caseValidation.value.replayCaseId === option.caseId,
      })
      caseValidation.value = result.validation
      if (['queued', 'running'].includes(result.validation.status)) scheduleCaseValidationPolling(200)
    } catch (error) {
      caseValidationError.value = error instanceof Error ? error.message : String(error)
    } finally {
      caseValidationPending.value = false
    }
  }

  function openCaseValidationDetail(): void {
    if (caseValidation.value?.status === 'succeeded') caseValidationDetailVisible.value = true
  }

  function closeCaseValidationDetail(): void {
    caseValidationDetailVisible.value = false
  }

  function scheduleAutoAdvance(delay = AUTO_ADVANCE_INTERVAL_MS): void {
    stopAutoAdvance()
    if (run.value?.automation?.status !== 'running') return
    autoAdvanceTimer = window.setTimeout(() => { void pollAutoRun() }, delay)
  }

  async function pollAutoRun(): Promise<void> {
    if (!run.value || revision.value == null || run.value.automation?.status !== 'running') return
    try {
      const record = await getEvolutionRun(run.value.id)
      acceptRunRecord(record)
      if (record.run.automation?.status === 'running') {
        scheduleAutoAdvance()
      } else {
        completionVisible.value = true
      }
    } catch (error) {
      report(error, 'AUTO_RUN_FAILED')
    }
  }

  function report(error: unknown, fallback: string): void {
    const code = error instanceof ApiError ? error.code : fallback
    const message = error instanceof Error ? error.message : String(error)
    window.alert(`${code}: ${message}`)
  }

  async function transition(operation: () => Promise<RunRecord>): Promise<void> {
    if (actionPending.value || !run.value || revision.value == null) return
    actionPending.value = true
    try {
      acceptRunRecord(await operation())
    } catch (error) {
      report(error, 'RUN_ERROR')
    } finally {
      actionPending.value = false
    }
  }

  async function initialize(): Promise<void> {
    try {
      const [nextCatalog, library] = await Promise.all([getEvolutionCatalog(), listInitialSkills()])
      Object.assign(catalog, nextCatalog)
      initialSkills.value = prioritizeDemoSkills(library.skills)
      libraryState.value = 'ready'
      selectedSkillId.value = initialSkills.value[0]?.id ?? null
      selectedModeId.value = Object.values(nextCatalog.runModes)[0]?.id ?? ''
      if (savedRun.value) {
        try {
          const restored = await getEvolutionRun(savedRun.value.id)
          acceptRunRecord(restored)
          selectedSkillId.value = restored.run.baseSkillId
          selectedModeId.value = restored.run.modeId
          seed.value = restored.run.seed
          scheduleAutoAdvance(120)
        } catch {
          localStorage.removeItem(STORAGE_KEY)
          savedRun.value = null
        }
      }
    } catch (error) {
      libraryState.value = 'offline'
      loadingError.value = error instanceof Error ? error.message : String(error)
    }
  }

  async function startRun(overrideSeed?: string): Promise<void> {
    const skill = selectedSkill.value
    if (!skill || actionPending.value || !selectedModeId.value) return
    if (!selectedMonsterIds.value.length) {
      window.alert('请至少选择一个目标失败模式。')
      return
    }
    actionPending.value = true
    try {
      agentPreset.value = null
      presetRunId.value = ''
      const created = await createEvolutionRun({
        seed: overrideSeed ?? seed.value,
        modeId: selectedModeId.value,
        skillId: skill.id,
      })
      const started = await startAutomaticEvolution(created.run.id, {
        expectedRevision: created.revision,
        selectedMonsterIds: selectedMonsterIds.value,
        projectName: `${skill.genome.name} Evolution Project`,
        projectDescription: skill.genome.description,
        scenario: skill.genome.metadata.category,
      })
      acceptRunRecord(started)
      completionVisible.value = false
      scheduleAutoAdvance(120)
    } catch (error) {
      report(error, 'RUN_CREATE_FAILED')
    } finally {
      actionPending.value = false
    }
  }

  async function continueRun(): Promise<void> {
    if (!savedRun.value) return
    try {
      acceptRunRecord(await getEvolutionRun(savedRun.value.id))
      scheduleAutoAdvance(120)
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY)
      savedRun.value = null
      report(error, 'RUN_LOAD_FAILED')
    }
  }

  async function retrySeed(): Promise<void> {
    if (!run.value || actionPending.value) return
    const current = run.value
    const automatedTargets = current.automation?.selectedMonsterIds
    if (automatedTargets?.length) selectedMonsterIds.value = [...automatedTargets]
    seed.value = current.seed
    selectedModeId.value = current.modeId
    selectedSkillId.value = current.baseSkillId
    run.value = null
    revision.value = null
    await startRun(current.seed)
  }

  function returnToSetup(): void {
    stopAutoAdvance()
    run.value = null
    revision.value = null
    completionVisible.value = false
  }

  function randomizeSeed(): void {
    const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    const part = Array.from({ length: 5 }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join('')
    seed.value = `RUN-${part}`
  }

  function mutationById(id: string) { return catalog.mutations.find((item) => item.id === id) }
  function evolutionById(id: string) { return catalog.evolutions.find((item) => item.id === id) }
  function monsterById(id?: string | null) { return id ? catalog.monsters[id] ?? null : null }

  function objectiveScore(state: EvolutionRun): number {
    const weights = catalog.runModes[state.modeId]?.weights ?? {}
    const value = Object.entries(weights).reduce(
      (total, [stat, weight]) => total + (state.stats[stat] ?? 0) * weight,
      0,
    )
    return Math.round(value * 10) / 10
  }

  function evolutionProgress(state: EvolutionRun) {
    const counts: Record<string, number> = {}
    state.mutationIds.forEach((id) => mutationById(id)?.tags.forEach((tag) => {
      counts[tag] = (counts[tag] ?? 0) + 1
    }))
    return catalog.evolutions.map((evolution: Evolution) => {
      const requirements = Object.entries(evolution.tagRequirements).map(([tag, required]) => ({
        tag, required, current: Math.min(counts[tag] ?? 0, required),
      }))
      return {
        ...evolution,
        unlocked: state.evolutionIds.includes(evolution.id),
        requirements,
        progress: requirements.reduce((sum, item) => sum + item.current, 0),
        total: requirements.reduce((sum, item) => sum + item.required, 0),
      }
    })
  }

  function nodeState(node: RunNode): string {
    const state = run.value
    if (!state) return 'locked'
    if (state.nodeHistory?.find((item) => item.nodeId === node.id)?.status === 'failed') return 'failed'
    if (state.completedNodeIds.includes(node.id)) return 'completed'
    if (state.selectedNodeId === node.id) return 'selected'
    if (node.layer < state.layerIndex) return 'skipped'
    if (state.automation?.status === 'running') return 'locked'
    if (node.layer === state.layerIndex && state.phase === 'choose_node' && state.status === 'active') return 'available'
    return 'locked'
  }

  const selectNode = (nodeId: string) => {
    if (!run.value || revision.value == null) return Promise.resolve()
    return transition(() => selectEvolutionNode(run.value!.id, nodeId, revision.value!))
  }

  function openNodeDetail(nodeId: string): void {
    if (!run.value?.nodeHistory?.some((item) => item.nodeId === nodeId)) return
    nodeDetailReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    nodeDetailNodeId.value = nodeId
  }

  function closeNodeDetail(): void {
    nodeDetailNodeId.value = null
    const returnFocus = nodeDetailReturnFocus
    nodeDetailReturnFocus = null
    if (returnFocus) void nextTick(() => returnFocus.focus())
  }

  function setMapActIndex(actIndex: number): void {
    if (!run.value?.map[actIndex]) return
    mapActIndex.value = actIndex
  }

  function handleNodeClick(node: RunNode): Promise<void> | void {
    const state = nodeState(node)
    if (state === 'available' && run.value?.automation?.status !== 'running') {
      return selectNode(node.id)
    }
    if (state === 'selected' || state === 'completed' || state === 'failed') {
      openNodeDetail(node.id)
    }
  }
  const resolveNode = () => {
    if (!run.value || revision.value == null) return Promise.resolve()
    return transition(() => resolveEvolutionNode(run.value!.id, revision.value!))
  }
  const chooseMutation = (mutationId: string) => {
    if (!run.value || revision.value == null) return Promise.resolve()
    return transition(() => chooseEvolutionMutation(run.value!.id, mutationId, revision.value!))
  }
  const skipMutation = () => {
    if (!run.value || revision.value == null) return Promise.resolve()
    return transition(() => skipEvolutionMutation(run.value!.id, revision.value!))
  }

  function toggleMonster(monsterId: string): void {
    selectedMonsterIds.value = selectedMonsterIds.value.includes(monsterId)
      ? selectedMonsterIds.value.filter((id) => id !== monsterId)
      : [...selectedMonsterIds.value, monsterId]
  }

  function closeCompletion(): void {
    completionVisible.value = false
  }

  function dispose(): void {
    stopAutoAdvance()
    stopCaseValidationPolling()
  }

  async function saveAgentPreset(): Promise<void> {
    if (
      !run.value
      || run.value.status !== 'victory'
      || revision.value == null
      || presetPending.value
    ) return
    presetPending.value = true
    presetError.value = ''
    try {
      const result = await createAgentPreset(run.value.id, {
        expectedRevision: revision.value,
        projectName: presetProjectName.value,
        projectDescription: presetProjectDescription.value,
        scenario: presetScenario.value,
      })
      agentPreset.value = result.preset
    } catch (error) {
      presetError.value = error instanceof Error ? error.message : String(error)
    } finally {
      presetPending.value = false
    }
  }

  async function exportAgentPreset(): Promise<void> {
    if (!agentPreset.value) return
    try {
      await downloadAgentPreset(agentPreset.value.id, presetExportTarget.value)
    } catch (error) {
      report(error, 'AGENT_PRESET_EXPORT_FAILED')
    }
  }

  return reactive({
    actionPending, agentPreset, availableMonsters, catalog, chooseMutation, closeCompletion,
    caseValidation, caseValidationDetailVisible, caseValidationError, caseValidationOptions,
    caseValidationPending, closeCaseValidationDetail,
    completionVisible, continueRun, currentLayer, currentRegion, dispose,
    exportAgentPreset,
    evolutionById, evolutionProgress, initialSkills, initialize, libraryState, loadingError,
    displayRunText, runEnglishName,
    MAX_STABILITY, monsterById, mutationById, nodeState, objectiveScore, randomizeSeed,
    presetError, presetExportTarget, presetPending, presetProjectDescription, presetProjectName, presetScenario,
    closeNodeDetail, displayRegion, handleNodeClick, mapActIndex, nodeDetailNode, nodeDetailNodeId,
    nodeDetailRecord, openNodeDetail, resolveNode, retrySeed, returnToSetup, run, savedRun,
    saveAgentPreset, seed, selectNode, selectedModeId, setMapActIndex,
    selectedMonsterIds, selectedNode, selectedReplayCaseId, selectedScenarioId, selectedSkill,
    selectedSkillId, skipMutation, startCaseValidation, startRun, toggleMonster,
    openCaseValidationDetail,
  })
}

export type EvolutionController = ReturnType<typeof useEvolutionRun>
