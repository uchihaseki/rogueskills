<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const controller = props.controller
const statsRoot = ref<HTMLElement | null>(null)
const capabilityProfile = () => props.controller.selectedSkill?.capabilityProfile ?? props.controller.catalog.archetypes.browser?.stats ?? {}

async function animateStats() {
  await nextTick()
  const bars = statsRoot.value?.querySelectorAll<HTMLElement>('.mini-stats i b') ?? []
  if (!bars.length) return
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduced) {
    bars.forEach((bar) => { bar.style.width = bar.dataset.value ?? '0%' })
    return
  }
  const targets = [...bars].map((bar) => ({
    bar,
    width: Number.parseFloat(bar.dataset.value ?? '0'),
  }))
  const startedAt = performance.now()
  const duration = 1150
  const stagger = 90
  function frame(now: number) {
    let active = false
    targets.forEach(({ bar, width }, index) => {
      const elapsed = now - startedAt - 150 - index * stagger
      const progress = Math.min(1, Math.max(0, elapsed / duration))
      const eased = 1 - (1 - progress) ** 3
      bar.style.width = `${width * eased}%`
      if (progress < 1) active = true
    })
    if (active) requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}

onMounted(animateStats)
watch(() => props.controller.selectedSkillId, animateStats)
</script>

