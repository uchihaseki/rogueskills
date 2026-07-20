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
  archetypes: {}, evolutions: [], monsters: {}, mutations: [], nodeTypes: {}, runModes: {}, statLabels: {},
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
  const agentPreset = ref<AgentPreset | null>(null)
  const presetPending = ref(false)
  const presetError = ref('')
  const presetProjectName = ref('')
  const presetProjectDescription = ref('')
  const presetScenario = ref('')
  const presetRunId = ref('')
  const catalog = reactive<EvolutionCatalog>({ ...emptyCatalog })

  const selectedSkill = computed(() =>
    initialSkills.value.find((skill) => skill.id === selectedSkillId.value) ?? initialSkills.value[0] ?? null,
  )
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
      agentPreset.value = null
      presetError.value = ''
      presetRunId.value = value.id
      presetProjectName.value = `${value.skillName ?? 'RogueSkills'} Agent`
      presetProjectDescription.value = value.skillDescription
        ?? `基于 ${value.skillName ?? value.baseSkillId} 构建的候选业务 Agent 配置。`
      presetScenario.value = value.skillRole ?? 'browser-extraction'
    }
  }, { immediate: true })

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
    run.value = record.run
    revision.value = record.revision
    persistRun()
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
    actionPending.value = true
    try {
      acceptRunRecord(await createEvolutionRun({
        seed: overrideSeed ?? seed.value,
        modeId: selectedModeId.value,
        skillId: skill.id,
      }))
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
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY)
      savedRun.value = null
      report(error, 'RUN_LOAD_FAILED')
    }
  }

  async function retrySeed(): Promise<void> {
    if (!run.value || actionPending.value) return
    const current = run.value
    actionPending.value = true
    try {
      acceptRunRecord(await createEvolutionRun({
        seed: current.seed,
        modeId: current.modeId,
        skillId: current.baseSkillId,
      }))
    } catch (error) {
      report(error, 'RUN_CREATE_FAILED')
    } finally {
      actionPending.value = false
    }
  }

  function returnToSetup(): void {
    run.value = null
    revision.value = null
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
    actionPending, agentPreset, catalog, chooseMutation, continueRun, currentLayer, currentRegion,
    exportAgentPreset,
    evolutionById, evolutionProgress, initialSkills, initialize, libraryState, loadingError,
    MAX_STABILITY, monsterById, mutationById, nodeState, objectiveScore, randomizeSeed,
    presetError, presetPending, presetProjectDescription, presetProjectName, presetScenario,
    resolveNode, retrySeed, returnToSetup, run, savedRun, saveAgentPreset, seed, selectNode, selectedModeId,
    selectedNode, selectedSkill, selectedSkillId, skipMutation, startRun,
  })
}

export type EvolutionController = ReturnType<typeof useEvolutionRun>
