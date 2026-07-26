<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import MapNode from './MapNode.vue'

defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <section v-if="controller.displayRegion" class="panel map-panel">
    <nav class="map-act-tabs" aria-label="Evaluation stages">
      <button
        v-for="(region, index) in controller.run!.map"
        :key="region.act"
        :class="{ active: controller.mapActIndex === index, completed: index < controller.run!.actIndex }"
        @click="controller.setMapActIndex(index)"
      >阶段 {{ region.act }}<small>{{ region.englishName ?? controller.runEnglishName(region.name) }}</small></button>
    </nav>
    <div class="region-heading"><div><span>阶段 {{ controller.displayRegion.act }} · 评估计划 <small>STAGE · EVALUATION PLAN</small></span><h1>{{ controller.displayRunText(controller.displayRegion.name) }}</h1><p>{{ controller.displayRunText(controller.displayRegion.description) }}</p></div><div class="region-seed"><small>运行种子 · RUN SEED</small><strong>{{ controller.run!.seed }}</strong></div></div>
    <div class="map-stage"><div class="map-grid">
      <div v-for="(layer, layerIndex) in controller.displayRegion.layers" :key="layerIndex" class="map-layer" :class="{ current: controller.mapActIndex === controller.run!.actIndex && layerIndex === controller.run!.layerIndex }">
        <div class="layer-label"><span>{{ String(layerIndex + 1).padStart(2, '0') }}</span><small>{{ layerIndex === controller.displayRegion.layers.length - 1 ? 'HOLDOUT' : 'TESTS' }}</small></div>
        <div class="layer-nodes"><MapNode v-for="node in layer" :key="node.id" :controller="controller" :node="node" /></div>
        <span v-if="layerIndex < controller.displayRegion.layers.length - 1" class="path-line">→</span>
      </div>
    </div></div>
    <div class="map-legend"><span><i class="normal"></i>标准评估</span><span><i class="elite"></i>压力评估</span><span><i class="utility"></i>候选优化 / 预算</span><span><i class="boss"></i>隐藏留出集</span></div>
  </section>
</template>
