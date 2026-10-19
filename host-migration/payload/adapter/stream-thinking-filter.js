// Streaming SSE filter for DeepSeek via cc-switch.
// Drops empty thinking blocks (eliminating "Thought for 0s") and coalesces
// fragmented text blocks into a single contiguous downstream text block
// in REAL-TIME streaming (tokens are immediately emitted to preserve typing animation).

const fs = require("node:fs");
const path = require("node:path");

class StreamThinkingFilter {
  constructor(emit, options = {}) {
    this.emit = emit;
    this.logFn = typeof options.log === "function" ? options.log : () => {};
    this.buffer = "";
    this.frame = [];

    this.downstreamNextIndex = 0;
    this.activeTextBlock = null; // { downstreamIndex, origIndices: Set } | null
    this.bufferedThinking = null; // { origIndex, text, frames: [] } | null
    this.blockIndexMap = new Map(); // origIndex -> downstreamIndex
    this.droppedEmptyThinkingCount = 0;
    this.mergedTextFragmentCount = 0;
  }

  get dropped() {
    return this.droppedEmptyThinkingCount;
  }

  push(text) {
    this.buffer += text;
    let idx;
    while ((idx = this.buffer.indexOf("\n")) !== -1) {
      let line = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line === "") {
        this._handleFrameEnd();
      } else {
        this.frame.push(line);
      }
    }
  }

  flush() {
    if (this.buffer) {
      let line = this.buffer;
      this.buffer = "";
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line !== "") this.frame.push(line);
    }
    if (this.frame.length) this._handleFrameEnd();
    this._flushBufferedThinking();
    this._closeActiveTextBlock();
  }

  _handleFrameEnd() {
    if (this.frame.length === 0) return;
    const lines = this.frame;
    this.frame = [];

    let eventName = null;
    const dataParts = [];
    for (const l of lines) {
      if (l.startsWith("event:")) eventName = l.slice(6).trim();
      else if (l.startsWith("data:")) dataParts.push(l.slice(5).replace(/^ /, ""));
    }
    if (dataParts.length === 0) {
      this._emitLines(lines);
      return;
    }

    const data = dataParts.join("\n");
    if (data === "[DONE]") {
      this._flushBufferedThinking();
      this._closeActiveTextBlock();
      this._emitLines(lines);
      return;
    }

    let obj = null;
    try {
      obj = JSON.parse(data);
    } catch {
      this._emitLines(lines);
      return;
    }

    const type = obj.type;
    const index = obj.index;

    // 1. content_block_start
    if (type === "content_block_start") {
      const cb = obj.content_block || {};

      if (cb.type === "thinking") {
        this._flushBufferedThinking();
        this.bufferedThinking = {
          origIndex: index,
          text: "",
          startEventName: eventName,
          startObj: obj,
          deltaFrames: []
        };
        return;
      }

      this._flushBufferedThinking();

      if (cb.type === "text") {
        if (this.activeTextBlock) {
          this.activeTextBlock.origIndices.add(index);
          this.mergedTextFragmentCount++;
          return;
        }
        const downstreamIndex = this.downstreamNextIndex++;
        this.activeTextBlock = {
          downstreamIndex,
          origIndices: new Set([index])
        };
        const mappedObj = Object.assign({}, obj, { index: downstreamIndex });
        this._emitEvent(mappedObj, eventName);
        return;
      }

      this._closeActiveTextBlock();
      const downstreamIndex = this.downstreamNextIndex++;
      this.blockIndexMap.set(index, downstreamIndex);
      const mappedObj = Object.assign({}, obj, { index: downstreamIndex });
      this._emitEvent(mappedObj, eventName);
      return;
    }

    // 2. content_block_delta
    if (type === "content_block_delta") {
      const delta = obj.delta || {};

      if (this.bufferedThinking && index === this.bufferedThinking.origIndex && delta.type === "thinking_delta") {
        this.bufferedThinking.text += (typeof delta.thinking === "string" ? delta.thinking : "");
        this.bufferedThinking.deltaFrames.push({ obj, eventName });
        return;
      }

      if (delta.type === "text_delta") {
        this._flushBufferedThinking();
        if (!this.activeTextBlock) {
          const downstreamIndex = this.downstreamNextIndex++;
          this.activeTextBlock = {
            downstreamIndex,
            origIndices: new Set([index])
          };
          this._emitEvent({
            type: "content_block_start",
            index: downstreamIndex,
            content_block: { type: "text", text: "" }
          }, "content_block_start");
        } else {
          this.activeTextBlock.origIndices.add(index);
        }

        const mappedObj = Object.assign({}, obj, {
          index: this.activeTextBlock.downstreamIndex
        });
        this._emitEvent(mappedObj, eventName);
        return;
      }

      this._flushBufferedThinking();
      this._closeActiveTextBlock();
      const mappedIndex = this.blockIndexMap.has(index) ? this.blockIndexMap.get(index) : index;
      const mappedObj = Object.assign({}, obj, { index: mappedIndex });
      this._emitEvent(mappedObj, eventName);
      return;
    }

    // 3. content_block_stop
    if (type === "content_block_stop") {
      if (this.bufferedThinking && index === this.bufferedThinking.origIndex) {
        const bt = this.bufferedThinking;
        this.bufferedThinking = null;
        if (!bt.text || bt.text.trim() === "") {
          this.droppedEmptyThinkingCount++;
          this.logFn({ type: "empty_thinking_block_dropped", index: bt.origIndex, text_len: bt.text.length });
          return;
        }
        this._closeActiveTextBlock();
        const downstreamIndex = this.downstreamNextIndex++;
        this.blockIndexMap.set(bt.origIndex, downstreamIndex);

        this._emitEvent(Object.assign({}, bt.startObj, { index: downstreamIndex }), bt.startEventName);
        for (const df of bt.deltaFrames) {
          this._emitEvent(Object.assign({}, df.obj, { index: downstreamIndex }), df.eventName);
        }
        this._emitEvent(Object.assign({}, obj, { index: downstreamIndex }), eventName);
        return;
      }

      if (this.activeTextBlock && this.activeTextBlock.origIndices.has(index)) {
        return;
      }

      this._flushBufferedThinking();
      this._closeActiveTextBlock();
      const mappedIndex = this.blockIndexMap.has(index) ? this.blockIndexMap.get(index) : index;
      this._emitEvent(Object.assign({}, obj, { index: mappedIndex }), eventName);
      return;
    }

    // 4. message_delta / message_stop / other events
    this._flushBufferedThinking();
    this._closeActiveTextBlock();
    this._emitEvent(obj, eventName);
  }

  _flushBufferedThinking() {
    if (!this.bufferedThinking) return;
    const bt = this.bufferedThinking;
    this.bufferedThinking = null;
    if (!bt.text || bt.text.trim() === "") {
      this.droppedEmptyThinkingCount++;
      this.logFn({ type: "empty_thinking_block_dropped", index: bt.origIndex, text_len: bt.text.length });
      return;
    }
    this._closeActiveTextBlock();
    const downstreamIndex = this.downstreamNextIndex++;
    this.blockIndexMap.set(bt.origIndex, downstreamIndex);
    this._emitEvent(Object.assign({}, bt.startObj, { index: downstreamIndex }), bt.startEventName);
    for (const df of bt.deltaFrames) {
      this._emitEvent(Object.assign({}, df.obj, { index: downstreamIndex }), df.eventName);
    }
    this._emitEvent({ type: "content_block_stop", index: downstreamIndex }, "content_block_stop");
  }

  _closeActiveTextBlock() {
    if (!this.activeTextBlock) return;
    const tb = this.activeTextBlock;
    this.activeTextBlock = null;
    this._emitEvent({
      type: "content_block_stop",
      index: tb.downstreamIndex
    }, "content_block_stop");
  }

  _emitEvent(obj, eventName) {
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

module.exports = { StreamThinkingFilter };
