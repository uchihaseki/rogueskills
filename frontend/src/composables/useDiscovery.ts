import { computed, reactive, watch } from 'vue'
import {
  apiHealth, benchmarkSkill, bootstrapFinanceSkills, convertMaterial, deleteSkill, importDiscoveryCandidate,
  listDiscoveryConnectors, listSkills, promoteSkill, searchDiscovery, storeSkillGenome,
} from '@/api/client'
import type {
  DiscoveryCandidate, FinanceBootstrapResult, NormalizerStatus, ProviderStatus, SkillGenome, SourceConnector,
} from '@/types/domain'
import { errorMessage, loadJson, recordToGenome, saveJson } from '@/utils'

const STORAGE_KEY = 'rogueskills.discovery.library.v1'
export type DiscoveryView = 'search' | 'finance' | 'convert' | 'library'

export function useDiscovery() {
  const state = reactive({
    view: 'search' as DiscoveryView,
    query: 'browser extraction',
    sourceIds: new Set<string>(['builtin']),
    kindFilter: 'all',
    results: [] as DiscoveryCandidate[],
    providerStatus: [] as ProviderStatus[],
    connectors: [] as SourceConnector[],
    searching: false,
    financeRunning: false,
    financeResult: null as FinanceBootstrapResult | null,
    normalizing: false,
    normalizer: null as NormalizerStatus | null,
    normalization: null as NormalizerStatus | null,
    stagingId: null as string | null,
    library: loadJson<SkillGenome[]>(STORAGE_KEY, []),
    preview: null as SkillGenome | null,
    uploadedText: '', uploadedName: '', sourceLabel: '', license: 'unknown',
    notice: null as { message: string; tone: 'success' | 'error' } | null,
    gateway: 'checking' as 'checking' | 'online' | 'offline',
  })

  const visibleResults = computed(() => state.kindFilter === 'all'
    ? state.results
    : state.results.filter((item) => item.kind === state.kindFilter))

  watch(() => state.view, (view) => {
    const labels: Record<DiscoveryView, string> = { search: 'Skill Discovery', finance: 'Finance Bootstrap', convert: 'SOP Converter', library: 'Skill Repository' }
    document.title = `RogueSkills · ${labels[view]}`
  }, { immediate: true })

  function setNotice(message: string, tone: 'success' | 'error' = 'success') { state.notice = { message, tone } }
  function saveLibrary() { saveJson(STORAGE_KEY, state.library) }
  function connectorById(id: string) { return state.connectors.find((item) => item.id === id) ?? null }
  function candidateInLibrary(candidate: DiscoveryCandidate) {
    return state.library.some((genome) => genome.discovery?.candidateId === candidate.id || genome.provenance?.url === candidate.url)
  }
  function switchView(view: DiscoveryView) { state.view = view; state.notice = null }
  function toggleSource(id: string) {
    state.sourceIds.has(id) ? state.sourceIds.delete(id) : state.sourceIds.add(id)
    if (!state.sourceIds.size) state.sourceIds.add('builtin')
  }
  function requestedSourceFilters(query: string) {
    return [...query.matchAll(/\bsource:(?:"([^"]+)"|(\S+))/gi)].map((match) => (match[1] ?? match[2] ?? '').toLowerCase())
  }
  async function syncRepository() {
    const { skills } = await listSkills()
    state.library = skills.map(recordToGenome)
    saveLibrary()
  }

  async function runSearch() {
    const requested = requestedSourceFilters(state.query).filter((id) => state.connectors.some((item) => item.id === id && ['live', 'beta'].includes(item.status)))
    if (requested.length) state.sourceIds = new Set(requested)
    state.searching = true; state.notice = null
    try {
      if (state.gateway !== 'online') throw new Error('Python Gateway offline')
      const response = await searchDiscovery(state.query.trim(), [...state.sourceIds])
      state.results = response.results; state.providerStatus = response.status
      if (response.status.every((item) => item.state !== 'ok')) setNotice('所选远程来源当前不可用，请保留种子索引或稍后重试。', 'error')
    } catch (error) {
      state.results = []; state.providerStatus = []; setNotice(`检索失败：${errorMessage(error)}`, 'error')
    } finally { state.searching = false }
  }

  async function stageCandidate(candidate: DiscoveryCandidate) {
    state.stagingId = candidate.id; state.notice = null
    try {
      if (state.gateway !== 'online') throw new Error('Python Gateway offline')
      const { skill } = await importDiscoveryCandidate(candidate)
      const genome = recordToGenome(skill)
      state.library = [genome, ...state.library.filter((item) => item.id !== genome.id)]
      saveLibrary(); setNotice(`「${genome.name}」已保存到隔离候选库。`)
    } catch (error) { setNotice(`候选转换失败：${errorMessage(error)}`, 'error') }
    finally { state.stagingId = null }
  }

  async function runFinanceBootstrap() {
    if (!state.normalizer?.configured) return setNotice('后端尚未配置 Qwen LLM Normalizer。', 'error')
    state.financeRunning = true; state.notice = null
    try {
      state.financeResult = await bootstrapFinanceSkills({ maxCommunitySkills: 2, autoPromote: true })
      await syncRepository()
      const summary = state.financeResult.summary
      setNotice(
        `金融初始化完成：${summary.initialSkills} 个 Skill 已进入 Initial Library，${summary.rejected} 个候选被过滤。`,
        summary.initialSkills > 0 ? 'success' : 'error',
      )
    } catch (error) {
      setNotice(`金融初始化失败：${errorMessage(error)}`, 'error')
    } finally { state.financeRunning = false }
  }

  async function convert() {
    const content = state.uploadedText.trim()
    if (!content) return setNotice('请先粘贴或上传 SOP 材料。', 'error')
    if (!state.normalizer?.configured) return setNotice('后端尚未配置 LLM Normalizer。', 'error')
    state.normalizing = true; state.notice = null
    try {
      const { genome, normalization } = await convertMaterial({ title: state.uploadedName.trim(), content, license: state.license, source: { platform: state.sourceLabel.trim() || 'Manual SOP', author: 'Local User' } })
      state.preview = genome; state.normalization = normalization
      setNotice(`模型「${normalization.model ?? normalization.provider}」已完成语义归一化。`)
    } catch (error) { setNotice(`转换失败：${errorMessage(error)}`, 'error') }
    finally { state.normalizing = false }
  }

  async function stagePreview() {
    if (!state.preview) return
    try {
      if (state.gateway !== 'online') throw new Error('Python Gateway offline')
      const { skill } = await storeSkillGenome(state.preview, 'manual')
      const genome = recordToGenome(skill)
      state.library = [genome, ...state.library.filter((item) => item.id !== genome.id)]
      saveLibrary(); setNotice(`「${genome.name}」已保存到 Skill Repository。`)
    } catch (error) { setNotice(`保存失败：${errorMessage(error)}`, 'error') }
  }

  async function benchmark(genomeId: string) {
    try {
      const { result } = await benchmarkSkill(genomeId); await syncRepository()
      setNotice(result.passed ? `准入 Benchmark 通过，得分 ${result.score}。请人工确认后晋升。` : `准入 Benchmark 未通过，得分 ${result.score}。`, result.passed ? 'success' : 'error')
    } catch (error) { setNotice(`Benchmark 失败：${errorMessage(error)}`, 'error') }
  }
  async function promote(genomeId: string, evaluationId: string, versionId: string) {
    try { await promoteSkill(genomeId, evaluationId, versionId); await syncRepository(); setNotice('Skill 已进入 Initial Skill Library，可以在 Evolution Run 中选择。') }
    catch (error) { setNotice(`晋升失败：${errorMessage(error)}`, 'error') }
  }
  async function remove(genomeId: string) {
    try { await deleteSkill(genomeId); state.library = state.library.filter((item) => item.id !== genomeId); saveLibrary() }
    catch (error) { setNotice(`移除失败：${errorMessage(error)}`, 'error') }
  }
  function download(genome: SkillGenome) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(genome, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${genome.id}.json`; anchor.click(); URL.revokeObjectURL(url)
  }
  async function upload(file?: File) {
    if (!file) return
    state.uploadedText = await file.text(); state.uploadedName = file.name.replace(/\.(?:md|txt)$/i, ''); state.preview = null
  }
  async function initialize() {
    try {
      const [health, connectorResponse] = await Promise.all([apiHealth(), listDiscoveryConnectors()])
      state.connectors = connectorResponse.connectors; state.normalizer = health.materialNormalizer; state.gateway = 'online'
      await syncRepository(); const response = await searchDiscovery(state.query, ['builtin'])
      state.results = response.results; state.providerStatus = response.status
    } catch { state.gateway = 'offline'; state.results = []; state.providerStatus = [] }
  }

  return { benchmark, candidateInLibrary, connectorById, convert, download, initialize, promote, remove, runFinanceBootstrap, runSearch, stageCandidate, stagePreview, state, switchView, toggleSource, upload, visibleResults }
}

export type DiscoveryController = ReturnType<typeof useDiscovery>
