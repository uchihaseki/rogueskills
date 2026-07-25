# Awesome Finance Skills · Browser → Codex Demo

This clean Codex project uses the same RogueSkills API as the Vue Evolution
frontend. The local `Awesome-finance-skills/` snapshot is seeded into the Initial
Library when the normal local database starts; there is no frontend import step.

Start the API and frontend from the repository root:

```bash
npm start
npm run frontend:dev
```

Open `http://127.0.0.1:5174/`, choose an `alphaear-*` Skill (the recommended
demo choice is `alphaear-signal-tracker`), and click `开始完整自动进化`.

Then start Codex in this directory:

```bash
cd examples/codex-awesome-finance-demo
codex
```

Useful demo prompts:

```text
读取最新的 Demo Context。解释当前选中的 Skill Genome：输入、workflow、约束、来源和当前版本是什么？

读取最新 Evolution Run。逐个解释本次 Mutation 修复了哪个金融失败模式、付出了什么 trade-off，以及解锁了哪些 Evolution。

读取生成的 AgentPreset，整理 source Run、Skill Version、workflow、工具、digest 和 runtimeVerified 边界。
```

The bridge also exposes the approved Finance Case Pack. Its default finance Skill
version is pinned to `alphaear-signal-tracker-90641e@2`; change that pin only as an
explicit demo choice.
