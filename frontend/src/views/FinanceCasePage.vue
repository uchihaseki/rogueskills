<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createFinanceCase,
  financeCasePreflight,
  downloadAgentPreset,
  listFinanceCases,
  listInitialSkills,
} from '@/api/client'
import FinanceBusinessReport from '@/components/finance/FinanceBusinessReport.vue'
import type {
  FinanceCasePreflight,
  FinanceCaseRun,
  FinanceResearchReport,
  SkillRecord,
} from '@/types/domain'
import '@/assets/finance-case.css'

const preflight = ref<FinanceCasePreflight | null>(null)
const financeSkills = ref<SkillRecord[]>([])
const previousCases = ref<FinanceCaseRun[]>([])
const selectedSkillId = ref('')
const ticker = ref('AAPL')
const asOfDate = ref(new Date().toISOString().slice(0, 10))
const mode = ref<'live' | 'verified_replay'>('live')
const replayCaseId = ref('')
const running = ref(false)
const error = ref('')
const result = ref<FinanceCaseRun | null>(null)

const report = computed(() => result.value?.finalReport ?? null)
const baselineScore = computed(() => result.value?.baseline?.evaluation.score ?? null)
const evolvedScore = computed(() => result.value?.evolved?.evaluation.score ?? null)

function formatValue(value: number, unit: string): string {
  if (unit === '%') return `${value.toFixed(1)}%`
  if (unit === 'USD' && Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`
  if (unit === 'shares' && Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
  if (unit === 'USD' || unit === 'USD/shares') return `$${value.toFixed(2)}`
  return `${value.toLocaleString()} ${unit}`
}

function downloadReport(current: FinanceResearchReport) {
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify(current, null, 2)],
    { type: 'application/json' },
  ))
  const link = document.createElement('a')
  link.href = url
  link.download = `${current.company.ticker}-${current.stage}-finance-report.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadPreset() {
  if (result.value?.agentPreset) {
    await downloadAgentPreset(result.value.agentPreset.id, 'universal')
  }
}

async function initialize() {
  try {
    const [status, library, history] = await Promise.all([
      financeCasePreflight(), listInitialSkills(), listFinanceCases(),
    ])
    preflight.value = status
    financeSkills.value = library.skills.filter(
      (skill) => skill.genome.metadata.category === 'finance',
    )
    previousCases.value = history.cases.filter((item) => item.status === 'succeeded')
    selectedSkillId.value = financeSkills.value[0]?.id ?? ''
    replayCaseId.value = previousCases.value[0]?.id ?? ''
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : String(caught)
  }
}

async function runCase() {
  if (!selectedSkillId.value || running.value) return
  running.value = true
  error.value = ''
  result.value = null
  try {
    const response = await createFinanceCase({
      ticker: ticker.value.trim().toUpperCase(),
      skillId: selectedSkillId.value,
      asOfDate: asOfDate.value,
      mode: mode.value,
      replayCaseId: mode.value === 'verified_replay' ? replayCaseId.value : undefined,
      autoEvolve: true,
    })
    result.value = response.case
    previousCases.value = [response.case, ...previousCases.value]
    replayCaseId.value = response.case.id
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : String(caught)
  } finally {
    running.value = false
  }
}

onMounted(initialize)
</script>

<template>
  <main class="finance-case-page">
    <header class="finance-case-nav">
      <RouterLink class="brand" to="/"><span class="brand-mark">R</span><span><strong>RogueSkills</strong><small>REAL FINANCE RUNTIME</small></span></RouterLink>
      <nav><RouterLink to="/discovery">技能发现 <small>DISCOVERY</small></RouterLink><RouterLink to="/">技能评估 <small>EVALUATION</small></RouterLink></nav>
    </header>

    <section class="finance-case-hero">
      <div><p>运行时验证 · 仅使用公开数据 <small>RUNTIME VERIFIED · PUBLIC DATA ONLY</small></p><h1>让金融 Skill 真正分析一家公司</h1><span>SEC EDGAR 与市场价格实时抓取、不可变证据快照、事实级引用评测、Genome 优化和重跑对比。</span></div>
      <aside :class="{ ready: preflight?.ready }"><i></i><div><small>分析模型 · ANALYST RUNTIME</small><strong>{{ preflight?.analyst.model || '未配置' }}</strong><span>{{ preflight?.ready ? '模型已配置，数据源将在运行时检查' : '运行前检查未通过' }}</span></div></aside>
    </section>

    <section class="finance-case-flow">
      <div :class="{ active: running || result }"><b>01</b><span>真实来源</span><small>SEC · Stooq</small></div><i>→</i>
      <div :class="{ active: running || result }"><b>02</b><span>基线执行</span><small>Skill vCurrent</small></div><i>→</i>
      <div :class="{ active: running || result }"><b>03</b><span>证据评测</span><small>Fact-level gates</small></div><i>→</i>
      <div :class="{ active: result?.mutation }"><b>04</b><span>真实 Mutation</span><small>Genome JSON Patch</small></div><i>→</i>
      <div :class="{ active: result?.runtimeVerified }"><b>05</b><span>验证产物</span><small>runtimeVerified</small></div>
    </section>

    <section class="finance-case-launch">
      <div class="finance-field"><label>上市公司代码</label><input v-model="ticker" maxlength="12" spellcheck="false"></div>
      <div class="finance-field"><label>分析基准日</label><input v-model="asOfDate" type="date"></div>
      <div class="finance-field wide"><label>Initial Finance Skill</label><select v-model="selectedSkillId"><option disabled value="">请选择金融 Skill</option><option v-for="skill in financeSkills" :key="skill.id" :value="skill.id">{{ skill.name }} · {{ skill.currentVersionId }}</option></select></div>
      <div class="finance-field"><label>数据模式</label><select v-model="mode"><option value="live">在线数据 · LIVE</option><option value="verified_replay">已验证回放 · VERIFIED REPLAY</option></select></div>
      <div v-if="mode === 'verified_replay'" class="finance-field wide"><label>真实快照 Case</label><select v-model="replayCaseId"><option v-for="item in previousCases" :key="item.id" :value="item.id">{{ item.ticker }} · {{ item.asOfDate }} · {{ item.id }}</option></select></div>
      <button :disabled="running || !selectedSkillId || !preflight?.ready" @click="runCase"><span v-if="running" class="case-spinner"></span>{{ running ? '正在执行真实分析与进化…' : '运行真实金融 Case' }} <b>→</b></button>
    </section>

    <div v-if="!financeSkills.length && !error" class="finance-case-message warning">Initial Library 中没有 Finance Skill。请先在 Discovery 的“金融场景”完成初始化。</div>
    <div v-if="error" class="finance-case-message error"><strong>案例执行失败 <small>CASE FAILED</small></strong><span>{{ error }}</span></div>
    <div v-if="running" class="finance-case-running"><span></span><div><strong>执行中的请求没有模拟回退</strong><p>正在抓取 SEC 与市场数据、调用配置的 LLM、执行证据评测；若基线未通过，将应用 Genome Patch 并重跑。</p></div></div>

    <template v-if="result && report">
      <section class="case-result-heading"><div><p>{{ report.company.ticker }} · {{ report.asOfDate }}</p><h2>{{ report.company.name }}</h2><span>{{ result.mode === 'live' ? 'LIVE SOURCES' : 'VERIFIED REPLAY' }} · {{ result.id }}</span></div><div class="case-result-actions"><button @click="downloadReport(report)">下载报告 JSON</button><button v-if="result.agentPreset" class="secondary" @click="downloadPreset">下载 Runtime Preset</button></div></section>

      <section class="finance-case-scores">
        <article><span>基础版本 <small>BASELINE</small></span><strong>{{ baselineScore ?? '—' }}</strong><small>{{ result.baseline?.evaluation.passed ? '通过 · PASSED' : '未通过 · FAILED' }}</small></article>
        <article><span>优化后版本 <small>EVOLVED</small></span><strong>{{ evolvedScore ?? baselineScore ?? '—' }}</strong><small>{{ result.evolved ? (result.evolved.accepted ? '已验收 · ACCEPTED' : '未验收 · REJECTED') : '无需优化' }}</small></article>
        <article><span>分数变化 <small>SCORE DELTA</small></span><strong>{{ result.comparison ? `${result.comparison.scoreDelta > 0 ? '+' : ''}${result.comparison.scoreDelta}` : '—' }}</strong><small>证据评估器 · EVIDENCE EVALUATOR</small></article>
        <article :class="{ verified: result.runtimeVerified }"><span>运行时验证 <small>RUNTIME</small></span><strong>{{ result.runtimeVerified ? '通过' : '未通过' }}</strong><small>runtimeVerified</small></article>
      </section>

      <section class="finance-case-grid">
        <article class="case-panel sources"><header><span>来源与证据链 <small>PROVENANCE</small></span><h3>不可变来源快照</h3></header><a v-for="source in report.sources" :key="source.id" :href="source.url" target="_blank" rel="noreferrer"><div><b>{{ source.provider }}</b><strong>{{ source.title }}</strong><small>{{ source.fetchedAt }} · {{ source.contentType }}</small></div><code>{{ source.sha256.slice(0, 24) }}…</code></a></article>
        <article class="case-panel"><header><span>财务事实 <small>FINANCIAL FACTS</small></span><h3>可追溯核心指标</h3></header><div class="case-metric-list"><div v-for="fact in report.facts.filter((item) => item.metric.includes('annual_current') || item.metric === 'market_price_latest').slice(0, 10)" :key="fact.id"><span>{{ fact.label }}</span><strong>{{ formatValue(fact.value, fact.unit) }}</strong><small>{{ fact.periodEnd }} · {{ fact.form }} · {{ fact.factName }}</small></div><div v-for="metric in report.derivedMetrics" :key="metric.id" class="derived"><span>{{ metric.label }}</span><strong>{{ formatValue(metric.value, metric.unit) }}</strong><small>{{ metric.formula }}</small></div></div></article>
      </section>

      <section class="case-panel valuation"><header><span>估值敏感性 <small>VALUATION SENSITIVITY</small></span><h3>双方法三情景</h3></header><div class="valuation-table"><div class="head"><span>情景 <small>SCENARIO</small></span><span>市盈率</span><span>隐含价格</span><span>自由现金流收益率</span><span>隐含价格</span></div><div v-for="scenario in report.valuationScenarios" :key="scenario.name"><strong>{{ scenario.name }}</strong><span>{{ scenario.peMultiple }}×</span><span>{{ scenario.impliedPriceByPe ? `$${scenario.impliedPriceByPe}` : 'N/A' }}</span><span>{{ (scenario.fcfYield * 100).toFixed(1) }}%</span><span>{{ scenario.impliedPriceByFcf ? `$${scenario.impliedPriceByFcf}` : 'N/A' }}</span></div></div></section>

      <section class="finance-case-grid evaluation-grid">
        <article class="case-panel"><header><span>基础版本评估 <small>BASELINE EVALUATION</small></span><h3>实际失败证据</h3></header><div class="eval-list"><div v-for="item in result.baseline?.evaluation.cases" :key="item.id" :class="{ passed: item.passed }"><b>{{ item.passed ? '通过' : '未通过' }}</b><span><strong>{{ item.label }}</strong><small>{{ item.details }}</small></span><em>{{ item.score }}</em></div></div></article>
        <article class="case-panel"><header><span>最终评估 <small>FINAL EVALUATION</small></span><h3>优化后验收</h3></header><div class="eval-list"><div v-for="item in result.finalEvaluation?.cases" :key="item.id" :class="{ passed: item.passed }"><b>{{ item.passed ? '通过' : '未通过' }}</b><span><strong>{{ item.label }}</strong><small>{{ item.details }}</small></span><em>{{ item.score }}</em></div></div></article>
      </section>

      <section v-if="result.mutation" class="case-panel mutation-panel"><header><span>技能配置优化 <small>GENOME MUTATION</small></span><h3>{{ result.mutation.name }}</h3><p>{{ result.mutation.reason }}</p></header><div><code v-for="(operation, index) in result.mutation.genomePatch" :key="index"><b>{{ operation.op }}</b> {{ operation.path }} <span>{{ operation.value }}</span></code></div><footer><strong>{{ result.mutation.status === 'accepted' ? '已验收' : result.mutation.status === 'rejected' ? '未验收' : '测试中' }} <small>{{ result.mutation.status }}</small></strong><span>{{ result.mutation.tradeoff }}</span><em>{{ result.baseSkillVersionId }} → {{ result.evolvedSkillVersionId || '未验收' }}</em></footer></section>

      <FinanceBusinessReport :report="report" />
    </template>
  </main>
</template>
