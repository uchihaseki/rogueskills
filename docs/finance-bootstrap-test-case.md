# 金融股票分析 Skill 初始化测试 Case

## 1. 模型配置

项目根目录 `.env` 已按以下配置创建：

```text
ROGUESKILLS_LLM_BASE_URL=http://10.10.105.11:8000/v1
ROGUESKILLS_LLM_MODEL=Qwen3.5-122B-A10B
ROGUESKILLS_LLM_TIMEOUT_SECONDS=180
```

该流水线需要后端能够同时访问：

- `http://10.10.105.11:8000/v1/chat/completions`
- `https://api.github.com`
- `https://raw.githubusercontent.com`

启动完整流程前，可以先单独验证模型配置、模型列表和一次真实 SOP 转换：

```sh
cd /Users/shuo/workspace/code/rogueskills
.venv/bin/python scripts/test_qwen_finance.py
```

脚本会从项目根目录 `.env` 读取配置，依次检查 `/v1/models` 中是否存在目标模型，并调用真实 Normalizer 转换一份金融 SOP。成功时应看到 `NORMALIZATION status=passed`；脚本不会输出 API Key。

## 2. 启动

```sh
cd /Users/shuo/workspace/code/rogueskills
.venv/bin/alembic upgrade head
npm start
```

另开终端：

```sh
cd /Users/shuo/workspace/code/rogueskills
npm run frontend:dev
```

访问：

```text
http://127.0.0.1:5174/discovery
```

## 3. 前端完整流程

1. 打开 Discovery 页面。
2. 点击顶部“金融场景”。
3. 确认右侧模型显示 `Qwen3.5-122B-A10B`。
4. 点击“开始自动构建”。
5. 等待 GitHub 检索、内容拉取、Qwen 标准化和 Admission 完成。

按钮代表一次显式的批量准入授权：只有通过 License、安全、Schema 和 Admission Benchmark 的结果会进入 Initial Library。

## 4. 流水线输入

系统自动执行三组社区查询：

```text
stock fundamental analysis agent skill valuation financial statements
equity research earnings analysis workflow agent
stock analysis investment research skill risk valuation
```

社区候选硬门槛：

- GitHub Stars 至少 5。
- License 已知。
- Discovery 综合分和金融相关度达标。
- 成功拉取 `SKILL.md` 或 README 快照。
- 内容至少 240 字符。
- 内容包含至少两个股票、财报或估值语义词。
- 内容包含 Agent、Skill、Workflow 或步骤结构。
- 不包含高风险指令或危险执行内容。

系统还会把两份内置 SOP 发送给 Qwen：

- `上市公司基本面与估值分析 SOP`
- `上市公司财报与业绩电话会复盘 SOP`

## 5. 页面预期

完成后页面展示：

- 社区召回数量。
- 实际拉取内容数量。
- 社区入库数量。
- SOP 转换数量，应为 `2`。
- Initial Skills 数量。
- 被过滤候选数量和原因。
- 每个入库 Skill 的模型、Admission 分数和状态。

网络搜索结果会随 GitHub 当前内容变化，因此社区入库数量不写死；两份内置 SOP 应稳定完成转换。如果社区结果为 0，页面必须展示过滤原因或 Provider 错误，而不能把失败伪装成成功。

## 6. Repository 与 Evolution 验证

1. 点击顶部 `Skill Repository`。
2. 确认至少能看到两项 `metadata.category=finance` 且状态为 `initial` 的 SOP Skill。
3. 返回 Evolution Run 设置页。
4. 选择任一金融 Skill，点击“生成 Evolution Run”。

预期：

- 角色标记显示 `FI`。
- `archetypeId=finance`。
- 第一幕地图为“披露数据区”。
- 第一幕 Boss 为“财报重述九头蛇”。
- 后续地图依次为“估值实验场”和“风险投委会”。
- Mutation Draft 可以出现 `Source Triangulation`、`Accounting Normalizer`、`Valuation Sensitivity`、`Risk Register` 等金融配置。

## 7. API 辅助验证

```text
POST /api/scenarios/finance/bootstrap
GET  /api/library/initial
POST /api/runs
```

Bootstrap 请求：

```json
{
  "maxCommunitySkills": 2,
  "autoPromote": true
}
```

自动化 Fixture Case 的稳定预期为：

```text
discovered = 1
communityStored = 1
sopsProcessed = 2
initialSkills = 3
Qwen-compatible normalization calls = 3
rerun does not create duplicate Skills
finance Skill creates finance Evolution map
```
