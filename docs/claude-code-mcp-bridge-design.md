# Claude Code MCP Bridge 接入方案

## 1. 结论

RogueSkills 应作为股票分析能力的唯一维护与执行中心，Claude Code 作为用户交互和结果呈现入口。

二者之间增加一个 MCP Bridge，把 RogueSkills 的真实 Case Runtime 注册为 Claude Code 可以调用的工具。Claude Code 不复制 SEC 抓取、财务计算、证据评测或 Skill 自进化逻辑，而是在工作过程中调用 RogueSkills，拿到结构化结果后进行解释和排版。

目标链路：

```text
用户自然语言
    ↓
Claude Code
    ↓ MCP tool call
Claude Code MCP Bridge
    ↓ HTTP API
RogueSkills Finance Case Runtime
    ├─ SEC EDGAR / 行情 Provider
    ├─ Dataset 与确定性财务计算
    ├─ Qwen Structured Analyst
    ├─ Evidence Evaluator
    ├─ Genome Mutation / Skill Version
    └─ Runtime AgentPreset
    ↓
结构化 Case / Report / Evaluation
    ↓
Claude Code 最终回答
```

本方案基于已经真实跑通的 AAPL Case：

- Case：`finance-case-6266b782a74c416ea985aa35031aee9d`
- Base Skill Version：`sop-9e7795@2`
- `runtimeVerified=true`
- Final Score：`100.0`
- Source Count：`3`
- Fact Count：`26`
- Runtime AgentPreset：`preset-9695e25378e49ce5489c`
- Preset Digest：`sha256:097a6d1570a0632a0b036c5db45f8e55d026461fae384e4a07a83c8a875d2f0d`

## 2. 当前状态与缺口

当前 RogueSkills 已支持将 AgentPreset 导出为 Claude Code 项目文件，导出内容包括：

```text
CLAUDE.md
.claude/skills/<skill-name>/SKILL.md
.rogueskills/<preset-id>/preset.json
.rogueskills/<preset-id>/runtime-config.json
.rogueskills/<preset-id>/export-manifest.json
```

当前导出包可以让 Claude Code：

- 了解何时使用金融分析 Skill；
- 遵循工作步骤、事实引用和安全约束；
- 读取 Preset Digest、运行预算和验证边界；
- 在项目内保存一份可审计的配置快照。

但当前导出包还不能让 Claude Code 自动重新执行 RogueSkills Runtime。当前 Preset 的 `tools` 为空，且仓库内还没有 Claude Code MCP Server。也就是说，当前能力是“把规范交给 Claude”，不是“把 RogueSkills 运行时接入 Claude”。

两种模式的区别：

| 模式 | Claude Code 得到什么 | 是否自动跑真实 Case | 适用场景 |
| --- | --- | --- | --- |
| 静态 Skill 导出 | `CLAUDE.md`、`SKILL.md`、Preset 快照 | 否 | 规范试用、离线阅读 |
| MCP Bridge | 可调用的 `analyze_stock` 等工具 | 是 | 真实 Demo、团队使用、生产接入 |

## 3. 目标与非目标

### 3.1 目标

1. RogueSkills 继续集中维护 Skill、Skill Version、Case Pack、Evaluator、Mutation 和 Provider 配置。
2. Claude Code 能在用户提出股票分析任务时主动调用 RogueSkills。
3. 真实数据、来源摘要、事实、派生指标、评测和自进化结果都来自 RogueSkills Runtime。
4. Claude 只能解释已返回的结构化结果，不得把未验证信息包装成已验证结论。
5. 每次调用都能追溯到 `caseId`、`skillVersionId`、`runtimeVerified` 和 Artifact Digest。
6. 保留 Live、Verified Replay、失败证据和 rejected Mutation 语义。

### 3.2 非目标

- 不在 Claude Code 中复制金融计算和评测算法。
- 不让 Claude 直接访问 SEC、行情 Provider 或 Qwen 密钥。
- 不让 Claude 直接修改 Skill Genome、Skill Version 或数据库。
- 不把 `runtimeVerified=true` 解释为投资建议或生产授权。
- 不用 MCP Bridge 绕过 RogueSkills 现有的硬门槛。

## 4. 组件职责

