<script setup lang="ts">
import type { DiscoveryController, DiscoveryView } from '@/composables/useDiscovery'
defineProps<{ controller: DiscoveryController }>()
const tabs: Array<[DiscoveryView, string]> = [['search', '统一搜索'], ['finance', '金融场景'], ['convert', 'SOP 转换'], ['library', 'Skill Repository']]
</script>

<template>
  <header class="discovery-nav"><RouterLink class="brand" to="/" aria-label="返回 RogueSkills"><span class="brand-mark">R</span><span><strong>RogueSkills</strong><small>DISCOVERY OBSERVATORY</small></span></RouterLink>
    <nav class="discovery-tabs" aria-label="Discovery 导航"><button v-for="[view, label] in tabs" :key="view" :class="{ active: controller.state.view === view }" @click="controller.switchView(view)">{{ label }} <span v-if="view === 'library'">{{ controller.state.library.length }}</span></button></nav>
    <div class="discovery-global-links"><RouterLink to="/finance-demo">REAL FINANCE CASE</RouterLink><RouterLink class="back-to-run" to="/">{{ controller.state.gateway === 'online' ? 'GATEWAY ONLINE' : 'GATEWAY OFFLINE' }} · Evolution Run <b>→</b></RouterLink></div>
  </header>
</template>
