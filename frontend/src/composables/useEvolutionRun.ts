import { computed, reactive, ref, watch } from 'vue'
import {
  chooseEvolutionMutation,
  createAgentPreset,
  createEvolutionRun,
  downloadAgentPreset,
  getEvolutionCatalog,
  getEvolutionRun,
  listInitialSkills,
  resolveEvolutionNode,
  selectEvolutionNode,
  skipEvolutionMutation,
  startAutomaticEvolution,
} from '@/api/client'
import type {
  AgentPreset,
  Evolution,
  EvolutionCatalog,
  EvolutionRun,
  RunNode,
  RunRecord,
  SkillRecord,
} from '@/types/domain'
import { ApiError } from '@/types/domain'
import { loadJson, saveJson } from '@/utils'

const STORAGE_KEY = 'rogueskills.prototype.run.v1'
const SAVE_VERSION = 2
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
  const agentPreset = ref<AgentPreset | null>(null)
  const presetPending = ref(false)
  const presetError = ref('')
  const presetProjectName = ref('')
  const presetProjectDescription = ref('')
  const presetScenario = ref('')
  const presetRunId = ref('')
  const catalog = reactive<EvolutionCatalog>({ ...emptyCatalog })
  let autoAdvanceTimer: number | null = null

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
  const currentLayer = computed(() => currentRegion.value?.layers[run.value?.layerIndex ?? 0] ?? [])
  const selectedNode = computed(() => {
    if (!run.value?.selectedNodeId) return null
    return currentRegion.value?.layers.flat().find((node) => node.id === run.value?.selectedNodeId) ?? null
  })

  watch(run, (value) => {
    document.title = value
      ? `RogueSkills · ${value.seed} · Act ${value.actIndex + 1}`
      : 'RogueSkills · 新建 Evolution Run'
    if (value?.status === 'victory' && presetRunId.value !== value.id) {
      if (agentPreset.value?.sourceRun.runId !== value.id) agentPreset.value = null
      presetError.value = ''
      presetRunId.value = value.id
      presetProjectName.value = `${value.skillName ?? 'RogueSkills'} Agent`
      presetProjectDescription.value = value.skillDescription
        ?? `基于 ${value.skillName ?? value.baseSkillId} 构建的候选业务 Agent 配置。`
      presetScenario.value = value.skillRole ?? 'browser-extraction'
    }
  }, { immediate: true })

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
      initialSkills.value = library.skills
      libraryState.value = 'ready'
      selectedSkillId.value = library.skills[0]?.id ?? null
      selectedModeId.value = Object.values(nextCatalog.runModes)[0]?.id ?? ''
    } catch (error) {
      libraryState.value = 'offline'
      loadingError.value = error instanceof Error ? error.message : String(error)
    }
  }

  async function startRun(overrideSeed?: string): Promise<void> {
    const skill = selectedSkill.value
    if (!skill || actionPending.value || !selectedModeId.value) return
    if (!selectedMonsterIds.value.length) {
      window.alert('请至少选择一个挑战怪物。')
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
      await downloadAgentPreset(agentPreset.value.id)
    } catch (error) {
      report(error, 'AGENT_PRESET_EXPORT_FAILED')
    }
  }

  return reactive({
    actionPending, agentPreset, availableMonsters, catalog, chooseMutation, closeCompletion,
    completionVisible, continueRun, currentLayer, currentRegion, dispose,
    exportAgentPreset,
    evolutionById, evolutionProgress, initialSkills, initialize, libraryState, loadingError,
    MAX_STABILITY, monsterById, mutationById, nodeState, objectiveScore, randomizeSeed,
    presetError, presetPending, presetProjectDescription, presetProjectName, presetScenario,
    resolveNode, retrySeed, returnToSetup, run, savedRun, saveAgentPreset, seed, selectNode, selectedModeId,
    selectedMonsterIds, selectedNode, selectedScenarioId, selectedSkill, selectedSkillId,
    skipMutation, startRun, toggleMonster,
  })
}

export type EvolutionController = ReturnType<typeof useEvolutionRun>
