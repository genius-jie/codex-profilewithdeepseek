const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const proxyScript = path.join(__dirname, "codex-id-sanitizer-proxy.js");
const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-id-exec-envelope-"));

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}

function request(port, options, body) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, ...options }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({
        status: res.statusCode,
        body: Buffer.concat(chunks).toString("utf8")
      }));
    });
    req.once("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function abortRequest(port, options, body, delayMs = 100) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, ...options });
    req.once("error", (error) => {
      if (error.code === "ECONNRESET") resolve();
      else reject(error);
    });
    req.write(body);
    req.end();
    setTimeout(() => req.destroy(), delayMs);
  });
}

async function reservePort() {
  const server = http.createServer();
  const port = await listen(server);
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function responseBody(toolName, argumentsText) {
  const chunk = {
    choices: [{
      delta: {
        tool_calls: [{
          index: 0,
          id: `call_${toolName}`,
          function: { name: toolName, arguments: argumentsText }
        }]
      }
    }]
  };
  return `data: ${JSON.stringify(chunk)}\n\ndata: [DONE]\n\n`;
}

function findEvent(body, type) {
  for (const line of body.split("\n")) {
    if (!line.startsWith("data: ")) continue;
    const raw = line.slice(6).trim();
    if (!raw || raw === "[DONE]") continue;
    const event = JSON.parse(raw);
    if (event.type === type) return event;
  }
  return null;
}

async function main() {
  let lastUpstreamRequest = "";
  let upstreamErrorAttempts = 0;
  let upstreamSawClientClose = false;
  let upstreamActive = 0;
  let upstreamMaxConcurrent = 0;
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      lastUpstreamRequest = Buffer.concat(chunks).toString("utf8");
      const testCase = req.headers["x-test-case"];
      let body;
      if (testCase === "exec_arguments") {
        body = responseBody("exec", JSON.stringify({ arguments: "text(1 + 1)" }));
      } else if (testCase === "exec_code") {
        body = responseBody("exec", JSON.stringify({ code: "text(2)" }));
      } else if (testCase === "exec_empty") {
        body = responseBody("exec", "{}");
      } else if (testCase === "exec_input") {
        body = responseBody("exec", JSON.stringify({ input: "text('VISIBLE_OUTPUT')" }));
      } else if (testCase === "exec_cmd") {
        body = responseBody("exec", JSON.stringify({
          cmd: "echo ok",
          workdir: "@@PROFILE_REPO:forward@@"
        }));
      } else if (testCase === "non_exec_input") {
        body = responseBody("apply_patch", JSON.stringify({ input: "*** Begin Patch\n*** End Patch\n" }));
      } else if (testCase === "exec_command_alias") {
        body = responseBody("exec_command", JSON.stringify({
          cmd: "echo ok",
          workdir: "@@PROFILE_REPO:forward@@"
        }));
      } else if (testCase === "upstream_error" || testCase === "upstream_error_terminal") {
        upstreamErrorAttempts += 1;
        body = (testCase === "upstream_error_terminal" || upstreamErrorAttempts === 1)
          ? "data: " + JSON.stringify({
              error: {
                type: "rate_limit_error",
                message: "Concurrency limit exceeded for user, please retry later"
              }
            }) + "\n\ndata: [DONE]\n\n"
          : "data: " + JSON.stringify({ choices: [{ delta: { content: "recovered" } }] }) + "\n\ndata: [DONE]\n\n";
      } else if (testCase === "hold_open") {
        req.once("close", () => { upstreamSawClientClose = true; });
        return;
      } else if (testCase === "socket_abort") {
        res.writeHead(200, { "content-type": "text/event-stream" });
        res.write("data: " + JSON.stringify({ choices: [{ delta: { content: "partial" } }] }) + "\n\n");
        setTimeout(() => res.destroy(), 20);
        return;
      } else if (testCase === "idle_hold") {
        res.writeHead(200, { "content-type": "text/event-stream" });
        res.flushHeaders();
        return;
      } else if (testCase === "delayed") {
        body = "data: " + JSON.stringify({ choices: [{ delta: { content: "queued_ok" } }] }) + "\n\ndata: [DONE]\n\n";
      } else {
        body = "data: " + JSON.stringify({ choices: [{ delta: { content: "ok" } }] }) + "\n\ndata: [DONE]\n\n";
      }
      upstreamActive += 1;
      upstreamMaxConcurrent = Math.max(upstreamMaxConcurrent, upstreamActive);
      const finish = () => { upstreamActive -= 1; };
      res.once("close", finish);
      const send = () => {
        res.writeHead(200, { "content-type": "text/event-stream" });
        res.end(body);
      };
      if (testCase === "delayed") setTimeout(send, 120);
      else send();
    });
  });

  const upstreamPort = await listen(upstream);
  const proxyPort = await reservePort();
  const child = spawn(process.execPath, [proxyScript], {
    env: {
      ...process.env,
      CODEX_SANITIZER_HOST: "127.0.0.1",
      CODEX_SANITIZER_PORT: String(proxyPort),
      CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`,
      CODEX_SANITIZER_UPSTREAM_FIRST_BYTE_TIMEOUT_MS: "1000",
      CODEX_SANITIZER_UPSTREAM_IDLE_TIMEOUT_MS: "150",
      CODEX_SANITIZER_LOG_DIR: logDir
    },
    stdio: ["ignore", "pipe", "pipe"]
  });

  async function waitForHealth() {
    for (let i = 0; i < 60; i += 1) {
      try {
        const result = await request(proxyPort, { path: "/health", method: "GET" });
        if (result.status === 200) return;
      } catch (_) {}
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    throw new Error("proxy health check timed out");
  }

  async function runResponseCase(testCase, toolName) {
    const body = JSON.stringify({
      model: "deepseek-v4-pro",
      stream: true,
      input: [{ role: "user", content: "test" }],
      tools: [{ type: "custom", name: toolName }]
    });
    return request(proxyPort, {
      path: "/v1/responses",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(body),
        "x-test-case": testCase
      }
    }, body);
  }

  async function runPassthroughCase(testCase) {
    const body = JSON.stringify({
      model: "gpt-5",
      stream: true,
      input: "test"
    });
    return request(proxyPort, {
      path: "/v1/responses",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(body),
        "x-test-case": testCase
      }
    }, body);
  }

  try {
    await waitForHealth();

    const inputWrapped = await runResponseCase("exec_input", "exec");
    const declaredExec = JSON.parse(lastUpstreamRequest).tools[0].function;
    assert.deepEqual(declaredExec.parameters.required, ['input']);
    assert.equal(declaredExec.parameters.properties.input.type, 'string');
    assert.equal(findEvent(inputWrapped.body, 'response.custom_tool_call_input.done').input, "text('VISIBLE_OUTPUT')");
    assert.equal(Object.hasOwn(findEvent(inputWrapped.body,'response.output_item.done').item,'code'),false);
    const observed = [];
    require('node:vm').runInNewContext(findEvent(inputWrapped.body, 'response.custom_tool_call_input.done').input, {text:v=>observed.push(v)}, {timeout:100});
    assert.deepEqual(observed,['VISIBLE_OUTPUT']);

    const emptyExec = await runResponseCase('exec_empty', 'exec');
    assert.ok(findEvent(emptyExec.body,'response.failed'), 'empty exec must not be a successful no-op');
    assert.doesNotMatch(emptyExec.body,/response.completed/);

    const execArguments = await runResponseCase("exec_arguments", "exec");
    assert.equal(execArguments.status, 200);
    assert.equal(
      findEvent(execArguments.body, "response.custom_tool_call_input.done").input,
      "text(1 + 1)"
    );

    const execCode = await runResponseCase("exec_code", "exec");
    assert.equal(execCode.status, 200);
    assert.equal(
      findEvent(execCode.body, "response.custom_tool_call_input.done").input,
      "text(2)"
    );

    const execCmd = await runResponseCase("exec_cmd", "exec");
    assert.equal(execCmd.status, 200);
    const execCmdInput = findEvent(execCmd.body, "response.custom_tool_call_input.done").input;
    assert.ok(
      execCmdInput.startsWith(
        'const r = await tools.exec_command({"cmd":"echo ok","workdir":"@@PROFILE_REPO:forward@@"}); text(r && r.output !== undefined ? r.output : r);'
      ),
      "exec command payload keeps the host bridge"
    );
    assert.match(execCmdInput, /\[CODEX_TOOL_RESULT_META\]/, "exec command payload carries the machine result envelope");

    const nonExec = await runResponseCase("non_exec_input", "apply_patch");
    assert.equal(nonExec.status, 200);
    assert.equal(
      findEvent(nonExec.body, "response.custom_tool_call_input.done").input,
      "*** Begin Patch\n*** End Patch\n"
    );

    const alias = await runResponseCase("exec_command_alias", "exec_command");
    assert.equal(alias.status, 200);
    const aliasDone = findEvent(alias.body, "response.custom_tool_call_input.done");
    assert.match(aliasDone.input, /^const r = await tools\.exec_command/);
    assert.equal(
      findEvent(alias.body, "response.output_item.done").item.name,
      "exec"
    );

    const upstreamError = await runResponseCase("upstream_error_terminal", "exec");
    assert.equal(upstreamError.status, 200);
    const failed = findEvent(upstreamError.body, "response.failed");
    assert.ok(failed, "upstream SSE errors must become response.failed");
    assert.equal(failed.response.status, "failed");
    assert.equal(failed.response.error.type, "rate_limit_error");
    assert.match(upstreamError.body, /Concurrency limit exceeded/);
    assert.doesNotMatch(upstreamError.body, /response.completed/);

    const recovered = await runResponseCase("upstream_error", "exec");
    assert.equal(recovered.status, 200);
    assert.match(recovered.body, /recovered/);
    assert.match(recovered.body, /response.completed/);

    const socketAbort = await runResponseCase("socket_abort", "exec");
    assert.equal(socketAbort.status, 200);
    assert.ok(findEvent(socketAbort.body, "response.failed"), "socket abort after SSE output must become response.failed");
    assert.match(socketAbort.body, /data: \[DONE\]/, "socket abort must close the Responses stream with [DONE]");

    const idleTimeout = await runPassthroughCase("idle_hold");
    assert.equal(idleTimeout.status, 200);
    const idleFailed = findEvent(idleTimeout.body, "response.failed");
    assert.ok(idleFailed, "idle upstream must become response.failed");
    assert.equal(typeof idleFailed.sequence_number, "number", "terminal timeout event must carry sequence_number");
    assert.match(idleTimeout.body, /data: \[DONE\]/, "idle timeout must close the Responses stream with [DONE]");

    upstreamMaxConcurrent = 0;
    const queued = await Promise.all([
      runResponseCase("delayed", "exec"),
      runResponseCase("delayed", "exec")
    ]);
    assert.equal(queued.length, 2);
    assert.equal(upstreamMaxConcurrent, 1, "adapted provider requests must be single-flight");

    const holdBody = JSON.stringify({
      model: "deepseek-v4-pro",
      stream: true,
      input: [{ role: "user", content: "hold" }],
      tools: [{ type: "custom", name: "exec" }]
    });
    upstreamSawClientClose = false;
    await abortRequest(proxyPort, {
      path: "/v1/responses",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(holdBody),
        "x-test-case": "hold_open"
      }
    }, holdBody);
    await new Promise((resolve) => setTimeout(resolve, 250));
    assert.equal(upstreamSawClientClose, true, "client disconnect must cancel upstream stream");

    const historyBody = JSON.stringify({
      model: "deepseek-v4-pro",
      stream: true,
      input: [
        { role: "user", content: "continue" },
        {
          type: "custom_tool_call",
          id: "ctc_old_exec",
          name: "exec",
          input: JSON.stringify({ arguments: "text(1 + 1)" })
        },
        { type: "custom_tool_call_output", call_id: "ctc_old_exec", output: "2" }
      ],
      tools: [{ type: "custom", name: "exec" }]
    });
    await request(proxyPort, {
      path: "/v1/responses",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(historyBody),
        "x-test-case": "plain"
      }
    }, historyBody);
    const forwarded = JSON.parse(lastUpstreamRequest);
    const historicalToolCall = forwarded.messages
      .find((message) => Array.isArray(message.tool_calls))
      ?.tool_calls?.[0];
    assert.deepEqual(JSON.parse(historicalToolCall.function.arguments), {input:"text(1 + 1)"});

    const debugLog = fs.readFileSync(path.join(logDir, "debug-exec.log"), "utf8");
    assert.match(debugLog, /UNWRAPPED_ARGUMENTS/);
    assert.match(debugLog, /UNWRAPPED_CODE/);
    assert.match(debugLog, /UNWRAPPED_CMD/);
    console.log("codex-id exec envelope regression passed");
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    await new Promise((resolve) => upstream.close(resolve));
    fs.rmSync(logDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
