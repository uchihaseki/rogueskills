# RogueSkills P1 Contracts v1

## 1. 状态

本文是 P1 三方协作的契约基线。当前状态为 `Draft`，完成 Browser 真实执行纵向闭环后升级为 `Stable 1.0`。

契约遵循以下规则：

- 新增可选字段属于兼容变更。
- 删除字段、改变含义或把可选字段改为必填属于破坏性变更。
- 破坏性变更必须升级 Schema 版本，并同步 Fixture 和集成测试。
- 时间统一使用 ISO 8601 UTC，标识符使用稳定字符串。
- 分数统一为 `0..100`，耗时统一为毫秒，成本同时保留原始用量和标准化值。

## 2. Skill Genome

当前正式 Schema：`src/contracts/skill-genome.schema.json`。

Skill Genome 描述可执行资产本身，不承载服务端权限。`status` 只作为服务端返回的生命周期快照，客户端提交该字段不能触发状态转换。

生命周期由后端命令管理：

```text
quarantine → initial → evolving → candidate → production
```

约束：

- 外部导入和人工创建统一从 `quarantine` 开始。
- `quarantine → initial` 需要当前版本通过准入 Benchmark，并由人工触发。
- `initial → evolving` 由创建 Evolution Run 触发。
- `evolving → candidate` 需要当前 Run 通过 Hidden Test，并保存 Genome Patch。
- `candidate → production` 需要后续 A/B、Canary 或明确审批。

## 3. Evaluation Request

算法定义字段语义，后端负责创建请求和控制执行环境。

```json
{
  "contractVersion": "1.0.0",
  "runId": "run-001",
  "skillId": "browser-extraction",
  "skillVersionId": "browser-extraction@3",
  "benchmarkId": "browser-runtime-v1",
  "scenarioPackVersion": "browser-scenarios@1",
  "caseId": "extract-product-json",
  "split": "validation",
  "seed": "RUN-001",
  "budget": {
    "maxTokens": 10000,
    "maxToolCalls": 20,
    "timeoutMs": 60000
  }
}
```

规则：

- `split` 只能是 `train`、`validation` 或 `hidden`。
- Hidden Request 可以包含 `caseId`，但不能向前端返回输入、答案或验收细节。
- Evaluation 必须绑定不可变 `skillVersionId` 和 `scenarioPackVersion`。

## 4. Runtime Adapter

后端实现统一执行接口：

```text
execute(EvaluationRequest, SkillGenome, RuntimeCase)
→ RuntimeExecution
```

`RuntimeExecution`：

```json
{
  "contractVersion": "1.0.0",
  "executionId": "exec-001",
  "status": "succeeded",
  "output": {},
  "traceId": "trace-001",
  "usage": {
    "inputTokens": 2100,
    "outputTokens": 800,
    "toolCalls": 5,
    "latencyMs": 3200
  },
  "error": null,
  "runtimeVersion": "browser-adapter@1"
}
```

`status` 取值：`queued`、`running`、`succeeded`、`failed`、`timed_out`、`cancelled`。

算法只能读取允许进入评测的 Trace 和 Output；后端必须先完成 Secret 脱敏。

## 5. Evaluation Result

算法根据 RuntimeExecution 和 Scenario 验收规则生成：

```json
{
  "contractVersion": "1.0.0",
  "evaluationId": "eval-001",
  "executionId": "exec-001",
  "skillVersionId": "browser-extraction@3",
  "benchmarkId": "browser-runtime-v1",
  "scenarioPackVersion": "browser-scenarios@1",
  "split": "validation",
  "passed": true,
  "score": 86.5,
  "metrics": {
    "quality": 90,
    "coverage": 88,
    "latencyMs": 3200,
    "tokenCost": 2900,
    "securityPassed": true
  },
  "cases": [],
  "summary": "通过标准业务验收",
  "algorithmVersion": "browser-evaluator@1"
}
```

要求：

- Result 必须引用实际执行的不可变版本。
- 前端只展示 Result，不重新聚合分数。
- 后端保存完整 Result；Hidden Result 对前端只返回分数、状态和脱敏摘要。

## 6. Scenario Pack

```json
{
  "id": "browser-scenarios",
  "version": 1,
  "category": "browser",
  "fingerprint": "sha256:...",
  "cases": [
    {
      "id": "extract-product-json",
      "split": "validation",
      "inputRef": "dataset://browser/product/001",
      "evaluatorId": "json-extraction-v1",
      "requirements": {
        "requiredFields": ["name", "price"],
        "maxLatencyMs": 10000
      },
      "runtimeProfile": "browser-sandbox-v1"
    }
  ]
}
```

数据治理：

- Train 可以为 Mutation 提供详细反馈。
- Validation 可以提供指标和有限诊断。
- Hidden 不公开输入、答案和逐字段诊断。
- Runtime Trace 回流进入数据集前必须脱敏、去重并经过审批。

## 7. Mutation Proposal

```json
{
  "contractVersion": "1.0.0",
  "id": "add-schema-validation",
  "sourceSkillVersionId": "browser-extraction@3",
  "reason": "连续两个用例出现必填字段缺失",
  "evidenceRefs": ["eval-001:case-output-contract"],
  "tradeoff": "增加一次校验步骤和执行延迟",
  "complexityCost": 1,
  "tags": ["schema", "validation"],
  "genomePatch": [
    {
      "op": "add",
      "path": "/workflow/steps/-",
      "value": "Validate the output against the declared schema."
    }
  ],
  "expectedEffects": {
    "structure": 12,
    "latencyMs": 300
  },
  "algorithmVersion": "mutation-planner@1"
}
```

应用 Patch 的顺序：

1. 验证 `sourceSkillVersionId` 仍是 Run 的当前父版本。
2. 应用受支持的 Patch 操作。
3. 重新执行 Skill Genome Schema 和静态安全检查。
4. 保存不可变子版本和 Mutation 历史。
5. 失败时保持父版本不变。

## 8. Lifecycle Command

前端使用命令，而不是直接更新状态：

```text
POST /api/skills/:id/benchmark
POST /api/skills/:id/promote
POST /api/runs
POST /api/runs/:id/mutations/:mutationId/apply
POST /api/runs/:id/candidate
```

晋升请求至少包含：

```json
{
  "evaluationId": "eval-001",
  "expectedSkillVersionId": "browser-extraction@3"
}
```

后端必须同时校验 Evaluation、当前版本、Benchmark 类型、许可证和风险门槛。

## 9. API Error

所有新 API 使用统一错误结构：

```json
{
  "error": {
    "code": "STALE_EVALUATION",
    "message": "Evaluation does not belong to the current Skill version.",
    "retryable": false,
    "details": {}
  },
  "requestId": "req-001"
}
```

前端根据 `code` 决定交互，不解析 `message`。旧 API 在 P1 迁移期间可以兼容 `{ "error": "message" }`。

## 10. 契约 Fixture

每个 Stable Contract 必须同时提供：

- 一个最小成功 Fixture。
- 一个完整成功 Fixture。
- 至少一个校验失败 Fixture。
- 提供方测试和消费方测试。

Fixture 后续统一放入 `tests/fixtures/contracts/v1/`。
