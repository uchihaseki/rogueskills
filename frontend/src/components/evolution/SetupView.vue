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
        <span><strong>RogueSkills</strong><small>EVOLUTION LAB</small></span>
      </RouterLink>
      <div class="nav-actions">
        <RouterLink class="discovery-link" to="/discovery">发现 Skill <b>⌕</b></RouterLink>
        <div class="prototype-pill"><span></span> Core prototype · v0.1</div>
      </div>
    </header>

    <section v-if="controller.loadingError" class="hero">
      <p class="eyebrow">PYTHON GATEWAY OFFLINE</p>
      <h1>后端暂时不可用</h1>
      <p class="hero-copy">请启动 Python FastAPI 服务后刷新页面。{{ controller.loadingError }}</p>
    </section>

    <template v-else>
      <section class="hero">
        <p class="eyebrow">A ROGUELIKE SKILL EVOLUTION PROTOCOL</p>
        <h1>把一次 Skill 优化<br><em>变成一场可重放的冒险</em></h1>
        <p class="hero-copy">穿过由真实业务失败模式组成的地图，在有限 Stability、Compute 和 Complexity 中构筑能力，最终通过隔离的隐藏验收。</p>
      </section>

      <section class="setup-grid">
        <article class="setup-card archetype-card">
          <div class="card-kicker">01 · 选择基础角色</div>
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
              {{ controller.libraryState === 'loading' ? '正在读取 Initial Skill Library…' : 'Gateway 离线，使用内置 Browser Skill。' }}
            </div>
          </div>
          <template v-if="controller.selectedSkill">
            <div class="archetype-heading">
              <div class="role-orb"><span>{{ controller.selectedSkill.genome.metadata.category === 'finance' ? 'FI' : 'BR' }}</span></div>
              <div>
                <h2>{{ controller.selectedSkill.genome.name }}</h2>
                <p>{{ controller.selectedSkill.genome.metadata.category }}</p>
              </div>
              <span class="selected-badge">INITIAL</span>
            </div>
            <p class="card-description">{{ controller.selectedSkill.genome.description }}</p>
            <div class="loadout">
              <span class="section-label">初始武器</span>
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
          <div class="card-kicker">02 · 定义自动进化目标</div>
          <div class="mode-options">
            <label v-for="mode in controller.catalog.runModes" :key="mode.id" class="mode-option">
              <input v-model="controller.selectedModeId" type="radio" name="mode" :value="mode.id">
              <span class="mode-radio"></span><span class="mode-copy"><strong>{{ mode.name }}</strong><small>{{ mode.description }}</small></span>
            </label>
          </div>
          <div class="monster-target-block">
            <div class="target-heading">
              <div><span>挑战怪物</span><strong>选择要重点攻克的失败模式</strong></div>
              <b>{{ controller.selectedMonsterIds.length }} SELECTED</b>
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
                <small>{{ monster.failureMode }}</small>
              </button>
            </div>
            <p>自动规划会优先经过所选怪物，并自动处理其余路线、Mutation 与隐藏验收。</p>
          </div>
          <div class="seed-block">
            <label for="run-seed">地图 Seed</label>
            <div class="seed-input-wrap">
              <input id="run-seed" v-model="controller.seed" spellcheck="false" maxlength="32">
              <button class="icon-button" aria-label="随机 Seed" title="随机 Seed" @click="controller.randomizeSeed">↻</button>
            </div>
            <p>相同 Seed 会生成相同地图；相同构筑也会得到相同评估。</p>
          </div>
          <button class="primary-button large" :disabled="controller.actionPending || !controller.selectedMonsterIds.length" @click="controller.startRun()"><span>{{ controller.actionPending ? '正在创建自动流程…' : '开始完整自动进化' }}</span><b>→</b></button>
          <p class="auto-run-note">一次启动 · 自动 Benchmark · 自动 Mutation · 胜利后生成项目产物</p>
          <button v-if="controller.savedRun" class="secondary-button continue-button" @click="controller.continueRun">
            继续上次 Run · 第 {{ controller.savedRun.actIndex + 1 }} 幕 · {{ controller.savedRun.seed }}
          </button>
        </article>
      </section>

      <section class="protocol-strip">
        <div><span>01</span><strong>随机地图</strong><small>受业务覆盖约束</small></div><i></i>
        <div><span>02</span><strong>失败遭遇</strong><small>怪物即失败模式</small></div><i></i>
        <div><span>03</span><strong>能力构筑</strong><small>每次升级都有代价</small></div><i></i>
        <div><span>04</span><strong>隐藏验收</strong><small>通关只获得候选资格</small></div>
      </section>
      <footer class="landing-footer">Skill Genome 1.0 · Python Benchmark Engine · Versioned Lineage Repository</footer>
    </template>
  </main>
</template>
