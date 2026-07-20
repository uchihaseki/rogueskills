<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const emit = defineEmits<{ back: [] }>()
const controller = props.controller
</script>

<template>
  <main class="pixel-setup-shell objective-view">
    <div class="setup-scanlines" aria-hidden="true"></div>

    <header class="pixel-stage-header">
      <button class="pixel-back-button" type="button" @click="emit('back')">‹ 返回选择角色</button>
      <div class="pixel-step"><span>STEP</span><strong>02 / 02</strong></div>
    </header>

    <section class="pixel-stage-heading">
      <p>CONFIGURE YOUR EVOLUTION RUN</p>
      <h1>定义本局目标</h1>
      <span>选择胜利条件，并生成本次冒险的地图</span>
    </section>

    <section class="objective-layout">
      <aside v-if="controller.selectedSkill" class="objective-character-summary">
        <span class="pixel-avatar" aria-hidden="true">{{ (controller.selectedSkill.name ?? controller.selectedSkill.genome.name).slice(0, 2).toUpperCase() }}</span>
        <small>SELECTED CHARACTER</small>
        <strong>{{ controller.selectedSkill.genome.name }}</strong>
        <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
        <div><span v-for="tool in controller.selectedSkill.genome.tools" :key="tool">{{ tool }}</span></div>
      </aside>

      <article class="pixel-objective-panel">
        <label class="pixel-section-label">CHOOSE RUN MODE</label>
        <div class="pixel-mode-options">
          <label v-for="mode in controller.catalog.runModes" :key="mode.id" class="pixel-mode-option">
            <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id">
            <span aria-hidden="true"></span>
            <strong>{{ mode.name }}</strong>
            <small>{{ mode.description }}</small>
          </label>
        </div>

        <div class="pixel-seed-block">
          <label for="run-seed">MAP SEED</label>
          <div>
            <input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32">
            <button type="button" aria-label="随机 Seed" title="随机 Seed" @click="controller.randomizeSeed">↻</button>
          </div>
          <p>相同 Seed 会生成相同地图。</p>
        </div>

        <button class="pixel-launch-button" type="button" :disabled="controller.actionPending" @click="controller.startRun()">
          <span>{{ controller.actionPending ? 'GENERATING...' : '生成 EVOLUTION RUN' }}</span><b>▶</b>
        </button>
        <button v-if="controller.savedRun" class="pixel-continue-button" type="button" @click="controller.continueRun">
          继续上次 RUN · ACT {{ controller.savedRun.actIndex + 1 }} · {{ controller.savedRun.seed }}
        </button>
      </article>
    </section>
  </main>
</template>
