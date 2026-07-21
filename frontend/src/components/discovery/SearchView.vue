<script setup lang="ts">
import { computed } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'
import CandidateCard from './CandidateCard.vue'
import CandidatePreviewDrawer from './CandidatePreviewDrawer.vue'
import ImportReviewDialog from './ImportReviewDialog.vue'
import SearchProgressPanel from './SearchProgressPanel.vue'
import SourceTree from './SourceTree.vue'

const props = defineProps<{ controller: DiscoveryController }>()
const visibleResults = computed(() => props.controller.visibleResults.value)
const kinds: Array<[string, string]> = [['all', '全部'], ['skill', 'Skill'], ['sop', 'SOP'], ['runbook', 'Runbook'], ['checklist', 'Checklist'], ['material', '材料']]
const examples = ['browser extraction with schema validation', '上市公司基本面分析，带引用和风险检查', 'incident response agent skill']
</script>

<template>
  <section class="discovery-hero"><div><p>REAL-TIME MULTI-PROVIDER SEARCH</p><h1>真实搜索互联网<br><em>找到可验证的 Skill 来源</em></h1><span>GitHub、Brave、Tavily、Exa 返回的来源会被抓取、展开和扫描；任何内容都不会自动执行。</span></div><div class="discovery-stats"><div><strong>{{ controller.state.providers.filter(item => item.configured).length }}</strong><span>已配置 API</span></div><div><strong>{{ controller.state.searchRun?.counts.sourceHits ?? controller.state.sources.length }}</strong><span>真实来源</span></div><div><strong>{{ controller.state.selectedIds.size }}</strong><span>待保存</span></div></div></section>
  <section class="search-console"><div class="search-box"><span>⌕</span><input id="discovery-query" v-model="controller.state.query" placeholder="描述能力、业务目标或失败模式…" autocomplete="off" @keydown.enter="controller.runSearch"><button :disabled="controller.state.searching || !controller.state.providerIds.size" @click="controller.runSearch">{{ controller.state.searching ? '真实搜索中…' : '开始联网搜索' }}<b>→</b></button></div><div class="query-examples"><span>搜索示例</span><button v-for="query in examples" :key="query" @click="controller.state.query = query">{{ query }}</button></div></section>

  <section class="connector-section"><div class="section-heading"><div><span>REAL API PROVIDERS</span><h2>选择真实搜索 API</h2></div><p>未配置的 Provider 会如实显示并禁止选择；系统不会用本地种子伪装远程搜索成功。</p></div>
    <div class="connector-grid provider-grid"><button v-for="provider in controller.state.providers" :key="provider.id" class="connector-card provider-card" :class="{ selected: controller.state.providerIds.has(provider.id), disabled: !provider.configured }" :disabled="!provider.configured || controller.state.searching" @click="controller.toggleProvider(provider.id)"><span class="connector-mark">{{ provider.shortName }}</span><span class="connector-copy"><strong>{{ provider.name }}</strong><small>{{ provider.description }}</small></span><span class="connector-state" :class="provider.configured ? 'live' : 'planned'">{{ provider.configured ? 'API READY' : 'NOT CONFIGURED' }}</span><i v-if="provider.configured">{{ controller.state.providerIds.has(provider.id) ? '✓' : '+' }}</i></button></div>
  </section>

  <section class="live-discovery-layout">
    <div class="search-evidence-column"><SearchProgressPanel :controller="controller" /><SourceTree :controller="controller" /></div>
    <div class="search-candidate-column">
      <div class="result-toolbar selection-toolbar"><div><span>VERIFIED CANDIDATES</span><h2>{{ controller.state.searching ? '正在读取来源正文…' : `${visibleResults.length} 个候选` }}</h2></div><div class="selection-controls"><button @click="controller.selectRecommended">全选推荐</button><button @click="controller.clearSelection">清空</button><button class="review-selection-button" :disabled="!controller.state.selectedIds.size || controller.state.searching" @click="controller.openImportReview">复核并保存 {{ controller.state.selectedIds.size }}</button></div></div>
      <div class="kind-filters"><button v-for="[id, label] in kinds" :key="id" :class="{ active: controller.state.kindFilter === id }" @click="controller.state.kindFilter = id">{{ label }}</button></div>
      <div class="candidate-list realtime-candidate-list"><CandidateCard v-for="candidate in visibleResults" :key="candidate.id" :controller="controller" :candidate="candidate" /><div v-if="!visibleResults.length" class="empty-state"><span>⌕</span><h3>{{ controller.state.searching ? '真实搜索正在进行' : '还没有联网搜索结果' }}</h3><p>{{ controller.state.searching ? '来源和 Skill Artifact 会随着 API 事件逐步出现。' : '选择至少一个已配置 Provider，然后开始搜索。' }}</p></div></div>
    </div>
  </section>
  <CandidatePreviewDrawer :controller="controller" />
  <ImportReviewDialog :controller="controller" />
</template>