| 组件 | 主要职责 | 不负责的事情 |
| --- | --- | --- |
| `CLAUDE.md` | 项目级触发规则、结果表达方式 | 真实数据抓取 |
| `.claude/skills/.../SKILL.md` | 工作流、约束、输出结构 | 评测和版本持久化 |
| MCP Bridge | MCP 工具注册、参数校验、API 转发、结果裁剪 | 财务事实计算 |
| RogueSkills API | Case、Report、Evaluation、Preset API | Claude 的自然语言表达 |
| Finance Runtime | Provider、Dataset、LLM、Evaluator、Mutation | Claude Code 会话管理 |
| Claude Code | 理解用户意图、调用工具、组织答案 | 绕过硬门槛或自行宣称验证 |

MCP Bridge 不是另一个分析 Agent。它是一个受限的适配器：将 Claude 的工具调用翻译成 RogueSkills API 调用，再将结果转换成 Claude 易于消费的结构化内容。

## 5. 目标接入方式

### 5.1 本地 Demo：stdio Bridge

本地 Demo 推荐使用 stdio MCP Server。Claude Code 启动 Bridge 子进程，Bridge 通过 HTTP 访问本机的 RogueSkills 服务。

示意配置：

```json
{
  "mcpServers": {
    "rogueskills-finance": {
      "command": "/Users/shuo/workspace/code/rogueskills/.venv/bin/python",
      "args": ["-m", "rogueskills.mcp.finance_bridge"],
      "env": {
        "PYTHONPATH": "/Users/shuo/workspace/code/rogueskills/backend",
        "ROGUESKILLS_API_BASE_URL": "http://127.0.0.1:5173",
        "ROGUESKILLS_DEFAULT_FINANCE_SKILL_ID": "sop-9e7795"
      }
    }
  }
}
```

该配置由当前仓库的 `rogueskills-finance-mcp` 入口提供；通用 Case 项目使用
`rogueskills-case-mcp`，两者都通过 HTTP 调用 RogueSkills API，不携带 Provider Key。

### 5.2 团队/生产：远程 Bridge

团队环境可以将 Bridge 部署成受认证的远程 MCP 服务：

```text
Claude Code → HTTPS MCP Endpoint → RogueSkills API → Case Runtime
```

远程模式应增加：

- OAuth 或短期访问令牌；
- workspace/project 级权限；
- Case 和 Skill Version 的审计身份；
- 请求频率和预算限制；
- 服务端日志与 Trace ID。

不建议将 SEC、行情或 LLM Key 放入 `.mcp.json`。这些 Key 只能配置在 RogueSkills 后端。

## 6. MCP 工具设计

Bridge 的工具应保持少而稳定。工具不应暴露数据库操作，也不应允许任意 URL、任意 SQL 或任意 Genome Patch。

### 6.1 `finance_preflight`

检查 Runtime 是否准备好。

输入：

```json
{}
```

输出：

```json
{
  "ready": true,
  "runtime": "real-finance-case-v1",
  "analyst": {
    "provider": "OpenAI-compatible",
    "model": "qwen-...",
    "configured": true
  },
  "sources": [
    {"id": "sec-edgar", "state": "checked_on_run"},
    {"id": "market-price", "state": "checked_on_run"}
  ]
}
```

Claude 在执行 Live Case 前可以调用该工具；如果 `ready=false`，应报告配置问题，而不是假装完成分析。

### 6.2 `analyze_stock`

执行完整的金融 Case。该工具是主要入口。

建议输入：

