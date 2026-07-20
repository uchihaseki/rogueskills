# RogueSkills ProjectRelease 设计与演进路线

> 状态：长期方向已确认；短期 `AgentPreset v0.1` 已实现，完整 ProjectRelease 尚未实现。
>
> 日期：2026-07-20
>
> 本文记录 RogueSkills 从“单 Skill 发现与数值型进化原型”演进为“可按业务场景发布并装载 Agent 配置”的目标设计，同时给出一个可基于现有代码落地的短期过渡产物。

## 1. 已确认的产品方向

RogueSkills 的目标链路是：

```text
拉取 Skills
→ 过滤与标准化
→ 保存和准入
→ 基于评测证据持续进化
→ 按业务场景组合 Skills、Prompt、Workflow 和规则
→ 发布完整配置
→ 装载为特定业务 Agent
→ 收集脱敏反馈并产生下一版本
```

已确认以下设计决策：

1. 最终产物采用 `ProjectSpec → ProjectRelease` 两层模型。
2. Agent 只加载不可变 Release，Release 固定所有 Skill Version。
3. 自回归进化可覆盖 Skill、Routing、Workflow 和 Project Prompt，但每一代只修改一个主要维度。
4. 安全、权限、Secret 和合规规则不能被自动放宽。
5. 最终胜负由 Project 级 Scenario Pack 决定，不使用全局 Skill 排名决定业务 Agent。

## 2. 当前原型的实际最终产物

当前原型已经具备：

- Builtin/GitHub Skill Discovery。
- 候选排序、去重、License 和静态风险扫描。
- Material/SOP 到 Skill Genome 的转换。
- Quarantine、Admission Benchmark 和 Initial Library。
- 不可变 Skill Version、来源快照和评测记录。
- 服务端权威 Evolution Run、固定 Seed 地图和并发 Revision。
- Mutation、Evolution、Encounter 和 Run Replay。

但当前 Evolution Run 的实际结果仍是一份 `EvolutionRun.state_json`：

- `baseSkillGenome`
- `stats`
- `mutationIds`
- `evolutionIds`
- `encounterHistory`
- `logs`
- `victory` 或 `defeat`

当前 Mutation 只改变 Run 中的能力数值，没有生成真实 Genome Patch；Victory 只表示“获得候选资格”，不会保存 Candidate、Project 配置或可装载 Agent Bundle。

因此当前原型是一个可持久化的 Skill 进化实验过程，还不是完整的 Agent 装备与发布系统。

## 3. 目标资产分层

### 3.1 Skill Genome

Skill Genome 是一个原子能力，包含：

- Metadata
- Prompt
- Workflow
- Inputs / Outputs
- Constraints
- Tools
- Capabilities
- Examples / Test Cases
- Evaluation
- Provenance / Risk
- Version / Lineage

Skill Genome 不负责描述一个完整业务 Agent，也不直接保存服务端权限。

### 3.2 ProjectSpec

ProjectSpec 是可编辑的业务场景设计稿，描述：

- 业务目标和边界。
- 支持与禁止的用户意图。
- 所需能力和可选能力。
- 输入输出 Contract。
- Agent 身份、语言、语气和 Prompt。
- Workflow、Routing、Fallback 和人工接管规则。
- Tool、Runtime、预算和权限要求。
- Memory、Knowledge 和数据保留策略。
- Guardrails 和合规要求。
- 业务指标、Scenario Pack 和停止条件。

ProjectSpec 允许被编辑，但不能直接作为生产 Agent 配置使用。

### 3.3 ProjectCandidate

ProjectCandidate 是某个 ProjectSpec 经 Skill 选择、组合和进化后形成的完整候选配置：

- 固定的 ProjectSpec Version。
- 固定的 Skill Version Loadout。
- 编译后的 Prompt、Workflow、Routing 和规则。
- Tool Binding 和权限要求。
- 父 Candidate、Mutation 和评测证据。
- 内容摘要和兼容信息。

Candidate 可以继续进化，但不能直接覆盖生产 Release。

### 3.4 ProjectRelease

ProjectRelease 是通过 Validation、Hidden Test 和发布审批后的不可变配置包，也是 Agent Loader 唯一允许装载的 RogueSkills 产物。

Release 必须固定所有依赖，不能引用 `latest`。

## 4. 完整 ProjectRelease 内容

### 4.1 Manifest

- Project ID、Release ID 和父 Release。
- Schema Version、Release Version 和状态。
- 创建、审批和发布时间。
- 内容 Digest。
- 目标 Agent Runtime 和兼容版本。

### 4.2 Business Contract

- 业务目标。
- 支持和禁止的场景。
- 用户意图。
- 输入输出 Schema。
- 成功标准、SLA 和人工升级条件。

### 4.3 Agent Profile 与 Prompt Set

- Agent 身份、职责、语言和语气。
- Project 级业务指令。
- 回答模板和 Few-shot 示例。
- Prompt 变量和编译顺序。

