"use strict";

// Regression for switching from a third-party model back to native GPT.
// store=false cannot replay a summary-only rs_ reasoning item that the
// provider never persisted. The adapter must drop that item/reference while
// keeping valid encrypted reasoning and normal tool history intact.
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
    server.listen(0, "127.0.0.1", () => {
      server.removeListener("error", reject);
      resolve(server.address().port);
    });
  });
}

function requestJson(port, body) {
  return new Promise((resolve, reject) => {
    const raw = JSON.stringify(body);
    const req = http.request({
      host: "127.0.0.1",
      port,
      path: "/v1/responses",
      method: "POST",
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

function waitForHealth(port, child) {
  const deadline = Date.now() + 5000;
  return new Promise((resolve, reject) => {
    const probe = () => {
      if (child.exitCode != null) return reject(new Error(`adapter exited: ${child.exitCode}`));
      const req = http.get({ host: "127.0.0.1", port, path: "/health" }, (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          if (res.statusCode === 200) {
            try {
              const health = JSON.parse(Buffer.concat(chunks).toString("utf8"));
              assert.equal(health.adapter, "responses-summary-v39-qwen-vision-v1");
              resolve();
            } catch (error) { reject(error); }
          } else if (Date.now() < deadline) setTimeout(probe, 50);
          else reject(new Error(`health HTTP ${res.statusCode}`));
        });
      });
      req.once("error", () => {
        if (Date.now() < deadline) setTimeout(probe, 50);
        else reject(new Error("health timeout"));
      });
    };
    probe();
  });
}

function baseInput(reasoning) {
  return [
    reasoning,
    { type: "item_reference", id: "ref_stale", item_id: reasoning.id },
    { type: "message", role: "user", content: [{ type: "input_text", text: "继续执行" }] },
    { type: "custom_tool_call", id: "msg_33333333-3333-4333-8333-333333333333", call_id: "call_ASaeoCuMsArQMPZZOEJGOENX", name: "exec", input: "text('SWITCH_OK')", code: "text('SWITCH_OK')" },
    { type: "custom_tool_call_output", call_id: "call_ASaeoCuMsArQMPZZOEJGOENX", output: "SWITCH_OK" }
  ];
}

async function main() {
  const captured = [];
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      captured.push(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ id: "resp-switch-test", object: "response", status: "completed", output: [] }));
    });
  });
  const upstreamPort = await listen(upstream);
  const adapterProbe = http.createServer();
  const adapterPort = await listen(adapterProbe);
  await new Promise((resolve) => adapterProbe.close(resolve));
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-gpt-switch-replay-"));
  const child = spawn(process.execPath, [adapterScript], {
    env: { ...process.env, CODEX_SANITIZER_HOST: "127.0.0.1", CODEX_SANITIZER_PORT: String(adapterPort), CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`, CODEX_SANITIZER_LOG_DIR: logDir },
    stdio: ["ignore", "ignore", "pipe"]
  });
  try {
    await waitForHealth(adapterPort, child);
    const staleReasoning = { type: "reasoning", id: "rs_stale-reasoning", summary: [{ type: "summary_text", text: "old" }], encrypted_content: null, status: "completed" };
    const first = await requestJson(adapterPort, { model: "gpt-6-astra", store: false, input: baseInput(staleReasoning) });
    assert.equal(first.status, 200);
    const firstInput = captured[0].input;
    assert.equal(firstInput.some((item) => item.type === "reasoning" || item.type === "item_reference"), false);
    const firstCall = firstInput.find((item) => item.type === "custom_tool_call");
    const firstOutput = firstInput.find((item) => item.type === "custom_tool_call_output");
    assert.equal(firstCall.id.startsWith("ctc_"), true);
    assert.equal(Object.hasOwn(firstCall,'code'),false,'transport wrapper metadata cannot leak into GPT input');
    assert.equal(firstCall.call_id, "call_ASaeoCuMsArQMPZZOEJGOENX");
    assert.equal(firstOutput.call_id, firstCall.call_id, 'preserve opaque native correlation identity');

    const encryptedReasoning = { type: "reasoning", id: "rs_persisted-reasoning", summary: [], encrypted_content: "opaque", status: "completed" };
    const second = await requestJson(adapterPort, { model: "gpt-6-astra", store: false, input: baseInput(encryptedReasoning) });
    assert.equal(second.status, 200);
    assert.equal(captured[1].input.some((item) => item.id === "rs_persisted-reasoning"), true);
    assert.equal(captured.length, 2);
  console.log(JSON.stringify({ status: "PASS", adapter: "responses-summary-v39-qwen-vision-v1", cases: 2 }));
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    upstream.close();
    fs.rmSync(logDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ status: "FAIL", error: error.message }));
  process.exitCode = 1;
});
