# AgentPreset v0.1 前端验收测试

> 适用版本：2026-07-20 AgentPreset v0.1
>
> 这些路径已经使用 Python 权威 Evolution Engine 按固定 Seed 验证。严格按照节点和 Mutation 选择，可以稳定到达 Victory 并生成 AgentPreset。

## 1. 启动与准备

在项目根目录执行数据库迁移：

```sh
.venv/bin/alembic upgrade head
```

启动 FastAPI：

```sh
npm start
```

另开一个终端启动 Vue 前端：

```sh
npm run frontend:dev
```

访问：

```text
http://127.0.0.1:5174/
```

如果页面保留了上一次 Run，可以点击“新建 Run”或“返回 Run 设置”后开始新 Case。

## 2. Case A：稳定型商品采集 AgentPreset

### 目标

完整验证：

```text
创建 Run
→ 三幕构筑
→ Victory
→ 填写 Project 信息
→ 保存 AgentPreset
→ 查看摘要
→ 导出 JSON
```

### Run 设置

- 基础 Skill：`Browser Extraction Base`
- 模式：`稳定构筑`
- Seed：`PRESET-STABLE-01`

### 固定选择路径

| 顺序 | 节点 | 选择 Mutation |
|---|---|---|
| 1 | 第一幕 · 脏数据史莱姆（普通） | `Schema Validator` |
| 2 | 第一幕 · 延迟潜伏者（精英） | `Visual Locator` |
| 3 | 第一幕 · 进化实验室 | `Semantic Locator` |
| 4 | 第一幕 · Schema 九头蛇 | Boss 无 Mutation |
| 5 | 第二幕 · Canvas 幽灵（普通） | `Injection Shield` |
| 6 | 第二幕 · Canvas 幽灵（精英） | `Permission Guard` |
| 7 | 第二幕 · 批处理虫群（精英） | `Error Classifier` |
| 8 | 第二幕 · 视觉巨像 | Boss 无 Mutation |
| 9 | 第三幕 · 指令模仿怪（普通） | `Aggressive Cache` |
| 10 | 第三幕 · 分布漂移兽（普通） | `Prompt Compression` |
| 11 | 第三幕 · 分布漂移兽（精英） | `Fallback Tool` |
| 12 | 第三幕 · 影子发布者 | 最终 Boss |

### Project 表单

- Project 名称：`商品采集 Agent`
- 业务场景：`电商商品信息提取`
- 配置说明：`DOM 优先提取商品字段，必要时使用视觉定位，并对结果执行结构化校验。`

### 页面预期

- Run 状态：Victory。
- 最终得分：`86.0`。
- 出现 `AGENT PRESET · V0.1` 表单。
- 保存后出现 `PRESET SAVED`。
- 摘要显示：
  - Workflow：`8`
  - Tools：`2`
  - Rules：`12`
- 显示边界说明：`Candidate · capability simulation · runtimeVerified=false`。
- 点击“导出 Preset JSON”后下载一个以 `preset-` 开头的 JSON 文件。

### 导出 JSON 预期

```text
status = candidate
primarySkill.skillVersionId = browser-extraction-base@1
tools = [Browser, Vision]
runtimeDefaults.maxTokens = 12000
runtimeDefaults.maxToolCalls = 20
runtimeDefaults.timeoutMs = 60000
runtimeDefaults.priority = quality_and_robustness
evaluationEvidence.runtimeVerified = false
evaluationEvidence.objectiveScore = 86.0
digest 以 sha256: 开头
```

## 3. Case B：节能型 AgentPreset

### 目标

验证不同 Run Mode 会生成不同的 Runtime Defaults，并且固定 Mutation 会进入导出的规则和 Workflow。

### Run 设置

- 基础 Skill：`Browser Extraction Base`
- 模式：`节能构筑`
- Seed：`PRESET-EFFICIENT-01`

### 固定选择路径

| 顺序 | 节点 | 选择 Mutation |
|---|---|---|
| 1 | 第一幕 · 脏数据史莱姆（普通） | `Aggressive Cache` |
| 2 | 第一幕 · 字段变形怪（普通） | `Visual Locator` |
| 3 | 第一幕 · 脏数据史莱姆（普通） | `Schema Validator` |
| 4 | 第一幕 · Schema 九头蛇 | Boss 无 Mutation |
| 5 | 第二幕 · Canvas 幽灵（普通） | `Budget Guard` |
| 6 | 第二幕 · 超时魔像（普通） | `Early Exit` |
| 7 | 第二幕 · 超时魔像（精英） | `Error Classifier` |
| 8 | 第二幕 · 视觉巨像 | Boss 无 Mutation |
| 9 | 第三幕 · 分布漂移兽（普通） | `Permission Guard` |
| 10 | 第三幕 · 权限骑士（普通） | `Injection Shield` |
| 11 | 第三幕 · 进化实验室 | `Semantic Locator` |
| 12 | 第三幕 · 影子发布者 | 最终 Boss |

### Project 表单

- Project 名称：`低成本商品采集 Agent`
- 业务场景：`预算受限的批量商品信息提取`
- 配置说明：`在严格 Token 和工具调用预算下完成商品字段提取与结构化校验。`

### 预期结果

- Victory 最终得分：`85.0`。
- 保存成功并可以导出 JSON。
- 导出配置包含：

```text
runtimeDefaults.maxTokens = 6000
runtimeDefaults.maxToolCalls = 10
runtimeDefaults.timeoutMs = 45000
runtimeDefaults.priority = cost
runtimeDefaults.enforceBudget = true
tools 包含 Browser 和 Vision
rules.constraints 包含预算、权限和外部内容隔离规则
```

## 4. Case C：幂等保存与不可变保护

### 前置条件

先完成 Case A 并保存 `商品采集 Agent`。

### 幂等保存

1. 刷新页面。
2. 点击“继续上次 Run”。
3. 使用与 Case A 完全相同的 Project 名称、业务场景和配置说明。
4. 再次点击“保存 AgentPreset”。

预期：

- 返回同一个 Preset ID。
- Digest 不变化。
- `/api/agent-presets` 中不会产生重复记录。

### 不可变保护

1. 再次刷新并继续相同 Run。
2. 把 Project 名称改为 `被修改的商品采集 Agent`。
3. 点击“保存 AgentPreset”。

预期：

- 页面显示“该 Run 已经生成 AgentPreset，不能覆盖不可变配置”。
- 原 Preset 的 Project 名称和 Digest 不变。

## 5. Case D：未通关时不能生成 Preset

1. 新建任意 Run。
2. 在第一幕或第二幕停止操作。

预期：

- 页面不会显示 AgentPreset 保存表单。
- 只有 `status=victory` 且 `phase=ended` 的 Run 才能生成 Preset。
- 失败 Run 的结束页也不会出现保存入口。

## 6. API 辅助检查

保存成功后，可以从浏览器或 OpenAPI 页面检查：

```text
GET /api/agent-presets
GET /api/agent-presets/{presetId}
GET /api/agent-presets/{presetId}/export
GET /api/agent-presets/{presetId}/runtime-config
```

`runtime-config` 预期包含：

- `systemPrompt`
- `developerPrompt`
- `workflow`
- `tools`
- `rules`
- `runtimeDefaults`
- `runtimeVerified=false`

如果数据库中的 Preset 内容被修改而 Digest 没有同步更新，Loader 必须返回 `AGENT_PRESET_INTEGRITY_FAILED`。
