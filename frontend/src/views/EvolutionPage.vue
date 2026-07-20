<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import html2canvas from 'html2canvas'
import { useEvolutionRun } from '@/composables/useEvolutionRun'
import CharacterSelectView from '@/components/evolution/CharacterSelectView.vue'
import EvolutionUtilityNav from '@/components/evolution/EvolutionUtilityNav.vue'
import RunView from '@/components/evolution/RunView.vue'
import TitlePixelTransition from '@/components/evolution/TitlePixelTransition.vue'
import TitleView from '@/components/evolution/TitleView.vue'

type SetupStage = 'title' | 'character' | 'objective'

const controller = useEvolutionRun()
const stage = ref<SetupStage>('title')
const transitionSource = ref<HTMLCanvasElement | null>(null)
const transitionDirection = ref<'fall' | 'cover'>('fall')
const transitionActive = ref(false)
const pendingStage = ref<SetupStage | null>(null)

async function captureScene(element: HTMLElement): Promise<HTMLCanvasElement> {
  await document.fonts?.ready
  const zoom = Number.parseFloat(getComputedStyle(document.body).zoom || '1') || 1
  return html2canvas(element, {
    backgroundColor: '#070b09',
    logging: false,
    scale: Math.min(2, window.devicePixelRatio) / zoom,
    useCORS: true,
    windowWidth: window.innerWidth / zoom,
    windowHeight: window.innerHeight / zoom,
  })
}

async function transitionTo(targetStage: SetupStage, sourceSelector: string) {
  if (transitionSource.value) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    stage.value = targetStage
    return
  }
  const source = document.querySelector<HTMLElement>(sourceSelector)
  if (!source) return
  try {
    transitionDirection.value = 'fall'
    pendingStage.value = targetStage
    transitionSource.value = await captureScene(source)
  } catch {
    stage.value = targetStage
    pendingStage.value = null
    transitionActive.value = false
    transitionSource.value = null
  }
}

function startCharacterStage() {
  return transitionTo('character', '.evolution-page > .title-screen')
}

function returnToTitle() {
  return transitionTo('title', '.evolution-page > .pixel-setup-shell')
}

function startPreparedTransition() {
  if (!pendingStage.value) return
  transitionActive.value = true
  stage.value = pendingStage.value
  pendingStage.value = null
}

function finishTitleTransition() {
  transitionActive.value = false
  pendingStage.value = null
  if (transitionSource.value) {
    transitionSource.value.width = 0
    transitionSource.value.height = 0
  }
  transitionSource.value = null
}

watch(() => controller.run, (run, previousRun) => {
  if (!run && previousRun) stage.value = 'character'
})

onMounted(controller.initialize)
onBeforeUnmount(controller.dispose)
</script>

<template>
  <div class="evolution-page" :class="{ 'has-active-run': controller.run }">
    <TitlePixelTransition
      v-if="transitionSource"
      :source="transitionSource"
      :direction="transitionDirection"
      :active="transitionActive"
      @ready="startPreparedTransition"
      @done="finishTitleTransition"
    />
    <EvolutionUtilityNav />
    <RunView v-if="controller.run" :controller="controller" />
    <Transition v-else name="pixel-scene" mode="out-in">
      <TitleView v-if="stage === 'title'" key="title" @start="startCharacterStage" />
      <CharacterSelectView
        v-else
        key="setup"
        :controller="controller"
        :objective-mode="stage === 'objective'"
        @back="stage === 'objective' ? stage = 'character' : returnToTitle()"
        @next="stage = 'objective'"
      />
    </Transition>
  </div>
</template>
