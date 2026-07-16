# RogueSkills P1 三人开发计划

> v0.2 更新：Python/FastAPI 迁移、权威 Run 状态机、生命周期版本校验和 Agent Port 已完成。本文后续工作包仍有效，但实现路径以 `python-architecture.md` 为准。

## 1. P1 共同目标

P1 不以增加更多页面、职业或连接器为首要目标。三个人共同交付一个 Browser Skill 的真实进化纵向闭环：

```text
Initial Browser Skill
→ 真实 Runtime 执行
→ Output Evaluator
→ Mutation Proposal
→ Genome Patch 和子版本
→ Validation
→ Hidden Boss
→ Candidate 落库
```

P1 完成后，系统应从“数值驱动的游戏原型”升级为“能产生真实 Skill 候选版本的实验平台”。

## 2. 当前基线

- P0 Discovery、Repository、确定性 Benchmark 和 Evolution Run 已连通。
- 27 项测试覆盖前端、后端、Core 和 P0 集成流程。
- 代码已按 `frontend/backend/core/contracts` 重排。
- GitHub 网络、内容拉取和跨源编排已从 Core 移入 Backend Connector。
- 当前 Benchmark 仍基于 Capability 数值，不调用真实 LLM 或工具。
- 当前 Mutation 只改变 Run 属性，不生成 Genome Patch。
- 当前 Victory 只展示候选资格，不保存 Candidate。

P0.1 必须先解决：

- 外部 `POST /api/skills` 可以通过提交状态绕过准入。
- 旧版本通过的 Evaluation 可以晋升已经修改的新版本。
- Hidden Test 尚未真正隔离，界面描述应与实际能力保持一致。

## 3. 工作包

### 3.1 前端负责人

| ID | 任务 | 交付物 | 前置依赖 | 验收标准 |
|---|---|---|---|---|
| FE-01 | API Client 与错误协议统一 | 请求封装、错误码映射、加载与重试状态 | CON-01 | 不再依赖解析错误文案；旧 API 保持兼容 |
| FE-02 | Benchmark 执行状态 | 排队、运行、超时、失败、完成界面 | BE-03 | Fixture 和真实 API 两种模式均可展示 |
| FE-03 | Result 与 Trace 展示 | 用例、指标、成本、延迟、脱敏 Trace | CON-02、BE-04 | 前端不重新计算分数；Hidden 不泄露细节 |
| FE-04 | Genome Diff 展示 | Mutation 前后对比、收益和代价 | ALG-04 | 能展示 Prompt/Workflow/Tools/Constraints 变化 |
| FE-05 | Candidate 保存流程 | 通关确认、保存中、成功和冲突处理 | BE-06 | Candidate 返回真实版本 ID，可进入详情页 |
| FE-06 | Candidate 对比页 | Initial 与 Candidate 指标、Diff、谱系 | BE-06 | 能追溯父版本、算法版本和评估版本 |
| FE-07 | 纵向 E2E | Browser 闭环浏览器测试 | M3 | 覆盖成功路径和一次 Runtime 失败路径 |

### 3.2 后端负责人

| ID | 任务 | 交付物 | 前置依赖 | 验收标准 |
|---|---|---|---|---|
| BE-01 | 生命周期边界修复 | Command Service、状态转换校验、回归测试 | 无 | 直接写 `initial` 被拒绝；旧 Evaluation 不能晋升新版本 |
| BE-02 | Repository 迁移基线 | Migration 版本、执行记录和回滚策略 | 无 | 新库和现有库都能升级；重复执行安全 |
| BE-03 | Runtime Orchestrator | 队列状态、超时、取消、Adapter 接口 | CON-02 | 固定 Fixture Adapter 可稳定执行 |
| BE-04 | Execution/Trace 存储 | execution、trace、usage、result 数据模型 | BE-02、BE-03 | 每次评测绑定 Skill 和 Scenario 不可变版本 |
| BE-05 | Dataset 隔离服务 | Pack 版本、Split 权限、Hidden 脱敏 | ALG-02 | Hidden 输入和答案不出服务端 |
| BE-06 | Evolving/Candidate 持久化 | Run、Patch、父版本、Candidate API | ALG-04、BE-02 | Patch 失败不污染父版本；成功生成不可变子版本 |
| BE-07 | 外部连接器生产化 | Connector 健康检查、持久缓存、限流和凭证策略 | M3 | Core 不访问网络；连接器故障可观测、可降级 |
| BE-08 | CI 与服务集成测试 | 分层测试、迁移测试、API 测试 | 全程 | 合并前自动运行所有测试 |

### 3.3 算法负责人

| ID | 任务 | 交付物 | 前置依赖 | 验收标准 |
|---|---|---|---|---|
| ALG-01 | Evaluation Contract | Request、Result、Metric 定义和 Fixture | 无 | 前端、后端共同确认字段 |
| ALG-02 | Browser Scenario Pack | Train/Validation/Hidden 用例和版本规则 | ALG-01 | 三种 Split 有明确反馈边界和 Golden Cases |
| ALG-03 | Output Evaluator | JSON 提取质量、安全、成本和延迟评分 | ALG-02、BE-03 | 同一 Output 得到相同结果；错误原因可解释 |
| ALG-04 | Mutation Proposal/Patch | Patch 白名单、证据、收益和代价 | ALG-01 | Patch 可通过 Genome Schema；失败可安全回退 |
| ALG-05 | Mutation 召回和排序 | 基于失败证据的三选一 | ALG-03、ALG-04 | 固定 Seed 与证据下结果可复现 |
| ALG-06 | Boss/Hidden 规则 | 只返回必要摘要的最终验收算法 | ALG-02、BE-05 | 进化阶段无法读取 Hidden 答案 |
| ALG-07 | Algorithm Versioning | evaluator、planner、scenario 版本字段 | ALG-01 | 每个 Result 和 Proposal 可追溯算法版本 |
| ALG-08 | Golden Regression | 算法成功和失败 Fixture | ALG-02～07 | 算法改动导致预期变化时必须显式更新基线 |