```json
{
  "ticker": "AAPL",
  "asOfDate": "2026-07-21",
  "mode": "live",
  "autoEvolve": true,
  "skillId": "sop-9e7795"
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `ticker` | 是 | 股票代码，由 Bridge 做格式校验 |
| `asOfDate` | 是 | 分析截止日期，不能默认为当前时间而不告知用户 |
| `mode` | 是 | `live` 或 `verified_replay` |
| `replayCaseId` | Replay 必填 | 只能引用已经保存的 Live Case |
| `autoEvolve` | 建议显式 | 是否允许 Runtime 尝试 Mutation |
| `skillId` | 可配置默认值 | Initial Finance Skill；不能接受任意非金融 Skill |

Bridge 调用当前 API：

```http
POST /api/finance/cases
```

建议工具返回精简摘要，而不是一次性把所有原始快照塞进上下文：

```json
{
  "caseId": "finance-case-...",
  "ticker": "AAPL",
  "asOfDate": "2026-07-21",
  "status": "succeeded",
  "runtimeVerified": true,
  "baseSkillVersionId": "sop-9e7795@2",
  "evolvedSkillVersionId": null,
  "finalScore": 100.0,
  "sourceCount": 3,
  "factCount": 26,
  "reportTool": "get_finance_report",
  "caseTool": "get_finance_case"
}
```

如果工具返回 `status=failed` 或 `runtimeVerified=false`，Claude 必须保留失败原因和验证边界。

### 6.3 `get_finance_case`

获取 Case 聚合状态，包括：

- `status`、`phase`、`mode`；
- `baseSkillVersionId`、`evolvedSkillVersionId`；
- `mutation` 和 `comparison`；
- `finalEvaluation`；
- `runtimeVerified`；
- `financeEvolutionRunId`；
- `agentPreset` 摘要。

输入：

```json
{
  "caseId": "finance-case-..."
}
```

对应：

```http
GET /api/finance/cases/{caseId}
```

### 6.4 `get_finance_report`

获取某个阶段的结构化报告。

输入：

```json
{
  "caseId": "finance-case-...",
  "stage": "final"
}
```

`stage` 只能是：

```text
baseline | evolved | final
```

对应：

```http
GET /api/finance/cases/{caseId}/report?stage=final
```

报告的权威字段包括：

```text
company
sources
filings
facts
derivedMetrics
valuationScenarios
narrative
warnings
```

Claude 应优先使用该工具的 `final` 报告；只有在解释自进化过程时才额外读取 `baseline` 和 `evolved`。

### 6.5 `get_verified_agent_preset`

获取通过真实 Case 生成的 Runtime AgentPreset。

输入：

```json
{
  "caseId": "finance-case-..."
}
```

对应：

```http
GET /api/finance/cases/{caseId}/agent-preset
```

### 6.6 通用 Case 工具

在至少两个真实 Case Pack 存在后，Bridge 同时提供通用工具：

```text
list_case_packs
get_case_pack
case_preflight
run_case
get_case_run
get_case_report
get_case_evaluation
```

通用输入固定 `casePackId`、可选 `casePackVersion`、`skillId`、可选
`skillVersionId`、行业输入 `input`、`mode`、`replayCaseId` 和 `autoEvolve`。
`input` 只允许 JSON 对象，限制 64 KB，并拒绝 token、cookie、authorization、API key
等敏感字段。Case Pack 的具体字段仍由 RogueSkills 服务端 Contract 校验。

Bridge 默认只允许 `finance-stock-analysis`；项目必须通过
`ROGUESKILLS_ALLOWED_CASE_PACKS` 显式增加 `release-readiness` 或其他 Pack。未批准
Pack 会在 Bridge 访问 HTTP API 前返回 `CASE_PACK_NOT_APPROVED`。

`skillVersionId` 可用于复现历史版本。历史版本本身必须曾处于 `initial`；若它不是当前
版本，API 允许执行和 Replay，但拒绝 `autoEvolve=true`，防止旧版本进化覆盖当前
Skill。项目可用 `ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS` JSON 映射为每个 Pack
设置默认 pin，显式工具参数优先于默认值。

通用 Report 使用 `factOffset/factLimit` 分页，并移除 raw snapshots；超出上下文限制时
按可选顶层 section 裁剪，同时返回 `window.omittedSections` 和 `window.truncated`。

返回中至少要保留：

```text
preset.id
preset.digest
preset.status
preset.primarySkill.skillVersionId
preset.evaluationEvidence.runtimeVerified
preset.evaluationEvidence.benchmarkIds
```

## 7. 典型执行流程

### 7.1 用户请求

```text
用真实数据分析 AAPL，截至 2026-07-21。
需要跑证据评测，如果基线失败可以自动进化，但不要给出保证收益或直接买卖指令。
```

### 7.2 Claude 调用顺序

```text
1. finance_preflight
2. analyze_stock(mode=live, autoEvolve=true)
3. get_finance_case(caseId)
4. get_finance_report(caseId, stage=final)
5. 必要时 get_finance_report(baseline/evolved)
```

### 7.3 Claude 最终回答要求

最终回答应至少包含：

1. Case ID、分析截止日期、Skill Version；
2. `runtimeVerified`、总分、硬门槛状态；
3. 主要事实和期间/单位；
4. 派生指标及公式来源；
5. Bear/Base/Bull 估值情景和关键假设；
6. 来源清单、抓取时间和警告；
7. 风险、数据缺口和下一次跟踪事件；
8. 明确的投资建议边界。

Claude 不应自行补充报告里没有的市场一致预期，也不应把管理层预测写成已经发生的事实。

## 8. Skill 与版本策略

### 8.1 静态快照模式

导出的 ZIP 包包含固定的 `preset.json`、`runtime-config.json` 和 `SKILL.md`。这种模式适合：

- 审核一个确定版本；
- 离线复现；
- 对外分发候选 Skill。

缺点是 RogueSkills 中的 Skill 更新后，需要重新导出和重新安装包。

### 8.2 在线连接模式

Bridge 只保存 `skillId` 或 `presetId`，每次调用从 RogueSkills 解析当前允许使用的版本。这种模式适合团队使用，但必须防止“无意漂移”。

推荐规则：

- 每次 Case 都记录最终解析出的 `baseSkillVersionId`；
- 默认使用人工批准的 Current Version；
- `evolvedSkillVersionId` 只有严格改善并通过硬门槛时才进入结果；
- Bridge 不接受 Claude 直接传入任意 Genome Patch；
- 生产任务可以锁定 `skillVersionId`，需要升级时显式批准。

### 8.3 更新后的生效方式

```text
RogueSkills 修改 Skill
    ↓
