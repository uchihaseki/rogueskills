# RogueSkills 真实联网 Skill 搜索、预览与选择方案

> 状态：Proposal v0.2
>
> 日期：2026-07-21
>
> 范围：Skill Discovery 搜索、来源追溯、候选预览、人工选择与隔离入库
>
> 不包含：自动安装、自动执行、自动晋升 Production

> 实施进度（2026-07-21）：GitHub、Brave、Tavily、Exa Provider，Search Run/SSE、来源树、Candidate Preview、默认选择和 Import Batch 的首个纵向切片已经落地。Search Run 当前由服务端进程内任务持有，数据库持久化与 Worker 迁移仍按 M3 实施。

## 1. 结论先行

当前 Discovery **不是完全没有联网搜索**，但用户的判断基本成立：它还没有形成“真实搜索产品”的完整体验。

本版方案把“多个真实 API 搜索”设为硬性要求：首期并行接入 GitHub Search API、Brave Search API、Tavily API 和 Exa API。远程 Provider 没有配置或调用失败时必须如实展示，不得以本地种子、静态 Catalog 或缓存样例冒充互联网结果。

现有后端在选择 GitHub 来源时会调用 GitHub Public API；点击“拉取并转换”后，也会继续读取仓库树中的 `SKILL.md`，找不到时退回 README。但是当前默认只选择 `builtin` 本地种子索引，远程搜索只返回“仓库级候选”，来源过程不可见，每个仓库最多读取一个 `SKILL.md`，并且单个候选会在点击后直接转换并保存。用户无法像 Grok 搜索那样看到系统查了哪些来源、某个来源下面发现了哪些具体 Skill，也没有“预览—默认勾选—人工增删—批量确认”的中间层。

本方案建议把 Discovery 改造成以下闭环：

```text
用户描述目标
  → 创建 Search Run
  → 服务端实时搜索多个互联网来源
  → 展示搜索进度和来源命中
  → 展开来源，枚举其中的具体 Skill Artifact
  → 拉取固定 Revision 的只读快照
  → 去重、风险、许可证、质量与相关度过滤
  → 生成可解释的默认勾选
  → 用户预览并增删选择
  → 二次确认
  → 服务端重新校验所选 Candidate ID
  → 批量保存到 Quarantine Repository
```

核心原则是：**搜索结果不等于 Skill，预览不等于保存，保存不等于安装，隔离入库不等于发布。**

## 2. 当前实现审计

### 2.1 已经真实存在的能力

| 能力 | 当前实现 | 结论 |
|---|---|---|
| GitHub 联网搜索 | `DiscoveryGateway.search_github()` 请求 `https://api.github.com/search/repositories` | 真实联网，但只做仓库搜索 |
| 官方来源限定 | OpenAI、Anthropic Connector 通过 GitHub `org:` qualifier 检索 | 仍是 GitHub 搜索，不是独立平台连接器 |
| 精确仓库导入 | 支持 GitHub URL 或 `owner/repo` | 可用 |
| 内容拉取 | 导入时读取仓库 Tree，优先取 `SKILL.md`，否则取 README | 真实拉取，但最多只取一个 Skill 文件 |
| 统一排序 | 相关度、质量、可信度、可转换性、新鲜度和风险惩罚 | 已有基础模型 |
| 来源快照 | 保存 URL、Revision、Artifact Path、Fingerprint 和抓取时间 | 数据底座可复用 |
| 安全边界 | 外部候选强制进入 `quarantine`，不会自动执行 | 应继续保留 |

### 2.2 为什么用户仍会感觉是“假搜索”

| 问题 | 现状证据 | 用户影响 |
|---|---|---|
| 默认不联网 | `useDiscovery()` 默认 `sourceIds = new Set(['builtin'])`，初始化也只搜索 `builtin` | 第一次打开看到的是静态种子结果 |
| 搜索粒度错误 | GitHub Search 返回 Repository，不是 `SKILL.md` 文件 | “一个仓库”被误当成“一个 Skill” |
| 丢失子 Skill | `hydrate_candidate()` 对匹配到的 `SKILL.md` 排序后使用 `[:1]` | 多 Skill 仓库只展示、导入第一个文件 |
| 没有搜索过程 | API 一次性返回最终 JSON，没有 Search Run 或事件流 | 看不到正在查哪些站点、查到哪些来源 |
| 来源不能内联展开 | 卡片只提供“查看来源 ↗”外链 | 无法在产品内核验证据 |
| 排序基于浅层信息 | 初次排序主要使用仓库名、描述、Topic、Star | 未读正文前的质量与风险分可能失真 |
| 没有预览确认 | 点击“拉取并转换”后，`POST /api/discovery/import` 直接写 Repository | 用户还没看到正文或 Genome 就已保存 |
| 没有批量选择 | 每张卡只能单独导入 | 无法默认挑一批，再增删勾选 |
| 信任边界偏弱 | Import API 接收浏览器回传的完整 `candidate` 对象 | 字段可能被篡改，应只接受服务端 Candidate ID |
| 连接器名大于实际能力 | MCP Registry、Smithery、Composio 都是 planned | 页面看起来像跨平台搜索，实际远程能力主要只有 GitHub |
| 缓存不支持会话恢复 | Search Cache 是进程内 60 秒 TTL | 刷新后不能恢复搜索来源、进度和选择上下文 |

