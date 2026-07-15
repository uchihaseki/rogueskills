# RogueSkills P0 Architecture（Implemented v0.1）

## 1. P0 交付目标

P0 将原先两个独立的浏览器原型连接成一条可持久化闭环：

```text
Skill Search / SOP Material
↓
Skill Genome 1.0
↓
Quarantine Repository
↓
Admission Benchmark
↓
Human Promotion
↓
Initial Skill Library
↓
Evolution Run
↓
Scenario Benchmark Cases
```

## 2. 已实现组件

### Skill Genome Schema

- JSON Schema：`schemas/skill-genome.schema.json`
- Runtime Validator：`src/skill-genome.js`
- 当前版本：`1.0.0`
- 包含 Prompt、Workflow、Input、Output、Constraints、Tools、Capabilities、Test Cases、Evaluation、Provenance 和 Risk

### SQLite Skill Repository

默认数据库：`data/rogueskills.db`

数据表：

- `skills`：Skill 身份和生命周期
- `skill_versions`：不可变 Genome 版本和父版本
- `source_snapshots`：来源、Revision、Artifact Path、Fingerprint 和内容快照
- `benchmark_runs`：评测套件、Split、分数、用例和通过状态

生命周期：

```text
quarantine → initial → evolving → candidate → production
```

P0 界面只开放 `quarantine → initial`。

### Benchmark Runner

Initial Library 准入套件 `library-admission-v1` 包含：

- Schema
- Provenance
- Workflow
- Constraints
- Test Cases
- License 硬门槛
- Static Safety 硬门槛
- Capability Evidence

Evolution Run 场景套件 `scenario-runtime-v1` 每次执行：

- Nominal business case
- Standard acceptance case
- Degraded environment
- Cost and latency SLA
- Output contract
- Security boundary

评估已经没有随机波动；Seed 只决定地图和节点难度。

### Search Gateway

入口：`server.mjs`

能力：

- 同源静态服务与 JSON API
- GitHub Token 只保存在服务端环境变量
- 搜索结果 TTL 缓存
- 2 MB 请求体限制
- SQLite Repository 初始化和 Seed Skill
- 限制可访问的静态文件目录

## 3. API

| Method | Path | 作用 |
|---|---|---|
| GET | `/api/health` | Gateway 状态 |
| POST | `/api/discovery/search` | 多来源搜索 |
| POST | `/api/discovery/import` | 拉取并保存候选 |
| POST | `/api/materials/convert` | SOP 转 Genome |
| GET | `/api/skills` | 查询 Repository |
| POST | `/api/skills` | 保存 Genome |
| GET | `/api/skills/:id` | Skill、版本、快照、评估详情 |
| DELETE | `/api/skills/:id` | 删除 Quarantine Skill |
| POST | `/api/skills/:id/benchmark` | 执行准入 Benchmark |
| POST | `/api/skills/:id/promote` | 人工晋升 Initial Library |
| GET | `/api/skills/:id/evaluations` | 评估历史 |
| GET | `/api/library/initial` | Evolution Run 可选 Skill |
| POST | `/api/benchmark/scenario` | 执行场景 Benchmark |

## 4. 运行

要求 Node.js 22.5+，因为 Repository 使用 Node 内置 SQLite。

```bash
npm start
```

可选环境变量：

```text
PORT=4173
HOST=127.0.0.1
ROGUESKILLS_DB=/absolute/path/rogueskills.db
GITHUB_TOKEN=github_token
```

## 5. 安全边界

- 外部仓库内容不执行
- GitHub Token 不进入浏览器
- 只有 Quarantine Skill 可以直接删除
- 未知 License 不能晋升
- High Risk 不能晋升
- 必须有通过的 `library-admission-v1` 记录
- 晋升操作必须由用户点击触发
- 数据库和 WAL 文件默认不进入版本控制

## 6. “真实 Benchmark”的当前含义

P0 Benchmark 是实际执行、逐用例、可解释、可落库的确定性评测，不再是随机分数模拟。

它目前根据 Skill Genome 的 Capability Evidence 和业务场景要求执行，不会调用外部 LLM 或真实浏览器工具。下一阶段可在保持相同 `EvaluationResult` 协议的前提下增加 LLM/Tool Runtime Adapter。

## 7. P0 之后

- 真实 LLM / Tool Runtime Adapter
- 按 Skill Category 生成领域地图
- Validation / Hidden Test 数据集管理
- Mutation 生成真实 Genome Diff
- Candidate、A/B Test 和 Canary 发布
