# Awesome Finance Skills 自进化 Demo

这条 Demo 把本地 `Awesome-finance-skills` 快照接入 RogueSkills 的正式生命周期：

```text
SKILL.md 快照
  → 本地确定性 Genome 转换
  → quarantine
  → library-admission-v1 + 许可证 + 静态安全门槛
  → Initial Skill Library
  → Finance Evolution Map
  → 自动选择 Mutation / Evolution
  → AgentPreset
```

上游的 `skill-creator` 不是金融能力，因此不会被导入；当前会导入 9 个
`alphaear-*` skill。导入器会保存 `SKILL.md` 原文、仓库 revision、Apache-2.0
许可证和 GitHub artifact URL，并以 `sourceId=awesome-finance-skills` 标记。

这条演示验证的是 RogueSkills 的 Skill Genome、生命周期、准入和自进化 Runtime；
它不会在导入阶段直接执行上游 `scripts/`。上游脚本依赖 `requests`、`pandas`、
`torch`、`akshare` 等可选运行时，应在单独配置这些依赖和数据源后测试。

## 一键跑通

在项目根目录执行：

```sh
PYTHONPATH=backend .venv/bin/python \
  scripts/run_awesome_finance_self_evolution.py
```

这个 runner 使用生产 FastAPI 组合，但不需要 LLM、GitHub 或行情网络。默认把
9 个 skill 写入 `data/rogueskills.db`，并将演示产物写入：

```text
artifacts/awesome-finance-self-evolution-20260724/
```

推荐现场展示的文件：

- `01-awesome-import.json`：9/9 发现、9/9 通过准入并进入 Initial Library。
- `05-run-final.json`：Finance Map 的 12 个节点全部完成，状态为 `victory`。
- `06-agent-preset.json`：由 9 个金融 Mutation 和 3 个 Evolution 组合出的候选 AgentPreset。
- `07-runtime-config.json`：可加载的运行时配置。
- `08-summary.json`：适合在演示页面直接读取的摘要。
- `09-codex-demo-context.json`：Codex `get_demo_context` 会读取的最新 Skill、Run、目录和 AgentPreset 结构。

## 前端直接演示

使用默认本地数据库启动：

```sh
npm start
npm run frontend:dev
```

打开 `http://127.0.0.1:5174/`。后端启动时会自动、幂等地把本地
`Awesome-finance-skills` 快照放入 Initial Library；前端的角色选择页会直接显示这些
Finance Skill，不需要再点击导入按钮。选择任意 `alphaear-*` Skill，进入任务部署并运行
Evolution 即可。默认地图码 `ROGUE-0714` 对当前 9 个 Skill 均可完成 Finance Map。

默认数据库同时会加入 `Apple AAPL 公开财务分析` 真实数据案例。它来自已经持久化的
SEC EDGAR、Company Facts 和截至日市场价格快照，随库文件为
`backend/rogueskills/domain/data/finance-demo-aapl.json`。Victory 后页面会直接选中该案例，
不需要先跑 Live 或导入数据库；Validation 始终使用 `verified_replay`，不会现场请求 Provider。

现场可以在 Codex 中继续问：

```text
解释当前选中的 Skill Genome：它的输入、步骤、约束和能力证据是什么？
为什么本局选择这些 Mutation？它们分别修复了哪个金融验收压力？
把这次 Run 的 baseline、Mutation、最终 AgentPreset 和 runtimeVerified 状态整理成演示讲稿。
```

这些问题直接对应 `/api/library/initial`、`/api/runs/{runId}`、
`/api/agent-presets/{presetId}/runtime-config` 的权威状态，不依赖前端自行计算。
如果从 Codex 演示，使用 `examples/codex-awesome-finance-demo` 的项目配置；先调用
`get_demo_context`，它会自动找到最近一局并返回 Skill、Run、Mutation/Evolution 目录和
AgentPreset。之后可按需调用 `get_skill`、`get_skill_version`、`get_evolution_run` 和
`get_agent_preset`，无需让演示者手工复制 opaque Run ID。

演示选择的是 `alphaear-signal-tracker`，因为它的“研究 → 分析 → 跟踪信号”
工作流与自进化叙事最匹配。自动运行锁定四个金融压力项：

```text
stale_filing_imp → multiple_trap → source_conflict_sphinx → advice_mimic
```

其中 `advice_mimic` 会让自动 Mutation 优先补齐风险治理和安全边界；如果不选它，
某些较弱的 AlphaEar skill 会在第一幕财报重述 Boss 的安全硬门槛处失败，这是一个
有意义的反例，不应被隐藏。

## 运行时证据版

如果需要展示“真实 Case 证据驱动的 Skill Version 进化”，再执行：

```sh
PYTHONPATH=backend .venv/bin/python \
  scripts/run_awesome_finance_verified_replay.py
```

这个 runner 从已经持久化的真实 AAPL Case 读取 SEC EDGAR、公司事实和市场价格快照，
以 `verified_replay` 重跑，不重新抓取网络，也不会把 replay 冒充成 live。默认来源是：

```text
artifacts/finance-e2e-20260722/prior-real.db
```

为保证演示完全可复现，本 runner 的 Analyst 使用本地 deterministic fixture；来源快照、
Case Contract、Evaluation、Mutation 和 Skill Version 仍走生产 Runtime。要验证真实模型，
把同一 Case 改为 `live` 并配置 Finance Analyst 即可。

推荐现场展示的文件：

- `10-verified-replay-case.json`：`alphaear-signal-tracker@2` 的基线和进化阶段。
- `13-verified-replay-evaluation.json`：基线 `88.0`、因 `claim-citations` 失败；进化后 `100.0`。
- `14-verified-replay-artifact.json`：`runtimeVerified=true` 的 AgentPreset。
- `15-evolved-skill.json`：不可变版本链，`@2 → @3`。
- `16-verified-replay-summary.json`：Case ID、Mutation、版本、Digest 和证据模式摘要。

这条路径的关键讲解点是：

1. 基线报告可以有足够的财务覆盖，但没有逐事实引用，不能通过硬门槛。
2. Mutation Planner 提议加入 `SEC EDGAR`、`MarketData`、事实级 evidence ID、现金流核对和三情景估值步骤。
3. 进化报告得分从 88 提升到 100，Mutation 被接受，保存为新的 `Skill Version`。
4. 只有通过硬门槛的最终结果才会生成 `real-finance-case-v1`、`runtimeVerified=true` 的 AgentPreset。

## API 演示顺序

如果要在 UI/API 页面逐步演示，可按这个顺序调用：

```text
POST /api/scenarios/finance/import-awesome
GET  /api/library/initial
POST /api/runs
POST /api/runs/{runId}/auto
GET  /api/runs/{runId}
GET  /api/agent-presets/{presetId}/runtime-config
```

Codex 只读上下文入口：

```text
GET  /api/demo/context
GET  /api/skill-versions/{skillVersionId}
```

运行时证据版使用通用 Case API：

```text
GET  /api/finance/cases
POST /api/case-runs   (mode=verified_replay, autoEvolve=true)
GET  /api/case-runs/{caseId}
GET  /api/case-runs/{caseId}/evaluation
GET  /api/case-runs/{caseId}/artifact
GET  /api/skills/{skillId}
```

注意：传统 Evolution 产物的 `evaluationEvidence.mode` 是
`capability-simulation-v1`、`runtimeVerified=false`；Verified Replay 产物才是
`real-finance-case-v1`、`runtimeVerified=true`。两者都是有效产物，但不能混称。
