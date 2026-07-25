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
  <section class="search-console" :class="{ 'is-searching': controller.state.searching }"><div class="search-box"><span>⌕</span><input id="discovery-query" v-model="controller.state.query" placeholder="描述能力、业务目标或失败模式…" autocomplete="off" @keydown.enter="controller.runSearch"><button :disabled="controller.state.searching || !controller.state.providerIds.size" :aria-busy="controller.state.searching" @click="controller.runSearch">{{ controller.state.searching ? '真实搜索中…' : '开始联网搜索' }}<b>→</b></button></div><div class="search-console-meta"><div class="query-examples"><span>搜索示例</span><button v-for="query in examples" :key="query" @click="controller.state.query = query">{{ query }}</button></div><div class="provider-chips"><span>搜索源</span><button v-for="provider in controller.state.providers" :key="provider.id" :class="{ selected: controller.state.providerIds.has(provider.id) }" :disabled="!provider.configured || controller.state.searching" :title="provider.configured ? provider.description : `${provider.name} 未配置`" @click="controller.toggleProvider(provider.id)"><i></i>{{ provider.shortName }}</button></div></div></section>

  <section class="discovery-flow"><div class="active"><b>1</b><span><strong>搜索来源</strong><small>多 API 返回真实网页</small></span></div><i>→</i><div :class="{ active: controller.state.flowStage >= 2 }"><b>2</b><span><strong>选择材料</strong><small>核对正文与来源证据</small></span></div><i>→</i><div :class="{ active: controller.state.flowStage >= 3 }"><b>3</b><span><strong>提炼 Skill</strong><small>模型生成可编辑草稿</small></span></div><i>→</i><div :class="{ active: controller.state.flowStage >= 4 }"><b>4</b><span><strong>保存沉淀</strong><small>带快照进入隔离库</small></span></div></section>

  <section class="live-discovery-layout">
    <div class="search-evidence-column"><SearchProgressPanel :controller="controller" /><SourceTree :controller="controller" /></div>
    <div class="search-candidate-column">
      <div class="result-toolbar selection-toolbar"><div><span>READY TO DISTILL</span><h2>{{ controller.state.searching ? '正在读取来源正文…' : `${visibleResults.length} 份可提炼材料` }}</h2><p>单篇材料可直接提炼成可编辑 Skill；已有 Skill Artifact 也可以批量归档。</p></div><div class="selection-controls"><button @click="controller.selectRecommended">选择推荐项</button><button @click="controller.clearSelection">清空</button><button class="review-selection-button" :disabled="!controller.state.selectedIds.size || controller.state.searching" @click="controller.openImportReview">批量归档 {{ controller.state.selectedIds.size }}</button></div></div>
      <div class="kind-filters"><button v-for="[id, label] in kinds" :key="id" :class="{ active: controller.state.kindFilter === id }" @click="controller.state.kindFilter = id">{{ label }}</button></div>
      <div class="candidate-list realtime-candidate-list"><CandidateCard v-for="candidate in visibleResults" :key="candidate.id" :controller="controller" :candidate="candidate" /><div v-if="!visibleResults.length" class="empty-state"><span>⌕</span><h3>{{ controller.state.searching ? '真实搜索正在进行' : '还没有联网搜索结果' }}</h3><p>{{ controller.state.searching ? '来源和 Skill Artifact 会随着 API 事件逐步出现。' : '选择至少一个已配置 Provider，然后开始搜索。' }}</p></div></div>
    </div>
  </section>
  <CandidatePreviewDrawer :controller="controller" />
  <ImportReviewDialog :controller="controller" />
</template>
