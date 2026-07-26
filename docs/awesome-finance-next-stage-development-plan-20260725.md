# Awesome Finance Skills 下一阶段开发计划

> 日期：2026-07-25
> 输入：[Awesome Finance Skills 自进化 Demo 阶段性总结](./awesome-finance-stage-summary-20260725.md)
> 核心目标：把前端 Evolution Run 生成的 Candidate AgentPreset 接入真实 Finance Case Verified Replay，完成严格同源 A/B、Runtime Verification 和 Skill Version 晋升；同时补齐 Evolution Map 已执行节点的可点击详情与完整 Replay 证据。

> 完成状态（2026-07-25）：P0-1 至 P0-8 与 P1 业务讲稿均已实现并通过自动测试。当前环境的 Browser 安全策略拒绝 `localhost:5175`，因此点击级 smoke test 保留为正式 Demo 机器的人工检查；没有使用替代浏览器或 Raw CDP 绕过。

## 1. 下一阶段结论

下一阶段只聚焦一条主链路：

```text
Initial Finance Skill
  → Frontend Evolution Run
  → Candidate AgentPreset
  → Verified Replay CaseValidation
  → Base Skill Version / Candidate AgentPreset 同源 A/B
  → Candidate Evaluation
  → 严格提升判断
  → Runtime Verified Preset Binding
  → 新 Skill Version（仅 accepted 时）
```

并行补齐一项前端 Replay 可解释性能力：

```text
用户点击任意已执行地图节点
  → 展开 Node Detail Drawer
  → 查看进入节点时的构筑、业务失败模式、Benchmark、资源变化、
     Mutation Draft、最终选择、Evolution 解锁和该节点日志
```

本阶段不扩展 Live Validation、多 Primary Skill、多 Agent 路由，也不把游戏 Mutation 强行转换为 Genome JSON Patch。

## 2. 范围和非目标

### 2.1 P0 范围

- Victory 页面触发 Verified Replay Validation。
- Candidate 执行对象是当前 Run 的不可变 AgentPreset。
- Baseline 固定为 Run 中记录的 Base Skill Version。
- Baseline 和 Candidate 使用相同 Source Bundle、Dataset、Analyst/model、Evaluator 和实验预算。
- Candidate 不允许再次 autoEvolve，也不接收 Baseline feedback。
- 页面展示业务 Report、分数、硬门槛、关联修复、晋升结果和 `runtimeVerified`。
- 每个已执行 Evolution 节点可以点击查看完整详情。
- Codex 可以发现并解释最新 CaseValidation。

### 2.2 非目标

- 不开放 Live Validation UI。
- 不支持 AgentPreset 多 Skill 路由。
- 不为 Release Case 等其他 Case Pack 同时实现 Preset Runtime。
- 不执行逐 Mutation ablation，不宣称单个 Mutation 的独立因果贡献。
- 不允许 Preset 声明的工具自动获得额外权限。
- 不把 Verified Replay 描述成 Live。

## 3. 必须先冻结的核心语义

### 3.1 Baseline 与 Candidate

Baseline：

- 使用 `AgentPreset.sourceRun.baseSkillVersionId` 指向的历史 Skill Version。
- 不读取当前 Skill 的最新 Genome 替换历史版本。
- 不应用 AgentPreset additions。

Candidate：

- 使用 `candidatePresetId` 加 `candidatePresetDigest` 锁定不可变配置。
- 必须通过现有 AgentPreset Contract 和 digest 校验。
- `primarySkill.skillVersionId`、`sourceRun.baseSkillVersionId` 和 Evolution Run 的 Base Version 必须一致。
- `agent.instruction`、`workflow`、`rules` 和 runtime additions 通过正式 Preset Runtime Adapter 生效。
- `primarySkill.genome` 仍作为来源 Genome，不被伪造成新的 Genome Patch。

### 3.2 A/B 控制变量

一次 Validation 内必须保证：

- Source Bundle ID 和 digest 相同。
- Dataset 只构建一次，两组共用同一份确定性结果和 digest。
- Analyst provider、model、temperature 和可选 seed 相同。
- Evaluator 和 algorithm version 相同。
- 两组使用同一执行预算 envelope。
- 两组可访问的 Runtime 工具集合相同，由 Case Pack 决定。
- Candidate 不接收 Baseline Evaluation feedback。
- `autoEvolve=false`。