建议的运行时优先级：

```text
平台安全策略
→ Project Agent Prompt
→ Project Workflow 和业务规则
→ 当前 Skill Prompt、Workflow 和 Constraints
→ 用户任务和运行时数据
```

低层内容不能覆盖高层策略。

### 4.4 Skill Loadout

每个 Skill Binding 至少包含：

- `skillId`
- `skillVersionId`
- `role`: primary / supporting / fallback
- `triggers`
- `priority`
- `dependsOn`
- `fallbackTo`
- `inputBindings`
- `outputBindings`
- `budgetOverrides`

### 4.5 Routing 与 Workflow

- Task 到 Skill 的匹配规则。
- 最低置信度和冲突处理。
- 无匹配场景处理。
- 节点、边和条件分支。
- 并行、重试、回退、终止和人工审批。

### 4.6 Tools 与 Runtime

- 逻辑 Tool ID 和 Runtime Binding。
- 参数 Schema 和返回 Contract。
- Tool Allowlist、权限范围和副作用级别。
- 模型选择、Token、Tool Call、延迟和并发预算。
- Environment 和 Secret 引用。

权限必须由 Runtime 强制执行，不能只写在 Prompt 中。

### 4.7 Knowledge、Memory 与 Guardrails

- 知识库引用和检索策略。
- Session Memory 和长期记忆策略。
- 隐私、保留周期和清理规则。
- Prompt Injection、PII、License 和危险操作策略。
- 人工接管与审批规则。

### 4.8 Evaluation 与 Lineage

- Skill Evaluation。
- Project 端到端 Evaluation。
- Scenario Pack、Split 和算法版本。
- Baseline、Candidate 和回归比较。
- Source Snapshot、Mutation、父版本和审批记录。

### 4.9 不进入 Release 的数据

- Secret 和 Token 的真实值。
- Hidden Test 的输入和答案。
- 用户会话数据。
- 可变长期记忆内容。
- 未脱敏 Trace。
- 外部来源中的任意可执行代码。

## 5. 目标端到端算法

```text
ProjectSpec
→ 需求标准化和能力拆解
→ 多来源 Discovery
→ 拉取前元数据粗过滤
→ 拉取内容快照
→ 统一语义标准化为 Skill Genome
→ 安全、License、Schema 和兼容性深度过滤
→ Quarantine 和 Admission
→ Project Skill Portfolio Selection
→ Baseline ProjectCandidate
→ Train Runtime Execution
→ Evaluation 和失败证据聚类
→ Mutation Proposal
→ 白名单 Patch 和不可变子版本
→ 同 Seed 配对评测和 Champion Selection
→ Validation
→ Hidden Project Evaluation
→ ProjectRelease
→ Agent Loader
```

### 5.1 Skill 过滤

保留现有 Discovery Score 作为候选基础分，在 Project 阶段增加 Project Fit：

```text
ProjectFit =
  能力覆盖
+ 真实评测证据
+ 输入输出兼容性
+ Runtime 和 Tool 兼容性
+ 对当前 Loadout 的互补性
+ Discovery 基础分
- 风险、冲突、成本和复杂度惩罚
```

硬门槛失败直接拒绝；其余候选进入 Portfolio Selection。

### 5.2 Portfolio Selection

MVP 可以采用确定性的加权集合覆盖：

1. 选择覆盖最多必需能力的 Primary Skill。
2. 使用 Supporting Skills 补齐能力缺口。
3. 为关键失败模式选择 Fallback。
4. 检查 Prompt、Tool、I/O 和权限冲突。
5. 生成 Skill 间的 Input/Output Binding。
6. 固定所有 Skill Version。

不存在全局最强 Skill，只有在指定 Project Scenario Pack 下更合适的组合。

### 5.3 自回归进化

```text
Evidence_t = Evaluate(Execute(Candidate_t, TrainPack))

Proposals_t = Planner(Candidate_t, Evidence_t)

Children_t = Validate(ApplyWhitelistPatch(Candidate_t, Proposals_t))

Candidate_t+1 = Select(Candidate_t, Children_t)
```

每轮保持一个 Champion，并基于证据生成三个 Challenger。

每一代只允许一个主要 Mutation Scope：

- Skill Prompt / Workflow / Constraints / Example。
- Routing。
- Project Workflow。
- Project Prompt。

安全、权限、Secret、Hidden 和合规策略不能自动放宽。

### 5.4 Selection 与停止条件

新 Candidate 只有满足以下条件才能成为下一代 Champion：

- Schema、License、安全和权限硬门槛通过。
- 使用相同 Scenario Pack、Seed 和 Runtime 进行配对比较。
- Project Utility 达到最小有效提升。
- 关键指标回归不超过容忍值。
- 复杂度和计算预算没有超限。

停止条件包括：

- 达到目标分数和覆盖率。
- 连续若干代无有效提升。
- Token、Execution 或时间预算耗尽。
- 达到最大复杂度。
- 出现必须人工处理的权限或业务决策。

