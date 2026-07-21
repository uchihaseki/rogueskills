<script setup lang="ts">
import { ref } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'

defineProps<{ controller: DiscoveryController }>()
const expanded = ref(new Set<string>())
function toggle(id: string) {
  expanded.value.has(id) ? expanded.value.delete(id) : expanded.value.add(id)
  expanded.value = new Set(expanded.value)
}
</script>

<template>
  <section class="source-tree-panel">
    <div class="source-tree-heading"><span>SOURCE HITS</span><strong>{{ controller.state.sources.length }} 个真实来源</strong></div>
    <div class="source-tree-list">
      <article v-for="source in controller.state.sources" :key="source.id" class="source-tree-item" :class="source.status">
        <button @click="toggle(source.id)"><i>{{ expanded.has(source.id) ? '−' : '+' }}</i><span><strong>{{ source.title }}</strong><small>{{ source.publisher }} · {{ source.kind }}</small></span><b>{{ source.artifactIds?.length ?? 0 }}</b></button>
        <div v-if="expanded.has(source.id)" class="source-tree-detail"><p>{{ source.snippet }}</p><div class="discovered-by"><span v-for="provider in [...new Set(source.discoveredBy.map(item => item.providerId))]" :key="provider">{{ controller.providerById(provider)?.name ?? provider }}</span></div><ul><li v-for="candidate in controller.state.results.filter(item => item.sourceHitIds?.includes(source.id) ?? item.sourceHitId === source.id)" :key="candidate.id"><button @click="controller.openCandidatePreview(candidate)"><span>{{ candidate.artifactPath ?? candidate.name }}</span><b>{{ candidate.ranking.total }}</b></button></li></ul><a :href="source.url" target="_blank" rel="noreferrer">打开原始网页 ↗</a><small v-if="source.error" class="source-error">{{ source.error }}</small></div>
      </article>
      <div v-if="!controller.state.sources.length" class="source-tree-empty">尚未发现来源</div>
    </div>
  </section>
</template>
