<script setup lang="ts">
defineProps<{ showCharacterSelect?: boolean }>()

defineEmits<{ selectCharacter: [] }>()
</script>

<template>
  <nav class="evolution-utility-nav" aria-label="全局工具">
    <button v-if="showCharacterSelect" type="button" title="重新选择角色" @click="$emit('selectCharacter')">
      <span aria-hidden="true">↶</span>
      <strong>重新选择角色</strong>
    </button>
    <RouterLink to="/discovery" title="发现 Skill">
      <span aria-hidden="true">⌕</span>
      <strong>发现 SKILL</strong>
    </RouterLink>
  </nav>
</template>
