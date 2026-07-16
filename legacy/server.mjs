// Frozen Node prototype. The production entrypoint is backend/rogueskills/main.py.
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { createApiRouter } from "./src/backend/api/router.mjs";
import { SkillRepository } from "./src/backend/repository/skill-repository.mjs";
import { SEED_SKILLS } from "./src/core/genome/seed-skills.js";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const PORT = Number(process.env.PORT || 4173);
const HOST = process.env.HOST || "127.0.0.1";
const DATABASE_PATH = process.env.ROGUESKILLS_DB || resolve(ROOT, "data/rogueskills.db");
const repository = new SkillRepository(DATABASE_PATH);

for (const skill of SEED_SKILLS) {
  if (!repository.getSkill(skill.id)) repository.upsertSkill(skill, { sourceId: "seed" });
}

function gatewayFetch(url, options = {}) {
  const headers = new Headers(options.headers ?? {});
  if (process.env.GITHUB_TOKEN && String(url).startsWith("https://api.github.com/")) {
    headers.set("Authorization", `Bearer ${process.env.GITHUB_TOKEN}`);
  }
  headers.set("User-Agent", "RogueSkills-Discovery/0.1");
  return fetch(url, { ...options, headers });
}

const routeApi = createApiRouter({ repository, fetchImpl: gatewayFetch });
const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};

function sendJson(response, status, body, headers = {}) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", ...headers });
  response.end(JSON.stringify(body));
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 2_000_000) throw new Error("Request body exceeds 2 MB");
    chunks.push(chunk);
  }
  if (!chunks.length) return null;
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function allowedStaticPath(pathname) {
  if (pathname === "/" || pathname.endsWith(".html") || pathname.endsWith(".css")) return true;
  if (
    (pathname.startsWith("/src/frontend/") || pathname.startsWith("/src/core/")) &&
    pathname.endsWith(".js")
  ) return true;
  if (pathname.startsWith("/docs/") && pathname.endsWith(".md")) return true;
  if (pathname === "/schemas/skill-genome.schema.json") return true;
  if (pathname.startsWith("/src/contracts/") && pathname.endsWith(".json")) return true;
  return pathname.endsWith(".svg") || pathname.endsWith(".png");
}

async function serveStatic(requestPath, response) {
  const decodedPath = decodeURIComponent(requestPath);
  const pathname =
    decodedPath === "/"
      ? "/index.html"
      : decodedPath === "/schemas/skill-genome.schema.json"
        ? "/src/contracts/skill-genome.schema.json"
        : decodedPath;
  if (!allowedStaticPath(pathname)) {
    sendJson(response, 404, { error: "File not found" });
    return;
  }
  const filePath = resolve(ROOT, `.${pathname}`);
  if (!filePath.startsWith(`${resolve(ROOT)}${sep}`)) {
    sendJson(response, 403, { error: "Forbidden" });
    return;
  }
  try {
    const info = await stat(filePath);
    if (!info.isFile()) throw new Error("Not a file");
    response.writeHead(200, {
      "Content-Type": CONTENT_TYPES[extname(filePath)] ?? "application/octet-stream",
      "Content-Length": info.size,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    createReadStream(filePath).pipe(response);
  } catch {
    sendJson(response, 404, { error: "File not found" });
  }
}

const server = createServer(async (request, response) => {
  const requestUrl = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  if (requestUrl.pathname.startsWith("/api/")) {
    try {
      const body = ["POST", "PUT", "PATCH"].includes(request.method) ? await readJsonBody(request) : null;
      const result = await routeApi({ method: request.method, url: requestUrl.pathname + requestUrl.search, body });
      sendJson(response, result.status, result.body, result.headers);
    } catch (error) {
      sendJson(response, 400, { error: error.message });
    }
    return;
  }
  await serveStatic(requestUrl.pathname, response);
});

server.listen(PORT, HOST, () => {
  console.log(`RogueSkills running at http://${HOST}:${PORT}`);
});

function shutdown() {
  server.close(() => {
    repository.close();
    process.exit(0);
  });
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
