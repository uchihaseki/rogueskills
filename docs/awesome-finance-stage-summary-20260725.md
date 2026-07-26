# Awesome Finance Skills 自进化 Demo 阶段性总结

> 日期：2026-07-25
> 状态：P0 与 P1 已完成；默认入库、前端自进化、真实案例同源 A/B、运行时验证、技能版本晋升和 Codex 业务演示已经连成一条链路。
> 非目标：Victory 页面不开放 Live Validation；本阶段只允许 `verified_replay`。

## 1. 当前结论

现在可以完整演示：

```text
Awesome-finance-skills 本地快照
  → 自动准入 Initial Library
  → 前端直接选择 AlphaEar Skill
  → 自动执行 Finance Evaluation Run
  → 生成不可变 Candidate AgentPreset
  → 选择已持久化的真实 Finance Case
  → Base Skill Version / Candidate AgentPreset 严格同源 A/B
  → 运行时验证与严格提升判断
  → 通过后创建 Runtime-bound Skill Version
  → Codex 自动发现并生成业务优先讲稿
```

这条链路同时保留两类证据，且不会混称：

- 前端 Evaluation Run：`capability-simulation-v1`，Candidate 生成时 `runtimeVerified=false`。
- 真实案例验证：`mode=verified_replay`，使用已持久化真实来源；Candidate 通过硬门槛后 `runtimeVerified=true`。

演示不需要前端导入按钮，也不需要复制 Run、Preset 或 Validation ID。

## 2. 已完成能力

### 2.1 Awesome Finance Skills 默认入库

默认本地数据库启动时，9 个 `alphaear-*` Skill 经过正式准入流程进入 Initial Library：

```text
SKILL.md
  → deterministic Genome conversion
  → quarantine
  → library-admission-v1
  → license / static safety gates
  → Initial Library
```

Skill 列表：

```text
alphaear-deepear-lite
alphaear-logic-visualizer
alphaear-news
alphaear-predictor
alphaear-reporter
alphaear-search
alphaear-sentiment
alphaear-signal-tracker
alphaear-stock
```

该过程只对默认本地数据库自动执行；测试数据库和显式指定数据库不会被污染。重复启动幂等。

默认数据库还会幂等写入一个可直接选择的真实数据案例：

- 名称：`Apple AAPL 公开财务分析`；
- Case ID：`case-run-demo-aapl-2026-07-21`；
- 分析基准日：`2026-07-21`；
- 来源：SEC EDGAR、SEC Company Facts、Yahoo Finance 截至日价格；
- Source Bundle digest：`sha256:70e28e357e7cdd0d7148738821fd023a8352f5fb627c67005e7a5b57d028b7ea`；
- Dataset digest：`sha256:e165a0bbbc2e33c78851873da64a73c619760267461528c429ed1411ebe9d28f`。

随库 fixture 只保留实际进入 Dataset Builder 的 26 条财务事实、4 份申报记录、3 个来源及其原始 URL、抓取时间和 SHA-256；去掉重复 raw response 后约 15 KB。它与原始 8.5 MB 持久化 Source Bundle 重建出的 Dataset 完全一致。临时数据库和显式数据库不会自动注入该案例。

### 2.2 中文前端和直接演示

前端已经采用中文主文案，英文只作为小字标签。用户不需要理解 Rogue 游戏术语：

- `Monster` 显示为业务失败模式或测试项；
- `Boss` 显示为隐藏验收测试；
- `Mutation` 显示为候选优化项；
- `Evolution` 显示为能力组合；
- `Weapon/Build` 显示为工具与候选配置。

前端直接从 Initial Library 读取 Skill，`alphaear-signal-tracker` 默认优先。用户点击“开始完整自动进化”即可完成 12 个节点并生成 Candidate AgentPreset。

Victory 后，“已验证回放案例”会默认选中内置的 AAPL 真实案例，并展示案例名称、说明、来源提供方、捕获时间和 Source Bundle digest，不需要先去 Finance 页面手工运行 Live Case。

### 2.3 Node History v3

所有新 Run 使用 `saveVersion=3`，每个已执行节点都保存：

- 节点入口时的 stats、失败预算、算力预算、复杂度和配置快照；
- Encounter、Rest、Lab 和 Hidden Holdout 的结构化结果；
- Mutation Draft、最终选择或跳过；
- 本节点解锁的能力组合；
- 节点出口快照和关联日志；
- `entered / completed / failed` 状态。

历史 v2 Run 会按 `completedNodeIds` 和 `encounterHistory` 重建可证明的记录。Rest/Lab 等缺失内容标记 `legacyIncomplete=true`，不伪造 before、after、reward 或 result。

前端的 selected/completed/failed 节点可打开只读详情抽屉。抽屉支持 ESC、遮罩关闭、标题焦点和关闭后返回原节点；查看详情不会触发 Run 状态迁移。

### 2.4 CaseValidation 与严格同源 A/B

Victory 页面现在可选择兼容的真实数据案例。选项始终返回：

