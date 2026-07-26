<script setup lang="ts">
import { computed } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'
import type { Mutation } from '@/types/domain'
import EvaluationResult from './EvaluationResult.vue'
import CaseValidationCard from './CaseValidationCard.vue'
import MutationCard from './MutationCard.vue'

const props = defineProps<{ controller: EvolutionController }>()
const run = computed(() => props.controller.run!)
const node = computed(() => props.controller.selectedNode)
const monster = computed(() => props.controller.monsterById(node.value?.monsterId))
const type = computed(() => node.value ? props.controller.catalog.nodeTypes[node.value.type] : null)
const draft = computed(() => run.value.currentDraft
  .map(props.controller.mutationById)
  .filter((item): item is Mutation => Boolean(item)))
const automationStageLabels: Record<string, string> = {
  planning: '规划评估',
  encounter: '执行评估',
  mutation: '选择候选优化项',
  artifact: '生成智能体预设',
  ended: '运行已结束',
}
const automationStageLabel = computed(() => {
  const stage = run.value.automation?.stage
  return stage ? automationStageLabels[stage] ?? stage : '准备中'
})
</script>

<template>
  <aside class="panel action-panel">
    <div v-if="run.automation?.status === 'running'" class="action-content auto-run-content">
      <span class="encounter-kicker">自动评估运行 <small>AUTOMATED EVALUATION RUN</small></span>
      <div class="auto-run-orb"><i></i><span>{{ run.automation.progress }}%</span></div>
      <h2>自动评估流程运行中</h2>
      <p>{{ controller.displayRunText(run.automation.message) }}</p>
      <div class="auto-progress-track"><b :style="{ width: `${run.automation.progress}%` }"></b></div>
      <div class="auto-progress-meta">
        <div><span>已完成评估</span><strong>{{ run.automation.completedNodes }} / {{ run.automation.totalNodes }}</strong></div>
        <div><span>当前步骤</span><strong>{{ automationStageLabel }}</strong></div>
      </div>
      <div class="auto-targets">
        <span>目标失败模式</span>
        <div><small v-for="monsterId in run.automation.selectedMonsterIds" :key="monsterId">{{ controller.monsterById(monsterId)?.name }}</small></div>
      </div>
      <EvaluationResult v-if="run.lastResult && !run.lastResult.kind" :result="run.lastResult" />
      <small class="deterministic-note">评估计划、评估执行和候选优化均由后端权威状态机自动推进，页面只同步运行状态。</small>
    </div>

    <div v-else-if="run.phase === 'choose_node'" class="action-content choose-content">
      <span class="encounter-kicker">评估计划 <small>EVALUATION PLAN</small></span><div class="radar-mark"><i></i><i></i><span>{{ controller.currentLayer.length }}</span></div><h2>选择下一组评估</h2>
      <p>当前评估计划提供 {{ controller.currentLayer.length }} 个可选测试节点。压力评估覆盖更多组合失败模式，并返回更丰富的反馈。</p>
      <div class="decision-rules"><div><span>标准评估</span><strong>完整评估反馈</strong></div><div><span>压力评估</span><strong>更高难度与更丰富的反馈</strong></div><div><span>隐藏留出集</span><strong>隔离数据，不提供训练反馈</strong></div></div><p class="select-hint">← 在评估计划中选择高亮节点</p>
    </div>

    <template v-else-if="run.phase === 'encounter'">
      <div v-if="node?.type === 'rest'" class="action-content utility-content"><span class="encounter-kicker">预算恢复 <small>BUDGET RECOVERY</small></span><div class="utility-symbol">○</div><h2>恢复运行预算</h2><p>恢复当前运行的失败预算，并补充下一阶段需要的算力预算。</p><div class="utility-reward"><span>失败预算</span><strong>最多 +3</strong><span>算力预算</span><strong>+10</strong></div><button class="primary-button" @click="controller.resolveNode">恢复预算</button></div>
      <div v-else-if="node?.type === 'lab'" class="action-content utility-content lab-content"><span class="encounter-kicker">候选优化生成 <small>CANDIDATE GENERATOR</small></span><div class="utility-symbol">✦</div><h2>生成候选优化项</h2><p>跳过当前基准评估，根据技能状态和业务目标直接生成一组候选优化项。</p><div class="lab-note">不会恢复失败预算；选择仍会占用复杂度预算。</div><button class="primary-button" @click="controller.resolveNode">生成候选优化项</button></div>
      <div v-else-if="node && monster && type" class="action-content encounter-content"><span class="encounter-kicker">{{ type.name }} · 难度 {{ node.difficulty }} <small>{{ type.englishName }} · D{{ node.difficulty }}</small></span><div class="monster-emblem" :class="node.type"><span>{{ type.symbol }}</span></div><h2>{{ monster.name }}</h2><small>{{ monster.englishName }}</small><p class="failure-mode">{{ monster.failureMode }}</p><div class="business-case"><span>失败示例 <small>FAILURE MODE EXAMPLE</small></span><p>{{ monster.businessExample }}</p></div>
        <div class="requirement-list"><span>Capability Requirements</span><div v-for="(weight, stat) in monster.requirements" :key="stat"><span>{{ controller.catalog.statLabels[stat] }}</span><i><b :style="{ width: `${weight * 100}%` }"></b></i><strong>{{ Math.round(weight * 100) }}%</strong></div></div>
        <div v-if="monster.securityFloor" class="hard-gate">安全硬门槛：{{ monster.securityFloor }}</div><button class="primary-button" @click="controller.resolveNode">{{ node.type === 'boss' ? '运行隐藏留出集评估' : '运行评估' }}<b>→</b></button><small class="deterministic-note">结果由运行种子、当前候选配置和测试节点共同决定，可完整重放。</small>
      </div>
    </template>

    <div v-else-if="run.phase === 'reward'" class="reward-content"><span class="encounter-kicker">{{ run.lastResult?.kind === 'lab' ? 'CANDIDATE GENERATOR' : 'EVALUATION FEEDBACK' }}</span><EvaluationResult :result="run.lastResult" />
      <div class="reward-heading"><div><h2>选择一个候选优化项</h2><p>{{ run.lastResult?.kind === 'lab' ? '候选优化生成器根据当前目标生成了三个优化方向。' : `针对「${monster?.failureMode ?? '当前测试场景'}」生成，同时保留探索性选项。` }}</p></div><span>1 / {{ run.currentDraft.length }}</span></div>
      <div class="mutation-draft"><MutationCard v-for="mutation in draft" :key="mutation.id" :controller="controller" :mutation="mutation" /><p v-if="!draft.length" class="empty-copy">当前复杂度预算无法容纳新的候选优化项。</p></div><button class="text-button" @click="controller.skipMutation">跳过本次优化，保持当前配置 →</button>
    </div>

    <div v-else class="action-content end-content" :class="run.status === 'victory' ? 'victory' : 'defeat'"><span class="encounter-kicker">运行{{ run.status === 'victory' ? '通过' : '未通过' }} <small>RUN {{ run.status === 'victory' ? 'PASSED' : 'FAILED' }}</small></span><div class="end-symbol">{{ run.status === 'victory' ? '✦' : '×' }}</div><h2>{{ run.status === 'victory' ? (controller.agentPreset ? '候选智能体预设已生成' : '可以生成智能体预设') : '本次运行未通过评估' }}</h2><p>{{ run.status === 'victory' ? '当前候选配置已通过能力模拟并保存为候选智能体预设；它尚未经过真实工具运行时验证，也不会自动进入生产。' : '生产技能没有受到影响。评估计划、选择、结果与失败样本已经保存在本次回放记录中。' }}</p>
      <div class="run-summary"><div><span>评估通过</span><strong>{{ run.encounterHistory.filter(item => item.passed).length }} / {{ run.encounterHistory.length }}</strong></div><div><span>候选优化项</span><strong>{{ run.mutationIds.length }}</strong></div><div><span>能力组合</span><strong>{{ run.evolutionIds.length }}</strong></div><div><span>综合得分</span><strong>{{ controller.objectiveScore(run) }}</strong></div></div>
      <section v-if="run.status === 'victory'" class="preset-builder project-artifact-card">
        <template v-if="!controller.agentPreset">
          <div class="preset-heading"><span>智能体预设 <small>AGENT PRESET · V0.1</small></span><strong>把本次候选配置保存为智能体预设</strong></div>
          <label>项目名称<input v-model.trim="controller.presetProjectName" maxlength="160"></label>
          <label>业务场景<input v-model.trim="controller.presetScenario" maxlength="500"></label>
          <label>配置说明<textarea v-model.trim="controller.presetProjectDescription" maxlength="2000" rows="3"></textarea></label>
          <p v-if="controller.presetError" class="preset-error">{{ controller.presetError }}</p>
          <button class="primary-button" :disabled="controller.presetPending || !controller.presetProjectName || !controller.presetScenario || !controller.presetProjectDescription" @click="controller.saveAgentPreset">
            {{ controller.presetPending ? '正在编译配置…' : '保存智能体预设' }}
          </button>
        </template>
        <template v-else>
          <div class="preset-saved"><span>项目产物已保存 <small>PROJECT ARTIFACT · SAVED</small></span><strong>{{ controller.agentPreset.project.name }}</strong><small>{{ controller.agentPreset.id }}</small></div>
          <div class="preset-stats"><div><span>工作流</span><strong>{{ controller.agentPreset.workflow.length }}</strong></div><div><span>工具</span><strong>{{ controller.agentPreset.tools.length }}</strong></div><div><span>规则</span><strong>{{ controller.agentPreset.rules.constraints.length + controller.agentPreset.rules.retry.length + controller.agentPreset.rules.fallback.length + controller.agentPreset.rules.outputValidation.length }}</strong></div></div>
          <p class="preset-warning">候选配置 · 能力模拟 · 尚未通过运行时验证</p>
          <label>导出类型<select v-model="controller.presetExportTarget" aria-label="导出类型"><option value="codex">Codex（AGENTS.md）</option><option value="claude-code">Claude Code（CLAUDE.md）</option><option value="universal">Universal（双平台）</option></select></label>
          <button class="primary-button" @click="controller.exportAgentPreset">导出项目产物包</button>
        </template>
      </section>
      <CaseValidationCard v-if="run.status === 'victory' && controller.agentPreset" :controller="controller" />
      <button class="primary-button secondary-run-button" @click="controller.retrySeed">使用相同种子重新运行</button><button class="text-button" @click="controller.returnToSetup">返回运行设置</button>
    </div>
  </aside>
</template>
