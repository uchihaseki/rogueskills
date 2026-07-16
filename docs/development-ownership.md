# RogueSkills 三人协作与模块归属

> v0.2 更新：后端、算法和 Agent Runtime 已迁入 `backend/rogueskills/`；浏览器不再导入 Core。最新依赖方向和框架决策见 `python-architecture.md`。

## 1. 目的

项目进入 P1 后由前端、后端和算法三位负责人并行开发。模块按职责而不是页面拆分，跨模块只通过版本化契约协作。

```text
Frontend：交互、展示、客户端状态
Backend：API、持久化、安全、生命周期、执行编排
Core：评测、发现、进化和可复现的纯领域逻辑
Contracts：三方共同遵守的数据协议
```

核心约束：

- 前端不计算 Benchmark 分数，不直接决定 Skill 生命周期。
- 后端不在 API 或 Repository 中复制算法公式。
- 算法不访问数据库、网络、DOM、环境变量或生产凭证。
- 外部系统的副作用由后端 Adapter 封装，算法只接收和返回结构化数据。
- `src/contracts` 的破坏性变更必须由三方共同确认并升级版本。

## 2. 目录和依赖方向

```text
src/
├── frontend/                  # 前端负责人
│   ├── app.js                 # Evolution Run 工作台
│   ├── discovery-app.js       # Discovery 工作台
│   └── api-client.js          # API 调用与错误适配
├── backend/                   # 后端负责人
│   ├── api/router.mjs         # HTTP API 编排
│   ├── connectors/
│   │   └── discovery-gateway.mjs
│   └── repository/
│       └── skill-repository.mjs
├── core/                      # 算法负责人
│   ├── benchmark/runner.js
│   ├── discovery/
│   │   ├── engine.js
│   │   └── catalog.js
│   ├── evolution/
│   │   ├── engine.js
│   │   └── catalog.js
│   ├── genome/
│   │   ├── skill-genome.js
│   │   └── seed-skills.js
│   └── shared/random.js
└── contracts/                 # 三方共享，按契约变更流程维护
    └── skill-genome.schema.json
```

允许的依赖方向：

```text
Frontend ──HTTP──> Backend
Frontend ────────> Core（仅限浏览器内的纯 Run 逻辑）
Backend ─────────> Core
Frontend/Backend/Core ──> Contracts
```

禁止的依赖方向：

- Core 不能导入 Frontend 或 Backend。
- Backend 不能导入 Frontend。
- Frontend 不能导入 Backend 源码，只能调用 HTTP API。
- 浏览器静态服务不能暴露 `src/backend`。

## 3. 前端负责人

### 所有模块

- Evolution Run 页面、Discovery 页面和后续 Candidate 审核页面。
- 用户操作、加载态、空状态、错误态和重试交互。
- Initial Library、Benchmark、Trace、Genome Diff 和 Replay 的展示。
- API Client、响应适配和前端缓存。
- 浏览器 E2E 与前端 smoke test。

### 交付边界

前端向后端提交操作意图，例如：

- 创建隔离候选。
- 请求执行 Benchmark。
- 请求晋升 Initial。
- 请求保存 Candidate。

前端不能通过提交 `status` 字段直接改变 Skill 生命周期，也不能自行计算最终分数。

### 需要评审前端改动的情况

- API 字段或错误码发生变化：后端负责人必须评审。
- 前端需要解释算法分数、Mutation 原因或 Diff：算法负责人必须评审。

## 4. 后端负责人

### 所有模块

- HTTP API、输入校验、错误协议和服务端配置。
- SQLite Repository、迁移、版本谱系和事务。
- Skill 生命周期命令与权限边界。
- Runtime Orchestrator、LLM/Tool Adapter 和执行超时。
- GitHub 等外部连接器的网络、凭证、缓存和限流。
- Scenario Pack 存储、Validation/Hidden Test 隔离。
- Execution Trace、成本、延迟和 EvaluationResult 落库。
- Candidate、A/B Test、Canary 和 Runtime Feedback 服务。
- 后端集成测试、迁移测试和服务健康检查。

