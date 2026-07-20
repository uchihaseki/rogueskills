<script setup lang="ts">
import { onMounted } from 'vue'
import { useDiscovery } from '@/composables/useDiscovery'
import ConvertView from '@/components/discovery/ConvertView.vue'
import DiscoveryNav from '@/components/discovery/DiscoveryNav.vue'
import FinanceBootstrapView from '@/components/discovery/FinanceBootstrapView.vue'
import LibraryView from '@/components/discovery/LibraryView.vue'
import SearchView from '@/components/discovery/SearchView.vue'

const controller = useDiscovery()
onMounted(controller.initialize)
</script>

<template>
  <main class="discovery-shell"><DiscoveryNav :controller="controller" /><div v-if="controller.state.notice" class="discovery-notice" :class="controller.state.notice.tone"><span>{{ controller.state.notice.tone === 'error' ? '!' : '✓' }}</span>{{ controller.state.notice.message }}</div>
    <SearchView v-if="controller.state.view === 'search'" :controller="controller" /><FinanceBootstrapView v-else-if="controller.state.view === 'finance'" :controller="controller" /><ConvertView v-else-if="controller.state.view === 'convert'" :controller="controller" /><LibraryView v-else :controller="controller" />
    <footer class="discovery-footer"><span>{{ controller.state.gateway === 'online' ? 'PYTHON REPOSITORY · SEARCH GATEWAY ONLINE' : 'PYTHON GATEWAY OFFLINE' }}</span><a href="/api/docs">API contract v0.2</a></footer>
  </main>
</template>
