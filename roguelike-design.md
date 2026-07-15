# RogueSkills —— Skill 肉鸽化产品设计（Draft v0.1）

> **定位**
>
> RogueSkills 不是让系统自动寻找一个全局最高分的 Skill，而是让人和 Agent 在有限资源、随机挑战与高风险选择中，构筑出适合不同任务环境的 Skill 变体。

---

## 1. 设计背景

现有的 `design.md` 已经具备以下核心能力：

- Skill Genome
- Mutation
- Benchmark
- Skill Tree
- Skill Fusion
- Ranking
- Runtime Feedback

这些能力构成了很好的“进化系统”，但目前更像自动优化平台，还缺少真正的肉鸽体验：

- 没有清晰的单局边界
- 没有随机路线和遭遇
- 缺少玩家主动选择
- Mutation 普遍只有收益，缺少代价
- 没有资源限制和构筑容量
- 失败不会结束一局，也没有重开的意义
- 系统总是选择最高分版本，缺少不同流派和适用场景

RogueSkills 的肉鸽化目标，是把 Skill Evolution 转换为一个可重复、可构筑、可失败、可复盘的 Run。

---

## 2. 核心设计原则

### 2.1 每一局都是一次独立实验

每个 Run 从生产 Skill 的只读副本开始。在通关并完成发布验证之前，任何 Mutation 都不能直接覆盖生产版本。

### 2.2 随机性制造问题，选择决定构筑

系统随机生成地图、挑战条件和奖励候选，但最终由玩家或 Agent 决定路线与 Mutation。

### 2.3 每个强化都必须有代价

Mutation 不能只是单向增加成功率。它可能提高鲁棒性，同时增加延迟、成本、复杂度或工具依赖。

### 2.4 不存在全局最强 Skill

不同构筑分别追求高成功率、低延迟、低成本、高确定性或复杂任务能力。系统保留多目标下的最优解，而不是只保留一个总分最高的版本。

### 2.5 失败产生知识，而不是污染生产环境

失败的构筑会被丢弃，但失败样本、Replay、解锁项和发现的组合关系可以保留，成为局外成长的一部分。

---

## 3. 核心游戏循环

```text
选择初始 Skill / 职业

↓

生成带随机种子的地图

↓

选择路线并进入 Benchmark 遭遇

↓

执行当前 Skill Genome

↓

根据成功、失败、成本和延迟结算

↓

从三个 Mutation 中选择一个

↓

形成新的 Skill 构筑

↓

继续冒险 / 主动撤离 / 挑战 Boss

↓

隐藏测试与发布验证

↓

保存候选版本或结束本局
```

一次 Run 的核心感受应该是：

> “我不知道下一场会遇到什么，但我能根据已有资源和构筑方向做出有风险的选择。”

---

## 4. 系统概念与肉鸽机制映射

| Skill 系统概念 | 肉鸽机制 |
|---|---|
| Skill Genome | 角色基础属性与当前构筑 |
| Mutation | 卡牌、升级或能力选择 |
| Benchmark | 战斗遭遇 |
| Hidden Test | Boss 战 |
| Runtime Failure | 敌人攻击或负面状态 |
| Skill Fusion | 卡牌组合或高级技能合成 |
| Skill Tree | 单局进化路线与构筑历史 |
| Skill Repository | 角色、卡牌和遗物图鉴 |
| Ranking | 通关评分与构筑档案 |
| Compute / Token Budget | 金币、法力或行动资源 |
| Robustness / Integrity | 生命值或稳定性 |
| Context / Tool Limit | 卡槽与构筑容量 |
| Evolution Queue | 后续可能遇到的挑战池 |

---

## 5. 单局结构

建议每个 Run 分为三幕，每幕逐渐增加任务难度和环境压力。

### 第一幕：建立基础能力

主要测试：

- 输出格式
- 简单指令遵循
- 基础工具调用
- 常规错误处理
- 低复杂度任务

目标是让玩家确定本局的初步构筑方向。

### 第二幕：形成专精流派

主要测试：

- 多步骤工作流
- 视觉或浏览器任务
- 并行执行
- 长上下文
- 工具异常和回退