```json
{
  "mode": "verified_replay",
  "sourceMode": "live"
}
```

其中 `sourceMode` 只说明原始 Case 的采集方式；Validation 本身不会重新访问在线数据源。

一次 Validation 在创建时锁定：

- Base Skill Version；
- Candidate Preset ID 与 digest；
- Replay Case、输入和 Case Pack version；
- Source Bundle digest；
- Analyst provider、model、temperature；
- token、timeout、tool-call 等共享预算；
- Execution Policy digest。

Baseline 和 Candidate 共用同一个 Source Bundle、一次构建的数据集、模型配置、预算和 Evaluator。Baseline 使用 `executionKind=skill_version`；Candidate 使用 `executionKind=agent_preset`。Candidate 不接收 Baseline feedback，也不会二次 `autoEvolve`。

系统明确区分：

```text
runtimeVerified = Candidate 自身通过评估与全部硬门槛
accepted        = runtimeVerified 且 Candidate score 严格大于 Baseline
promoted        = accepted 且 Base Skill 当前版本未漂移，新版本创建成功
```

失败、无提升和版本冲突都保留证据，但不会错误晋升。

### 2.5 Runtime Binding 与后续执行

accepted Candidate 会创建包含以下字段的新 Skill Version：

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

后续执行该 Skill Version 时，Runtime Resolver 会加载精确 Preset 并校验 digest。Preset 不存在、内容改变或 digest 不匹配时直接阻止执行；绑定版本也不允许再次 `autoEvolve`。

### 2.6 前端真实案例结果

Finance Case 页面与 Evolution Validation Drawer 共用 `FinanceBusinessReport.vue`。展示顺序为：

1. 公司研究结论、findings、risks、data gaps 和结论边界；
2. 来源证据与 Source/Dataset/Policy/Preset digest；
3. Baseline/Candidate 分数与全部 hard gates；
4. 节点优化项与 fail→pass gate 的关联修复；
5. `runtimeVerified`、`accepted`、`promoted` 和新 Skill Version。

贡献表述固定为 `associated_not_causal`：只能说明候选组合与门槛修复相关，不宣称单个优化项具有独立因果效果。

页面刷新会恢复保存的 Run、自动运行和进行中的 Validation polling。

## 3. Codex MCP

Demo 项目配置位于：

```text
examples/codex-awesome-finance-demo/.codex/config.toml
```

与 CaseValidation 相关的工具：

```text
list_case_validations
get_latest_case_validation_context
get_case_validation_demo_script
validate_evolution_run_on_case
get_case_validation
get_case_validation_comparison
```

`get_demo_context` 现在还返回：

- 最新或最新 Validation 所属的 Evolution Run；
- Candidate AgentPreset；
- 最新 CaseValidation；
- promotion result；
- Node History summary；
- 业务优先演示顺序和推荐 Prompt。

`get_latest_case_validation_context` 会比较多个 Run 下 Validation 的 `createdAt`，不会把“最近更新的 Run”误当成“最新 Validation”。

`get_case_validation_demo_script` 从持久化证据生成中文讲稿：先讲公司业务报告，再讲同源 A/B，然后用 Node History 解释 Candidate 如何形成，最后分别报告 verification、acceptance 和 promotion。

## 4. 可复现真实 Case

完整演示脚本：

```bash
npm run demo:awesome-finance
npm run demo:awesome-finance-replay
npm run demo:awesome-finance-preset-validation
```

最新 Candidate Preset Validation 结果：

| 项目 | 结果 |
|---|---|
| Source Case | `finance-case-6266b782a74c416ea985aa35031aee9d` |
| Evolution Run | `run-4c5f6a3f-536cba5160` |
| Node History | 12 / 12 completed，saveVersion 3 |
| Candidate Preset | `preset-79bc498291a81646d238` |
| Candidate digest | `sha256:5561053689af44325fb3582ad91091ef8f8b02b05466f7e0554dbd81aea2abf1` |
| Validation | `case-validation-b7de636ca4a0455594c68cea962ef64b` |
| Mode | `verified_replay` |
| Base Skill Version | `alphaear-signal-tracker-90641e@2` |
| Baseline | 88，`claim-citations` hard gate failed |
| Candidate | 100，all hard gates passed |
| Delta | +12 |
| Runtime verified | `true` |
| Accepted | `true` |
| Promoted | `true` |
| New Skill Version | `alphaear-signal-tracker-90641e@3` |

主要产物：

- `artifacts/awesome-finance-self-evolution-20260724/17-preset-validation-import.json`
- `artifacts/awesome-finance-self-evolution-20260724/18-preset-validation-run.json`
- `artifacts/awesome-finance-self-evolution-20260724/19-preset-validation.json`
- `artifacts/awesome-finance-self-evolution-20260724/20-preset-validation-comparison.json`
- `artifacts/awesome-finance-self-evolution-20260724/21-preset-validation-summary.json`

该脚本使用真实持久化 AAPL Source Bundle。为保证现场可复现，Demo Analyst 是 deterministic fixture，不是现场 LLM Provider 请求；真实 Live Analyst 仍属于独立增强模式。

