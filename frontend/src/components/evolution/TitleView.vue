<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

const emit = defineEmits<{ start: [] }>()
let started = false

function start() {
  if (started) return
  started = true
  emit('start')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.repeat) return
  if (event.target instanceof HTMLElement && event.target.closest('a[href]')) return
  event.preventDefault()
  start()
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <main class="title-screen">
    <div class="title-pixel-sky" aria-hidden="true"></div>
    <div class="title-scanlines" aria-hidden="true"></div>
    <div class="title-horizon" aria-hidden="true">
      <i></i><i></i><i></i><i></i><i></i>
    </div>

    <section class="title-content">
      <p class="title-kicker">A ROGUELIKE SKILL EVOLUTION PROTOCOL</p>
      <div class="title-lockup">
        <span class="title-mark" aria-hidden="true"><b>R</b></span>
        <h1><span>ROGUE</span><strong>SKILLS</strong></h1>
      </div>
      <p class="title-subtitle">— EVOLVE · SURVIVE · ASCEND —</p>

      <nav class="title-menu" aria-label="主菜单">
        <button class="title-menu-item title-start-button" type="button" autofocus @click="start">
          <b aria-hidden="true">▶</b><span>START GAME</span>
        </button>
      </nav>
      <p class="title-key-hint"><kbd>ENTER</kbd><span>TO START</span></p>
    </section>

    <footer class="title-footer">
      <span>EVOLUTION LAB</span>
      <i aria-hidden="true"></i>
      <span>CORE PROTOCOL v0.1</span>
    </footer>
  </main>
</template>
