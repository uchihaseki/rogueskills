<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const heading = ref<HTMLElement | null>(null)
const record = computed(() => props.controller.nodeDetailRecord)
const node = computed(() => props.controller.nodeDetailNode)
const monster = computed(() => props.controller.monsterById(record.value?.monsterId))
const type = computed(() => node.value ? props.controller.catalog.nodeTypes[node.value.type] : null)
const logs = computed(() => {
  const ids = new Set(record.value?.logIds ?? [])
  return props.controller.run?.logs.filter((item) => ids.has(item.id)) ?? []
})
const statDelta = computed(() => {
  const before = record.value?.before?.stats
  const after = record.value?.after?.stats
  if (!before || !after) return []
  return Object.keys({ ...before, ...after }).map((id) => ({
    id,
    label: props.controller.catalog.statLabels[id] ?? id,
    before: before[id] ?? 0,
    after: after[id] ?? 0,
    delta: (after[id] ?? 0) - (before[id] ?? 0),
  })).filter((item) => item.delta !== 0)
})

function signed(value: number): string {
  return `${value > 0 ? '+' : ''}${value}`
}

const recordStatusLabels: Record<string, string> = {
  entered: '执行中',
  completed: '已完成',
  failed: '未通过',
}

function handleEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.controller.closeNodeDetail()
}

watch(() => props.controller.nodeDetailNodeId, async (value) => {
  if (!value) return
  await nextTick()
  heading.value?.focus()
})

onMounted(() => {
  window.addEventListener('keydown', handleEscape)
  void nextTick(() => heading.value?.focus())
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleEscape))
</script>

