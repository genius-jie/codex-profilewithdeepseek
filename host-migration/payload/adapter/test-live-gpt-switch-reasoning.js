"use strict";

// Live smoke for switching from a third-party model back to native GPT. The
// stale rs_ item mirrors the historical failure; success proves the active
// 15740 service removes only the non-persisted replay state before GPT sees it.
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const codexHome = process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";
const auth = JSON.parse(fs.readFileSync(path.join(codexHome, "auth.json"), "utf8"));
const apiKey = auth.OPENAI_API_KEY;
if (!apiKey) throw new Error(`Codex++ API key is not configured under ${codexHome}`);

const body = {
  model: "gpt-6-astra",
  store: false,
  instructions: "Continue the conversation briefly and confirm the replay boundary is healthy.",
  input: [
    {
      type: "reasoning",
      id: "rs_a01abbc2-720b-4318-a847-6e9ba5cbeb7a",
      summary: [{ type: "summary_text", text: "stale third-party/native summary-only reasoning" }],
      encrypted_content: null,
      status: "completed"
    },
    {
      type: "item_reference",
      id: "ref_stale_gpt_switch",
      item_id: "rs_a01abbc2-720b-4318-a847-6e9ba5cbeb7a"
    },
    { type: "message", role: "user", content: [{ type: "input_text", text: "请继续当前任务，回复 GPT_SWITCH_OK。" }] }
  ],
  max_output_tokens: 64,
  stream: false
};

const raw = JSON.stringify(body);
const req = http.request({
  host: "127.0.0.1",
  port: 15740,
  path: "/v1/responses",
  method: "POST",
  headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json", "content-length": Buffer.byteLength(raw) },
  timeout: 90000
}, (res) => {
  const chunks = [];
  res.on("data", (chunk) => chunks.push(chunk));
  res.on("end", () => {
    const text = Buffer.concat(chunks).toString("utf8");
    if (res.statusCode !== 200) {
      console.error(JSON.stringify({ status: "FAIL", http: res.statusCode, body: text.slice(0, 1000) }));
      process.exitCode = 1;
      return;
    }
    let parsed;
    try { parsed = JSON.parse(text); } catch (_) { parsed = null; }
    if (!parsed || parsed.error || parsed.status === "failed") {
      console.error(JSON.stringify({ status: "FAIL", reason: "GPT response contained an error", body: text.slice(0, 1000) }));
      process.exitCode = 1;
      return;
    }
    console.log(JSON.stringify({ status: "PASS", model: "gpt-6-astra", http: res.statusCode, response_status: parsed.status || "received" }));
  });
});
req.once("timeout", () => req.destroy(new Error("request timed out")));
req.once("error", (error) => {
  console.error(JSON.stringify({ status: "FAIL", error: error.message }));
  process.exitCode = 1;
});
req.end(raw);