<template>
  <main ref="statsRoot" class="setup-shell">
    <header class="landing-nav">
      <RouterLink class="brand" to="/" aria-label="RogueSkills 首页">
        <span class="brand-mark">R</span>
        <span><strong>技能评估</strong><small>ROGUESKILLS</small></span>
      </RouterLink>
      <div class="nav-actions">
        <div class="prototype-pill"><span></span> 核心原型 · v0.1</div>
      </div>
    </header>

    <section v-if="controller.loadingError" class="hero">
      <p class="eyebrow">服务暂不可用 <small>PYTHON GATEWAY OFFLINE</small></p>
      <h1>后端暂时不可用</h1>
      <p class="hero-copy">请启动后端服务后刷新页面。{{ controller.loadingError }}</p>
    </section>

    <template v-else>
      <section class="hero">
        <p class="eyebrow">可回放的技能评估协议 <small>A REPLAYABLE SKILL EVALUATION PROTOCOL</small></p>
        <h1>评估、优化并验证<br><em>一个可进化的技能</em></h1>
        <p class="hero-copy">使用真实业务失败模式构建评估计划，在有限的失败、算力和复杂度预算下生成候选配置，最终通过隔离的隐藏留出集评估。</p>
      </section>

      <section class="setup-grid">
        <article class="setup-card archetype-card">
          <div class="card-kicker">01 · 选择基础技能</div>
          <div class="initial-library-list">
            <button
              v-for="skill in controller.initialSkills"
              :key="skill.id"
              class="library-skill-button"
              :class="{ selected: skill.id === controller.selectedSkill?.id }"
              @click="controller.selectedSkillId = skill.id"
            >
              <span>{{ skill.genome.metadata.category }}</span>
              <strong>{{ skill.name ?? skill.genome.name }}</strong>
              <small>v{{ skill.versions?.[0]?.version ?? 1 }} · {{ skill.genome.evaluation.score ?? '—' }} score</small>
            </button>
            <div v-if="!controller.initialSkills.length" class="library-status" :class="controller.libraryState">
              {{ controller.libraryState === 'loading' ? '正在读取初始技能库…' : '后端服务离线，使用内置浏览器技能。' }}
            </div>
          </div>
          <template v-if="controller.selectedSkill">
            <div class="archetype-heading">
              <div class="role-orb"><span>{{ controller.selectedSkill.genome.metadata.category === 'finance' ? 'FI' : 'BR' }}</span></div>
              <div>
                <h2>{{ controller.selectedSkill.genome.name }}</h2>
                <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
              </div>
              <span class="selected-badge">初始技能</span>
            </div>
            <p class="card-description">{{ controller.selectedSkill.genome.description }}</p>
            <div class="loadout">
              <span class="section-label">基础工具 <small>BASE TOOLS</small></span>
              <div class="chip-row"><span v-for="tool in (controller.selectedSkill.genome.tools.length ? controller.selectedSkill.genome.tools : controller.catalog.archetypes.browser?.initialWeapons ?? [])" :key="tool" class="weapon-chip">{{ tool }}</span></div>
            </div>
            <div class="mini-stats">
              <div v-for="(value, stat) in capabilityProfile()" :key="stat">
                <span>{{ controller.catalog.statLabels[stat] }}</span><strong>{{ value }}</strong>
                <i><b :data-value="`${value}%`" style="width: 0%"></b></i>
              </div>
            </div>
          </template>
        </article>

        <article class="setup-card run-config-card">
          <div class="card-kicker">02 · 定义评估目标</div>
          <div class="mode-options">
            <label v-for="mode in controller.catalog.runModes" :key="mode.id" class="mode-option">
              <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id">
              <span class="mode-radio"></span><span class="mode-copy"><strong>{{ mode.name }}</strong><small>{{ mode.englishName }} · {{ mode.description }}</small></span>
            </label>
          </div>
          <div class="monster-target-block">
            <div class="target-heading">
              <div><span>Target Failure Modes</span><strong>选择需要重点验证的失败模式</strong></div>
              <b>已选择 {{ controller.selectedMonsterIds.length }} 项</b>
            </div>
            <div class="monster-target-list">
              <button
                v-for="monster in controller.availableMonsters"
                :key="monster.id"
                class="monster-target"
                :class="{ selected: controller.selectedMonsterIds.includes(monster.id) }"
                :aria-pressed="controller.selectedMonsterIds.includes(monster.id)"
                @click="controller.toggleMonster(monster.id)"
              >
                <span>{{ monster.regionName }}</span>
                <strong>{{ monster.name }}</strong>
                <small>{{ monster.englishName }} · {{ monster.failureMode }}</small>
              </button>
            </div>
            <p>系统会优先覆盖所选失败模式，并自动执行其余评估、候选优化和隐藏留出集评估。</p>
          </div>
          <div class="seed-block">
            <label for="run-seed">运行种子 <small>RUN SEED</small></label>
            <div class="seed-input-wrap">
              <input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32">
              <button class="icon-button" aria-label="随机生成运行种子" title="随机生成运行种子" @click="controller.randomizeSeed">↻</button>
            </div>
            <p>相同运行种子会生成相同评估计划；相同候选配置会得到相同评估结果。</p>
          </div>
          <button class="primary-button large" :disabled="controller.actionPending || !controller.selectedMonsterIds.length" @click="controller.startRun()"><span>{{ controller.actionPending ? '正在创建评估运行…' : '开始自动评估运行' }}</span><b>→</b></button>
          <p class="auto-run-note">一次启动 · 自动评估 · 自动生成候选优化项 · 通过后生成智能体预设</p>
          <button v-if="controller.savedRun" class="secondary-button continue-button" @click="controller.continueRun">
            继续上次运行 · 阶段 {{ controller.savedRun.actIndex + 1 }} · {{ controller.savedRun.seed }}
          </button>
        </article>
      </section>

      <section class="protocol-strip">
        <div><span>01</span><strong>评估计划</strong><small>EVALUATION PLAN</small></div><i></i>
        <div><span>02</span><strong>基准评估</strong><small>BENCHMARK</small></div><i></i>
        <div><span>03</span><strong>候选优化</strong><small>CANDIDATE CHANGE</small></div><i></i>
        <div><span>04</span><strong>隐藏留出集</strong><small>HIDDEN HOLDOUT</small></div>
      </section>
      <footer class="landing-footer">Skill Genome 1.0 · Python Benchmark Engine · Versioned Lineage Repository</footer>
    </template>
  </main>
</template>
