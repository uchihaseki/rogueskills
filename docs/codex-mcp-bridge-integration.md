# Codex MCP 接入与验证方案

> 状态：实现完成；Codex Host 端真实 Replay 已通过。

## 1. 结论

Codex 与 Claude Code 共用 RogueSkills Generic Case MCP Bridge：

```text
Codex / Claude Code
        ↓ stdio MCP
rogueskills.mcp.case_bridge
        ↓ HTTP
RogueSkills Case API
        ↓
Case Pack → Skill Version → Runtime → Evaluation → Artifact
```

不增加 Codex 专用业务协议，也不把 Finance 或 Release Readiness 的分析逻辑复制到客户端。
Host 差异只存在于配置入口：

- Claude Code：项目 `.mcp.json`；
- Codex：项目 `.codex/config.toml`，或 `codex mcp add`；
- 两者使用同一组 `list_case_packs`、`run_case`、`get_case_report` 等工具。

## 2. 已实现内容

### 2.1 Codex Demo 项目

`examples/codex-case-demo` 包含：

- `.codex/config.toml`：Generic Case MCP stdio 配置；
- `AGENTS.md`：Case 调用顺序、验证边界和输出要求；
- `README.md`：交互式与非交互式运行说明。

项目配置只允许：

```text
finance-stock-analysis
release-readiness
```

并固定默认 Skill Version：

```text
finance-stock-analysis → sop-9e7795@2
release-readiness      → release-readiness-base@1
```

### 2.2 AgentPreset Codex 导出

`GET /api/agent-presets/{presetId}/export/codex` 继续导出：

- `AGENTS.md`；
- `.agents/skills/<skill>/SKILL.md`；
- `.rogueskills/<preset>/preset.json`；
- `.rogueskills/<preset>/runtime-config.json`；
- Digest Manifest。

对于可识别的 Finance Runtime Preset，新增 `ROGUESKILLS-CODEX-INSTALL.md`，其中包含：

- 可审阅的 `codex mcp add rogueskills-cases` 命令；
- Case Pack allowlist；
- Skill Version pin；
- `codex mcp get/list` 验证命令；
- 不覆盖已有 `.codex/config.toml` 的合并规则；
- Provider/LLM Key 不进入 Codex 配置的安全边界。

导出器不直接生成并覆盖 `.codex/config.toml`。这是有意设计：项目通常已经有 model、sandbox、
hooks 或其他 MCP 配置，静默覆盖会破坏现有 Codex 工作流。

### 2.3 Host E2E Runner

完整 runner：

```bash
zsh artifacts/release-e2e-20260723/run_codex_mcp_release_demo.sh
```

它依次执行：

1. 使用 `release-live.db` 启动正式 RogueSkills API；
2. 通过 `codex mcp get --json` 确认项目 MCP 配置被 Codex 加载；
3. 运行非交互式 `codex exec`；
4. 让 Codex 调用 Generic Case MCP 工具完成 Release Readiness Verified Replay；
5. 强制最终结果符合 JSON Schema；
6. 断言 score、hard gates、source/fact/check counts 和 `runtimeVerified`；
7. 保存 Codex JSONL 事件与最终结构化结果。

Runner 保留用户的 model-provider 配置（包括本地 Responses proxy），只通过
`--disable apps/plugins/remote_plugin` 关闭个人插件和远程插件；项目 `.codex/config.toml`
额外禁用 `node_repl`，仍负责加载 `rogueskills-cases`。

项目只 allowlist 七个 Generic Case 工具，并将 `rogueskills-cases` 自身的
`default_tools_approval_mode` 设为 `approve`。该批准不扩散到 shell、其他 MCP 或个人插件；
它用于避免非交互 `codex exec` 把 MCP 确认请求自动记成 `user cancelled`。

Verified Replay 使用真实 Live Case 持久化的 GitHub Source Bundle，不使用 fixture、
`MockTransport` 或伪造数据，同时不会在回归时再次请求 GitHub。

## 3. Codex 配置方式

### 3.1 项目级配置

