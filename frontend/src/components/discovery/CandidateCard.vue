<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
import type { DiscoveryCandidate } from '@/types/domain'
import { shortDate } from '@/utils'

defineProps<{ controller: DiscoveryController; candidate: DiscoveryCandidate }>()
</script>

<template>
  <article class="candidate-card">
    <div class="candidate-source"><span>{{ controller.connectorById(candidate.sourceId)?.shortName ?? candidate.sourceId }}</span><small>{{ candidate.platform }}</small><i></i><small>{{ candidate.kind.toUpperCase() }}</small><em v-if="candidate.signals?.official">VERIFIED ORG</em></div>
    <div class="candidate-main"><div class="candidate-copy"><div class="candidate-title-line"><h3>{{ candidate.name }}</h3><span class="risk-badge" :class="candidate.risk?.level ?? 'medium'">{{ candidate.risk?.level ?? 'medium' }} risk</span></div><p>{{ candidate.summary }}</p><div class="candidate-meta"><span>by {{ candidate.author }}</span><span>更新 {{ shortDate(candidate.updatedAt) }}</span><span>License: {{ candidate.license }}</span><span v-if="candidate.signals?.stars">★ {{ candidate.signals.stars.toLocaleString() }}</span></div><div class="candidate-tags"><span v-for="tag in candidate.tags?.slice(0, 7)" :key="tag">#{{ tag }}</span></div></div><div class="candidate-score"><strong>{{ candidate.ranking.total }}</strong><small>DISCOVERY SCORE</small><i><b :style="{ width: `${candidate.ranking.total}%` }"></b></i></div></div>
    <div class="score-breakdown"><div><span>相关度</span><strong>{{ candidate.ranking.relevance }}</strong></div><div><span>质量</span><strong>{{ candidate.ranking.quality }}</strong></div><div><span>可信度</span><strong>{{ candidate.ranking.trust }}</strong></div><div><span>可转换性</span><strong>{{ candidate.ranking.convertibility }}</strong></div></div>
    <div class="candidate-actions"><span>{{ candidate.risk?.reasons?.[0] ?? '静态扫描未发现高风险模式' }}</span><div><a v-if="candidate.url" :href="candidate.url" target="_blank" rel="noreferrer">查看来源 ↗</a><button class="stage-button" :class="{ staged: controller.candidateInLibrary(candidate) }" :disabled="controller.candidateInLibrary(candidate) || controller.state.stagingId === candidate.id" @click="controller.stageCandidate(candidate)">{{ controller.state.stagingId === candidate.id ? '拉取快照中…' : controller.candidateInLibrary(candidate) ? '已在隔离区' : '拉取并转换' }}</button></div></div>
  </article>
</template>
