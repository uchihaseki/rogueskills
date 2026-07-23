# Release Readiness 真实 Case

## 1. 目的

`release-readiness@1.0.0` 是 Finance 之后的第二个真实 Case Pack，用来证明
RogueSkills 的 Live、Dataset、Typed Report、Evaluation、Mutation、Skill Version、
Artifact 和 Verified Replay 可以复用同一套通用 Runtime。

它不会复制 `FinanceCaseService`，也没有新增 Release 专用 API。执行入口仍然是：

```text
POST /api/case-runs
GET  /api/case-runs/{caseId}
GET  /api/case-runs/{caseId}/report
GET  /api/case-runs/{caseId}/evaluation
GET  /api/case-runs/{caseId}/artifact
POST /api/case-runs/{caseId}/replay
```

## 2. 初始输入

```json
{
  "casePackId": "release-readiness",
  "casePackVersion": "1.0.0",
  "skillId": "release-readiness-base",
  "input": {
    "repository": "openai/openai-python",
    "ref": "main",
    "baseBranch": "main",
    "maxPullRequests": 20
  },
  "mode": "live",
  "autoEvolve": false
}
```

`repository` 只能是 `owner/name`，客户端不能传入任意 URL。`ref` 会先解析为不可变
commit SHA；`baseBranch` 只用于查询 open pulls。未配置 GitHub Token 时可以访问公开
仓库，但受匿名 rate limit 约束。Token 只保留在后端。

## 3. 真实来源

Gateway 只允许以下 GET 路由：

```text
https://api.github.com/repos/{owner}/{repo}
https://api.github.com/repos/{owner}/{repo}/commits/{ref}
https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs
https://api.github.com/repos/{owner}/{repo}/pulls
```

每份 Source Snapshot 保存实际 URL、抓取时间、candidate SHA revision、响应 SHA-256、
content type 和原始响应。Repository、commit、check-runs 或 pulls 任一请求失败时，
Live Case 失败并保留稳定错误码；不会用 fixture 或本地数据回退。

## 4. Dataset 和输出

确定性 Dataset 包含：

- candidate commit SHA；
- check 总数、成功数、失败数、pending 数；
- open pull 和 draft pull 数；
- successful/total check pass rate；
- 所有 Fact 与派生指标的 Source Evidence ID。

最终 Report 为 `ReleaseReadinessReport@1.0.0`，核心字段是：

```json
{
  "recommendation": "ready | review | blocked",
  "summary": "...",
  "sources": [],
  "facts": [],
  "derivedMetrics": [],
  "findings": [],
  "dataGaps": []
}
```

三态规则：

- `blocked`：candidate 存在 failing check，或 repository 已 archived；
- `review`：存在 pending check、没有 check，或 base branch 上存在 draft pull；
- `ready`：至少一个 check，全部完成且成功/neutral/skipped，并且没有上述阻塞状态。

`runtimeVerified=true` 表示报告证据可信，不代表 recommendation 必须是 `ready`。一个
有完整失败证据并正确给出 `blocked` 的报告同样可以被 Runtime 验证。

## 5. 硬门槛

Evaluator 独立校验：

1. `source-integrity`：四个 GitHub Snapshot、revision 和 SHA-256 完整；
2. `finding-citations`：所有 finding 只引用已捕获 Evidence ID；
3. `no-fabricated-status`：Report Fact 与确定性 Dataset 完全一致；
4. `ci-evidence`：candidate 至少返回一个真实 check run；
5. `review-evidence`：open-pulls 状态已捕获，同时明确它不等于 approval；
6. `recommendation-consistency`：三态结论与 check/draft/archive 状态一致。

任何 hard gate 失败时，即使总分达到阈值也不能生成 Runtime Artifact。

## 6. Mutation 与 Replay

当 Skill 缺少 evidence workflow 时，Planner 通过 JSON Patch 增加 GitHub evidence ID、
missing-CI 和 readiness constraint。只有 evolved Report 通过全部 hard gates 且分数严格
高于 baseline，才保存新的 Skill Version。

Provider 本身没有返回 check runs 时，Mutation 不能伪造证据，因此 attempt 会被明确
标记为 `rejected`，Initial Skill 不变。

Verified Replay 只读取 Live Case 已持久化的 Source Bundle。Repository 和 ref 必须与
原 Case 一致；Replay 不访问 GitHub，也不会把旧 Snapshot 标成最新数据。

## 7. 真实运行

```sh
cd /Users/shuo/workspace/code/rogueskills

PYTHONPATH=backend .venv/bin/python \
  artifacts/release-e2e-20260723/run_live_release_case.py
```

可用环境变量选择其他公开仓库或 candidate ref：

```sh
ROGUESKILLS_RELEASE_REPOSITORY=owner/repository \
ROGUESKILLS_RELEASE_REF=main \
ROGUESKILLS_RELEASE_BASE_BRANCH=main \
PYTHONPATH=backend .venv/bin/python \
  artifacts/release-e2e-20260723/run_live_release_case.py
```

Runner 走正式 `create_app` 和 `/api/case-runs`，不安装 MockTransport。成功后保存 Live
Case、Verified Replay、Source Bundle Digest、Artifact Digest 和前后 Gateway 调用数。

## 8. 2026-07-23 真实验收结果

```text
Repository：openai/openai-python@main
Candidate SHA：e67afa88433dad9f97e733ae8f2ee6e9c240bc51
Live Case：case-run-c13f4265126a4e2ca3eb58b5b61b61f3
Recommendation：blocked（19 checks：18 successful，1 failing，0 pending）
Runtime Verified：true
Evaluation：100；6/6 hard gates passed
Sources / Facts：4 / 7
Source Bundle Digest：sha256:2ee8fdb00d0693de9ae05d5def02df1ecdea8de8934e6ad0afbbfc893d505f64
Artifact：artifact-43343ba872d8678c944e
Artifact Digest：sha256:43343ba872d8678c944e62bb5b518f507918604dd87ab00d9015165158e51b07
Verified Replay：case-run-6ef697f4ee8745d6b84d91cfe305b07e
Replay Gateway Calls：1 → 1
Offline Replay：case-run-81a5c71032b44a5daf3c0b7c4fe035a5；Gateway Calls=0
Gate：PASS
```

`blocked` 与 `runtimeVerified=true` 并不冲突：前者表示当前 candidate 不应发布，后者
表示该结论有完整真实证据、事实未被篡改，且报告通过全部评估门槛。
