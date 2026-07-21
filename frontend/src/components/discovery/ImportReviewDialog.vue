<script setup lang="ts">
import { computed } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'

const props = defineProps<{ controller: DiscoveryController }>()
const selected = computed(() => props.controller.state.results.filter((item) => props.controller.state.selectedIds.has(item.id)))
</script>

<template>
  <div v-if="controller.state.reviewOpen" class="review-backdrop" @click.self="controller.state.reviewOpen = false">
    <section class="import-review-dialog">
      <header><div><span>HUMAN CONFIRMATION</span><h2>确认保存 {{ selected.length }} 个 Skill</h2></div><button @click="controller.state.reviewOpen = false">×</button></header>
      <p>只会把以下选中项保存到 Quarantine Repository，不会安装、执行或自动晋升。</p>
      <div class="import-review-list"><article v-for="candidate in selected" :key="candidate.id"><button @click="controller.toggleCandidate(candidate)">×</button><div><strong>{{ candidate.name }}</strong><small>{{ candidate.artifactPath }} · {{ candidate.platform }}</small></div><span class="risk-badge" :class="candidate.risk?.level">{{ candidate.risk?.level }}</span><em>{{ candidate.license }}</em></article></div>
      <div v-if="selected.some(item => item.selection?.reasonCodes.includes('LICENSE_REVIEW_REQUIRED'))" class="import-warning">! 选择中包含许可证未知的候选。继续即表示同意将它保存到隔离区等待人工许可证复核。</div>
      <footer><button class="secondary-button" @click="controller.state.reviewOpen = false">返回调整</button><button class="primary-button" :disabled="controller.state.importing || !selected.length" @click="controller.confirmImport">{{ controller.state.importing ? '正在重新校验并保存…' : `确认保存 ${selected.length} 项` }}</button></footer>
    </section>
  </div>
</template>