真实 Case / Evaluation 验证
    ↓
Skill Version 晋升或保持 rejected
    ↓
在线 Bridge 下一次调用解析批准版本
```

如果使用静态导出，则在最后一步改为重新导出 Claude Code 包。

## 9. 安全边界

### 9.1 凭证

- SEC User-Agent、Tavily/Exa/GitHub Key、LLM Key 只存在 RogueSkills 后端。
- `.mcp.json` 只包含 Bridge 地址、非敏感配置和必要的项目标识。
- Claude 的上下文中不应出现 Provider Secret。

### 9.2 工具权限

Bridge 初版只允许：

- 读取 Runtime preflight；
- 创建 Live 或 Verified Replay Case；
- 查询 Case、Report、Evaluation 和 AgentPreset。

Bridge 不开放：

- 任意 HTTP 请求；
- 任意 SQL；
- 任意文件读写；
- 任意 Skill Genome Patch；
- 直接发布或删除 Skill Version。

### 9.3 状态修改

`autoEvolve=true` 可能在严格条件满足时持久化新的 Skill Version，因此建议：

- Claude 只有在用户明确要求“允许自进化”时才传 `true`；
- 默认可使用 `autoEvolve=false` 先做基线分析；
- Mutation 的接受条件仍由 RogueSkills 服务端决定，不能由 Claude 覆盖；
- 所有 rejected Mutation 也要保留审计记录。

### 9.4 外部内容

SEC、行情、网页和模型输出均视为不可信数据。Bridge 不把外部文本拼接成新的系统指令；RogueSkills 的 Dataset、Contract 和 Evaluator 仍是权威边界。

## 10. 错误与可观测性

Bridge 应将错误转换成稳定的工具错误类型：

| 错误 | Claude 应如何处理 |
| --- | --- |
| `FINANCE_ANALYST_NOT_CONFIGURED` | 告知模型未配置，不宣称完成分析 |
| Provider timeout | 显示 Provider、是否可重试和已保存的 partial evidence |
| `FINANCE_CASE_NOT_FOUND` | 要求重新提供 Case ID |
| `VERIFIED_REPLAY_NOT_FOUND` | 不能把 Replay 当作 Live 运行 |
| schema/evaluation failure | 返回失败阶段和具体硬门槛 |
| Bridge timeout | 保留 request ID，允许查询 Case 状态 |

每次调用至少记录：

```text
requestId
claudeSessionId（如可用）
toolName
caseId
skillVersionId
provider calls
runtime phase
latency
status
```

长耗时 Case 不应依赖单个同步 MCP 请求。P1 应改为：创建 Case 后返回 `caseId`，Claude 通过 `get_finance_case` 轮询，或使用事件订阅获取阶段变化。

## 11. 分阶段交付

### P0：本地可运行 Bridge

- 新增 `backend/rogueskills/mcp/finance_bridge.py`；
- 使用 stdio 暴露 `finance_preflight`、`analyze_stock`、`get_finance_case`、`get_finance_report`；
- Bridge 仅调用现有 `/api/finance/cases*` API；
- 增加输入、错误、权限和结果裁剪测试；
- 手动用 AAPL Live Case 完成一次 Claude Code Demo。

### P1：导出器集成

- Claude Code 导出包增加 `.mcp.json`；
- `CLAUDE.md` 增加“股票分析必须优先调用 RogueSkills 工具”的规则；
- Preset Digest 和 Skill Version 自动写入 Bridge 配置；
- 对已有 `CLAUDE.md` 提供 merge 说明，避免解压覆盖用户文件。

### P2：异步 Case

- `POST /api/finance/cases` 或通用 `/api/case-runs` 改为 queued；
- Bridge 返回 `caseId` 和状态查询提示；
- Claude 轮询 `get_finance_case`，直到 `completed` 或失败；
- UI 和 MCP 共用同一个 Case 状态机。

### P3：通用 Case Pack

- Bridge 工具已经从 `finance_*` 抽象为 Case Pack 查询；
- Finance 和 Release Readiness 均可以通过 `run_case` 选择；
- 第二个真实 Case 已验证 Bridge 不含行业分支；
- 通过 `casePackId` 选择分析能力，同时保留专用 Finance 工具别名。

### P4：团队与生产

- 远程 MCP、认证和 workspace 隔离；
- skillVersion pinning、人工审批和回滚；
- 统一审计、Trace、用量和预算；
- 仅将 `runtimeVerified` 与完整 Evidence 一起展示，不将其转成交易授权。

## 12. 验收标准

### 功能验收

- Claude Code 能发现并调用 `finance_preflight`；
- 输入 AAPL 后，Bridge 创建真实 `live` Case；
- RogueSkills 真实访问 SEC 和行情 Provider；
- Claude 能查询并展示 `finalReport`；
- 结果包含 `caseId`、`skillVersionId`、`runtimeVerified`、score 和来源；
- `verified_replay` 不访问外部网络并明确标记；
- baseline 通过时不生成冗余 Skill Version；
- Mutation 失败时 Claude 能看到 rejected 状态和失败 Case。

### 安全验收

- Claude 不能提供任意 URL 让 Bridge 代为抓取；
- Claude 不能直接提交 Genome Patch；
- `.mcp.json` 和 Claude 上下文不包含 Provider Key；
- 未通过硬门槛的结果不能被 Bridge 标记为 verified；
- Bridge 超时后可以通过 `caseId` 查询最终状态。

### Demo 验收命令

目标体验：

```text
用户：用真实数据分析 AAPL，截至 2026-07-21，允许自动进化。