### 交付边界

后端负责保证状态真实：

- 外部新建 Skill 必须进入 `quarantine`。
- 晋升使用的 Evaluation 必须属于同一个 Skill 的当前版本。
- Hidden Test 内容不能返回前端或进入 Mutation 上下文。
- Runtime Adapter 返回原始执行事实，评分由 Core Evaluator 完成。

### 需要评审后端改动的情况

- 新增或修改 API：前端负责人必须评审。
- 改变 Runtime 输入、Trace 或 Evaluation 数据：算法负责人必须评审。

## 5. 算法负责人

### 所有模块

- Skill Genome 语义、能力画像和验证规则。
- Discovery 查询解析、归一化、排序、去重和静态风险规则。
- Scenario Pack、难度模型、Dataset Split 规则。
- Benchmark Case、Output Evaluator 和聚合评分。
- Mutation 召回、排序、代价和可解释原因。
- Mutation 到 Genome Patch、武器进化和组合规则。
- Seed 地图、Run 状态机和 Replay 可复现规则。
- Golden Cases、算法回归测试和算法版本号。

### 交付边界

Core 模块的目标形态是：

```text
输入 JSON + 固定版本配置
→ 纯计算
→ 输出 JSON
```

Core 不直接调用 GitHub、LLM、Browser、SQLite 或 DOM。需要执行能力时，通过后端实现的 Runtime Adapter 获取 Trace 和 Output。

现有 Core 中依赖当前时间的 Freshness、CapturedAt 和 Run ID 将在 P1 契约冻结时改为显式 Clock 输入，避免时间成为隐藏依赖。

### 需要评审算法改动的情况

- 改变 Evaluation、Mutation 或 Scenario 输出：前端和后端负责人必须评审。
- 新增工具需求或执行环境：后端负责人必须评审。

## 6. 共享契约归属

| 契约 | 主负责人 | 必须评审 |
|---|---|---|
| Skill Genome | 算法 | 前端、后端 |
| API Request/Response | 后端 | 前端 |
| Evaluation Request/Result | 算法 | 前端、后端 |
| Runtime Adapter/Trace | 后端 | 算法 |
| Mutation Proposal/Patch | 算法 | 前端、后端 |
| Lifecycle Command | 后端 | 前端、算法 |
| Scenario Pack/Split | 算法 | 后端 |

具体字段见 `docs/contracts-v1.md`。

## 7. 测试归属

```text
tests/frontend/      前端组件与交互 smoke test
tests/backend/       API、Repository、迁移和安全边界
tests/core/          算法纯函数、Golden Cases 和可复现性
tests/integration/   三方共同维护的纵向闭环
```

测试失败由拥有失败模块的人首先处理；`tests/integration` 失败由最近改变契约的一方牵头，三方共同确认。

## 8. 跨模块变更流程

1. 提交契约变更说明，写清输入、输出、错误和兼容策略。
2. 消费方在开发前确认字段足以完成自己的任务。
3. 提供方先提交 Schema、Fixture 和失败样例。
4. 消费方基于 Fixture 并行实现。
5. 集成测试通过后才把契约状态标记为 Stable。

禁止在同一个 PR 中无说明地同时修改三层内部实现。确实需要纵向修改时，应按 `Contracts → Core/Backend → Frontend → Integration Test` 的顺序组织提交。

## 9. 统一完成标准

一个任务只有同时满足以下条件才算完成：

- 输入、输出和错误情况有明确契约。
- 正常路径和至少一个失败路径有自动测试。
- 未破坏现有 P0 闭环和固定 Seed 可复现性。
- 涉及数据结构时包含版本或迁移策略。
- 消费方完成一次集成确认。
- 文档、Fixture 和实现处于同一个变更中。
