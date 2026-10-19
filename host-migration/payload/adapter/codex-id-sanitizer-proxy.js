const http = require("node:http");
const https = require("node:https");
const { URL } = require("node:url");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { StringDecoder } = require("node:string_decoder");

const LISTEN_HOST = process.env.CODEX_SANITIZER_HOST || "127.0.0.1";
const LISTEN_PORT = Number(process.env.CODEX_SANITIZER_PORT || "15740");
// Upstream is the local CodexManager gateway (default 48760), NOT a third-party
// endpoint directly. Model switching happens inside that gateway; by sitting
// between the Codex++ client and the gateway we see every request regardless
// of which upstream model the gateway routes to.
const UPSTREAM_URL = new URL(process.env.CODEX_SANITIZER_UPSTREAM || "http://127.0.0.1:48760");
const LOG_DIR = process.env.CODEX_SANITIZER_LOG_DIR || path.join(__dirname, "logs-codex-id");
const LOG_FILE = path.join(LOG_DIR, "codex-id-sanitizer.log");
const ADAPTER_VERSION = "responses-summary-v39-qwen-vision-v1";
// Maximum request body size (bytes) we will buffer to sanitize tool call ids.
// Bodies larger than this are passed through unchanged to avoid memory pressure.
const MAX_INTERCEPT_BODY = Number(process.env.CODEX_SANITIZER_MAX_BODY || String(32 * 1024 * 1024));
// A provider-side concurrency rejection is delivered as a 200/SSE stream by
// the gateway. Retry only an empty adapted stream; once any model output or
// tool call has reached Codex++, replaying would duplicate side effects.
const MAX_EMPTY_STREAM_RETRIES = 4;
const EMPTY_STREAM_RETRY_DELAYS_MS = [1000, 3000, 7000, 15000];

// v32: upstream liveness watchdog. Node's http.request has no default
// timeout, so a hung upstream (gateway stall, Cloudflare challenge page,
// dead socket) left the client spinner spinning forever and the single-flight
// queue slot occupied for 70+ minutes (observed 2026-09-24 05:28-06:41, queue
// piled 7->11). Two-stage watchdog: first byte must arrive within
// UPSTREAM_FIRST_BYTE_TIMEOUT_MS; after that, no data for
// UPSTREAM_IDLE_TIMEOUT_MS means the stream is dead. On either timeout the
// client gets a terminal event (SSE response.failed, or a 504 before headers)
// so Codex++ stops spinning instead of waiting forever.
function positiveTimeoutMs(name, fallback) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

const UPSTREAM_FIRST_BYTE_TIMEOUT_MS = positiveTimeoutMs("CODEX_SANITIZER_UPSTREAM_FIRST_BYTE_TIMEOUT_MS", 120000);
const UPSTREAM_IDLE_TIMEOUT_MS = positiveTimeoutMs("CODEX_SANITIZER_UPSTREAM_IDLE_TIMEOUT_MS", 300000);

// DeepSeek's tool endpoint is single-flight for this Codex-compatible
// provider. Keep that constraint in the provider adapter instead of allowing
// several converted Responses requests to race through the gateway. The
// queue is process-local, derived state; it is released on response finish or
// client cancellation and is never persisted as a second runtime state store.
const adaptedRequestQueue = [];
let adaptedRequestActive = null;

// v30: per-model "previous turn was tool-only" flag. When Kimi's last turn
// returned tool_calls with textLength=0 (pure tool, no text), the next turn
// does NOT force tool_choice=required — this gives Kimi an exit channel to
// stop after completing a task instead of looping on meaningless exec calls.
const prevTurnWasToolOnly = new Map(); // model -> boolean

function pumpAdaptedRequestQueue() {
  if (adaptedRequestActive) return;
  while (adaptedRequestQueue.length > 0) {
    const job = adaptedRequestQueue.shift();
    if (job.lifecycle.cancelled) continue;
    adaptedRequestActive = job;
    log("starting queued adapted request", {
      model: job.model,
      queued: adaptedRequestQueue.length
    });
    job.start();
    return;
  }
}

function enqueueAdaptedRequest(job) {
  adaptedRequestQueue.push(job);
  log("queued adapted request", {
    model: job.model,
    queued: adaptedRequestQueue.length,
    active: !!adaptedRequestActive
  });
  pumpAdaptedRequestQueue();
}

function releaseAdaptedRequest(job, reason) {
  if (!job || adaptedRequestActive !== job) return;
  adaptedRequestActive = null;
  log("released adapted request slot", {
    model: job.model,
    reason,
    queued: adaptedRequestQueue.length
  });
  pumpAdaptedRequestQueue();
}

function log(msg, extra = {}) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const line = JSON.stringify({ ts: new Date().toISOString(), msg, ...extra }) + "\n";
    fs.appendFileSync(LOG_FILE, line, "utf8");
  } catch (_) {}
}

function normalizeCustomToolCallId(id) {
  if (typeof id !== "string") return id;
  if (id.startsWith("ctc")) return id;
  if (id.startsWith("msg_")) return "ctc_" + id.slice(4);
  if (id.startsWith("call_")) return "ctc_" + id.slice(5);
  return "ctc_" + id;
}

function transformSseLine(line, sseState) {
  // SSE spec allows "data:" or "data: " before the payload. a2agent (qwen)
  // emits "data:" with no space; OpenAI-native emits "data: ". Match both.
  let dataPrefixLen = 0;
  if (line.startsWith("data: ")) dataPrefixLen = 6;
  else if (line.startsWith("data:")) dataPrefixLen = 5;
  else return line;
  const rawData = line.slice(dataPrefixLen).trim();
  if (!rawData || rawData === "[DONE]") return line;

  try {
    const json = JSON.parse(rawData);
    let modified = false;

    const itemCandidates = [];
    if (json && json.output_item) itemCandidates.push(json.output_item);
    if (json && json.item) itemCandidates.push(json.item);

    for (const it of itemCandidates) {
      if (it && it.type === "custom_tool_call") {
        const origId = it.id;
        const newId = normalizeCustomToolCallId(origId);
        if (newId !== origId) {
          it.id = newId;
          modified = true;
        }
        if (sseState) {
          if (typeof it.input === "string" && it.input.trim().startsWith("{")) {
            // Complete input already present on this event: unwrap in place.
            if (unwrapExecInput(it)) modified = true;
            if (sseState.pending && sseState.pending.id === it.id) sseState.pending = null;
          } else if (json.type === "response.output_item.added" && typeof it.id === "string") {
            // Input will arrive as deltas: start accumulating for this item.
            sseState.pending = { id: it.id, index: json.output_index, name: it.name, input: "", unwrapped: null };
          }
        }
      }
    }

    // Normalize item_id references in any event that carries one. The added
    // event may have rewritten item.id from msg_ to ctc_; downstream delta/done
    // events still reference the original msg_ id and must be kept in sync so
    // the client can correlate them. Done before the pending state-machine
    // branch so pending.id (ctc_) matches the rewritten item_id (ctc_).
    if (json && typeof json.item_id === "string" && json.item_id.startsWith("msg_")) {
      json.item_id = "ctc_" + json.item_id.slice(4);
      modified = true;
    }

    // Streaming custom_tool_call input: accumulate deltas, unwrap at done,
    // preserving the client's expected event sequence
    // (added -> input.delta* -> input.done -> output_item.done).
    if (sseState && sseState.pending) {
      const p = sseState.pending;
      if (json && json.type === "response.custom_tool_call.input.delta") {
        p.input += typeof json.delta === "string" ? json.delta : "";
        return null;
      }
      if (json && json.type === "response.custom_tool_call.input.done") {
        const full = p.input + (typeof json.input === "string" ? json.input : "");
        const probe = { type: "custom_tool_call", name: p.name, input: full };
        if (unwrapExecInput(probe)) {
          p.unwrapped = probe.input;
          json.input = probe.input;
          log("unwrapped streamed exec input envelope", { id: p.id });
          return "data: " + JSON.stringify(json);
        }
        return line;
      }
      if (json && json.type === "response.output_item.done") {
        const it2 = json.item;
        if (it2 && it2.type === "custom_tool_call" && it2.id === p.id) {
          if (p.unwrapped != null) {
            it2.input = p.unwrapped;
          } else if (typeof it2.input === "string") {
            unwrapExecInput(it2);
          }
          sseState.pending = null;
          return "data: " + JSON.stringify(json);
        }
      }
    }

    // Terminal events carry the full output array: unwrap envelopes there too.
    if (json && json.response && Array.isArray(json.response.output)) {
      let u = 0;
      for (const it of json.response.output) {
        if (unwrapExecInput(it)) u++;
      }
      if (u > 0) {
        log("unwrapped exec input envelope in terminal event", { type: json.type, fixed: u });
        return "data: " + JSON.stringify(json);
      }
    }

    if (json && Array.isArray(json.choices)) {
      for (const choice of json.choices) {
        if (choice.delta && Array.isArray(choice.delta.tool_calls)) {
          for (const tc of choice.delta.tool_calls) {
            if (tc.type === "custom_tool_call" || tc.id) {
              if (tc.id && tc.id.startsWith("msg_")) {
                tc.id = "ctc_" + tc.id.slice(4);
                modified = true;
              }
            }
          }
        }
      }
    }

    if (modified) {
      return "data: " + JSON.stringify(json);
    }
  } catch (_) {}
  return line;
}

// --- Request-direction sanitization -------------------------------------
// OpenAI's Responses protocol requires custom_tool_call ids to begin with
// `ctc_` and function_call ids to begin with `fc_`. Third-party gateways
// (Qwen / a2agent etc.) emit Anthropic-style `msg_` ids. When a session that
// ran tools under a third-party model is replayed to an OpenAI-native model,
// the historical ids trip a hard HTTP 400. We rewrite them on the way out.

function rewriteToolId(id, wantPrefix) {
  if (typeof id !== "string" || id.startsWith(wantPrefix)) return id;
  if (id.startsWith("msg_")) return wantPrefix + id.slice(4);
  if (id.startsWith("call_")) return wantPrefix + id.slice(5);
  return wantPrefix + id;
}

/**
 * Some upstreams (observed: qwen via a2agent) wrap code-mode tool input in a
 * JSON envelope: input = '{"data": "<the real JS script>"}'. The Codex client
 * executes `input` as a JS statement, so the envelope parses as a block with a
 * string expression and dies on the colon:
 *   SyntaxError: Unexpected token ':'
 * Unwrap it back to the bare script. Returns true when rewritten.
 */
function extractExecScriptEnvelope(value) {
  let obj = null;
  if (typeof value === "string") {
    const t = value.trim();
    if (!t.startsWith("{")) return null;
    try { obj = JSON.parse(t); } catch (_) { return null; }
  } else if (value && typeof value === "object" && !Array.isArray(value)) {
    obj = value;
  } else {
    return null;
  }
  for (const key of ["data", "code", "input", "arguments"]) {
    if (obj && typeof obj[key] === "string") return { key, script: obj[key], keys: Object.keys(obj) };
  }
  // DeepSeek can emit the host shell payload directly through the code-mode
  // `exec` tool: {"cmd":"...", "workdir":"..."}. Passing that JSON as JS
  // produces `SyntaxError: Unexpected token ':'`; translate it to the same
  // tools.exec_command bridge used for the explicit exec_command alias.
  if (obj && typeof obj.cmd === "string") {
    const literal = JSON.stringify(obj);
    const script = `const r = await tools.exec_command(${literal}); text(r && r.output !== undefined ? r.output : r);`;
    return { key: "cmd", script, keys: Object.keys(obj) };
  }
  return obj ? { key: null, script: null, keys: Object.keys(obj) } : null;
}