Claude：
1. 调用 finance_preflight
2. 调用 analyze_stock
3. 调用 get_finance_report
4. 返回带 Case ID、来源、评测、估值情景和风险边界的 Markdown 报告
```

Demo 的权威结果仍必须能在 RogueSkills API 中复查：

```text
GET /api/finance/cases/{caseId}
GET /api/finance/cases/{caseId}/report?stage=final
GET /api/finance/cases/{caseId}/agent-preset
```

## 13. 建议的代码结构

```text
backend/rogueskills/mcp/
├── __init__.py
├── finance_bridge.py       # stdio MCP Server
├── api_client.py           # RogueSkills API client
├── contracts.py            # MCP 输入输出模型
└── errors.py               # 稳定错误码映射

tests/python/
└── test_finance_mcp_bridge.py

export package/
├── .mcp.json
├── CLAUDE.md
├── .claude/skills/.../SKILL.md
└── .rogueskills/<preset-id>/...
```

Bridge 应通过 HTTP Client 调用 RogueSkills API，而不是直接 import `FinanceCaseService`。这样 Claude Code 连接的是和 Web UI、脚本相同的正式边界，避免出现一套 API 行为和一套内部调用行为。

## 14. 最终建议

短期可以继续使用现有 `claude-code` 静态导出包验证 Skill 文案和工作流；正式 Demo 应优先实现本地 stdio MCP Bridge，并让 Bridge 复用现有 `/api/finance/cases` 接口。

推荐的最小闭环是：

```text
RogueSkills 服务启动
    ↓
Claude Code 加载 .mcp.json
    ↓
Claude 调用 analyze_stock
    ↓
RogueSkills 跑真实金融 Case
    ↓
Claude 查询 final report
    ↓
用户得到带证据和验证状态的股票分析报告
```

这样维护责任清晰：RogueSkills 维护能力和质量，Claude Code 负责交互和表达；股票分析逻辑不会分散到多个客户端，也不会因为 Claude Code 换项目而失去来源、评测和版本审计。

## 15. 现有实现参考

- 真实金融 Case Demo：`docs/finance-real-case-demo.md`
- 通用 Real Case Runtime：`docs/generalized-real-case-runtime-evolution-design.md`
- Claude Code 导出器：`backend/rogueskills/adapters/agent_preset_exporter.py`
- AgentPreset 导出 API：`GET /api/agent-presets/{presetId}/export/{target}`
- Finance Case API：`POST /api/finance/cases`
- Final Report API：`GET /api/finance/cases/{caseId}/report?stage=final`
