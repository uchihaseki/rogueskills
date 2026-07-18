<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
defineProps<{ controller: DiscoveryController }>()
</script>

<template>
  <div v-if="!controller.state.preview" class="genome-empty"><span>DNA</span><h3>等待材料转换</h3><p>转换结果会显示抽取出的目标、Workflow、约束、工具、完整度和安全风险。</p></div>
  <div v-else class="genome-preview"><div class="genome-heading"><div><span>SKILL GENOME · {{ controller.state.preview.schemaVersion }}</span><h2>{{ controller.state.preview.name }}</h2></div><div class="completeness-ring" :style="{ '--score': `${controller.state.preview.metadata.completeness * 3.6}deg` }"><strong>{{ controller.state.preview.metadata.completeness }}</strong><small>完整度</small></div></div>
    <p class="genome-description">{{ controller.state.preview.description }}</p><div class="genome-status-row"><span class="quarantine-tag">QUARANTINE</span><span class="risk-badge" :class="controller.state.preview.risk.level">{{ controller.state.preview.risk.level }} risk</span><span>{{ controller.state.preview.metadata.license }}</span></div>
    <div class="genome-block"><span>WORKFLOW · {{ controller.state.preview.workflow.steps.length }} STEPS</span><ol><li v-for="step in controller.state.preview.workflow.steps" :key="step.order"><b>{{ step.order }}</b><p>{{ step.instruction }}</p></li><li v-if="!controller.state.preview.workflow.steps.length" class="missing">没有识别出明确步骤，需要人工补充。</li></ol></div>
    <div class="genome-columns"><div class="genome-block"><span>CONSTRAINTS</span><ul><li v-for="item in controller.state.preview.constraints" :key="item">{{ item }}</li><li v-if="!controller.state.preview.constraints.length" class="missing">未识别</li></ul></div><div class="genome-block"><span>TOOLS</span><div class="tool-list"><i v-for="tool in controller.state.preview.tools" :key="tool">{{ tool }}</i><i v-if="!controller.state.preview.tools.length">未声明</i></div></div></div>
    <div class="gate-list"><div v-for="gate in controller.state.preview.evaluation.requiredGates" :key="gate"><span>○</span><strong>{{ gate }}</strong><small>NOT RUN</small></div></div><button class="primary-button" @click="controller.stagePreview">保存到隔离候选库 <b>→</b></button>
  </div>
</template>
