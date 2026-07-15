# RogueSkills 原型开发设计与文档清单

## 1. 原型目标

第一版要验证的不是完整 Skill 生态，而是一个最小、可玩的 Skill Evolution Run：

```text
选择基础 Skill
→ 生成 Seed 地图
→ 选择业务场景节点
→ 对抗失败模式
→ 获得三选一 Mutation
→ 形成能力构筑与武器进化
→ 挑战隐藏 Boss
→ 输出候选版本或失败 Replay
```

评估器已经升级为可复现、逐用例、可解释并可落库的确定性 Benchmark Runner。它当前基于 Skill Capability 与场景契约执行，未来可以通过相同结果协议接入真实 LLM 和 Tool Runtime。

## 2. 开发文档清单

| 优先级 | 文档 | 目的 | 原型状态 |
|---|---|---|---|
| P0 | 产品范围与验收标准 | 明确第一版做什么、不做什么 | 本文已包含 |
| P0 | 核心概念映射 | 定义角色、武器、地图、怪物与 Skill 概念 | `roguelike-skill-mapping.md` |
| P0 | Run 状态机 | 定义节点选择、评估、奖励、死亡与通关 | 本文已包含 |
| P0 | 核心数据模型 | 定义 Run、Map、Monster、Mutation、Evolution | 代码配置 + 本文 |
| P0 | 评估协议 | 定义能力、难度、成本、伤害与通过条件 | 本文已包含 |
| P0 | 内容配置规范 | 让怪物、Mutation 和进化配方数据驱动 | `src/catalog.js` |
| P0 | 原型交互说明 | 定义单局主界面和操作反馈 | 本文已包含 |
| P0 | 测试与可复现规范 | 固定 Seed、引擎单测、Replay | `tests/engine.test.js` |
| P0 | Benchmark Runner | 确定性场景用例与 Initial Library 准入 | 已实现 |
| P0 | Skill Genome Schema | Prompt、Workflow、Capabilities 与 Provenance | Schema 1.0 已实现 |
| P0 | 持久化与版本谱系 | Skill、版本、来源快照和评估记录 | SQLite 已实现 |
| P0 | Search Gateway | 服务端搜索、缓存、凭证与 Repository API | 已实现 |
| P1 | Runtime Adapter | 接入真实 LLM、工具和数据集 | 待实现 |
| P1 | 安全与数据治理 | 脱敏、Train/Validation/Hidden Test 隔离 | 静态安全已实现，数据集隔离待实现 |
| P2 | 内容生产工具 | 可视化编辑怪物、地图和 Mutation | 待设计 |
| P2 | 多业务职业扩展 | Research、Support、Coding 等职业 | 待设计 |
| P2 | 灰度发布与线上反馈 | Canary、A/B Test、Runtime Trace 回流 | 待设计 |

## 3. MVP 范围

### 本轮实现

- Browser Skill 角色及其初始 Skill Genome
- 稳定、竞速、节能三种 Run 目标
- 三幕带 Seed 的随机地图
- 普通遭遇、精英、实验室、休息和 Boss 节点
- 失败模式驱动的怪物目录
- 可复现的评估结果
- Stability、Compute、Complexity 三类资源
- 三选一 Mutation Draft
- Mutation 的收益、代价、标签和稀有度
- 基于标签配方的武器进化
- 通关、死亡、重新开始
- Run 日志与浏览器本地存档
- Skill Discovery 工作台
- GitHub 与官方组织仓库搜索适配器
- SOP/Runbook/Checklist 到 Skill Genome 的转换
- 隔离候选库、来源追踪和风险扫描
- Skill Genome JSON Schema 1.0
- SQLite Repository、版本、快照和评估记录
- Initial Skill Library 准入和人工晋升
- 服务端 Search Gateway
- Evolution Run 从 Initial Library 选择基础 Skill
- 确定性多用例 Benchmark Runner

### 本轮不实现

- 真实 LLM 和工具执行
- 用户账号、权限与多租户数据库
- Skill 自动部署
- Marketplace 和多人排名
- 在线 Trace 数据回流
- 自动生成真实 Prompt/Workflow 补丁

## 4. 模块划分