function unwrapExecInput(item) {
  if (!item || typeof item !== "object" || item.type !== "custom_tool_call" || item.name !== "exec") return false;
  // Debug logging
  try {
    const debugLog = { ts: new Date().toISOString(), fn: "unwrapExecInput", item: { type: item?.type, name: item?.name, input: item?.input?.slice(0, 200) } };
    fs.appendFileSync(path.join(LOG_DIR, "debug-exec.log"), JSON.stringify(debugLog) + "\n");
  } catch (_) {}

  const inp = item.input;
  const envelope = extractExecScriptEnvelope(inp);
  if (!envelope) {
    return false;
  }

  // Debug: log parsed obj
  try {
    const debugLog = { ts: new Date().toISOString(), fn: "unwrapExecInput", objKeys: envelope.keys, envelopeKey: envelope.key };
    fs.appendFileSync(path.join(LOG_DIR, "debug-exec.log"), JSON.stringify(debugLog) + "\n");
  } catch (_) {}

  if (envelope.key && typeof envelope.script === "string") {
    item.input = envelope.script;
    try {
      const debugLog = { ts: new Date().toISOString(), fn: "unwrapExecInput", action: "UNWRAPPED_" + envelope.key.toUpperCase(), code: envelope.script.slice(0, 100) };
      fs.appendFileSync(path.join(LOG_DIR, "debug-exec.log"), JSON.stringify(debugLog) + "\n");
    } catch (_) {}
    return true;
  }

  return false;
}

function isNonPersistedReasoningItem(item) {
  return !!(
    item && typeof item === "object" && item.type === "reasoning" &&
    typeof item.id === "string" && item.id.startsWith("rs_") &&
    !item.encrypted_content
  );
}

function isReferenceToNonPersistedReasoning(item, droppedIds, persistedIds) {
  if (!item || typeof item !== "object" || item.type !== "item_reference") return false;
  const candidates = [item.id, item.item_id, item.reference_id];
  return candidates.some((value) => {
    if (typeof value !== "string") return false;
    return droppedIds.has(value) || (value.startsWith("rs_") && !persistedIds.has(value));
  });
}

function walkResponsesArrays(value, visitor) {
  if (Array.isArray(value)) {
    value.forEach((item) => visitor(item));
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const key of ["input", "output", "included", "content", "arguments"]) {
    if (Array.isArray(value[key])) walkResponsesArrays(value[key], visitor);
  }
}

function stripNonPersistedReasoning(obj) {
  // With store=false the provider has no server-side item to resolve on the
  // next model request. Keep self-contained native reasoning items that carry
  // encrypted_content; remove only the non-persisted form and its references.
  if (!obj || typeof obj !== "object" || obj.store !== false) return 0;
  const droppedIds = new Set();
  const persistedIds = new Set();
  walkResponsesArrays(obj, (item) => {
    if (!item || typeof item !== "object" || item.type !== "reasoning" || typeof item.id !== "string") return;
    if (isNonPersistedReasoningItem(item)) droppedIds.add(item.id);
    else if (item.encrypted_content) persistedIds.add(item.id);
  });
  if (!droppedIds.size && !persistedIds.size) return 0;

  let removed = 0;
  const prune = (array) => {
    for (let i = array.length - 1; i >= 0; i -= 1) {
      const item = array[i];
      if (isNonPersistedReasoningItem(item) || isReferenceToNonPersistedReasoning(item, droppedIds, persistedIds)) {
        array.splice(i, 1);
        removed += 1;
        continue;
      }
      if (!item || typeof item !== "object") continue;
      for (const key of ["input", "output", "included", "content", "arguments"]) {
        if (Array.isArray(item[key])) prune(item[key]);
      }
    }
  };
  for (const key of ["input", "output", "included"]) {
    if (Array.isArray(obj[key])) prune(obj[key]);
  }
  if (Array.isArray(obj)) prune(obj);
  return removed;
}

/**
 * Sanitize a parsed Responses request body in place.
 * Returns the number of body changes (for logging).
 */
function sanitizeResponsesBody(obj, skipReasoningStrip) {
  let fixed = skipReasoningStrip ? 0 : stripNonPersistedReasoning(obj);
  if (!obj || typeof obj !== "object") return 0;
  // Debug: log entry
  try {
    const debugLog = { ts: new Date().toISOString(), fn: "sanitizeResponsesBody", keys: Object.keys(obj), hasInput: Array.isArray(obj.input), inputLen: Array.isArray(obj.input) ? obj.input.length : 0 };
    fs.appendFileSync(path.join(LOG_DIR, "debug-sanitize.log"), JSON.stringify(debugLog) + "\n");
  } catch (_) {}

  const visitItem = (item) => {
    if (!item || typeof item !== "object") return;
    fixed += normalizeImageContentItem(item);
    const t = item.type;
    if (unwrapExecInput(item)) fixed++;
    // Older exec envelope adapters leaked a non-Responses `code` sibling.
    // The script is already in input; GPT rejects the transport-only sibling.
    if (t === "custom_tool_call" && item.name === "exec" && Object.prototype.hasOwnProperty.call(item, "code")) {
      delete item.code;
      fixed++;
    }
    if (t === "custom_tool_call" || t === "function_call") {
      // item.id identifies the Responses item; call_id joins a call to its
      // result and is opaque. Preserve native call_* values on both sides.
      // Legacy adapters omitted call_id and used item.id as the correlation.
      if (!item.call_id && typeof item.id === "string") {
        item.call_id = item.id;
        fixed++;
      }
      const prefix = t === "custom_tool_call" ? "ctc_" : "fc_";
      if (typeof item.id === "string" && !item.id.startsWith(prefix)) {
        item.id = rewriteToolId(item.id, prefix);
        fixed++;
      }
    } else if ((t === "custom_tool_call_output" || t === "function_call_output") &&
        !item.call_id && typeof item.tool_call_id === "string") {
      item.call_id = item.tool_call_id;
      fixed++;
    }
    // Recurse into nested containers some variants use.
    for (const key of ["input", "output", "included", "content", "arguments"]) {
      const v = item[key];
      if (Array.isArray(v)) v.forEach(visitItem);
    }
  };

  for (const key of ["input", "output", "included", "messages"]) {
    if (Array.isArray(obj[key])) obj[key].forEach(visitItem);
  }
  // Some Responses payloads put the history directly at top-level without a wrapper.
  if (Array.isArray(obj)) obj.forEach(visitItem);

  return fixed;
}

/**
 * Decide whether a request path/method should be intercepted for body
 * sanitization. Only POST to a `responses` endpoint qualifies.
 */
function isResponsesWriteRequest(method, pathname) {
  if (method !== "POST") return false;
  // Match /v1/responses, /responses, and /v1/responses/compact etc.
  return /(^|\/)responses(\b|\/|$)/i.test(pathname);
}

// --- Responses <-> chat/completions protocol adaptation -----------------
// a2agent.me exposes the stable Chat Completions surface for third-party
// models (deepseek-v4-pro, kimi-k3 and GLM-5.x). The Codex client speaks the Responses protocol, and the
// CodexManager gateway passes the client path through untouched for
// aggregate APIs, so those models 502 with upstream_error. We adapt here:
// rewrite the request to /v1/chat/completions and translate the response
// back into Responses shape (streaming included).
const CHAT_ONLY_MODELS = new Set(
  (process.env.CODEX_SANITIZER_CHAT_ONLY_MODELS || "deepseek-v4-pro,kimi-k3,qwen3.8-max,qwen3.8-flash,glm-5.2,glm-5.3,glm-5.3-flash")
    .split(",").map((s) => s.trim()).filter(Boolean)
);

// Remote compaction v2 is carried on the ordinary Responses endpoint. Codex
// appends a `compaction_trigger` input item and expects exactly one
// `compaction` output item back. Chat-only providers do not understand either
// private Responses item, so keep the summary in an opaque, adapter-owned
// envelope and unwrap it only when replaying history to a chat provider.
const ADAPTER_COMPACTION_PREFIX = "ccs1:";
const REMOTE_COMPACTION_INSTRUCTION =
  "This is a context compaction request. Return one concise, self-contained summary of the conversation, decisions, files, tool results, and unfinished work. Do not call tools. Output summary text only.";

function hasCompactionTrigger(body) {
  return !!(body && Array.isArray(body.input) && body.input.some((item) =>
    item && typeof item === "object" && item.type === "compaction_trigger"
  ));
}

function encodeAdapterCompactionSummary(summary) {
  const text = typeof summary === "string" && summary.trim()
    ? summary.trim()
    : "Earlier context was compacted; rely on the retained conversation items.";
  return ADAPTER_COMPACTION_PREFIX + Buffer.from(text, "utf8").toString("base64");
}

function decodeAdapterCompactionSummary(value) {
  if (typeof value !== "string" || !value.startsWith(ADAPTER_COMPACTION_PREFIX)) return null;
  try {
    const decoded = Buffer.from(value.slice(ADAPTER_COMPACTION_PREFIX.length), "base64").toString("utf8");
    return decoded.trim() || null;
  } catch (_) {
    return null;
  }
}

function compactionItemFromSummary(summary, id = rid("cmp_")) {
  return {
    type: "compaction",
    id,
    encrypted_content: encodeAdapterCompactionSummary(summary)
  };
}

function chatMessageText(message) {
  if (!message || typeof message !== "object") return "";
  if (typeof message.content === "string") return message.content;
  if (Array.isArray(message.content)) {
    return message.content.map((part) => {
      if (typeof part === "string") return part;
      return part && typeof part.text === "string" ? part.text : "";
    }).filter(Boolean).join("\n");
  }
  return "";
}

function compactionSummaryFromChat(chat) {
  const message = chat && Array.isArray(chat.choices) && chat.choices[0] && chat.choices[0].message;
  const content = chatMessageText(message);
  if (content.trim()) return content;
  return message && typeof message.reasoning_content === "string" ? message.reasoning_content : "";
}

function downgradeAdapterCompactionMarkers(body) {
  let fixed = 0;
  const visit = (value) => {
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    if (!value || typeof value !== "object") return;
    if (value.type === "compaction" && typeof value.encrypted_content === "string") {
      const summary = decodeAdapterCompactionSummary(value.encrypted_content);
      if (summary) {
        const originalId = value.id;
        value.type = "message";
        // A compaction item uses a `cmp_` id. Once its adapter-owned summary
        // is downgraded to a normal Responses message, Codex's public item
        // contract requires a `msg_` id. Never replay the private compaction
        // id as a message id.
        value.id = rid("msg_");
        value.role = "assistant";
        // This is an assistant message after the downgrade. Responses uses
        // output_text for assistant content; input_text is only valid for
        // user/developer input and is rejected during native replay.
        value.content = [{ type: "output_text", text: `[Previous context summary]\n${summary}` }];
        delete value.encrypted_content;
        fixed++;
        log("downgraded adapter compaction marker to Responses message", {
          originalId: typeof originalId === "string" ? originalId : null,
          messageId: value.id
        });
        return;
      }
    }
    for (const key of ["input", "output", "included", "messages", "content"]) visit(value[key]);
  };
  visit(body);
  return fixed;
}

const DEEPSEEK_MULTIMODAL_MODEL = "deepseek-v4.1-flash";



// Kimi can spend a small output budget entirely on reasoning_summary events
// before emitting the required tool call. Keep the provider adapter's
// capability normalization local to Kimi; do not inflate other models' user
// budgets or change the Codex++ host contract.
const MIN_OUTPUT_TOKENS_BY_MODEL = new Map([
  ["kimi-k3", 1024]
]);

