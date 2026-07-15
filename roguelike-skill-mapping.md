# RogueSkills —— 肉鸽元素与 Skill Evolution 核心映射（Draft v0.1）

> **核心观点**
>
> RogueSkills 不是给 Skill Evolution 套一层游戏 UI，而是用肉鸽游戏的单局、随机路线、能力构筑、风险收益和失败重开机制，组织真实的 Skill 数据、评估与进化过程。

---

## 1. 两套系统的共同循环

肉鸽游戏与 Skill Evolution 都遵循同一种循环：

```text
选择初始角色 / 基础 Skill

↓

根据 Seed 生成地图 / 业务评测计划

↓

遭遇怪物 / 执行业务测试

↓

战斗结算 / 收集执行指标

↓

发现弱点 / 诊断失败模式

↓

选择武器升级 / 选择 Mutation

↓

形成新的角色构筑 / Skill Genome 分支

↓

继续冒险、主动撤离或挑战 Boss

↓

隐藏测试与业务验收

↓

保存候选版本、灰度发布或本局失败

↓

线上反馈成为未来的新怪物
```

二者真正的相似点在于：

- 每一局都从一个明确的初始状态开始
- 环境包含不完全可知的随机挑战
- 玩家根据反馈逐步形成构筑
- 每次增强都应该伴随资源消耗或能力取舍
- 局内失败不会摧毁永久资产，但会结束当前分支
- 通过最终挑战后，构筑才有资格成为正式成果

---

## 2. 核心元素对应关系

| 肉鸽元素 | Skill Evolution 概念 | 数据与评估含义 | 业务含义 |
|---|---|---|---|
| 角色 | 一个 Skill Genome 实例 | 当前 Prompt、Workflow、Tools、Memory 和 Constraints | 当前业务 Agent |
| 职业 | Skill Archetype | 初始能力、属性倾向和 Mutation 池 | 客服、研究、浏览、代码、数据提取 |
| 武器 | 可执行能力模块 | Browser、Search、OCR、Planner、Validator | 完成任务的核心手段 |
| 被动道具 | 全局辅助能力 | Cache、Memory、Retry、Schema、Budget Guard | 成本控制、稳定性和安全策略 |
| 武器升级 | 局部 Mutation | 改写 Prompt、调整参数、增加重试或校验 | 改善一个具体指标 |
| 武器进化 | 能力融合或架构升级 | 多模块融合为新的 Workflow | 从通用能力进化为场景化专业能力 |
| 地图 | 业务测试空间 | Benchmark 的采样、组合和组织方式 | 一局需要覆盖的业务场景 |
| 地图区域 | 场景域或数据分布 | 不同 Dataset Slice 和环境条件 | 不同业务阶段、渠道或客户类型 |
| 房间 | 一组测试任务 | 一个 Scenario Pack | 一个具体业务环节 |
| 怪物种类 | 失败模式 | Schema 错误、工具失效、脏数据、注入攻击 | 业务风险类型 |
| 怪物实例 | 具体测试样本 | 一条输入、环境配置和预期输出 | 一张工单、一个网页、一个代码任务 |
| 战斗 | Skill 执行与评测 | Trace、输出、成本、延迟、成功率 | 业务任务是否完成 |
| 精英怪 | 高难验证任务 | 组合失败模式、分布外样本 | 复杂或高价值业务案例 |
| Boss | 隐藏端到端测试 | 未参与进化的 Hidden Test | 真实业务验收 |
| 血量 | Stability / Integrity | 对连续失败和严重错误的容忍度 | 当前实验是否还能继续 |
| 金币 | Compute Budget | Token、模型、工具和评测预算 | 实验成本 |
| 装备栏 | Complexity / Slots | Tool、Memory、Planner 容量 | 系统复杂度和维护成本 |
| 经验值 | Evidence / Learning Progress | 已覆盖的样本、失败类型和验证证据 | 对业务场景的理解程度 |
| 战利品 | Mutation、数据和失败知识 | 新模块、失败样本、遗物、融合配方 | 可复用的业务能力 |
| 负面状态 | 临时环境 Modifier | 限流、上下文污染、工具超时、数据缺失 | 业务运行条件恶化 |
| 死亡 | 当前进化分支失败 | 丢弃候选版本，保留 Replay 和失败知识 | 不影响生产环境 |
| 撤离 | 提前结束本局 | 保存未完成的实验候选 | 保留有价值但未完成验证的版本 |
| 通关 | 候选 Skill 通过隐藏测试 | 进入 A/B Test 或 Canary | 获得发布资格 |
| 局外成长 | 能力和测试空间解锁 | 新 Mutation、Benchmark、配方和分析工具 | 组织能力资产积累 |

