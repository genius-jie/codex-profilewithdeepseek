// DeepSeek "Thought for 0s" filter — thin transparent proxy in front of cc-switch's
// Claude local proxy (127.0.0.1:15733). It strips EMPTY `thinking` content blocks
// from the Anthropic Messages API stream so Claude Code stops rendering
// "Thought for 0s" for deepseek-v4-pro.
//
// Own port + own NSSM service (DeepSeekThinkingFilter). Upstream is cc-switch's own
// 15733 proxy, so authentication, model mapping and tool adaptation are all preserved;
// this shim only touches the response stream.
//
// Only blank thinking blocks are dropped (blocks whose accumulated `thinking` text is
// empty/whitespace). Real reasoning is kept and passed through unchanged, with block
// indices renumbered so downstream block ordering stays contiguous.

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { StreamThinkingFilter } = require("./stream-thinking-filter.js");

const HOST = process.env.DEEPSEEK_FILTER_HOST || "127.0.0.1";
const PORT = Number(process.env.DEEPSEEK_FILTER_PORT || "15735");
const UPSTREAM = process.env.DEEPSEEK_FILTER_UPSTREAM || "http://127.0.0.1:15733";
const LOG_DIR = process.env.DEEPSEEK_FILTER_LOG_DIR || path.join(__dirname, "logs-deepseek");
const ENABLE_LOG = !/^(0|false|no|off)$/i.test(process.env.DEEPSEEK_FILTER_LOG || "1");

const upstream = new URL(UPSTREAM);

function isBlank(v) {
  return v == null || (typeof v === "string" && v.trim() === "");
}

function log(event) {
  if (!ENABLE_LOG) return;
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(
      path.join(LOG_DIR, "deepseek-thinking-filter.jsonl"),
      JSON.stringify({ ts: new Date().toISOString(), ...event }) + "\n"
    );
  } catch {
    /* logging must never break proxying */
  }
}

// Streaming SSE filter. Parses the stream into frames (event:/data: lines terminated by
// a blank line), drops thinking blocks that end up empty, renumbering later blocks, and
// coalesces adjacent text blocks. DeepSeek via cc-switch may emit one text content block
// per tiny token fragment; Claude Code then renders each block as a separate list item.
// Adjacent text blocks separated only by blank thinking blocks are one visible paragraph,
// so emit them as one downstream text block.
class EmptyThinkingFilter {
  constructor(emit) {
    this.emit = emit;
    this.buffer = "";
    this.frame = [];
    // Index remapping table: replaces simple subtraction-based renumber.
    // cc-switch may emit tool_use input_json_delta with decreasing indices,
    // so a simple offset cannot work. Instead we maintain a Map from original
    // index → new sequential index, and fall back to the most recently
    // resolved block index for anomalous deltas.
    this.indexMap = new Map();   // original index → new index
    this.nextIndex = 0;          // next new index to assign
    this.lastMappedIndex = -1;   // last successfully resolved new index (fallback)
    this.openBlockOrigIndex = -1; // original index of currently open non-thinking block
    this.thinking = null;        // { index, text, frames: [{eventName, obj}] } | null
    this.textBlock = null;       // currently open source text block metadata | null
    this.mergedTextBlock = null; // adjacent visible text blocks merged for Claude Code | null
    this.dropped = 0;
  }

