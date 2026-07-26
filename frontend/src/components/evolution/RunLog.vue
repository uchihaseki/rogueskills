<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <section class="panel log-panel"><div class="log-heading"><div><span>执行日志 <small>EXECUTION LOG</small></span><h2>运行记录</h2></div><span>{{ controller.run!.logs.length }} 条事件 <small>EVENTS</small></span></div><div class="log-list"><div v-for="entry in [...controller.run!.logs].reverse()" :key="entry.id" class="log-entry" :class="entry.tone"><span>{{ String(entry.id).padStart(2, '0') }}</span><i></i><p>{{ controller.displayRunText(entry.message) }}</p><small>阶段 STAGE {{ entry.act }}</small></div></div></section>
</template>