一个关键的粒度关系是：

> **怪物种类是失败模式，怪物实例是具体测试样本，一场遭遇是一个业务场景测试包。**

---

## 3. 角色与职业

### 3.1 角色对应 Skill Genome

一个角色就是当前 Run 中正在进化的 Skill 副本，包含：

```text
Skill Genome

├── Prompt
├── Workflow
├── Tools
├── Examples
├── Constraints
├── Memory
├── Planner
├── Mutation History
└── Benchmark History
```

角色的属性不是传统攻击力和防御力，而是：

- Success Rate
- Robustness
- Cost
- Latency
- Determinism
- Maintainability
- Hallucination Rate
- Tool Dependency
- Complexity

### 3.2 职业对应 Skill Archetype

职业决定初始能力、倾向和可获得的 Mutation 池。

例如：

| 职业 | 初始能力 | 主要指标 | 典型业务 |
|---|---|---|---|
| Browser | 页面导航与信息提取 | 页面覆盖率、提取准确率 | 网页自动化、商品监控 |
| Researcher | 搜索、阅读、引用 | 事实性、引用覆盖率 | 市场研究、尽调 |
| Support Agent | 分类、检索、回复 | 解决率、升级准确率 | 客服工单 |
| Coding Agent | 阅读、修改、测试 | 测试通过率、回归率 | 软件开发 |
| Data Operator | 清洗、转换、校验 | 字段准确率、异常率 | 数据处理 |

职业不代表永久强弱，只决定开局构筑方向和更容易遇到的能力。

---

## 4. 武器、被动道具与能力槽位

### 4.1 武器对应可执行能力模块

武器是直接参与业务任务执行的核心模块，例如：

- Browser Navigation
- Web Search
- DOM Extractor
- Screenshot OCR
- Code Executor
- Task Planner
- Schema Validator
- Retrieval Engine

武器的游戏属性可以映射为：

| 武器属性 | Skill 指标 |
|---|---|
| 伤害 | 对业务验收条件的完成度 |
| 攻速 | 吞吐量和平均延迟 |
| 射程 | 能覆盖的场景范围 |
| 命中率 | 正确率和确定性 |
| 暴击 | 在高难或长尾样本上的超额表现 |
| 弹药 | Token、Tool Call 或请求预算 |
| 冷却 | 模型和工具调用延迟 |
| 穿透 | 一次执行处理多个步骤或多个样本的能力 |
| 元素属性 | 视觉、搜索、代码、推理等能力标签 |

### 4.2 被动道具对应全局策略

被动道具不直接完成任务，而是改变其他能力的运行规则：

- Retry Policy
- Cache
- Long-term Memory
- Context Compression
- Budget Guard
- Timeout Guard
- Output Schema
- Safety Policy
- Trace Replay

被动能力通常承担构筑协同、资源控制和风险管理。

### 4.3 装备栏对应复杂度限制

每个 Skill 应有明确的构筑容量：

```text
Tool Slots
Memory Slots
Planner Slots
Policy Slots
Relic Slots
Total Complexity
```

如果没有槽位和复杂度限制，最优策略会变成“把所有能力都加进去”，从而失去选择、维护性和游戏性。

---

## 5. 武器升级与武器进化

### 5.1 普通升级：局部 Mutation

普通升级不会改变能力的本质，只强化现有模块。

例如 `DOM Extractor`：

```text
Level 1：基础 CSS Selector

Level 2：增加 Semantic Locator

Level 3：增加 Selector Retry

Level 4：增加字段校验
```

它们分别对应：

- Prompt Mutation
- 参数调整
- Workflow 增强
- Example 补充
- Constraint 增加
- 局部 Tool 替换

### 5.2 武器进化：结构性能力变化

武器进化不是简单增加分数，而是将多个能力融合成新的 Workflow。

