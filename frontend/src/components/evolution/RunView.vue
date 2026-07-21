<script setup lang="ts">
import '@/assets/run-pixel-theme.css'
import type { EvolutionController } from '@/composables/useEvolutionRun'
import ActionPanel from './ActionPanel.vue'
import BuildPanel from './BuildPanel.vue'
import MapPanel from './MapPanel.vue'
import RunHud from './RunHud.vue'
import RunLog from './RunLog.vue'

defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <main class="run-shell pixel-run-theme">
    <div class="run-scanlines" aria-hidden="true"></div>
    <header class="run-nav"><RouterLink class="brand" to="/" aria-label="RogueSkills"><span class="brand-mark">R</span><span><strong>RogueSkills</strong><small>EVOLUTION RUN</small></span></RouterLink>
      <div class="run-identity"><span>{{ controller.run!.skillName ?? controller.catalog.archetypes[controller.run!.archetypeId]?.name }}</span><i></i><span>{{ controller.catalog.runModes[controller.run!.modeId]?.name }}</span><i></i><code>{{ controller.run!.seed }}</code></div>
      <div class="nav-actions"><button class="nav-button" @click="controller.returnToSetup">重新选择角色</button></div>
    </header>
    <RunHud :controller="controller" />
    <div class="game-grid"><BuildPanel :controller="controller" /><MapPanel :controller="controller" /><ActionPanel :controller="controller" /></div>
    <RunLog :controller="controller" />
    <footer class="run-footer"><span>BENCHMARK RUNNER · SAVE V2</span><span>刷新页面可恢复当前 Run</span></footer>
    <div v-if="controller.completionVisible" class="completion-backdrop" @click.self="controller.closeCompletion">
      <section class="completion-dialog" role="dialog" aria-modal="true" aria-labelledby="completion-title">
        <span class="completion-kicker">AUTOMATIC EVOLUTION · COMPLETE</span>
        <div class="completion-symbol" :class="controller.run!.status">{{ controller.run!.status === 'victory' ? '✦' : '×' }}</div>
        <h2 id="completion-title">{{ controller.run!.status === 'victory' ? '自进化完成，项目产物已保存' : '自进化流程已结束' }}</h2>
        <p>{{ controller.run!.status === 'victory' ? '完整流程已经自动跑完。产物会继续保留在右侧项目框中，可随时查看或导出。' : '本次分支未通过隐藏验收，Replay 已保留，但不会生成无效项目产物。' }}</p>
        <div v-if="controller.agentPreset" class="completion-project">
          <span>PROJECT</span><strong>{{ controller.agentPreset.project.name }}</strong><small>{{ controller.agentPreset.id }}</small>
        </div>
        <button class="primary-button" @click="controller.closeCompletion">查看运行结果</button>
      </section>
    </div>
  </main>
</template>
