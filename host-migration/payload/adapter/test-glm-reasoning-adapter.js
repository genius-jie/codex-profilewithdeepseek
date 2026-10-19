"use strict";

// Loopback regression for GLM: the picker effort must reach the Chat
// Completions provider through the shared Responses adapter.
const assert = require("node:assert/strict");
const http = require("node:http");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const adapterScript = path.join(__dirname, "codex-id-sanitizer-proxy.js");
function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}
function sse(payload) { return `data: ${JSON.stringify(payload)}\n\n`; }
function request(port, body) {
  const raw = JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const req = http.request({
      host: "127.0.0.1", port, path: "/v1/responses", method: "POST",
      headers: { "content-type": "application/json", "content-length": Buffer.byteLength(raw) }
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.once("error", reject);
    req.end(raw);
  });
}

async function main() {
  let captured;
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      captured = { path: req.url, body: JSON.parse(Buffer.concat(chunks).toString("utf8")) };
      res.writeHead(200, { "content-type": "text/event-stream" });
      res.write(sse({ id: "glm-chat", choices: [{ index: 0, delta: { reasoning_content: "GLM_REASONING" }, finish_reason: null }] }));
      res.write(sse({ id: "glm-chat", choices: [{ index: 0, delta: { content: "GLM_OK" }, finish_reason: null }] }));
      res.write(sse({ id: "glm-chat", choices: [{ index: 0, delta: {}, finish_reason: "stop" }] }));
      res.end("data: [DONE]\n\n");
    });
  });
  const upstreamPort = await listen(upstream);
  const probe = http.createServer();
  const port = await listen(probe);
  await new Promise((resolve) => probe.close(resolve));
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-glm-reasoning-"));
  const child = spawn(process.execPath, [adapterScript], {
    env: { ...process.env, CODEX_SANITIZER_PORT: String(port), CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`, CODEX_SANITIZER_LOG_DIR: logDir },
    stdio: "ignore"
  });
  try {
    const deadline = Date.now() + 5000;
    while (true) {
      try { if ((await fetch(`http://127.0.0.1:${port}/health`)).ok) break; } catch (_) {}
      if (Date.now() > deadline) throw new Error("adapter health timeout");
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    const result = await request(port, {
      model: "glm-5.2",
      stream: true,
      reasoning: { effort: "max" },
      input: [{ type: "message", role: "user", content: [{ type: "input_text", text: "Reply with OK" }] }]
    });
    assert.equal(result.status, 200);
    assert.equal(captured.path, "/v1/chat/completions");
    assert.equal(captured.body.model, "glm-5.2");
    assert.equal(captured.body.reasoning_effort, "max");
    const events = result.body.split(/\n\n/).filter(Boolean).filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6)).filter((line) => line !== "[DONE]").map(JSON.parse);
    const completed = events.find((event) => event.type === "response.completed");
    assert(completed, "missing response.completed");
    const completedItems = events.filter((event) => event.type === "response.output_item.done").map((event) => event.item);
    assert(completedItems.some((item) => item.type === "reasoning"), `items=${JSON.stringify(completedItems)}`);
    assert((completed.response.output || []).some((item) => item.type === "message"), `output=${JSON.stringify(completed.response.output)}`);
    console.log(JSON.stringify({ status: "PASS", model: "glm-5.2", reasoning_effort: "max", path: captured.path }));
  } finally {
    child.kill();
    upstream.close();
    fs.rmSync(logDir, { recursive: true, force: true });
  }
}
main().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