// Codex++ parses item ids as UUID-shaped strings (msg_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).
// Plain hex without hyphens (e.g. msg_e4bf55b05820844092c0e669) makes serde reject the
// whole ResponseItem in output_item.added/done — the turn completes server-side but the
// user sees no reply. Generate UUID-with-hyphens ids to match the qwen passthrough shape.
const rid = (prefix) => {
  const b = crypto.randomBytes(16);
  // RFC 4122 v4 layout: set version (4) and variant (8/9/a/b)
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const hex = b.toString("hex");
  const uuid = `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  return prefix + uuid;
};

function imageMimeFromBase64(value) {
  if (typeof value !== "string") return null;
  const encoded = value.trim().replace(/\s+/g, "");
  if (encoded.startsWith("iVBORw0KGgo")) return "image/png";
  if (encoded.startsWith("/9j/")) return "image/jpeg";
  if (encoded.startsWith("R0lGOD")) return "image/gif";
  if (encoded.startsWith("UklGR")) return "image/webp";
  if (encoded.startsWith("Qk")) return "image/bmp";
  return null;
}

function normalizeImageDataUrl(value, hintedMime = null) {
  if (typeof value !== "string") return { value, changed: false };
  const match = /^data:([^;,]+)(;base64)?,([\s\S]*)$/i.exec(value);
  if (!match) return { value, changed: false };
  const currentMime = match[1].toLowerCase();
  const hinted = typeof hintedMime === "string" && /^image\//i.test(hintedMime)
    ? hintedMime.toLowerCase()
    : null;
  const sniffed = match[2] ? imageMimeFromBase64(match[3]) : null;
  const nextMime = ["application/octet-stream", "binary/octet-stream", "application/binary"].includes(currentMime)
    ? (sniffed || hinted || currentMime)
    : currentMime;
  if (nextMime === currentMime) return { value, changed: false };
  return {
    value: `data:${nextMime}${match[2] || ""},${match[3]}`,
    changed: true
  };
}

function imageMimeHint(item) {
  if (!item || typeof item !== "object") return null;
  for (const key of ["mime_type", "mimeType", "content_type", "contentType"]) {
    if (typeof item[key] === "string" && item[key].trim()) return item[key].trim();
  }
  return null;
}

function isImageContentItem(item) {
  if (!item || typeof item !== "object") return false;
  const type = typeof item.type === "string" ? item.type : "";
  return ["input_image", "output_image", "image", "image_url"].includes(type) ||
    item.image_url != null || item.imageUrl != null ||
    (typeof item.data === "string" && /^image\//i.test(imageMimeHint(item) || ""));
}

/**
 * Repair image MIME metadata at the shared Responses boundary. The native
 * view_image tool currently emits PNG data with application/octet-stream;
 * third-party model adapters must receive a real image MIME instead.
 */
function normalizeImageContentItem(item) {
  if (!isImageContentItem(item)) return 0;
  let fixed = 0;
  const hint = imageMimeHint(item);

  const normalizeStringField = (container, key) => {
    if (!container || typeof container[key] !== "string") return;
    const normalized = normalizeImageDataUrl(container[key], hint);
    if (normalized.changed) {
      container[key] = normalized.value;
      fixed++;
    }
  };

  for (const key of ["image_url", "imageUrl", "url"]) {
    const value = item[key];
    if (typeof value === "string") {
      normalizeStringField(item, key);
    } else if (value && typeof value === "object") {
      normalizeStringField(value, "url");
      normalizeStringField(value, "image_url");
    }
  }

  if (typeof item.data === "string") {
    const normalized = normalizeImageDataUrl(item.data, hint);
    if (normalized.changed) {
      item.data = normalized.value;
      fixed++;
    } else if (!item.data.startsWith("data:")) {
      const sniffed = imageMimeFromBase64(item.data);
      if (sniffed && hint && !/^image\//i.test(hint)) {
        if (Object.prototype.hasOwnProperty.call(item, "mime_type")) item.mime_type = sniffed;
        if (Object.prototype.hasOwnProperty.call(item, "mimeType")) item.mimeType = sniffed;
        fixed++;
      }
    }
  }

  return fixed;
}

function contentToChatPart(part) {
  if (typeof part === "string") return { type: "text", text: part };
  if (!part || typeof part !== "object") return null;
  const type = typeof part.type === "string" ? part.type : "";
  if (["input_text", "output_text", "text"].includes(type)) {
    return typeof part.text === "string" ? { type: "text", text: part.text } : null;
  }
  if (!isImageContentItem(part)) return null;

  let rawUrl = null;
  let detail = typeof part.detail === "string" ? part.detail : null;
  if (typeof part.image_url === "string") {
    rawUrl = part.image_url;
  } else if (part.image_url && typeof part.image_url === "object") {
    rawUrl = typeof part.image_url.url === "string"
      ? part.image_url.url
      : (typeof part.image_url.image_url === "string" ? part.image_url.image_url : null);
    if (!detail && typeof part.image_url.detail === "string") detail = part.image_url.detail;
  } else if (typeof part.imageUrl === "string") {
    rawUrl = part.imageUrl;
  } else if (typeof part.url === "string") {
    rawUrl = part.url;
  } else if (typeof part.data === "string") {
    rawUrl = part.data;
    if (!rawUrl.startsWith("data:")) {
      const mime = imageMimeFromBase64(rawUrl) || (imageMimeHint(part) && /^image\//i.test(imageMimeHint(part)) ? imageMimeHint(part) : "image/png");
      rawUrl = `data:${mime};base64,${rawUrl}`;
    }
  }
  if (typeof rawUrl !== "string" || !rawUrl) return null;
  const normalized = normalizeImageDataUrl(rawUrl, imageMimeHint(part));
  const imageUrl = { url: normalized.value };
  // Chat Completions accepts auto/low/high. Preserve those values and map
  // Responses-only "original" to the closest supported high-detail mode.
  if (["auto", "low", "high"].includes(detail)) imageUrl.detail = detail;
  else if (detail === "original") imageUrl.detail = "high";
  return { type: "image_url", image_url: imageUrl };
}

/** Responses content -> Chat Completions content, including images. */
function contentToChatContent(content) {
  if (typeof content === "string") return content;
  const parts = Array.isArray(content) ? content : (content && typeof content === "object" ? [content] : []);
  const mapped = parts.map(contentToChatPart).filter(Boolean);
  if (!mapped.length) return "";
  if (mapped.length === 1 && mapped[0].type === "text") return mapped[0].text;
  return mapped;
}

function bodyContainsImage(value) {
  const pending = [value];
  while (pending.length) {
    const current = pending.pop();
    if (!current || typeof current !== "object") continue;
    if (isImageContentItem(current)) return true;
    if (Array.isArray(current)) {
      pending.push(...current);
      continue;
    }
    for (const key of ["input", "output", "included", "messages", "content"]) {
      if (current[key] && typeof current[key] === "object") pending.push(current[key]);
    }
  }
  return false;
}

const HISTORICAL_IMAGE_PLACEHOLDER =
  "[Earlier image omitted after visual analysis; use the preceding assistant text summary.]";

function isUserMessageItem(item) {
  if (!item || typeof item !== "object") return false;
  if (item.type === "message") return item.role === "user" || item.role === "developer";
  return !item.type && (item.role === "user" || item.role === "developer");
}

function latestUserMessage(body) {
  for (const key of ["input", "messages"]) {
    const items = body && Array.isArray(body[key]) ? body[key] : [];
    for (let i = items.length - 1; i >= 0; i--) {
      if (isUserMessageItem(items[i])) return items[i];
    }
  }
  return null;
}

function stripHistoricalImages(body, latest) {
  if (!latest) return 0;
  let stripped = 0;
  const visit = (value, keepImages = false) => {
    if (Array.isArray(value)) return value.map((item) => visit(item, keepImages || item === latest));
    if (!value || typeof value !== "object") return value;
    if (isImageContentItem(value) && !keepImages) {
      stripped++;
      return { type: "input_text", text: HISTORICAL_IMAGE_PLACEHOLDER };
    }
    const next = {};
    for (const [key, child] of Object.entries(value)) next[key] = visit(child, keepImages);
    return next;
  };
  const nextBody = visit(body);
  for (const key of Object.keys(body)) delete body[key];
  Object.assign(body, nextBody);
  return stripped;
}

const TOOL_RESULT_META_PREFIX = "[CODEX_TOOL_RESULT_META]";

// The exec code-mode result has two consumers: a human needs stdout/stderr,
// while the next model turn needs an explicit machine outcome. Keep both in a
// single output contract. Do not infer failure from rendered prose.
function withExecResultMetadataScript(input) {
  if (typeof input !== "string" || !input.includes("tools.exec_command") || input.includes(TOOL_RESULT_META_PREFIX)) return input;
  return `${input}\ntry { if (typeof r !== "undefined") { const exitCode = typeof r.exit_code === "number" ? r.exit_code : (typeof r.exitCode === "number" ? r.exitCode : null); text("\\n${TOOL_RESULT_META_PREFIX}" + JSON.stringify({ ok: exitCode === null ? null : exitCode === 0, exit_code: exitCode })); } } catch (_) {}`;
}

function readToolResultMetadata(text) {
  if (typeof text !== "string") return null;
  const index = text.lastIndexOf(TOOL_RESULT_META_PREFIX);
  if (index < 0) return null;
  try {
    const value = JSON.parse(text.slice(index + TOOL_RESULT_META_PREFIX.length).trim());
    return value && typeof value === "object" ? value : null;
  } catch (_) {
    return null;
  }
}

// Chat tool_calls.id corresponds to Responses call_id, not Responses item.id.
// Prefix aliases are a legacy fallback only, and must not resolve collisions.
function toolIdLookupKey(id) {
  if (typeof id !== "string" || !id) return "";
  return id.replace(/^(?:ctc_|fc_|call_|msg_)/, "");
}

function rememberToolCall(index, ids, call) {
  for (const id of ids) {
    if (typeof id !== "string" || !id) continue;
    index.exact.set(id, call);
    const key = toolIdLookupKey(id);
    if (!key) continue;
    if (index.aliases.has(key) && index.aliases.get(key) !== call) index.aliases.set(key, null);
    else if (!index.aliases.has(key)) index.aliases.set(key, call);
  }
}

function resolveToolCall(index, id) {
  return index.exact.get(id) || index.aliases.get(toolIdLookupKey(id)) || null;
}

// Kimi can end the turn with a short announcement right after a successful
// tool result instead of continuing the task. The machine result envelope
// only forces continuation on failures (ok=false), so the success path needs
// a behavioral contract carried in the tool schema itself.
const KIMI_CONTINUATION_CONTRACT_MODELS = new Set(["kimi-k3"]);
const KIMI_CONTINUATION_CONTRACT =
  "\nAfter this tool returns its result, never end the turn with only an announcement of what you will do next. Either call another tool to continue the task, or, if the task is already fully complete, reply with the final concrete result.";

function withKimiContinuationContract(description, modelName) {
  if (!KIMI_CONTINUATION_CONTRACT_MODELS.has(modelName)) return description;
  const base = typeof description === "string" ? description : "";
  return base.includes(KIMI_CONTINUATION_CONTRACT) ? base : base + KIMI_CONTINUATION_CONTRACT;
}

// Responses carries the Codex++ reasoning selection as `reasoning.effort`.
// The Chat Completions provider expects the same choice under
// `reasoning_effort`; dropping it makes the UI's highest Kimi setting look
// accepted while the upstream silently uses its default.  Keep this mapping
// in the existing protocol adapter and omit `none`/unknown values so models
// that do not support reasoning are not sent a new field.
const SUPPORTED_REASONING_EFFORTS = new Set(["low", "medium", "high", "xhigh", "max", "ultra"]);

function getReasoningEffort(body) {
  const nested = body && body.reasoning && typeof body.reasoning === "object"
    ? body.reasoning.effort
    : null;
  const raw = typeof nested === "string"
    ? nested
    : typeof body?.reasoning_effort === "string"
      ? body.reasoning_effort
      : "";
  const effort = raw.trim().toLowerCase();
  return SUPPORTED_REASONING_EFFORTS.has(effort) ? effort : null;
}

/** Responses request body -> chat/completions request body. */
function responsesToChat(body, state) {
  const messages = [];
  let latestToolBatchHasFailure = false;
  let latestToolBatchHasAnyResult = false;
  if (typeof body.instructions === "string" && body.instructions) {
    messages.push({ role: "system", content: body.instructions });
  }
  if (state.compactionMode) {
    messages.push({ role: "system", content: REMOTE_COMPACTION_INSTRUCTION });
  }
  const toolTypes = {};
  const toolNames = { exact: new Map(), aliases: new Map() };
  let pendingToolCalls = [];
  const declaredCustomToolNames = [];
  if (Array.isArray(body.tools)) {
    for (const t of body.tools) {
      if (!t || typeof t !== "object" || typeof t.name !== "string") continue;
      if (t.type === "custom") declaredCustomToolNames.push(t.name);
      if (t.type === "custom" || t.type === "function") toolTypes[t.name] = t.type;
    }
  }
  // Codex++ newer builds send `input` in multiple shapes: a bare string, an
  // array of {role, content} items WITHOUT a `type` field, or the older
  // {type:"message", role, content} items. The chat/completions endpoint needs
  // every conversational turn mapped to a messages entry — dropping them
  // yields `messages cannot be empty` from the upstream. Normalize all three.
  const items = Array.isArray(body.input)
    ? body.input
    : (typeof body.input === "string" ? [{ role: "user", content: body.input }] : []);
  for (const it of items) {
    if (!it || typeof it !== "object") {
      if (typeof it === "string") messages.push({ role: "user", content: it });
      continue;
    }
    if (it.type === "compaction") {
      const summary = decodeAdapterCompactionSummary(it.encrypted_content);
      messages.push({
        role: "assistant",
        content: summary
          ? `[Previous context summary]\n${summary}`
          : "[Previous context was compacted by another provider; use the retained conversation items.]"
      });
      pendingToolCalls = [];
      continue;
    }
    if (it.type === "compaction_trigger") {
      // The trigger is a protocol control item. Its meaning is represented by
      // REMOTE_COMPACTION_INSTRUCTION above; it must not become chat content.
      continue;
    }
    const isMessageLike = it.type === "message" || (!it.type && (it.role === "user" || it.role === "assistant" || it.role === "system" || it.role === "developer"));
    if (isMessageLike) {
      const role = it.role === "developer" ? "system" : (it.role || "user");
      messages.push({ role, content: contentToChatContent(it.content) });
      pendingToolCalls = [];
      latestToolBatchHasFailure = false;
      // v26: latestToolBatchHasAnyResult is NOT reset by any message item
      // (user, system, or assistant). Once the session has seen a tool result,
      // Kimi must keep calling tools while tools are available — this prevents
      // the "announce next step then stop" escape via user "继续" or assistant
      // text between tool batches. The flag starts false and only goes true on
      // a tool_call_output; it never goes back to false within the session.
    } else if (it.type === "function_call" || it.type === "custom_tool_call") {
      const name = typeof it.name === "string" ? it.name : "tool";
      toolTypes[name] = it.type === "function_call" ? "function" : "custom";
      const callId = it.call_id || it.id || rid("call_");
      const call = { id: callId, name, type: it.type, consumed: false };
      rememberToolCall(toolNames, [callId, it.id], call);
      pendingToolCalls.push(call);
      const rawToolInput = it.type === "custom_tool_call" ? it.input : it.arguments;
      const chatCall = {
          id: callId,
          type: "function",
          function: {
            name,
            arguments: it.type === "custom_tool_call"
              ? JSON.stringify({input: typeof rawToolInput === "string" ? rawToolInput : JSON.stringify(rawToolInput == null ? {} : rawToolInput)})
              : (typeof rawToolInput === "string" ? rawToolInput : JSON.stringify(rawToolInput == null ? {} : rawToolInput))
          }
      };
      // Responses emits one item per parallel call. Chat represents the same
      // batch in one assistant message; splitting it resets Kimi's tool context.
      const previous = messages[messages.length - 1];
      if (previous && previous.role === "assistant" && Array.isArray(previous.tool_calls)) {
        previous.tool_calls.push(chatCall);
      } else {
        messages.push({ role: "assistant", content: null, tool_calls: [chatCall] });
      }
    } else if (it.type === "function_call_output" || it.type === "custom_tool_call_output") {
      const toolCallId = it.call_id || it.tool_call_id || "";
      const explicitName = typeof it.name === "string" ? it.name
        : (typeof it.tool === "string" ? it.tool : "");
      const callType = it.type === "function_call_output" ? "function_call" : "custom_tool_call";
      let matched = resolveToolCall(toolNames, toolCallId);
      if (matched && matched.type !== callType) matched = null;
      if (!matched) {
        const candidates = pendingToolCalls.filter(c => !c.consumed && c.type === callType && (!explicitName || c.name === explicitName));
        if (candidates.length === 1) matched = candidates[0];
      }
      const compatibleExplicitName = !matched || !explicitName || explicitName === matched.name;
      let resolvedName = compatibleExplicitName ? (matched ? matched.name : explicitName) : "";
      if (!resolvedName && it.type === "custom_tool_call_output") {
        // Code-mode has one declared custom tool in Codex++ (normally exec).
        // A truncated/switching history can retain the output without the
        // preceding assistant item; Kimi still needs the tool name to accept it.
        if (compatibleExplicitName && !matched && declaredCustomToolNames.length === 1) resolvedName = declaredCustomToolNames[0];
      }
      if (!resolvedName) {
        const error = new Error("Tool result has no unambiguous matching call/name; preserve its source history instead of guessing from tool declaration order.");
        error.code = "unresolved_tool_result";
        throw error;
      }
      if (matched) matched.consumed = true;
      const toolMessage = {
        role: "tool",
        tool_call_id: matched ? matched.id : toolCallId,
        content: contentToChatContent(it.output)
      };
      const resultMeta = readToolResultMetadata(toolMessage.content);
      latestToolBatchHasFailure = latestToolBatchHasFailure || resultMeta?.ok === false || (typeof resultMeta?.exit_code === "number" && resultMeta.exit_code !== 0);
      latestToolBatchHasAnyResult = true;
      if (resolvedName) toolMessage.name = resolvedName;
      messages.push({
        ...toolMessage
      });
    }
    // reasoning / item_reference / others: dropped, chat protocol has no slot.
  }
  state.toolTypes = toolTypes;

  const chat = { model: body.model, messages };
  if (body.stream) chat.stream = true;
  const reasoningEffort = getReasoningEffort(body);
  if (reasoningEffort) chat.reasoning_effort = reasoningEffort;
  if (typeof body.max_output_tokens === "number") {
    const minimum = MIN_OUTPUT_TOKENS_BY_MODEL.get(body.model) || 0;
    chat.max_tokens = Math.max(body.max_output_tokens, minimum);
  }
  if (typeof body.temperature === "number") chat.temperature = body.temperature;
  if (typeof body.top_p === "number") chat.top_p = body.top_p;
  if (!state.compactionMode && Array.isArray(body.tools)) {
    const tools = [];
    for (const t of body.tools) {
      if (!t || typeof t !== "object") continue;
      if (t.type === "function" || t.type === "custom") {
        toolTypes[t.name] = t.type;
        tools.push({
          type: "function",
          function: {
            name: t.name,
            description: t.type === "custom"
              ? withKimiContinuationContract(
                `${t.description || ""}\nPass the exact free-form tool input in the required input string. Do not call this function with empty arguments.`,
                body.model
              )
              : t.description,
            parameters: t.type === "custom"
              ? { type: "object", properties: { input: { type: "string", minLength: 1, description: "The complete, literal input to the original custom tool." } }, required: ["input"], additionalProperties: false }
              : (t.parameters || { type: "object", properties: {} })
          }
        });
      }
    }
    if (tools.length) chat.tools = tools;
  }
  // v24 tried a soft contract in the exec tool description; Kimi ignores it and
  // still stops on a one-sentence announcement after a successful tool result.
  // v25 makes the continuation a protocol-level hard constraint: kimi-k3 with
  // any preceding tool batch (success or failure) and available tools must keep
  // calling tools. tool_choice=required is a single-request parameter, not a
  // replay: it does not resend the request or duplicate side effects.
  // v30: do not force tool_choice when the previous Kimi turn was tool-only
  // (tool_calls with no text). That turn already did its work; forcing another
  // tool call makes Kimi loop on meaningless exec calls after task completion.
  // This gives Kimi an exit channel: after a pure-tool turn, the next turn can
  // output a text summary and stop naturally.
  const prevWasToolOnly = prevTurnWasToolOnly.get(body.model) === true;
  if (body.model === "kimi-k3" && latestToolBatchHasAnyResult && !prevWasToolOnly && Array.isArray(chat.tools) && chat.tools.length) {
    chat.tool_choice = "required";
    state.kimiErrorToolContinuation = true;
  }
  return chat;
}

// Codex++ 26.901's local exec_command router consumes the public host fields
// `cmd`, `workdir`, and `yield_time_ms`. Third-party chat models may emit
// descriptive aliases such as `command`, `cwd`, `working_directory`, `timeout`,
// or `timeout_ms`. Normalize only this known tool shape; leave all other custom
// tools untouched.
function normalizeExecCommandInput(name, raw) {
  if (name !== "exec_command" || typeof raw !== "string") return raw;
  let value;
  try { value = JSON.parse(raw); } catch (_) { return raw; }
  if (!value || typeof value !== "object" || Array.isArray(value)) return raw;
  let changed = false;
  if (value.cmd == null && typeof value.command === "string") {
    value.cmd = value.command;
    delete value.command;
    changed = true;
  }
  if (value.workdir == null) {
    const workdir = typeof value.cwd === "string"
      ? value.cwd
      : typeof value.working_directory === "string"
        ? value.working_directory
        : null;
    if (workdir != null) {
      value.workdir = workdir;
      delete value.cwd;
      delete value.working_directory;
      changed = true;
    }
  }
  if (value.yield_time_ms == null) {
    const yieldTime = value.timeout_ms != null
      ? value.timeout_ms
      : value.timeout != null
        ? value.timeout
        : null;
    if (yieldTime != null) {
      value.yield_time_ms = yieldTime;
      delete value.timeout_ms;
      delete value.timeout;
      changed = true;
    }
  }
  // Remove aliases when a model emits both forms; the host deserializer is
  // strict and should receive one unambiguous schema.
  if (value.cmd != null && value.command != null) {
    delete value.command;
    changed = true;
  }
  if (value.workdir != null) {
    if (value.cwd != null) {
      delete value.cwd;
      changed = true;
    }
    if (value.working_directory != null) {
      delete value.working_directory;
      changed = true;
    }
  }
  if (value.yield_time_ms != null) {
    if (value.timeout_ms != null) {
      delete value.timeout_ms;
      changed = true;
    }
    if (value.timeout != null) {
      delete value.timeout;
      changed = true;
    }
  }
  return changed ? JSON.stringify(value) : raw;
}

function parseToolArgs(rawArgs) {
  if (typeof rawArgs !== "string") return rawArgs == null ? {} : rawArgs;
  try {
    const parsed = JSON.parse(rawArgs);
    return parsed == null ? {} : parsed;
  } catch (_) {
    return rawArgs;
  }
}

// DeepSeek sometimes emits the host's underlying tool names directly even
// though Codex++ exposes them to the model through the single code-mode `exec`
// custom tool. Keep this compatibility mapping narrow: only the two observed
// aliases are translated, and all other custom tools retain their original
// type/name/input.
function codeModeAliasInput(name, args) {
  if (name === "exec_command") {
    const payload = parseToolArgs(args);
    const literal = JSON.stringify(payload == null ? {} : payload);
    return `const r = await tools.exec_command(${literal}); text(r && r.output !== undefined ? r.output : r);`;
  }
  if (name === "mcp__node_repl__js") {
    const payload = parseToolArgs(args);
    const code = payload && typeof payload === "object" && typeof payload.code === "string"
      ? payload.code
      : payload && typeof payload === "object" && typeof payload.arguments === "string"
        ? payload.arguments
        : typeof payload === "string" ? payload : "";
    // The node-repl bridge is not a separate Codex++ tool in this runtime. Its
    // write primitive is equivalent to code-mode `text`, so preserve the code
    // while supplying that one small compatibility binding.
    return `const nodeRepl = { write: (...xs) => text(xs.join("")) };\n${code}`;
  }
  return args;
}

function toolCallItem(state, tc) {
  const aliasToExec = tc.name === "exec_command" || tc.name === "mcp__node_repl__js";
  const emittedName = aliasToExec ? "exec" : tc.name;
  const kind = state.toolTypes && state.toolTypes[emittedName] === "function" ? "function_call" : "custom_tool_call";
  const prefix = kind === "function_call" ? "fc_" : "ctc_";
  // chat/completions emits OpenAI-style tool ids (`call_xxx`); Responses needs a
  // single `fc_`/`ctc_` prefix. Strip any existing call_/fc_/ctc_ prefix first so
  // we never produce double-prefixed garbage like `fc_call_xxx`.
  const bareId = String(tc.id || "").replace(/^(call_|fc_|ctc_)/, "");
  const id = prefix + (bareId || crypto.randomBytes(12).toString("hex"));
  // Tool arguments arrive as `.arguments` on a non-streaming chat message, but as
  // `.args` when accumulated from streaming deltas in finishChatSse. Read both —
  // reading only `.arguments` silently emitted `"{}"` and dropped the real
  // command, so the exec ran empty and the turn collapsed after ~10-18s.
  const rawArgs = tc.arguments != null ? tc.arguments : tc.args;
  const args = normalizeExecCommandInput(
    tc.name,
    typeof rawArgs === "string" ? rawArgs : JSON.stringify(rawArgs == null ? {} : rawArgs)
  );
  // Responses uses `input` for custom_tool_call and `arguments` for
  // function_call.  Sending `arguments` on a custom_tool_call makes the
  // Codex++ ResponseItem deserializer reject the item, so the turn is closed
  // without dispatching the tool.
  if (kind === "custom_tool_call") {
    // Convert the two observed host aliases into the code-mode `exec` input;
    // this is the shape the local router actually executes.
    let finalInput = aliasToExec ? codeModeAliasInput(tc.name, args) : args;
    // Chat function arguments wrap a free-form custom input. Decode that
    // transport envelope for every declared custom tool, preserving its bytes.
    if (!aliasToExec) {
      const envelope = parseToolArgs(args);
      if (envelope && typeof envelope === "object" && typeof envelope.input === "string") finalInput = envelope.input;
    }
    // Special handling for exec tool: unwrap JSON envelopes to bare JS code.
    if (emittedName === "exec" && !aliasToExec && typeof args === "string" && args.trim().startsWith("{")) {
      const envelope = extractExecScriptEnvelope(args);
      if (envelope && envelope.key && typeof envelope.script === "string") {
        finalInput = envelope.script;
        try {
          const debugLog = { ts: new Date().toISOString(), fn: "toolCallItem", action: "UNWRAPPED_" + envelope.key.toUpperCase(), name: tc.name, code: envelope.script.slice(0, 100) };
          fs.appendFileSync(path.join(LOG_DIR, "debug-exec.log"), JSON.stringify(debugLog) + "\n");
        } catch (_) {}
      }
    }
    if (emittedName === "exec" && (typeof finalInput !== "string" || !finalInput.trim() || /^\{\s*\}$/.test(finalInput.trim()))) {
      const error = new Error("The provider returned an empty exec input. The tool needs a non-empty input string; no command was executed.");
      error.code = "invalid_custom_tool_input";
      throw error;
    }
    finalInput = withExecResultMetadataScript(finalInput);
    return {
      type: kind,
      id,
      call_id: id,
      name: emittedName,
      input: finalInput,
      status: "completed"
    };
  }
  return {
    type: kind,
    id,
    call_id: id,
    name: emittedName,
    arguments: args,
    status: "completed"
  };
}

function mapUsage(u) {
  if (!u || typeof u !== "object") return undefined;
  return {
    input_tokens: u.prompt_tokens || 0,
    output_tokens: u.completion_tokens || 0,
    total_tokens: u.total_tokens || 0,
    input_tokens_details: u.prompt_tokens_details,
    output_tokens_details: u.completion_tokens_details
  };
}

/** chat/completions (non-stream) response -> Responses response object. */
function chatToResponses(chat, state) {
  const output = [];
  if (state.compactionMode) {
    const item = compactionItemFromSummary(compactionSummaryFromChat(chat));
    log("adapted chat summary -> compaction item", {
      model: state.model,
      summaryLength: decodeAdapterCompactionSummary(item.encrypted_content)?.length || 0
    });
    return {
      id: rid("resp_"),
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      model: state.model,
      status: "completed",
      output: [item],
      usage: mapUsage(chat && chat.usage)
    };
  }
  const msg = chat && chat.choices && chat.choices[0] && chat.choices[0].message;
  const finishReason = chat && chat.choices && chat.choices[0] && chat.choices[0].finish_reason;
  const incompleteReason = finishReason === "length" || finishReason === "max_tokens" || finishReason === "max_output_tokens"
    ? "max_output_tokens"
    : (finishReason === "content_filter" ? "content_filter" : null);
  // DeepSeek/Kimi put reasoning in `message.reasoning_content`. Emit it as a
  // `reasoning` output item BEFORE the message item, matching the streaming
  // path and qwen passthrough structure Codex++ expects.
  if (msg && typeof msg.reasoning_content === "string" && msg.reasoning_content) {
    output.push({
      id: rid("rs_"),
      summary: [{ text: msg.reasoning_content, type: "summary_text" }],
      type: "reasoning",
      content: null,
      encrypted_content: null,
      status: "completed"
    });
  }
  if (msg && Array.isArray(msg.tool_calls)) {
    for (const tc of msg.tool_calls) output.push(toolCallItem(state, { id: tc.id, name: tc.function && tc.function.name, arguments: tc.function && tc.function.arguments }));
  }
  if (msg && msg.content) {
    output.push({
      type: "message",
      id: rid("msg_"),
      role: "assistant",
      content: [{ type: "output_text", text: String(msg.content), annotations: [], logprobs: null }],
      status: "completed"
    });
  }
  return {
    id: rid("resp_"),
    object: "response",
    created_at: Math.floor(Date.now() / 1000),
    model: state.model,
    status: incompleteReason ? "incomplete" : "completed",
    output,
    usage: mapUsage(chat && chat.usage),
    ...(incompleteReason ? { incomplete_details: { reason: incompleteReason } } : {})
  };
}

// --- streaming adaptation state machine ---------------------------------
function newChatSseState(state) {
  // Codex++ 26.901 consumes the Responses reasoning-summary event family.
  // The older reasoning_text.done event is logged as "unhandled" and leaves
  // the following tool call unparsed.  Use the native `rs_` item id and the
  // reasoning_summary_* events below.
  const reasoningId = rid("rs_");
  return {
    model: state.model,
    compactionMode: state.compactionMode === true,
    compactionText: "",
    compactionReasoningText: "",
    compactionItemId: rid("cmp_"),
    toolTypes: state.toolTypes || {},
    respId: rid("resp_"),
    msgId: rid("msg_"),
    reasoningId,                              // used for BOTH item.id and item_id
    started: false,
    reasoningOpened: false,
    reasoningDone: false,
    reasoningText: "",
    textOpened: false,
    text: "",
    // message item's output_index: 0 if no reasoning item, 1 if reasoning came first.
    // Set when the message item is opened (in convertChatSseLine) or when reasoning
    // is flushed at finish (so the message close in finishChatSse stays aligned).
    msgIndex: 0,
    tools: [],           // accumulated {id,name,args}
    usage: null,
    // Preserve the provider's terminal reason. Older versions always emitted
    // response.completed, hiding Kimi length/content-filter truncation.
    finishReason: null,
    incompleteDetails: null,
    // Chat Completions providers may send an error as the terminal SSE event
    // while keeping the HTTP stream at 200. Preserve that failure so the
    // Responses facade cannot turn it into an empty successful completion.
    error: null,
    done: false,
    // Codex++ requires a monotonically increasing `sequence_number` on every
    // Responses SSE event. Without it the client logs "failed to parse
    // ResponseItem from output_item.added/done" and drops the whole item.
    seq: 0
  };
}

// Wrap an event payload with the state's next sequence_number. Callers that
// have a `st` must pass it so the counter advances per-event; the bare
// sseEvent(type, payload) form (no st) is kept for non-streaming / one-shot
// events where sequence ordering is not enforced.
function sseEvent(type, payload, st) {
  const base = { type };
  if (st) base.sequence_number = st.seq++;
  return "data: " + JSON.stringify(Object.assign(base, payload)) + "\n\n";
}

function baseResponse(st, status, output) {
  const response = {
    id: st.respId,
    object: "response",
    created_at: Math.floor(Date.now() / 1000),
    model: st.model,
    status,
    output: output || [],
    usage: st.usage ? mapUsage(st.usage) : undefined
  };
  if (status === "incomplete" && st.incompleteDetails) {
    response.incomplete_details = st.incompleteDetails;
  }
  if (st.error) response.error = st.error;
  return response;
}

/** Convert one chat SSE line into zero or more Responses SSE events. */
function convertChatSseLine(line, st) {
  if (!line.startsWith("data: ")) return "";
  const raw = line.slice(6).trim();
  if (!raw || raw === "[DONE]") return "";
  let chunk;
  try { chunk = JSON.parse(raw); } catch (_) { return ""; }

  let out = "";
  if (!st.started) {
    st.started = true;
    out += sseEvent("response.created", { response: baseResponse(st, "in_progress", []) }, st);
    out += sseEvent("response.in_progress", { response: baseResponse(st, "in_progress", []) }, st);
  }
  if (chunk.usage) st.usage = chunk.usage;

  // Chat Completions puts the terminal reason on the choice carrying the
  // final delta. Keep it before translating the stream; otherwise a Kimi
  // `length` or content-filter stop is falsely reported as completed.
  const choice = chunk.choices && chunk.choices[0];
  if (choice && choice.finish_reason != null) st.finishReason = String(choice.finish_reason);
  if (chunk.stop_reason != null && !st.finishReason) st.finishReason = String(chunk.stop_reason);

  // CodexManager can return an upstream failure as `data: {"error": ...}`
  // on an otherwise successful SSE connection. Do not drop it: if it is
  // ignored, finishChatSse() emits response.completed with output=[], which
  // makes Codex++ silently stop the turn and prevents retry/error handling.
  if (chunk.error && !st.error) {
    st.error = typeof chunk.error === "object"
      ? chunk.error
      : { message: String(chunk.error) };
    log("upstream SSE error preserved", {
      model: st.model,
      error: st.error
    });
  }

  const ch = choice;
  if (ch && ch.delta) {
    if (st.compactionMode) {
      if (typeof ch.delta.content === "string") st.compactionText += ch.delta.content;
      if (typeof ch.delta.reasoning_content === "string") st.compactionReasoningText += ch.delta.reasoning_content;
      return out;
    }
    // DeepSeek/Kimi emit reasoning as a separate `reasoning_content` field on
    // each chat delta, alongside (empty) `content`. Codex++ expects a distinct
    // `reasoning` output item BEFORE the message item, with its own
    // output_item.added / reasoning_summary_text.delta /
    // reasoning_summary_text.done / reasoning_summary_part.done /
    // output_item.done sequence. If we skip reasoning deltas (because content
    // is "" and falsy), Codex++ sees a message item with no preceding
    // reasoning item and fails to parse output_item.added — the turn
    // completes server-side but the user sees no reply. Mirror the structure
    // qwen passthrough produces.
    if (typeof ch.delta.reasoning_content === "string" && ch.delta.reasoning_content) {
      if (!st.reasoningOpened) {
        st.reasoningOpened = true;
        out += sseEvent("response.output_item.added", {
          output_index: 0,
          item: { id: st.reasoningId, summary: [], type: "reasoning", content: null, encrypted_content: null, status: "in_progress" }
        }, st);
        out += sseEvent("response.reasoning_summary_part.added", {
          item_id: st.reasoningId, output_index: 0, summary_index: 0,
          part: { type: "summary_text", text: "" }
        }, st);
      }
      st.reasoningText += ch.delta.reasoning_content;
      out += sseEvent("response.reasoning_summary_text.delta", {
        output_index: 0, item_id: st.reasoningId, summary_index: 0, delta: ch.delta.reasoning_content
      }, st);
    }
    if (typeof ch.delta.content === "string" && ch.delta.content) {
      // First text content closes the reasoning item (if any) and bumps output_index.
      const msgIndex = st.reasoningOpened ? 1 : 0;
      st.msgIndex = msgIndex;
      if (st.reasoningOpened && !st.reasoningDone) {
        st.reasoningDone = true;
        out += sseEvent("response.reasoning_summary_text.done", {
          output_index: 0, item_id: st.reasoningId, summary_index: 0, text: st.reasoningText
        }, st);
        out += sseEvent("response.reasoning_summary_part.done", {
          item_id: st.reasoningId, output_index: 0, summary_index: 0,
          part: { type: "summary_text", text: st.reasoningText }
        }, st);
        out += sseEvent("response.output_item.done", {
          output_index: 0,
          item: { id: st.reasoningId, summary: [{ text: st.reasoningText, type: "summary_text" }], type: "reasoning", content: null, encrypted_content: null, status: "completed" }
        }, st);
      }
      if (!st.textOpened) {
        st.textOpened = true;
        out += sseEvent("response.output_item.added", {
          output_index: msgIndex,
          item: { type: "message", id: st.msgId, role: "assistant", content: [], status: "in_progress" }
        }, st);
        out += sseEvent("response.content_part.added", {
          output_index: msgIndex, content_index: 0, item_id: st.msgId,
          part: { type: "output_text", text: "", annotations: [], logprobs: null }
        }, st);
      }
      st.text += ch.delta.content;
      out += sseEvent("response.output_text.delta", {
        output_index: msgIndex, content_index: 0, item_id: st.msgId, delta: ch.delta.content
      }, st);
    }
    if (Array.isArray(ch.delta.tool_calls)) {
      for (const tc of ch.delta.tool_calls) {
        const idx = tc.index == null ? st.tools.length : tc.index;
        if (!st.tools[idx]) {
          st.tools[idx] = { id: tc.id || rid("ctc_"), name: (tc.function && tc.function.name) || "", args: "" };
        }
        if (tc.function && tc.function.name) st.tools[idx].name = tc.function.name;
        if (tc.function && tc.function.arguments) st.tools[idx].args += tc.function.arguments;
      }
    }
  }
  return out;
}

/** Flush remaining events when the chat stream ends. */
function finishChatSse(st) {
  let out = "";

  if (st.error) {
    st.done = true;
    out += sseEvent("response.failed", {
      response: baseResponse(st, "failed", [])
    }, st);
    out += "data: [DONE]\n\n";
    return out;
  }

  if (st.compactionMode) {
    const summary = st.compactionText.trim() || st.compactionReasoningText.trim();
    const item = compactionItemFromSummary(summary, st.compactionItemId);
    const output = [item];
    log("adapted chat stream -> compaction item", {
      model: st.model,
      summaryLength: summary.length,
      summarySource: st.compactionText.trim() ? "content" : (st.compactionReasoningText.trim() ? "reasoning" : "fallback")
    });
    out += sseEvent("response.output_item.added", { output_index: 0, item }, st);
    out += sseEvent("response.output_item.done", { output_index: 0, item }, st);
    out += sseEvent("response.completed", {
      response: baseResponse(st, "completed", output)
    }, st);
    out += "data: [DONE]\n\n";
    return out;
  }

  let toolItems;
  try {
    toolItems = st.tools.filter(Boolean).map(tc => toolCallItem({toolTypes:st.toolTypes},tc));
  } catch (error) {
    st.error = { type: "invalid_response_error", code: error.code || "invalid_tool_input", message: error.message };
    return finishChatSse(st);
  }

  const output = [];
  // Close reasoning item first if it was opened and not already closed by the
  // first content delta. DeepSeek sometimes emits reasoning with no follow-up
  // content (e.g. tool-only turns) — flush it here so Codex++ sees a done item.
  if (st.reasoningOpened && !st.reasoningDone) {
    st.reasoningDone = true;
    out += sseEvent("response.reasoning_summary_text.done", {
      output_index: 0, item_id: st.reasoningId, summary_index: 0, text: st.reasoningText
    }, st);
    out += sseEvent("response.reasoning_summary_part.done", {
      item_id: st.reasoningId, output_index: 0, summary_index: 0,
      part: { type: "summary_text", text: st.reasoningText }
    }, st);
    const reasoningItem = {
      id: st.reasoningId,
      summary: [{ text: st.reasoningText, type: "summary_text" }],
      type: "reasoning", content: null, encrypted_content: null, status: "completed"
    };
    output.push(reasoningItem);
    out += sseEvent("response.output_item.done", { output_index: 0, item: reasoningItem }, st);
    st.msgIndex = 1;
  }
  let idx = st.msgIndex;
  if (st.textOpened) {
    out += sseEvent("response.output_text.done", { output_index: idx, content_index: 0, item_id: st.msgId, logprobs: null, text: st.text }, st);
    out += sseEvent("response.content_part.done", {
      output_index: idx, content_index: 0, item_id: st.msgId,
      part: { type: "output_text", text: st.text, annotations: [], logprobs: null }
    }, st);
    output.push({
      type: "message", id: st.msgId, role: "assistant",
      content: [{ type: "output_text", text: st.text, annotations: [], logprobs: null }],
      status: "completed"
    });
    out += sseEvent("response.output_item.done", { output_index: idx, item: output[output.length - 1] }, st);
    idx++;
  }
  for (const item of toolItems) {
    // A streamed custom tool call is opened first, then its input is delivered
    // through the Responses custom_tool_call_input events.  The prior adapter
    // emitted only output_item.added/done with an `arguments` field, which is
    // not a valid custom_tool_call item for Codex++ and prevented execution.
    if (item.type === "custom_tool_call") {
      const openItem = { ...item, input: "", status: "in_progress" };
      out += sseEvent("response.output_item.added", { output_index: idx, item: openItem }, st);
      out += sseEvent("response.custom_tool_call_input.delta", {
        output_index: idx, item_id: item.id, delta: item.input
      }, st);
      out += sseEvent("response.custom_tool_call_input.done", {
        output_index: idx, item_id: item.id, input: item.input
      }, st);
      output.push(item);
      out += sseEvent("response.output_item.done", { output_index: idx, item }, st);
    } else {
      out += sseEvent("response.output_item.added", { output_index: idx, item: { ...item, status: "in_progress" } }, st);
      out += sseEvent("response.function_call_arguments.delta", {
        output_index: idx, item_id: item.id, delta: item.arguments
      }, st);
      out += sseEvent("response.function_call_arguments.done", {
        output_index: idx, item_id: item.id, arguments: item.arguments
      }, st);
      output.push(item);
      out += sseEvent("response.output_item.done", { output_index: idx, item }, st);
    }
    idx++;
  }
  const reason = st.finishReason;
  let terminalStatus = "completed";
  if (reason === "length" || reason === "max_tokens" || reason === "max_output_tokens") {
    terminalStatus = "incomplete";
    st.incompleteDetails = { reason: "max_output_tokens" };
  } else if (reason === "content_filter") {
    terminalStatus = "incomplete";
    st.incompleteDetails = { reason: "content_filter" };
  }
  log("chat stream finished", {
    model: st.model,
    finishReason: reason,
    status: terminalStatus,
    toolCount: toolItems.length,
    textLength: st.text.length
  });
  // v30: record whether this turn was tool-only (tool_calls, no text). If so,
  // the next kimi-k3 turn will NOT force tool_choice=required, giving Kimi an
  // exit channel to stop after task completion instead of looping endlessly.
  if (st.model && reason === "tool_calls" && st.text.length === 0) {
    prevTurnWasToolOnly.set(st.model, true);
  } else {
    prevTurnWasToolOnly.delete(st.model);
  }
  out += sseEvent(terminalStatus === "completed" ? "response.completed" : "response.incomplete", {
    response: baseResponse(st, terminalStatus, output)
  }, st);
  out += "data: [DONE]\n\n";
  return out;
}

const server = http.createServer((clientReq, clientRes) => {
  const reqUrl = new URL(clientReq.url, `http://${clientReq.headers.host || LISTEN_HOST}`);
  const targetPath = reqUrl.pathname;

  if (targetPath === "/health" || targetPath === "/__health") {
    clientRes.writeHead(200, { "content-type": "application/json" });
    return clientRes.end(JSON.stringify({ status: "ok", proxy: "codex-id-sanitizer", port: LISTEN_PORT, adapter: ADAPTER_VERSION }));
  }

  // Compact (context compression) was previously intercepted here and returned
  // a synthesized no-op compaction. That hid "compact_not_supported" errors
  // from the qwen account pool, but the no-op left the context uncompressed —
  // Codex++ believed compact succeeded and never retried, so the session grew
  // linearly until it hit the upstream 1 MB character limit ("Input exceeds
  // the maximum length of 1048576 characters"). Transparent passthrough is
  // safer: a visible error is better than silent context inflation. If the
  // gateway returns compact_not_supported, Codex++ will surface the error and
  // the user can start a new session; the session will not silently bloat.

  const adaptState = { active: false, model: null, toolTypes: {}, stream: false, compactionMode: false };
  // Keep the provider request tied to the Codex++ response lifecycle. If the
  // client drops a malformed/failed turn, leaving the upstream stream alive
  // consumes the provider concurrency slot and makes a later (often fifth)
  // model request fail with a misleading concurrency error.
  const lifecycle = { cancelled: false };
  let adaptedJob = null;

  const makeUpstreamReq = (pathOverride, requestBody = null, attempt = 0) => {
    const upstreamOptions = {
      protocol: UPSTREAM_URL.protocol,
      hostname: UPSTREAM_URL.hostname,
      port: UPSTREAM_URL.port || (UPSTREAM_URL.protocol === "https:" ? 443 : 80),
      path: pathOverride || (reqUrl.pathname + reqUrl.search),
      method: clientReq.method,
      headers: {
        ...clientReq.headers,
        host: UPSTREAM_URL.host
      }
    };
    const transport = UPSTREAM_URL.protocol === "https:" ? https : http;
    const watchdog = { firstByte: false, firstByteTimer: null, idleTimer: null, fired: false };
    let terminalState = null;
    let terminalSent = false;
    const clearWatchdog = () => {
      if (watchdog.firstByteTimer) { clearTimeout(watchdog.firstByteTimer); watchdog.firstByteTimer = null; }
      if (watchdog.idleTimer) { clearTimeout(watchdog.idleTimer); watchdog.idleTimer = null; }
    };
    const sendTerminalFailure = (failure, statusCode = 502) => {
      if (terminalSent || lifecycle.cancelled || clientRes.writableEnded) return false;
      terminalSent = true;
      clearWatchdog();

      const error = {
        type: failure && failure.type ? failure.type : "server_error",
        code: failure && failure.code ? failure.code : "upstream_error",
        message: failure && failure.message ? failure.message : "Upstream request failed"
      };
      log("upstream terminal failure", { error, path: targetPath, model: adaptState.model || null, attempt });

      if (!clientRes.headersSent) {
        clientRes.writeHead(statusCode, { "content-type": "application/json" });
        clientRes.end(JSON.stringify({ error }));
      } else if (terminalState) {
        terminalState.error = error;
        const term = sseEvent("response.failed", {
          response: terminalState.respId
            ? baseResponse(terminalState, "failed", [])
            : {
                id: rid("resp_"), object: "response", status: "failed", output: [], error
              }
        }, terminalState);
        try { clientRes.write(term + "data: [DONE]\n\n"); } catch (_) {}
        try { clientRes.end(); } catch (_) {}
      } else {
        // A non-SSE response has already committed its headers. It cannot be
        // converted into an SSE failure without corrupting its media type;
        // close the truncated response and let the HTTP client classify it.
        try { clientRes.end(); } catch (_) {}
      }

      if (upstreamReq && !upstreamReq.destroyed) upstreamReq.destroy();
      return true;
    };
    const failClientUpstreamTimeout = (stage) => {
      if (watchdog.fired || terminalSent) return;
      watchdog.fired = true;
      log("upstream watchdog fired", { stage, path: targetPath, model: adaptState.model || null, attempt });
      sendTerminalFailure({
        type: "server_error",
        code: "upstream_timeout",
        message: `Upstream ${stage} timeout`
      }, 504);
    };
    const pokeIdle = () => {
      if (watchdog.fired) return;
      if (watchdog.idleTimer) clearTimeout(watchdog.idleTimer);
      watchdog.idleTimer = setTimeout(() => failClientUpstreamTimeout("idle"), UPSTREAM_IDLE_TIMEOUT_MS);
    };
    const watchdogFirstByte = () => {
      if (watchdog.firstByte) return;
      watchdog.firstByte = true;
      if (watchdog.firstByteTimer) { clearTimeout(watchdog.firstByteTimer); watchdog.firstByteTimer = null; }
      pokeIdle();
    };
    watchdog.firstByteTimer = setTimeout(() => failClientUpstreamTimeout("first_byte"), UPSTREAM_FIRST_BYTE_TIMEOUT_MS);
    const upstreamReq = transport.request(upstreamOptions, (upstreamRes) => {
      watchdogFirstByte();
      upstreamRes.on("data", () => pokeIdle());
      const contentType = (upstreamRes.headers["content-type"] || "").toLowerCase();
      const isEventStream = contentType.includes("text/event-stream");

      // --- Protocol adaptation on the way back -------------------------
      if (adaptState.active && upstreamRes.statusCode < 400) {
        if (isEventStream || adaptState.stream) {
          const st = newChatSseState(adaptState);
          terminalState = st;
          // DIAG 20260909-b: capture synthesized Responses events Codex++ actually
          // receives, to find the field mismatch in output_item.added/done that
          // survives the item_id fix. Remove after root cause confirmed.
          const diagDir = "@@SANITIZER_ROOT:escaped@@\\diag-dump";
          try { require("fs").mkdirSync(diagDir, { recursive: true }); } catch (_) {}
          const diagStamp = Date.now();
          const outPath = diagDir + "\\out-" + (adaptState.model || "unk").replace(/[^a-z0-9]/gi,"_") + "-" + diagStamp + ".sse";
          let outFh = null;
          try { outFh = require("fs").createWriteStream(outPath, { flags: "a" }); } catch (_) {}
          let committed = false;
          let retryScheduled = false;
          const pending = [];
          const commit = () => {
            if (committed) return;
            committed = true;
            clientRes.writeHead(upstreamRes.statusCode, {
              "content-type": "text/event-stream",
              "cache-control": upstreamRes.headers["cache-control"] || "no-cache",
              "connection": "keep-alive"
            });
            for (const buffered of pending.splice(0)) clientRes.write(buffered);
          };
          const retryEmptyStream = () => {
            clearWatchdog();
             if (retryScheduled || committed || !st.error || st.reasoningOpened || st.textOpened || st.tools.some(Boolean)) return false;
            if (attempt >= MAX_EMPTY_STREAM_RETRIES || !requestBody) return false;
             retryScheduled = true;
            const delay = EMPTY_STREAM_RETRY_DELAYS_MS[attempt] || EMPTY_STREAM_RETRY_DELAYS_MS.at(-1);
            log("retrying empty adapted stream after upstream error", {
              model: adaptState.model,
              attempt: attempt + 1,
              maxAttempts: MAX_EMPTY_STREAM_RETRIES + 1,
              delayMs: delay,
              error: st.error
            });
            if (outFh) { try { outFh.end(); } catch (_) {} }
            setTimeout(() => {
              if (lifecycle.cancelled) return;
              const retryReq = makeUpstreamReq(pathOverride, requestBody, attempt + 1);
              retryReq.removeHeader("transfer-encoding");
              retryReq.setHeader("content-length", String(requestBody.length));
              retryReq.write(requestBody);
              retryReq.end();
            }, delay);
            return true;
          };
          let sseBuf = "";
          const sseDecoder = new StringDecoder("utf8");
          upstreamRes.on("data", (chunk) => {
            sseBuf += sseDecoder.write(chunk);
            const lines = sseBuf.split("\n");
            sseBuf = lines.pop();
            for (const line of lines) {
              const ev = convertChatSseLine(line, st);
              if (ev) {
                if (outFh) { try { outFh.write(ev); } catch (_) {} }
                if (!committed) pending.push(ev);
                else clientRes.write(ev);
                // Do not hold a normal response back once model output starts.
                if (!committed && (st.reasoningOpened || st.textOpened || st.tools.some(Boolean))) commit();
              }
            }
          });
          upstreamRes.on("end", () => {
            clearWatchdog();
            sseBuf += sseDecoder.end();
            if (sseBuf) {
              const ev = convertChatSseLine(sseBuf, st);
              if (ev) {
                if (outFh) { try { outFh.write(ev); } catch (_) {} }
                if (!committed) pending.push(ev);
                else clientRes.write(ev);
                if (!committed && (st.reasoningOpened || st.textOpened || st.tools.some(Boolean))) commit();
              }
            }
            if (retryEmptyStream()) return;
            const fin = finishChatSse(st);
            if (outFh) { try { outFh.write(fin); } catch (_) {} }
            if (!committed) commit();
            clientRes.write(fin);
            clientRes.end();
            if (outFh) { try { outFh.end(); } catch (_) {} }
          });
          upstreamRes.on("error", (err) => {
            log("adapted SSE stream error", { error: err.message, path: targetPath });
            if (retryEmptyStream()) return;
            sendTerminalFailure({ type: "server_error", code: "upstream_stream_error", message: "Upstream stream failed" });
          });
          upstreamRes.on("aborted", () => {
            log("adapted SSE stream aborted", { path: targetPath });
            if (retryEmptyStream()) return;
            sendTerminalFailure({ type: "server_error", code: "upstream_stream_aborted", message: "Upstream stream aborted" });
          });
        } else {
          const bodyChunks = [];
          upstreamRes.on("data", (c) => bodyChunks.push(c));
          upstreamRes.on("end", () => {
            clearWatchdog();
            const rawBody = Buffer.concat(bodyChunks);
            let chatResp;
            try {
              chatResp = JSON.parse(rawBody.toString("utf8"));
            } catch (e) {
              clientRes.writeHead(upstreamRes.statusCode, upstreamRes.headers);
              clientRes.end(rawBody);
              return;
            }
            let resp;
            try { resp = chatToResponses(chatResp, adaptState); }
            catch (error) {
              resp = {id:rid("resp_"),object:"response",model:adaptState.model,status:"failed",output:[],error:{type:"invalid_response_error",code:error.code || "invalid_tool_input",message:error.message}};
            }
            const out = Buffer.from(JSON.stringify(resp), "utf8");
            // Node rejects a response that carries both Content-Length and
            // Transfer-Encoding.  CodexManager commonly sends chunked
            // chat/completions responses, while this branch materializes a
            // new JSON Responses body and therefore needs an exact length.
            // Strip hop-by-hop framing headers before forwarding the adapted
            // non-stream response.
            const { "transfer-encoding": _transferEncoding, connection: _connection, ...responseHeaders } = upstreamRes.headers;
            const headers = {
              ...responseHeaders,
              "content-type": "application/json",
              "content-length": String(out.length)
            };
            clientRes.writeHead(upstreamRes.statusCode, headers);
            clientRes.end(out);
          });
          upstreamRes.on("error", (err) => {
            log("adapted response error", { error: err.message, path: targetPath });
            sendTerminalFailure({ type: "server_error", code: "upstream_response_error", message: "Upstream response failed" });
          });
          upstreamRes.on("aborted", () => {
            log("adapted response aborted", { path: targetPath });
            sendTerminalFailure({ type: "server_error", code: "upstream_response_aborted", message: "Upstream response aborted" });
          });
        }
        return;
      }

      // --- Original passthrough behavior --------------------------------
      if (isEventStream) {
        terminalState = {
          seq: 0,
          respId: rid("resp_"),
          model: adaptState.model || null,
          usage: null,
          error: null
        };
        clientRes.writeHead(upstreamRes.statusCode, upstreamRes.headers);
        let buffer = "";
        const decoder = new StringDecoder("utf8");
        const sseState = { pending: null };

        upstreamRes.on("data", (chunk) => {
          buffer += decoder.write(chunk);
          const lines = buffer.split("\n");
          buffer = lines.pop();

          for (const line of lines) {
            const transformed = transformSseLine(line, sseState);
            if (transformed !== null) {
              try {
                const parsed = JSON.parse(transformed.slice(6).trim());
                if (Number.isInteger(parsed.sequence_number)) {
                  terminalState.seq = Math.max(terminalState.seq, parsed.sequence_number + 1);
                }
              } catch (_) {}
              clientRes.write(transformed + "\n");
            }
          }
        });

        upstreamRes.on("end", () => {
          clearWatchdog();
          buffer += decoder.end();
          if (buffer) {
            const transformed = transformSseLine(buffer, sseState);
            if (transformed !== null) clientRes.write(transformed);
          }
          clientRes.end();
        });

        upstreamRes.on("error", (err) => {
          log("upstream SSE stream error", { error: err.message });
          sendTerminalFailure({ type: "server_error", code: "upstream_stream_error", message: "Upstream stream failed" });
        });
        upstreamRes.on("aborted", () => {
          log("upstream SSE stream aborted", { path: targetPath });
          sendTerminalFailure({ type: "server_error", code: "upstream_stream_aborted", message: "Upstream stream aborted" });
        });
      } else if (isResponsesWriteRequest(clientReq.method, targetPath)) {
        // Non-streaming Responses response: unwrap any JSON-enveloped exec
        // input in the returned output items before handing it to the client.
        const bodyChunks = [];
        upstreamRes.on("data", (c) => bodyChunks.push(c));
        upstreamRes.on("end", () => {
          clearWatchdog();
          const rawBody = Buffer.concat(bodyChunks);
          let outBuf = rawBody;
          try {
            const parsed = JSON.parse(rawBody.toString("utf8"));
            let fixed = 0;
            const visit = (it) => {
              if (unwrapExecInput(it)) fixed++;
            };
            if (parsed && Array.isArray(parsed.output)) parsed.output.forEach(visit);
            if (parsed && parsed.output_item) visit(parsed.output_item);
            if (fixed > 0) {
              outBuf = Buffer.from(JSON.stringify(parsed), "utf8");
              log("unwrapped exec input envelope in non-stream response", { fixed, path: targetPath });
            }
          } catch (_) {}
          const { "transfer-encoding": _transferEncoding, connection: _connection, ...responseHeaders } = upstreamRes.headers;
          const headers = { ...responseHeaders, "content-length": String(outBuf.length) };
          clientRes.writeHead(upstreamRes.statusCode, headers);
          clientRes.end(outBuf);
        });
        upstreamRes.on("error", (err) => {
          log("upstream response error", { error: err.message });
          sendTerminalFailure({ type: "server_error", code: "upstream_response_error", message: "Upstream response failed" });
        });
        upstreamRes.on("aborted", () => {
          log("upstream response aborted", { path: targetPath });
          sendTerminalFailure({ type: "server_error", code: "upstream_response_aborted", message: "Upstream response aborted" });
        });
      } else {
        clientRes.writeHead(upstreamRes.statusCode, upstreamRes.headers);
        upstreamRes.pipe(clientRes);
        upstreamRes.on("error", (err) => {
          log("upstream passthrough error", { error: err.message, path: targetPath });
          sendTerminalFailure({ type: "server_error", code: "upstream_passthrough_error", message: "Upstream response failed" });
        });
        upstreamRes.on("aborted", () => {
          log("upstream passthrough aborted", { path: targetPath });
          sendTerminalFailure({ type: "server_error", code: "upstream_passthrough_aborted", message: "Upstream response aborted" });
        });
      }
    });

    upstreamReq.on("error", (err) => {
      log("upstream request error", { error: err.message, path: targetPath });
      sendTerminalFailure({ type: "server_error", code: "upstream_request_error", message: "Upstream request failed" });
    });
    const cancelUpstream = () => {
      if (clientRes.writableEnded || lifecycle.cancelled) return;
      lifecycle.cancelled = true;
      clearWatchdog();
      log("client disconnected, cancelling upstream request", { path: targetPath, attempt });
      if (!upstreamReq.destroyed) upstreamReq.destroy();
      releaseAdaptedRequest(adaptedJob, "client_cancelled");
    };
    clientReq.once("aborted", cancelUpstream);
    clientRes.once("close", cancelUpstream);
    clientRes.once("finish", () => { clearWatchdog(); releaseAdaptedRequest(adaptedJob, "response_finished"); });
    return upstreamReq;
  };

  // --- Request body sanitization + protocol adaptation ------------------
  // For POST /responses* we buffer the body, rewrite any msg_-prefixed
  // custom_tool_call / function_call ids (and their matching tool_call_id
  // references) to the required ctc_ / fc_ prefixes, and for chat-only
  // models translate the whole request to /v1/chat/completions.
  // Compact (context compression) must bypass ALL body interception —
  // sanitizeResponsesBody strips reasoning and CHAT_ONLY_MODELS would
  // convert it to chat/completions. The gateway needs the raw Responses
  // compact payload; Codex++ expects the gateway's native compaction
  // response shape, not an adapted one. v29 removed the fake no-op
  // compaction; v31 ensures compact is a pure pipe.
  //
  // v33: compact must go through body interception for id normalization
  // (msg_ → ctc_/fc_) but skip stripNonPersistedReasoning. v31 pure pipe
  // skipped id normalization → after model switch (deepseek→gpt) history
  // carried msg_-prefixed ids that chatgpt.com rejected.
  const isCompactPassthrough = targetPath.endsWith("/responses/compact");
  const shouldInterceptBody = isResponsesWriteRequest(clientReq.method, targetPath) && !isCompactPassthrough;

  // Compact: go through body interception but with a lighter touch —
  // only id normalization + exec unwrap, skip stripNonPersistedReasoning.
  if (isCompactPassthrough) {
    log("compact request intercepted for id normalization", { path: targetPath });
    const reqChunks2 = [];
    clientReq.on("data", (chunk) => reqChunks2.push(chunk));
    clientReq.on("end", () => {
      let outBuf2 = Buffer.concat(reqChunks2);
      try {
        const bodyStr2 = outBuf2.toString("utf8");
        if (bodyStr2 && bodyStr2.trim().startsWith("{")) {
          const parsed2 = JSON.parse(bodyStr2);
          const fixed2 = sanitizeResponsesBody(parsed2, true); // skipReasoningStrip=true
          if (fixed2 > 0) {
            outBuf2 = Buffer.from(JSON.stringify(parsed2), "utf8");
            log("sanitized compact body", { fixed: fixed2, bytesBefore: bodyStr2.length, bytesAfter: outBuf2.length });
          }
        }
      } catch (e) {
        log("compact body sanitize skipped", { error: e.message });
      }
      const upstreamReq2 = makeUpstreamReq(null, outBuf2, 0);
      upstreamReq2.end();
    });
    return;
  }

  if (!shouldInterceptBody) {
    const upstreamReq = makeUpstreamReq(null);
    clientReq.pipe(upstreamReq);
    clientReq.on("error", (err) => {
      log("client request stream error", { error: err.message, path: targetPath });
      upstreamReq.destroy();
    });
    return;
  }

  const reqChunks = [];
  clientReq.on("data", (chunk) => reqChunks.push(chunk));

  clientReq.on("end", () => {
    const raw = Buffer.concat(reqChunks);
    if (raw.length > MAX_INTERCEPT_BODY) {
      log("request body exceeds MAX_INTERCEPT_BODY, passing through unsanitized", {
        bytes: raw.length, limit: MAX_INTERCEPT_BODY, path: targetPath
      });
      const upstreamReq = makeUpstreamReq(null);
      upstreamReq.write(raw);
      upstreamReq.end();
      return;
    }
    let outBuf = raw;
    let pathOverride = null;
    try {
      const bodyStr = raw.toString("utf8");
      if (bodyStr && bodyStr.trim().startsWith("{")) {
        const parsed = JSON.parse(bodyStr);
        const fixed = sanitizeResponsesBody(parsed);
        if (fixed > 0) {
          outBuf = Buffer.from(JSON.stringify(parsed), "utf8");
          log("sanitized request body", { fixed, path: targetPath, bytesBefore: raw.length, bytesAfter: outBuf.length });
        }
        let multimodal = bodyContainsImage(parsed);
        const latestUser = latestUserMessage(parsed);
        const latestUserHasImage = latestUser ? bodyContainsImage(latestUser) : false;
        const requestedModel = parsed.model;
        let rerouteDeepSeekVision = false;
        if (parsed.model === "deepseek-v4-pro" && multimodal) {
          if (latestUser && !latestUserHasImage) {
            const stripped = stripHistoricalImages(parsed, latestUser);
            if (stripped > 0) {
              outBuf = Buffer.from(JSON.stringify(parsed), "utf8");
              multimodal = bodyContainsImage(parsed);
              log("stripped historical images for text continuation", {
                requested_model: parsed.model,
                model: parsed.model,
                stripped,
                path: targetPath,
                bytes: outBuf.length
              });
            } else {
              // Keep the image in the request when there is no safe textual
              // replacement; the provider's current capability gate decides.
              rerouteDeepSeekVision = true;
            }
          } else {
            rerouteDeepSeekVision = true;
          }
        }
        if (rerouteDeepSeekVision) {
          parsed.model = DEEPSEEK_MULTIMODAL_MODEL;
          outBuf = Buffer.from(JSON.stringify(parsed), "utf8");
          log("rerouted multimodal model", {
            requested_model: requestedModel,
            model: parsed.model,
            path: targetPath,
            bytes: outBuf.length
          });
        }
        const remoteCompactionRequest = hasCompactionTrigger(parsed);
        if (!CHAT_ONLY_MODELS.has(parsed.model)) {
          const downgradedCompactions = downgradeAdapterCompactionMarkers(parsed);
          if (downgradedCompactions > 0) {
            outBuf = Buffer.from(JSON.stringify(parsed), "utf8");
            log("downgraded adapter compaction markers for Responses provider", {
              model: parsed.model,
              fixed: downgradedCompactions,
              path: targetPath,
              bytes: outBuf.length
            });
          }
        }
        const preserveResponsesForMultimodal = parsed.model === DEEPSEEK_MULTIMODAL_MODEL && multimodal;
        // Standalone /responses/compact remains a pure Responses passthrough.
        // Remote compaction v2 uses ordinary /responses with a
        // compaction_trigger and is adapted by the branch below for chat-only
        // models.
        const isCompactRequest = targetPath.endsWith("/responses/compact");
        if (CHAT_ONLY_MODELS.has(parsed.model) && !preserveResponsesForMultimodal && !isCompactRequest) {
          // Keep a compact, secret-free record of the tool contract the Codex
          // client sent. This is useful when a third-party model emits a
          // syntactically valid call that the local router rejects.
          const toolShape = Array.isArray(parsed.tools)
            ? parsed.tools.map((t) => ({
                type: t && t.type,
                name: t && t.name,
                hasParameters: !!(t && t.parameters),
                parameterKeys: t && t.parameters && t.parameters.properties
                  ? Object.keys(t.parameters.properties)
                  : []
              }))
            : [];
          log("captured Responses tool shape", { model: parsed.model, tools: toolShape });
          adaptState.compactionMode = remoteCompactionRequest;
          const chat = responsesToChat(parsed, adaptState);
          if (adaptState.kimiErrorToolContinuation) {
            log("forcing Kimi tool choice after tool batch", {
              model: parsed.model,
              toolChoice: chat.tool_choice
            });
          }
          adaptState.active = true;
          adaptState.model = parsed.model;
          adaptState.stream = !!parsed.stream;
          outBuf = Buffer.from(JSON.stringify(chat), "utf8");
          pathOverride = "/v1/chat/completions";
          log("adapting responses -> chat/completions", {
            model: parsed.model, stream: adaptState.stream,
            reasoning_effort: chat.reasoning_effort || null,
            messages: Array.isArray(chat.messages) ? chat.messages.length : null,
            compaction: remoteCompactionRequest,
            bytesBefore: raw.length, bytesAfter: outBuf.length, path: targetPath
          });
        } else if (preserveResponsesForMultimodal) {
          log("preserving Responses multimodal request", {
            model: parsed.model, path: targetPath, bytes: outBuf.length
          });
        }
      }
    } catch (e) {
      if (e.code === "unresolved_tool_result") {
        clientRes.writeHead(400, { "content-type": "application/json" });
        clientRes.end(JSON.stringify({error:{type:"invalid_request_error",code:e.code,message:e.message}}));
        return;
      }
      log("request body sanitize skipped (non-JSON or parse error)", { path: targetPath, error: e.message });
    }
    const upstreamPath = pathOverride ? pathOverride + reqUrl.search : null;
    const launch = () => {
      if (lifecycle.cancelled) return;
      const upstreamReq = makeUpstreamReq(upstreamPath, outBuf, 0);
      // Update Content-Length to match the (possibly rewritten) body.
      upstreamReq.removeHeader("transfer-encoding");
      upstreamReq.setHeader("content-length", String(outBuf.length));
      if (outBuf.length) upstreamReq.write(outBuf);
      upstreamReq.end();
    };
    if (adaptState.active) {
      adaptedJob = {
        lifecycle,
        model: adaptState.model,
        start: launch
      };
      clientReq.once("aborted", () => { lifecycle.cancelled = true; });
      enqueueAdaptedRequest(adaptedJob);
    } else {
      launch();
    }
  });

  clientReq.on("error", (err) => {
    log("client request stream error", { error: err.message, path: targetPath });
  });
});

server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  log("CodexIdSanitizer proxy started", { listen: `${LISTEN_HOST}:${LISTEN_PORT}`, upstream: UPSTREAM_URL.toString() });
  console.log(`CodexIdSanitizer proxy listening on http://${LISTEN_HOST}:${LISTEN_PORT} -> ${UPSTREAM_URL.toString()}`);
});