```text
index.html
└── src/app.js                 UI 与交互编排
    ├── src/engine.js          Run 状态机和领域逻辑
    ├── src/catalog.js         怪物、Mutation、进化配方和职业配置
    └── src/random.js          Seed 随机数与通用纯函数
```

### Catalog

只保存静态内容配置，不包含状态变化逻辑。未来可以替换为后端内容服务。

### Engine

使用纯函数接收 Run State 并返回新的 Run State，负责：

- 地图生成
- 节点选择
- 遭遇评估
- 资源结算
- Mutation Draft
- Mutation 应用
- 武器进化检测
- Act 切换、死亡和通关

### App

负责：

- 把 Run State 渲染成界面
- 将用户操作转交给 Engine
- 保存和恢复本地 Run
- 展示指标、构筑、进化配方和 Replay

UI 不直接计算评估结果或修改业务规则。

## 5. Run 状态机

```text
SETUP
  ↓ startRun
CHOOSE_NODE
  ↓ enterNode
ENCOUNTER
  ↓ resolveNode
  ├── REST → CHOOSE_NODE
  ├── DEAD → DEFEAT
  ├── BOSS PASS → NEXT_ACT / VICTORY
  └── NORMAL / ELITE / LAB → REWARD
                                  ↓ chooseMutation
                             CHOOSE_NODE
```

关键约束：

- 每个状态转换都写入 Run Log
- 相同 Seed、节点和构筑得到相同评估结果
- Hidden Boss 不参与 Mutation Draft
- 死亡不会修改初始 Skill

## 6. 核心数据模型

### Run State

```yaml
id:
seed:
status:
phase:
mode:
actIndex:
layerIndex:
stability:
compute:
complexity:
stats: {}
mutations: []
evolutions: []
completedNodes: []
encounterHistory: []
logs: []
```

### Monster

```yaml
id:
name:
failureMode:
requirements: {}
severity:
description:
businessExample:
```

### Mutation

```yaml
id:
name:
category:
rarity:
tags: []
complexityCost:
effects: {}
benefit:
tradeoff:
```

### Evolution Recipe

```yaml
id:
name:
tagRequirements: {}
effects: {}
description:
```

## 7. 原型评估协议

原型用七个能力维度表达 Skill：

- Quality：任务输出质量
- Robustness：异常与失败恢复能力
- Speed：执行速度
- Efficiency：成本效率
- Security：安全和权限约束能力
- Vision：视觉页面能力
- Structure：结构化输出与校验能力

每个怪物使用不同权重组合这些能力。节点难度、目标模式和固定 Seed 波动共同产生本次评估结果。

输出指标包括：

- Coverage：业务验收条件覆盖率
- Quality：质量得分
- P95 Latency：模拟延迟
- Compute Cost：本次消耗
- Stability Damage：失败伤害

普通节点 Coverage 达到 70 通过，精英达到 74，Boss 达到 78。严重安全场景还要求最低 Security。

## 8. 交互界面

单局界面包含五个区域：

1. 顶部 Run 状态：幕、Stability、Compute、Complexity
2. 左侧 Skill 构筑：基础武器、Mutation、已完成进化
3. 中间随机地图：显示当前层的路线选择与节点状态
4. 右侧场景面板：怪物、业务案例、评估结果或三选一奖励
5. 底部 Run Log：完整的选择、评估和进化记录

## 9. 验收标准

- 输入相同 Seed 开始两局，地图内容一致
- 同一构筑挑战同一节点，评估结果一致
- 不同 Mutation 会真实改变能力、成本和复杂度
- 标签满足配方时自动触发且只触发一次进化
- Stability 归零后不能继续选择节点
- 通过第三幕 Boss 后进入 Victory
- 刷新页面能够恢复未完成的 Run
- 核心 Engine 测试全部通过

## 10. 下一阶段接口

未来接入真实执行器时，`resolveEncounter` 应被拆为：

```text
Run Engine
  ↓ EvaluationRequest
Benchmark Adapter
  ↓ execute Skill Genome against Scenario Pack
LLM / Tool Runtime
  ↓ Trace + Output
Metric Evaluator
  ↓ EvaluationResult
Run Engine
```

只要真实适配器返回与原型一致的 `EvaluationResult`，地图、奖励、进化和 UI 都无需重写。
