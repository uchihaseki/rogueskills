<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{
  controller: EvolutionController
  objectiveMode?: boolean
}>()
const emit = defineEmits<{ back: []; next: [] }>()
const statsRoot = ref<HTMLElement | null>(null)

const capabilityProfile = () => props.controller.selectedSkill?.capabilityProfile
  ?? props.controller.catalog.archetypes.browser?.stats
  ?? {}

const modeMeta: Record<string, { code: string; icon: string; strategy: string; risk: string }> = {
  stable: { code: 'STB', icon: '▣', strategy: 'DEFENSE PROTOCOL', risk: 'LOW RISK' },
  speed: { code: 'SPD', icon: '»', strategy: 'RUSH PROTOCOL', risk: 'HIGH RISK' },
  efficient: { code: 'ECO', icon: '◇', strategy: 'RESOURCE PROTOCOL', risk: 'MID RISK' },
}

function meta(modeId: string) {
  return modeMeta[modeId] ?? { code: modeId.slice(0, 3).toUpperCase(), icon: '◆', strategy: 'CUSTOM PROTOCOL', risk: 'UNKNOWN' }
}

async function animateStats() {
  await nextTick()
  const bars = statsRoot.value?.querySelectorAll<HTMLElement>('.character-stats i b') ?? []
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  bars.forEach((bar, index) => {
    bar.style.transitionDelay = reduced ? '0ms' : `${80 + index * 45}ms`
    bar.style.width = bar.dataset.value ?? '0%'
  })
}

onMounted(animateStats)
watch(() => props.controller.selectedSkillId, animateStats)
watch(() => props.objectiveMode, animateStats)
</script>