这一阶段开始出现稀有 Mutation、Fusion 和强流派联动。

### 第三幕：极限压力测试

主要测试：

- 上下文污染
- 工具不可用
- 高延迟环境
- 成本限制
- 对抗输入
- 任务需求动态变化

玩家需要面对自己构筑的弱点，而不能只依赖最强组合。

### 最终 Boss

Boss 使用完全没有参与本局进化过程的隐藏测试集，防止 Skill 对公开 Benchmark 过拟合。

---

## 6. 地图与节点

每幕建议包含 5～8 个节点，并提供 2～3 条可选路线。

### 6.1 普通挑战

- 使用公开 Benchmark
- 难度较低
- 奖励普通 Mutation 和少量 Compute
- 适合修正构筑短板

### 6.2 精英挑战

- 带有额外环境限制或更复杂任务
- 失败惩罚更高
- 奖励稀有 Mutation、遗物或更高容量

### 6.3 随机事件

可能发生：

- 免费升级一个 Mutation
- 删除一个 Mutation
- 用成本换取稀有能力
- 接受临时负面状态换取长期收益
- 发现新的失败样本或隐藏测试线索

### 6.4 实验室

- 融合两个兼容 Mutation
- 改变 Mutation 标签
- 重构 Prompt 或 Workflow
- 将普通能力升级为流派核心能力

### 6.5 商店

可以使用 Compute：

- 购买 Mutation
- 删除低价值 Mutation
- 重抽奖励
- 修复稳定性
- 购买一次性测试辅助道具

### 6.6 休息节点

玩家二选一：

- 恢复稳定性
- 冒险升级一个 Mutation

### 6.7 Boss 节点

- 使用隐藏测试集
- 失败造成大量稳定性损失或直接结束本幕
- 通过后获得流派级奖励，并进入下一幕

---

## 7. 单局资源

### 7.1 Stability / Integrity

代表当前 Skill 构筑的稳定程度，相当于生命值。

以下情况会损失稳定性：

- Benchmark 失败
- 出现严重幻觉
- 输出不符合 Schema
- 工具调用进入死循环
- 超出硬性成本或延迟限制
- 在关键测试中产生不可恢复错误

稳定性归零时，本局失败。

### 7.2 Compute

代表单局可用的计算与实验预算，用于：

- 执行额外评测
- 重抽 Mutation
- 在商店购买能力
- 进行 Fusion
- 修复或重构 Skill

### 7.3 Complexity

代表构筑容量。Prompt、Workflow、Tool、Memory、Planner 等 Mutation 都会占据复杂度。

复杂度接近上限时：

- 维护性下降
- 冲突概率上升
- 调试难度增加
- 可能受到额外稳定性惩罚

这可以防止玩家无限叠加所有能力。

### 7.4 Slots

部分能力受到槽位限制，例如：

- Tool Slots
- Memory Slots
- Planner Slots
- Relic Slots

槽位比简单的数值上限更适合表达互斥选择。

---

## 8. Mutation 卡牌设计

每个 Mutation 应至少包含：

```yaml
id: retry_guard
name: Retry Guard
rarity: uncommon
category: workflow
tags:
  - robustness
  - retry

effects:
  success_rate: +8%
  robustness: +12%
  latency: +18%
  token_cost: +10%

complexity_cost: 1

requires: []

conflicts:
  - minimalist

upgrade_to: retry_guard_plus
```

### Mutation 类别

- Prompt Mutation：改写、压缩、扩展、增加约束
- Workflow Mutation：规划、反思、回退、重试、并行
- Tool Mutation：增加、替换或组合工具
- Example Mutation：Few-shot、失败样本、反例
- Memory Mutation：缓存、长期记忆、上下文压缩
- Planner Mutation：任务拆解、检查、重新规划
- Constraint Mutation：Schema、预算、超时、权限边界

### 收益与代价示例

- 深度反思：提高复杂任务成功率，但增加成本和延迟
- 并行搜索：提高速度和覆盖率，但消耗更多工具调用
- 强制结构化输出：提高确定性，但降低开放任务表现
- 激进缓存：降低成本，但可能读取过期信息
- 视觉回退：提高动态页面鲁棒性，但依赖视觉模型
- Prompt 压缩：降低成本，但可能遗漏长尾约束