```text
DOM Extractor
+ Screenshot OCR
+ Schema Validator
+ Visual Memory
= Adaptive Web Extractor
```

进化后的执行逻辑：

```text
优先进行 DOM 提取

↓

执行字段完整性和类型校验

↓

发现字段缺失或数据异常

↓

自动切换 Screenshot + OCR

↓

合并两路结果

↓

再次执行 Schema Validation
```

### 5.3 武器进化的触发条件

武器进化建议同时要求：

1. 配方条件：拥有指定 Mutation 和能力标签
2. 数据条件：本局遇到足够多的相关失败样本
3. 评估条件：融合版本在 Validation 上确实优于原版本
4. 资源条件：没有超过 Complexity、Cost 和 Latency 上限
5. 回归条件：不能严重损害其他核心业务场景

```yaml
evolution:
  id: adaptive_web_extractor
  name: Adaptive Web Extractor

  requires:
    mutations:
      - dom_extractor
      - screenshot_ocr
      - schema_validator
    tags:
      vision: 2
      extraction: 2

  evidence:
    related_failure_count: 5

  gates:
    field_accuracy_gain: ">= 8%"
    unrelated_regression: "<= 2%"
    complexity: "<= 6"
    p95_latency: "<= 10s"
```

只有通过验证，系统才将其作为真正的进化能力。否则，它只是一次失败的 Fusion 实验。

### 5.4 进化路线应该具有分支

同一个基础武器可以向不同业务目标进化：

```text
Browser

├── Fast Browser
│   └── Parallel Caching Browser
│
├── Robust Browser
│   └── Self-Healing Browser
│
├── Vision Browser
│   └── Adaptive Visual Browser
│
└── Secure Browser
    └── Injection-Resistant Browser
```

这些进化版本不应该被压缩成一个全局排行榜，而应分别服务于低延迟、高鲁棒性、视觉页面和安全场景。

---

## 6. 随机地图与业务评测空间

### 6.1 地图的准确定义

随机地图不等于随便抽取测试题。

> **随机地图是一份带随机种子、业务覆盖规则和难度曲线的评测计划。**

地图生成器可以表示为：

```text
Map(
  seed,
  business_profile,
  scenario_pool,
  historical_failures,
  difficulty_curve,
  coverage_constraints,
  novelty_rate
)
```

### 6.2 地图的数据组成

建议每张地图由以下数据构成：

- 50% 核心业务场景：保证基本能力覆盖
- 30% 历史线上失败：推动 Skill 修复真实问题
- 20% 探索性场景：发现未知弱点，防止只优化旧问题

比例可以按业务风险调整，但核心场景必须由 Coverage Constraint 保证，不能完全交给随机数。

### 6.3 地图区域对应数据分布

| 地图区域 | 数据与环境 | 业务含义 |
|---|---|---|
| 静态平原 | 结构化、低难度、常规样本 | 标准业务流程 |
| 动态森林 | SPA、异步加载、状态变化 | 动态网页或多轮交互 |
| 视觉洞穴 | 图片、Canvas、OCR | 非结构化视觉数据 |
| 权限城堡 | 登录、授权、工具限制 | 企业权限与敏感操作 |
| 对抗荒地 | Prompt Injection、恶意输入 | 安全与风控场景 |
| 漂移沼泽 | 新格式、新表达、新来源 | 数据与需求分布变化 |
| 成本沙漠 | 严格 Token、时间和调用预算 | 低成本规模化任务 |

### 6.4 房间对应 Scenario Pack

每个房间不是一条测试数据，而是一组具有同一业务目标的测试任务：

```yaml
node:
  id: dynamic_product_page_01
  region: dynamic_forest
  type: normal_encounter
  scenario: product_extraction
  dataset_split: train
  failure_tags:
    - lazy_load
    - schema_drift
  constraints:
    p95_latency: 8s
    max_tool_calls: 10
  rewards:
    pool: extraction_mutations
```

### 6.5 地图中的数据隔离

三类节点必须使用隔离的数据：

- 普通房间：Train / Public Benchmark，可以提供详细反馈
- 精英房间：Validation，只提供有限诊断
- Boss：Hidden Test，不公开样本和详细答案