<template>
  <Teleport to="body">
    <div v-if="record && node" class="node-detail-backdrop pixel-run-theme" @click.self="controller.closeNodeDetail">
      <aside id="node-detail-drawer" class="node-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="node-detail-title">
        <header class="node-detail-heading">
          <div><span>测试 {{ String(record.sequence).padStart(2, '0') }} · 阶段 {{ record.act }} <small>TEST · STAGE</small></span><h2 id="node-detail-title" ref="heading" tabindex="-1">{{ monster?.name ?? (node.type === 'lab' ? '候选优化生成' : node.type === 'rest' ? '预算恢复' : type?.name) }}</h2><p>{{ monster?.failureMode ?? type?.description }}</p></div>
          <button aria-label="关闭测试详情" @click="controller.closeNodeDetail">×</button>
        </header>

        <div class="node-detail-status"><b :class="record.status">{{ recordStatusLabels[record.status] ?? record.status }}</b><span>{{ controller.displayRunText(record.regionName) }} · L{{ record.layer + 1 }} · {{ type?.englishName }} · D{{ record.difficulty }}</span></div>
        <p v-if="record.legacyIncomplete" class="node-legacy-warning">旧版运行未保存该测试的完整候选配置与优化证据；这里只展示能够从历史基准评估证明的内容。</p>

        <section v-if="monster" class="node-detail-section"><span>业务失败模式 <small>BUSINESS FAILURE MODE</small></span><h3>{{ monster.failureMode }}</h3><p>{{ monster.businessExample }}</p></section>

        <section v-if="record.before" class="node-detail-section"><span>进入节点时的候选配置 <small>CANDIDATE ON ENTRY</small></span><div class="node-resource-grid"><div><small>失败预算 · FAILURE</small><strong>{{ record.before.stability }}</strong></div><div><small>算力预算 · COMPUTE</small><strong>{{ record.before.compute }}</strong></div><div><small>已用复杂度 · COMPLEXITY</small><strong>{{ record.before.complexityUsed }}</strong></div><div><small>候选优化项 · CHANGES</small><strong>{{ record.before.mutationIds.length }}</strong></div></div></section>

        <section v-if="record.result" class="node-detail-section"><span>测试结果 <small>TEST RESULT</small></span>
          <div v-if="record.result.kind === 'rest'" class="node-result-summary"><strong>运行预算已恢复</strong><p>失败预算 {{ signed(record.result.healed ?? 0) }} · 算力预算 {{ signed(record.result.computeReward ?? 0) }}</p></div>
          <div v-else-if="record.result.kind === 'lab'" class="node-result-summary"><strong>候选优化项已生成</strong><p>该测试不运行基准评估，直接生成候选优化项。</p></div>
          <template v-else>
            <div class="node-score-grid"><div><small>覆盖率 · COVERAGE</small><strong>{{ record.result.coverage ?? '—' }}</strong></div><div><small>通过线 · THRESHOLD</small><strong>{{ record.result.threshold ?? '—' }}</strong></div><div><small>算力消耗 · COMPUTE</small><strong>{{ record.result.computeCost ?? '—' }}</strong></div><div><small>结论 · VERDICT</small><strong>{{ record.result.passed ? '通过' : '未通过' }}</strong></div></div>
            <div v-if="record.result.cases?.length" class="node-case-list"><div v-for="item in record.result.cases" :key="item.label" :class="{ passed: item.passed }"><b>{{ item.passed ? '通过' : '未通过' }}</b><span>{{ item.label }}</span><em>{{ item.score }}</em></div></div>
          </template>
        </section>

        <section v-if="record.reward.mutationDraftIds.length" class="node-detail-section"><span>候选优化项 <small>CANDIDATE CHANGES</small></span><div class="node-mutation-list"><article v-for="mutationId in record.reward.mutationDraftIds" :key="mutationId" :class="{ selected: record.reward.selectedMutationId === mutationId }"><div><b>{{ controller.mutationById(mutationId)?.name ?? mutationId }}</b><small>{{ controller.mutationById(mutationId)?.englishName }} · {{ controller.mutationById(mutationId)?.rarity }}</small></div><p>{{ controller.mutationById(mutationId)?.benefit }}</p><strong v-if="record.reward.selectedMutationId === mutationId">已选择</strong></article></div><p v-if="record.reward.skipped" class="node-skip-note">本次未应用候选优化项，配置保持不变。</p></section>

        <section v-if="record.reward.unlockedEvolutionIds.length" class="node-detail-section"><span>已启用能力组合 <small>CAPABILITY BUNDLE ENABLED</small></span><article v-for="evolutionId in record.reward.unlockedEvolutionIds" :key="evolutionId" class="node-evolution"><b>{{ controller.evolutionById(evolutionId)?.name ?? evolutionId }}</b><p>{{ controller.evolutionById(evolutionId)?.subtitle }}</p></article></section>

        <section v-if="statDelta.length" class="node-detail-section"><span>能力变化 <small>CAPABILITY DELTA</small></span><div class="node-delta-list"><div v-for="item in statDelta" :key="item.id"><span>{{ item.label }}</span><small>{{ item.before }} → {{ item.after }}</small><strong :class="{ positive: item.delta > 0, negative: item.delta < 0 }">{{ signed(item.delta) }}</strong></div></div></section>

        <section v-if="record.after" class="node-detail-section"><span>离开节点时的候选配置 <small>CANDIDATE ON EXIT</small></span><div class="node-resource-grid"><div><small>失败预算 · FAILURE</small><strong>{{ record.after.stability }}</strong></div><div><small>算力预算 · COMPUTE</small><strong>{{ record.after.compute }}</strong></div><div><small>已用复杂度 · COMPLEXITY</small><strong>{{ record.after.complexityUsed }}</strong></div><div><small>候选优化项 · CHANGES</small><strong>{{ record.after.mutationIds.length }}</strong></div></div></section>

        <section v-if="logs.length" class="node-detail-section"><span>测试执行日志 <small>TEST EXECUTION LOG</small></span><div class="node-log-list"><p v-for="item in logs" :key="item.id"><b>#{{ item.id }}</b>{{ controller.displayRunText(item.message) }}</p></div></section>
      </aside>
    </div>
  </Teleport>
</template>