AgentPreset 的 `runtimeDefaults` 可以参与确定共享实验预算，但不能只给 Candidate 增加 token、timeout 或 tool-call 配额，否则分数变化无法只归因于 Candidate instructions/workflow/rules。

### 3.3 `runtimeVerified`、`accepted` 和 `promoted`

三个状态必须分开：

- `runtimeVerified=true`：Candidate 自身通过 Case Evaluator 且所有 hard gates 通过。
- `accepted=true`：Candidate `runtimeVerified=true`，并且 Candidate score 严格大于 Baseline score。
- `promoted=true`：Candidate accepted，且 Base Skill 当前版本仍等于 Validation 固定的 Base Version，新 Skill Version 创建成功。

因此允许出现：

```text
runtimeVerified=true
accepted=true
promoted=false
promotionStatus=version_conflict
```

这时 Validation 证据仍然有效，但系统不能覆盖已经发生变化的 Skill lineage。

## 4. CaseValidation Contract

### 4.1 建议请求

```json
{
  "casePackId": "finance-stock-analysis",
  "casePackVersion": "1.0.0",
  "mode": "verified_replay",
  "replayCaseId": "finance-case-...",
  "input": {
    "ticker": "AAPL",
    "asOfDate": "2026-07-21"
  }
}
```

`sourceRunId` 和 `candidatePresetId` 不由前端自由提交，后端根据路径中的 `runId` 和该 Run 的不可变 AgentPreset 解析，避免错误组合。

### 4.2 建议状态

```text
queued
→ loading_replay
→ validating_preset
→ building_dataset
→ executing_baseline
→ evaluating_baseline
→ executing_candidate
→ evaluating_candidate
→ comparing
→ promoting
→ completed / failed
```

### 4.3 建议结果摘要

```json
{
  "validationId": "case-validation-...",
  "sourceRunId": "run-...",
  "candidatePresetId": "preset-...",
  "candidatePresetDigest": "sha256:...",
  "casePackId": "finance-stock-analysis",
  "casePackVersion": "1.0.0",
  "mode": "verified_replay",
  "replayCaseId": "finance-case-...",
  "sourceBundleDigest": "sha256:...",
  "datasetDigest": "sha256:...",
  "executionPolicyDigest": "sha256:...",
  "baseSkillVersionId": "alphaear-signal-tracker-...@2",
  "baselineScore": 88,
  "candidateScore": 100,
  "scoreDelta": 12,
  "baselineHardGatesPassed": false,
  "candidateHardGatesPassed": true,
  "runtimeVerified": true,
  "accepted": true,
  "promotionStatus": "created",
  "evolvedSkillVersionId": "alphaear-signal-tracker-...@3"
}
```

### 4.4 API

```text
POST /api/runs/{runId}/case-validations
GET  /api/runs/{runId}/case-validation-options
GET  /api/runs/{runId}/case-validations
GET  /api/case-validations/{validationId}
```

其中：

- `case-validation-options` 只返回与 Run Base Skill category 兼容、具有持久化真实 Source Bundle 的 Case。
- P0 只返回 `verified_replay` 选项。
- POST 创建后台任务并立即返回 queued/running Validation，前端通过 GET 轮询。
- 重复请求需要基于 Run、Preset digest、Replay Case、Case Pack 和 execution policy 做幂等处理。

## 5. AgentPreset Runtime Adapter

### 5.1 推荐实现

新增一个 Case Pack 可选 Port：

```python
class PresetCaseRuntime(Protocol):
    async def execute_preset(
        self,
        preset: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        execution_policy: dict[str, Any],
    ) -> dict[str, Any]: ...
```

`CasePack` 增加可选 `preset_runtime`。P0 只为 `finance-stock-analysis` 实现，并为该 Pack 增加 `agent_preset_validation` capability。

不要求 `release-readiness` 立即实现空方法，也不修改已有 Genome Runtime 的行为。

### 5.2 Finance 执行映射

Finance Preset Runtime 使用现有 `load_agent_preset()` 完成完整性校验，并传递：

