<script setup lang="ts">
import type { BenchmarkResult } from '@/types/domain'

defineProps<{ result?: BenchmarkResult | null }>()
</script>

<template>
  <div v-if="result && !result.kind" class="evaluation-result" :class="result.passed ? 'passed' : 'failed'">
    <div class="result-verdict"><span>{{ result.passed ? '通过' : '未通过' }}</span><div><small>BUSINESS COVERAGE</small><strong>{{ result.coverage }}% <i>/ {{ result.threshold }}%</i></strong></div></div>
    <div class="metric-grid"><div><small>质量</small><strong>{{ result.quality }}</strong></div><div><small>P95 延迟</small><strong>{{ result.latency }}s</strong></div><div><small>评估消耗</small><strong>{{ result.computeCost }}</strong></div><div><small>能力 / 难度</small><strong>{{ result.capability }} / {{ result.difficulty }}</strong></div></div>
    <div class="benchmark-case-list"><div v-for="item in result.cases" :key="item.label" :class="item.passed ? 'passed' : 'failed'"><span>{{ item.passed ? '✓' : '×' }}</span><strong>{{ item.label }}</strong><small>{{ item.score }}</small></div></div>
    <p v-if="!result.securityGatePassed" class="security-warning">安全硬门槛未通过：当前候选配置缺少应对恶意输入或工具权限边界的能力。</p>
  </div>
</template>
