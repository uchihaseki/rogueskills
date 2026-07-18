<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import MapNode from './MapNode.vue'

defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <section v-if="controller.currentRegion" class="panel map-panel">
    <div class="region-heading"><div><span>ACT {{ controller.currentRegion.act }} · BUSINESS SCENARIO MAP</span><h1>{{ controller.currentRegion.name }}</h1><p>{{ controller.currentRegion.description }}</p></div><div class="region-seed"><small>MAP SEED</small><strong>{{ controller.run!.seed }}</strong></div></div>
    <div class="map-stage"><div class="map-grid">
      <div v-for="(layer, layerIndex) in controller.currentRegion.layers" :key="layerIndex" class="map-layer" :class="{ current: layerIndex === controller.run!.layerIndex }">
        <div class="layer-label"><span>{{ String(layerIndex + 1).padStart(2, '0') }}</span><small>{{ layerIndex === controller.currentRegion.layers.length - 1 ? 'BOSS' : 'ROUTE' }}</small></div>
        <div class="layer-nodes"><MapNode v-for="node in layer" :key="node.id" :controller="controller" :node="node" /></div>
        <span v-if="layerIndex < controller.currentRegion.layers.length - 1" class="path-line">→</span>
      </div>
    </div></div>
    <div class="map-legend"><span><i class="normal"></i>普通 Benchmark</span><span><i class="elite"></i>精英验证</span><span><i class="utility"></i>实验 / 休息</span><span><i class="boss"></i>Hidden Test</span></div>
  </section>
</template>