- Agent role 和 objective；
- Candidate instruction；
- Base 与追加 workflow；
- constraints、retry、fallback、output validation；
- tools 声明；
- Preset ID、digest 和 source Run lineage；
- 共享 execution policy。

Finance Analyst 的请求材料需要明确区分：

```text
executionKind=skill_version     # Baseline
executionKind=agent_preset      # Candidate
```

Preset 中的 `tools` 不直接触发任意工具调用。Finance Case 仍只使用 Case Pack 已批准的数据来源和确定性 Dataset。

## 6. Skill Version 与 Runtime Binding

现有 `save_evolved_skill()` 面向 Genome Patch，不应直接承担 AgentPreset Validation 晋升。

新增 `save_verified_preset_binding()`：

```json
{
  "runtimeBinding": {
    "contractVersion": "1.0.0",
    "kind": "agent-preset",
    "presetId": "preset-...",
    "presetDigest": "sha256:...",
    "validationId": "case-validation-..."
  },
  "runtimeVerification": {
    "runtimeVerified": true,
    "casePackId": "finance-stock-analysis",
    "casePackVersion": "1.0.0",
    "caseId": "finance-case-...",
    "evaluationId": "finance-eval-...",
    "sourceDigest": "sha256:...",
    "datasetDigest": "sha256:...",
    "verifiedAt": "..."
  }
}
```

需要同步修复 Skill Genome Schema 与 Python validator 的一致性。目前 Python Runtime 已写入 `runtimeVerification`，但 `src/contracts/skill-genome.schema.json` 尚未正式声明该字段。

未来执行绑定了 AgentPreset 的 Skill Version 时，Runtime Resolver 必须解析并验证对应 Preset digest，不能把该版本降级成只执行原始 Base Genome。

## 7. Evolution 已执行节点详情

### 7.1 当前缺口

当前 Run 状态主要保存：

- `completedNodeIds`；
- Monster Encounter 的 `encounterHistory`；
- 最后一次 `lastResult`；
- 全局 Mutation/Evolution ID；
- 文本日志。

这些数据不足以完整还原每个节点：

- Rest 和 Lab 只有短期 `lastResult`，后续会被覆盖。
- Mutation Draft 没有固定绑定到来源节点。
- 最终选择或跳过没有节点级结构化记录。
- Evolution 解锁没有记录是在哪个节点后发生。
- 无法比较进入节点前后的 stats、stability、compute 和 complexity。

因此不能只把已完成节点的 `<button disabled>` 改成可点击，必须先扩展权威 Run State。

### 7.2 新增 NodeRunRecord

建议在 `EvolutionRun` 增加：

```ts
interface NodeRunRecord {
  nodeId: string
  sequence: number
  act: number
  regionId?: string
  regionName: string
  layer: number
  type: string
  difficulty: number
  monsterId?: string | null
  status: 'entered' | 'completed' | 'failed'
  before: NodeBuildSnapshot
  result: BenchmarkResult | RestResult | LabResult | null
  reward: {
    mutationDraftIds: string[]
    selectedMutationId?: string | null
    skipped: boolean
    unlockedEvolutionIds: string[]
  }
  after: NodeBuildSnapshot | null
  logIds: number[]
}

interface NodeBuildSnapshot {
  stats: Record<string, number>
  stability: number
  compute: number
  complexityUsed: number
  mutationIds: string[]
  evolutionIds: string[]
}
```

字段要求：

- 进入节点时立即创建 `entered` record 和 before snapshot。
- Encounter、Rest、Lab、Boss 都必须保存 result。
- 生成 Mutation Draft 时写入 `mutationDraftIds`。
- 选择 Mutation 或 Skip 时更新同一个 NodeRunRecord。
- Evolution 解锁后记录本节点新增的 Evolution ID。
- 完成或失败时写入 after snapshot。
- 记录使用 sequence 和状态机顺序，不依赖前端本地时间。
- Boss 隐藏规则在执行前保持不变；执行后才展示真实 Benchmark 结果。

建议将 Run `saveVersion` 从 2 升到 3。读取历史 v2 Run 时进行兼容归一化：

- 能从 `encounterHistory` 还原的节点显示基础 Benchmark 详情；
- 无法还原的 Rest、Lab、Mutation 关联明确显示“旧版 Run 未保存完整节点证据”；
- 不伪造历史数据。

