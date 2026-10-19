const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { StringDecoder } = require("node:string_decoder");
const LISTEN_HOST = process.env.READ_SANITIZER_HOST || "127.0.0.1";
const LISTEN_PORT = Number(process.env.READ_SANITIZER_PORT || "15722");
const UPSTREAM = new URL(process.env.READ_SANITIZER_UPSTREAM || "http://127.0.0.1:48760");
const LOG_DIR = process.env.READ_SANITIZER_LOG_DIR || path.join(__dirname, "logs");
const LOG_FILE = path.join(LOG_DIR, "read-tool-sanitizer.jsonl");
const STRIP_EMPTY_THINKING = /^(1|true|yes|on)$/i.test(process.env.READ_SANITIZER_STRIP_EMPTY_THINKING || "");
const REPAIR_TOOL_JSON = /^(1|true|yes|on)$/i.test(process.env.READ_SANITIZER_REPAIR_TOOL_JSON || "");
const TEXT_ONLY_MESSAGE_CONTENT = /^(1|true|yes|on)$/i.test(process.env.READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT || "");
const PROMOTE_TOOL_TEXT = /^(1|true|yes|on)$/i.test(process.env.READ_SANITIZER_PROMOTE_TOOL_TEXT || "");
const ENFORCE_READ_FILE_PATH = /^(1|true|yes|on)$/i.test(process.env.READ_SANITIZER_ENFORCE_READ_FILE_PATH || "");
const STATIC_MODELS = String(process.env.READ_SANITIZER_MODELS_LIST || "")
  .split(",")
  .map((model) => model.trim())
  .filter(Boolean);
const MODELS_UPSTREAM = process.env.READ_SANITIZER_MODELS_UPSTREAM
  ? new URL(process.env.READ_SANITIZER_MODELS_UPSTREAM)
  : null;
