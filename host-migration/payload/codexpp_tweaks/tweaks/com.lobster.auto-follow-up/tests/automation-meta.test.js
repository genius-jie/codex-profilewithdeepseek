const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");

const sourcePath = path.resolve(__dirname, "..", "automation.js");
const source = fs.readFileSync(sourcePath, "utf8");

class FakeElement {
  constructor({ tagName = "DIV", className = "", dataset = {}, textContent = "", attributes = {}, inComposer = false } = {}) {
    this.tagName = tagName;
    this.className = className;
    this.dataset = dataset;
    this.textContent = textContent;
    this.attributes = attributes;
    this.inComposer = inComposer;
    this.disabled = false;
    this.value = "";
    this.events = [];
    this.style = { visibility: "visible", display: "block" };
  }

  getBoundingClientRect() {
    return { width: 120, height: 24, x: 0 };
  }

  getAttribute(name) {
    return this.attributes[name] || null;
  }

  closest(selector) {
    return this.inComposer && String(selector).includes("composer") ? this : null;
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  dispatchEvent(event) {
    this.events.push(event.type);
    return true;
  }

  focus() {}
}

const fakeDocument = {
  addEventListener() {},
  removeEventListener() {},
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
};

const fakeWindow = {
  location: { pathname: "", hash: "", search: "", href: "" },
  crypto: webcrypto,
  addEventListener() {},
  removeEventListener() {},
};

fakeWindow.window = fakeWindow;

const sandbox = {
  window: fakeWindow,
  document: fakeDocument,
  console,
  Event,
  KeyboardEvent: function KeyboardEvent() {},
  Element: FakeElement,
  HTMLElement: FakeElement,
  crypto: webcrypto,
  getComputedStyle(node) {
    return node.style || { visibility: "visible", display: "block" };
  },
  setTimeout,
  clearTimeout,
  TextEncoder,
};

vm.runInNewContext(source, sandbox, { filename: sourcePath });

const helpers = sandbox.automation.__test;
assert.ok(helpers, "automation test helpers should be exposed");

function panelFromPayload(payload) {
  return {
    previousElementSibling: {
      textContent: `\`\`\`json\n${JSON.stringify(payload)}\n\`\`\``,
      previousElementSibling: null,
    },
    dataset: {},
    querySelectorAll() {
      return [];
    },
  };
}

function panelFromDatasetPayload(payload) {
  return {
    previousElementSibling: null,
    dataset: { followupMeta: JSON.stringify(payload) },
    querySelectorAll() {
      return [];
    },
  };
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    items: [
      {
        prompt: "Run critical verifier",
        priority: "P0",
        evidence_refs: ["AGENTS.md:117"],
        reason: "The gate marks it as the one auto continuation.",
        is_current_task_debt: false,
        confidence: 0.9,
      },
      {
        prompt: "Manual review item",
        priority: "P1",
        evidence_refs: ["AGENTS.md:121"],
        reason: "Important project continuation.",
        is_current_task_debt: false,
        confidence: 0.8,
      },
    ],
  }));
  assert.equal(meta.source, "payload");
  assert.equal(meta.taskComplete, true);
  assert.equal(JSON.stringify(meta.items.map((item) => item.priority)), JSON.stringify(["P0", "P1"]));
  const queue = helpers.selectAutoSubmitPrompts(meta);
  assert.equal(JSON.stringify(queue.items.map((item) => item.prompt)), JSON.stringify(["Run critical verifier", "Manual review item"]));
  assert.equal(queue.reason, "p0_p1_queue");
  assert.equal(queue.candidateCount, 2);
  const selection = helpers.selectAutoSubmitPrompt(meta);
  assert.equal(selection.prompt, "Run critical verifier");
  assert.equal(selection.priority, "P0");
  assert.equal(selection.reason, "p0");
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    items: [
      {
        prompt: "Validate important rollout",
        priority: "P1",
        is_current_task_debt: false,
      },
      {
        prompt: "Run urgent gate",
        priority: "P0",
        is_current_task_debt: false,
      },
      {
        prompt: "Capture follow-on evidence",
        priority: "P1",
        is_current_task_debt: false,
      },
      {
        prompt: "Nice polish",
        priority: "P2",
        is_current_task_debt: false,
      },
    ],
  }));
  const queue = helpers.selectAutoSubmitPrompts(meta);
  assert.equal(
    JSON.stringify(queue.items.map((item) => `${item.priority}:${item.prompt}`)),
    JSON.stringify([
      "P0:Run urgent gate",
      "P1:Validate important rollout",
      "P1:Capture follow-on evidence",
    ])
  );
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    items: [
      {
        prompt: "修正 runtime 飞书路由漂移到 W36",
        priority: "P1",
        is_current_task_debt: false,
      },
      {
        prompt: "  修正   runtime 飞书路由漂移到 W36  ",
        priority: "P1",
        is_current_task_debt: false,
      },
      {
        prompt: "运行 opencli lark_readonly 相关测试,确认项目证据 Lane 仍可审",
        priority: "P1",
        is_current_task_debt: false,
      },
    ],
  }));
  const queue = helpers.selectAutoSubmitPrompts(meta);
  assert.equal(
    JSON.stringify(queue.items.map((item) => item.prompt)),
    JSON.stringify([
      "修正 runtime 飞书路由漂移到 W36",
      "运行 opencli lark_readonly 相关测试,确认项目证据 Lane 仍可审",
    ])
  );
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    items: [
      {
        prompt: "Manual review item",
        priority: "P1",
        evidence_refs: ["AGENTS.md:121"],
        reason: "Important project continuation.",
        is_current_task_debt: false,
        confidence: 0.8,
      },
    ],
  }));
  const selection = helpers.selectAutoSubmitPrompt(meta);
  assert.equal(selection.prompt, "Manual review item");
  assert.equal(selection.priority, "P1");
  assert.equal(selection.reason, "p1");
  assert.equal(helpers.autoSubmitBudgetDecision(selection, {
    known: true,
    safeForP1: false,
    safeForP0: true,
    bytes: 1850000,
    maxLineChars: 60000,
  }).reason, "p1_budget_soft_limit");
  assert.equal(helpers.autoSubmitBudgetDecision(selection, {
    known: true,
    safeForP1: true,
    safeForP0: true,
    bytes: 1200000,
    maxLineChars: 60000,
  }).allowed, true);
  assert.equal(helpers.budgetPausePanelText("p1_budget_soft_limit"), "预算保护暂停(P1)");
  const budgetFiltered = helpers.filterAutoSubmitQueueByBudget([selection], {
    known: true,
    safeForP1: false,
    safeForP0: true,
    bytes: 1850000,
    maxLineChars: 60000,
  });
  assert.equal(budgetFiltered.items.length, 0);
  assert.equal(budgetFiltered.reason, "p1_budget_soft_limit");
}