---

## 9. 构筑流派与标签联动

Mutation 使用标签形成组合。当同类标签达到特定数量时，可以触发套装效果或 Fusion。

### 9.1 坚韧流

```text
Retry Guard
+ Error Classification
+ Exponential Backoff
+ Fallback Tool
= Resilient Executor
```

特点：成功率和鲁棒性高，但延迟与成本较高。

### 9.2 极速流

```text
Prompt Compression
+ Parallel Search
+ Early Exit
+ Aggressive Cache
= Speed Runner
```

特点：延迟低、吞吐量高，但复杂任务与长尾场景风险较大。

### 9.3 规划流

```text
Task Decomposition
+ Planner
+ Reflection
+ RePlanning
= Autonomous Planner
```

特点：适合复杂的多步骤任务，但 Token 和 Compute 消耗较大。

### 9.4 视觉流

```text
Screenshot
+ OCR
+ Visual Locator
+ Browser Fallback
= Vision Browser
```

特点：适合动态网页和非结构化界面，但需要视觉模型与额外工具。

### 9.5 结构化流

```text
Output Schema
+ Self Validation
+ Repair Loop
+ Deterministic Template
= Reliable Formatter
```

特点：输出稳定、易于系统集成，但开放性和创造性受到限制。

---

## 10. 遗物系统

遗物不直接修改 Skill 内容，而是改变 Run 的规则或 Mutation 之间的互动。

示例：

### Visual Memory

连续两次使用视觉工具后，下一次 OCR 的 Compute 成本降低 40%。

### Failure Notebook

每幕第一次 Benchmark 失败不会损失稳定性，但该失败样本会进入后续测试集。

### Minimalist Seal

当 Complexity 不超过上限的一半时，所有任务延迟降低 15%。

### Parallel Core

并行类 Mutation 少消耗一个 Complexity，但失败时额外损失稳定性。

遗物应该促进不同玩法，而不是提供无条件的全局数值加成。

---

## 11. 评分与多目标选择

原始设计中的 `Select Highest Score` 应调整为多目标选择。

可以保留以下基础指标：

- Success Rate
- Robustness
- Cost
- Latency
- Maintainability
- Determinism
- Hallucination Rate
- Retry Count

但不同 Run 可以使用不同权重：

### 稳定模式

成功率和鲁棒性权重最高。

### 竞速模式

延迟和吞吐量权重最高。

### 节能模式

成本和工具调用次数权重最高。

### 极限模式

复杂任务质量和长程规划能力权重最高。

### 每日挑战

由系统使用固定 Seed，随机指定目标、禁用能力和环境条件，使所有玩家面对相同挑战。

最终 Repository 应保留 Pareto 最优构筑，而不是只保留一个全局最高分版本。

---

## 12. 死亡、撤离与发布

### 12.1 本局失败

当稳定性归零或关键 Boss 失败时：

- 丢弃本局生成的可执行 Skill 分支
- 不影响生产版本
- 保存完整 Run Replay
- 保存失败样本和构筑统计
- 记录 Mutation 之间的冲突与协同

### 12.2 主动撤离

玩家可以在 Boss 前主动结束本局：

- 保留当前构筑为实验候选
- 不获得正式通关资格
- 可以用于离线分析或后续人工修改

这形成“继续冒险还是见好就收”的风险收益选择。

### 12.3 通关发布

通过最终 Boss 后，构筑不会自动替换生产 Skill，而是进入候选发布池：

```text
Run 胜利

↓

Hidden Test 通过

↓

安全与权限检查

↓

与生产版本 A/B Test

↓

人工确认或发布策略确认

↓

部署 / 保留为场景化版本 / 放弃
```

---

## 13. 局外成长

局外成长应该解锁更多选择，而不是永久提高成功率。

可以解锁：

- 新的基础 Skill / 职业
- 新的 Mutation 卡池
- 新的 Benchmark 区域
- 新的精英和 Boss
- 新的遗物
- 新的 Fusion 配方
- 更多开局路线候选
- 更详细的失败分析能力

不建议设计：

- 永久增加 10% 成功率
- 永久降低所有 Skill 成本
- 让老玩家天然拥有更高 Benchmark 分数

