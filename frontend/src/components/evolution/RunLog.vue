<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <section class="panel log-panel"><div class="log-heading"><div><span>RUN REPLAY</span><h2>进化记录</h2></div><span>{{ controller.run!.logs.length }} EVENTS</span></div><div class="log-list"><div v-for="entry in [...controller.run!.logs].reverse()" :key="entry.id" class="log-entry" :class="entry.tone"><span>{{ String(entry.id).padStart(2, '0') }}</span><i></i><p>{{ entry.message }}</p><small>ACT {{ entry.act }}</small></div></div></section>
</template>
