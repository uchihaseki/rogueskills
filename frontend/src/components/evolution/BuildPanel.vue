<script setup lang="ts">
import { computed } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const run = computed(() => props.controller.run!)
const mutations = computed(() => run.value.mutationIds.map(props.controller.mutationById).filter(Boolean))
const evolutions = computed(() => run.value.evolutionIds.map(props.controller.evolutionById).filter(Boolean))
const recipes = computed(() => props.controller.evolutionProgress(run.value)
  .filter((item) => !item.unlocked)
  .sort((left, right) => right.progress / right.total - left.progress / left.total)
  .slice(0, 3))
</script>

<template>
  <aside class="panel build-panel">
    <div class="panel-heading"><div><span>SKILL GENOME</span><h2>当前构筑</h2></div><span class="build-count">{{ run.mutationIds.length }} MUT</span></div>
    <div class="build-section"><span class="section-label">基础武器</span><div class="base-weapons"><div v-for="(weapon, index) in run.initialWeapons" :key="weapon"><b>0{{ index + 1 }}</b><span>{{ weapon }}</span></div></div></div>
    <div class="build-section"><span class="section-label">能力属性</span><div class="stat-list"><div v-for="(value, stat) in run.stats" :key="stat" class="stat-row"><span>{{ controller.catalog.statLabels[stat] }}</span><i><b :style="{ width: `${value}%` }"></b></i><strong>{{ value }}</strong></div></div></div>
    <div class="build-section mutation-stack-section"><span class="section-label">已装配 Mutation</span><div class="mutation-stack">
      <div v-for="mutation in mutations" :key="mutation.id" class="equipped-mutation"><span class="rarity-dot" :class="mutation.rarity"></span><div><strong>{{ mutation.name }}</strong><small>{{ mutation.category }} · {{ mutation.tags.join(' / ') }}</small></div><b>{{ mutation.complexityCost }}</b></div>
      <p v-if="!mutations.length" class="empty-copy">尚未装配能力。通过第一个遭遇获得 Mutation。</p>
    </div></div>
    <div class="build-section evolution-section"><span class="section-label">武器进化</span>
      <div v-if="evolutions.length" class="unlocked-evolutions"><div v-for="evolution in evolutions" :key="evolution.id" class="evolution-badge"><span>✦</span><div><strong>{{ evolution.name }}</strong><small>{{ evolution.subtitle }}</small></div></div></div>
      <div class="recipe-list"><div v-for="recipe in recipes" :key="recipe.id" class="recipe"><div><strong>{{ recipe.name }}</strong><span>{{ recipe.progress }}/{{ recipe.total }}</span></div><i><b :style="{ width: `${recipe.progress / recipe.total * 100}%` }"></b></i><small>{{ recipe.requirements.map((item) => `${item.tag} ${item.current}/${item.required}`).join(' · ') }}</small></div></div>
    </div>
  </aside>
</template>
