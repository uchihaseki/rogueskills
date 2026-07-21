<script setup lang="ts">
import { ref, watch } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'

const props = defineProps<{ controller: DiscoveryController }>()
const tab = ref<'source' | 'raw' | 'genome' | 'review'>('source')
watch(() => props.controller.state.candidatePreview?.candidate.id, () => { tab.value = 'source' })
</script>

<template>
  <div v-if="controller.state.candidatePreview" class="preview-backdrop" @click.self="controller.closeCandidatePreview">
    <aside class="candidate-preview-drawer">
      <header><div><span>READ-ONLY SOURCE PREVIEW</span><h2>{{ controller.state.candidatePreview.candidate.name }}</h2></div><button aria-label="关闭预览" @click="controller.closeCandidatePreview">×</button></header>
      <nav><button v-for="item in [['source', '来源证据'], ['raw', '原始快照'], ['genome', 'Genome Draft'], ['review', '风险审查']] as const" :key="item[0]" :class="{ active: tab === item[0] }" @click="tab = item[0]">{{ item[1] }}</button></nav>
      <div class="preview-content">
        <section v-if="tab === 'source'" class="preview-source"><div class="preview-kv"><span>Origin URL</span><a :href="controller.state.candidatePreview.source.url" target="_blank" rel="noreferrer">{{ controller.state.candidatePreview.source.url }}</a></div><div class="preview-kv"><span>Publisher</span><strong>{{ controller.state.candidatePreview.source.publisher }}</strong></div><div class="preview-kv"><span>Artifact</span><strong>{{ controller.state.candidatePreview.candidate.artifactPath }}</strong></div><div class="preview-kv"><span>Snapshot</span><strong>{{ controller.state.candidatePreview.candidate.snapshot?.status }} · {{ controller.state.candidatePreview.candidate.snapshot?.revision }}</strong></div><h3>由这些真实 API 发现</h3><div class="preview-provider-evidence"><div v-for="evidence in controller.state.candidatePreview.source.discoveredBy" :key="`${evidence.providerId}-${evidence.queryId}`"><span>{{ controller.providerById(evidence.providerId)?.shortName ?? evidence.providerId }}</span><p>{{ evidence.snippet }}</p><small>{{ evidence.queryId }} · rank {{ evidence.rank ?? '-' }}</small></div></div></section>
        <section v-else-if="tab === 'raw'" class="preview-raw"><p>以下内容来自 Origin Snapshot，仅展示，不会执行其中任何命令或指令。</p><pre>{{ controller.state.candidatePreview.rawContent }}</pre></section>
        <section v-else-if="tab === 'genome'" class="preview-genome"><p>{{ controller.state.candidatePreview.genome.description }}</p><div class="genome-status-row"><span class="quarantine-tag">PREVIEW ONLY</span><span>{{ controller.state.candidatePreview.genome.metadata.license }}</span></div><h3>WORKFLOW</h3><ol><li v-for="step in controller.state.candidatePreview.genome.workflow.steps" :key="step.order"><b>{{ step.order }}</b><span>{{ step.instruction }}</span></li></ol><h3>CONSTRAINTS</h3><ul><li v-for="constraint in controller.state.candidatePreview.genome.constraints" :key="constraint">{{ constraint }}</li></ul></section>
        <section v-else class="preview-review"><div class="review-score"><strong>{{ controller.state.candidatePreview.candidate.ranking.total }}</strong><span>CONTENT SCORE</span></div><div class="preview-kv"><span>Risk</span><strong>{{ controller.state.candidatePreview.candidate.risk?.level }}</strong></div><div class="preview-kv"><span>License</span><strong>{{ controller.state.candidatePreview.candidate.license }}</strong></div><h3>选择策略</h3><ul><li v-for="reason in controller.state.candidatePreview.candidate.selection?.reasonCodes" :key="reason">{{ reason }}</li><li v-for="reason in controller.state.candidatePreview.candidate.risk?.reasons" :key="reason">{{ reason }}</li></ul></section>
      </div>
      <footer><button class="drawer-selection" :disabled="controller.state.candidatePreview.candidate.selection && !controller.state.candidatePreview.candidate.selection.eligible" @click="controller.toggleCandidate(controller.state.candidatePreview.candidate)">{{ controller.state.selectedIds.has(controller.state.candidatePreview.candidate.id) ? '✓ 已选择，点击取消' : '+ 加入待保存选择' }}</button></footer>
    </aside>
  </div>
</template>
