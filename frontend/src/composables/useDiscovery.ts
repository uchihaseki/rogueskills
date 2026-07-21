import { computed, onScopeDispose, reactive, watch } from 'vue'
import {
  apiHealth, benchmarkSkill, bootstrapFinanceSkills, convertMaterial, createDiscoverySearchRun,
  deleteSkill, discoveryEventsUrl, getDiscoverySearchRun, importDiscoveryBatch,
  importDiscoveryCandidate, listDiscoveryProviders, listSkills, previewDiscoveryCandidate,
  promoteSkill, storeSkillGenome,
} from '@/api/client'
import type {
  DiscoveryCandidate, DiscoveryCandidatePreview, DiscoveryEvent, DiscoveryImportBatch,
  DiscoveryQueryPlan, DiscoverySearchRun, DiscoverySourceHit, FinanceBootstrapResult,
  NormalizerStatus, ProviderStatus, SearchProvider, SkillGenome, SourceConnector,
} from '@/types/domain'
import { errorMessage, loadJson, recordToGenome, saveJson } from '@/utils'

const STORAGE_KEY = 'rogueskills.discovery.library.v1'
export type DiscoveryView = 'search' | 'finance' | 'convert' | 'library'

export function useDiscovery() {
  let eventSource: EventSource | null = null
  const state = reactive({
    view: 'search' as DiscoveryView,
    query: 'browser extraction',
    sourceIds: new Set<string>(),
    providerIds: new Set<string>(),
    kindFilter: 'all',
    results: [] as DiscoveryCandidate[],
    providerStatus: [] as ProviderStatus[],
    providers: [] as SearchProvider[],
    connectors: [] as SourceConnector[],
    searchRun: null as DiscoverySearchRun | null,
    queries: [] as DiscoveryQueryPlan[],
    events: [] as DiscoveryEvent[],
    sources: [] as DiscoverySourceHit[],
    selectedIds: new Set<string>(),
    userEditedSelection: false,
    candidatePreview: null as DiscoveryCandidatePreview | null,
    previewingId: null as string | null,
    reviewOpen: false,
    importing: false,
    importBatch: null as DiscoveryImportBatch | null,
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
  function providerById(id: string) { return state.providers.find((item) => item.id === id) ?? null }
  function candidateInLibrary(candidate: DiscoveryCandidate) {
    return state.library.some((genome) => genome.discovery?.candidateId === candidate.id || genome.provenance?.url === candidate.url)
  }
  function switchView(view: DiscoveryView) { state.view = view; state.notice = null }
  function toggleSource(id: string) {
    state.sourceIds.has(id) ? state.sourceIds.delete(id) : state.sourceIds.add(id)
    if (!state.sourceIds.size) state.sourceIds.add('builtin')
  }
  function toggleProvider(id: string) {
    const provider = providerById(id)
    if (!provider?.configured || state.searching) return
    state.providerIds.has(id) ? state.providerIds.delete(id) : state.providerIds.add(id)
  }
  function applySearchSnapshot(snapshot: {
    run: DiscoverySearchRun
    queries: DiscoveryQueryPlan[]
    providerStatus: ProviderStatus[]
    sources: DiscoverySourceHit[]
    candidates: DiscoveryCandidate[]
  }) {
    state.searchRun = snapshot.run
    state.queries = snapshot.queries
    state.providerStatus = snapshot.providerStatus
    state.sources = snapshot.sources
    state.results = snapshot.candidates
    if (!state.userEditedSelection) {
      state.selectedIds = new Set(
        snapshot.candidates
          .filter((candidate) => candidate.selection?.recommended)
          .map((candidate) => candidate.id),
      )
    }
  }
  function upsertResult(candidate: DiscoveryCandidate) {
    const index = state.results.findIndex((item) => item.id === candidate.id)
    if (index === -1) state.results.push(candidate)
    else state.results[index] = candidate
  }
  function upsertSource(source: DiscoverySourceHit) {
    const index = state.sources.findIndex((item) => item.id === source.id)
    if (index === -1) state.sources.push(source)
    else state.sources[index] = source
  }
  async function refreshCompletedRun() {
    if (!state.searchRun) return
    const snapshot = await getDiscoverySearchRun(state.searchRun.id)
    applySearchSnapshot(snapshot)
    state.searching = !['review_ready', 'failed', 'cancelled', 'expired'].includes(snapshot.run.state)
    if (!state.searching) {
      eventSource?.close()
      eventSource = null
    }
  }
  function consumeSearchEvent(event: DiscoveryEvent) {
    if (event.type !== 'heartbeat') state.events.push(event)
    if (state.events.length > 120) state.events.splice(0, state.events.length - 120)
    if (state.searchRun) state.searchRun.revision = Math.max(state.searchRun.revision, event.revision)
    const payload = event.payload as {
      providerId?: string
      state?: string
      count?: number
      code?: string
      message?: string
      source?: DiscoverySourceHit
      candidate?: DiscoveryCandidate
      run?: DiscoverySearchRun
    }
    if (event.type.startsWith('provider.') && payload.providerId) {
      const index = state.providerStatus.findIndex((item) => item.providerId === payload.providerId)
      const status: ProviderStatus = {
        providerId: payload.providerId,
        state: payload.state ?? event.type.replace('provider.', ''),
        count: payload.count,
        message: payload.message,
      }
      if (index === -1) state.providerStatus.push(status)
      else state.providerStatus[index] = status
    }
    if (payload.source) upsertSource(payload.source)
    if (payload.candidate) upsertResult(payload.candidate)
    if (payload.run) state.searchRun = payload.run
    if (event.type === 'run.review_ready' || event.type === 'run.failed' || event.type === 'run.cancelled') {
      void refreshCompletedRun()
    }
  }
  async function syncRepository() {
    const { skills } = await listSkills()
    state.library = skills.map(recordToGenome)
    saveLibrary()
  }

  async function runSearch() {
    if (!state.query.trim()) return setNotice('请输入要发现的能力或业务目标。', 'error')
    if (!state.providerIds.size) return setNotice('请至少选择一个已经配置的真实搜索 API。', 'error')
    eventSource?.close()
    eventSource = null
    state.searching = true; state.notice = null
    state.results = []; state.sources = []; state.events = []; state.providerStatus = []
    state.selectedIds = new Set(); state.userEditedSelection = false
    state.candidatePreview = null; state.importBatch = null
    try {
      if (state.gateway !== 'online') throw new Error('Python Gateway offline')
      const snapshot = await createDiscoverySearchRun({
        query: state.query.trim(), providerIds: [...state.providerIds], includeLocalExamples: false,
      })
      applySearchSnapshot(snapshot)
      eventSource = new EventSource(discoveryEventsUrl(snapshot.run.id))
      eventSource.onmessage = (message) => consumeSearchEvent(JSON.parse(message.data) as DiscoveryEvent)
      eventSource.onerror = () => {
        if (state.searchRun && ['review_ready', 'failed', 'cancelled', 'expired'].includes(state.searchRun.state)) {
          eventSource?.close(); eventSource = null
        }
      }
    } catch (error) {
      state.results = []; state.providerStatus = []; setNotice(`检索失败：${errorMessage(error)}`, 'error')
      state.searching = false
    }
  }

  function toggleCandidate(candidate: DiscoveryCandidate) {
    if (candidate.selection && !candidate.selection.eligible) return
    state.userEditedSelection = true
    if (state.selectedIds.has(candidate.id)) state.selectedIds.delete(candidate.id)
    else state.selectedIds.add(candidate.id)
  }
  function selectRecommended() {
    state.userEditedSelection = true
    state.selectedIds = new Set(state.results.filter((item) => item.selection?.recommended).map((item) => item.id))
  }
  function clearSelection() {
    state.userEditedSelection = true
    state.selectedIds = new Set()
  }
  async function openCandidatePreview(candidate: DiscoveryCandidate) {
    state.previewingId = candidate.id
    try { state.candidatePreview = await previewDiscoveryCandidate(candidate.id) }
    catch (error) { setNotice(`预览失败：${errorMessage(error)}`, 'error') }
    finally { state.previewingId = null }
  }
  function closeCandidatePreview() { state.candidatePreview = null }
  function openImportReview() {
    if (!state.selectedIds.size) return
    state.reviewOpen = true
  }
  async function confirmImport() {
    if (!state.searchRun || !state.selectedIds.size) return
    state.importing = true; state.notice = null
    const selected = state.results.filter((candidate) => state.selectedIds.has(candidate.id))
    const acknowledgedWarnings = selected.flatMap((candidate) =>
      candidate.selection?.reasonCodes
        .filter((code) => code === 'LICENSE_REVIEW_REQUIRED')
        .map((code) => ({ candidateId: candidate.id, code })) ?? [],
    )
    try {
      state.importBatch = await importDiscoveryBatch({
        searchRunId: state.searchRun.id,
        candidateIds: [...state.selectedIds],
        expectedRunRevision: state.searchRun.revision,
        acknowledgedWarnings,
      })
      await syncRepository()
      state.reviewOpen = false
      setNotice(`批量保存完成：${state.importBatch.summary.saved} 项进入隔离候选库。`, state.importBatch.summary.saved ? 'success' : 'error')
    } catch (error) { setNotice(`批量保存失败：${errorMessage(error)}`, 'error') }
    finally { state.importing = false }
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
      const [health, providerResponse] = await Promise.all([apiHealth(), listDiscoveryProviders()])
      state.providers = providerResponse.providers
      state.providerIds = new Set(state.providers.filter((provider) => provider.configured).map((provider) => provider.id))
      state.normalizer = health.materialNormalizer; state.gateway = 'online'
      await syncRepository()
      if (!state.providerIds.size) setNotice('尚未配置真实搜索 API，请先在后端配置 GitHub、Brave、Tavily 或 Exa Key。', 'error')
    } catch { state.gateway = 'offline'; state.results = []; state.providerStatus = [] }
  }

  onScopeDispose(() => eventSource?.close())

  return {
    benchmark, candidateInLibrary, clearSelection, closeCandidatePreview, confirmImport, connectorById,
    convert, download, initialize, openCandidatePreview, openImportReview, promote, providerById, remove,
    runFinanceBootstrap, runSearch, selectRecommended, stageCandidate, stagePreview, state, switchView,
    toggleCandidate, toggleProvider, toggleSource, upload, visibleResults,
  }
}

export type DiscoveryController = ReturnType<typeof useDiscovery>
