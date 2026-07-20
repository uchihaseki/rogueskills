<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const emit = defineEmits<{ back: [] }>()
const controller = props.controller

const modeMeta: Record<string, { code: string; icon: string; strategy: string; risk: string }> = {
  stable: { code: 'STB', icon: '▣', strategy: 'DEFENSE PROTOCOL', risk: 'LOW RISK' },
  speed: { code: 'SPD', icon: '»', strategy: 'RUSH PROTOCOL', risk: 'HIGH RISK' },
  efficient: { code: 'ECO', icon: '◇', strategy: 'RESOURCE PROTOCOL', risk: 'MID RISK' },
}

function meta(modeId: string) {
  return modeMeta[modeId] ?? { code: modeId.slice(0, 3).toUpperCase(), icon: '◆', strategy: 'CUSTOM PROTOCOL', risk: 'UNKNOWN' }
}
</script>

<template>
  <main class="pixel-setup-shell objective-view">
    <div class="setup-scanlines" aria-hidden="true"></div>

    <header class="pixel-stage-header">
      <button class="pixel-back-button" type="button" @click="emit('back')">‹ 返回选择角色</button>
      <div class="pixel-step"><span>MISSION BRIEFING</span><strong>02 / 02</strong></div>
    </header>

    <section class="pixel-stage-heading objective-heading">
      <p>SELECT CONTRACT · CONFIGURE ROUTE · DEPLOY</p>
      <h1>任务部署</h1>
      <span>选择本局进化协议，系统将根据地图代码生成真实路线</span>
    </section>

    <section class="mission-console">
      <aside v-if="controller.selectedSkill" class="party-slot">
        <div class="party-status"><i></i><span>UNIT READY</span></div>
        <span class="pixel-avatar" aria-hidden="true">{{ (controller.selectedSkill.name ?? controller.selectedSkill.genome.name).slice(0, 2).toUpperCase() }}</span>
        <small>ACTIVE UNIT</small>
        <strong>{{ controller.selectedSkill.genome.name }}</strong>
        <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
        <div class="party-loadout">
          <label>LOADOUT</label>
          <span v-for="tool in controller.selectedSkill.genome.tools" :key="tool">{{ tool }}</span>
        </div>
      </aside>

      <article class="mission-board">
        <div class="mission-board-heading">
          <div><span>CONTRACT DATABASE</span><strong>选择进化协议</strong></div>
          <small>{{ Object.keys(controller.catalog.runModes).length }} CONTRACTS FOUND</small>
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
              <small>{{ meta(mode.id).code }} · {{ meta(mode.id).strategy }}</small>
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
              <span>ROUTE SIMULATION</span>
              <strong>{{ meta(controller.selectedModeId).strategy }}</strong>
            </div>
            <div class="route-track" :class="`route-${controller.selectedModeId}`" aria-label="装饰性路线预览">
              <span class="route-origin"><i></i><small>START</small></span>
              <b></b>
              <span class="route-node"><i></i><small>ACT 1</small></span>
              <b></b>
              <span class="route-node elite"><i></i><small>ACT 2</small></span>
              <b></b>
              <span class="route-boss"><i>!</i><small>HIDDEN</small></span>
            </div>
          </div>
        </Transition>

        <div class="deployment-strip">
          <div class="map-code-console">
            <label for="run-seed">MAP CODE</label>
            <div>
              <span aria-hidden="true">#</span>
              <input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32">
              <button type="button" aria-label="随机地图代码" title="随机地图代码" @click="controller.randomizeSeed">↻</button>
            </div>
          </div>
          <button class="deploy-button" type="button" :disabled="controller.actionPending" @click="controller.startRun()">
            <span><small>READY TO DEPLOY</small>{{ controller.actionPending ? 'GENERATING...' : '进入 EVOLUTION RUN' }}</span>
            <b>▶</b>
          </button>
        </div>

        <button v-if="controller.savedRun" class="pixel-continue-button" type="button" @click="controller.continueRun">
          载入上次任务 · ACT {{ controller.savedRun.actIndex + 1 }} · {{ controller.savedRun.seed }}
        </button>
      </article>
    </section>
  </main>
</template>
