<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import type { RunNode } from '@/types/domain'

const props = defineProps<{ controller: EvolutionController; node: RunNode }>()
const state = () => props.controller.nodeState(props.node)
const type = () => props.controller.catalog.nodeTypes[props.node.type]
const monster = () => props.controller.monsterById(props.node.monsterId)
const hidden = () => props.node.type === 'boss' && state() === 'locked'
const title = () => hidden() ? '隐藏留出集评估' : monster()?.name ?? (props.node.type === 'lab' ? '候选优化生成' : '预算恢复')
const subtitle = () => hidden() ? '数据与规则未公开' : monster()?.failureMode ?? type()?.description
const canInspect = () => ['selected', 'completed', 'failed'].includes(state())
const disabled = () => !canInspect() && state() !== 'available'
const actionLabel = () => canInspect() ? `查看 ${title()} 测试详情` : `选择 ${title()} 测试`
</script>

<template>
  <button class="map-node" :class="[node.type, state(), { targeted: controller.run?.automation?.selectedMonsterIds.includes(node.monsterId ?? ''), inspectable: canInspect() }]" :disabled="disabled()" :aria-label="actionLabel()" :aria-expanded="canInspect() ? controller.nodeDetailNodeId === node.id : undefined" :aria-controls="canInspect() ? 'node-detail-drawer' : undefined" @click="controller.handleNodeClick(node)">
    <span class="node-symbol">{{ state() === 'completed' ? '✓' : type()?.symbol }}</span>
    <span class="node-copy"><small>{{ monster()?.englishName ?? type()?.englishName }} · D{{ node.difficulty }}</small><strong>{{ title() }}</strong><em>{{ subtitle() }}</em></span>
    <span v-if="controller.run?.automation?.selectedMonsterIds.includes(node.monsterId ?? '')" class="node-target">目标</span>
    <span v-if="state() === 'available'" class="node-enter">选择 →</span>
    <span v-else-if="canInspect()" class="node-enter">详情 ↗</span>
  </button>
</template>
