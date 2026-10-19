"use strict";

// Local protocol regression for Codex image inputs. The upstream is a
// loopback capture, so no provider request or credential is used.
const assert = require("node:assert/strict");
const http = require("node:http");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const adapterScript = path.join(__dirname, "codex-id-sanitizer-proxy.js");
const PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

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
          if (res.statusCode === 200) return resolve();
          if (Date.now() < deadline) return setTimeout(probe, 50);
          reject(new Error(`health HTTP ${res.statusCode}`));
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

function bodyFor(model, content) {
  return {
    model,
    stream: false,
    instructions: "Inspect the supplied image.",
    input: [{ type: "message", role: "user", content }],
    tools: []
  };
}

async function main() {
  const captured = [];
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      captured.push({ path: req.url, body: JSON.parse(Buffer.concat(chunks).toString("utf8")) });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ id: "image-contract", object: "response", status: "completed", output: [] }));
    });
  });
  const upstreamPort = await listen(upstream);
  const probe = http.createServer();
  const adapterPort = await listen(probe);
  await new Promise((resolve) => probe.close(resolve));
  const logDir = fs.mkdtempSync(path.join(os.tmpdir(), "codex-image-contract-"));
  const child = spawn(process.execPath, [adapterScript], {
    env: {
      ...process.env,
      CODEX_SANITIZER_HOST: "127.0.0.1",
      CODEX_SANITIZER_PORT: String(adapterPort),
      CODEX_SANITIZER_UPSTREAM: `http://127.0.0.1:${upstreamPort}`,
      CODEX_SANITIZER_LOG_DIR: logDir
    },
    stdio: ["ignore", "ignore", "pipe"]
  });
  try {
    await waitForHealth(adapterPort, child);

    const chatContent = [
      { type: "input_text", text: "read this image" },
      { type: "input_image", image_url: `data:application/octet-stream;base64,${PNG_BASE64}`, detail: "original" }
    ];
    const kimi = await requestJson(adapterPort, bodyFor("kimi-k3", chatContent));
    assert.equal(kimi.status, 200);
    assert.equal(captured[0].path, "/v1/chat/completions");
    const kimiContent = captured[0].body.messages.find((message) => message.role === "user").content;
    assert.equal(Array.isArray(kimiContent), true);
    assert.equal(kimiContent[0].text, "read this image");
    assert.equal(kimiContent[1].type, "image_url");
    assert.equal(kimiContent[1].image_url.url.startsWith("data:image/png;base64,"), true);
    assert.equal(kimiContent[1].image_url.detail, "high");

    const glm = await requestJson(adapterPort, bodyFor("glm-5.3-flash", chatContent));
    assert.equal(glm.status, 200);
    assert.equal(captured[1].path, "/v1/chat/completions");
    assert.equal(captured[1].body.model, "glm-5.3-flash");
    const glmContent = captured[1].body.messages.find((message) => message.role === "user").content;
    assert.equal(Array.isArray(glmContent), true);
    assert.equal(glmContent[1].type, "image_url");
    assert.equal(glmContent[1].image_url.url.startsWith("data:image/png;base64,"), true);

    const deepseek = await requestJson(adapterPort, bodyFor("deepseek-v4-pro", [
      { type: "input_text", text: "read this image" },
      { type: "image", data: PNG_BASE64, mimeType: "application/octet-stream", detail: "high" }
    ]));
    assert.equal(deepseek.status, 200);
    assert.equal(captured[2].path, "/v1/responses");
    assert.equal(captured[2].body.model, "deepseek-v4.1-flash");
    const deepseekImage = captured[2].body.input[0].content[1];
    assert.equal(deepseekImage.mimeType, "image/png");

    const deepseekHistory = await requestJson(adapterPort, {
      ...bodyFor("deepseek-v4-pro", [{ type: "input_text", text: "follow up" }]),
      input: [
        { type: "message", role: "user", content: [{ type: "input_image", image_url: `data:application/octet-stream;base64,${PNG_BASE64}` }] },
        { type: "message", role: "user", content: [{ type: "input_text", text: "follow up" }] }
      ]
    });
    assert.equal(deepseekHistory.status, 200);
    assert.equal(captured[3].path, "/v1/chat/completions");
    assert.equal(captured[3].body.model, "deepseek-v4-pro");
    assert.equal(JSON.stringify(captured[3].body).includes("image_url"), false);
    assert.equal(JSON.stringify(captured[3].body).includes("Earlier image omitted after visual analysis"), true);

    const deepseekFlash = await requestJson(adapterPort, bodyFor("deepseek-v4.1-flash", [
      { type: "input_text", text: "read this image" },
      { type: "input_image", data: PNG_BASE64, mimeType: "application/octet-stream", detail: "high" }
    ]));
    assert.equal(deepseekFlash.status, 200);
    assert.equal(captured[4].path, "/v1/responses");
    assert.equal(captured[4].body.model, "deepseek-v4.1-flash");
    const deepseekFlashImage = captured[4].body.input[0].content[1];
    assert.equal(deepseekFlashImage.mimeType, "image/png");

    const qwenMax = await requestJson(adapterPort, bodyFor("qwen3.8-max", chatContent));
    assert.equal(qwenMax.status, 200);
    assert.equal(captured[5].path, "/v1/chat/completions");
    assert.equal(captured[5].body.model, "qwen3.8-max");
    assert.equal(captured[5].body.messages.find((message) => message.role === "user").content[1].type, "image_url");

    const qwenFlash = await requestJson(adapterPort, bodyFor("qwen3.8-flash", chatContent));
    assert.equal(qwenFlash.status, 200);
    assert.equal(captured[6].path, "/v1/chat/completions");
    assert.equal(captured[6].body.model, "qwen3.8-flash");
    assert.equal(captured[6].body.messages.find((message) => message.role === "user").content[1].type, "image_url");

    console.log(JSON.stringify({ status: "PASS", cases: 7, models: ["kimi-k3", "glm-5.3-flash", "deepseek-v4-pro->deepseek-v4.1-flash", "deepseek-history-pro", "deepseek-v4.1-flash", "qwen3.8-max", "qwen3.8-flash"] }));
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
