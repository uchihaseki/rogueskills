<script setup lang="ts">
import type { FinanceResearchReport } from '@/types/domain'

withDefaults(defineProps<{
  report: FinanceResearchReport
  variant?: 'case' | 'validation'
}>(), {
  variant: 'case',
})
</script>

<template>
  <section
    class="finance-business-report"
    :class="variant === 'case' ? 'case-panel narrative-panel' : 'validation-business-report'"
  >
    <header v-if="variant === 'case'">
      <span>业务研究报告 <small>RESEARCH OUTPUT</small></span>
      <h3>证据约束的分析结论</h3>
    </header>
    <template v-else>
      <span>候选业务报告 <small>CANDIDATE BUSINESS REPORT</small></span>
      <h3>真实数据回放生成的公司研究结论</h3>
    </template>

    <p class="case-summary">{{ report.narrative.summary }}</p>

    <div class="finding-list">
      <article v-for="finding in report.narrative.findings" :key="finding.id">
        <b>{{ finding.kind }}</b>
        <p>{{ finding.claim }}</p>
        <small>{{ finding.evidenceIds.join(' · ') }}</small>
      </article>
    </div>

    <div class="risk-list">
      <article v-for="risk in report.narrative.risks" :key="risk.id">
        <b>风险 <small>RISK</small></b>
        <p>{{ risk.risk }}</p>
        <small v-if="risk.evidenceIds.length">{{ risk.evidenceIds.join(' · ') }}</small>
      </article>
    </div>

    <div v-if="report.narrative.dataGaps.length" class="data-gap-list">
      <b>数据缺口 <small>DATA GAPS</small></b>
      <ul><li v-for="gap in report.narrative.dataGaps" :key="gap">{{ gap }}</li></ul>
    </div>

    <footer>{{ report.narrative.conclusionBoundary }}</footer>
  </section>
</template>

<style scoped>
.finance-business-report > span,
.finance-business-report header span {
  display: block;
}

.finance-business-report span small,
.finance-business-report b small {
  margin-left: 6px;
  color: inherit;
  font-size: 0.78em;
  opacity: 0.68;
}

.finance-business-report.validation-business-report .case-summary {
  margin: 10px 0 0;
  color: var(--run-text);
  font-size: 13px;
  line-height: 1.7;
}

.finance-business-report.validation-business-report .finding-list,
.finance-business-report.validation-business-report .risk-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.finance-business-report.validation-business-report article,
.finance-business-report .data-gap-list {
  padding: 12px;
  border: 1px solid var(--run-border);
  background: rgb(255 255 255 / 2%);
}

.finance-business-report .data-gap-list {
  margin-top: 10px;
}

.finance-business-report .data-gap-list b {
  color: var(--run-warning);
  font-size: 10px;
}

.finance-business-report .data-gap-list ul {
  margin: 8px 0 0;
  padding-left: 18px;
}

.finance-business-report .data-gap-list li {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.55;
}

@media (max-width: 760px) {
  .finance-business-report.validation-business-report .finding-list,
  .finance-business-report.validation-business-report .risk-list {
    grid-template-columns: 1fr;
  }
}
</style>
