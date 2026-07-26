# Awesome Finance Skills Codex Demo

这是前端自进化到真实金融案例验证的 Codex 演示项目。

## 默认工作流

1. 先调用 `get_demo_context`，自动发现最新 Skill、Evolution Run、AgentPreset、CaseValidation、Promotion 和 Node History summary。
2. 用户要演示讲稿时，调用 `get_case_validation_demo_script`。
3. 业务内容优先：先讲 Candidate 公司研究报告、findings、risks、data gaps 和结论边界。
4. 再讲 Base Skill Version 与 Candidate AgentPreset 的同源 A/B、score 和 hard gates。
5. 用 Node History 解释 Candidate 如何形成：节点测试、已选择候选优化项和解锁能力组合。
6. Contribution Coverage 只能描述为“关联修复”或 `associated_not_causal`，不能描述为单项独立因果。
7. 最后分别报告 `runtimeVerified`、`accepted` 和 `promoted`；三者不能混用。

## 证据边界

- Browser Evolution 产物是 `capability-simulation-v1`，生成时 `runtimeVerified=false`。
- CaseValidation 固定为 `mode=verified_replay`，使用真实持久化 Source Bundle，但不是现场 Live 请求。
- 不得把 Verified Replay 描述为 Live。
- 不得遗漏 Source、Dataset、Execution Policy 和 Candidate Preset digest。
- `validate_evolution_run_on_case` 会写入 Validation，并可能创建 Skill Version；只有用户明确要求执行验证时才调用。
- 其他 CaseValidation 工具是只读的。

不要编造 Skill、Run、Preset、Validation 或业务报告内容。如果 `get_demo_context.available=false`，说明需要先在前端完成一次 Evaluation Run。
