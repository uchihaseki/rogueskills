<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{
  controller: EvolutionController
  layout?: 'grid' | 'row'
  animate?: boolean
}>()

const root = ref<HTMLElement | null>(null)
const profile = computed(() => props.controller.selectedSkill?.capabilityProfile
  ?? props.controller.catalog.archetypes.browser?.stats
  ?? {})

async function animateBars() {
  if (props.animate === false) return
  await nextTick()
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  root.value?.querySelectorAll<HTMLElement>('i b').forEach((bar, index) => {
    bar.style.transitionDelay = reduced ? '0ms' : `${80 + index * 45}ms`
    bar.style.width = bar.dataset.value ?? '0%'
  })
}

onMounted(animateBars)
watch(() => props.controller.selectedSkillId, animateBars)
</script>

<template>
  <div ref="root" class="skill-capability-stats" :class="`stats-${layout ?? 'grid'}`">
    <label>能力画像 <small>CAPABILITY</small></label>
    <div v-for="(value, stat) in profile" :key="stat">
      <span>{{ controller.catalog.statLabels[stat] ?? stat }}</span>
      <i><b :data-value="`${value}%`" :style="animate === false ? { width: `${value}%` } : undefined"></b></i>
      <strong>{{ value }}</strong>
    </div>
  </div>
</template>