<template>
  <main
    ref="statsRoot"
    class="pixel-setup-shell character-select-view setup-morph-view"
    :class="{ 'is-objective': objectiveMode }"
  >
    <div class="setup-scanlines" aria-hidden="true"></div>

    <header class="pixel-stage-header">
      <button class="pixel-back-button" type="button" @click="emit('back')">
        ‹ {{ objectiveMode ? '返回选择角色' : '返回标题' }}
      </button>
      <div class="pixel-step">
        <span>{{ objectiveMode ? 'MISSION BRIEFING' : 'STEP' }}</span>
        <strong>{{ objectiveMode ? '02 / 02' : '01 / 02' }}</strong>
      </div>
    </header>

    <section class="pixel-stage-heading morph-stage-heading">
      <div class="morph-heading-copy character-heading-copy">
        <p>SELECT YOUR INITIAL SKILL</p>
        <h1>选择基础角色</h1>
        <span>每一个 Skill 都是一种不同的初始构筑</span>
      </div>
      <div class="morph-heading-copy objective-heading-copy">
        <p>SELECT CONTRACT · CONFIGURE ROUTE · DEPLOY</p>
        <h1>任务部署</h1>
        <span>选择本局进化协议，系统将根据地图代码生成真实路线</span>
      </div>
    </section>

    <section v-if="controller.loadingError" class="pixel-error-panel">
      <strong>PYTHON GATEWAY OFFLINE</strong>
      <p>无法读取 Initial Skill Library。{{ controller.loadingError }}</p>
    </section>

    <section v-else class="setup-morph-grid">
      <div class="character-roster morph-roster" aria-label="基础角色列表">
        <button
          v-for="(skill, index) in controller.initialSkills"
          :key="skill.id"
          class="character-slot"
          :class="{ selected: skill.id === controller.selectedSkill?.id }"
          type="button"
          :tabindex="objectiveMode ? -1 : 0"
          @click="controller.selectedSkillId = skill.id"
        >
          <span class="slot-number">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="pixel-avatar" aria-hidden="true">{{ (skill.name ?? skill.genome.name).slice(0, 2).toUpperCase() }}</span>
          <span class="slot-copy">
            <small>{{ skill.genome.metadata.category }}</small>
            <strong>{{ skill.name ?? skill.genome.name }}</strong>
            <em>LV.{{ skill.versions?.[0]?.version ?? 1 }}</em>
          </span>
          <b aria-hidden="true">▶</b>
        </button>
        <div v-if="!controller.initialSkills.length" class="pixel-loading">
          {{ controller.libraryState === 'loading' ? 'LOADING CHARACTER DATA...' : 'NO INITIAL SKILL FOUND' }}
        </div>
      </div>

      <article v-if="controller.selectedSkill" class="character-sheet morph-skill-card">
        <div class="sheet-topline">
          <span>{{ objectiveMode ? 'ACTIVE UNIT' : 'CHARACTER DATA' }}</span>
          <b>{{ objectiveMode ? 'READY' : 'INITIAL' }}</b>
        </div>
        <div class="character-portrait">
          <span aria-hidden="true">{{ (controller.selectedSkill.name ?? controller.selectedSkill.genome.name).slice(0, 2).toUpperCase() }}</span>
          <i></i><i></i><i></i><i></i>
        </div>
        <div class="character-identity">
          <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
          <h2>{{ controller.selectedSkill.genome.name }}</h2>
          <span>{{ controller.selectedSkill.genome.description }}</span>
        </div>
        <div class="character-loadout">
          <label>INITIAL EQUIPMENT</label>
          <div><span v-for="tool in (controller.selectedSkill.genome.tools.length ? controller.selectedSkill.genome.tools : controller.catalog.archetypes.browser?.initialWeapons ?? [])" :key="tool">{{ tool }}</span></div>
        </div>
        <div class="character-stats">
          <label>CAPABILITY</label>
          <div v-for="(value, stat) in capabilityProfile()" :key="stat">
            <span>{{ controller.catalog.statLabels[stat] ?? stat }}</span>
            <i><b :data-value="`${value}%`"></b></i>
            <strong>{{ value }}</strong>
          </div>
        </div>
      </article>

      <article class="mission-board morph-mission-board" :aria-hidden="!objectiveMode">
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
            <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id" :tabindex="objectiveMode ? 0 : -1">
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

        <div class="route-briefing">
          <div class="route-heading"><span>ROUTE SIMULATION</span><strong>{{ meta(controller.selectedModeId).strategy }}</strong></div>
          <div class="route-track" :class="`route-${controller.selectedModeId}`" aria-label="装饰性路线预览">
            <span class="route-origin"><i></i><small>START</small></span><b></b>
            <span class="route-node"><i></i><small>ACT 1</small></span><b></b>
            <span class="route-node elite"><i></i><small>ACT 2</small></span><b></b>
            <span class="route-boss"><i>!</i><small>HIDDEN</small></span>
          </div>
        </div>

        <div class="map-code-console mission-map-code">
          <label for="run-seed">MAP CODE</label>
          <div><span aria-hidden="true">#</span><input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32"><button type="button" aria-label="随机地图代码" title="随机地图代码" @click="controller.randomizeSeed">↻</button></div>
        </div>

        <div class="mission-deploy-actions" :class="{ 'has-saved-run': controller.savedRun }">
          <button class="deploy-button mission-ready-button" type="button" :disabled="controller.actionPending" @click="controller.startRun()">
            <span><small>READY TO DEPLOY</small>{{ controller.actionPending ? 'GENERATING...' : '进入 EVOLUTION RUN' }}</span><b>▶</b>
          </button>
          <button v-if="controller.savedRun" class="pixel-continue-button mission-continue-button" type="button" @click="controller.continueRun">
            <span><small>RESUME MISSION</small>载入上次任务</span>
            <b>ACT {{ controller.savedRun.actIndex + 1 }}</b>
          </button>
        </div>
      </article>
    </section>

    <footer class="pixel-stage-actions morph-stage-actions">
      <span>{{ controller.selectedSkill ? `SELECTED · ${controller.selectedSkill.genome.name}` : 'SELECT A CHARACTER' }}</span>
      <button v-if="!objectiveMode" class="pixel-next-button" type="button" :disabled="!controller.selectedSkill" @click="emit('next')">
        下一步：定义本局目标 <b>▶</b>
      </button>
    </footer>
  </main>
</template>
