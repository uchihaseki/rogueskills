<script setup lang="ts">
import { computed } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const validation = computed(() => props.controller.caseValidation)
const selectedOption = computed(() => props.controller.caseValidationOptions.find(
  (item) => item.caseId === props.controller.selectedReplayCaseId,
))
const running = computed(() => validation.value && ['queued', 'running'].includes(validation.value.status))
const failedSameSelection = computed(() => validation.value?.status === 'failed'
  && validation.value.replayCaseId === props.controller.selectedReplayCaseId)
const phaseLabels: Record<string, string> = {
  queued: '等待执行',
  loading_replay: '加载真实来源快照',
  validating_preset: '校验候选预设',
  building_dataset: '构建同源数据集',
  executing_baseline: '执行基础技能版本',
  evaluating_baseline: '评估基线版本',
  executing_candidate: '执行候选智能体预设',
  evaluating_candidate: '评估候选版本',
  comparing: '生成严格同源对照',
  promoting: '晋升运行时绑定',
  completed: '验证完成',
  failed: '验证失败',
}
const phaseLabel = computed(() => {
  const phase = validation.value?.phase
  return phase ? phaseLabels[phase] ?? phase : '未开始'
})
</script>

<template>
  <section class="case-validation-card">
    <header><span>已验证回放 · 运行时验证 <small>VERIFIED REPLAY · RUNTIME VALIDATION</small></span><strong>在已持久化的真实数据上验证候选配置</strong><p>基础技能与候选智能体预设使用相同的来源快照、数据集、模型设置、预算和评估器，执行严格的同源对照；不会重新请求在线数据。</p></header>
    <div class="validation-boundary">
      <span>当前证据模式</span><b>能力模拟 · capability-simulation-v1</b>
      <span>基础技能版本</span><code>{{ controller.agentPreset?.sourceRun.baseSkillVersionId }}</code>
      <span>候选智能体预设</span><code>{{ controller.agentPreset?.id }}</code>
      <span>候选配置摘要</span><code>{{ controller.agentPreset?.digest }}</code>
    </div>

    <template v-if="!validation || validation.status === 'failed'">
      <label>已验证回放案例 <small>VERIFIED REPLAY</small>
        <select v-model="controller.selectedReplayCaseId" :disabled="controller.caseValidationPending || !controller.caseValidationOptions.length">
          <option value="" disabled>{{ controller.caseValidationOptions.length ? '选择一个已记录的真实数据案例' : '没有可用的真实数据案例' }}</option>
          <option v-for="option in controller.caseValidationOptions" :key="option.caseId" :value="option.caseId">{{ option.demoIncluded ? '内置真实案例 · ' : '' }}{{ option.caseLabel ?? option.ticker ?? '案例' }} · {{ option.asOfDate ?? '日期未知' }}</option>
        </select>
      </label>
      <div v-if="selectedOption" class="validation-option-meta"><span>{{ selectedOption.demoIncluded ? '内置真实数据案例' : '已记录真实数据案例' }} · 原始来源 {{ selectedOption.sourceMode === 'live' ? '在线采集' : '回放' }} <small>VERIFIED REPLAY · SOURCE ORIGIN {{ selectedOption.sourceMode.toUpperCase() }}</small></span><strong>{{ selectedOption.caseLabel ?? selectedOption.ticker }} · {{ selectedOption.asOfDate }}</strong><p v-if="selectedOption.caseDescription">{{ selectedOption.caseDescription }}</p><small>{{ selectedOption.sourceCount }} 个来源 · {{ selectedOption.sourceProviders.join(' / ') }} · 捕获于 {{ selectedOption.sourceCapturedAt ?? '时间未知' }}</small><small>来源摘要 {{ selectedOption.sourceBundleDigest }}</small><small>{{ selectedOption.caseId }}</small></div>
      <p v-if="failedSameSelection" class="preset-error">上一次验证失败的证据已保留，可以在修复运行环境后重新执行。</p>
      <button class="primary-button" :disabled="controller.caseValidationPending || !controller.selectedReplayCaseId" @click="controller.startCaseValidation">{{ controller.caseValidationPending ? '正在创建验证…' : failedSameSelection ? '重新运行时验证' : '开始运行时验证' }}</button>
    </template>

    <div v-if="running" class="validation-running"><span class="validation-pulse"></span><div><b>{{ phaseLabel }}</b><small>{{ validation?.id }}</small></div></div>

    <div v-else-if="validation?.status === 'succeeded'" class="validation-result-summary">
      <div class="validation-score-row"><div><span>基础版本 <small>BASELINE</small></span><strong>{{ validation.comparison?.baselineScore }}</strong></div><div><span>候选配置 <small>CANDIDATE</small></span><strong>{{ validation.comparison?.candidateScore }}</strong></div><div><span>分数变化 <small>DELTA</small></span><strong>{{ validation.comparison ? `${validation.comparison.scoreDelta > 0 ? '+' : ''}${validation.comparison.scoreDelta}` : '—' }}</strong></div></div>
      <div class="validation-badges"><b :class="{ passed: validation.runtimeVerified }">运行时验证：{{ validation.runtimeVerified ? '通过' : '未通过' }}</b><b :class="{ passed: validation.accepted }">候选验收：{{ validation.accepted ? '通过' : '未通过' }}</b><b :class="{ passed: validation.promotion.promoted }">晋升：{{ validation.promotion.promoted ? '完成' : '未完成' }}</b></div>
      <p>已记录真实数据案例 · {{ validation.replayCaseId }}</p>
      <button class="primary-button" @click="controller.openCaseValidationDetail">查看业务报告与完整对照</button>
    </div>

    <p v-if="controller.caseValidationError || validation?.error" class="preset-error">{{ controller.caseValidationError || validation?.error?.message }} <small v-if="validation?.error?.code">{{ validation.error.code }}</small></p>
    <small class="validation-disclaimer">该模式使用已持久化的真实来源快照，不会重新请求在线数据提供方。同源对照可以证明候选配置与门槛修复相关，但不宣称单个优化项具有独立因果关系。</small>
  </section>
</template>