  push(text) {
    this.buffer += text;
    let idx;
    while ((idx = this.buffer.indexOf("\n")) !== -1) {
      let line = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line === "") this._frameEnd();
      else this.frame.push(line);
    }
  }

  flush() {
    if (this.buffer) {
      let line = this.buffer;
      this.buffer = "";
      if (line.endsWith("\r")) line = line.slice(0, -1);
      this.frame.push(line);
    }
    if (this.frame.length) this._frameEnd();
    this._flushThinking();
    this._flushTextBlock();
  }

  _frameEnd() {
    if (this.frame.length === 0) return;
    const lines = this.frame;
    this.frame = [];

    let eventName = null;
    const dataParts = [];
    for (const l of lines) {
      if (l.startsWith("event:")) eventName = l.slice(6).trim();
      else if (l.startsWith("data:")) dataParts.push(l.slice(5).replace(/^ /, ""));
    }
    if (dataParts.length === 0) { this._emitLines(lines); return; }

    const data = dataParts.join("\n");
    if (data === "[DONE]") {
      this._flushThinking();
      this._flushTextBlock();
      this._emitLines(lines);
      return;
    }

    let obj = null;
    try { obj = JSON.parse(data); } catch { this._flushThinking(); this._flushTextBlock(); this._emitLines(lines); return; }

    const type = obj.type;
    const index = obj.index;

    if (type === "content_block_start") {
      const cb = obj.content_block || {};
      if (cb.type === "thinking") {
        this._finishOpenTextBlock();
        // open a thinking block; buffer until its content_block_stop.
        this.thinking = { index, text: "", frames: [{ eventName, obj }] };
        return;
      }
      this._flushThinking();
      this._finishOpenTextBlock();
      // If this is a text block, start accumulating text deltas
      if (cb.type === "text") {
        this.textBlock = { index, startObj: obj, startEventName: eventName, sawText: false };
        this.openBlockOrigIndex = index;
        return; // don't emit yet; adjacent text blocks may be merged
      }
      this._flushTextBlock(); // flush pending visible text before non-text blocks
      // Register this kept block in the index remapping table
      this.indexMap.set(index, this.nextIndex++);
      this.openBlockOrigIndex = index; // track which block is currently open
      this._emitObject(obj, eventName);
      return;
    }

    if (type === "content_block_delta") {
      const d = obj.delta || {};
      if (this.thinking && index === this.thinking.index && d.type === "thinking_delta") {
        this.thinking.text += (typeof d.thinking === "string" ? d.thinking : "");
        this.thinking.frames.push({ eventName, obj });
        return;
      }
      this._flushThinking();
      // Accumulate text deltas for text blocks
      if (this.textBlock && index === this.textBlock.index && d.type === "text_delta") {
        const text = (typeof d.text === "string" ? d.text : "");
        if (text.length > 0) {
          const firstDeltaForBlock = !this.textBlock.sawText;
          this._ensureMergedTextBlock(this.textBlock.startObj, this.textBlock.startEventName, firstDeltaForBlock);
          this.mergedTextBlock.text += text;
          this.textBlock.sawText = true;
        }
        return; // don't emit yet; merge adjacent source text blocks
      }
      this._finishOpenTextBlock();
      this._flushTextBlock(); // flush any pending text block before processing other deltas
      // Validate delta belongs to currently open block
      let deltaIndex = index;
      if (this.indexMap.has(index) && index !== this.openBlockOrigIndex) {
        // Delta for a closed block (cc-switch index bug) → map to active block
        deltaIndex = this.openBlockOrigIndex >= 0 ? this.openBlockOrigIndex : index;
        obj = Object.assign({}, obj, { index: deltaIndex });
      }
      // Track last successfully mapped index for fallback on anomalous deltas
      if (this.indexMap.has(deltaIndex)) this.lastMappedIndex = this.indexMap.get(deltaIndex);
      this._emitObject(obj, eventName);
      return;
    }

    if (type === "content_block_stop") {
      if (this.thinking && index === this.thinking.index) {
        const th = this.thinking;
        this.thinking = null;
        if (isBlank(th.text)) {
          // empty thinking block -> drop all of its frames (no index assigned)
          this.dropped += 1;
          log({ type: "empty_thinking_block_dropped", index: th.index, text_len: th.text.length });
          return;
        }
        this._flushTextBlock(); // real thinking is a semantic boundary after preceding text
        // keep: register in index remapping table, then emit buffered start/deltas + stop
        this.indexMap.set(th.index, this.nextIndex++);
        for (const f of th.frames) this._emitObject(f.obj, f.eventName);
        this._emitObject(obj, eventName);
        return;
      }
      this._flushThinking();
      // Handle text block stop
      if (this.textBlock && index === this.textBlock.index) {
        this._finishOpenTextBlock(eventName);
        return; // keep merged text pending for possible adjacent text blocks
      }
      this._finishOpenTextBlock();
      this._flushTextBlock();
      // Non-thinking content_block_stop: index already registered at content_block_start
      this.openBlockOrigIndex = -1; // close the block
      this._emitObject(obj, eventName);
      return;
    }

    // message_start / message_delta / message_stop / ping / error — pass through
    this._flushThinking();
    this._finishOpenTextBlock();
    this._flushTextBlock();
    this._emitObject(obj, eventName);
  }

  // Emit any pending (kept) thinking block.
  _flushThinking() {
    if (!this.thinking) return;
    const th = this.thinking;
    this.thinking = null;
    this._flushTextBlock();
    for (const f of th.frames) this._emitObject(f.obj, f.eventName);
  }

  _ensureMergedTextBlock(startObj, startEventName, countSourceBlock) {
    if (!this.mergedTextBlock) {
      const outIndex = this.nextIndex++;
      this.indexMap.set(startObj.index, outIndex);
      this.mergedTextBlock = {
        firstIndex: startObj.index,
        outIndex,
        startObj,
        startEventName,
        stopEventName: "content_block_stop",
        sourceBlocks: 0,
        text: ""
      };
    } else {
      this.indexMap.set(startObj.index, this.mergedTextBlock.outIndex);
    }
    if (countSourceBlock) this.mergedTextBlock.sourceBlocks += 1;
  }

  _finishOpenTextBlock(stopEventName) {
    if (!this.textBlock) return;
    if (this.mergedTextBlock && this.textBlock.sawText) {
      this.mergedTextBlock.stopEventName = stopEventName || "content_block_stop";
    }
    this.textBlock = null;
    this.openBlockOrigIndex = -1;
  }

  // Emit accumulated adjacent text blocks as a single downstream text block.
  _flushTextBlock() {
    this._finishOpenTextBlock();
    if (!this.mergedTextBlock) return;
    const tb = this.mergedTextBlock;
    this.mergedTextBlock = null;
    if (tb.text.length === 0) return;
    // Emit the start event
    this._emitObject(tb.startObj, tb.startEventName);
    // Emit a single accumulated text delta
    const deltaObj = {
      type: "content_block_delta",
      index: tb.firstIndex,
      delta: { type: "text_delta", text: tb.text }
    };
    this._emitObject(deltaObj, "content_block_delta");
    this._emitObject({ type: "content_block_stop", index: tb.firstIndex }, tb.stopEventName);
    if (tb.sourceBlocks > 1) {
      log({ type: "text_blocks_merged", count: tb.sourceBlocks, text_len: tb.text.length });
    }
  }

  _emitObject(obj, eventName) {
    if (obj && Number.isInteger(obj.index)) {
      const origIndex = obj.index;
      let newIndex;
      if (this.indexMap.has(origIndex)) {
        // Known block: use its mapped index
        newIndex = this.indexMap.get(origIndex);
      } else if (this.lastMappedIndex >= 0) {
        // Anomalous index (cc-switch decreasing-index bug for input_json_delta):
        // map to the most recently active block
        newIndex = this.lastMappedIndex;
        this.indexMap.set(origIndex, newIndex);
        log({ type: "index_fallback", original: origIndex, mapped_to: newIndex });
      } else {
        newIndex = 0;
        this.indexMap.set(origIndex, newIndex);
      }
      this.lastMappedIndex = newIndex;
      obj = Object.assign({}, obj, { index: newIndex });
    }
    const out = [];
    if (eventName) out.push("event: " + eventName);
    out.push("data: " + JSON.stringify(obj));
    for (const l of out) this.emit(l + "\n");
    this.emit("\n");
  }

  _emitLines(lines) {
    for (const l of lines) this.emit(l + "\n");
    this.emit("\n");
  }
}

