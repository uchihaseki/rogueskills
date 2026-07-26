# Awesome Finance Skills · 前端到 Codex 演示

这个目录提供一套不需要复制 ID 的完整 Demo。默认本地数据库会自动把 `Awesome-finance-skills/` 中的 9 个 `alphaear-*` Skill 放入 Initial Library，并加入一个可直接选择的 `Apple AAPL 公开财务分析` 真实数据回放案例；前端没有专用导入按钮，也不需要预先执行 Live Case。

## 启动

在仓库根目录分别启动 API 和前端：

```bash
npm start
npm run frontend:dev
```

打开 `http://127.0.0.1:5174/`，默认选择 `alphaear-signal-tracker`，点击“开始完整自动进化”。Victory 后，页面会默认选中内置的 AAPL 已验证回放案例；直接点击“开始运行时验证”。

然后在本目录启动 Codex：

```bash
cd examples/codex-awesome-finance-demo
codex
```

本目录的 `.codex/config.toml` 已默认启用 `rogueskills-demo` MCP。

## 推荐演示问题

```text
读取最新 Demo Context，说明当前 Skill、Evolution Run、Candidate AgentPreset 和证据模式。

生成最新 CaseValidation 的业务优先演示讲稿。

先给出 Candidate 的 AAPL 公司研究结论、风险和数据缺口，再解释 Baseline/Candidate 同源 A/B。

用 Node History 解释 Candidate 如何形成，并说明哪些候选优化项与 hard gate 修复相关。

最后分别说明 runtimeVerified、accepted、promoted 和新 Skill Version；不要把 Replay 称为 Live。
```

## CaseValidation 工具

```text
list_case_validations
get_latest_case_validation_context
get_case_validation_demo_script
validate_evolution_run_on_case
get_case_validation
get_case_validation_comparison
```

- `get_latest_case_validation_context`：自动发现真正最新的 Validation。
- `get_case_validation_demo_script`：从公司报告、A/B、Node History 和晋升证据生成中文讲稿。
- `validate_evolution_run_on_case`：创建幂等 Verified Replay A/B，严格提升时可能创建 Runtime-bound Skill Version。
- 其余工具为只读查询。

## 可复现脚本

```bash
npm run demo:awesome-finance
npm run demo:awesome-finance-replay
npm run demo:awesome-finance-preset-validation
```

最新完整验证产物位于：

```text
artifacts/awesome-finance-self-evolution-20260724/17-preset-validation-import.json
artifacts/awesome-finance-self-evolution-20260724/18-preset-validation-run.json
artifacts/awesome-finance-self-evolution-20260724/19-preset-validation.json
artifacts/awesome-finance-self-evolution-20260724/20-preset-validation-comparison.json
artifacts/awesome-finance-self-evolution-20260724/21-preset-validation-summary.json
```

演示主路径只使用 `verified_replay`：来源是真实持久化数据，但不会现场重新请求 Provider。前端 Candidate 生成阶段是 `capability-simulation-v1`；完成 CaseValidation 后才可能得到 `runtimeVerified=true`。
