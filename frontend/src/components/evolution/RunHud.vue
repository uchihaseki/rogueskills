<script setup lang="ts">
import { computed } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const run = computed(() => props.controller.run!)
const region = computed(() => props.controller.currentRegion!)
const stabilityPercent = computed(() => Math.max(0, run.value.stability / props.controller.MAX_STABILITY * 100))
const complexityPercent = computed(() => Math.min(100, run.value.complexityUsed / run.value.complexityMax * 100))
</script>

<template>
  <section class="hud">
    <div class="hud-card act-hud"><span class="hud-icon">S{{ run.actIndex + 1 }}</span><div><small>当前评估阶段</small><strong>{{ controller.displayRunText(region.name) }}</strong></div></div>
    <div class="hud-card"><span class="hud-icon integrity">F</span><div class="resource-copy"><small>失败预算 · FAILURE BUDGET</small><strong>{{ run.stability }}<i> / {{ controller.MAX_STABILITY }}</i></strong><span class="resource-bar danger"><b :style="{ width: `${stabilityPercent}%` }"></b></span></div></div>
    <div class="hud-card"><span class="hud-icon compute">C</span><div class="resource-copy"><small>算力预算 · COMPUTE BUDGET</small><strong>{{ run.compute }}<i> units</i></strong><span class="resource-bar compute-bar"><b :style="{ width: `${Math.min(100, run.compute)}%` }"></b></span></div></div>
    <div class="hud-card"><span class="hud-icon complexity">◇</span><div class="resource-copy"><small>复杂度预算 · COMPLEXITY BUDGET</small><strong>{{ run.complexityUsed }}<i> / {{ run.complexityMax }}</i></strong><span class="resource-bar complexity-bar"><b :style="{ width: `${complexityPercent}%` }"></b></span></div></div>
    <div class="hud-card score-hud"><small>加权分数 · WEIGHTED SCORE</small><strong>{{ controller.objectiveScore(run) }}</strong><span>{{ controller.catalog.runModes[run.modeId]?.name }}</span></div>
  </section>
</template>