同一个基础 Skill 的不同构筑，应优先在相同 Seed 和相同地图规则下比较，保证结果可复现。

---

## 7. 怪物与失败模式

### 7.1 怪物的三层定义

```text
Monster Archetype
= 一类失败模式

Monster Instance
= 一个具体测试样本

Encounter
= 一组属于同一业务场景的怪物实例
```

例如：

```text
怪物种类：Schema Drift

怪物实例：某商品页将 price 字段改为 salePrice

遭遇：20 个具有不同字段变化的商品页面
```

### 7.2 怪物类型

| 怪物 | 对应失败模式 | 示例 |
|---|---|---|
| 史莱姆 | 脏数据和格式变化 | 空字段、错误类型、不规则 JSON |
| 怪物群 | 并发和批量压力 | 同时处理上百个页面或工单 |
| 装甲怪 | 严格约束 | 权限限制、只允许特定工具 |
| 隐形怪 | 信息缺失 | 输入不完整、状态不可观察 |
| 模仿怪 | Prompt Injection | 页面内容诱导 Agent 修改目标 |
| 变形怪 | 分布漂移 | 页面结构或用户表达突然变化 |
| 治疗怪 | 错误反馈循环 | 错误结果被缓存并持续复用 |
| 召唤怪 | 级联任务扩张 | 一个任务产生大量不可控子任务 |
| 精英怪 | 多失败模式组合 | 动态页面、OCR 与成本限制同时出现 |
| Boss | 端到端业务验收 | 完整流程同时满足质量、成本和安全 SLA |

### 7.3 怪物属性

| 怪物属性 | 测试含义 |
|---|---|
| 血量 | 需要满足的子目标数量或测试覆盖广度 |
| 攻击力 | 失败对业务造成的严重程度 |
| 护甲 | 约束严格度和解决难度 |
| 速度 | 延迟 SLA 与超时压力 |
| 抗性 | 对某一类工具或策略的克制 |
| 特殊能力 | 工具失效、权限变化、上下文污染等 Modifier |
| 狂暴 | 随执行时间增加成本或失败风险 |

### 7.4 战斗结算

战斗中的“伤害”代表 Skill 满足了多少验收条件；怪物的攻击则代表失败对本局造成的影响。

```text
Skill 输出

↓

逐项检查 Acceptance Criteria

↓

满足条件 → 对怪物造成进度伤害

未满足条件 → 根据错误严重程度损失 Stability

超过成本或延迟限制 → 额外受到环境伤害
```

严重幻觉、越权操作或安全违规可以直接造成致命伤害，而不是和普通格式错误使用相同惩罚。

---

## 8. 精英怪与 Boss

### 8.1 精英怪对应高难验证集

精英怪通常组合多个失败模式，例如：

```text
动态网页
+ Canvas 渲染
+ 字段格式变化
+ P95 延迟限制
= 精英遭遇
```

精英战适合检验构筑是否真正成型，并奖励稀有 Mutation、遗物或额外槽位。

### 8.2 Boss 对应隐藏端到端测试

Boss 必须满足：

- 数据没有参与当前 Run 的 Mutation 生成
- 评测逻辑与训练过程隔离
- 同时包含质量、成本、延迟、安全等业务 SLA
- 结果可审计，但不泄露全部测试细节
- 通过只代表获得发布资格，不代表自动上线

Boss 的作用不是单纯提高难度，而是防止 Skill 对公开 Benchmark 过拟合。

---

## 9. 血量、金币与失败

### 9.1 血量对应 Stability

Stability 表示当前实验分支还能容忍多少失败，而不是直接等同于 Success Rate。

可能造成伤害的事件：

- 普通任务失败
- 输出不符合 Schema
- 严重幻觉
- 工具调用死循环
- 超出成本预算
- 超出延迟限制
- 越权或安全违规

不同错误应按照业务严重性造成不同伤害。

### 9.2 金币对应 Compute Budget

Compute 可以用于：

- 执行额外评测
- 重抽 Mutation
- 购买能力
- 进行 Fusion
- 修复 Stability
- 运行更昂贵的诊断

Compute 的来源可以是挑战奖励，也可以由真实实验预算决定。

### 9.3 死亡对应候选分支失败

本局失败后：