{
  const meta = helpers.extractPayloadMeta(panelFromDatasetPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    created_at_ms: 1779860000000,
    items: [
      {
        prompt: "Run dataset-backed continuation",
        priority: "P0",
        is_current_task_debt: false,
      },
    ],
  }));
  assert.equal(meta.source, "payload");
  assert.equal(meta.taskComplete, true);
  assert.equal(meta.createdAtMs, 1779860000000);
  const selection = helpers.selectAutoSubmitPrompt(meta);
  assert.equal(selection.prompt, "Run dataset-backed continuation");
  assert.equal(selection.priority, "P0");
  assert.equal(selection.reason, "p0");
  assert.equal(helpers.autoSubmitBudgetDecision(selection, {
    known: true,
    safeForP1: false,
    safeForP0: true,
    bytes: 1850000,
    maxLineChars: 60000,
  }).allowed, true);
  assert.equal(helpers.autoSubmitBudgetDecision(selection, {
    known: true,
    safeForP1: false,
    safeForP0: false,
    bytes: 2100000,
    maxLineChars: 130000,
  }).reason, "p0_budget_hard_limit");
  assert.equal(helpers.budgetPausePanelText("p0_budget_hard_limit"), "预算保护暂停(P0)");
  const mixedBudget = helpers.filterAutoSubmitQueueByBudget([
    { prompt: "Run dataset-backed continuation", priority: "P0" },
    { prompt: "Manual review item", priority: "P1" },
  ], {
    known: true,
    safeForP1: false,
    safeForP0: true,
    bytes: 1850000,
    maxLineChars: 60000,
  });
  assert.equal(JSON.stringify(mixedBudget.items.map((item) => item.priority)), JSON.stringify(["P0"]));
  assert.equal(mixedBudget.blockedCount, 1);
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: true,
    items: [
      {
        prompt: "Nice polish",
        priority: "P2",
        evidence_refs: ["AGENTS.md:122"],
        reason: "Minor friction reducer.",
        is_current_task_debt: false,
        confidence: 0.7,
      },
      {
        prompt: "Background context",
        priority: "P3",
        evidence_refs: ["AGENTS.md:123"],
        reason: "Informational only.",
        is_current_task_debt: false,
        confidence: 0.6,
      },
    ],
  }));
  const selection = helpers.selectAutoSubmitPrompt(meta);
  assert.equal(selection.prompt, "");
  assert.equal(selection.reason, "no_p0_or_p1");
}

