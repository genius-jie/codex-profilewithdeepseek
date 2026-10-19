"use strict";

// Regression for the v24 Kimi continuation contract. Loopback upstream only:
// the adapter is spawned in isolation and the translated chat request is
// captured, so no provider key or live gateway is touched.
//
// Contract under test: kimi-k3 custom-tool descriptions carry a hard
// continuation sentence (tool result returned -> keep calling tools or give
// the final result, never stop on an announcement). Function tools, other
// models, and the v23 failure-envelope tool_choice rule must be unchanged.
const assert = require("node:assert/strict");
const http = require("node:http");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const adapterScript = path.join(__dirname, "codex-id-sanitizer-proxy.js");
const nodeExe = process.execPath;
const CONTRACT = "never end the turn with only an announcement of what you will do next";
const CONTRACT_SENTENCE = `\nAfter this tool returns its result, ${CONTRACT}. Either call another tool to continue the task, or, if the task is already fully complete, reply with the final concrete result.`;

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.removeListener("error", reject);
      resolve(server.address().port);
    });
  });
}

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = new http.Server();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const port = probe.address().port;
      probe.close(() => resolve(port));
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
          if (res.statusCode === 200) { resolve(); return; }
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

function baseBody(model, input) {
  return {
    model,
    stream: false,
    instructions: "You are a test model.",
    input,
    tools: [
      { type: "custom", name: "exec", description: "run a command", parameters: { type: "object", properties: {} } },
      { type: "function", name: "wait", description: "wait", parameters: { type: "object", properties: {} } }
    ]
  };
}

const plainInput = [{ type: "message", role: "user", content: [{ type: "input_text", text: "go" }] }];

