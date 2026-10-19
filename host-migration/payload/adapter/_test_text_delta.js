// Test text delta handling
const { EmptyThinkingFilter } = require("@@SANITIZER_ROOT:forward@@/deepseek-thinking-filter-proxy.js");

const output = [];
const filter = new EmptyThinkingFilter((chunk) => output.push(chunk));

function send(obj, event) {
  const lines = [];
  if (event) lines.push("event: " + event);
  lines.push("data: " + JSON.stringify(obj));
  lines.push("");
  filter.push(lines.join("\r\n") + "\r\n");
}

// Simulate: 1 empty thinking + text block with multiple deltas
send({ type: "content_block_start", index: 0, content_block: { type: "thinking" } });
send({ type: "content_block_delta", index: 0, delta: { type: "thinking_delta", thinking: "" } });
send({ type: "content_block_stop", index: 0 });

// Text block at index 1
send({ type: "content_block_start", index: 1, content_block: { type: "text", text: "" } });

// Multiple text deltas (simulating cc-switch behavior)
send({ type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "你好" } });
send({ type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "！我很" } });
send({ type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "乐意帮忙" } });
send({ type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "。不过" } });

send({ type: "content_block_stop", index: 1 });
filter.flush();

console.log("=== Output ===");
const raw = output.join("");
console.log(raw);

// Parse and count text deltas
const frames = raw.split("\n\n").filter(Boolean);
let textDeltaCount = 0;
let textContent = "";
for (const frame of frames) {
  const lines = frame.split("\n");
  for (const l of lines) {
    if (l.startsWith("data: ")) {
      try {
        const obj = JSON.parse(l.slice(6));
        if (obj.type === "content_block_delta" && obj.delta && obj.delta.type === "text_delta") {
          textDeltaCount++;
          textContent += obj.delta.text;
          console.log(`Delta ${textDeltaCount}: index=${obj.index}, text="${obj.delta.text}"`);
        }
      } catch {}
    }
  }
}

console.log(`\nTotal text deltas: ${textDeltaCount}`);
console.log(`Accumulated text: "${textContent}"`);