{
  const meta = helpers.extractPayloadMeta(panelFromPayload({
    codex_follow_up_candidate: true,
    task_complete: false,
    items: [
      {
        prompt: "Current task debt",
        priority: "P0",
        evidence_refs: ["AGENTS.md:121"],
        reason: "Current task is not closed.",
        is_current_task_debt: false,
        confidence: 0.8,
      },
    ],
  }));
  const selection = helpers.selectAutoSubmitPrompt(meta);
  assert.equal(selection.prompt, "");
  assert.equal(selection.reason, "task_incomplete");
}

{
  const meta = helpers.extractPayloadMeta({
    previousElementSibling: null,
    dataset: { signature: JSON.stringify({ items: ["P0:Signature only"] }) },
    querySelectorAll() {
      return [];
    },
  });
  assert.equal(meta.source, "signature");
  assert.equal(JSON.stringify(meta.items.map((item) => item.priority)), JSON.stringify(["P0"]));
  assert.equal(helpers.selectAutoSubmitPrompt(meta).reason, "unstructured_payload");
}

async function runRuntimeSmoke() {
  const panel = new FakeElement({
    dataset: {
      followupMeta: JSON.stringify({
        codex_follow_up_candidate: true,
        task_complete: true,
        items: [
          { prompt: "Queue first P1", priority: "P1", is_current_task_debt: false },
          { prompt: "Queue second P1", priority: "P1", is_current_task_debt: false },
        ],
      }),
    },
  });
  const textarea = new FakeElement({
    tagName: "TEXTAREA",
    attributes: { "aria-label": "Message" },
    inComposer: true,
  });
  const submitted = [];
  const sendButton = new FakeElement({
    tagName: "BUTTON",
    className: "bg-token-foreground",
    inComposer: true,
  });
  sendButton.click = () => {
    submitted.push(textarea.value);
  };

  fakeDocument.querySelector = () => null;
  fakeDocument.querySelectorAll = (selector) => {
    if (selector === ".soren-radar-panel") return [panel];
    if (selector === "button") return [sendButton];
    if (String(selector).includes("textarea")) return [textarea];
    return [];
  };

  let depth = 0;
  const floatingLabels = [];
  const runOptions = {
    api: {
      log: { info() {}, warn() {}, error(...args) { throw new Error(args.map(String).join(" ")); } },
      ipc: { invoke: async () => ({ known: true, safeForP0: true, safeForP1: true }) },
    },
    isAutoEnabled: true,
    maxDepth: 5,
    debounceMs: 0,
    currentDepth: 0,
    updateDepth: (nextDepth) => { depth = nextDepth; },
    updateFloatingPanel: (label) => { if (label) floatingLabels.push(label); },
    sessionKey: "019e0000-0000-7000-8000-000000000001",
  };

  sandbox.automation.run({ ...runOptions, isAiGenerating: () => true });
  sandbox.automation.run({ ...runOptions, isAiGenerating: () => false });

  await new Promise((resolve) => setTimeout(resolve, 1800));
  assert.deepEqual(submitted, ["Queue first P1", "Queue second P1"]);
  assert.equal(depth, 2);
  assert.equal(panel.dataset.autoFollowupTriggered, "true");
  assert.ok(floatingLabels.some((label) => label.includes("逐条")));

  panel.dataset = {
    followupMeta: JSON.stringify({
      codex_follow_up_candidate: true,
      task_complete: true,
      items: [
        { prompt: "Queue first P1", priority: "P1", is_current_task_debt: false },
        { prompt: "Queue second P1", priority: "P1", is_current_task_debt: false },
      ],
    }),
  };
  sandbox.automation.run({
    ...runOptions,
    currentDepth: depth,
    isAiGenerating: () => false,
  });
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.deepEqual(submitted, ["Queue first P1", "Queue second P1"]);
  assert.equal(depth, 2);

  const freshPanel = new FakeElement({
    dataset: {
      followupMeta: JSON.stringify({
        codex_follow_up_candidate: true,
        task_complete: true,
        created_at_ms: Date.now(),
        items: [
          { prompt: "Queue fresh P1 after return", priority: "P1", is_current_task_debt: false },
        ],
      }),
    },
  });
  fakeDocument.querySelectorAll = (selector) => {
    if (selector === ".soren-radar-panel") return [freshPanel];
    if (selector === "button") return [sendButton];
    if (String(selector).includes("textarea")) return [textarea];
    return [];
  };
  sandbox.automation.run({
    ...runOptions,
    sessionKey: "019e0000-0000-7000-8000-000000000002",
    currentDepth: 0,
    isAiGenerating: () => false,
  });
  await new Promise((resolve) => setTimeout(resolve, 1800));
  assert.deepEqual(submitted, ["Queue first P1", "Queue second P1", "Queue fresh P1 after return"]);
  assert.equal(freshPanel.dataset.autoFollowupTriggered, "true");

  const oldPanel = new FakeElement({
    dataset: {
      followupMeta: JSON.stringify({
        codex_follow_up_candidate: true,
        task_complete: true,
        created_at_ms: Date.now() - (11 * 60 * 1000),
        items: [
          { prompt: "Queue old P1 under session switch", priority: "P1", is_current_task_debt: false },
        ],
      }),
    },
  });
  fakeDocument.querySelectorAll = (selector) => {
    if (selector === ".soren-radar-panel") return [oldPanel];
    if (selector === "button") return [sendButton];
    if (String(selector).includes("textarea")) return [textarea];
    return [];
  };
  sandbox.automation.run({
    ...runOptions,
    sessionKey: "019e0000-0000-7000-8000-000000000003",
    currentDepth: 0,
    isAiGenerating: () => false,
  });
  await new Promise((resolve) => setTimeout(resolve, 1800));
  assert.deepEqual(submitted, [
    "Queue first P1",
    "Queue second P1",
    "Queue fresh P1 after return",
    "Queue old P1 under session switch",
  ]);
  assert.equal(oldPanel.dataset.autoFollowupTriggered, "true");
}

runRuntimeSmoke()
  .then(() => {
    console.log("automation-meta.test.js: PASS");
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
