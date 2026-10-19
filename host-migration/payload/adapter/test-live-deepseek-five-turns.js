const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

// This is a Host-level adapter regression, so resolve the active Codex++
// profile from the same D-only contract as the formal launcher.  The current
// relay mode keeps the key in auth.json; config.toml is only a legacy fallback.
const plusRoot = process.env.CODEX_PLUSPLUS_PROFILE_ROOT || "@@CODEXPP_PROFILE:escaped@@";
const codexHome = process.env.CODEX_HOME || path.join(plusRoot, "AppData\\Roaming\\Codex\\.codex");
const configPath = path.join(codexHome, "config.toml");
const authPath = path.join(codexHome, "auth.json");
const config = fs.readFileSync(configPath, "utf8");
let apiKey = "";
try {
  const auth = JSON.parse(fs.readFileSync(authPath, "utf8"));
  if (auth && typeof auth.OPENAI_API_KEY === "string") apiKey = auth.OPENAI_API_KEY;
} catch (_) {}
if (!apiKey) {
  const keyMatch = config.match(/^api_key\s*=\s*"([^"]+)"/m);
  if (keyMatch) apiKey = keyMatch[1];
}
if (!apiKey) throw new Error(`Codex++ API key is not configured under ${codexHome}`);
const model = process.env.CODEX_LIVE_MODEL || "deepseek-v4-pro";
const maxOutputTokens = Number(process.env.CODEX_LIVE_MAX_OUTPUT_TOKENS || "256");

function request(body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const req = http.request({
      host: "127.0.0.1",
      port: 15740,
      path: "/v1/responses",
      method: "POST",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
        "content-length": Buffer.byteLength(payload)
      },
      timeout: 90000
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({
        status: res.statusCode,
        body: Buffer.concat(chunks).toString("utf8")
      }));
    });
    req.on("timeout", () => req.destroy(new Error("request timed out")));
    req.on("error", reject);
    req.end(payload);
  });
}

function events(body) {
  return body.split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6).trim())
    .filter((line) => line && line !== "[DONE]")
    .map((line) => JSON.parse(line));
}

async function main() {
  const input = [{
    role: "user",
    content: "请连续处理五轮。现在执行第 1 轮：调用 exec 执行 echo LIVE_ROUND_1_OK，并在收到工具结果后继续下一轮。"
  }];
  let toolCalls = 0;
  for (let round = 1; round <= 5; round += 1) {
    const response = await request({
      model,
      input,
      tools: [{ type: "custom", name: "exec", description: "执行本地命令并返回结果" }],
      stream: true,
      max_output_tokens: maxOutputTokens
    });
    const parsed = events(response.body);
    const completed = parsed.find((event) => event.type === "response.completed");
    if (response.status !== 200 || !completed) {
      throw new Error(`round ${round} did not complete: HTTP ${response.status} EVENTS=${parsed.map((event) => event.type).join(",")}`);
    }
    const toolItem = parsed.find((event) => event.type === "response.output_item.done" &&
      event.item && event.item.type === "custom_tool_call");
    if (!toolItem) {
      const text = parsed
        .filter((event) => event.type === "response.output_text.delta")
        .map((event) => event.delta || "")
        .join("")
        .slice(0, 240);
      const items = parsed
        .filter((event) => event.type === "response.output_item.done")
        .map((event) => ({ type: event.item && event.item.type, name: event.item && event.item.name }))
        .slice(-3);
      throw new Error(`round ${round} did not produce a tool call EVENTS=${parsed.map((event) => event.type).join(",")} ITEMS=${JSON.stringify(items)} TEXT=${text}`);
    }
    toolCalls += 1;
    input.push({
      type: "custom_tool_call",
      id: toolItem.item.id,
      call_id: toolItem.item.call_id,
      name: toolItem.item.name,
      input: toolItem.item.input
    });
    input.push({
      type: "custom_tool_call_output",
      call_id: toolItem.item.call_id,
      output: `LIVE_ROUND_${round}_OK`
    });
    input.push({
      role: "user",
      content: round < 5
        ? `工具结果已返回，请继续执行第 ${round + 1} 轮，并调用 exec。`
        : "五轮工具结果均已返回，请给出最终完成答复。"
    });
    process.stdout.write(`ROUND=${round} STATUS=completed TOOL=exec\n`);
  }
  process.stdout.write(`FIVE_TURN_TOOL_LOOP=PASS TOOL_CALLS=${toolCalls}\n`);
}

main().catch((error) => {
  console.error(`FIVE_TURN_TOOL_LOOP=FAIL ${error.message}`);
  process.exitCode = 1;
});