## 6. 长期数据与服务模块

目标实现需要增加以下核心数据：

- `projects`
- `project_spec_versions`
- `project_candidate_versions`
- `project_releases`
- `project_release_skills`
- `project_evolution_runs`
- `mutation_proposals`
- `scenario_packs`
- `executions`
- `project_evaluations`

建议的 Python 模块：

```text
backend/rogueskills/
├── domain/
│   ├── projects.py
│   ├── portfolio.py
│   ├── project_evolution.py
│   ├── project_evaluation.py
│   └── releases.py
├── contracts/
│   ├── projects.py
│   ├── project_releases.py
│   ├── scenarios.py
│   └── loader.py
├── application/
│   ├── project_service.py
│   ├── project_run_service.py
│   └── release_service.py
├── infrastructure/
│   └── project_repository.py
├── agents/
│   ├── project_normalizer.py
│   └── project_mutation_planner.py
└── adapters/
    ├── fixture_runtime.py
    ├── project_loader.py
    └── scenario_store.py
```

现有单 Skill Evolution Engine 保留为原型和 Fixture，新 Project 算法不继续堆入现有 `domain/evolution.py`。

## 7. 长期实施阶段

### M0：Contract 和迁移基线

- 冻结 ProjectSpec、Candidate、Release、Scenario Contract。
- 增加 Contract Fixture。
- 增加 Project 相关数据库表。
- 保证现有测试继续通过。

### M1：Project 和初始 Skill Loadout

- ProjectSpec Version。
- Discovery 查询生成和两级过滤。
- Portfolio Selection。
- Baseline ProjectCandidate。

### M2：真实执行和 Project Evaluation

- Fixture Runtime。
- Execution、Trace 和 Usage。
- Project Scenario Pack。
- Train、Validation、Hidden 权限。

### M3：真实 Mutation 和 Candidate

- Mutation Proposal。
- Patch 白名单。
- Project-scoped Skill 子版本。
- Champion/Challenger Selection。

### M4：ProjectRelease 和 Agent Loader

- Hidden Gate。
- Release 编译和 Digest。
- 审批、发布和回滚。
- Python Loader。

### M5：反馈闭环

- 脱敏 Runtime Feedback。
- 去重和失败聚类。
- Evolution Queue。
- Canary 和新一代 Release。

## 8. 短期过渡目标：AgentPreset v0.1

完整 ProjectRelease 短期实现成本过高。当前代码已经交付一个更小但真实可保存、可导出、可装载的产物：

> `AgentPreset v0.1`：从一局胜利的单 Skill Evolution Run 生成的不可变、静态 Agent 配置快照。

它不是经过真实 Runtime 和 Hidden Dataset 验证的 Production Release，也不支持多 Skill 动态路由，但能把当前 Run 的成果从“游戏状态”转成一个明确的 Agent 配置资产。

### 8.1 AgentPreset 内容

```text
AgentPreset
├── manifest
├── projectProfile
├── sourceRun
├── primarySkill
├── prompt
├── workflow
├── tools
├── rules
├── runtimeDefaults
├── evaluationEvidence
└── limitations
```

至少包含：

- Project 名称、场景和说明。
- Run ID、Seed、Mode 和 Revision。
- 精确的基础 Skill Version。
- 嵌入的 Skill Genome 快照。
- 编译后的 Role、Objective、Instructions。
- 基础 Workflow 和固定 Mutation/Evolution 规则扩展。
- Tool Allowlist。
- Constraints、Fallback、Retry 和输出验证规则。
- 当前数值 Benchmark 证据。
- `runtimeVerified: false` 和能力边界声明。
- 内容 Digest。

### 8.2 固定 Mutation 编译

短期不使用 LLM 生成任意 Patch，而是在内部 Mutation Catalog 中增加经过人工维护的确定性配置片段，例如：

```text
schema_validator
→ 增加输出 Schema 校验步骤和约束

retry_guard
→ 增加有界重试规则

screenshot_ocr
→ 增加 OCR Tool 需求和视觉回退步骤

injection_shield
→ 增加页面内容与系统指令隔离规则
```

编译器将基础 Genome 与选中的固定片段合并、去重并校验，生成 AgentPreset。这样产物比数值属性更接近真实 Agent 配置，同时避免立即实现 Mutation Planner、真实 Runtime 和复杂 Project 数据模型。

### 8.3 短期能力边界

AgentPreset v0.1：

- 支持单 Project 场景描述。
- 支持一个 Primary Skill。
- 支持固定版本和不可变快照。
- 支持 Prompt、Workflow、Tools 和规则导出。
- 支持简单 Python Loader 或导出 JSON。
- 不支持多 Skill Router。
- 不支持真实 Tool Runtime 编排。
- 不把当前数值 Benchmark 宣称为真实业务验证。
- 不自动发布为 Production。

这个过渡产物的数据结构应尽量成为未来 ProjectRelease 的子集，使后续升级不需要推翻已有数据。
