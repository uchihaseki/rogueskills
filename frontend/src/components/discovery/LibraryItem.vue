<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
import type { SkillGenome } from '@/types/domain'

const props = defineProps<{ controller: DiscoveryController; genome: SkillGenome }>()
const repository = () => props.genome.repository
const status = () => repository()?.status ?? props.genome.status
const admission = () => repository()?.evaluations.find((item) => item.benchmarkId === 'library-admission-v1' && item.passed)
</script>

<template>
  <article class="library-item"><div class="library-item-main"><span class="library-icon">{{ status() === 'initial' ? 'IN' : 'SK' }}</span><div><div class="library-title"><h3>{{ genome.name }}</h3><span class="risk-badge" :class="genome.risk.level">{{ genome.risk.level }}</span><span class="repository-status" :class="status()">{{ status() }}</span></div><p>{{ genome.description }}</p><div class="library-meta"><span>{{ genome.provenance?.platform }}</span><span>{{ genome.workflow.steps.length }} workflow steps</span><span>{{ repository()?.versions.length ?? 1 }} versions</span><span>fingerprint {{ genome.provenance?.fingerprint }}</span></div></div><div class="library-score"><strong>{{ genome.evaluation.score ?? admission()?.score ?? genome.metadata.completeness }}</strong><small>{{ genome.evaluation.score != null || admission() ? '准入分' : '完整度' }}</small></div></div>
    <div class="library-gates"><span v-for="gate in genome.evaluation.requiredGates" :key="gate"><i></i>{{ gate }}</span></div><div class="library-actions"><span>状态：<b>{{ status() === 'initial' ? 'INITIAL SKILL LIBRARY' : admission() ? 'BENCHMARK PASSED · READY TO PROMOTE' : 'WAITING FOR ADMISSION BENCHMARK' }}</b></span><div>
      <button v-if="status() === 'quarantine' && controller.state.gateway === 'online'" class="benchmark-button" @click="controller.benchmark(genome.id)">运行准入 Benchmark</button>
      <button v-if="status() === 'quarantine' && admission() && repository()" class="promote-button" @click="controller.promote(genome.id, admission()!.id, repository()!.currentVersionId)">晋升 Initial Library</button>
      <button @click="controller.download(genome)">导出 JSON</button><button v-if="status() === 'quarantine'" class="remove" @click="controller.remove(genome.id)">移除</button>
    </div></div>
  </article>
</template>
