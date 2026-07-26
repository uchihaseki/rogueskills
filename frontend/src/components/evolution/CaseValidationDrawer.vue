<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import FinanceBusinessReport from '@/components/finance/FinanceBusinessReport.vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const closeButton = ref<HTMLButtonElement | null>(null)
const validation = computed(() => props.controller.caseValidation)
const report = computed(() => validation.value?.candidate?.report)
const gateRows = computed(() => {
  const baseline = new Map(validation.value?.baseline?.evaluation.cases.map((item) => [item.id, item]) ?? [])
  return validation.value?.candidate?.evaluation.cases.map((candidate) => ({
    id: candidate.id,
    label: candidate.label,
    hardGate: candidate.hardGate,
    baseline: baseline.get(candidate.id),
    candidate,
  })) ?? []
})

function contributionName(kind: string, id: string): string {
  return kind === 'mutation'
    ? props.controller.mutationById(id)?.name ?? id
    : props.controller.evolutionById(id)?.name ?? id
}

const promotionLabels: Record<string, string> = {
  pending: '等待晋升',
  not_eligible: '不满足晋升条件',
  created: '已创建运行时验证版本',
  version_conflict: '技能版本冲突',
  failed: '晋升失败',
}

function promotionLabel(status: string): string {
  return promotionLabels[status] ?? status
}

function handleEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.controller.closeCaseValidationDetail()
}

onMounted(() => {
  window.addEventListener('keydown', handleEscape)
  void nextTick(() => closeButton.value?.focus())
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleEscape))
</script>

<template>
  <Teleport to="body">
    <div v-if="validation && report" class="case-validation-backdrop pixel-run-theme" @click.self="controller.closeCaseValidationDetail">
      <main class="case-validation-drawer" role="dialog" aria-modal="true" aria-labelledby="case-validation-title">
        <header class="case-validation-heading"><div><span>已记录真实数据案例 · 运行时证据 <small>RECORDED REAL-DATA CASE · RUNTIME EVIDENCE</small></span><h2 id="case-validation-title">{{ report.company.name }}</h2><p>{{ report.company.ticker }} · {{ report.asOfDate }} · {{ validation.id }}</p></div><button ref="closeButton" aria-label="关闭运行时验证详情" @click="controller.closeCaseValidationDetail">×</button></header>

        <FinanceBusinessReport :report="report" variant="validation" />

        <section class="validation-comparison-hero"><article><span>基础版本 <small>BASELINE</small></span><strong>{{ validation.comparison?.baselineScore }}</strong><small>{{ validation.comparison?.baselineHardGatesPassed ? '硬门槛通过 · HARD GATES PASS' : '硬门槛未通过 · HARD GATES FAIL' }}</small></article><article><span>候选配置 <small>CANDIDATE</small></span><strong>{{ validation.comparison?.candidateScore }}</strong><small>{{ validation.comparison?.candidateHardGatesPassed ? '硬门槛通过 · HARD GATES PASS' : '硬门槛未通过 · HARD GATES FAIL' }}</small></article><article><span>分数变化 <small>SCORE DELTA</small></span><strong>{{ validation.comparison ? `${validation.comparison.scoreDelta > 0 ? '+' : ''}${validation.comparison.scoreDelta}` : '—' }}</strong><small>{{ validation.accepted ? '已验收 · ACCEPTED' : '未验收 · NOT ACCEPTED' }}</small></article><article><span>运行时验证 <small>RUNTIME</small></span><strong>{{ validation.runtimeVerified ? '已验证' : '未验证' }}</strong><small>runtimeVerified</small></article></section>

        <section class="validation-detail-section"><span>来源与证据链 <small>SOURCE PROVENANCE</small></span><div class="validation-source-list"><a v-for="source in report.sources" :key="source.id" :href="source.url" target="_blank" rel="noreferrer"><div><b>{{ source.provider }}</b><strong>{{ source.title }}</strong><small>{{ source.fetchedAt }}</small></div><code>{{ source.sha256.slice(0, 22) }}…</code></a></div><div class="validation-digests"><code>来源 SOURCE {{ validation.sourceBundleDigest }}</code><code>数据集 DATASET {{ validation.datasetDigest }}</code><code>策略 POLICY {{ validation.executionPolicyDigest }}</code><code>预设 PRESET {{ validation.candidatePresetDigest }}</code></div></section>

        <section class="validation-detail-section"><span>硬门槛与评估对照 <small>HARD GATE & EVALUATION COMPARISON</small></span><div class="validation-gate-list"><div v-for="row in gateRows" :key="row.id" :class="{ repaired: !row.baseline?.passed && row.candidate.passed, regressed: row.baseline?.passed && !row.candidate.passed }"><span><b v-if="row.hardGate">硬门槛</b>{{ row.label }}</span><small>{{ row.baseline?.score ?? '—' }} · {{ row.baseline?.passed ? '通过 PASS' : '未通过 FAIL' }}</small><i>→</i><strong>{{ row.candidate.score }} · {{ row.candidate.passed ? '通过' : '未通过' }}</strong></div></div></section>

        <section class="validation-detail-section"><span>候选优化覆盖 · 关联而非独立因果 <small>CANDIDATE CHANGE COVERAGE · ASSOCIATED, NOT CAUSAL</small></span><div class="validation-contribution-list"><article v-for="item in validation.contributionCoverage" :key="`${item.kind}:${item.id}`" :class="{ repaired: item.repairedCaseIds.length }"><div><small>{{ item.kind === 'mutation' ? '候选优化项 · candidate change' : '能力组合 · capability bundle' }}</small><strong>{{ contributionName(item.kind, item.id) }}</strong></div><p>目标：{{ item.targetCaseIds.join(' · ') || '未声明评估门槛' }}</p><b v-if="item.repairedCaseIds.length">关联修复：{{ item.repairedCaseIds.join(' · ') }}</b></article></div></section>

        <section class="validation-detail-section validation-promotion"><span>版本晋升结果 <small>PROMOTION RESULT</small></span><h3>{{ promotionLabel(validation.promotion.status) }}</h3><p v-if="validation.promotion.promoted">已创建通过运行时验证的技能版本：<code>{{ validation.promotion.evolvedSkillVersionId }}</code></p><p v-else>{{ validation.promotion.error?.message ?? '候选配置未满足严格晋升条件。' }}</p><div><b>运行时验证：{{ validation.runtimeVerified ? '通过' : '未通过' }}</b><b>候选验收：{{ validation.accepted ? '通过' : '未通过' }}</b><b>版本晋升：{{ validation.promotion.promoted ? '完成' : '未完成' }}</b></div></section>
      </main>
    </div>
  </Teleport>
</template>