### 7.3 前端交互

新增：

- `NodeDetailDrawer.vue`：节点详情抽屉。
- `NodeBuildDelta.vue`：before/after 能力和资源变化。
- `NodeRewardDetail.vue`：Mutation Draft、选择、跳过和 Evolution 解锁。

`MapNode.vue` 点击规则调整为：

```text
available
  → 执行 selectNode

selected / completed / failed
  → 打开 Node Detail Drawer，不触发状态迁移

locked / skipped
  → 不可进入；可根据产品需要只显示基础 tooltip
```

自动进化运行期间：

- 当前正在执行和已经完成的节点可以打开只读详情。
- 可用路线仍由后端自动选择，前端点击不得触发 `selectNode`。
- Drawer 中的数据随轮询更新；正在执行的节点显示实时阶段。

节点详情展示顺序：

1. 节点、Region、难度和执行状态；
2. Monster 业务失败模式和业务示例；
3. 进入节点前的构筑与资源；
4. Benchmark coverage、threshold、case scores、compute 和 stability 变化；
5. Mutation Draft 三选一及最终选择/跳过；
6. 新解锁 Evolution；
7. 离开节点后的构筑；
8. 与该节点关联的 Replay 日志。

### 7.4 可访问性和防误操作

- 可查看详情的节点使用真实 button，并提供 `aria-expanded` 和 Drawer 关联 ID。
- ESC、关闭按钮和点击遮罩可以关闭 Drawer。
- Drawer 打开时焦点进入标题，关闭后返回原 Map Node。
- “查看详情”和“选择路线”需要不同的 aria-label 和视觉提示。
- 已执行节点不能因为点击详情而产生新的 API 状态迁移。

## 8. 前端 Real Case Validation

### 8.1 Victory 卡片

在 `ActionPanel.vue` 的 Victory 区域增加 `RealCaseValidationCard.vue`：

- Candidate AgentPreset ID 和 digest；
- Base Skill Version；
- 当前 evidence mode；
- Compatible Verified Replay 选择；
- `开始真实 Case 验证`；
- Validation phase 和进度；
- 最新 Validation 结果入口。

### 8.2 结果展示

优先展示业务内容：

1. Candidate 最终公司研究报告；
2. Source、evidence coverage 和 digest；
3. Baseline / Candidate score；
4. hard gate 差异；
5. Mutation/Evolution 与 fail→pass Gate 的关联；
6. accepted、promotion status 和新 Skill Version；
7. `runtimeVerified` 和 Replay 标签。

现有 `FinanceCasePage.vue` 已经包含 Report、Source、Evaluation 和 Comparison UI。应先抽取可复用展示组件，避免在 Evolution 页面复制 Finance 页面模板。

### 8.3 Mutation 效果表述

一次组合 Candidate A/B 无法证明单个 Mutation 的独立因果效果。

P0 只展示：

- Contribution 声明针对的 evaluator gates；
- 哪些 gates 从 Baseline fail 变为 Candidate pass；
- 文案统一使用“关联修复”或“覆盖该失败项”。

若未来需要独立归因，应增加逐 Mutation ablation Validation，作为单独阶段，不纳入 P0。

## 9. Codex MCP

新增：

```text
list_case_validations
get_latest_case_validation_context
validate_evolution_run_on_case
get_case_validation
get_case_validation_comparison
```

约束：

- `validate_evolution_run_on_case` 不是 read-only。
- 默认只允许 Verified Replay。
- Live 必须在后续阶段由用户明确授权。
- 所有输出保留 `mode`、Replay Case ID、source digest、Preset digest 和 `runtimeVerified`。
- Codex 不需要用户手工复制 Run、Preset 或 Validation ID。

同时扩展 Demo Context，使其返回最新：

- Evolution Run；
- AgentPreset；
- CaseValidation；
- Promotion result；
- Node History 摘要。

## 10. 分阶段开发任务

### P0-1：Contract 和数据模型（0.5–1 天）

- [x] 新增 `contracts/case_validation.py`。
- [x] 冻结 Baseline/Candidate、comparison、promotion 和 evidence 字段。
- [x] 新增 `NodeRunRecord` Contract。
- [x] Run `saveVersion` 升级到 3，并定义 v2 兼容规则。
- [x] 修正 Skill Genome Schema 对 `runtimeBinding` 和 `runtimeVerification` 的声明。
- [x] 增加 Contract 单元测试。

