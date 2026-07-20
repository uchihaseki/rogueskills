<script setup lang="ts">
import type { EvolutionController } from '@/composables/useEvolutionRun'
import ActionPanel from './ActionPanel.vue'
import BuildPanel from './BuildPanel.vue'
import MapPanel from './MapPanel.vue'
import RunHud from './RunHud.vue'
import RunLog from './RunLog.vue'

defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <main class="run-shell">
    <header class="run-nav"><RouterLink class="brand" to="/" aria-label="RogueSkills"><span class="brand-mark">R</span><span><strong>RogueSkills</strong><small>EVOLUTION RUN</small></span></RouterLink>
      <div class="run-identity"><span>{{ controller.run!.skillName ?? controller.catalog.archetypes[controller.run!.archetypeId]?.name }}</span><i></i><span>{{ controller.catalog.runModes[controller.run!.modeId]?.name }}</span><i></i><code>{{ controller.run!.seed }}</code></div>
      <div class="nav-actions"><button class="nav-button" @click="controller.returnToSetup">重新选择角色</button></div>
    </header>
    <RunHud :controller="controller" />
    <div class="game-grid"><BuildPanel :controller="controller" /><MapPanel :controller="controller" /><ActionPanel :controller="controller" /></div>
    <RunLog :controller="controller" />
    <footer class="run-footer"><span>BENCHMARK RUNNER · SAVE V2</span><span>刷新页面可恢复当前 Run</span></footer>
  </main>
</template>
