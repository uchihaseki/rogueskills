<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useEvolutionRun } from '@/composables/useEvolutionRun'
import RunView from '@/components/evolution/RunView.vue'
import SetupView from '@/components/evolution/SetupView.vue'

const controller = useEvolutionRun()
onMounted(controller.initialize)
onBeforeUnmount(controller.dispose)
</script>

<template>
  <RunView v-if="controller.run" :controller="controller" />
  <SetupView v-else :controller="controller" />
</template>
