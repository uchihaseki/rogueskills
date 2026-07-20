<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useEvolutionRun } from '@/composables/useEvolutionRun'
import CharacterSelectView from '@/components/evolution/CharacterSelectView.vue'
import EvolutionUtilityNav from '@/components/evolution/EvolutionUtilityNav.vue'
import RunView from '@/components/evolution/RunView.vue'
import TitleView from '@/components/evolution/TitleView.vue'

type SetupStage = 'title' | 'character' | 'objective'

const controller = useEvolutionRun()
const stage = ref<SetupStage>('title')

watch(() => controller.run, (run, previousRun) => {
  if (!run && previousRun) stage.value = 'character'
})

onMounted(controller.initialize)
</script>

<template>
  <div class="evolution-page" :class="{ 'has-active-run': controller.run }">
    <EvolutionUtilityNav />
    <RunView v-if="controller.run" :controller="controller" />
    <Transition v-else name="pixel-scene" mode="out-in">
      <TitleView v-if="stage === 'title'" key="title" @start="stage = 'character'" />
      <CharacterSelectView
        v-else
        key="setup"
        :controller="controller"
        :objective-mode="stage === 'objective'"
        @back="stage = stage === 'objective' ? 'character' : 'title'"
        @next="stage = 'objective'"
      />
    </Transition>
  </div>
</template>
