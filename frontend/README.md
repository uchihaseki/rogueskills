# RogueSkills Frontend

Vue 3 + TypeScript + Vite 单页应用。前端与 FastAPI 后端独立运行和部署。

## Routes

- `/` — Evolution Run
- `/discovery` — Skill Discovery
- `/discovery.html` — 兼容旧链接，自动跳转到 `/discovery`

路由使用 Vue Router 的 HTML5 History 模式。生产环境的前端静态服务器需要把未知前端路径回退到 `index.html`。

## Local development

在项目根目录启动 FastAPI（默认 `127.0.0.1:4173`）：

```sh
npm start
```

在另一个终端启动 Vite：

```sh
npm run frontend:dev
```

然后访问 `http://localhost:5173/`。Vite 会把 `/api` 请求代理到 FastAPI。

## API configuration

默认 API 基础路径为 `/api`。如果前后端部署在不同域名，构建前设置：

```sh
VITE_API_BASE_URL=http://127.0.0.1:4173
```

参考 `.env.example`。使用完整后端 URL 时，后端的 `ROGUESKILLS_CORS_ORIGINS` 必须包含前端来源。

## Commands

```sh
npm install
npm run dev
npm run type-check
npm run build
npm run preview
```