适合随项目审阅和版本控制：

```toml
[mcp_servers.rogueskills-cases]
command = "/absolute/path/to/rogueskills/.venv/bin/python"
args = ["-m", "rogueskills.mcp.case_bridge"]

[mcp_servers.rogueskills-cases.env]
PYTHONPATH = "/absolute/path/to/rogueskills/backend"
ROGUESKILLS_API_BASE_URL = "http://127.0.0.1:5173"
ROGUESKILLS_ALLOWED_CASE_PACKS = "finance-stock-analysis,release-readiness"
ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS = '{"finance-stock-analysis":"sop-9e7795@2","release-readiness":"release-readiness-base@1"}'
```

Demo 内使用仓库相对路径，便于直接运行。

### 3.2 CLI 注册

适合已安装 `rogueskills-case-mcp` console entrypoint 的本机：

```bash
codex mcp add rogueskills-cases \
  --env ROGUESKILLS_API_BASE_URL=http://127.0.0.1:5173 \
  --env ROGUESKILLS_ALLOWED_CASE_PACKS=finance-stock-analysis,release-readiness \
  --env 'ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS={"finance-stock-analysis":"sop-9e7795@2","release-readiness":"release-readiness-base@1"}' \
  -- rogueskills-case-mcp
```

注册后检查：

```bash
codex mcp get rogueskills-cases --json
codex mcp list
```

如果同名 Server 已存在，先比较，不自动 remove/re-add。

## 4. 验收口径

链路只有同时满足以下条件才算完整通过：

- Codex 能发现 `rogueskills-cases`；
- MCP initialize 协商成功并返回 `rogueskills-cases@0.2.0`；
- tools/list 包含 7 个 Generic Case 工具和 5 个 Finance 兼容别名；
- Codex 实际调用 `run_case`，而不是自己生成结论；
- 新 Case ID 可由 `get_case_run/report/evaluation` 复查；
- `mode=verified_replay` 且 `replayCaseId` 指向真实 Live Case；
- `runtimeVerified=true`、score=100、hard gates passed；
- Release Readiness 结果为 4 sources、7 facts、19 checks；
- `recommendation=blocked` 被解释为发布判断，不被误判成 Runtime 失败；
- 事件 transcript 与结构化 final result 均落盘。

## 5. 本轮分层验证结果

已通过：

- 本机 Codex CLI：`codex-cli 0.144.6`；
- `codex mcp add/get/list/remove` 命令面可用；
- 项目 `.codex/config.toml` 被 `codex mcp get rogueskills-cases --json` 正确解析；
- stdio initialize：MCP `2025-06-18`；
- Server：`rogueskills-cases@0.2.0`；
- tools/list：Generic 与 Finance 兼容工具均可发现；
- Generic MCP 对真实 GitHub Source Bundle 的 Replay 已通过；
- Codex Host Replay：`case-run-f2d521df7adc46089fd291a8ae6327d4`；
- Codex 实际调用全部七个 Generic Case MCP 工具；
- Codex Host 结果：`runtimeVerified=true`、score=100、4 sources、7 facts、19 checks；
- Python 全量测试：94 passed；
- `git diff --check`：通过。

Codex Host 成功证据：`08-codex-mcp-config.json`、`09-codex-mcp-release-events.jsonl`、
`10-codex-mcp-release-result.json`。数据库、WAL、原始日志和完整 transcript 由仓库根目录
`.gitignore` 排除，不作为源代码提交。

## 6. 与 Claude Code 的关系

Claude Code 登录问题不会影响 Codex MCP。两边是独立 Host：

- Claude Code 需要自己的账号登录，并读取 `.mcp.json`；
- Codex 使用自己的登录状态，并读取 `.codex/config.toml` 或个人 MCP 注册；
- RogueSkills Bridge、Case ID、Source Bundle、Skill Version、Evaluation 和 Artifact 完全共用。

因此 RogueSkills 继续作为能力、版本、证据和自进化的维护端；Claude Code 与 Codex 都只是受控消费者。
