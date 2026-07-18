<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
import LibraryItem from './LibraryItem.vue'
defineProps<{ controller: DiscoveryController }>()
</script>

<template>
  <section class="subpage-heading library-heading"><div><p>VERSIONED SKILL REPOSITORY</p><h1>Skill Repository</h1><span>候选、版本、来源快照与准入评估已经持久化；只有 Initial Skill 可以进入 Evolution Run。</span></div><div class="library-overview"><div><strong>{{ controller.state.library.length }}</strong><span>全部 Skill</span></div><div><strong>{{ controller.state.library.filter(item => (item.repository?.status ?? item.status) === 'initial').length }}</strong><span>Initial Library</span></div><div><strong>{{ controller.state.library.filter(item => item.risk.level === 'high').length }}</strong><span>高风险</span></div></div></section>
  <section class="library-layout"><aside class="gate-explainer"><span>RELEASE GATES</span><h2>候选进入初始库前</h2><ol><li><b>01</b><div><strong>Static Safety</strong><small>注入、Secret 与危险脚本扫描</small></div></li><li><b>02</b><div><strong>License Review</strong><small>确认允许保存、改写与分发</small></div></li><li><b>03</b><div><strong>Benchmark</strong><small>公开、Validation 与 Hidden Test</small></div></li><li><b>04</b><div><strong>Human Review</strong><small>确认业务边界和评估结论</small></div></li></ol><p>隔离区内容永远不会被自动执行或部署。</p></aside>
    <div class="library-list"><LibraryItem v-for="genome in controller.state.library" :key="genome.id" :controller="controller" :genome="genome" /><div v-if="!controller.state.library.length" class="empty-state library-empty"><span>0</span><h3>Repository 还是空的</h3><p>从统一搜索拉取已有 Skill，或把自己的 SOP 转换成候选。</p><button @click="controller.switchView('search')">开始发现 Skill →</button></div></div>
  </section>
</template>
