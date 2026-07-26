<script setup lang="ts">
defineProps<{ showCharacterSelect?: boolean }>()

defineEmits<{ selectCharacter: [] }>()
</script>

<template>
  <nav class="evolution-utility-nav" aria-label="全局工具">
    <RouterLink to="/finance-demo" title="真实金融案例">
      <span aria-hidden="true">FI</span>
      <strong>真实案例</strong>
    </RouterLink>
    <button v-if="showCharacterSelect" type="button" title="重新选择基础技能" @click="$emit('selectCharacter')">
      <span aria-hidden="true">↶</span>
      <strong>选择基础技能</strong>
    </button>
    <RouterLink to="/discovery" title="发现技能">
      <span aria-hidden="true">⌕</span>
      <strong>发现技能</strong>
    </RouterLink>
  </nav>
</template>
