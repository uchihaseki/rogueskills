<script setup lang="ts">
import { computed } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'
import CandidateCard from './CandidateCard.vue'

const props = defineProps<{ controller: DiscoveryController }>()
const visibleResults = computed(() => props.controller.visibleResults.value)
const kinds: Array<[string, string]> = [['all', '全部'], ['skill', 'Skill'], ['sop', 'SOP'], ['runbook', 'Runbook'], ['checklist', 'Checklist'], ['material', '材料']]
const examples = ['browser extraction source:github type:skill', '客服 升级 SOP type:sop', 'incident response tag:security']
</script>

<template>
  <section class="discovery-hero"><div><p>FEDERATED SKILL SEARCH</p><h1>从已有能力和行业知识中<br><em>发现下一代 Skill 的起点</em></h1><span>搜索只产生候选，不会安装或执行任何外部内容。</span></div><div class="discovery-stats"><div><strong>{{ controller.state.connectors.filter(item => item.status !== 'planned').length }}</strong><span>可用连接器</span></div><div><strong>{{ controller.state.results.length }}</strong><span>本次召回</span></div><div><strong>{{ controller.state.library.length }}</strong><span>隔离候选</span></div></div></section>
  <section class="search-console" :class="{ 'is-searching': controller.state.searching }"><div class="search-box"><span>⌕</span><input id="discovery-query" v-model="controller.state.query" placeholder="描述能力、业务目标或失败模式…" autocomplete="off" @keydown.enter="controller.runSearch"><button :disabled="controller.state.searching" :aria-busy="controller.state.searching" @click="controller.runSearch">{{ controller.state.searching ? '正在检索…' : '跨源搜索' }}<b>→</b></button></div><div class="query-examples"><span>查询语法</span><button v-for="query in examples" :key="query" @click="controller.state.query = query">{{ query }}</button></div></section>
  <section class="connector-section"><div class="section-heading"><div><span>SEARCH ROUTER</span><h2>选择数据来源</h2></div><p>官方组织预设仍通过 GitHub 公共接口检索；平台专用连接器会逐步替换。</p></div>
    <div class="connector-grid"><button v-for="connector in controller.state.connectors" :key="connector.id" class="connector-card" :class="{ selected: controller.state.sourceIds.has(connector.id), disabled: !['live', 'beta'].includes(connector.status) || connector.mode === 'upload' }" :disabled="!['live', 'beta'].includes(connector.status) || connector.mode === 'upload'" @click="controller.toggleSource(connector.id)"><span class="connector-mark">{{ connector.shortName }}</span><span class="connector-copy"><strong>{{ connector.name }}</strong><small>{{ connector.description }}</small></span><span class="connector-state" :class="connector.status">{{ connector.status === 'live' ? 'LIVE' : connector.status === 'beta' ? 'BETA' : 'NEXT' }}</span><i v-if="['live', 'beta'].includes(connector.status) && connector.mode !== 'upload'">{{ controller.state.sourceIds.has(connector.id) ? '✓' : '+' }}</i></button></div>
    <div v-if="controller.state.providerStatus.length" class="provider-status-row"><div v-for="item in controller.state.providerStatus" :key="item.sourceId" class="provider-status" :class="item.state"><span>{{ controller.connectorById(item.sourceId)?.shortName ?? item.sourceId }}</span><strong>{{ item.state === 'ok' ? `${item.count} results` : item.message ?? '暂不可用' }}</strong></div></div>
  </section>
  <section class="result-section"><div class="result-toolbar"><div><span>DISCOVERY RESULTS</span><h2>{{ controller.state.searching ? '正在聚合来源…' : `${visibleResults.length} 个候选` }}</h2></div><div class="kind-filters"><button v-for="[id, label] in kinds" :key="id" :class="{ active: controller.state.kindFilter === id }" @click="controller.state.kindFilter = id">{{ label }}</button></div></div>
    <div class="candidate-list"><CandidateCard v-for="candidate in visibleResults" :key="candidate.id" :controller="controller" :candidate="candidate" /><div v-if="!visibleResults.length" class="empty-state"><span>⌕</span><h3>{{ controller.state.searching ? '正在查询所选来源' : '没有匹配的候选' }}</h3><p>尝试减少过滤器，或者切换到 SOP 转换导入自己的材料。</p></div></div>
  </section>
</template>
