<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'

defineProps<{ controller: DiscoveryController }>()

const labels: Record<string, string> = {
  'run.created': '已创建搜索任务',
  'query.planned': '已生成搜索查询',
  'provider.started': '开始调用搜索 API',
  'provider.completed': '搜索 API 返回完成',
  'provider.skipped': '搜索 API 未配置',
  'provider.error': '搜索 API 调用失败',
  'provider.rate_limited': '搜索 API 达到限流',
  'source.found': '发现网页或仓库来源',
  'source.updated': '合并重复来源证据',
  'source.failed': '来源正文读取失败',
  'artifact.found': '识别出 Skill Artifact',
  'candidate.scored': '完成正文评分',
  'candidate.updated': '合并重复 Skill 证据',
  'run.review_ready': '候选已可人工复核',
  'run.failed': '本次真实搜索失败',
}
</script>

<template>
  <aside class="search-progress-panel">
    <div class="progress-heading"><span>LIVE SEARCH</span><strong>真实搜索过程</strong><small v-if="controller.state.searchRun">RUN {{ controller.state.searchRun.id.slice(-8) }}</small></div>
    <div class="provider-live-list">
      <div v-for="provider in controller.state.providers" :key="provider.id" class="provider-live-item" :class="controller.state.providerStatus.find(item => item.providerId === provider.id)?.state ?? provider.state">
        <span>{{ provider.shortName }}</span><div><strong>{{ provider.name }}</strong><small>{{ controller.state.providerStatus.find(item => item.providerId === provider.id)?.message ?? (provider.configured ? '等待搜索' : 'API KEY 未配置') }}</small></div><b>{{ controller.state.providerStatus.find(item => item.providerId === provider.id)?.count ?? 0 }}</b>
      </div>
    </div>
    <div v-if="controller.state.queries.length" class="query-plan"><span>QUERY PLAN</span><ol><li v-for="query in controller.state.queries" :key="query.id"><b>{{ query.id }}</b>{{ query.text }}</li></ol></div>
    <div class="search-event-list">
      <div v-for="event in controller.state.events.slice(-18).reverse()" :key="event.eventId" class="search-event" :class="event.type"><i></i><div><strong>{{ labels[event.type] ?? event.type }}</strong><small>{{ new Date(event.timestamp).toLocaleTimeString() }}</small></div></div>
      <div v-if="!controller.state.events.length" class="progress-empty">发起搜索后，这里会显示来自后端的真实 API 事件。</div>
    </div>
  </aside>
</template>
