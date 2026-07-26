<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const emit = defineEmits<{ back: [] }>()
const controller = props.controller

const modeMeta: Record<string, { code: string; icon: string; strategy: string; risk: string }> = {
  stable: { code: 'QLT', icon: '▣', strategy: '质量优先', risk: '均衡' },
  speed: { code: 'LAT', icon: '»', strategy: '延迟优先', risk: '失败风险较高' },
  efficient: { code: 'CST', icon: '◇', strategy: '成本优先', risk: '预算严格' },
}

function meta(modeId: string) {
  return modeMeta[modeId] ?? { code: modeId.slice(0, 3).toUpperCase(), icon: '◆', strategy: '自定义策略', risk: '自定义' }
}
</script>

<template>
  <main class="pixel-setup-shell objective-view">
    <div class="setup-scanlines" aria-hidden="true"></div>

    <header class="pixel-stage-header">
      <button class="pixel-back-button" type="button" @click="emit('back')">‹ 返回选择基础技能</button>
      <div class="pixel-step"><span>运行配置 <small>RUN CONFIGURATION</small></span><strong>02 / 02</strong></div>
    </header>

    <section class="pixel-stage-heading objective-heading">
      <p>选择策略 · 配置评估 · 开始 <small>SELECT POLICY · CONFIGURE EVALUATION · START</small></p>
      <h1>配置评估运行</h1>
      <span>选择优化策略和运行种子，系统将生成可重放的评估计划</span>
    </section>

    <section class="mission-console">
      <aside v-if="controller.selectedSkill" class="party-slot">
        <div class="party-status"><i></i><span>技能已就绪 <small>SKILL READY</small></span></div>
        <span class="pixel-avatar" aria-hidden="true">{{ (controller.selectedSkill.name ?? controller.selectedSkill.genome.name).slice(0, 2).toUpperCase() }}</span>
        <small>当前技能 · ACTIVE SKILL</small>
        <strong>{{ controller.selectedSkill.genome.name }}</strong>
        <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
        <div class="party-loadout">
          <label>基础工具 <small>BASE TOOLS</small></label>
          <span v-for="tool in controller.selectedSkill.genome.tools" :key="tool">{{ tool }}</span>
        </div>
      </aside>

      <article class="mission-board">
        <div class="mission-board-heading">
          <div><span>优化策略 <small>OPTIMIZATION POLICIES</small></span><strong>选择优化策略</strong></div>
          <small>{{ Object.keys(controller.catalog.runModes).length }} POLICIES FOUND</small>
        </div>

        <div class="contract-list">
          <label
            v-for="mode in controller.catalog.runModes"
            :key="mode.id"
            class="contract-card"
            :class="[`contract-${mode.id}`, { selected: controller.selectedModeId === mode.id }]"
          >
            <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id">
            <span class="contract-icon" aria-hidden="true">{{ meta(mode.id).icon }}</span>
            <span class="contract-copy">
              <small>{{ meta(mode.id).code }} · {{ mode.englishName }}</small>
              <strong>{{ mode.name }}</strong>
              <em>{{ mode.description }}</em>
            </span>
            <span class="contract-risk">{{ meta(mode.id).risk }}</span>
            <b aria-hidden="true">▶</b>
          </label>
        </div>

        <Transition name="briefing-swap" mode="out-in">
          <div :key="controller.selectedModeId" class="route-briefing">
            <div class="route-heading">
              <span>评估顺序 <small>EVALUATION SEQUENCE</small></span>
              <strong>{{ meta(controller.selectedModeId).strategy }}</strong>
            </div>
            <div class="route-track" :class="`route-${controller.selectedModeId}`" aria-label="Evaluation Plan 预览">
              <span class="route-origin"><i></i><small>开始 · START</small></span>
              <b></b>
              <span class="route-node"><i></i><small>阶段 1 · STAGE 1</small></span>
              <b></b>
              <span class="route-node elite"><i></i><small>阶段 2 · STAGE 2</small></span>
              <b></b>
              <span class="route-boss"><i>!</i><small>留出集 · HOLDOUT</small></span>
            </div>
          </div>
        </Transition>

        <div class="deployment-strip">
          <div class="map-code-console">
            <label for="run-seed">运行种子 <small>RUN SEED</small></label>
            <div>
              <span aria-hidden="true">#</span>
              <input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32">
              <button type="button" aria-label="随机 Run Seed" title="随机 Run Seed" @click="controller.randomizeSeed">↻</button>
            </div>
          </div>
          <button class="deploy-button" type="button" :disabled="controller.actionPending" @click="controller.startRun()">
            <span><small>准备开始 · READY TO START</small>{{ controller.actionPending ? '正在生成…' : '开始评估运行' }}</span>
            <b>▶</b>
          </button>
        </div>

        <button v-if="controller.savedRun" class="pixel-continue-button" type="button" @click="controller.continueRun">
          载入上次评估运行 · 阶段 {{ controller.savedRun.actIndex + 1 }} · {{ controller.savedRun.seed }}
        </button>
      </article>
    </section>
  </main>
</template>
