<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import type { Mutation } from '@/types/domain'

defineProps<{ controller: EvolutionController; mutation: Mutation }>()
</script>

<template>
  <button class="mutation-card" :class="mutation.rarity" @click="controller.chooseMutation(mutation.id)">
    <div class="mutation-card-top"><span>{{ mutation.category }}</span><em>{{ mutation.rarity }}</em></div>
    <h3>{{ mutation.name }}</h3>
    <div class="effect-row"><span v-for="(value, stat) in mutation.effects" :key="stat" class="effect" :class="value > 0 ? 'positive' : 'negative'">{{ controller.catalog.statLabels[stat] ?? stat }} {{ value > 0 ? '+' : '' }}{{ value }}</span></div>
    <p>{{ mutation.benefit }}</p><div class="tradeoff"><span>代价</span>{{ mutation.tradeoff }}</div>
    <div class="mutation-card-foot"><span>{{ mutation.tags.map((tag) => `#${tag}`).join(' ') }}</span><strong>复杂度 {{ mutation.complexityCost }}</strong></div>
  </button>
</template>
