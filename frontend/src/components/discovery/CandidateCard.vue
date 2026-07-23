<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
import type { DiscoveryCandidate } from '@/types/domain'
import { shortDate } from '@/utils'

defineProps<{ controller: DiscoveryController; candidate: DiscoveryCandidate }>()
</script>

<template>
  <article
    class="candidate-card selection-card"
    :class="{
      selected: controller.state.selectedIds.has(candidate.id),
      blocked: candidate.selection && !candidate.selection.eligible,
    }"
  >
    <div class="candidate-source">
      <button
        class="candidate-checkbox"
        :class="{ checked: controller.state.selectedIds.has(candidate.id) }"
        :disabled="candidate.selection && !candidate.selection.eligible"
        :aria-label="controller.state.selectedIds.has(candidate.id) ? '取消选择' : '选择候选'"
        @click="controller.toggleCandidate(candidate)"
      >{{ controller.state.selectedIds.has(candidate.id) ? '✓' : '' }}</button>
      <span v-for="provider in [...new Set(candidate.discoveredBy?.map(item => item.providerId) ?? [candidate.sourceId])]" :key="provider">
        {{ controller.providerById(provider)?.shortName ?? provider.toUpperCase() }}
      </span>
      <small>{{ candidate.platform }}</small><i></i><small>{{ candidate.kind.toUpperCase() }}</small>
      <em v-if="candidate.selection?.recommended">RECOMMENDED</em>
    </div>
    <div class="candidate-main"><div class="candidate-copy"><div class="candidate-title-line"><h3>{{ candidate.name }}</h3><span class="risk-badge" :class="candidate.risk?.level ?? 'medium'">{{ candidate.risk?.level ?? 'medium' }} risk</span></div><p>{{ candidate.summary }}</p><div class="candidate-meta"><span>by {{ candidate.author }}</span><span v-if="candidate.updatedAt">更新 {{ shortDate(candidate.updatedAt) }}</span><span>License: {{ candidate.license }}</span><span v-if="candidate.artifactPath">{{ candidate.artifactPath }}</span><span v-if="candidate.signals?.stars">★ {{ candidate.signals.stars.toLocaleString() }}</span></div><div class="candidate-tags"><span v-for="tag in candidate.tags?.slice(0, 7)" :key="tag">#{{ tag }}</span></div></div><div class="candidate-score"><strong>{{ candidate.ranking.total }}</strong><small>CONTENT SCORE</small><i><b :style="{ width: `${candidate.ranking.total}%` }"></b></i></div></div>
    <div class="score-breakdown"><div><span>相关度</span><strong>{{ candidate.ranking.relevance }}</strong></div><div><span>质量</span><strong>{{ candidate.ranking.quality }}</strong></div><div><span>可信度</span><strong>{{ candidate.ranking.trust }}</strong></div><div><span>可转换性</span><strong>{{ candidate.ranking.convertibility }}</strong></div></div>
    <div class="candidate-reason" :class="{ warning: !candidate.selection?.recommended }">
      {{ candidate.selection?.reasonCodes?.join(' · ') || candidate.risk?.reasons?.[0] || '已完成来源正文扫描' }}
    </div>
    <div class="candidate-actions"><span>{{ candidate.discoveredBy?.length ?? 1 }} 条搜索证据 · 正文已抓取，可提炼为 Skill</span><div><button class="evidence-button" :disabled="controller.state.previewingId === candidate.id" @click="controller.openCandidatePreview(candidate)">查看证据</button><button class="stage-button extract-skill-button" :disabled="controller.state.draftingId === candidate.id || (candidate.selection && !candidate.selection.eligible)" @click="controller.openCandidateDraft(candidate)">{{ controller.state.draftingId === candidate.id ? '正在提炼…' : '提炼为 Skill' }} <b>→</b></button></div></div>
  </article>
</template>
