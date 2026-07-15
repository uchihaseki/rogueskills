# SkillForge —— 可进化 Skill 生态系统（Architecture Draft v0.1）

> **Vision**
>
> 将 Skill 从静态 Prompt / Workflow 升级为可持续进化的软件资产（Evolving Skill），构建一个能够自主学习、自主优化、自主评级的 Skill Ecosystem，为 Agent 提供持续增强的能力。

---

# 1. 项目背景

目前绝大多数 Agent Framework（OpenAI Skills、Claude Skills、MCP、Composio 等）中的 Skill 都属于静态资源。

它们具有以下特点：

* 人工编写
* 人工维护
* 人工升级
* 一旦发布几乎不会持续优化

因此，不同来源的 Skill 质量参差不齐，Agent 通常无法判断：

* 哪个 Skill 最稳定？
* 哪个 Skill 成功率最高？
* 哪个版本性能最好？
* 哪个 Skill 已经过时？

本项目希望解决的问题是：

> **Skill 不应该是一次性的产物，而应该像生命一样持续进化。**

---

# 2. 核心思想

整个系统遵循四个原则：

```
Discover
    ↓
Evaluate
    ↓
Evolve
    ↓
Deploy
```

Skill 的生命周期：

```
Internet

↓

Collect

↓

Evaluate

↓

Evolution

↓

Rank

↓

Deploy

↓

Runtime Feedback

↓

Evolution Again
```

形成持续闭环。

---

# 3. 整体架构

```
                    ┌────────────────────────────┐
                    │      Skill Sources         │
                    │────────────────────────────│
                    │ OpenAI Skills             │
                    │ Claude Skills             │
                    │ MCP Registry              │
                    │ Github                    │
                    │ Awesome Lists             │
                    │ Smithery                  │
                    │ Composio                  │
                    └──────────────┬────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │     Skill Discovery        │
                    └──────────────┬────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │     Skill Normalizer       │
                    └──────────────┬────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │    Skill Repository        │
                    └──────────────┬────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
          Benchmark Engine             Evolution Engine
                     │                           │
                     └─────────────┬─────────────┘
                                   ▼
                           Skill Ranking
                                   │
                                   ▼
                          Production Skill Hub
                                   │
                                   ▼
                              Agent Runtime
                                   │
                                   ▼
                           Runtime Feedback
                                   │
                                   └──────────────┐
                                                  ▼
                                            Evolution Queue
```

---

# 4. 系统模块设计

---

## 4.1 Skill Discovery

负责从多个开放平台持续收集 Skill。

### 数据来源

* OpenAI Skills
* Claude Skills
* MCP Registry
* GitHub
* Awesome Lists
* Smithery
* Composio
* HuggingFace Space（未来）

---

### 功能

自动：

* 搜索
* 下载
* 更新
* 去重
* 分类
* 建立索引

输出统一格式：

```yaml
id:
name:
description:
author:
source:
category:
downloads:
likes:
stars:
last_update:
version:
dependencies:
```

---

## 4.2 Skill Normalizer

由于不同平台 Skill 格式不同，因此需要统一。

例如统一为：

```
Skill

├── Metadata
├── Prompt
├── Workflow
├── Examples
├── Constraints
├── Tool Definition
├── Input Schema
├── Output Schema
└── Test Cases
```

Normalizer 不关注来源，只关注能力描述。

最终形成统一 Skill DSL。

---

## 4.3 Skill Repository

Repository 不保存单一 Prompt，而保存 Skill Genome。

```
Skill Genome

Metadata

Prompt

Workflow

Tools

Examples

Constraints

Evaluation

Version

Parent

Children

Mutation History

Benchmark History
```

每个 Skill 都具有完整生命周期。

---

# 5. Skill Evolution Framework

这是整个系统的核心。

Evolution =

```
Mutation

↓

Evaluation

↓

Selection
```

---

## Mutation

支持多种进化策略：

### Prompt Mutation

例如：

* Rewrite
* Compress
* Expand
* Better Instruction

---

### Workflow Mutation

例如：

```
Search

↓

Search

↓

Reflection

↓

Execute
```

或者：

```
Single Agent

↓

Planner

↓

Executor
```

---

### Tool Mutation

自动替换：

```
Playwright

↓

Browser Use

↓

Chrome MCP
```

---

### Example Mutation

自动生成：

* Few-shot
* Failure Example
* Counter Example

---

### Memory Mutation

增加：

