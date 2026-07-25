<script setup lang="ts">
import type { DiscoveryController } from '@/composables/useDiscovery'

defineProps<{ controller: DiscoveryController }>()
</script>

<template>
  <section class="subpage-heading finance-heading">
    <div><p>FINANCE SKILL BOOTSTRAP</p><h1>自动构建金融股票分析 Skill 库</h1><span>从 GitHub 社区召回高质量材料，经过许可证、社区信号、金融相关度和内容安全筛选；金融 SOP 使用 Qwen 归一化后进入同一准入流程。</span></div>
    <div class="finance-model"><span>LLM NORMALIZER</span><strong>{{ controller.state.normalizer?.model || '未配置' }}</strong><small>{{ controller.state.normalizer?.configured ? 'JSON Schema · temperature 0 · no tools' : '请配置后端模型' }}</small></div>
  </section>

  <section class="finance-pipeline">
    <div><b>01</b><strong>社区检索</strong><span>GitHub 股票、财报、估值工作流</span></div><i>→</i>
    <div><b>02</b><strong>自动筛选</strong><span>Stars、License、相关度、风险</span></div><i>→</i>
    <div><b>03</b><strong>Qwen 标准化</strong><span>社区材料与内置金融 SOP</span></div><i>→</i>
    <div><b>04</b><strong>准入入库</strong><span>Schema、Benchmark、Initial Library</span></div>
  </section>

  <section class="finance-launch" :class="{ 'is-running': controller.state.financeRunning }">
    <div><span>FINANCIAL STOCK ANALYSIS</span><h2>一键初始化场景武器库</h2><p>默认选取最多 2 个社区候选，并转换“基本面与估值分析”“财报与业绩电话会复盘”两份 SOP。该操作会调用 GitHub 和后端配置的 Qwen 模型；点击按钮同时表示允许所有通过 License、安全和 Admission 硬门槛的结果批量进入 Initial Library。</p></div>
    <button :disabled="controller.state.financeRunning || !controller.state.normalizer?.configured" :aria-busy="controller.state.financeRunning" @click="controller.runFinanceBootstrap">
      {{ controller.state.financeRunning ? '正在检索、筛选和归一化…' : '开始自动构建' }} <b>→</b>
    </button>
  </section>

  <template v-if="controller.state.financeResult">
    <section class="finance-summary">
      <div><strong>{{ controller.state.financeResult.summary.discovered }}</strong><span>社区召回</span></div>
      <div><strong>{{ controller.state.financeResult.summary.hydrated }}</strong><span>内容拉取</span></div>
      <div><strong>{{ controller.state.financeResult.summary.communityStored }}</strong><span>社区入库</span></div>
      <div><strong>{{ controller.state.financeResult.summary.sopsProcessed }}</strong><span>SOP 转换</span></div>
      <div class="success"><strong>{{ controller.state.financeResult.summary.initialSkills }}</strong><span>Initial Skills</span></div>
      <div><strong>{{ controller.state.financeResult.summary.rejected }}</strong><span>自动过滤</span></div>
    </section>

    <section class="finance-results-grid">
      <article class="finance-result-panel"><div class="section-heading compact"><div><span>COMMUNITY SKILLS</span><h2>社区候选</h2></div></div>
        <div v-if="controller.state.financeResult.community.length" class="finance-result-list"><div v-for="item in controller.state.financeResult.community" :key="item.skillId" class="finance-result-item"><span>GH</span><div><strong>{{ item.name || item.candidate?.name }}</strong><small>★ {{ item.candidate?.stars || 0 }} · {{ item.candidate?.license }} · Finance {{ item.candidate?.financeRanking?.score }}</small></div><b :class="item.status">{{ item.status }}</b></div></div>
        <div v-else class="finance-empty">本次没有社区候选通过完整筛选；SOP 流程仍会继续。</div>
      </article>
      <article class="finance-result-panel"><div class="section-heading compact"><div><span>NORMALIZED SOPS</span><h2>金融 SOP</h2></div></div>
        <div class="finance-result-list"><div v-for="item in controller.state.financeResult.sops" :key="item.sopId" class="finance-result-item"><span>SOP</span><div><strong>{{ item.title }}</strong><small>{{ item.normalization?.model || controller.state.financeResult.model.model }} · Admission {{ item.evaluation?.score ?? '—' }}</small></div><b :class="item.status">{{ item.status }}</b></div></div>
      </article>
    </section>

    <section v-if="controller.state.financeResult.rejected.length" class="finance-rejected"><div class="section-heading compact"><div><span>FILTER EVIDENCE</span><h2>被自动过滤的候选</h2></div></div><div><p v-for="item in controller.state.financeResult.rejected.slice(0, 8)" :key="`${item.stage}-${item.candidateId}`"><strong>{{ item.name || item.candidateId }}</strong><span>{{ item.reasons.join(' · ') }}</span></p></div></section>
  </template>
</template>
