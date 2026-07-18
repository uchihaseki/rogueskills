<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import type { RunNode } from '@/types/domain'

const props = defineProps<{ controller: EvolutionController; node: RunNode }>()
const state = () => props.controller.nodeState(props.node)
const type = () => props.controller.catalog.nodeTypes[props.node.type]
const monster = () => props.controller.monsterById(props.node.monsterId)
const hidden = () => props.node.type === 'boss' && state() === 'locked'
const title = () => hidden() ? '隐藏验收' : monster()?.name ?? (props.node.type === 'lab' ? '进化实验室' : '安全节点')
const subtitle = () => hidden() ? '数据与规则未公开' : monster()?.failureMode ?? type()?.description
</script>

<template>
  <button class="map-node" :class="[node.type, state()]" :disabled="state() !== 'available'" :aria-label="title()" @click="controller.selectNode(node.id)">
    <span class="node-symbol">{{ state() === 'completed' ? '✓' : type()?.symbol }}</span>
    <span class="node-copy"><small>{{ type()?.name }} · D{{ node.difficulty }}</small><strong>{{ title() }}</strong><em>{{ subtitle() }}</em></span>
    <span v-if="state() === 'available'" class="node-enter">选择 →</span>
  </button>
</template>
