<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{
  controller: EvolutionController
  objectiveMode?: boolean
}>()
const emit = defineEmits<{ back: []; next: []; deploy: [] }>()
const statsRoot = ref<HTMLElement | null>(null)

const capabilityProfile = () => props.controller.selectedSkill?.capabilityProfile
  ?? props.controller.catalog.archetypes.browser?.stats
  ?? {}

const modeMeta: Record<string, { code: string; icon: string; strategy: string; risk: string }> = {
  stable: { code: 'QLT', icon: '▣', strategy: '质量优先', risk: '均衡' },
  speed: { code: 'LAT', icon: '»', strategy: '延迟优先', risk: '失败风险较高' },
  efficient: { code: 'CST', icon: '◇', strategy: '成本优先', risk: '预算严格' },
}

function meta(modeId: string) {
  return modeMeta[modeId] ?? { code: modeId.slice(0, 3).toUpperCase(), icon: '◆', strategy: '自定义策略', risk: '自定义' }
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
        ‹ {{ objectiveMode ? '返回选择基础技能' : '返回标题' }}
      </button>
      <div class="pixel-step">
        <span>{{ objectiveMode ? 'RUN CONFIGURATION' : 'STEP' }}</span>
        <strong>{{ objectiveMode ? '02 / 02' : '01 / 02' }}</strong>
      </div>
    </header>

    <section class="pixel-stage-heading morph-stage-heading">
      <div class="morph-heading-copy character-heading-copy">
        <p>选择基础技能 <small>SELECT BASE SKILL</small></p>
        <h1>选择基础技能</h1>
        <span>选择本次评估运行使用的技能配置和初始能力</span>
      </div>
      <div class="morph-heading-copy objective-heading-copy">
        <p>选择策略 · 配置评估 · 开始 <small>SELECT POLICY · CONFIGURE EVALUATION · START</small></p>
        <h1>配置评估运行</h1>
        <span>选择优化策略和运行种子，系统将生成可重放的评估计划</span>
      </div>
    </section>

    <section v-if="controller.loadingError" class="pixel-error-panel">
      <strong>后端服务不可用</strong>
      <p>无法读取初始技能库。{{ controller.loadingError }}</p>
    </section>

    <section v-else class="setup-morph-grid">
      <div class="character-roster morph-roster" aria-label="基础技能列表">
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
            <small>{{ skill.sourceId === 'awesome-finance-skills' ? 'AWESOME FINANCE' : skill.genome.metadata.category }}</small>
            <strong>{{ skill.name ?? skill.genome.name }}</strong>
            <em>LV.{{ skill.versions?.[0]?.version ?? 1 }}</em>
          </span>
          <b aria-hidden="true">▶</b>
        </button>
        <div v-if="!controller.initialSkills.length" class="pixel-loading">
          {{ controller.libraryState === 'loading' ? '正在加载技能库…' : '未找到初始技能' }}
        </div>
      </div>

      <article v-if="controller.selectedSkill" class="character-sheet morph-skill-card">
        <div class="sheet-topline">
          <span>{{ objectiveMode ? 'ACTIVE SKILL' : 'SKILL GENOME' }}</span>
          <b>{{ objectiveMode ? '已就绪' : '初始技能' }}</b>
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
          <label>基础工具 <small>BASE TOOLS</small></label>
          <div><span v-for="tool in (controller.selectedSkill.genome.tools.length ? controller.selectedSkill.genome.tools : controller.catalog.archetypes.browser?.initialWeapons ?? [])" :key="tool">{{ tool }}</span></div>
        </div>
        <div class="character-stats">
          <label>能力画像 <small>CAPABILITY</small></label>
          <div v-for="(value, stat) in capabilityProfile()" :key="stat">
            <span>{{ controller.catalog.statLabels[stat] ?? stat }}</span>
            <i><b :data-value="`${value}%`"></b></i>
            <strong>{{ value }}</strong>
          </div>
        </div>
      </article>

      <article class="mission-board morph-mission-board" :aria-hidden="!objectiveMode">
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
            <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id" :tabindex="objectiveMode ? 0 : -1">
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

        <div class="route-briefing">
          <div class="route-heading"><span>评估顺序 <small>EVALUATION SEQUENCE</small></span><strong>{{ meta(controller.selectedModeId).strategy }}</strong></div>
          <div class="route-track" :class="`route-${controller.selectedModeId}`" aria-label="Evaluation Plan 预览">
            <span class="route-origin"><i></i><small>开始 · START</small></span><b></b>
            <span class="route-node"><i></i><small>阶段 1 · STAGE 1</small></span><b></b>
            <span class="route-node elite"><i></i><small>阶段 2 · STAGE 2</small></span><b></b>
            <span class="route-boss"><i>!</i><small>留出集 · HOLDOUT</small></span>
          </div>
        </div>

        <div class="map-code-console mission-map-code">
          <label for="run-seed">运行种子 <small>RUN SEED</small></label>
          <div><span aria-hidden="true">#</span><input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32"><button type="button" aria-label="随机 Run Seed" title="随机 Run Seed" @click="controller.randomizeSeed">↻</button></div>
        </div>

        <div class="mission-deploy-actions" :class="{ 'has-saved-run': controller.savedRun }">
          <button class="deploy-button mission-ready-button" type="button" :disabled="controller.actionPending" @click="emit('deploy')">
            <span><small>准备开始 · READY TO START</small>{{ controller.actionPending ? '正在生成…' : '开始评估运行' }}</span><b>▶</b>
          </button>
          <button v-if="controller.savedRun" class="pixel-continue-button mission-continue-button" type="button" @click="controller.continueRun">
            <span><small>恢复运行 · RESUME RUN</small>载入上次评估运行</span>
            <b>阶段 {{ controller.savedRun.actIndex + 1 }}</b>
          </button>
        </div>
      </article>
    </section>

    <footer class="pixel-stage-actions morph-stage-actions">
      <span>{{ controller.selectedSkill ? `已选择 · ${controller.selectedSkill.genome.name}` : '请选择基础技能' }}</span>
      <button v-if="!objectiveMode" class="pixel-next-button" type="button" :disabled="!controller.selectedSkill" @click="emit('next')">
        下一步：定义评估目标 <b>▶</b>
      </button>
    </footer>
  </main>
</template>
