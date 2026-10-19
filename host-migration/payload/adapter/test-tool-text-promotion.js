const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const proxyScript = path.join(__dirname, "read-tool-sanitizer-proxy.js");
const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "tool-text-promotion-"));

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
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.once("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function reservePort() {
  const server = http.createServer();
  const port = await listen(server);
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function sse(text) {
  const events = [
    ["message_start", { type: "message_start", message: { id: "msg_test", type: "message", role: "assistant", content: [], model: "glm-5.2", stop_reason: null, usage: { input_tokens: 1, output_tokens: 1 } } }],
    ["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } }],
    ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "text_delta", text } }],
    ["content_block_stop", { type: "content_block_stop", index: 0 }],
    ["message_delta", { type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: 1 } }],
    ["message_stop", { type: "message_stop" }],
  ];
  return `${events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}`).join("\n\n")}\n\n`;
}

function nativeReadSse(input, partialJson = "") {
  const events = [
    ["message_start", { type: "message_start", message: { id: "msg_test", type: "message", role: "assistant", content: [], model: "qwen3.8-max", stop_reason: null, usage: { input_tokens: 1, output_tokens: 1 } } }],
    ["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "tool_use", id: "toolu_test", name: "Read", input } }],
  ];
  if (partialJson) {
    events.push(["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "input_json_delta", partial_json: partialJson } }]);
  }
  events.push(
    ["content_block_stop", { type: "content_block_stop", index: 0 }],
    ["message_delta", { type: "message_delta", delta: { stop_reason: "tool_use", stop_sequence: null }, usage: { output_tokens: 1 } }],
    ["message_stop", { type: "message_stop" }],
  );
  return `${events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}`).join("\n\n")}\n\n`;
}

function tool(name, schema) {
  return { name, description: name, input_schema: schema };
}

const readSchema = {
  type: "object",
  properties: {
    path: { type: "string" },
    line_start: { type: "integer" },
  },
  required: ["path"],
  additionalProperties: false,
};
const nativeReadSchema = {
  type: "object",
  properties: { file_path: { type: "string" } },
  required: ["file_path"],
  additionalProperties: false,
};

