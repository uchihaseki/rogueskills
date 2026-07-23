# RogueSkills

RogueSkills 是一个可发现、评测、进化和版本化 Agent Skill 的实验平台。当前正式架构采用浏览器 JavaScript 前端与 Python 后端；Benchmark、Discovery、Genome 和 Evolution 的权威算法均在 Python 运行。

## 技术栈

- Python 3.12、FastAPI、Pydantic v2
- SQLAlchemy 2、Alembic；本地使用 SQLite，生产使用 PostgreSQL
- LangGraph Agent Runtime 扩展点、Celery/Redis 后台任务扩展点
- 原生 ES Modules 前端；只通过 HTTP API 提交命令和读取权威状态
- pytest、unittest、Node smoke tests

完整决策与模块边界见 `docs/python-architecture.md`。

真实 Case Runtime 的泛化设计与迁移路线见 `docs/generalized-real-case-runtime-evolution-design.md`。

第二个真实 Case Pack `release-readiness@1.0.0` 的输入、GitHub 数据边界和
Live/Replay 验收方法见 `docs/release-readiness-real-case.md`。

## 本地运行

推荐安装 `uv`，也可以直接使用 Python venv。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
npm start
```

访问：

- Evolution Run：http://127.0.0.1:5173
- Skill Discovery：http://127.0.0.1:5173/discovery.html
- OpenAPI：http://127.0.0.1:5173/api/docs

默认数据库为 `data/rogueskills.db`。真实 Skill Discovery 可以同时调用 GitHub、Brave、Tavily 和 Exa 的正式搜索 API；所有 Key 只配置在 Python 后端：

```bash
ROGUESKILLS_GITHUB_TOKEN=your_github_token \
ROGUESKILLS_BRAVE_API_KEY=your_brave_key \
ROGUESKILLS_TAVILY_API_KEY=your_tavily_key \
ROGUESKILLS_EXA_API_KEY=your_exa_key \
npm start
```

未配置的 Provider 会在 Discovery 页面显示 `NOT CONFIGURED` 并禁止选择。远程搜索失败时不会回退到本地种子结果。开发环境至少建议配置 GitHub 和一个 Web Search API；生产验收建议四个都配置。

SOP 转换使用 OpenAI-compatible LLM 做语义归一化：

```bash
ROGUESKILLS_LLM_BASE_URL=https://你的模型服务/v1 \
ROGUESKILLS_LLM_API_KEY=your_key \
ROGUESKILLS_LLM_MODEL=your_model \
npm start
```

模型没有工具权限；输出仍会经过 Contract、静态安全和许可证校验。

PostgreSQL 与 Redis 开发环境：

```bash
docker compose up -d postgres redis
ROGUESKILLS_DATABASE_URL=postgresql+psycopg://rogueskills:rogueskills-dev@127.0.0.1:5432/rogueskills npm start
```

数据库迁移：

```bash
.venv/bin/alembic upgrade head
```

## 测试

```bash
npm test                       # 前端/旧基线回归 + 无依赖 Python Domain 测试
npm run test:frontend
npm run test:python            # Python Domain、Repository 和 FastAPI 集成测试
```

`legacy/` 中保留冻结的 Node 原型，作用是迁移行为对拍。它不是生产入口，也不会由 FastAPI 静态服务暴露。

## 安全与权威边界

- 外部或人工创建的 Skill 强制进入 `quarantine`，客户端提交的 `status` 不生效。
- 晋升必须引用当前 Skill Version 的准入 Evaluation。
- Evolution Run 的每次命令必须携带 `expectedRevision`，过期操作会被拒绝。
- 前端不计算 Benchmark 结果，不执行 Discovery/Mutation/生命周期算法。
- GitHub Token 只发送到 `https://api.github.com/`。
- `/api/benchmark/scenario` 只返回非权威预览；正式结果由 `/api/runs` 状态机产生。
- Hidden Dataset、答案和详细诊断必须只存在于后端 Runtime Worker。

## 项目结构

```text
backend/rogueskills/
├── api/                 FastAPI 与版本化请求模型
├── application/         Skill、Run 命令服务
├── domain/              Genome、Discovery、Benchmark、Evolution 纯 Python 算法
├── agents/              LangGraph 编排与 Runtime/Evaluator/Planner Port
├── adapters/            GitHub、LLM、Browser、MCP 等外部适配器
├── contracts/           Runtime、Evaluation、Mutation Pydantic Contract
└── infrastructure/      SQLAlchemy、Alembic、Queue、Storage

src/
├── frontend/            浏览器 ES Modules，只调用 API
└── contracts/           跨语言 JSON Schema

legacy/                  冻结的 Node 迁移基线
tests/
├── python/              Python Domain/API/生命周期测试
├── frontend/            API-only 前端 smoke tests
└── backend/core/...     冻结 Node 基线测试
```

## 当前能力

- Skill Discovery、GitHub 快照、统一排序和风险扫描
- 金融股票分析场景：社区质量筛选、Qwen SOP 标准化、批量准入和金融 Evolution 地图
- Real Finance Case：SEC EDGAR + 市场价格快照、事实级引用评测、Genome Mutation 重跑和 Verified Replay
- Release Readiness Case：GitHub commit/check-runs/open-pulls 快照、三态报告、硬门槛、Mutation 和 Digest Artifact
- Generic Case MCP：Case Pack allowlist、Live/Replay、Report 分页、Skill Version pinning，兼容 Finance MCP 别名
- SOP/Runbook/Checklist → Skill Genome 1.0
- Quarantine Repository、不可变版本、来源快照和准入评测
- Initial Library 人工晋升与当前版本校验
- 服务端权威 Evolution Run、固定 Seed Replay、Mutation 和武器进化
- Victory Run → 不可变 AgentPreset v0.1、JSON 导出和 Digest 校验 Loader
- 确定性六用例 Benchmark
- LangGraph Runtime、Output Evaluator、Mutation Planner 的类型化扩展接口

传统 Evolution Run 生成的 AgentPreset 仍是能力数值模拟 Candidate；`/finance-demo` 的 Real Finance Case 已提供真实 LLM/SEC Runtime、证据评测、Genome JSON Patch、Verified Replay，并生成 `evaluationEvidence.mode=real-finance-case-v1`、`runtimeVerified=true` 的同 Contract AgentPreset。两种路径的证据模式会被显式区分。