* Long Memory
* Cache
* Context Compression

---

### Planner Mutation

自动增加：

* Reflection
* Self Check
* RePlanning

---

# 6. Skill Benchmark

任何 Evolution 必须经过 Benchmark。

Benchmark 包括：

```
Success Rate

Latency

Cost

Tool Calls

Reasoning Quality

Robustness

Determinism

Hallucination

Retry Count
```

Benchmark 分为：

```
Train

Validation

Hidden Test
```

Hidden Test 不参与 Evolution，仅用于最终评分。

---

# 7. Skill Ranking System

建立统一等级体系。

```
C

↓

B

↓

A

↓

S

↓

SS
```

评分来源：

```
40% Success Rate

20% Robustness

15% Cost

10% Latency

10% Maintainability

5% Community Score
```

达到阈值即可升级。

例如：

```
Score

65

↓

C

78

↓

B

86

↓

A

93

↓

S
```

Agent 默认调用最高等级版本。

---

# 8. Runtime Feedback

真正的进化来自真实使用。

Agent 每次执行都会记录：

```
Task

↓

Skill Used

↓

Trace

↓

Success

↓

Failure

↓

Latency

↓

Token Usage
```

失败案例进入：

```
Evolution Queue
```

后续自动：

```
Generate Better Skill

↓

Benchmark

↓

Replace Old Version
```

形成持续学习闭环。

---

# 9. Skill Fusion（未来版本）

除了 Mutation，还支持 Skill 合成。

例如：

```
Browser

+

OCR

↓

Vision Browser
```

或者：

```
Reflection

+

Planning

↓

Self Planning
```

Fusion 后自动 Benchmark。

只有性能提升才会保留。

---

# 10. Skill Tree

每个 Skill 都拥有自己的进化树。

```
Browser

├── Browser V1
│
├── Browser Retry
│
├── Browser Reflection
│
├── Browser Vision
│
└── Browser Cache
```

可以随时回滚。

也可以并行 Evolution。

---

# 11. Agent Runtime

Agent 调用流程：

```
Receive Task

↓

Retrieve Candidate Skills

↓

Rank

↓

Select Highest Score

↓

Execute

↓

Collect Runtime Metrics

↓

Feedback Repository
```

Agent 永远调用当前最佳 Skill。

---

# 12. 长期规划

## Phase 1

* Skill 收集
* Skill Repository
* Benchmark
* Ranking

目标：构建高质量 Skill 库。

---

## Phase 2

* 自动 Evolution
* 自动 Mutation
* 自动 Benchmark

目标：实现 Skill 自我优化。

---

## Phase 3

* Runtime Feedback
* Online Learning
* Continuous Evolution

目标：构建持续学习系统。

---

## Phase 4

* Skill Fusion
* Skill Tree
* Skill Marketplace
* Multi-Agent Skill Sharing

目标：形成可持续演化的 Skill Ecosystem。

---

# 13. 核心创新点

1. **统一 Skill 表示（Skill Genome）**

   * 将不同平台的 Skill 抽象为统一的数据结构，而非简单保存 Prompt。

2. **自动化 Skill Evolution**

   * 基于 Mutation、Benchmark 和 Selection，让 Skill 持续优化，而非依赖人工维护。

3. **数据驱动的 Skill Ranking**

   * 使用客观指标（成功率、成本、鲁棒性等）建立统一等级体系，而非依赖收藏数或点赞数。

4. **Runtime Feedback 闭环**

   * 利用 Agent 在真实任务中的执行反馈驱动下一轮进化，实现持续学习。

5. **Skill Tree 与 Skill Fusion**

   * 引入版本分支、谱系管理与技能融合机制，使 Skill 能够像软件版本和生物进化一样不断演化。

---

# 14. 一句话总结

> **SkillForge 的目标不是构建一个 Skill Library，而是构建一个能够持续发现、评估、进化和部署 Skill 的操作系统（Skill Operating System）。在这个系统中，每一个 Skill 都拥有生命周期、进化历史和能力等级，并通过真实任务反馈不断迭代，最终为 Agent 提供始终处于最优状态的能力集合。**

后续建议补充两份配套设计文档：

1. **《Skill Genome Specification》**：定义 Skill 的统一数据结构（Schema），作为整个系统的数据标准。
2. **《Evolution Engine Design》**：详细设计 Mutation、Benchmark、Selection、Rollback、A/B Test 等算法，这是整个项目最具创新性的核心。