### P0-2：Node History 状态机（0.5–1 天）

- [x] select node 时保存 before snapshot。
- [x] Encounter/Rest/Lab/Boss 保存结构化 result。
- [x] Mutation Draft、选择和 skip 绑定到来源节点。
- [x] 保存本节点新解锁的 Evolution。
- [x] 完成/失败时保存 after snapshot。
- [x] 自动进化和手动进化共用同一套记录逻辑。
- [x] 验证固定 Seed 重放得到相同 Node History。

### P0-3：CaseValidation 持久化和 API（0.5–1 天）

- [x] 新增 `case_validations` 表和 migration。
- [x] 新增 Repository、revision 和幂等写入。
- [x] 实现 options、create、list、get API。
- [x] 保存 Source、Dataset、Execution Policy digest。
- [x] 后台任务保存每个 phase，支持前端轮询。

### P0-4：Preset Runtime 和 A/B Orchestrator（1–2 天）

- [x] 实现 `PresetCaseRuntime` Port。
- [x] Finance Case Pack 注册 Preset Runtime capability。
- [x] 校验 Run、Preset、Base Skill Version lineage。
- [x] Verified Replay Source Bundle 只加载一次。
- [x] Dataset 只构建一次。
- [x] 执行 Baseline 和 Candidate，不传 feedback。
- [x] 使用同一个 Evaluator 生成 comparison。
- [x] 记录 accepted/runtimeVerified 的独立判断。

### P0-5：Skill Version 晋升（0.5–1 天）

- [x] 新增 `save_verified_preset_binding()`。
- [x] accepted 时执行 optimistic version check。
- [x] 创建包含 Runtime Binding 的新 Skill Version。
- [x] 版本冲突时保留 Validation，不自动晋升。
- [x] rejected/no improvement 时不创建版本。
- [x] 后续执行绑定版本时解析并校验 Preset digest。

### P0-6：节点详情前端（0.5–1 天）

- [x] 扩展 TypeScript `EvolutionRun` 和 Node History 类型。
- [x] 调整 `MapNode.vue` 的选择/查看双行为。
- [x] 实现 `NodeDetailDrawer.vue`。
- [x] 展示 Benchmark、资源 delta、Mutation Draft、最终选择和 Evolution。
- [x] 自动运行期间支持只读实时详情。
- [x] 实现键盘、焦点和 aria 行为。

### P0-7：Validation 前端（1–1.5 天）

- [x] 新增 API Client 和 TypeScript Contract。
- [x] Victory 卡片加载 compatible replays。
- [x] 创建 Validation 并轮询 phase。
- [x] 抽取并复用 Finance Case 结果组件。
- [x] 展示 fail→pass gates、accepted、promotion 和 runtimeVerified。
- [x] Replay/Live/Simulation 标签保持严格区分。

### P0-8：Codex、Demo 和回归（0.5–1 天）

- [x] 新增 MCP Contract、API Client 和工具。
- [x] 更新 Codex Demo `AGENTS.md` 和 README。
- [x] 新增可复现的 Candidate Preset Validation 脚本。
- [x] 生成精简 summary 和完整 evidence artifacts。
- [x] 完成全量自动测试和构建。
- [ ] 浏览器点击 smoke test：Browser 安全策略拒绝 `localhost:5175`；正式 Demo 机器需人工执行，不允许在当前环境绕过。

## 11. 测试计划

### 11.1 Node History

- 普通 Encounter 记录 Benchmark、before/after 和 Mutation Draft。
- Mutation accepted 后记录 selected ID 和 Evolution unlock。
- Skip 记录 `skipped=true`。
- Rest 保存 heal 和 compute reward。
- Lab 保存 draft，后续选择绑定到同一节点。
- Boss 失败保存 result 和 failed 状态。
- 自动运行与手动运行生成同样结构。
- 旧 v2 Run 不伪造缺失详情。
- 点击 completed node 不产生新的 Run revision。

### 11.2 CaseValidation

