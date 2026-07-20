<script setup lang="ts">
import { computed } from 'vue'
import type { EvolutionController } from '@/composables/useEvolutionRun'
import type { Mutation } from '@/types/domain'
import EvaluationResult from './EvaluationResult.vue'
import MutationCard from './MutationCard.vue'

const props = defineProps<{ controller: EvolutionController }>()
const run = computed(() => props.controller.run!)
const node = computed(() => props.controller.selectedNode)
const monster = computed(() => props.controller.monsterById(node.value?.monsterId))
const type = computed(() => node.value ? props.controller.catalog.nodeTypes[node.value.type] : null)
const draft = computed(() => run.value.currentDraft
  .map(props.controller.mutationById)
  .filter((item): item is Mutation => Boolean(item)))
</script>

<template>
  <aside class="panel action-panel">
    <div v-if="run.automation?.status === 'running'" class="action-content auto-run-content">
      <span class="encounter-kicker">AUTOMATIC EVOLUTION</span>
      <div class="auto-run-orb"><i></i><span>{{ run.automation.progress }}%</span></div>
      <h2>自进化流程运行中</h2>
      <p>{{ run.automation.message }}</p>
      <div class="auto-progress-track"><b :style="{ width: `${run.automation.progress}%` }"></b></div>
      <div class="auto-progress-meta">
        <div><span>已完成节点</span><strong>{{ run.automation.completedNodes }} / {{ run.automation.totalNodes }}</strong></div>
        <div><span>当前阶段</span><strong>{{ run.automation.stage.toUpperCase() }}</strong></div>
      </div>
      <div class="auto-targets">
        <span>目标怪物</span>
        <div><small v-for="monsterId in run.automation.selectedMonsterIds" :key="monsterId">{{ controller.monsterById(monsterId)?.name }}</small></div>
      </div>
      <EvaluationResult v-if="run.lastResult && !run.lastResult.kind" :result="run.lastResult" />
      <small class="deterministic-note">路线、评估和能力选择均由后端权威状态机自动推进，页面只同步运行状态。</small>
    </div>

    <div v-else-if="run.phase === 'choose_node'" class="action-content choose-content">
      <span class="encounter-kicker">ROUTE DECISION</span><div class="radar-mark"><i></i><i></i><span>{{ controller.currentLayer.length }}</span></div><h2>选择下一条路线</h2>
      <p>地图随机生成了 {{ controller.currentLayer.length }} 个可选节点。精英风险更高，但更容易提供高价值 Mutation。</p>
      <div class="decision-rules"><div><span>公开节点</span><strong>完整评估反馈</strong></div><div><span>精英节点</span><strong>更高难度与奖励</strong></div><div><span>Hidden Boss</span><strong>隔离数据，不提供训练反馈</strong></div></div><p class="select-hint">← 在地图中选择高亮节点</p>
    </div>

    <template v-else-if="run.phase === 'encounter'">
      <div v-if="node?.type === 'rest'" class="action-content utility-content"><span class="encounter-kicker">SAFE NODE</span><div class="utility-symbol">○</div><h2>安全节点</h2><p>修复当前实验分支，并补充下一阶段需要的评估预算。</p><div class="utility-reward"><span>Stability</span><strong>最多 +3</strong><span>Compute</span><strong>+10</strong></div><button class="primary-button" @click="controller.resolveNode">执行重整</button></div>
      <div v-else-if="node?.type === 'lab'" class="action-content utility-content lab-content"><span class="encounter-kicker">EVOLUTION LAB</span><div class="utility-symbol">✦</div><h2>进化实验室</h2><p>跳过 Benchmark，直接根据当前构筑和业务目标生成一次 Mutation Draft。</p><div class="lab-note">实验室不会恢复 Stability，选择仍会占用 Complexity。</div><button class="primary-button" @click="controller.resolveNode">生成 Mutation</button></div>
      <div v-else-if="node && monster && type" class="action-content encounter-content"><span class="encounter-kicker">{{ type.name.toUpperCase() }} · D{{ node.difficulty }}</span><div class="monster-emblem" :class="node.type"><span>{{ type.symbol }}</span></div><h2>{{ monster.name }}</h2><p class="failure-mode">{{ monster.failureMode }}</p><div class="business-case"><span>业务案例</span><p>{{ monster.businessExample }}</p></div>
        <div class="requirement-list"><span>能力权重</span><div v-for="(weight, stat) in monster.requirements" :key="stat"><span>{{ controller.catalog.statLabels[stat] }}</span><i><b :style="{ width: `${weight * 100}%` }"></b></i><strong>{{ Math.round(weight * 100) }}%</strong></div></div>
        <div v-if="monster.securityFloor" class="hard-gate">安全硬门槛：{{ monster.securityFloor }}</div><button class="primary-button" @click="controller.resolveNode">{{ node.type === 'boss' ? '执行隐藏验收' : '运行 Benchmark' }}<b>→</b></button><small class="deterministic-note">结果由 Seed、当前构筑和节点共同决定，可完整重放。</small>
      </div>
    </template>

    <div v-else-if="run.phase === 'reward'" class="reward-content"><span class="encounter-kicker">{{ run.lastResult?.kind === 'lab' ? 'LAB MUTATION' : 'ENCOUNTER FEEDBACK' }}</span><EvaluationResult :result="run.lastResult" />
      <div class="reward-heading"><div><h2>选择一个 Mutation</h2><p>{{ run.lastResult?.kind === 'lab' ? '实验室根据当前目标生成了三个构筑方向。' : `针对「${monster?.failureMode ?? '当前场景'}」生成，但保留探索性选项。` }}</p></div><span>1 / {{ run.currentDraft.length }}</span></div>
      <div class="mutation-draft"><MutationCard v-for="mutation in draft" :key="mutation.id" :controller="controller" :mutation="mutation" /><p v-if="!draft.length" class="empty-copy">当前 Complexity 无法容纳新的 Mutation。</p></div><button class="text-button" @click="controller.skipMutation">放弃奖励，保持当前构筑 →</button>
    </div>

    <div v-else class="action-content end-content" :class="run.status === 'victory' ? 'victory' : 'defeat'"><span class="encounter-kicker">RUN {{ run.status === 'victory' ? 'COMPLETE' : 'TERMINATED' }}</span><div class="end-symbol">{{ run.status === 'victory' ? '✦' : '×' }}</div><h2>{{ run.status === 'victory' ? (controller.agentPreset ? '项目产物已生成' : '可以生成 AgentPreset') : '进化分支已经死亡' }}</h2><p>{{ run.status === 'victory' ? '当前构筑已通过能力数值模拟并保存为静态候选配置；它尚未经过真实 Tool Runtime 验证，也不会自动进入生产。' : '生产 Skill 没有受到影响。地图、选择、评估与失败样本已经保存在本次 Replay 中。' }}</p>
      <div class="run-summary"><div><span>遭遇通过</span><strong>{{ run.encounterHistory.filter(item => item.passed).length }} / {{ run.encounterHistory.length }}</strong></div><div><span>Mutation</span><strong>{{ run.mutationIds.length }}</strong></div><div><span>武器进化</span><strong>{{ run.evolutionIds.length }}</strong></div><div><span>最终得分</span><strong>{{ controller.objectiveScore(run) }}</strong></div></div>
      <section v-if="run.status === 'victory'" class="preset-builder project-artifact-card">
        <template v-if="!controller.agentPreset">
          <div class="preset-heading"><span>AGENT PRESET · V0.1</span><strong>把本局构筑保存为场景配置</strong></div>
          <label>Project 名称<input v-model.trim="controller.presetProjectName" maxlength="160"></label>
          <label>业务场景<input v-model.trim="controller.presetScenario" maxlength="500"></label>
          <label>配置说明<textarea v-model.trim="controller.presetProjectDescription" maxlength="2000" rows="3"></textarea></label>
          <p v-if="controller.presetError" class="preset-error">{{ controller.presetError }}</p>
          <button class="primary-button" :disabled="controller.presetPending || !controller.presetProjectName || !controller.presetScenario || !controller.presetProjectDescription" @click="controller.saveAgentPreset">
            {{ controller.presetPending ? '正在编译配置…' : '保存 AgentPreset' }}
          </button>
        </template>
        <template v-else>
          <div class="preset-saved"><span>PROJECT ARTIFACT · SAVED</span><strong>{{ controller.agentPreset.project.name }}</strong><small>{{ controller.agentPreset.id }}</small></div>
          <div class="preset-stats"><div><span>Workflow</span><strong>{{ controller.agentPreset.workflow.length }}</strong></div><div><span>Tools</span><strong>{{ controller.agentPreset.tools.length }}</strong></div><div><span>Rules</span><strong>{{ controller.agentPreset.rules.constraints.length + controller.agentPreset.rules.retry.length + controller.agentPreset.rules.fallback.length + controller.agentPreset.rules.outputValidation.length }}</strong></div></div>
          <p class="preset-warning">Candidate · capability simulation · runtimeVerified=false</p>
          <button class="primary-button" @click="controller.exportAgentPreset">导出项目产物 JSON</button>
        </template>
      </section>
      <button class="primary-button secondary-run-button" @click="controller.retrySeed">使用相同 Seed 重新构筑</button><button class="text-button" @click="controller.returnToSetup">返回 Run 设置</button>
    </div>
  </aside>
</template>