因此，更准确的产品描述应是：**当前已经有一个真实 GitHub Adapter 和本地候选排序原型，但还不是可解释、可预览、可人工筛选的真实互联网 Skill Discovery 工作台。**

## 3. 产品目标与边界

### 3.1 目标

1. 默认并行调用多个真实远程 Search API，并明确区分“互联网来源”和“本地示例”。
2. 实时展示搜索计划、Provider 状态、命中数量、失败、成本和限流信息。
3. 使用“来源父项 → Skill 子项”呈现仓库、网页与其中的 Skill Artifact。
4. 用户无需离开页面即可查看来源元数据、证据片段、原始内容和转换预览。
5. 系统根据明确规则默认勾选少量高质量候选，并解释选择或排除原因。
6. 用户可以勾选、取消、全选推荐项、清空选择，再统一确认。
7. 只保存最终确认的候选；每项保存结果独立返回，允许部分成功。
8. 保存前固定 Revision、重新抓取或校验 Fingerprint，避免来源漂移。
9. 所有外部内容继续只作为不可信数据处理，不执行其中的代码或指令。

### 3.2 非目标

- 不直接安装第三方 Skill 到运行环境。
- 不执行仓库内脚本、测试、安装命令或 MCP Server。
- 不因搜索分高而自动进入 Initial 或 Production。
- 不把大模型摘要当作来源证据。
- 不通过抓取 GitHub、搜索引擎或 Marketplace 的 HTML 页面建立脆弱协议。
- 第一阶段不实现没有正式 API Contract 的 Marketplace Connector；但 GitHub、Brave、Tavily、Exa 四个搜索 Provider 属于本方案首期范围。

## 4. 目标体验

