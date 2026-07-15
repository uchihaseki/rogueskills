# RogueSkills Prototype

一个把 Skill Evolution 表达为肉鸽 Run 的零依赖浏览器原型。

现在还包含 Skill Discovery 工作台，可从公开仓库发现 Skill，或把 SOP/Runbook 转换为隔离的 Skill Genome 候选。

## 运行

需要 Node.js 22.5+。服务端使用 Node 内置 SQLite，不需要安装第三方依赖。

```bash
npm start
```

然后访问：

```text
http://localhost:4173
```

Skill Discovery：

```text
http://localhost:4173/discovery.html
```

默认数据库：

```text
data/rogueskills.db
```

如果需要提高 GitHub 公共 API 限额，可以只在服务端配置：

```bash
GITHUB_TOKEN=your_token npm start
```

## 测试

```bash
npm test
```

## 已实现

- Seed 随机地图
- 三幕业务场景
- 普通、精英、实验室、休息和 Boss 节点
- 怪物/失败模式评估
- Stability、Compute、Complexity
- 三选一 Mutation
- 武器进化配方
- 本地存档和 Run Replay
- 多来源 Skill 搜索与统一排序
- GitHub `SKILL.md` / README 快照拉取
- SOP、Runbook、Checklist 转 Skill Genome
- 许可证与危险内容风险扫描
- 隔离候选库和 JSON 导出
- Skill Genome JSON Schema 1.0
- SQLite Skill、版本、来源快照和评估记录
- Initial Skill Library 准入与人工晋升
- 确定性多用例 Benchmark Runner
- 服务端 Search Gateway、缓存和凭证隔离
- Evolution Run 从 Initial Library 选择基础 Skill

当前 Benchmark 是本地确定性用例执行器，不包含随机分数；它尚未调用真实 LLM 或浏览器工具。GitHub Discovery 在用户启用远程来源时会通过服务端访问 GitHub 公共 API。

## 设计文档

- `design.md`：Skill Evolution 底层架构
- `roguelike-design.md`：肉鸽化产品设计
- `roguelike-skill-mapping.md`：游戏元素与 Skill 概念映射
- `docs/prototype-development-plan.md`：原型范围、模块和验收标准
- `docs/skill-discovery-design.md`：搜索、拉取、SOP 转换与安全入库协议
- `docs/p0-architecture.md`：P0 Repository、Benchmark、Gateway 与 API