### 3.4 共享契约任务

| ID | 任务 | 主负责人 | 共同评审 | 退出条件 |
|---|---|---|---|---|
| CON-01 | Lifecycle 和 API Error | 后端 | 前端、算法 | Schema、Fixture、错误码冻结 |
| CON-02 | Runtime/Evaluation | 算法、后端 | 前端 | Fixture Adapter 跑通并能完整展示 |
| CON-03 | Scenario Pack/Split | 算法 | 后端 | Hidden 权限测试通过 |
| CON-04 | Mutation/Patch | 算法 | 前端、后端 | Patch 校验、展示和持久化跑通 |

## 4. 里程碑与并行顺序

### M1：P0.1 边界收口

并行工作：

- 后端完成 BE-01、BE-02 和 CON-01。
- 算法完成 ALG-01、ALG-02 草案。
- 前端完成 FE-01，并用 Fixture 准备 Benchmark 状态容器。

退出条件：

- 生命周期绕过和旧 Evaluation 问题有回归测试。
- Contract v1 的 Evaluation、Error 和 Lifecycle 字段得到三方确认。
- 现有 P0 集成测试继续通过。

### M2：真实执行最小切片

并行工作：

- 后端完成 BE-03、BE-04。
- 算法完成 ALG-03 和最小 Validation Case。
- 前端完成 FE-02、FE-03。

退出条件：

- 一个 Browser Skill 能执行一个真实或受控 Runtime Case。
- Result 来自实际 Output，不再来自 Capability 数值推导。
- 前端能展示状态、Result 和脱敏 Trace。

### M3：真实 Mutation 和 Candidate

并行工作：

- 算法完成 ALG-04、ALG-05。
- 后端完成 BE-05、BE-06。
- 前端完成 FE-04、FE-05。

退出条件：

- 失败证据能生成三个 Mutation Proposal。
- 选择 Mutation 后生成并保存合法 Genome 子版本。
- Validation 通过后可以继续 Run，失败可回退父版本。

### M4：Hidden Boss 和纵向验收

并行工作：

- 算法完成 ALG-06～08。
- 后端完成 Hidden 隔离和 CI。
- 前端完成 FE-06、FE-07。

退出条件：

- Hidden 数据未泄露给前端和 Mutation Planner。
- 通关后生成真实 `candidate`，失败不改变 Initial Skill。
- Browser 纵向 E2E、Golden Regression 和现有 P0 测试全部通过。

## 5. 集成矩阵

| 集成点 | 提供方 | 消费方 | 首个里程碑 | 当前状态 |
|---|---|---|---|---|
| Lifecycle Command/Error | 后端 | 前端 | M1 | Draft |
| Evaluation Contract | 算法 | 后端、前端 | M1 | Draft |
| Runtime Adapter/Trace | 后端 | 算法 | M2 | Planned |
| Scenario Pack/Split | 算法 | 后端 | M2 | Draft |
| Evaluation Result UI | 算法、后端 | 前端 | M2 | Planned |
| Mutation Proposal/Patch | 算法 | 后端、前端 | M3 | Draft |
| Candidate API | 后端 | 前端 | M3 | Planned |
| Hidden Result Summary | 算法、后端 | 前端 | M4 | Planned |

## 6. 三方对齐机制

### 每个任务开始前

负责人写清：

1. 输入契约。
2. 输出契约。
3. 可重试与不可重试错误。
4. 数据版本和兼容策略。
5. 正常、失败和边界验收样例。

消费方确认 Fixture 后，提供方才进入实现阶段。

### 每日同步

只同步三项：

- 昨天完成了哪个可验收交付物。
- 今天需要哪个契约或 Fixture。
- 是否存在跨模块阻塞。

内部实现细节不占用三方同步时间，放在对应代码评审中解决。

### 每周两次集成检查

- 检查 `tests/integration` 是否仍然通过。
- 更新本文的集成矩阵和任务状态。
- 处理契约变更，不在群聊中口头修改字段。
- 演示一条真实纵向路径，而不是分别演示三个孤立模块。

## 7. 分支和评审规则

建议分支命名：

```text
frontend/FE-02-benchmark-state
backend/BE-03-runtime-orchestrator
algorithm/ALG-03-output-evaluator
contract/CON-02-evaluation-v1
```

评审规则：

- 模块内部修改由对应负责人评审。
- Contract 变更必须由所有消费方评审。
- `tests/integration` 修改必须至少两人评审。
- 数据库迁移、Hidden 数据访问和生产状态转换必须由后端负责人评审。
- 分数语义、Mutation 规则和 Scenario Split 必须由算法负责人评审。

## 8. P1 不做的事项

在 M4 完成前不进入以下工作：

- 大规模扩展 Research、Support、Coding 职业。
- 同时接入 MCP Registry、Smithery、Composio 等多个来源。
- Marketplace、社区排名和多租户。
- 无人监管的自动生产发布。
- 大规模 UI 动画和内容编辑器。

这些工作不能替代 Browser 真实执行闭环。
