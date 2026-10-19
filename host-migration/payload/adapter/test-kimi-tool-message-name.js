"use strict";

// Local regression for the Kimi Chat Completions contract.  It does not call
// the provider: a loopback upstream captures the translated request so the
// test proves the adapter emits a resolvable tool name without touching keys,
// history, or the live gateway.
const assert = require("node:assert/strict");
const http = require("node:http");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const adapterScript = path.join(__dirname, "codex-id-sanitizer-proxy.js");
const nodeExe = process.execPath;

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
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(raw)
      }
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const text = Buffer.concat(chunks).toString("utf8");
        try {
          resolve({ status: res.statusCode, body: text ? JSON.parse(text) : null });
        } catch (error) {
          reject(new Error(`adapter response was not JSON: ${error.message}; body=${text.slice(0, 500)}`));
        }
      });
    });
    req.once("error", reject);
    req.end(raw);
  });
}

function waitForHealth(port, child) {
  const deadline = Date.now() + 5000;
  return new Promise((resolve, reject) => {
    const probe = () => {
      if (child.exitCode != null) {
        reject(new Error(`adapter exited before health probe: ${child.exitCode}`));
        return;
      }
      const req = http.get({ host: "127.0.0.1", port, path: "/health" }, (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          if (res.statusCode === 200) {
            try {
              const health = JSON.parse(Buffer.concat(chunks).toString("utf8"));
              assert.equal(health.adapter, "responses-summary-v39-qwen-vision-v1");
              resolve();
              return;
            } catch (error) {
              reject(error);
              return;
            }
          }
          if (Date.now() < deadline) setTimeout(probe, 50);
          else reject(new Error(`health probe failed with HTTP ${res.statusCode}`));
        });
      });
      req.once("error", () => {
        if (Date.now() < deadline) setTimeout(probe, 50);
        else reject(new Error("health probe timed out"));
      });
    };
    probe();
  });
}

function baseBody(input) {
  return {
    model: "kimi-k3",
    stream: false,
    instructions: "You are a test model.",
    input,
    tools: [{ type: "custom", name: "exec", description: "run", parameters: { type: "object", properties: {} } }]
  };
}