否则游戏成长会污染 Skill 的客观评测。

---

## 14. 示例 Run：Browser Skill

### 初始状态

```text
Skill：Browser V1
Stability：10
Compute：100
Complexity：0 / 6
Tool Slots：2
Relic Slots：2
```

### 第一场挑战

任务：从动态网页中提取商品价格。

通过后出现三个 Mutation：

1. Retry Guard：失败时自动重试，但延迟上升
2. Screenshot OCR：增加视觉回退，但占用两个 Complexity
3. Prompt Compression：降低成本，但鲁棒性下降

玩家选择 `Screenshot OCR`。

### 精英挑战

任务：从 Canvas 渲染的页面中识别商品信息。

视觉构筑发挥作用，挑战成功并获得遗物：

```text
Visual Memory：
连续两次使用视觉工具后，下一次 OCR 成本降低 40%。
```

### 最终 Boss

任务：完成一个此前从未公开的跨站商品比较任务，同时受到延迟与成本限制。

通过后，这个 Browser 构筑进入候选发布池，并与当前生产版本进行 A/B Test。

---

## 15. 核心数据模型

### 15.1 Run State

```yaml
run_id:
seed:
status:
base_skill_version:
current_genome:
act:
current_node:
stability:
compute:
complexity:
slots:
mutations: []
relics: []
encounter_history: []
mutation_history: []
metrics:
```

### 15.2 Map Node

```yaml
node_id:
act:
type:
difficulty:
benchmark_pack:
modifiers: []
rewards: []
next_nodes: []
```

### 15.3 Encounter

```yaml
encounter_id:
benchmark_cases: []
environment_modifiers: []
success_conditions: []
hard_limits:
  token_cost:
  latency:
  tool_calls:
damage_rules:
reward_rules:
```

### 15.4 Mutation

```yaml
mutation_id:
name:
category:
rarity:
tags: []
effects: {}
tradeoffs: {}
complexity_cost:
requires: []
conflicts: []
upgrade_to:
fusion_recipes: []
```

所有随机过程都必须记录 Seed，保证 Run 可以完整重放。

---

## 16. MVP 范围

第一版的目标不是完成整个 Skill Ecosystem，而是验证：

1. Skill 构筑是否具有有意义的选择
2. 不同构筑是否真的产生不同性能特征
3. 隐藏测试是否能阻止 Benchmark 过拟合
4. 失败、重开和复盘是否能产生新的有效版本

建议 MVP 只实现：

- 1 个基础 Skill：Browser 或 Research
- 3 幕随机地图
- 20～30 个 Mutation
- 4 种节点：普通挑战、精英、实验室、Boss
- 3 种资源：Stability、Compute、Complexity
- 3 个可识别的构筑流派
- 5～8 个遗物
- 固定随机种子与完整 Replay
- 一个公开 Benchmark 集
- 一个隔离的 Hidden Test 集
- 通关版本候选池
- 人工确认后的 A/B Test，不自动覆盖生产版本

暂不实现：

- 全互联网 Skill Discovery
- Marketplace
- 多 Agent Skill 共享
- 无人监管的在线自动发布
- 大规模社区排名

---

## 17. 与原架构的关系

原有架构可以继续作为底层“Skill Evolution Engine”，本设计在其上增加“Roguelike Run Engine”。

```text
Roguelike Run Engine

├── Seeded Map Generator
├── Encounter Engine
├── Resource System
├── Mutation Draft
├── Build Synergy
├── Relic System
├── Run Replay
└── Victory / Death / Extraction

            ↓

Skill Evolution Engine

├── Skill Genome
├── Mutation
├── Benchmark
├── Selection
├── Fusion
└── Version Tree

            ↓

Skill Repository / Runtime / Feedback
```

Roguelike 层负责制造选择和单局体验；Evolution 层负责真正执行 Mutation、评测和版本管理。两者应该保持解耦。

---

## 18. 一句话总结

> **RogueSkills 是一个以真实 Benchmark 为战斗、以 Skill Mutation 为构筑、以隐藏测试为 Boss、以版本候选为战利品的 Skill 进化肉鸽系统。**