function forward(req, res) {
  const headers = Object.assign({}, req.headers);
  delete headers["accept-encoding"];
  delete headers["content-length"];
  delete headers["transfer-encoding"];
  delete headers["connection"];
  headers["host"] = upstream.host;
  headers["connection"] = "close";

  const proxyReq = http.request(
    {
      protocol: upstream.protocol,
      hostname: upstream.hostname,
      port: upstream.port || (upstream.protocol === "https:" ? 443 : 80),
      method: req.method,
      path: req.url,
      headers,
    },
    (proxyRes) => {
      const contentType = String(proxyRes.headers["content-type"] || "");
      const isSse = contentType.includes("text/event-stream");

      const resHeaders = Object.assign({}, proxyRes.headers);
      delete resHeaders["content-length"];
      delete resHeaders["transfer-encoding"];
      res.writeHead(proxyRes.statusCode || 200, proxyRes.statusMessage, resHeaders);

      if (!isSse) {
        proxyRes.pipe(res);
        return;
      }

      const filter = new StreamThinkingFilter((chunk) => res.write(chunk), { log });
      proxyRes.on("data", (chunk) => filter.push(chunk.toString("utf8")));
      proxyRes.on("end", () => {
        filter.flush();
        log({ type: "stream_done", dropped: filter.dropped });
        res.end();
      });
      proxyRes.on("error", () => res.end());
    }
  );

  proxyReq.on("error", (err) => {
    log({ type: "upstream_error", message: err.message });
    if (!res.headersSent) res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "upstream_error", message: err.message }));
  });

  req.pipe(proxyReq);
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && (req.url === "/health" || req.url === "/healthcheck")) {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, role: "deepseek-thinking-filter", port: PORT, upstream: UPSTREAM }));
    return;
  }
  forward(req, res);
});

if (require.main === module) {
  server.listen(PORT, HOST, () => {
    log({ type: "started", port: PORT, upstream: UPSTREAM });
  });
}

module.exports = { EmptyThinkingFilter: StreamThinkingFilter, StreamThinkingFilter };