## 5. Demo 建议流程

### 5.1 前端

1. 启动 API 与前端。
2. 选择默认的 `alphaear-signal-tracker`。
3. 点击“开始完整自动进化”。
4. 在运行中打开已完成节点，展示输入/输出快照、测试结果、候选优化项和能力组合。
5. Victory 后选择 AAPL 已验证回放案例。
6. 点击“开始运行时验证”。
7. 先展示 Candidate 公司研究报告，再展示 88→100、hard gate 修复和 Skill Version 晋升。

### 5.2 Codex

在 `examples/codex-awesome-finance-demo` 启动 Codex，然后依次提问：

```text
读取最新 Demo Context，说明当前 Skill、Evolution Run、Candidate AgentPreset 和证据模式。

生成最新 CaseValidation 的业务优先演示讲稿。

先给出 Candidate 的 AAPL 公司研究结论、风险和数据缺口，再解释 Baseline/Candidate 同源 A/B。

用 Node History 解释 Candidate 如何形成，并说明哪些优化项与 claim-citations 的修复相关。

最后分别说明 runtimeVerified、accepted、promoted 和新 Skill Version；不要把 Replay 称为 Live。
```

## 6. 测试与质量记录

已通过：

- Python pytest：121 tests；
- Node tests：29 tests；
- Python domain unittest：18 tests；
- Ruff：全 backend 与 tests/python；
- Vue type-check；
- Vue production build；
- 三条 Awesome Finance Demo 脚本；
- MCP Contract、initialize、tools/list 与 MockTransport 调用测试；
- `codex mcp get rogueskills-demo --json` 在 Demo 目录解析成功；
- `git diff --check`。

CaseValidation 分支覆盖包括：

- Replay 不调用 Live gateway；
- ticker 与 as-of date 不一致被拒绝；
- Source Bundle 和 Execution Policy 漂移被拒绝；
- Baseline/Candidate 共享执行策略且 Candidate 无 feedback；
- hard-gate failure、通过但无严格提升、严格提升；
- version conflict；
- 晋升后进程恢复不重复创建版本；
- unexpected error 保存 partial evidence；
- 失败记录保留后以新 attempt 重试，并记录 `retryOfValidationId` / `retryCount`；
- Preset digest、Run lineage 和绑定版本 digest 校验；
- 重复请求不重复创建 Validation 或 Skill Version。

### 6.1 2026-07-26 运行时失败修复

前端首次执行内置 AAPL Case 时出现过：

```text
CaseValidation 执行过程中发生未预期错误，已保留部分证据。
```

持久化状态中的底层类型为 `TypeError`。根因是上游 Analyst 连接失败时，
`FinanceAnalystError` 调用 `CaseRuntimeError` 漏传错误码，导致错误转换过程二次失败。
该构造器已修复，普通 Live Case 现在会保留原始的
`FINANCE_ANALYST_CONNECTION_FAILED` 等结构化错误，不再退化为泛化 `TypeError`。

内置 AAPL Demo 同时改为专用的本地确定性分析器：

- 只读取已持久化的 SEC / Yahoo Finance 快照和重建数据集；
- 不调用在线数据源，也不调用外部 LLM；
- Execution Policy 明确记录 `deterministic-replay`，不伪装成 Live 或现场 LLM；
- 稳定生成 Baseline 88、Candidate 100 的同源对照；
- 普通 Live Case 仍使用配置的真实 LLM Analyst。

失败后的同一选择不再锁死按钮。前端显示“重新运行时验证”，后端创建新的
Validation attempt，保留旧失败证据并建立重试链。已使用当前 Demo 数据库的备份验证：

| 项目 | 结果 |
|---|---|
| 旧 Validation | `case-validation-4c230f3e69744a5c9ff4185869a7437e`，`failed` |
| 新 attempt | 新 ID，`retryCount=1`，正确关联旧 Validation |
| Baseline / Candidate | 88 / 100 |
| Runtime verified / Accepted | `true` / `true` |
| Promotion | `created` |

## 7. 浏览器点击测试限制

本轮按 Browser 测试规范尝试打开 `http://localhost:5175/`，环境安全策略明确拒绝该地址，并禁止使用其他浏览器、Raw CDP 或间接方式绕过。因此无法在当前 Codex 环境完成点击级 smoke test。

已完成的安全替代验证为：进程内生产 FastAPI E2E、Vue type-check、production build、Node UI 基线测试、三条完整 Demo 脚本和 MCP 协议测试。正式 Demo 机器仍应人工执行第 5 节的点击流程一次。

## 8. 后续可选范围

P0/P1 没有遗留代码任务。后续仅为新范围：

- Live Validation UI 与明确授权；
- 多 Primary Skill / 多 Agent 路由；
- 其他 Case Pack 的 Preset Runtime；
- 逐优化项 ablation，用于独立因果归因；
- 远程 Worker 的强分布式 claim/lease。

这些内容不会影响当前 Verified Replay Demo 的完整性。
