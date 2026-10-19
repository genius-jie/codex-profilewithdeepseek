"use strict";

// Regression: adapter-owned compaction markers must become public Responses
// message items with msg_ ids when replayed to an OpenAI-native model.
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
      captured = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ id: "native-replay", object: "response", status: "completed", output: [] }));
    });
  });
  const upstreamPort = await listen(upstream);
  const probe = http.createServer();
  const port = await listen(probe);
  await new Promise((resolve) => probe.close(resolve));
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-compaction-replay-"));
  const child = spawn(process.execPath, [adapterScript], {
    env: { ...process.env, CODEX_SANITIZER_PORT: String(port), CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`, CODEX_SANITIZER_LOG_DIR: logDir },
    stdio: "ignore"
  });
  try {
    const deadline = Date.now() + 5000;
    while (true) {
      try {
        const health = await fetch(`http://127.0.0.1:${port}/health`);
        if (health.ok) break;
      } catch (_) {}
      if (Date.now() > deadline) throw new Error("adapter health timeout");
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    const marker = "ccs1:" + Buffer.from("SUMMARY_NATIVE").toString("base64");
    const result = await request(port, {
      model: "gpt-6-astra",
      stream: false,
      input: [
        { type: "compaction", id: "cmp_982e3b53-3dfa-4f03-afa1-d7ad8286eb4d", encrypted_content: marker },
        { type: "message", role: "user", content: [{ type: "input_text", text: "next" }] }
      ]
    });
    assert.equal(result.status, 200);
    assert.equal(captured.input[0].type, "message");
    assert.match(captured.input[0].id, /^msg_[0-9a-f-]{36}$/);
    assert.equal(captured.input[0].content[0].type, "output_text");
    assert.match(captured.input[0].content[0].text, /SUMMARY_NATIVE/);
    console.log(JSON.stringify({ status: "PASS", messageIdPrefix: "msg_", originalCompactionId: "cmp_" }));
  } finally {
    child.kill();
    upstream.close();
    fs.rmSync(logDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