async function main() {
  const captured = [];
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      captured.push({ path: req.url, body: JSON.parse(Buffer.concat(chunks).toString("utf8")) });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({
        id: "chatcmpl-contract-regression",
        object: "chat.completion",
        choices: [{ index: 0, message: { role: "assistant", content: "ok" }, finish_reason: "stop" }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 }
      }));
    });
  });
  const upstreamPort = await listen(upstream);
  const adapterPort = await freePort();
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-kimi-contract-"));
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

    // 1. kimi custom tool carries the contract exactly once; function tool untouched.
    const first = await requestJson(adapterPort, {
      ...baseBody("kimi-k3", plainInput),
      reasoning: { effort: "max" }
    });
    assert.equal(first.status, 200);
    assert.equal(captured[0].body.reasoning_effort, "max", "Responses reasoning effort reaches Chat Completions");
    const execTool = captured[0].body.tools.find((t) => t.function.name === "exec");
    const waitTool = captured[0].body.tools.find((t) => t.function.name === "wait");
    assert.equal(execTool.function.description.split(CONTRACT).length - 1, 1, "contract appears exactly once");
    assert.ok(execTool.function.description.endsWith(CONTRACT_SENTENCE), "contract is the trailing sentence");
    assert.equal(waitTool.function.description.includes(CONTRACT), false, "function tools stay untouched");

    // 2. DeepSeek keeps the v23 description shape without the contract.
    const second = await requestJson(adapterPort, baseBody("deepseek-v4-pro", plainInput));
    assert.equal(second.status, 200);
    const deepExec = captured[1].body.tools.find((t) => t.function.name === "exec");
    assert.equal(deepExec.function.description.includes(CONTRACT), false, "deepseek unaffected");
    assert.equal(deepExec.function.description, execTool.function.description.replace(CONTRACT_SENTENCE, ""));

    // 3. v23 failure envelope still forces continuation for kimi.
    const failing = baseBody("kimi-k3", [
      { type: "message", role: "user", content: [{ type: "input_text", text: "go" }] },
      { type: "custom_tool_call", id: "ctc_fail_1", call_id: "call_fail_1", name: "exec", input: "text('x')" },
      { type: "custom_tool_call_output", call_id: "call_fail_1", output: "boom\n[CODEX_TOOL_RESULT_META]{\"ok\":false,\"exit_code\":1}" }
    ]);
    const third = await requestJson(adapterPort, failing);
    assert.equal(third.status, 200);
    assert.equal(captured[2].body.tool_choice, "required", "failure envelope still forces tool_choice");

    // 4. success path now also forces continuation (v25 hard contract): Kimi
    // ignored the v24 soft tool-description contract and stopped on a 135-char
    // announcement right after a successful exec. tool_choice=required is now
    // applied whenever kimi-k3 has any preceding tool batch and tools available.
    const succeeding = baseBody("kimi-k3", [
      { type: "message", role: "user", content: [{ type: "input_text", text: "go" }] },
      { type: "custom_tool_call", id: "ctc_ok_1", call_id: "call_ok_1", name: "exec", input: "text('x')" },
      { type: "custom_tool_call_output", call_id: "call_ok_1", output: "fine\n[CODEX_TOOL_RESULT_META]{\"ok\":true,\"exit_code\":0}" }
    ]);
    const fourth = await requestJson(adapterPort, succeeding);
    assert.equal(fourth.status, 200);
    assert.equal(captured[3].body.tool_choice, "required", "success path now forces tool_choice (v25 hard contract)");

    // 5. v26 text-safe: a preceding tool batch stays in effect even when the
    // model inserted an assistant text announcement between the tool output and
    // the current turn. v25 reset latestToolBatchHasAnyResult on any message
    // item including assistant text, so Kimi escaped the constraint by emitting
    // a one-line plan and stopping. Only user/system messages reset it now.
    const textBetween = baseBody("kimi-k3", [
      { type: "message", role: "user", content: [{ type: "input_text", text: "go" }] },
      { type: "custom_tool_call", id: "ctc_ok_2", call_id: "call_ok_2", name: "exec", input: "text('x')" },
      { type: "custom_tool_call_output", call_id: "call_ok_2", output: "fine\\n[CODEX_TOOL_RESULT_META]{\"ok\":true,\"exit_code\":0}" },
      { type: "message", role: "assistant", content: [{ type: "output_text", text: "Now I will read the file header." }] }
    ]);
    const fifth = await requestJson(adapterPort, textBetween);
    assert.equal(fifth.status, 200);
    assert.equal(captured[4].body.tool_choice, "required", "v26 text-safe: assistant announcement does not reset the tool-batch flag");

    // 6. v27 sticky: a user "继续" message between tool output and the current
    // turn also preserves the flag. v25/v26 reset it on user messages, so Kimi
    // escaped by waiting for the user to type "继续" — the user message cleared
    // the flag and Kimi stopped again. v27 makes the flag sticky for the entire
    // session: once a tool result has been seen, it stays true.
    const userBetween = baseBody("kimi-k3", [
      { type: "message", role: "user", content: [{ type: "input_text", text: "do task" }] },
      { type: "custom_tool_call", id: "ctc_ok_3", call_id: "call_ok_3", name: "exec", input: "text('x')" },
      { type: "custom_tool_call_output", call_id: "call_ok_3", output: "fine\\n[CODEX_TOOL_RESULT_META]{\"ok\":true,\"exit_code\":0}" },
      { type: "message", role: "assistant", content: [{ type: "output_text", text: "Step done." }] },
      { type: "message", role: "user", content: [{ type: "input_text", text: "继续" }] }
    ]);
    const sixth = await requestJson(adapterPort, userBetween);
    assert.equal(sixth.status, 200);
    assert.equal(captured[5].body.tool_choice, "required", "v27 sticky: user message does not reset the tool-batch flag");

    console.log(JSON.stringify({ status: "PASS", adapter: "responses-summary-v39-qwen-vision-v1", cases: 6 }));
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    upstream.close();
    fs.rmSync(logDir, { recursive: true, force: true });
    if (childStderr) process.stderr.write(childStderr);
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ status: "FAIL", error: error.message }));
  process.exitCode = 1;
});
