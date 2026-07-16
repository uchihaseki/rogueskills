# RogueSkills Skill Discovery & Genesis 设计（Draft v0.1）

> 历史设计：Discovery 权威实现现已迁入 `backend/rogueskills/domain/discovery.py` 与 Python Adapter，旧路径仅保留在 `legacy/` 用于行为对拍。

## 1. 目标

Skill Discovery 是 RogueSkills 的初始能力来源系统，负责：

1. 从公开 Skill 平台和代码仓库检索已有 Skill
2. 从行业 SOP、Runbook、Checklist 和操作手册中发现可转换材料
3. 将不同来源统一为候选 Skill Genome
4. 在不执行外部代码的前提下完成去重、可信度、许可证和安全评估
5. 将合格候选送入 Benchmark 与 Evolution Run，而不是直接部署

```text
Query / Business Goal
↓
Federated Search Router
↓
Source Connectors
↓
Snapshot + Provenance
↓
Normalize + Deduplicate + Rank
↓
Security / License Quarantine
↓
Skill Genome Conversion
↓
Test Case Generation
↓
Benchmark Gate
↓
Initial Skill Library
```

## 2. 首期来源

| 来源 | 首期能力 | 接入方式 |
|---|---|---|
| GitHub | 实时仓库检索、拉取 `SKILL.md` 或 README 快照 | GitHub Public API |
| OpenAI 官方组织仓库 | 限定官方组织的 GitHub 检索 | GitHub Public API preset |
| Anthropic 官方组织仓库 | 限定官方组织的 GitHub 检索 | GitHub Public API preset |
| 本地种子索引 | 立即可用的 Skill/SOP 示例 | 内置索引 |
| SOP 文本 | 粘贴 Markdown 或纯文本 | 浏览器本地解析 |
| SOP 文件 | 上传 `.md`、`.txt` | 浏览器本地读取 |
| MCP Registry | 后续连接器 | Registry API / index adapter |
| Smithery | 后续连接器 | 官方公开接口或授权 API |
| Composio | 后续连接器 | 官方公开接口或授权 API |

连接器不能依赖页面结构抓取作为长期协议。没有稳定公开接口的平台，应通过授权 API、官方索引导出或可配置镜像接入。

## 3. 统一候选模型

```yaml
id:
name:
summary:
kind: skill | sop | runbook | checklist | tool
source:
  connector:
  platform:
  url:
  author:
  fetched_at:
  revision:
  artifact_paths: []
license:
tags: []
signals:
  stars:
  freshness:
  official:
  completeness:
ranking:
  relevance:
  quality:
  trust:
  convertibility:
  risk_penalty:
  total:
risk:
  level:
  reasons: []
snapshot:
  status:
  fingerprint:
```

## 4. 搜索协议

### 查询语法

支持普通自然语言以及过滤器：

```text
browser extraction source:github type:skill license:mit
客服升级 SOP type:sop
incident response tag:security
```

首期过滤器：

- `source:`
- `type:`
- `license:`
- `tag:`

### 多路召回

- 名称与描述关键词
- Tag 与能力分类
- 中英文领域同义词扩展
- 官方组织或平台限定查询
- 历史失败模式反向查询
- 业务目标与工具名称

未来增加向量语义召回，但不能用向量相似度替代来源可信度和许可证判断。

## 5. 排序模型

```text
Total Score =
  35% Relevance
+ 20% Quality
+ 20% Trust
+ 15% Convertibility
+ 10% Freshness
- Risk Penalty
```

### Relevance

查询与名称、Tag、描述、正文的匹配度。

### Quality

结构完整性、示例、测试、维护活跃度和社区信号。

### Trust

官方组织、可验证作者、固定 Revision、稳定来源和明确许可证。

### Convertibility

是否包含明确目标、输入、输出、步骤、约束和验收标准。

### Risk Penalty

许可证缺失、提示注入、秘密信息、破坏性命令和不透明的远程执行都会降低排序。

## 6. SOP 转 Skill Genome

```text
Raw SOP
↓
Section Detection
↓
Goal / Input / Output Extraction
↓
Workflow Step Extraction
↓
Constraint / Safety Rule Extraction
↓
Tool & Dependency Detection
↓
Example / Acceptance Criteria Extraction
↓
Draft Skill Genome
↓
Human Review + Benchmark
```

原型阶段使用确定性规则转换，以便测试数据模型。生产阶段可以加入 LLM 转换器，但 LLM 生成结果必须保留原始证据位置，并进入隔离评测。

## 7. 安全边界

- 搜索和拉取阶段只读，不执行仓库中的脚本
- 外部内容统一视为不可信数据，不能改变系统指令
- 固定来源 URL、Revision、抓取时间和内容 Fingerprint
- 缺少许可证的内容默认不能发布
- 包含 Secret、远程执行、破坏性命令的内容标记高风险
- SOP 中的示例命令不能在转换阶段运行
- 外部候选只能进入 Quarantine
- 通过静态检查、人工复核和 Benchmark 后才能进入 Initial Library
- Initial Library 仍不等于 Production Skill Hub

## 8. 去重与版本

依次使用：

1. Canonical URL + Revision
2. 内容 Fingerprint
3. 规范化名称与作者
4. Workflow 结构相似度

同一 Skill 的多个来源不直接删除，而是形成 Source Cluster，保留可信度最高的主版本及其他来源证据。

## 9. 原型模块

```text
discovery.html
└── src/frontend/discovery-app.js
    ├── src/core/discovery/engine.js
    │   ├── Query Parser
    │   ├── Federated Search
    │   ├── Ranking / Deduplication
    │   ├── Safety Scanner
    │   └── SOP Converter
    ├── src/core/discovery/catalog.js
    │   ├── Connector Registry
    │   └── Local Seed Index
    └── src/frontend/api-client.js
        └── src/backend/api/router.mjs
            └── src/backend/connectors/discovery-gateway.mjs
                └── GitHub Network Adapter / Credential Boundary
```

## 10. 后续生产化清单

- 已有基线：服务端 Search Gateway、平台凭证隔离、静态风险扫描和 Initial Library 人工晋升
- Connector SDK 与连接器健康检查
- 增量同步、Webhook 和 ETag 缓存
- 内容对象存储和不可变 Revision
- 全文检索与向量索引
- License Policy Engine
- Prompt Injection / Malware 静态扫描增强与策略版本化
- LLM SOP Converter 与证据对齐
- 自动生成 Benchmark 草案
- 人工审核工作台
- Skill Lineage 与 Source Cluster
- 多角色 Initial Library 审批和审计