async function main() {
  const responses = new Map([
    ["unique", '{"path":"C:\\\\demo.txt","line_start":1}'],
    ["windows_path", String.raw`{"path":"@@CLAUDE_HOME:win@@\settings.json"}`],
    ["grep_example", String.raw`{"glob":"*.{md,json,py,toml,txt,js,ts}","output_mode":"files_with_matches","path":"@@CLAUDE_HOME:win@@","pattern":"codex_follow_up_candidate|codex_follow_up|Follow-up candidate|follow_up_candidate"}`],
    ["trailing", '准备读取文件。\n\n{"path":"C:\\\\demo.txt","line_start":1}'],
    ["zero", '{"glob":"*.md"}'],
    ["type_error", '{"path":7,"line_start":1}'],
    ["ambiguous", '{"path":"C:\\\\demo.txt","line_start":1}'],
    ["unsupported", '{"path":"C:\\\\demo.txt"}'],
    ["native_invalid", nativeReadSse({})],
    ["native_valid", nativeReadSse({}, '{"file_path":"C:\\\\demo.txt"}')],
    ["native_alias", nativeReadSse({ path: "C:\\demo.txt" })],
  ]);
  const upstream = http.createServer((req, res) => {
    req.resume();
    req.on("end", () => {
      res.writeHead(200, { "content-type": "text/event-stream" });
      const response = responses.get(req.headers["x-test-case"]) || "plain text";
      res.end(response.startsWith("event:") ? response : sse(response));
    });
  });
  const upstreamPort = await listen(upstream);
  const proxyPort = await reservePort();
  const child = spawn(process.execPath, [proxyScript], {
    env: {
      ...process.env,
      READ_SANITIZER_HOST: "127.0.0.1",
      READ_SANITIZER_PORT: String(proxyPort),
      READ_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`,
      READ_SANITIZER_LOG_DIR: logDir,
      READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT: "1",
      READ_SANITIZER_PROMOTE_TOOL_TEXT: "1",
      READ_SANITIZER_ENFORCE_READ_FILE_PATH: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.on("data", (chunk) => { stderr += chunk.toString("utf8"); });

  try {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      try {
        const health = await request(proxyPort, { path: "/__read_sanitizer/health", method: "GET" });
        if (health.status === 200) break;
      } catch {}
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    async function run(testCase, tools) {
      const body = JSON.stringify({ model: "glm-5.2", messages: [{ role: "user", content: "read" }], tools, stream: true });
      return request(proxyPort, {
        path: "/v1/messages",
        method: "POST",
        headers: {
          "content-type": "application/json",
          "content-length": Buffer.byteLength(body),
          "x-test-case": testCase,
        },
      }, body);
    }

    const unique = await run("unique", [tool("Read", readSchema), tool("Glob", { type: "object", properties: { glob: { type: "string" } }, required: ["glob"], additionalProperties: false })]);
    assert.equal(unique.status, 200);
    assert.match(unique.body, /"type":"tool_use"/);
    assert.match(unique.body, /"name":"Read"/);
    assert.match(unique.body, /"stop_reason":"tool_use"/);
    assert.doesNotMatch(unique.body, /text_delta.*demo\.txt/);

    const windowsPath = await run("windows_path", [tool("Read", readSchema)]);
    assert.match(windowsPath.body, /"type":"tool_use"/);
    assert.match(windowsPath.body, /settings\.json/);

    const grepExample = await run("grep_example", [tool("Grep", {
      type: "object",
      properties: { glob: { type: "string" }, output_mode: { type: "string", enum: ["files_with_matches", "content", "count"] }, path: { type: "string" }, pattern: { type: "string" } },
      required: ["pattern"],
      additionalProperties: false,
    })]);
    assert.match(grepExample.body, /"type":"tool_use"/);
    assert.match(grepExample.body, /"name":"Grep"/);

    const trailing = await run("trailing", [tool("Read", readSchema)]);
    assert.match(trailing.body, /"text":"准备读取文件。"/);
    assert.match(trailing.body, /"type":"tool_use"/);

    const nativeInvalid = await run("native_invalid", [tool("Read", nativeReadSchema)]);
    assert.doesNotMatch(nativeInvalid.body, /"type":"tool_use"/);
    assert.match(nativeInvalid.body, /Invalid Read tool call: missing required file_path/);
    assert.match(nativeInvalid.body, /"stop_reason":"end_turn"/);

    const nativeValid = await run("native_valid", [tool("Read", nativeReadSchema)]);
    assert.match(nativeValid.body, /"type":"tool_use"/);
    assert.match(nativeValid.body, /file_path/);
    assert.match(nativeValid.body, /demo\.txt/);
    assert.match(nativeValid.body, /"stop_reason":"tool_use"/);

    const nativeAlias = await run("native_alias", [tool("Read", nativeReadSchema)]);
    assert.match(nativeAlias.body, /"type":"tool_use"/);
    assert.match(nativeAlias.body, /file_path/);
    assert.doesNotMatch(nativeAlias.body, /"path":"C:\\\\demo\.txt"/);

    const unchangedCases = [
      ["zero", [tool("Read", readSchema)]],
      ["type_error", [tool("Read", readSchema)]],
      ["ambiguous", [tool("ReadA", readSchema), tool("ReadB", readSchema)]],
      ["unsupported", [tool("Read", { ...readSchema, properties: { path: { type: "string", format: "uri" } } })]],
    ];
    for (const [testCase, tools] of unchangedCases) {
      const result = await run(testCase, tools);
      assert.equal(result.status, 200);
      assert.doesNotMatch(result.body, /"type":"tool_use"/);
      assert.equal(result.body, sse(responses.get(testCase)), `${testCase} must remain unchanged`);
    }

    const log = fs.readFileSync(path.join(logDir, "read-tool-sanitizer.jsonl"), "utf8");
    assert.match(log, /"type":"tool_text_promoted"/);
    assert.match(log, /"tool_name":"Read"/);
    assert.match(log, /"type":"read_tool_input_rejected"/);
    assert.match(log, /"type":"read_tool_input_normalized"/);
    console.log("tool text promotion integration cases passed");
  } finally {
    child.kill();
    await new Promise((resolve) => child.once("exit", resolve));
    await new Promise((resolve) => upstream.close(resolve));
    fs.rmSync(logDir, { recursive: true, force: true });
  }
  if (stderr) process.stderr.write(stderr);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
