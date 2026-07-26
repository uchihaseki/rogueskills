<script setup lang="ts">
import '@/assets/run-pixel-theme.css'
import type { EvolutionController } from '@/composables/useEvolutionRun'
import ActionPanel from './ActionPanel.vue'
import BuildPanel from './BuildPanel.vue'
import CaseValidationDrawer from './CaseValidationDrawer.vue'
import MapPanel from './MapPanel.vue'
import NodeDetailDrawer from './NodeDetailDrawer.vue'
import RunHud from './RunHud.vue'
import RunLog from './RunLog.vue'

defineProps<{ controller: EvolutionController }>()
</script>

<template>
  <main class="run-shell pixel-run-theme">
    <div class="run-scanlines" aria-hidden="true"></div>
    <header class="run-nav"><RouterLink class="brand" to="/" aria-label="RogueSkills"><span class="brand-mark">R</span><span><strong>技能评估</strong><small>ROGUESKILLS</small></span></RouterLink>
      <div class="run-identity"><span>{{ controller.run!.skillName ?? controller.catalog.archetypes[controller.run!.archetypeId]?.name }}</span><i></i><span>{{ controller.catalog.runModes[controller.run!.modeId]?.name }}</span><i></i><code>{{ controller.run!.seed }}</code></div>
    </header>
    <RunHud :controller="controller" />
    <div class="game-grid"><BuildPanel :controller="controller" /><MapPanel :controller="controller" /><ActionPanel :controller="controller" /></div>
    <RunLog :controller="controller" />
    <footer class="run-footer"><span>基准评估执行器 <small>BENCHMARK RUNNER · SAVE V3</small></span><span>刷新页面可恢复当前运行</span></footer>
    <NodeDetailDrawer v-if="controller.nodeDetailNodeId" :controller="controller" />
    <CaseValidationDrawer v-if="controller.caseValidationDetailVisible" :controller="controller" />
    <div v-if="controller.completionVisible" class="completion-backdrop" @click.self="controller.closeCompletion">
      <section class="completion-dialog" role="dialog" aria-modal="true" aria-labelledby="completion-title">
        <span class="completion-kicker">自动评估已完成 <small>AUTOMATED EVALUATION · COMPLETE</small></span>
        <div class="completion-symbol" :class="controller.run!.status">{{ controller.run!.status === 'victory' ? '✦' : '×' }}</div>
        <h2 id="completion-title">{{ controller.run!.status === 'victory' ? '评估完成，候选智能体预设已保存' : '评估流程已结束' }}</h2>
        <p>{{ controller.run!.status === 'victory' ? '完整评估计划已自动执行。候选智能体预设会保留在结果面板中，可继续验证或导出。' : '当前候选配置未通过隐藏留出集评估。回放记录已保留，但不会生成无效的智能体预设。' }}</p>
        <div v-if="controller.agentPreset" class="completion-project">
          <span>项目 <small>PROJECT</small></span><strong>{{ controller.agentPreset.project.name }}</strong><small>{{ controller.agentPreset.id }}</small>
        </div>
        <button class="primary-button" @click="controller.closeCompletion">查看运行结果</button>
      </section>
    </div>
  </main>
</template>
