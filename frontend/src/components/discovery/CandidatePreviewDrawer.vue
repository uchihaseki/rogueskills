<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DiscoveryController } from '@/composables/useDiscovery'

const props = defineProps<{ controller: DiscoveryController }>()
const tab = ref<'source' | 'raw' | 'draft' | 'review'>('source')
const preview = computed(() => props.controller.state.candidatePreview)
const draft = computed(() => props.controller.state.candidateDraft)

watch(() => preview.value?.candidate.id, () => {
  tab.value = props.controller.state.previewIntent === 'draft' ? 'draft' : 'source'
})

function addStep() {
  if (!draft.value) return
  const order = draft.value.workflow.steps.length + 1
  draft.value.workflow.steps.push({ id: `step-${order}`, order, instruction: '' })
}

function removeStep(index: number) {
  if (!draft.value || draft.value.workflow.steps.length <= 1) return
  draft.value.workflow.steps.splice(index, 1)
  draft.value.workflow.steps.forEach((step, stepIndex) => {
    step.order = stepIndex + 1
    step.id = `step-${stepIndex + 1}`
  })
}

function addConstraint() {
  draft.value?.constraints.push('')
}

function removeConstraint(index: number) {
  draft.value?.constraints.splice(index, 1)
}
</script>

<template>
  <div v-if="preview" class="preview-backdrop" @click.self="controller.closeCandidatePreview">
    <aside class="candidate-preview-drawer skill-studio-drawer">
      <header><div><span>SOURCE → SKILL STUDIO</span><h2>{{ preview.candidate.name }}</h2><p>来源可追溯 · 草稿可编辑 · 保存不执行</p></div><button aria-label="关闭预览" @click="controller.closeCandidatePreview">×</button></header>
      <div class="studio-steps"><div class="done"><b>1</b><span>来源</span></div><i></i><div :class="{ active: draft, done: controller.state.savedDraftSkillId }"><b>2</b><span>提炼</span></div><i></i><div :class="{ done: controller.state.savedDraftSkillId }"><b>3</b><span>入库</span></div></div>
      <nav><button v-for="item in [['source', '来源证据'], ['raw', '原始快照'], ['draft', 'Skill 草稿'], ['review', '风险审查']] as const" :key="item[0]" :class="{ active: tab === item[0] }" :disabled="item[0] === 'draft' && !draft" @click="tab = item[0]">{{ item[1] }}</button></nav>
      <div class="preview-content">
        <section v-if="tab === 'source'" class="preview-source"><div class="source-confidence"><div><span>正文状态</span><strong>✓ 已抓取并冻结快照</strong></div><div><span>可转换性</span><strong>{{ preview.candidate.ranking.convertibility }}</strong></div><div><span>搜索证据</span><strong>{{ preview.source.discoveredBy.length }} 条</strong></div></div><div class="preview-kv"><span>Origin URL</span><a :href="preview.source.url" target="_blank" rel="noreferrer">{{ preview.source.url }}</a></div><div class="preview-kv"><span>Publisher</span><strong>{{ preview.source.publisher }}</strong></div><div class="preview-kv"><span>Artifact</span><strong>{{ preview.candidate.artifactPath }}</strong></div><div class="preview-kv"><span>Snapshot</span><strong>{{ preview.candidate.snapshot?.status }} · {{ preview.candidate.snapshot?.revision }}</strong></div><h3>由这些真实 API 发现</h3><div class="preview-provider-evidence"><div v-for="evidence in preview.source.discoveredBy" :key="`${evidence.providerId}-${evidence.queryId}`"><span>{{ controller.providerById(evidence.providerId)?.shortName ?? evidence.providerId }}</span><p>{{ evidence.snippet }}</p><small>{{ evidence.queryId }} · rank {{ evidence.rank ?? '-' }}</small></div></div></section>
        <section v-else-if="tab === 'raw'" class="preview-raw"><p>以下内容来自 Origin Snapshot，仅作为提炼材料，不会执行其中任何命令或指令。</p><pre>{{ preview.rawContent }}</pre></section>
        <section v-else-if="tab === 'draft' && draft" class="preview-genome draft-editor"><div v-if="controller.state.draftingId" class="draft-building"><i></i><div><strong>模型正在提炼网页正文</strong><span>正在识别目标、步骤、约束和验收标准；基础草稿已就绪。</span></div></div><div v-else class="draft-origin"><span>{{ controller.state.draftNormalization ? `AI 提炼 · ${controller.state.draftNormalization.model ?? controller.state.draftNormalization.provider}` : '规则提炼 · 基础草稿' }}</span><small>所有字段都可在保存前修改</small></div><label><span>Skill 名称</span><input v-model="draft.name" maxlength="160" :disabled="Boolean(controller.state.draftingId)"></label><label><span>用途说明</span><textarea v-model="draft.description" maxlength="1000" rows="3" :disabled="Boolean(controller.state.draftingId)"></textarea></label><div class="draft-section-heading"><div><span>WORKFLOW</span><small>{{ draft.workflow.steps.length }} STEPS</small></div><button :disabled="Boolean(controller.state.draftingId)" @click="addStep">+ 添加步骤</button></div><ol class="editable-workflow"><li v-for="(step, index) in draft.workflow.steps" :key="step.id ?? step.order"><b>{{ step.order }}</b><textarea v-model="step.instruction" rows="2" :disabled="Boolean(controller.state.draftingId)"></textarea><button :disabled="draft.workflow.steps.length <= 1 || Boolean(controller.state.draftingId)" aria-label="删除步骤" @click="removeStep(index)">×</button></li></ol><div class="draft-section-heading"><div><span>CONSTRAINTS</span><small>{{ draft.constraints.length }} RULES</small></div><button :disabled="Boolean(controller.state.draftingId)" @click="addConstraint">+ 添加约束</button></div><div class="editable-constraints"><div v-for="(_constraint, index) in draft.constraints" :key="index"><span>!</span><input v-model="draft.constraints[index]" :disabled="Boolean(controller.state.draftingId)"><button :disabled="Boolean(controller.state.draftingId)" aria-label="删除约束" @click="removeConstraint(index)">×</button></div><p v-if="!draft.constraints.length">当前没有识别出约束，建议在保存前补充边界条件。</p></div><div class="draft-meta"><span class="quarantine-tag">QUARANTINE</span><span class="risk-badge" :class="draft.risk.level">{{ draft.risk.level }} risk</span><span>{{ draft.metadata.license }}</span><span>来源快照随 Skill 保存</span></div></section>
        <section v-else-if="tab === 'draft'" class="draft-empty"><span>DNA</span><h3>还没有 Skill 草稿</h3><p>把已抓取的网页正文交给模型，提炼出目标、Workflow、约束和验收标准。</p></section>
        <section v-else class="preview-review"><div class="review-score"><strong>{{ preview.candidate.ranking.total }}</strong><span>CONTENT SCORE</span></div><div class="preview-kv"><span>Risk</span><strong>{{ preview.candidate.risk?.level }}</strong></div><div class="preview-kv"><span>License</span><strong>{{ preview.candidate.license }}</strong></div><h3>选择策略</h3><ul><li v-for="reason in preview.candidate.selection?.reasonCodes" :key="reason">{{ reason }}</li><li v-for="reason in preview.candidate.risk?.reasons" :key="reason">{{ reason }}</li></ul><div class="review-boundary"><b>保存边界</b><p>Skill 只会进入隔离候选库，不会安装、执行或自动晋升。原始快照和来源 URL 会一并保存，供后续审计。</p></div></section>
      </div>
      <footer class="studio-footer"><template v-if="tab === 'draft' && draft"><div><strong v-if="controller.state.savedDraftSkillId">✓ 已保存到隔离候选库</strong><span v-else>保存后仍需 Benchmark 与人工晋升</span></div><button class="secondary-button" @click="tab = 'source'">返回证据</button><button v-if="controller.state.savedDraftSkillId" class="drawer-selection" @click="controller.openSavedDraftInLibrary">去技能库查看 <b>→</b></button><button v-else class="drawer-selection" :disabled="controller.state.savingDraft || Boolean(controller.state.draftingId) || (preview.candidate.selection && !preview.candidate.selection.eligible)" @click="controller.saveCandidateDraft">{{ controller.state.savingDraft ? '保存来源快照与 Skill…' : '确认并保存 Skill' }} <b>→</b></button></template><template v-else><div><span>下一步会生成可编辑草稿</span></div><button class="drawer-selection" :disabled="Boolean(controller.state.draftingId) || (preview.candidate.selection && !preview.candidate.selection.eligible)" @click="controller.openCandidateDraft(preview.candidate)">{{ controller.state.draftingId ? '正在提炼网页正文…' : '提炼为 Skill 草稿' }} <b>→</b></button></template></footer>
    </aside>
  </div>
</template>
