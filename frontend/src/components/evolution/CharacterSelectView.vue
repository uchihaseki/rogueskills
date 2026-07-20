<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'

const props = defineProps<{ controller: EvolutionController }>()
const emit = defineEmits<{ back: []; next: [] }>()
const statsRoot = ref<HTMLElement | null>(null)

const capabilityProfile = () => props.controller.selectedSkill?.capabilityProfile
  ?? props.controller.catalog.archetypes.browser?.stats
  ?? {}

async function animateStats() {
  await nextTick()
  const bars = statsRoot.value?.querySelectorAll<HTMLElement>('.character-stats i b') ?? []
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  bars.forEach((bar, index) => {
    bar.style.transitionDelay = reduced ? '0ms' : `${120 + index * 80}ms`
    bar.style.width = bar.dataset.value ?? '0%'
  })
}

onMounted(animateStats)
watch(() => props.controller.selectedSkillId, animateStats)
</script>

<template>
  <main ref="statsRoot" class="pixel-setup-shell character-select-view">
    <div class="setup-scanlines" aria-hidden="true"></div>

    <header class="pixel-stage-header">
      <button class="pixel-back-button" type="button" @click="emit('back')">‹ 返回标题</button>
      <div class="pixel-step"><span>STEP</span><strong>01 / 02</strong></div>
    </header>

    <section class="pixel-stage-heading">
      <p>SELECT YOUR INITIAL SKILL</p>
      <h1>选择基础角色</h1>
      <span>每一个 Skill 都是一种不同的初始构筑</span>
    </section>

    <section v-if="controller.loadingError" class="pixel-error-panel">
      <strong>PYTHON GATEWAY OFFLINE</strong>
      <p>无法读取 Initial Skill Library。{{ controller.loadingError }}</p>
    </section>

    <section v-else class="character-layout">
      <div class="character-roster" aria-label="基础角色列表">
        <button
          v-for="(skill, index) in controller.initialSkills"
          :key="skill.id"
          class="character-slot"
          :class="{ selected: skill.id === controller.selectedSkill?.id }"
          type="button"
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

      <Transition name="character-swap" mode="out-in" @after-enter="animateStats">
        <article v-if="controller.selectedSkill" :key="controller.selectedSkill.id" class="character-sheet">
          <div class="sheet-topline"><span>CHARACTER DATA</span><b>INITIAL</b></div>
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
      </Transition>
    </section>

    <footer class="pixel-stage-actions">
      <span>{{ controller.selectedSkill ? `SELECTED · ${controller.selectedSkill.genome.name}` : 'SELECT A CHARACTER' }}</span>
      <button class="pixel-next-button" type="button" :disabled="!controller.selectedSkill" @click="emit('next')">
        下一步：定义本局目标 <b>▶</b>
      </button>
    </footer>
  </main>
</template>