- Replay 不调用 Live Gateway。
- Baseline 使用固定历史 Skill Version。
- Candidate digest 不匹配时失败。
- Preset 与 Run lineage 不一致时失败。
- 两组 Source/Dataset/Policy digest 相同。
- Candidate 不接收 Baseline feedback。
- Candidate hard gates 失败时不 verified、不 accepted。
- Candidate 通过但无严格提升时 verified、not accepted。
- Candidate 严格提升时 accepted。
- Skill Version 漂移时 accepted、not promoted。
- accepted 且版本未漂移时创建绑定版本。
- 重复请求不重复创建 Validation 或 Skill Version。

### 11.3 前端和 MCP

- Node Drawer 可通过鼠标和键盘打开关闭。
- 自动运行中已完成节点可查看、不可手动选择路线。
- Validation 运行中刷新页面可恢复轮询。
- 失败状态保留 partial evidence。
- 失败状态允许创建新的 retry attempt，旧证据不删除且重试链可追踪。
- Codex 自动发现最新 Validation。
- Codex 不把 Replay 描述成 Live。

## 12. 验收标准

本阶段完成必须同时满足：

1. 每个新 Run 的已执行节点都有结构化 Node History。
2. 前端每个 selected/completed/failed 节点可以点击查看详情。
3. 节点详情包含节点前后构筑、结果、资源变化和奖励选择。
4. 查看节点不会触发 Run 状态迁移。
5. Victory 页面可以选择兼容的 Verified Replay。
6. Baseline 固定 Base Skill Version。
7. Candidate 执行不可变 AgentPreset，而不是伪造 Genome Patch。
8. A/B 使用相同 Source Bundle、Dataset、Analyst/model、Evaluator 和实验预算。
9. Candidate 不接收 Baseline feedback，也不二次 autoEvolve。
10. 页面展示业务 Report、分数和所有 hard gate 差异。
11. `runtimeVerified`、`accepted` 和 `promoted` 不混用。
12. 只有 accepted 且版本未漂移时才创建新 Skill Version。
13. Runtime Verified Skill Version 能解析回精确 Preset ID 和 digest。
14. Codex 无需复制 ID 即可发现并解释最新 Validation。
15. UI、API、MCP 和文档不会混称 Simulation、Replay 和 Live。
16. 失败、无提升或版本冲突时保留证据但不错误晋升。
17. Python、Node、Vue type-check/build 和 Demo 脚本全部通过。
18. 正式演示机器完成浏览器点击级回归。

## 13. 预计工作量与交付顺序

| 模块 | 预计工作量 |
|---|---:|
| Contract、Schema 和 Node History | 1–1.5 天 |
| CaseValidation 表、Repository 和 API | 0.5–1 天 |
| AgentPreset Runtime Adapter 和 A/B | 1–2 天 |
| Skill Version Runtime Binding | 0.5–1 天 |
| Node Detail Drawer | 0.5–1 天 |
| Victory Validation 和结果页 | 1–1.5 天 |
| Codex、测试和 Demo 文档 | 0.5–1 天 |
| P0 合计 | 5–8 天 |

推荐按以下提交顺序开发：

1. Contract、Schema、Node History；
2. Node History 状态机和测试；
3. CaseValidation Migration/Repository/API；
4. Preset Runtime 和 A/B Orchestrator；
5. Runtime Binding 和 Skill Version 晋升；
6. Node Detail Drawer；
7. Victory Validation UI；
8. Codex MCP、Demo artifacts 和完整回归。

Node History 应先于前端 Drawer 开发；CaseValidation Contract 和 Preset Runtime 语义应先于 Victory Validation UI 开发。

## 14. 后续阶段

### P1：Codex 完整业务演示增强

- [x] 自动生成业务优先的演示讲稿。
- [x] 支持从 Node History 解释 Candidate 如何形成。
- [x] 将 Node 关联修复与真实 Case hard-gate 变化串成完整故事。

### P2：Live Validation

- Provider preflight。
- 实时来源刷新和真实 Analyst。
- timeout、retry、恢复和 provider response identity。
- 保存成功 Live Case 供后续 Verified Replay。

### P3：独立 Mutation 归因

- 可选 ablation runs。
- 单 Mutation / Evolution 增量比较。
- 运行成本控制和统计置信度。
- 明确区分相关性、组合贡献和独立因果贡献。