### 4.1 页面布局

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 搜索：我需要一个能做上市公司基本面分析、带引用和风险检查的 Skill   [搜索] │
├──────────────────────┬───────────────────────────────────────────────┤
│ 搜索过程 / 来源       │ 候选 Skill（已选 4 / 共 17）                  │
│                      │ [仅看推荐] [全选推荐] [清空] [复核并保存 4]    │
│ ✓ GitHub API   12    │                                               │
│ ✓ Brave API     8    │ ☑ Equity Research                  推荐       │
│ ✓ Tavily API    5    │   来源 2 · SKILL.md · MIT · Low Risk          │
│ … Exa API       3    │   [展开证据] [预览]                            │
│                      │                                               │
│ ▼ 来源 github.com/a  │ ☐ Stock Picker Prompt              未推荐     │
│   ├─ skills/x/SKILL  │   未知许可证 · 高风险模式                      │
│   └─ skills/y/SKILL  │   [查看排除原因] [仍然选择]                    │
│ ▶ 来源 example.dev   │                                               │
├──────────────────────┴───────────────────────────────────────────────┤
│ 预览抽屉：来源信息 | 原文快照 | Genome Draft | 风险/许可证 | 选择原因 │
└──────────────────────────────────────────────────────────────────────┘
```

移动端将来源面板收起为“搜索过程”抽屉，候选列表和预览抽屉保持单列。

### 4.2 用户流程

#### A. 发起搜索

- 用户输入自然语言目标，也可以继续使用 `source:`、`type:`、`license:`、`tag:`。
- 默认选中已配置的真实远程 Provider，例如 GitHub Search、Brave Search、Tavily 和 Exa。
- `builtin` 改名为“本地示例”，默认不参与“互联网搜索”；用户可主动勾选。
- 页面立即创建 Search Run，不等待所有来源完成后才显示内容。

#### B. 查看搜索过程

- 左侧按时间展示：解析目标、查询改写、Provider API 开始、网页来源命中、Artifact 枚举、快照拉取、过滤完成。
- 每个真实 API Provider 显示 `running / ok / partial / rate_limited / error / skipped`。
- 部分来源失败时保留其他结果，并明确显示降级原因。
- “找到 20 个网页/仓库，识别出 13 个 Skill，过滤 5 个，推荐 4 个”必须使用不同计数，不能混称为“结果”。

#### C. 展开来源

- 父项是 `Source Hit`：仓库、网页、Registry Package 或官方索引条目。
- 子项是 `Skill Artifact`：具体的 `SKILL.md`、Skill 目录、Manifest 或可转换文档。
- 一个仓库有 8 个 `SKILL.md` 时，应显示 8 个子项，而不是只显示一个仓库候选。
- 同一 Skill 被多个来源引用时，结果卡显示“来源 3”，可展开 Source Cluster。

#### D. 预览

点击候选或“预览”打开右侧抽屉，包含：

1. 来源：平台、作者、Canonical URL、Commit SHA/Revision、抓取时间。
2. 证据：命中片段、Artifact Path、为何与查询相关。
3. 原文：经过安全渲染的只读 Markdown/Text；不加载来源页面脚本。
4. Genome Draft：名称、目标、Workflow、Inputs、Outputs、Tools、Constraints。
5. 审查：许可证、风险原因、重复项、质量维度、默认选择原因。

打开预览绝不触发保存。预览可以按需 Hydrate，以减少初始网络和 Token 成本。

#### E. 默认勾选与人工调整

- 搜索完成后系统默认勾选 3～5 个高质量且相互补充的候选。
- 推荐项显示“推荐原因”，未推荐项显示“未推荐原因”。
- 用户可以取消推荐项，也可以选择非推荐但未被硬性拦截的项。
- 高风险、许可证禁止或内容无法固定版本的候选不可默认勾选。
- 被硬性拦截的项禁用 Checkbox；需要显示可操作的原因，而不是直接从列表消失。

#### F. 复核并保存

点击“复核并保存 N 项”打开确认框：

- 列出最终选择、来源、许可证和风险等级。
- 汇总预计新增、已存在、重复合并、需要人工许可证复核的数量。
- 对显式选择的中风险项要求单独确认。
- 确认后服务端根据 Candidate ID 重新校验，不接受浏览器提交的来源内容、分数或风险字段。
- 批量保存结果逐项显示 `saved / already_exists / changed / rejected / failed`。

## 5. 信息模型：把“来源”与“候选 Skill”分开

当前一个 `DiscoveryCandidate` 同时承担仓库、内容和 Skill 三种语义。新模型应拆为四层。

### 5.1 Search Run

代表一次可恢复、可观测的搜索会话。

```json
{
  "id": "dsr_01...",
  "query": "上市公司基本面分析，带引用和风险检查",
  "state": "review_ready",
  "providerIds": ["github", "brave", "tavily", "exa"],
  "scopeIds": ["all_web_skills"],
  "includeLocalExamples": false,
  "revision": 18,
  "policyVersion": "discovery-selection-v1",
  "counts": {
    "sourceHits": 20,
    "artifacts": 13,
    "candidates": 11,
    "recommended": 4,
    "blocked": 2
  },
  "createdAt": "2026-07-21T10:00:00Z",
  "expiresAt": "2026-07-22T10:00:00Z"
}
```

### 5.2 Source Hit

代表互联网上真实命中的来源父项。

```json
{
  "id": "src_01...",
  "runId": "dsr_01...",
  "kind": "repository",
  "title": "owner/skills",
  "url": "https://github.com/owner/skills",
  "canonicalUrl": "https://github.com/owner/skills",
  "publisher": "owner",
  "revision": "4f8d...commit-sha",
  "matchedSnippets": ["financial analysis skill with cited evidence"],
  "discoveredBy": [
    { "providerId": "github", "queryId": "qry_01", "rank": 2 },
    { "providerId": "brave", "queryId": "qry_02", "rank": 6 }
  ],
  "discoveredAt": "2026-07-21T10:00:02Z",
  "status": "enumerated"
}
```

### 5.3 Skill Artifact

代表来源中的具体文件或条目，是后续快照的最小单位。

```json
{
  "id": "art_01...",
  "sourceHitId": "src_01...",
  "kind": "skill_md",
  "path": "skills/equity-research/SKILL.md",
  "rawUrl": "https://raw.githubusercontent.com/.../4f8d.../SKILL.md",
  "revision": "4f8d...commit-sha",
  "contentType": "text/markdown",
  "sizeBytes": 8421,
  "fingerprint": "sha256:...",
  "snapshotState": "captured"
}
```

### 5.4 Skill Candidate

代表经过内容读取、归一化、去重和过滤后的候选 Skill。

```json
{
  "id": "cand_01...",
  "runId": "dsr_01...",
  "primaryArtifactId": "art_01...",
  "sourceClusterIds": ["src_01...", "src_07..."],
  "name": "Evidence-first Equity Research",
  "summary": "...",
  "kind": "skill",
  "license": { "value": "MIT", "state": "allowed" },
  "risk": { "level": "low", "reasons": [] },
  "ranking": {
    "retrieval": 82,
    "content": 88,
    "final": 86,
    "explanations": ["命中目标与 Workflow", "包含引用约束和风险清单"]
  },
  "selection": {
    "eligible": true,
    "recommended": true,
    "reasonCodes": ["HIGH_RELEVANCE", "VALID_SKILL_MD", "LICENSE_ALLOWED"]
  },
  "previewState": "ready"
}
```

## 6. 多真实 API 搜索源设计

### 6.1 先区分 Search Provider 与 Web Source

“来源”在产品里有两层，不能继续混用一个 Connector 概念：

- **Search Provider**：系统实际调用的搜索 API，例如 GitHub Search、Brave、Tavily、Exa。
- **Web Source**：Provider 找到的真实网页、仓库、文件或 Registry 页面，例如 `github.com/foo/bar`。

一个网页可能同时被 Brave、Tavily 和 Exa 找到。系统应按 Canonical URL 合并成一个 `Source Hit`，同时保留发现证据：

```json
{
  "sourceHitId": "src_01...",
  "url": "https://example.com/skills/equity-research",
  "discoveredBy": [
    { "providerId": "brave", "queryId": "qry_01", "rank": 3, "snippet": "..." },
    { "providerId": "tavily", "queryId": "qry_02", "rank": 1, "snippet": "..." },
    { "providerId": "exa", "queryId": "qry_03", "rank": 5, "snippet": "..." }
  ]
}
```

Preview 中应显示“此网页由 Brave、Tavily、Exa 发现”，而不是把三个相同网页渲染成三个候选。

### 6.2 第一阶段必须接入的真实 API Provider

| Provider | 官方 API 用途 | 产出 | 必需配置 |
|---|---|---|---|
| `github` | Code Search 搜索 `SKILL.md`/Manifest；Repository Search 搜仓库；Git Tree 枚举文件 | 文件、仓库和固定 Commit 的 Raw Content | `ROGUESKILLS_GITHUB_TOKEN` |
| `brave` | 广泛网页检索，发现 GitHub 之外的 Skill 页面、博客、文档和 Registry | URL、标题、摘要、排名 | `ROGUESKILLS_BRAVE_API_KEY` |
| `tavily` | 面向研究任务的网页检索与内容摘要，用于补充长尾来源 | URL、标题、摘要、相关度信号 | `ROGUESKILLS_TAVILY_API_KEY` |
| `exa` | 语义网页检索，召回关键词不完全重合但能力相近的 Skill 页面 | URL、标题、摘要、语义相关度 | `ROGUESKILLS_EXA_API_KEY` |

这四个 Provider 都必须调用各厂商正式 API，禁止抓取它们的搜索结果网页。具体 Endpoint 和 API Version 封装在各自 Adapter 中，不能泄漏到 Domain 或前端。

建议默认并行调用所有已配置 Provider。产品验收环境至少配置 GitHub 加两个 Web Provider；生产环境建议四个都配置。任何 Provider 未配置、鉴权失败或达到限额，都必须显示真实状态，不能用 `builtin` 伪装成功。

服务端配置建议：

```dotenv
ROGUESKILLS_GITHUB_TOKEN=...
ROGUESKILLS_BRAVE_API_KEY=...
ROGUESKILLS_TAVILY_API_KEY=...
ROGUESKILLS_EXA_API_KEY=...
ROGUESKILLS_SEARCH_PROVIDER_TIMEOUT_SECONDS=12
ROGUESKILLS_SEARCH_RUN_MAX_PROVIDER_REQUESTS=16
ROGUESKILLS_SEARCH_RUN_MAX_USD=0.20
```

密钥只存在后端。Provider Health API 只返回 `configured`、`available`、`rateLimit`、`lastErrorCode` 和能力标签，不返回密钥或厂商原始错误正文。

所有 Web Provider 统一实现 provider-neutral 协议：

```python
class WebSearchProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def search(
        self,
        query: str,
        *,
        limit: int,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[WebSearchHit]: ...
```

Provider 只负责发现 URL；RogueSkills 自己负责安全抓取真实网页、识别 Skill Artifact、证据留存和评分。不同 Provider 返回的自有相关度只作为召回信号，不能直接当成最终 Skill 分数。

要求：

- 每个 Adapter 只请求厂商正式 JSON API，不抓取搜索结果 HTML 页面。
- Provider 未配置时返回 `skipped:not_configured`，UI 清晰展示；全部未配置时 Search Run 失败。
- “真实互联网模式”不得自动混入本地种子；`builtin` 只能由用户显式选择。
- 查询可能发送给第三方，首次启用时在来源设置中说明隐私边界。
- Web 命中的网页只有在识别出 Skill Artifact 或足够结构化的可转换材料后，才能生成 Candidate。
- 网页摘要只能用于召回，不能代替原始页面快照或许可证判断。
- 某 Provider 不原生支持 Domain Filter 时，Adapter 使用其正式查询语法并在返回后再次校验 Domain；不得假装厂商已经执行过滤。

### 6.3 搜索范围预设不是 Provider

当前 OpenAI、Anthropic 卡片本质上只是 GitHub `org:` qualifier，不应继续表现为独立搜索源。改为“搜索范围预设”：

| Scope Preset | 行为 |
|---|---|
| 全网 Skills | 四个 Provider 使用通用 Skill Query |
| 官方组织 | 对 GitHub 使用组织白名单；对 Web Provider 使用官方 Domain 白名单 |
| OpenAI | 搜索 `openai.com`、`platform.openai.com` 和配置的官方 GitHub 组织 |
| Anthropic | 搜索 `anthropic.com`、`docs.anthropic.com` 和配置的官方 GitHub 组织 |
| Registry | 搜索已审核的 Registry Domain 列表 |

同一个 Scope Query 应并行发给多个适用 Provider，使用户可以看到“目标网站来源”和“发现它的 API Provider”两类证据。

### 6.4 查询生成与多 Provider Fan-out

每次 Search Run 先产生可展示的 Query Plan，例如：

```json
{
  "queries": [
    { "id": "qry_01", "text": "equity research agent skill SKILL.md", "intent": "exact_skill" },
    { "id": "qry_02", "text": "fundamental analysis workflow citations risk", "intent": "capability" },
    { "id": "qry_03", "text": "stock analysis agent runbook", "intent": "adjacent_material" }
  ]
}
```

- Query Plan 默认由确定性模板、领域同义词和用户过滤器生成。
- 如后续使用 LLM 扩展 Query，生成结果也必须先展示并受数量、长度和 Domain Policy 限制。
- 每个 Provider Adapter 根据自身语法构造请求，不能把某厂商专用操作符原样发给所有 Provider。
- 每个 Query/Provider 组合都记录耗时、返回数、API Request ID（若厂商提供）和错误状态。
- 同一 Canonical URL 去重后保留全部 `discoveredBy` 记录，以支持 Grok 式来源追溯。

### 6.5 Direct URL、本地示例与后续来源

- `direct_url` 不是搜索 Provider，但允许用户精确输入 GitHub、Raw Content 或 Registry URL；仍需走安全抓取和过滤。
- `builtin` 是本地示例库，不参与默认互联网搜索、不计入 Provider 成功数，并在 UI 标记 `LOCAL DATA`。

MCP Registry、Smithery、Composio 等应在确认稳定 API 和许可证边界后分别实现 Adapter。UI 可以展示 Planned，但不能计入“可用连接器”或默认搜索范围。

### 6.6 命中网页后的真实内容抓取

Search API 返回 URL 后，RogueSkills 必须继续读取真实网页，才能形成可预览 Candidate：

1. 对 GitHub URL 优先走 GitHub API 获取 Commit SHA、Tree 和 Raw Content。
2. 对 `text/markdown`、`text/plain` 直接按大小上限读取。
3. 对 `text/html` 使用无脚本 HTTP Fetch，再进行正文抽取；不在服务端执行 JavaScript。
4. 页面只靠客户端渲染且无法获得正文时，保留 Source Hit 并标记 `content_unavailable`，不得使用搜索摘要伪造正文。
5. Provider 返回的 Extracted Content 可以作为辅助证据，但必须标记 `provider_extracted`，不能冒充 Origin Snapshot。
6. Preview 同时展示 Origin URL、抓取状态、Content Hash 和由哪个 Provider 发现。

## 7. 搜索编排与实时进度

### 7.1 为什么需要 Search Run + SSE

当前同步 `POST /api/discovery/search` 只有“等待”和“最终结果”两种状态。真实多源搜索会经历不同延迟、限流和部分失败，适合改为：

1. `POST` 创建 Search Run，立即返回 `202`。
2. 服务端异步执行 GitHub、Brave、Tavily、Exa 等 Provider Fan-out。
3. 前端通过 Server-Sent Events 接收单向进度。
4. 页面刷新后通过 Run Snapshot 恢复结果。

SSE 比 WebSocket 更适合本场景：客户端主要接收服务端事件，协议简单，断线可以使用 `Last-Event-ID` 续传。

### 7.2 状态机

```text
queued
  → planning
  → searching
  → enumerating
  → hydrating
  → filtering
  → review_ready
  → importing
  → completed
```

异常终态：

- `partial`：至少一个远程 Provider 成功，至少一个远程 Provider 失败。
- `failed`：没有远程 Provider 成功；真实互联网模式不能回退到本地种子后伪装成功。
- `cancelled`：用户主动停止。
- `expired`：Run 已超过保留期。

`review_ready` 后仍允许对单个 Candidate 按需生成 Preview；这不改变已返回 Candidate ID。

### 7.3 事件类型

```text
run.created
query.planned
provider.started
source.found
artifact.found
candidate.hydrating
candidate.scored
candidate.blocked
provider.completed
provider.rate_limited
run.review_ready
import.started
import.item_completed
import.completed
run.failed
```

每个事件包含 `eventId`、`runId`、`revision`、`timestamp` 和最小必要 Payload。原始全文不通过 SSE 发送。

## 8. 召回、内容过滤与默认选择

### 8.1 两阶段评分

不能继续只用仓库元数据完成最终排序。

#### 阶段一：Retrieval Score

用于控制需要 Hydrate 的数量，输入包括：

- 标题、描述、Topic、搜索命中片段。
- 官方组织、Star、维护时间、来源类型。
- 文件名和 Artifact Path 是否符合 Skill 约定。
- 被多少个独立 Provider 发现；该信号只增加检索置信度，不增加来源可信度。

#### 阶段二：Content Score

读取固定 Revision 的实际内容后重新评分：

- 查询与目标、Workflow、Constraints、Tools 的相关性。
- Skill 结构完整性和可转换性。
- 来源可信度、许可证状态、维护新鲜度。
- 注入、Secret、危险命令、远程执行和混淆内容风险。
- 与现有 Repository 以及本次搜索其他候选的重复度。

最终分继续保留可解释维度，不只返回一个总分。建议沿用现有 Ranking 基础，但将 `quality`、`convertibility` 和 `risk` 改为 Hydrate 后重算。

### 8.2 硬性过滤

以下候选保留在结果中但禁止勾选：

- 内容抓取失败或只有搜索摘要，没有可验证原文。
- 无法固定 Revision，且保存前内容已经漂移。
- 明确禁止保存、改写或分发的许可证。
- 检测到疑似 Secret、恶意下载执行链或严重破坏性指令。
- 文件超过大小限制、Content-Type 不允许或解析失败。
- Genome Draft 无法通过 Schema。

硬过滤项必须有稳定 `reasonCode`，例如 `CONTENT_UNAVAILABLE`、`LICENSE_DENIED`、`HIGH_RISK_SECRET`，方便测试和前端本地化。

### 8.3 默认不选择但允许人工选择

- 许可证未知，需要人工复核。
- 中风险静态扫描结果。
- Metadata-only 或结构完整度低。
- 分数低于推荐阈值。
- 重复 Cluster 中非主版本。
- 来源过于集中，为了多样性被推荐算法降位。

这些候选仍可进入 Quarantine，但确认框要显示额外警告。

### 8.4 默认选择策略

推荐使用确定性、版本化策略，第一版默认值：

1. 只考虑 `eligible = true` 的候选。
2. `finalScore >= 68`。
3. Risk 为 Low，License 为 Allowed。
4. 每个重复 Cluster 只选主候选。
5. 同一作者或仓库最多默认选择 2 个，避免结果被单一来源占满。
6. 按覆盖增益选择 3～5 个；不足 3 个时不凑数。
7. 每个推荐项返回人类可读原因和机器可读 `reasonCodes`。

用户的勾选状态不能因为后续迟到的搜索结果被重置。新到达的高分候选可以标记“新推荐”，但除非用户尚未开始手动编辑，否则不自动改变选择。

## 9. API 草案

### 9.1 创建和观察搜索

```http
POST /api/discovery/search-runs
Content-Type: application/json

{
  "query": "browser extraction with schema validation",
  "providerIds": ["github", "brave", "tavily", "exa"],
  "scopeIds": ["all_web_skills"],
  "filters": {
    "kinds": ["skill"],
    "licenses": ["MIT", "Apache-2.0"]
  }
}
```

响应：

```json
{
  "run": { "id": "dsr_01...", "state": "queued", "revision": 1 },
  "eventsUrl": "/api/discovery/search-runs/dsr_01.../events"
}
```

```http
GET /api/discovery/providers
GET /api/discovery/search-runs/{runId}
GET /api/discovery/search-runs/{runId}/events
POST /api/discovery/search-runs/{runId}/cancel
```

`GET /api/discovery/providers` 返回 GitHub、Brave、Tavily、Exa 各自的真实配置与健康状态。前端只允许用户选择 `configured = true` 的 Provider，但仍展示未配置项和配置提示。

### 9.2 来源与候选

```http
GET /api/discovery/search-runs/{runId}/sources
GET /api/discovery/search-runs/{runId}/candidates?state=all
GET /api/discovery/candidates/{candidateId}/preview
```

Preview 响应包含安全截断的原文、来源证据、Genome Draft、最新风险与许可证结果。大正文分页或按 Section 返回。

### 9.3 批量确认与保存

```http
POST /api/discovery/import-batches
Idempotency-Key: 7c4b...
Content-Type: application/json

{
  "searchRunId": "dsr_01...",
  "candidateIds": ["cand_01...", "cand_02..."],
  "expectedRunRevision": 18,
  "acknowledgedWarnings": [
    { "candidateId": "cand_02...", "code": "LICENSE_REVIEW_REQUIRED" }
  ]
}
```

响应逐项返回：

```json
{
  "batchId": "dib_01...",
  "summary": { "saved": 1, "existing": 0, "rejected": 1, "failed": 0 },
  "items": [
    { "candidateId": "cand_01...", "state": "saved", "skillId": "..." },
    { "candidateId": "cand_02...", "state": "rejected", "reasonCode": "SOURCE_CHANGED" }
  ]
}
```

关键变化：删除“客户端把完整 Candidate 回传给 Import API”的模式。服务端只信任由 Search Run 产生并持久化的 Candidate ID。

### 9.4 兼容策略

- 现有 `POST /api/discovery/search` 暂时保留一个版本，内部调用同步兼容层。
- 现有 `POST /api/discovery/import` 标记 Deprecated，只允许导入服务端签名的 Candidate Token，随后移除。
- 新前端只使用 Search Run API。
- 旧 Connector 选择迁移为 `providerIds + scopeIds`：`github` 是 Provider；`openai`、`anthropic` 迁移为 Scope Preset；`builtin` 迁移为显式本地数据开关。

## 10. 后端改造建议

### 10.1 模块边界

```text
backend/rogueskills/
├── api/
│   ├── app.py                         # Route，只处理协议和错误映射
│   └── models.py                      # SearchRun / Preview / ImportBatch 请求模型
├── application/
│   └── discovery_service.py           # Search Run 编排、Hydrate、批量导入
├── domain/
│   ├── discovery.py                   # 保留纯函数兼容入口
│   ├── discovery_models.py            # Source/Artifact/Candidate 状态
│   ├── discovery_ranking.py           # 两阶段评分
│   └── discovery_policy.py            # 过滤与默认选择策略
├── adapters/
│   ├── discovery_gateway.py           # Provider Registry 和出站边界
│   ├── github_discovery.py            # Code/Repo/Tree/Raw API
│   ├── brave_search.py                 # Brave Search API Adapter
│   ├── tavily_search.py                # Tavily API Adapter
│   ├── exa_search.py                   # Exa API Adapter
│   └── safe_web_fetcher.py             # 命中网页的安全抓取
└── infrastructure/
    └── discovery_repository.py        # Run、Hit、Artifact、Candidate、Batch 持久化
```

### 10.2 持久化

新增：

- `discovery_search_runs`
- `discovery_source_hits`
- `discovery_artifacts`
- `discovery_candidates`
- `discovery_events`
- `discovery_import_batches`
- `discovery_import_items`

现有 `source_snapshots` 继续作为已入库 Skill 的长期证据。Search Run 数据默认保留 24 小时，成功入库的 Artifact Snapshot 则随 Skill Version 长期保存。

正文可以先使用数据库 Text 支撑本地原型；生产化后迁到对象存储，数据库只保存 Content Hash 和对象引用。

### 10.3 任务执行

- MVP 可使用 FastAPI 进程内 Async Task，但 Run 状态和事件必须持久化。
- 生产环境迁移到 Celery/Redis Worker，API 和事件协议不变。
- 每个 Provider 独立 Timeout、并发上限、速率限制、成本预算和熔断状态。
- Hydrate 设置全局预算，例如每次 Search Run 最多拉取 30 个 Artifact、单文件 256 KB、总正文 3 MB。
- Preview 可以按需拉取，但必须经过相同网络安全策略。

### 10.4 固定版本

GitHub 来源不要把 `main` 当作最终 Revision：

1. 搜索命中仓库默认分支。
2. 解析默认分支当前 Commit SHA。
3. Tree、Raw Content 和 Source URL 全部使用 Commit SHA。
4. 保存前确认 Candidate 对应 SHA 与 Fingerprint 仍存在。

这可以避免搜索、预览、保存三个阶段读到不同内容。

## 11. 前端改造建议

### 11.1 Controller 状态

将当前 `useDiscovery()` 中的一次性 `results` 和单个 `stagingId` 改为：

```ts
interface DiscoverySearchState {
  run: DiscoverySearchRun | null
  events: DiscoveryEvent[]
  sources: Map<string, SourceHit>
  artifacts: Map<string, SkillArtifact>
  candidates: Map<string, SkillCandidate>
  selectedIds: Set<string>
  userEditedSelection: boolean
  previewCandidateId: string | null
  importBatch: DiscoveryImportBatch | null
}
```

### 11.2 新组件

```text
SearchView.vue
├── SearchComposer.vue
├── SearchProgressPanel.vue
│   ├── ProviderStatusItem.vue
│   └── SourceTree.vue
├── CandidateSelectionToolbar.vue
├── CandidateSelectionCard.vue
├── CandidatePreviewDrawer.vue
│   ├── SourceEvidenceTab.vue
│   ├── RawSnapshotTab.vue
│   ├── GenomeDraftTab.vue
│   └── ReviewTab.vue
├── ImportReviewDialog.vue
└── ImportBatchResult.vue
```

### 11.3 交互细节

- Checkbox 点击与打开 Preview 分离，避免误操作。
- 新结果插入时保持当前滚动位置。
- 用户第一次手改 Checkbox 后，不再自动覆盖选择集合。
- 候选卡始终显示来源数量、Artifact Path、快照状态、许可证和风险。
- 原文 Markdown 使用禁用 HTML 的渲染器并清理链接协议。
- 外链继续保留，但作为来源核验的补充，不是唯一查看方式。
- 保存按钮固定显示所选数量，并在 `0` 项时禁用。
- 浏览器刷新后根据 URL 中的 `runId` 恢复 Search Run；未提交的选择可以保存在 Session Storage。

## 12. 安全、许可证与隐私

### 12.1 网络抓取安全

Web Search 会引入任意 URL 抓取能力，必须防止 SSRF：

- 只允许 `https`，必要时允许受控 `http`。
- 禁止 loopback、私网、link-local、metadata service 和非 HTTP(S) Scheme。
- DNS 解析后校验 IP，Redirect 每一跳重新校验。
- 限制 Redirect 次数、响应大小、Content-Type、连接与读取 Timeout。
- Token 只发送到对应官方 API Host；沿用当前 GitHub Token Host 限制。
- 禁止 Cookie、浏览器登录态和用户 Authorization Header 透传给来源站点。

### 12.2 内容安全

- 所有远程内容作为不可信数据，不进入系统 Prompt 指令区。
- 不解析或执行 `<script>`、安装脚本、Shell、Python、JS、MCP Server。
- 原文预览禁用 HTML，代码块只显示。
- Static Scan 同时作用于原文和归一化结果。
- 搜索摘要中的 Prompt Injection 不应影响 Query Planner 或选择策略。

### 12.3 许可证

许可证状态拆为：

- `allowed`
- `review_required`
- `denied`
- `unknown`

Repository License 不一定覆盖仓库内所有文件。若 Artifact 自带 Frontmatter License，应同时保存两者及冲突状态；冲突时不得默认选择。

### 12.4 隐私

- UI 告知用户查询会发送给所选第三方 Search Provider。
- 查询会分别发送给多个已选 Provider；设置页应逐项说明厂商、用途和启用状态。
- 日志默认不记录完整私密 Query 和外部正文，只记录 Hash、长度和结构化指标。
- Search Run 24 小时清理；入库候选按 Repository 保留策略处理。

## 13. 可观测性与错误语义

建议指标：

- `discovery_search_runs_total{state}`
- `discovery_provider_latency_ms{provider}`
- `discovery_provider_requests_total{provider,status}`
- `discovery_provider_cost_total{provider}`
- `discovery_source_hits_total{provider,domain}`
- `discovery_artifacts_hydrated_total{state}`
- `discovery_candidates_total{recommended,risk,license_state}`
- `discovery_selection_override_total{direction}`
- `discovery_import_items_total{state}`
- `discovery_rate_limit_remaining{provider}`

错误必须区分：未配置、鉴权失败、限流、超时、来源不存在、正文过大、解析失败、内容变化和策略拒绝。前端不能把所有错误都显示成“远程来源不可用”。

## 14. 测试与验收标准

### 14.1 后端测试

1. 使用 `httpx.MockTransport` 分别验证 GitHub、Brave、Tavily、Exa 正式 JSON API 的出站请求、鉴权 Header、分页和响应归一化。
2. 一个仓库包含 3 个 `SKILL.md` 时产生 1 个 Source Hit、3 个 Artifact 和最多 3 个 Candidate。
3. Search Run 多 Provider 并行时，单个 Provider 失败只产生 `partial`；全部 Provider 失败不能回退成 builtin 成功。
4. SSE 事件顺序、断线续传和最终 Snapshot 一致。
5. Hydrate 后重新计算风险与排序，不沿用仓库描述得出的最终分。
6. 重复 URL、Fingerprint、名称/作者和 Workflow Cluster 正确合并。
7. 默认选择满足数量、阈值、来源多样性和确定性要求。
8. Import Batch 只接受属于该 Run 的 Candidate ID。
9. 浏览器篡改分数、许可证、URL 或风险字段无法影响保存。
10. 保存前 Source SHA/Fingerprint 改变时返回 `SOURCE_CHANGED`。
11. Idempotency Key 重试不会生成重复 Skill Version。
12. SSRF、Redirect 到私网、超大响应和错误 Content-Type 被拒绝。
13. 三个 Provider 命中同一 URL 时生成一个 Source Hit，并保留三条 `discoveredBy` 证据。
14. OpenAI/Anthropic Scope 会转换为各 Provider 支持的 Domain/Organization Filter，而不是伪装成独立 API。

真实互联网 Smoke Test 单独运行，不放入普通单元测试，避免网络波动造成 CI 不稳定。

### 14.2 前端测试

1. 至少两个远程 Provider 已配置时，首次搜索真实调用它们，且不返回 builtin，除非用户显式开启本地示例。
2. 搜索事件实时出现，来源可以展开到 Artifact 子项。
3. 推荐项默认勾选，用户取消后迟到结果不会重置选择。
4. Preview 可切换来源、原文、Genome 和审查 Tab，且不触发保存。
5. 硬拦截候选不可选择，但原因可见。
6. 用户可以增选未推荐项，并在确认框看到警告。
7. 批量保存只提交选中的 Candidate ID。
8. 部分保存失败时，成功项和失败项分别展示，可只重试失败项。

### 14.3 产品验收

- 用户能明确回答“系统刚才真的搜索了哪些来源”。
- 用户能从一个仓库父项展开看到多个具体 Skill 文件。
- 每个被推荐的候选都有可阅读的来源证据和推荐理由。
- 页面默认选择少量候选，但最终保存集合完全由用户确认。
- 未选择的候选不会写入 Repository。
- 任何外部候选都不会绕过 Quarantine 和后续 Benchmark/Human Review。

## 15. 分阶段实施

### M0：让现有能力如实可见

- 增加 Provider Health，明确显示 GitHub、Brave、Tavily、Exa 的已配置、未配置、鉴权失败、限流和可用状态。
- 默认选择全部已配置远程 Provider，`builtin` 改为“本地示例”且默认关闭。
- OpenAI、Anthropic 从“来源卡片”迁移为 Scope Preset。
- UI 将“仓库候选”标明为 Repository，不再直接称为 Skill。
- Import 改为服务端 Candidate ID 或短期签名 Token。

退出条件：用户能够分清本地示例和真实网络结果，客户端不能篡改导入内容。

### M1：Search Run 与来源树

- 新增 Search Run、SSE、持久化状态和刷新恢复。
- 接入 GitHub、Brave、Tavily、Exa 四个真实 API Adapter 与多 Provider 去重证据。
- 接入 GitHub Code Search 与 Repo Tree 全量 Artifact 枚举，并安全抓取其他 Provider 命中的真实网页。
- 实现 Source Hit → Artifact → Candidate 三层数据。
- 实现展开来源和实时搜索过程 UI。

退出条件：多 Skill 仓库能展示全部合格子项，部分来源失败仍可完成搜索。

### M2：预览、推荐与批量确认

- 实现按需 Hydrate、固定 Commit SHA、原文与 Genome Preview。
- 实现两阶段评分、硬过滤、默认选择和解释 Reason Code。
- 实现 Checkbox、确认框、Import Batch、幂等与逐项结果。

退出条件：完成“默认挑选 → 用户增删 → 确认 → 只保存所选项”的完整闭环。

### M3：搜索质量与生产化

- 优化多 Provider Query Plan、Domain Scope、召回覆盖和结果融合。
- 完善任意 URL 安全抓取、SSRF 防护、成本预算和熔断。
- Search Task 迁移 Worker，对象存储保存长期快照。
- 增加 Provider 运行指标、审计和保留策略。

退出条件：GitHub 外来源可以通过真实网络搜索发现，同时满足安全和可追溯要求。

## 16. 建议的默认产品决策

| 决策 | 建议默认值 |
|---|---|
| 默认搜索模式 | GitHub + Brave + Tavily + Exa 中所有已配置 Provider；本地示例不默认混入 |
| 默认推荐数量 | 3～5 个，不足则不凑数 |
| Search Run 保留 | 24 小时 |
| 单 Run Artifact Hydrate 上限 | 30 个 |
| 单 Artifact 正文上限 | 256 KB |
| 保存目标 | 仅 Quarantine Repository |
| Preview 策略 | 前 10 个候选预取，其余按需 |
| 版本固定 | Commit SHA + Content SHA-256 |
| 进度协议 | SSE |
| 批量保存语义 | 部分成功 + 幂等重试 |
| 选择策略 | 确定性、版本化、返回 Reason Code |
| Web Search Provider | Provider 接口统一；验收环境至少 GitHub + 2 个 Web API，生产建议四个全配 |

## 17. 最终推荐

不建议在当前 `CandidateCard` 上直接增加几个 Checkbox 就结束。那只能补表面交互，仍然解决不了“仓库不是 Skill”“来源不可展开”“搜索内容未 Hydrate 就评分”“客户端回传完整 Candidate”这些结构性问题。

推荐以 **Search Run、Source Hit、Skill Artifact、Skill Candidate、Import Batch** 五个对象作为新主干，由 GitHub、Brave、Tavily、Exa 多个正式 API 同时做真实搜索，再统一抓取实际网页、合并重复来源并形成来源树。这样既能实现类似 Grok 的可见搜索过程，又能保持 RogueSkills 现有的 Quarantine、Snapshot、Fingerprint、Benchmark 和人工晋升安全边界。