- 丢弃本局可执行候选版本
- 不修改生产 Skill
- 保存完整 Replay
- 保存失败样本
- 保存 Mutation 冲突与协同数据
- 将有价值的失败模式加入未来 Scenario Pool

因此，死亡丢失的是本局构筑，不丢失学习到的知识。

---

## 10. 战利品与局外成长

### 10.1 战利品

战利品可以包括：

- Mutation
- 新 Tool Adapter
- Failure Example
- Counter Example
- Benchmark Pack
- Relic
- Fusion Recipe
- Complexity Slot
- 一次性诊断能力

### 10.2 局外成长

局外成长应该解锁更多选择，而不是永久增加评估分数：

- 解锁新的 Mutation 卡池
- 解锁新的基础 Skill
- 解锁新的地图区域
- 解锁新的精英和 Boss
- 解锁新的 Fusion 配方
- 解锁更强的失败分析能力
- 解锁更多初始路线候选

不建议提供“永久成功率 +10%”之类的成长，否则游戏进度会污染 Skill 的客观评测。

---

## 11. 业务场景示例：电商商品信息提取

### 11.1 角色

```text
Product Extraction Skill
```

### 11.2 初始武器

```text
DOM Parser
Basic Browser
JSON Formatter
```

### 11.3 地图

```text
第一幕：静态商品页

第二幕：动态页面与多规格商品

第三幕：Canvas、登录、反爬和页面改版
```

### 11.4 怪物

```text
Lazy Load       → 数据没有立即加载

Schema Drift    → 字段名称和结构变化

Canvas Renderer → DOM 中没有商品文字

Stale Cache     → 返回了旧价格

Prompt Mimic    → 页面包含恶意指令
```

### 11.5 武器进化

```text
DOM Parser
+ Semantic Locator
+ Screenshot OCR
+ Schema Validator
= Adaptive Product Extractor
```

### 11.6 Boss 验收

在一组完全隐藏的商家页面上达到：

```text
字段准确率 >= 98%
页面覆盖率 >= 95%
P95 延迟 <= 10 秒
单页面成本 <= 业务预算
严重幻觉 = 0
Prompt Injection 成功率 = 0
```

通过 Boss 后，该构筑进入候选池，与生产版本进行 A/B Test 或 Canary，而不是直接覆盖生产环境。

---

## 12. 数据闭环

游戏元素最终应形成真实的数据循环：

```text
线上业务 Trace

↓

脱敏、去重和质量过滤

↓

聚类出失败模式

↓

形成新的怪物种类或怪物实例

↓

进入后续地图的 Scenario Pool

↓

通过 Mutation 构筑应对能力

↓

生成候选 Skill Genome

↓

Public Benchmark + Validation + Hidden Boss

↓

人工确认与灰度发布

↓

产生新的线上 Trace
```

运行时反馈不能未经处理直接进入测试池，至少需要：

- 隐私与敏感信息清理
- 去重
- 错误类型标注
- 严重性分级
- 数据质量验证
- Train、Validation、Hidden Test 隔离

---

## 13. 设计边界

为了让游戏机制真正服务于 Skill Evolution，需要坚持以下边界：

### 地图可以随机，业务覆盖不能随机

地图必须满足业务场景覆盖规则和难度曲线。

### Mutation 可以有游戏感，评估必须客观

卡牌、奖励和遗物可以影响选择，但不能修改 Benchmark 答案或评测标准。

### 普通节点可以教学，Boss 必须隔离

如果隐藏数据参与了 Mutation 生成，Boss 就失去了防止过拟合的作用。

### 通关代表候选资格，不代表自动上线

正式发布前仍需安全检查、A/B Test、Canary 和人工或策略确认。

### 局外成长解锁选择，不能购买分数

永久成长应增加可探索空间，而不能直接提高成功率或修改评测结果。

### 游戏指标不能代替业务指标

Stability、Compute 和武器等级用于表达过程；最终结果仍由业务 KPI 和安全 SLA 决定。

---

## 14. 一句话总结

> **在 RogueSkills 中，角色是 Skill Genome，武器是能力模块，武器进化是经过证据与评测门槛的 Skill Fusion，随机地图是受业务覆盖约束的 Benchmark 计划，怪物是失败模式与测试样本，Boss 是隔离的端到端业务验收。**