const EMPTY_REASONING_FIELDS = [
  "reasoning_content",
  "reasoning",
  "reasoning_delta",
  "thinking",
  "thought",
];
const THOUGHT_FOR_PATTERN = /^\s*thought\s+for\s+\d+(\.\d+)?\s*s?\s*$/i;
const THOUGHT_FOR_PATTERN_MULTI = /thought\s+for\s+\d+(\.\d+)?\s*s?\s*/gi;
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);
function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function isBlankText(value) {
  return value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "");
}
function isPdfPath(filePath) {
  return typeof filePath === "string" && filePath.toLowerCase().endsWith(".pdf");
}
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function writeEvent(event) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  fs.appendFileSync(LOG_FILE, `${JSON.stringify({ ts: new Date().toISOString(), ...event })}\n`, "utf8");
}
function checkTcp(host, port, timeoutMs = 800) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    let settled = false;
    function done(ok, error) {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(error ? { ok, error } : { ok });
    }
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false, "timeout"));
    socket.once("error", (error) => done(false, error.message));
  });
}
function upstreamPort() {
  if (UPSTREAM.port) return Number(UPSTREAM.port);
  return UPSTREAM.protocol === "https:" ? 443 : 80;
}
function modelsUpstreamPort() {
  if (!MODELS_UPSTREAM) return null;
  if (MODELS_UPSTREAM.port) return Number(MODELS_UPSTREAM.port);
  return MODELS_UPSTREAM.protocol === "https:" ? 443 : 80;
}
function isModelsRequest(req) {
  if ((!MODELS_UPSTREAM && STATIC_MODELS.length === 0) || !["GET", "HEAD"].includes(req.method || "")) return false;
  const url = new URL(req.url || "/", "http://127.0.0.1");
  return url.pathname === "/v1/models";
}
function sanitizeReadInput(input, source) {
  if (!isObject(input)) return [];
  const changes = [];
  if ((input.file_path === undefined || input.file_path === null || input.file_path === "") && typeof input.path === "string" && input.path.trim() !== "") {
    input.file_path = input.path;
    changes.push({ source, field: "file_path", action: "replace", reason: "alias_path_to_file_path" });
  }
  const filePath = typeof input.file_path === "string"
    ? input.file_path
    : (typeof input.path === "string" ? input.path : "");
  if (Object.prototype.hasOwnProperty.call(input, "pages")) {
    const pages = input.pages;
    const blankPages =
      pages === null ||
      pages === undefined ||
      (typeof pages === "string" && pages.trim() === "") ||
      (Array.isArray(pages) && pages.length === 0);
    if (blankPages || !isPdfPath(filePath)) {
      delete input.pages;
      changes.push({
        source,
        field: "pages",
        action: "delete",
        reason: blankPages ? "blank_pages" : "non_pdf_read",
        file_path: filePath || null,
      });
    }
  }
  for (const field of ["offset", "limit"]) {
    if (!Object.prototype.hasOwnProperty.call(input, field)) continue;
    const value = input[field];
    if (value === null || value === undefined || value === "") {
      delete input[field];
      changes.push({ source, field, action: "delete", reason: "blank_number" });
      continue;
    }
    if (typeof value === "number" && !Number.isFinite(value)) {
      delete input[field];
      changes.push({ source, field, action: "delete", reason: "non_finite_number" });
      continue;
    }
    if (field === "offset" && typeof value === "number" && value < 0) {
      input[field] = 0;
      changes.push({ source, field, action: "replace", reason: "negative_offset" });
    }
  }
  return changes;
}
function parseFirstJsonObject(raw) {
  if (typeof raw !== "string") return null;
  const start = raw.search(/\{/);
  if (start < 0) return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < raw.length; index += 1) {
    const ch = raw[index];
    if (inString) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === "\"") {
        inString = false;
      }
      continue;
    }
    if (ch === "\"") {
      inString = true;
      continue;
    }
    if (ch === "{") {
      depth += 1;
      continue;
    }
    if (ch !== "}") continue;
    depth -= 1;
    if (depth !== 0) continue;
    const jsonText = raw.slice(start, index + 1);
    try {
      return {
        value: JSON.parse(jsonText),
        end: index + 1,
        trailing: raw.slice(index + 1).trim(),
      };
    } catch {
      return null;
    }
  }
  return null;
}
function parseJsonObjectAt(raw, start) {
  if (typeof raw !== "string" || start < 0 || raw[start] !== "{") return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < raw.length; index += 1) {
    const ch = raw[index];
    if (inString) {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === "\"") {
        inString = false;
      }
      continue;
    }
    if (ch === "\"") {
      inString = true;
      continue;
    }
    if (ch === "{") {
      depth += 1;
      continue;
    }
    if (ch !== "}") continue;
    depth -= 1;
    if (depth !== 0) continue;
    try {
      return {
        value: JSON.parse(raw.slice(start, index + 1)),
        start,
        end: index + 1,
        trailing: raw.slice(index + 1).trim(),
      };
    } catch {
      return null;
    }
  }
  return null;
}
function findValidJsonObject(raw, predicate) {
  if (typeof raw !== "string") return null;
  for (let offset = 0; offset < raw.length; offset += 1) {
    const start = raw.indexOf("{", offset);
    if (start < 0) return null;
    offset = start;
    const parsed = parseJsonObjectAt(raw, start);
    if (parsed && predicate(parsed.value)) return parsed;
  }
  return null;
}
function isTodoWriteValue(value) {
  return isObject(value) &&
    Array.isArray(value.todos) &&
    value.todos.length > 0 &&
    value.todos.every((todo) =>
      isObject(todo) &&
      typeof todo.content === "string" &&
      typeof todo.status === "string" &&
      typeof todo.activeForm === "string");
}
function repairTodoWriteMissingFirstBrace(raw) {
  if (typeof raw !== "string") return null;
  const repairedRaw = raw.replace(
    /("todos"\s*:\s*\[)\s*([A-Za-z_][A-Za-z0-9_]*"\s*:)/,
    "$1{\"$2",
  );
  if (repairedRaw === raw) return null;
  const firstObject = parseFirstJsonObject(repairedRaw);
  if (!firstObject || !isTodoWriteValue(firstObject.value)) return null;
  return firstObject.value;
}
function extractQuotedValue(raw, key) {
  const pattern = new RegExp(`"${escapeRegExp(key)}"\\s*:\\s*"`, "m");
  const match = pattern.exec(raw);
  if (!match) return null;
  let encoded = "";
  let escaped = false;
  for (let index = match.index + match[0].length; index < raw.length; index += 1) {
    const ch = raw[index];
    if (escaped) {
      encoded += `\\${ch}`;
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === "\"" && /^\s*[,}]/.test(raw.slice(index + 1))) {
      return { encoded, closed: true };
    }
    encoded += ch;
  }
  return { encoded, closed: false };
}
function decodeJsonStringLoose(encoded) {
  const normalized = encoded.replace(/\r\n/g, "\n").replace(/\n/g, "\\n").replace(/\r/g, "\\r");
  try {
    return JSON.parse(`"${normalized}"`);
  } catch {
    return encoded
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      .replace(/\\r/g, "\r")
      .replace(/\\t/g, "\t")
      .replace(/\\"/g, "\"")
      .replace(/\\\\/g, "\\");
  }
}
function extractStringField(raw, key) {
  const value = extractQuotedValue(raw, key);
  if (!value || !value.closed) return null;
  return decodeJsonStringLoose(value.encoded);
}
function extractPrimitiveField(raw, key) {
  const pattern = new RegExp(`"${escapeRegExp(key)}"\\s*:\\s*(true|false|null|-?\\d+(?:\\.\\d+)?)`, "m");
  const match = pattern.exec(raw);
  if (!match) return undefined;
  if (match[1] === "true") return true;
  if (match[1] === "false") return false;
  if (match[1] === "null") return null;
  return Number(match[1]);
}
function firstObjectRepairSegment(raw) {
  if (typeof raw !== "string") return raw;
  const boundary = /}\s*{/.exec(raw);
  if (!boundary) return raw;
  return raw.slice(0, boundary.index + 1);
}
function repairMalformedToolJson(toolName, raw) {
  if (!REPAIR_TOOL_JSON || typeof raw !== "string") return null;
  try {
    JSON.parse(raw);
    return null;
  } catch {
    // Continue with targeted repairs below.
  }
  const firstObject = parseFirstJsonObject(raw);
  if (firstObject && firstObject.trailing.length > 0) {
    return { value: firstObject.value, reason: "extra_top_level_json" };
  }
  if (toolName === "TodoWrite") {
    const validTodoObject = findValidJsonObject(raw, isTodoWriteValue);
    if (validTodoObject) {
      return { value: validTodoObject.value, reason: "repaired_todowrite_json" };
    }
    const repairedTodos = repairTodoWriteMissingFirstBrace(raw);
    if (repairedTodos) {
      return { value: repairedTodos, reason: "repaired_todowrite_missing_first_brace" };
    }
    return null;
  }
  const rootRaw = firstObjectRepairSegment(raw);
  if (toolName === "PowerShell" || toolName === "Bash") {
    const command = extractStringField(rootRaw, "command");
    if (!command) return null;
    const repaired = { command };
    for (const key of ["description"]) {
      const value = extractStringField(rootRaw, key);
      if (value !== null) repaired[key] = value;
    }
    for (const key of ["timeout", "run_in_background", "dangerouslyDisableSandbox"]) {
      const value = extractPrimitiveField(rootRaw, key);
      if (value !== undefined) repaired[key] = value;
    }
    return { value: repaired, reason: "repaired_shell_command_json" };
  }
  if (toolName === "Write") {
    const filePath = extractStringField(rootRaw, "file_path");
    const content = extractStringField(rootRaw, "content");
    if (!filePath || content === null) return null;
    return { value: { file_path: filePath, content }, reason: "repaired_write_json" };
  }
  if (toolName === "Edit") {
    const filePath = extractStringField(rootRaw, "file_path");
    const oldString = extractStringField(rootRaw, "old_string");
    const newString = extractStringField(rootRaw, "new_string");
    if (!filePath || oldString === null || newString === null) return null;
    const value = {
      file_path: filePath,
      old_string: oldString,
      new_string: newString,
    };
    const replaceAll = extractPrimitiveField(rootRaw, "replace_all");
    if (typeof replaceAll === "boolean") value.replace_all = replaceAll;
    return { value, reason: "repaired_edit_json" };
  }
  return null;
}
function sanitizeToolArguments(toolCall, source) {
  if (!isObject(toolCall) || !isObject(toolCall.function)) return [];
  const toolName = toolCall.function.name;
  const args = toolCall.function.arguments;
  const changes = [];
  if (typeof args === "string") {
    const repair = repairMalformedToolJson(toolName, args);
    if (repair && isObject(repair.value)) {
      toolCall.function.arguments = JSON.stringify(repair.value);
      changes.push({
        source,
        field: "function.arguments",
        action: "replace",
        reason: repair.reason,
        tool_name: toolName,
        raw_length: args.length,
      });
    }
  }
  if (toolName !== "Read") return changes;
  const nextArgs = toolCall.function.arguments;
  if (typeof nextArgs === "string") {
    try {
      const parsed = JSON.parse(nextArgs);
      const readChanges = sanitizeReadInput(parsed, source);
      if (readChanges.length > 0) {
        toolCall.function.arguments = JSON.stringify(parsed);
      }
      return [...changes, ...readChanges];
    } catch {
      return changes;
    }
  }
  if (isObject(nextArgs)) {
    return [...changes, ...sanitizeReadInput(nextArgs, source)];
  }
  return changes;
}
function sanitizeAny(value, source = "root") {
  const changes = [];
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      changes.push(...sanitizeAny(item, `${source}[${index}]`));
    });
    return changes;
  }
  if (!isObject(value)) return changes;
  if (value.name === "Read" && isObject(value.input)) {
    changes.push(...sanitizeReadInput(value.input, `${source}.input`));
  }
  if (value.name === "Read" && isObject(value.tool_input)) {
    changes.push(...sanitizeReadInput(value.tool_input, `${source}.tool_input`));
  }
  changes.push(...sanitizeToolArguments(value, `${source}.function.arguments`));
  for (const [key, child] of Object.entries(value)) {
    if (key === "function" && isObject(child) && child.name === "Read") continue;
    changes.push(...sanitizeAny(child, `${source}.${key}`));
  }
  return changes;
}
function sanitizeJsonObject(obj, reqPath) {
  const changes = sanitizeAny(obj);
  if (changes.length > 0) {
    writeSanitizeEvent(reqPath, changes);
  }
  return changes.length > 0;
}
function writeSanitizeEvent(reqPath, changes) {
  const hasToolJsonRepair = changes.some((change) =>
    (typeof change.reason === "string" && change.reason.startsWith("repaired_")) ||
    change.reason === "extra_top_level_json");
  writeEvent({
    type: hasToolJsonRepair ? "tool_arguments_sanitized" : "read_tool_arguments_sanitized",
    path: reqPath,
    change_count: changes.length,
    changes,
  });
}
function sanitizeOpenAiEmptyReasoning(obj, source) {
  const changes = [];
  if (!STRIP_EMPTY_THINKING || !isObject(obj) || !Array.isArray(obj.choices)) {
    return { changed: false, drop: false, changes };
  }
  for (const [choiceIndex, choice] of obj.choices.entries()) {
    if (!isObject(choice)) continue;
    for (const containerKey of ["delta", "message"]) {
      const container = choice[containerKey];
      if (!isObject(container)) continue;
      for (const field of EMPTY_REASONING_FIELDS) {
        if (!Object.prototype.hasOwnProperty.call(container, field)) continue;
        if (!isBlankText(container[field])) continue;
        delete container[field];
        changes.push({
          source: `${source}.choices[${choiceIndex}].${containerKey}`,
          field,
          action: "delete",
          reason: "blank_reasoning",
        });
      }
    }
  }
  const drop = changes.length > 0 &&
    obj.choices.length > 0 &&
    obj.choices.every((choice) => {
      if (!isObject(choice) || choice.finish_reason) return false;
      const hasDelta = Object.prototype.hasOwnProperty.call(choice, "delta");
      const hasMessage = Object.prototype.hasOwnProperty.call(choice, "message");
      const deltaEmpty = !hasDelta || (isObject(choice.delta) && Object.keys(choice.delta).length === 0);
      const messageEmpty = !hasMessage || (isObject(choice.message) && Object.keys(choice.message).length === 0);
      return (hasDelta || hasMessage) && deltaEmpty && messageEmpty;
    });
  return { changed: changes.length > 0, drop, changes };
}
function sanitizeAnthropicEmptyThinkingBlocks(value, source = "root") {
  const changes = [];
  if (!STRIP_EMPTY_THINKING) return changes;
  if (Array.isArray(value)) {
    for (let index = value.length - 1; index >= 0; index -= 1) {
      const item = value[index];
      if (isObject(item) &&
        item.type === "thinking" &&
        isBlankText(item.thinking) &&
        isBlankText(item.signature)) {
        value.splice(index, 1);
        changes.push({
          source: `${source}[${index}]`,
          field: "content",
          action: "delete",
          reason: "blank_thinking_block",
        });
        continue;
      }
      changes.push(...sanitizeAnthropicEmptyThinkingBlocks(item, `${source}[${index}]`));
    }
    return changes;
  }
  if (!isObject(value)) return changes;
  for (const [key, child] of Object.entries(value)) {
    changes.push(...sanitizeAnthropicEmptyThinkingBlocks(child, `${source}.${key}`));
  }
  return changes;
}
function logEmptyThinkingChanges(changes, reqPath) {
  if (changes.length === 0) return;
  writeEvent({
    type: "empty_thinking_sanitized",
    path: reqPath,
    change_count: changes.length,
    changes,
  });
}
function responseHeaders(headers, changed) {
  const next = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) continue;
    if (changed && (lower === "content-length" || lower === "content-encoding")) continue;
    next[key] = value;
  }
  return next;
}
function forwardHeaders(headers) {
  const next = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) continue;
    next[key] = value;
  }
  next.host = UPSTREAM.host;
  next["accept-encoding"] = "identity";
  return next;
}
function forwardHeadersTo(headers, upstream) {
  const next = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) continue;
    next[key] = value;
  }
  next.host = upstream.host;
  next["accept-encoding"] = "identity";
  return next;
}
function requestHeaders(headers, bodyOverride) {
  const next = forwardHeaders(headers);
  if (bodyOverride) {
    for (const key of Object.keys(next)) {
      const lower = key.toLowerCase();
      if (lower === "content-length" || lower === "content-encoding") {
        delete next[key];
      }
    }
    next["content-length"] = String(bodyOverride.length);
  }
  return next;
}
function shouldReadRequestBody(req) {
  if (!TEXT_ONLY_MESSAGE_CONTENT && !PROMOTE_TOOL_TEXT) return false;
  if (!["POST", "PUT", "PATCH"].includes(req.method || "")) return false;
  const url = new URL(req.url || "/", "http://127.0.0.1");
  const contentType = String(req.headers["content-type"] || "");
  return contentType.includes("json") ||
    url.pathname.endsWith("/messages") ||
    url.pathname.endsWith("/chat/completions") ||
    url.pathname.endsWith("/responses");
}
function shouldSanitizeRequestBody(req) {
  return TEXT_ONLY_MESSAGE_CONTENT && shouldReadRequestBody(req);
}
function blockLabel(block) {
  if (!isObject(block)) return typeof block;
  return typeof block.type === "string" && block.type ? block.type : "object";
}
function stringifyBlockValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
function extractTextOnlyContent(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value
      .map((item) => extractTextOnlyContent(item))
      .filter((text) => typeof text === "string" && text.trim() !== "")
      .join("\n");
  }
  if (!isObject(value)) return stringifyBlockValue(value);
  const type = typeof value.type === "string" ? value.type : "";
  if (type === "thinking" || type === "redacted_thinking") return "";
  if (typeof value.text === "string") return value.text;
  if (typeof value.content === "string") return value.content;
  if (value.content !== undefined) return extractTextOnlyContent(value.content);
  if (value.input !== undefined) return stringifyBlockValue(value.input);
  if (value.arguments !== undefined) return stringifyBlockValue(value.arguments);
  if (value.name || value.id || type) {
    const label = [type, value.name, value.id].filter(Boolean).join(" ");
    return `[${label || "content"}]`;
  }
  return stringifyBlockValue(value);
}
function sanitizeContentToTextBlocks(value, source, changes) {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") return value;
  const items = Array.isArray(value) ? value : [value];
  const next = [];
  for (const item of items) {
    if (isObject(item) && item.type === "thinking") {
      changes.push({ source, action: "drop", from_type: "thinking" });
      continue;
    }
    if (isObject(item) && item.type === "redacted_thinking") {
      changes.push({ source, action: "drop", from_type: "redacted_thinking" });
      continue;
    }
    if (isObject(item) && (item.type === "tool_use" || item.type === "tool_result")) {
      next.push(item);
      continue;
    }
    const text = extractTextOnlyContent(item);
    if (typeof text !== "string" || text.trim() === "") {
      changes.push({ source, action: "drop", from_type: blockLabel(item), reason: "blank_after_text_extract" });
      continue;
    }
    if (isObject(item) && item.type === "text" && typeof item.text === "string") {
      next.push(item);
      continue;
    }
    next.push({ type: "text", text });
    changes.push({ source, action: "replace", from_type: blockLabel(item), to_type: "text" });
  }
  if (next.length === 0) {
    next.push({ type: "text", text: "[non-text content omitted]" });
    changes.push({ source, action: "insert", to_type: "text", reason: "empty_content_guard" });
  }
  return next;
}
function sanitizeTextOnlyMessageContentPayload(obj, reqPath) {
  if (!isObject(obj)) return [];
  const changes = [];
  if (Array.isArray(obj.messages)) {
    for (let i = 0; i < obj.messages.length; i += 1) {
      const message = obj.messages[i];
      if (!isObject(message) || !Object.prototype.hasOwnProperty.call(message, "content")) continue;
      message.content = sanitizeContentToTextBlocks(message.content, `messages[${i}].content`, changes);
    }
  }
  if (Object.prototype.hasOwnProperty.call(obj, "system")) {
    obj.system = sanitizeContentToTextBlocks(obj.system, "system", changes);
  }
  if (changes.length > 0) {
    writeEvent({
      type: "text_only_message_content_sanitized",
      path: reqPath,
      change_count: changes.length,
      changes,
    });
  }
  return changes;
}
function sanitizeRequestBody(req, reqPath, body) {
  if (!shouldSanitizeRequestBody(req) || body.length === 0) return body;
  const text = body.toString("utf8");
  if (!/^\s*[\[{]/.test(text)) return body;
  try {
    const obj = JSON.parse(text);
    const changes = sanitizeTextOnlyMessageContentPayload(obj, reqPath);
    if (changes.length === 0) return body;
    return Buffer.from(JSON.stringify(obj), "utf8");
  } catch (error) {
    writeEvent({ type: "request_body_sanitize_error", path: reqPath, message: error.message });
    return body;
  }
}
const SUPPORTED_TOOL_SCHEMA_KEYS = new Set([
  "$schema", "$id", "id", "definitions", "components", "oneOf", "anyOf", "allOf", "$ref",
  "type", "properties", "required", "additionalProperties", "items", "enum", "const",
  "description", "title", "default", "minLength", "maxLength", "pattern", "minimum",
  "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems",
]);
function isSupportedToolSchema(schema) {
  if (!isObject(schema)) return false;
  if (Object.keys(schema).some((key) => !SUPPORTED_TOOL_SCHEMA_KEYS.has(key))) return false;
  if (schema.type !== undefined && typeof schema.type !== "string") return false;
  if (schema.required !== undefined && (!Array.isArray(schema.required) || schema.required.some((key) => typeof key !== "string"))) return false;
  if (schema.enum !== undefined && !Array.isArray(schema.enum)) return false;
  if (schema.properties !== undefined) {
    if (!isObject(schema.properties)) return false;
    if (Object.values(schema.properties).some((child) => !isSupportedToolSchema(child))) return false;
  }
  if (schema.items !== undefined && !isSupportedToolSchema(schema.items)) return false;
  if (isObject(schema.additionalProperties) && !isSupportedToolSchema(schema.additionalProperties)) return false;
  if (schema.additionalProperties !== undefined && typeof schema.additionalProperties !== "boolean" && !isObject(schema.additionalProperties)) return false;
  return true;
}
function unsupportedToolSchemaReasons(schema, source = "root", reasons = []) {
  if (!isObject(schema)) {
    reasons.push(`${source}:not_object`);
    return reasons;
  }
  for (const key of Object.keys(schema)) {
    if (!SUPPORTED_TOOL_SCHEMA_KEYS.has(key)) reasons.push(`${source}:${key}`);
  }
  if (schema.type !== undefined && typeof schema.type !== "string") reasons.push(`${source}:type_not_string`);
  if (isObject(schema.properties)) {
    for (const [key, child] of Object.entries(schema.properties)) {
      unsupportedToolSchemaReasons(child, `${source}.properties.${key}`, reasons);
    }
  }
  if (schema.items !== undefined) unsupportedToolSchemaReasons(schema.items, `${source}.items`, reasons);
  if (isObject(schema.additionalProperties)) unsupportedToolSchemaReasons(schema.additionalProperties, `${source}.additionalProperties`, reasons);
  return Array.from(new Set(reasons));
}
function valueMatchesToolSchema(value, schema) {
  if (!isSupportedToolSchema(schema)) return false;
  if (schema.const !== undefined && JSON.stringify(value) !== JSON.stringify(schema.const)) return false;
  if (Array.isArray(schema.enum) && !schema.enum.some((item) => JSON.stringify(item) === JSON.stringify(value))) return false;
  const type = schema.type;
  if (type === "object" || schema.properties || schema.required) {
    if (!isObject(value)) return false;
    const properties = isObject(schema.properties) ? schema.properties : {};
    const required = Array.isArray(schema.required) ? schema.required : [];
    if (required.some((key) => !Object.prototype.hasOwnProperty.call(value, key))) return false;
    for (const [key, child] of Object.entries(value)) {
      if (Object.prototype.hasOwnProperty.call(properties, key)) {
        if (!valueMatchesToolSchema(child, properties[key])) return false;
      } else if (schema.additionalProperties === false) {
        return false;
      } else if (isObject(schema.additionalProperties) && !valueMatchesToolSchema(child, schema.additionalProperties)) {
        return false;
      }
    }
    return true;
  }
  if (type === "array") {
    if (!Array.isArray(value)) return false;
    if (Number.isInteger(schema.minItems) && value.length < schema.minItems) return false;
    if (Number.isInteger(schema.maxItems) && value.length > schema.maxItems) return false;
    return schema.items === undefined || value.every((item) => valueMatchesToolSchema(item, schema.items));
  }
  if (type === "string") {
    if (typeof value !== "string") return false;
    if (Number.isInteger(schema.minLength) && value.length < schema.minLength) return false;
    if (Number.isInteger(schema.maxLength) && value.length > schema.maxLength) return false;
    if (typeof schema.pattern === "string") {
      try {
        if (!new RegExp(schema.pattern).test(value)) return false;
      } catch {
        return false;
      }
    }
    return true;
  }
  if (type === "integer" && !Number.isInteger(value)) return false;
  if (type === "number" && (typeof value !== "number" || !Number.isFinite(value))) return false;
  if (type === "boolean" && typeof value !== "boolean") return false;
  if (type === "null" && value !== null) return false;
  if (["integer", "number"].includes(type)) {
    if (typeof schema.minimum === "number" && value < schema.minimum) return false;
    if (typeof schema.maximum === "number" && value > schema.maximum) return false;
    if (typeof schema.exclusiveMinimum === "number" && value <= schema.exclusiveMinimum) return false;
    if (typeof schema.exclusiveMaximum === "number" && value >= schema.exclusiveMaximum) return false;
  }
  return type === undefined || ["integer", "number", "boolean", "null"].includes(type);
}
function extractToolPromotionContext(body, reqPath) {
  if (!PROMOTE_TOOL_TEXT || !reqPath.endsWith("/messages") || body.length === 0) return null;
  try {
    const obj = JSON.parse(body.toString("utf8"));
    const tools = Array.isArray(obj.tools)
      ? obj.tools.filter((tool) => isObject(tool) && typeof tool.name === "string" && isObject(tool.input_schema))
      : [];
    writeEvent({ type: "tool_text_promotion_context", path: reqPath, tool_count: tools.length });
    return tools.length > 0 ? { tools } : null;
  } catch {
    return null;
  }
}
function parseToolCandidateObject(text) {
  const normalized = text.replace(/"([A-Za-z]:\\(?:[^"\\]|\\.)*)"/g, (quoted) => {
    const value = quoted.slice(1, -1);
    let escaped = "";
    for (let index = 0; index < value.length; index += 1) {
      if (value[index] !== "\\") {
        escaped += value[index];
      } else if (value[index + 1] === "\\") {
        escaped += "\\\\";
        index += 1;
      } else {
        escaped += "\\\\";
      }
    }
    return `"${escaped}"`;
  });
  try {
    const input = JSON.parse(normalized);
    return isObject(input) ? { input, repairedWindowsPath: normalized !== text } : null;
  } catch {
    return null;
  }
}
function extractToolCandidate(text) {
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  const pure = parseToolCandidateObject(trimmed);
  if (pure) return { input: pure.input, prefix: "", mode: pure.repairedWindowsPath ? "pure_json_windows_path_repaired" : "pure_json" };
  const separators = Array.from(text.matchAll(/\r?\n\r?\n/g));
  if (separators.length === 0) return null;
  const separator = separators[separators.length - 1];
  const suffix = text.slice(separator.index + separator[0].length).trim();
  const prefix = text.slice(0, separator.index).trimEnd();
  if (!prefix || !suffix) return null;
  const trailing = parseToolCandidateObject(suffix);
  return trailing
    ? { input: trailing.input, prefix, mode: trailing.repairedWindowsPath ? "trailing_json_windows_path_repaired" : "trailing_json" }
    : null;
}
function uniqueToolMatch(input, tools) {
  const matches = tools.filter((tool) => valueMatchesToolSchema(input, tool.input_schema));
  return matches.length === 1 ? matches[0] : null;
}
function parseSseFrame(frame) {
  const lines = frame.split(/\r?\n/);
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (dataLines.length !== 1) return { frame, lines, obj: null };
  try {
    return { frame, lines, obj: JSON.parse(dataLines[0].replace(/^data:\s?/, "")) };
  } catch {
    return { frame, lines, obj: null };
  }
}
function renderSseFrame(parsed, obj) {
  return parsed.lines
    .map((line) => (line.startsWith("data:") ? `data: ${JSON.stringify(obj)}` : line))
    .join("\n");
}
function newToolUseFrames(index, toolName, input, toolUseId) {
  return [
    `event: content_block_start\ndata: ${JSON.stringify({ type: "content_block_start", index, content_block: { type: "tool_use", id: toolUseId, name: toolName, input: {} } })}`,
    `event: content_block_delta\ndata: ${JSON.stringify({ type: "content_block_delta", index, delta: { type: "input_json_delta", partial_json: JSON.stringify(input) } })}`,
    `event: content_block_stop\ndata: ${JSON.stringify({ type: "content_block_stop", index })}`,
  ];
}
function promoteAnthropicToolTextSse(raw, context, reqPath) {
  if (!context || !Array.isArray(context.tools) || !raw.includes("message_delta")) return raw;
  const hadTrailingBreak = /\r?\n\r?\n$/.test(raw);
  const frames = raw.split(/\r?\n\r?\n/).filter((frame) => frame !== "").map(parseSseFrame);
  const blocks = new Map();
  let messageDelta = null;
  let maxIndex = -1;
  for (let position = 0; position < frames.length; position += 1) {
    const obj = frames[position].obj;
    if (!isObject(obj)) continue;
    if (obj.type === "content_block_start" && Number.isInteger(obj.index)) {
      maxIndex = Math.max(maxIndex, obj.index);
      if (obj.content_block?.type === "text") {
        blocks.set(obj.index, { index: obj.index, start: position, stop: -1, deltas: [], text: String(obj.content_block.text || "") });
      }
    } else if (obj.type === "content_block_delta" && blocks.has(obj.index) && obj.delta?.type === "text_delta") {
      const block = blocks.get(obj.index);
      block.deltas.push(position);
      block.text += String(obj.delta.text || "");
    } else if (obj.type === "content_block_stop" && blocks.has(obj.index)) {
      blocks.get(obj.index).stop = position;
    } else if (obj.type === "message_delta") {
      messageDelta = position;
    }
  }
  if (messageDelta === null || frames[messageDelta].obj?.delta?.stop_reason !== "end_turn") return raw;
  const matches = [];
  for (const block of blocks.values()) {
    if (block.stop < 0 || block.index !== maxIndex) continue;
    const candidate = extractToolCandidate(block.text);
    if (!candidate) continue;
    const tool = uniqueToolMatch(candidate.input, context.tools);
    if (tool) {
      matches.push({ block, candidate, tool });
    } else {
      const matchCount = context.tools.filter((item) => valueMatchesToolSchema(candidate.input, item.input_schema)).length;
      const nearTools = context.tools
        .filter((item) => (item.input_schema.required || []).every((key) => Object.prototype.hasOwnProperty.call(candidate.input, key)))
        .map((item) => ({ name: item.name, unsupported: unsupportedToolSchemaReasons(item.input_schema).slice(0, 8) }));
      writeEvent({ type: "tool_text_promotion_skipped", path: reqPath, reason: "schema_match_not_unique", match_count: matchCount, candidate_mode: candidate.mode, source_index: block.index, candidate_keys: Object.keys(candidate.input), near_tools: nearTools });
    }
  }
  if (matches.length !== 1) return raw;
  const { block, candidate, tool } = matches[0];
  const toolUseId = `toolu_sanitizer_${crypto.randomUUID().replace(/-/g, "").slice(0, 20)}`;
  const removed = new Set();
  const startObj = frames[block.start].obj;
  const firstDelta = block.deltas[0];
  if (candidate.prefix) {
    startObj.content_block.text = "";
    if (firstDelta !== undefined) {
      frames[firstDelta].obj.delta.text = candidate.prefix;
      for (const position of block.deltas.slice(1)) removed.add(position);
    } else {
      frames.splice(block.stop, 0, parseSseFrame(`event: content_block_delta\ndata: ${JSON.stringify({ type: "content_block_delta", index: block.index, delta: { type: "text_delta", text: candidate.prefix } })}`));
      block.stop += 1;
      if (messageDelta >= block.stop) messageDelta += 1;
    }
  } else {
    startObj.content_block = { type: "tool_use", id: toolUseId, name: tool.name, input: {} };
    frames[firstDelta].obj.delta = { type: "input_json_delta", partial_json: JSON.stringify(candidate.input) };
    for (const position of block.deltas.slice(1)) removed.add(position);
  }
  const rendered = [];
  for (let position = 0; position < frames.length; position += 1) {
    if (removed.has(position)) continue;
    if (position === messageDelta) frames[position].obj.delta.stop_reason = "tool_use";
    rendered.push(frames[position].obj ? renderSseFrame(frames[position], frames[position].obj) : frames[position].frame);
    if (candidate.prefix && position === block.stop) {
      rendered.push(...newToolUseFrames(maxIndex + 1, tool.name, candidate.input, toolUseId));
    }
  }
  writeEvent({
    type: "tool_text_promoted",
    path: reqPath,
    tool_name: tool.name,
    candidate_mode: candidate.mode,
    source_index: block.index,
  });
  return `${rendered.join("\n\n")}${hadTrailingBreak ? "\n\n" : ""}`;
}
function hasRequiredReadFilePath(input) {
  return isObject(input) &&
    typeof input.file_path === "string" &&
    input.file_path.indexOf("\u0000") === -1 &&
    input.file_path.trim() !== "";
}
function normalizeReadFilePathAlias(input) {
  if (!isObject(input)) return false;
  if (hasRequiredReadFilePath(input) || typeof input.path !== "string" || input.path.trim() === "") return false;
  input.file_path = input.path;
  delete input.path;
  return true;
}
function invalidReadToolText() {
  return "[sanitizer] Invalid Read tool call: missing required file_path.";
}
function validateAnthropicReadToolUseSse(raw, reqPath) {
  if (!ENFORCE_READ_FILE_PATH || !raw.includes("content_block_start")) return raw;
  const hadTrailingBreak = /\r?\n\r?\n$/.test(raw);
  const frames = raw.split(/\r?\n\r?\n/).filter((frame) => frame !== "").map(parseSseFrame);
  const blocks = new Map();
  const messageDeltas = [];
  const removed = new Set();
  const redactedThinkingIndices = new Set();
  for (let position = 0; position < frames.length; position += 1) {
    const obj = frames[position].obj;
    if (!isObject(obj)) continue;
    if (obj.type === "content_block_start" && Number.isInteger(obj.index)) {
      if (obj.content_block?.type === "redacted_thinking") {
        redactedThinkingIndices.add(obj.index);
        removed.add(position);
        continue;
      }
      if (obj.content_block?.type === "tool_use") {
        blocks.set(obj.index, {
          index: obj.index,
          name: obj.content_block.name,
          start: position,
          input: obj.content_block.input,
          partialJson: "",
          deltaPositions: [],
        });
      }
    } else if (Number.isInteger(obj.index) && redactedThinkingIndices.has(obj.index)) {
      removed.add(position);
    } else if (obj.type === "content_block_delta" && blocks.has(obj.index) && obj.delta?.type === "input_json_delta") {
      const block = blocks.get(obj.index);
      block.partialJson += String(obj.delta.partial_json || "");
      block.deltaPositions.push(position);
    } else if (obj.type === "message_delta") {
      messageDeltas.push(position);
    }
  }
  let normalized = redactedThinkingIndices.size > 0;
  for (const block of blocks.values()) {
    if (block.name !== "Read") continue;
    let input = block.input;
    let reason = "missing_file_path";
    if (block.partialJson.trim() !== "") {
      try {
        input = JSON.parse(block.partialJson);
      } catch {
        reason = "invalid_input_json";
      }
    }
    const sourceInputKeys = isObject(input) ? Object.keys(input).sort() : [];
    const normalizedAlias = reason !== "invalid_input_json" && normalizeReadFilePathAlias(input);
    if (reason !== "invalid_input_json" && hasRequiredReadFilePath(input)) {
      if (normalizedAlias) {
        normalized = true;
        if (block.deltaPositions.length > 0) {
          const firstDelta = block.deltaPositions[0];
          frames[firstDelta].obj.delta.partial_json = JSON.stringify(input);
          block.deltaPositions.slice(1).forEach((position) => removed.add(position));
        } else {
          frames[block.start].obj.content_block.input = input;
        }
        writeEvent({
          type: "read_tool_input_normalized",
          path: reqPath,
          source_index: block.index,
          source_input_keys: sourceInputKeys,
        });
      }
      continue;
    }
    const fallbackInput = isObject(input) ? input : {};
    if (typeof fallbackInput.file_path !== "string") {
      fallbackInput.file_path = typeof fallbackInput.path === "string" ? fallbackInput.path : "[missing_file_path]";
    }
    fallbackInput.file_path = fallbackInput.file_path.replace(/\0/g, "");
    if (block.deltaPositions.length > 0) {
      const firstDelta = block.deltaPositions[0];
      frames[firstDelta].obj.delta.partial_json = JSON.stringify(fallbackInput);
      block.deltaPositions.slice(1).forEach((position) => removed.add(position));
    } else {
      frames[block.start].obj.content_block.input = fallbackInput;
    }
    normalized = true;
    writeEvent({
      type: "read_tool_input_repaired_fallback",
      path: reqPath,
      reason,
      source_index: block.index,
      source_input_keys: sourceInputKeys,
    });
  }
  if (!normalized && removed.size === 0) return raw;
  const rendered = frames
    .filter((_, position) => !removed.has(position))
    .map((frame) => (frame.obj ? renderSseFrame(frame, frame.obj) : frame.frame));
  return `${rendered.join("\n\n")}${hadTrailingBreak ? "\n\n" : ""}`;
}
function validateBufferedAnthropicReadToolUse(obj, reqPath) {
  if (!ENFORCE_READ_FILE_PATH || !isObject(obj) || !Array.isArray(obj.content)) return false;
  let rejected = false;
  let remainingToolUse = false;
  obj.content = obj.content.map((block) => {
    if (!isObject(block) || block.type !== "tool_use") return block;
    if (block.name !== "Read") {
      remainingToolUse = true;
      return block;
    }
    const sourceInputKeys = isObject(block.input) ? Object.keys(block.input).sort() : [];
    if (normalizeReadFilePathAlias(block.input)) {
      writeEvent({ type: "read_tool_input_normalized", path: reqPath, source_input_keys: sourceInputKeys });
    }
    if (hasRequiredReadFilePath(block.input)) {
      remainingToolUse = true;
      return block;
    }
    if (!hasRequiredReadFilePath(block.input)) {
      if (!isObject(block.input)) block.input = {};
      if (typeof block.input.file_path !== "string") {
        block.input.file_path = typeof block.input.path === "string" ? block.input.path : "[missing_file_path]";
      }
      block.input.file_path = block.input.file_path.replace(/ /g, "");
      writeEvent({ type: "read_tool_input_repaired_fallback", path: reqPath, source_input_keys: sourceInputKeys });
    }
    remainingToolUse = true;
    return block;
  });
  if (rejected && !remainingToolUse && obj.stop_reason === "tool_use") obj.stop_reason = "end_turn";
  return rejected;
}
function modelsBodyFromIds(ids) {
  const uniqueIds = Array.from(new Set(ids)).filter(Boolean);
  const data = uniqueIds.map((id) => ({
    id,
    object: "model",
    created: 1700000000,
    owned_by: id.toLowerCase().includes("qwen") ? "qwen" : "provider",
  }));
  return {
    object: "list",
    data,
    models: uniqueIds,
  };
}
function normalizeModelsBody(text) {
  const obj = JSON.parse(text);
  const ids = [];
  if (Array.isArray(obj.data)) {
    for (const item of obj.data) {
      if (typeof item === "string") ids.push(item);
      else if (isObject(item) && typeof item.id === "string") ids.push(item.id);
    }
  }
  if (Array.isArray(obj.models)) {
    for (const item of obj.models) {
      if (typeof item === "string") ids.push(item);
      else if (isObject(item) && typeof item.id === "string") ids.push(item.id);
    }
  }
  return modelsBodyFromIds(ids);
}
function handleModelsRequest(req, res) {
  if (STATIC_MODELS.length > 0) {
    const body = Buffer.from(JSON.stringify(modelsBodyFromIds(STATIC_MODELS)), "utf8");
    res.writeHead(200, {
      "content-type": "application/json",
      "content-length": String(body.length),
    });
    if (req.method === "HEAD") res.end();
    else res.end(body);
    return;
  }
  const target = new URL(MODELS_UPSTREAM.toString());
  const transport = target.protocol === "https:" ? https : http;
  const proxyReq = transport.request({
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port || (target.protocol === "https:" ? 443 : 80),
    method: "GET",
    path: `${target.pathname}${target.search}`,
    headers: forwardHeadersTo(req.headers, target),
  }, (upstreamRes) => {
    const chunks = [];
    upstreamRes.on("data", (chunk) => chunks.push(chunk));
    upstreamRes.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8");
      try {
        const body = Buffer.from(JSON.stringify(normalizeModelsBody(text)), "utf8");
        res.writeHead(upstreamRes.statusCode || 200, {
          "content-type": "application/json",
          "content-length": String(body.length),
        });
        if (req.method === "HEAD") res.end();
        else res.end(body);
      } catch (error) {
        writeEvent({ type: "models_proxy_error", path: target.pathname, message: error.message });
        res.writeHead(502, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "models_proxy_error", message: error.message }));
      }
    });
  });
  proxyReq.on("error", (error) => {
    writeEvent({ type: "models_proxy_error", path: target.pathname, message: error.message });
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
    }
    res.end(JSON.stringify({ error: "models_proxy_error", message: error.message }));
  });
  proxyReq.end();
}
function getChoiceState(streamState, choiceIndex) {
  if (!streamState.choices.has(choiceIndex)) {
    streamState.choices.set(choiceIndex, {
      toolCalls: new Map(),
      functionCall: null,
      finishReason: null,
    });
  }
  return streamState.choices.get(choiceIndex);
}
function rememberChunkTemplate(streamState, obj) {
  if (streamState.template || !isObject(obj)) return;
  streamState.template = {
    id: obj.id,
    object: obj.object || "chat.completion.chunk",
    created: obj.created,
    model: obj.model,
  };
}
function stripEmpty(value) {
  for (const key of Object.keys(value)) {
    if (value[key] === undefined) delete value[key];
  }
  return value;
}
function captureOpenAiToolDeltas(obj, streamState) {
  if (!isObject(obj) || !Array.isArray(obj.choices)) return { changed: false, emit: true };
  let captured = false;
  let hasPayloadAfterCapture = false;
  rememberChunkTemplate(streamState, obj);
  for (const choice of obj.choices) {
    if (!isObject(choice)) continue;
    const choiceIndex = Number.isInteger(choice.index) ? choice.index : 0;
    const choiceState = getChoiceState(streamState, choiceIndex);
    const delta = isObject(choice.delta) ? choice.delta : {};
    if (choice.finish_reason === "tool_calls" || choice.finish_reason === "function_call") {
      choiceState.finishReason = choice.finish_reason;
      choice.finish_reason = null;
      captured = true;
    }
    if (Array.isArray(delta.tool_calls)) {
      for (const part of delta.tool_calls) {
        if (!isObject(part)) continue;
        const callIndex = Number.isInteger(part.index) ? part.index : 0;
        if (!choiceState.toolCalls.has(callIndex)) {
          choiceState.toolCalls.set(callIndex, {
            index: callIndex,
            id: "",
            type: "function",
            name: "",
            arguments: "",
          });
        }
        const call = choiceState.toolCalls.get(callIndex);
        if (typeof part.id === "string") call.id += part.id;
        if (typeof part.type === "string") call.type = part.type;
        if (isObject(part.function)) {
          if (typeof part.function.name === "string") call.name += part.function.name;
          if (typeof part.function.arguments === "string") call.arguments += part.function.arguments;
        }
      }
      delete delta.tool_calls;
      captured = true;
    }
    if (isObject(delta.function_call)) {
      if (!choiceState.functionCall) {
        choiceState.functionCall = { name: "", arguments: "" };
      }
      if (typeof delta.function_call.name === "string") {
        choiceState.functionCall.name += delta.function_call.name;
      }
      if (typeof delta.function_call.arguments === "string") {
        choiceState.functionCall.arguments += delta.function_call.arguments;
      }
      delete delta.function_call;
      captured = true;
    }
    if (Object.keys(delta).length > 0 || choice.finish_reason) {
      hasPayloadAfterCapture = true;
    }
  }
  return { changed: captured, emit: !captured || hasPayloadAfterCapture };
}
function buildChunk(streamState, choiceIndex, delta, finishReason = null) {
  const base = streamState.template || {};
  return stripEmpty({
    id: base.id || "read-sanitizer-stream",
    object: base.object || "chat.completion.chunk",
    created: base.created || Math.floor(Date.now() / 1000),
    model: base.model,
    choices: [{
      index: Number(choiceIndex),
      delta,
      finish_reason: finishReason,
    }],
  });
}
function flushCapturedOpenAiTools(streamState, clientRes, reqPath) {
  if (streamState.flushed) return;
  streamState.flushed = true;
  for (const [choiceIndex, choiceState] of streamState.choices.entries()) {
    if (choiceState.toolCalls.size > 0) {
      const toolCalls = Array.from(choiceState.toolCalls.values())
        .sort((a, b) => a.index - b.index)
        .map((call) => {
          const wrapper = { function: { name: call.name, arguments: call.arguments } };
          const changes = sanitizeToolArguments(
            wrapper,
            `stream.choice${choiceIndex}.tool_calls[${call.index}].function.arguments`,
          );
          if (changes.length > 0) {
            writeSanitizeEvent(reqPath, changes);
          }
          return stripEmpty({
            index: call.index,
            id: call.id || undefined,
            type: call.type || "function",
            function: {
              name: call.name,
              arguments: wrapper.function.arguments,
            },
          });
        });
      clientRes.write(`data: ${JSON.stringify(buildChunk(streamState, choiceIndex, { tool_calls: toolCalls }))}\n\n`);
      clientRes.write(`data: ${JSON.stringify(buildChunk(streamState, choiceIndex, {}, choiceState.finishReason || "tool_calls"))}\n\n`);
    }
    if (choiceState.functionCall) {
      const wrapper = {
        function: {
          name: choiceState.functionCall.name,
          arguments: choiceState.functionCall.arguments,
        },
      };
      const changes = sanitizeToolArguments(wrapper, `stream.choice${choiceIndex}.function_call.arguments`);
      if (changes.length > 0) {
        writeSanitizeEvent(reqPath, changes);
      }
      clientRes.write(`data: ${JSON.stringify(buildChunk(streamState, choiceIndex, {
        function_call: {
          name: wrapper.function.name,
          arguments: wrapper.function.arguments,
        },
      }))}\n\n`);
      clientRes.write(`data: ${JSON.stringify(buildChunk(streamState, choiceIndex, {}, choiceState.finishReason || "function_call"))}\n\n`);
    }
  }
}
function handleSse(upstreamRes, clientRes, reqPath, promotionContext = null) {
  const shouldValidateAnthropicRead = ENFORCE_READ_FILE_PATH && reqPath.endsWith("/messages");
  if ((PROMOTE_TOOL_TEXT && promotionContext) || shouldValidateAnthropicRead) {
    const chunks = [];
    upstreamRes.on("data", (chunk) => chunks.push(chunk));
    upstreamRes.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      let next = shouldValidateAnthropicRead ? validateAnthropicReadToolUseSse(raw, reqPath) : raw;
      if (PROMOTE_TOOL_TEXT && promotionContext) {
        next = promoteAnthropicToolTextSse(next, promotionContext, reqPath);
      }
      clientRes.writeHead(
        upstreamRes.statusCode || 200,
        upstreamRes.statusMessage,
        responseHeaders(upstreamRes.headers, next !== raw),
      );
      clientRes.end(next);
    });
    return;
  }
  const headers = responseHeaders(upstreamRes.headers, true);
  clientRes.writeHead(upstreamRes.statusCode || 200, upstreamRes.statusMessage, headers);
  const decoder = new StringDecoder("utf8");
  let pending = "";
  const streamState = { choices: new Map(), template: null, flushed: false };
  function flushLine(line) {
    if (!line.startsWith("data:")) {
      clientRes.write(`${line}\n`);
      return;
    }
    const prefix = line.match(/^data:\s*/)?.[0] || "data: ";
    const payload = line.slice(prefix.length);
    if (payload === "[DONE]" || payload.trim() === "") {
      if (payload === "[DONE]") flushCapturedOpenAiTools(streamState, clientRes, reqPath);
      clientRes.write(`${line}\n`);
      return;
    }
    try {
      const obj = JSON.parse(payload);
      const emptyReasoning = sanitizeOpenAiEmptyReasoning(obj, "stream");
      logEmptyThinkingChanges(emptyReasoning.changes, reqPath);
      if (emptyReasoning.drop) return;
      // Filter out "Thought for Xs" text content
      if (isObject(obj) && Array.isArray(obj.choices)) {
        for (const choice of obj.choices) {
          if (isObject(choice) && isObject(choice.delta) && typeof choice.delta.content === "string") {
            const originalContent = choice.delta.content;
            // Remove "Thought for Xs" patterns (exact match or embedded)
            choice.delta.content = choice.delta.content.replace(THOUGHT_FOR_PATTERN_MULTI, "").trim();
            if (choice.delta.content !== originalContent.trim()) {
              writeEvent({ type: "thought_for_filtered", path: reqPath, original: originalContent, filtered: choice.delta.content });
            }
          }
        }
      }
      const streamCapture = captureOpenAiToolDeltas(obj, streamState);
      if (!streamCapture.changed) sanitizeJsonObject(obj, reqPath);
      if (streamCapture.emit) clientRes.write(`${prefix}${JSON.stringify(obj)}\n`);
    } catch {
      clientRes.write(`${line}\n`);
    }
  }
  upstreamRes.on("data", (chunk) => {
    pending += decoder.write(chunk);
    const lines = pending.split(/\r?\n/);
    pending = lines.pop() || "";
    for (const line of lines) flushLine(line);
  });
  upstreamRes.on("end", () => {
    pending += decoder.end();
    if (pending.length > 0) flushLine(pending);
    flushCapturedOpenAiTools(streamState, clientRes, reqPath);
    clientRes.end();
  });
}
function handleBuffered(upstreamRes, clientRes, reqPath) {
  const chunks = [];
  upstreamRes.on("data", (chunk) => chunks.push(chunk));
  upstreamRes.on("end", () => {
    const body = Buffer.concat(chunks);
    const text = body.toString("utf8");
    const looksJson = /^\s*[\[{]/.test(text);
    const contentType = String(upstreamRes.headers["content-type"] || "");
    if (looksJson || contentType.includes("json")) {
      try {
        const obj = JSON.parse(text);
        const emptyThinkingChanges = sanitizeAnthropicEmptyThinkingBlocks(obj);
        logEmptyThinkingChanges(emptyThinkingChanges, reqPath);
        const invalidReadChanges = validateBufferedAnthropicReadToolUse(obj, reqPath);
        // Filter out "Thought for Xs" text content in non-streaming mode
        let thoughtFiltered = false;
        if (isObject(obj) && Array.isArray(obj.choices)) {
          for (const choice of obj.choices) {
            if (isObject(choice) && isObject(choice.message) && typeof choice.message.content === "string") {
              if (THOUGHT_FOR_PATTERN.test(choice.message.content)) {
                choice.message.content = "";
                thoughtFiltered = true;
                writeEvent({ type: "thought_for_filtered_nonstream", path: reqPath });
              }
            }
          }
        }
        const changed = sanitizeJsonObject(obj, reqPath) || emptyThinkingChanges.length > 0 || thoughtFiltered || invalidReadChanges;
        if (changed) {
          const nextBody = Buffer.from(JSON.stringify(obj), "utf8");
          const headers = responseHeaders(upstreamRes.headers, true);
          headers["content-length"] = String(nextBody.length);
          clientRes.writeHead(upstreamRes.statusCode || 200, upstreamRes.statusMessage, headers);
          clientRes.end(nextBody);
          return;
        }
      } catch {
        // Pass through unparseable responses unchanged.
      }
    }
    clientRes.writeHead(
      upstreamRes.statusCode || 200,
      upstreamRes.statusMessage,
      responseHeaders(upstreamRes.headers, false),
    );
    clientRes.end(body);
  });
}
const server = http.createServer(async (req, res) => {
  if (req.url === "/__read_sanitizer/health") {
    const upstreamTcp = await checkTcp(UPSTREAM.hostname, upstreamPort());
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({
      ok: true,
      pid: process.pid,
      listen: `${LISTEN_HOST}:${LISTEN_PORT}`,
      upstream: UPSTREAM.toString(),
      features: {
        repair_tool_json: REPAIR_TOOL_JSON,
        strip_empty_thinking: STRIP_EMPTY_THINKING,
        text_only_message_content: TEXT_ONLY_MESSAGE_CONTENT,
        promote_tool_text: PROMOTE_TOOL_TEXT,
        enforce_read_file_path: ENFORCE_READ_FILE_PATH,
        models_upstream: Boolean(MODELS_UPSTREAM),
        static_models: STATIC_MODELS.length > 0,
      },
      upstream_tcp: upstreamTcp,
      models_upstream: MODELS_UPSTREAM ? MODELS_UPSTREAM.toString() : null,
      static_models: STATIC_MODELS,
      models_upstream_tcp: MODELS_UPSTREAM
        ? await checkTcp(MODELS_UPSTREAM.hostname, modelsUpstreamPort())
        : null,
    }));
    return;
  }
  if (isModelsRequest(req)) {
    handleModelsRequest(req, res);
    return;
  }
  const target = new URL(req.url || "/", UPSTREAM);
  const transport = target.protocol === "https:" ? https : http;
  function sendProxy(bodyOverride, promotionContext = null) {
    const proxyReq = transport.request({
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (target.protocol === "https:" ? 443 : 80),
      method: req.method,
      path: `${target.pathname}${target.search}`,
      headers: requestHeaders(req.headers, bodyOverride),
    }, (upstreamRes) => {
      const contentType = String(upstreamRes.headers["content-type"] || "");
      if (contentType.includes("text/event-stream")) {
        handleSse(upstreamRes, res, target.pathname, promotionContext);
      } else {
        handleBuffered(upstreamRes, res, target.pathname);
      }
    });
    proxyReq.on("error", (error) => {
      writeEvent({ type: "proxy_error", path: target.pathname, message: error.message });
      if (!res.headersSent) {
        res.writeHead(502, { "content-type": "application/json" });
      }
      res.end(JSON.stringify({ error: "read_sanitizer_upstream_error", message: error.message }));
    });
    if (bodyOverride) {
      proxyReq.end(bodyOverride);
    } else {
      req.pipe(proxyReq);
    }
  }
  if (shouldReadRequestBody(req)) {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      const promotionContext = extractToolPromotionContext(body, target.pathname);
      sendProxy(sanitizeRequestBody(req, target.pathname, body), promotionContext);
    });
    req.on("error", (error) => {
      writeEvent({ type: "request_body_read_error", path: target.pathname, message: error.message });
      if (!res.headersSent) {
        res.writeHead(400, { "content-type": "application/json" });
      }
      res.end(JSON.stringify({ error: "read_sanitizer_request_body_error", message: error.message }));
    });
    return;
  }
  sendProxy(null);
});
server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  writeEvent({
    type: "started",
    listen: `${LISTEN_HOST}:${LISTEN_PORT}`,
    upstream: UPSTREAM.toString(),
  });
});
