<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'
import GenomePreview from './GenomePreview.vue'

const props = defineProps<{ controller: DiscoveryController }>()
const controller = props.controller

function onFileChange(event: Event) {
  return controller.upload((event.target as HTMLInputElement).files?.[0])
}
</script>

<template>
  <section class="subpage-heading"><div><p>SOP → SKILL GENOME</p><h1>把领域知识变成可评估的能力候选</h1><span>模型负责语义归一化，Python 负责结构校验、安全门禁和 Genome 构建。</span></div><div class="pipeline-mini"><span>原始材料</span><i>→</i><span>LLM 归一化</span><i>→</i><span>Contract 校验</span><i>→</i><span>安全扫描</span></div></section>
  <section class="converter-grid"><article class="material-editor"><div class="section-heading compact"><div><span>SOURCE MATERIAL</span><h2>输入 SOP 或操作材料</h2></div></div>
    <label class="field-label" for="material-title">候选名称</label><input id="material-title" v-model="controller.state.uploadedName" class="text-field" placeholder="例如：客户退款审核 SOP">
    <div class="field-row"><div><label class="field-label" for="material-source">来源说明</label><input id="material-source" v-model="controller.state.sourceLabel" class="text-field" placeholder="内部知识库 / URL / 团队"></div><div><label class="field-label" for="material-license">许可证</label><select id="material-license" v-model="controller.state.license" class="text-field"><option value="unknown">未知</option><option value="internal">内部授权</option><option value="MIT">MIT</option><option value="Apache-2.0">Apache-2.0</option><option value="CC-BY-4.0">CC-BY-4.0</option></select></div></div>
    <label class="field-label" for="material-content">Markdown / 纯文本</label><textarea id="material-content" v-model="controller.state.uploadedText" placeholder="# 目标&#10;&#10;描述这个流程解决的问题。&#10;&#10;## 步骤&#10;1. …&#10;2. …&#10;&#10;## 约束&#10;- 必须…&#10;- 不得…"></textarea>
    <div class="editor-actions"><label class="file-button"><input type="file" accept=".md,.txt,text/markdown,text/plain" @change="onFileChange">上传 .md / .txt</label><span>{{ controller.state.uploadedText.length.toLocaleString() }} chars · {{ controller.state.normalizer?.model || '未配置' }}</span><button class="convert-button" :disabled="!controller.state.normalizer?.configured || controller.state.normalizing" @click="controller.convert">{{ controller.state.normalizing ? '模型归一化中…' : '发送给模型并转换' }} <b>→</b></button></div>
    <div class="conversion-boundary" :class="{ 'not-configured': !controller.state.normalizer?.configured }"><span>{{ controller.state.normalizer?.configured ? '模型边界' : '需要配置' }}</span><p>{{ controller.state.normalizer?.configured ? `点击转换会把原始材料发送给后端配置的模型「${controller.state.normalizer.model}」。模型没有工具权限；返回结果还会经过 Pydantic Contract、静态安全和许可证检查。` : '后端尚未配置 LLM Normalizer，请设置 ROGUESKILLS_LLM_BASE_URL 和 ROGUESKILLS_LLM_MODEL 后重启服务。' }}</p></div>
  </article><article class="genome-panel"><GenomePreview :controller="controller" /></article></section>
</template>
