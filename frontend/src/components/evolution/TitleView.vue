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
      <p class="title-kicker">技能评估与优化 <small>ROGUESKILLS · SKILL EVALUATION & OPTIMIZATION</small></p>
      <div class="title-lockup">
        <span class="title-mark" aria-hidden="true"><b>R</b></span>
        <h1><span>技能评估</span><strong>与优化</strong></h1>
      </div>
      <p class="title-subtitle">— 测试 · 优化 · 验证 —</p>

      <nav class="title-menu" aria-label="主菜单">
        <button class="title-menu-item title-start-button" type="button" autofocus @click="start">
          <b aria-hidden="true">▶</b><span>开始评估</span>
        </button>
      </nav>
      <p class="title-key-hint"><kbd>回车</kbd><span>开始 <small>ENTER TO START</small></span></p>
    </section>

    <footer class="title-footer">
      <span>技能评估实验室 <small>SKILL EVALUATION LAB</small></span>
      <i aria-hidden="true"></i>
      <span>核心协议 <small>CORE PROTOCOL v0.1</small></span>
    </footer>
  </main>
</template>