async function main() {
  let captured = [];
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      captured.push({
        path: req.url,
        body: JSON.parse(Buffer.concat(chunks).toString("utf8"))
      });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({
        id: "chatcmpl-kimi-regression",
        object: "chat.completion",
        choices: [{ index: 0, message: { role: "assistant", content: "ok" }, finish_reason: "stop" }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 }
      }));
    });
  });
  const upstreamPort = await listen(upstream);
  const adapterPort = await new Promise((resolve, reject) => {
    const probe = netServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const port = probe.address().port;
      probe.close(() => resolve(port));
    });
  });
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-kimi-adapter-"));
  const child = spawn(nodeExe, [adapterScript], {
    env: {
      ...process.env,
      CODEX_SANITIZER_HOST: "127.0.0.1",
      CODEX_SANITIZER_PORT: String(adapterPort),
      CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`,
      CODEX_SANITIZER_LOG_DIR: logDir
    },
    stdio: ["ignore", "pipe", "pipe"]
  });
  let childStderr = "";
  child.stderr.on("data", (chunk) => { childStderr += chunk.toString(); });
  try {
    await waitForHealth(adapterPort, child);
    const toolId = "msg_11111111-1111-4111-8111-111111111111";
    const first = await requestJson(adapterPort, baseBody([
      { type: "message", role: "user", content: [{ type: "input_text", text: "run" }] },
      { type: "custom_tool_call", id: toolId, name: "exec", input: "echo KIMI_NAME" },
      { type: "custom_tool_call_output", call_id: toolId, output: "done" }
    ]));
    assert.equal(first.status, 200);
    assert.equal(captured[0].path, "/v1/chat/completions");
    const exactToolMessage = captured[0].body.messages.find((m) => m.role === "tool");
    assert.equal(exactToolMessage.name, "exec");
    assert.equal(exactToolMessage.tool_call_id, toolId);

    const second = await requestJson(adapterPort, baseBody([
      { type: "message", role: "user", content: [{ type: "input_text", text: "run again" }] },
      { type: "custom_tool_call", id: toolId, name: "exec", input: "echo KIMI_ORDER" },
      { type: "custom_tool_call_output", call_id: "unresolvable-id", output: "done" }
    ]));
    assert.equal(second.status, 200);
    const orderedToolMessage = captured[1].body.messages.find((m) => m.role === "tool");
    assert.equal(orderedToolMessage.name, "exec");

    const functionId = "msg_22222222-2222-4222-8222-222222222222";
    const third = await requestJson(adapterPort, baseBody([
      { type: "message", role: "user", content: [{ type: "input_text", text: "wait" }] },
      { type: "function_call", id: functionId, name: "wait", arguments: "{}" },
      { type: "function_call_output", call_id: functionId, output: "done" }
    ]));
    assert.equal(third.status, 200);
    const functionToolMessage = captured[2].body.messages.find((m) => m.role === "tool");
    assert.equal(functionToolMessage.name, "wait");
    assert.equal(functionToolMessage.tool_call_id, functionId);

    const fourth = await requestJson(adapterPort, baseBody([
      { type: "message", role: "user", content: [{ type: "input_text", text: "plain" }] }
    ]));
    assert.equal(fourth.status, 200);
    assert.equal(captured[3].body.messages.some((m) => m.role === "tool"), false);

    const fifth = await requestJson(adapterPort, baseBody([
      { type: "message", role: "user", content: [{ type: "input_text", text: "replay tool output" }] },
      { type: "custom_tool_call_output", call_id: "ctc_orphan_exec", output: "done" }
    ]));
    assert.equal(fifth.status, 200);
    const fallbackToolMessage = captured[4].body.messages.find((m) => m.role === "tool");
    assert.equal(fallbackToolMessage.name, "exec");

    // Real failing history: a Responses batch contains several calls before
    // any outputs. Chat must encode that as ONE assistant tool_calls array.
    const parallelBody = baseBody([
      { role: "user", content: "parallel fixture" },
      { type: "custom_tool_call", id: "ctc_item_a", call_id: "call_A", name: "exec", input: "text('A')" },
      { type: "function_call", id: "fc_item_b", call_id: "call_B", name: "wait", arguments: "{}" },
      { type: "custom_tool_call", id: "ctc_item_c", call_id: "call_C", name: "exec", input: "text('C')" },
      { type: "reasoning", id: "rs_summary", summary: [], encrypted_content: null },
      { type: "custom_tool_call", id: "ctc_item_d", call_id: "call_D", name: "exec", input: "text('D')" },
      { type: "function_call_output", call_id: "call_B", output: "B" },
      { type: "custom_tool_call_output", call_id: "call_D", output: "D" },
      { type: "custom_tool_call_output", call_id: "call_A", output: "A" },
      { type: "custom_tool_call_output", call_id: "call_C", output: "C" },
      { role: "user", content: "next batch" },
      { type: "custom_tool_call", id: "ctc_item_e", call_id: "call_E", name: "exec", input: "text('E')" },
      { type: "custom_tool_call_output", call_id: "call_E", output: "E" }
    ]);
    const sixth = await requestJson(adapterPort, parallelBody);
    assert.equal(sixth.status, 200);
    const batches = captured[5].body.messages.filter(m => m.tool_calls);
    assert.deepEqual(batches.map(m => m.tool_calls.length), [4, 1], 'preserve parallel and sequential batch boundaries');
    assert.deepEqual(batches[0].tool_calls.map(t => t.id), ['call_A', 'call_B', 'call_C', 'call_D'], 'correlation uses call_id, not item.id');
    const outputs = captured[5].body.messages.filter(m => m.role === 'tool');
    assert.deepEqual(outputs.map(m => [m.tool_call_id, m.name]), [['call_B','wait'],['call_D','exec'],['call_A','exec'],['call_C','exec'],['call_E','exec']]);
    assert.deepEqual(outputs.map(m => m.content), ['B','D','A','C','E']);

    // The same shared converter serves DeepSeek, with the same call lineage.
    const seventh = await requestJson(adapterPort, { ...parallelBody, model: 'deepseek-v4-pro' });
    assert.equal(seventh.status, 200);
    assert.deepEqual(captured[6].body.messages, captured[5].body.messages);

    // Tool declaration order is not execution order; never invent a name for
    // an ambiguous historical result from those declarations.
    const eighth = await requestJson(adapterPort, {
      ...baseBody([{ type: 'function_call_output', call_id: 'call_unknown', output: 'real result retained upstream by the caller' }]),
      tools: [{type:'function',name:'wait'},{type:'function',name:'request_user_input'}]
    });
    assert.equal(eighth.status, 400);
    assert.equal(eighth.body.error.code, 'unresolved_tool_result');
    assert.equal(captured.length, 7, 'ambiguous result must not be sent upstream under a guessed name');
    console.log(JSON.stringify({ status: "PASS", adapter: "responses-summary-v39-qwen-vision-v1", cases: 8 }));
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    upstream.close();
    fs.rmSync(logDir, { recursive: true, force: true });
    if (childStderr) process.stderr.write(childStderr);
  }
}

function netServer() {
  return new http.Server();
}

main().catch((error) => {
  console.error(JSON.stringify({ status: "FAIL", error: error.message }));
  process.exitCode = 1;
});
