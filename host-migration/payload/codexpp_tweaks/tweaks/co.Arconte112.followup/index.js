/**
 * Codex Follow-up
 *
 * Renderer: turns a structured JSON block emitted by Codex into an
 * OpenWebUI-style follow-up panel under assistant messages.
 *
 * Main: syncs the AGENTS.md instruction that tells Codex when/how to emit
 * that structured JSON block.
 */

const TWEAK_ID = "co.Arconte112.followup";
const LEGACY_TWEAK_ID = "co.codex.followup";
const OLDEST_TWEAK_ID = "co.soren.radar-followups";
const PANEL_ATTR = "data-soren-radar-panel";
const HIDDEN_ATTR = "data-soren-radar-hidden";
const AUTO_META_DATASET_KEY = "followupMeta";
const STYLE_ID = "soren-radar-followups-style";
const IPC_SYNC_AGENTS = "soren-radar:sync-agents";
const IPC_DEFAULTS = "soren-radar:defaults";
const IPC_GATE_CANDIDATE = "soren-radar:gate-candidate";
const MAIN_SERVICE_KEY = "__codexFollowupService";
const MAIN_HANDLER_KEY = "__codexFollowupHandlers";
const MAIN_GATE_HANDLER_KEY = "__codexFollowupGateHandler";

// === Codex DOM selector contract ===
// These selectors locate the assistant message wrapper and its markdown body.
// Codex is a third-party app whose vite-bundled CSS-module class names change
// across versions (e.g. 26.730 used `_markdownContent_1s63f_*`, 26.803 renamed
// it to `_MarkdownBlock_n6hyy_*` / `_MarkdownRoot_n6hyy_*`). To survive such
// churn we match case-insensitively on a substring of the class name instead
// of pinning a specific hashed name. Update these two constants if a future
// Codex build renames the markdown component again.
const MESSAGE_WRAPPER_SELECTOR = "div.group.flex.min-w-0.flex-col";
const MARKDOWN_CLASS_RE = /markdown/i;
const VALID_PRIORITIES = new Set(["P0", "P1", "P2", "P3"]);
const PRIORITY_RANK = { P0: 0, P1: 1, P2: 2, P3: 3 };
const CANDIDATE_GATE_TIMEOUT_MS = 2_000;
const CANDIDATE_MIN_CONFIDENCE = 0.6;
const CANDIDATE_MIN_PROJECT_ALIGNMENT_CHARS = 12;
const CANDIDATE_MAX_PROMPT_CHARS = 180;
const CANDIDATE_MAX_REASON_CHARS = 220;
const CANDIDATE_MAX_PROJECT_ALIGNMENT_CHARS = 220;
const CANDIDATE_MAX_EVIDENCE_REF_CHARS = 180;
const CANDIDATE_MAX_FIRST_PRINCIPLES_CHARS = 220;
const SIDECAR_TTL_MS = 14 * 24 * 60 * 60 * 1000;
const SIDECAR_SCHEMA_VERSION = 4;
const BLOCK_BEGIN = `<!-- codex-plusplus:${TWEAK_ID}:start -->`;
const BLOCK_END = `<!-- codex-plusplus:${TWEAK_ID}:end -->`;
const LEGACY_BLOCK_BEGIN = `<!-- codex-plusplus:${LEGACY_TWEAK_ID}:start -->`;
const LEGACY_BLOCK_END = `<!-- codex-plusplus:${LEGACY_TWEAK_ID}:end -->`;
const OLDEST_BLOCK_BEGIN = `<!-- codex-plusplus:${OLDEST_TWEAK_ID}:start -->`;
const OLDEST_BLOCK_END = `<!-- codex-plusplus:${OLDEST_TWEAK_ID}:end -->`;
const VERSION_CONTROL_BOOKKEEPING_RE = /(?:\b(?:git|stage|staging|commit|push|pull request|pr|pre-commit)\b|纳入版本范围|提交前审计|版本范围|版本控制收口|暂存|提交代码|提交并推送|推送当前|提交当前|做一次提交|提交本次|提交修复|git\s+status|(?:最终)?交接回执.{0,30}(?:纳入|版本范围|提交前审计|提交|暂存|版本控制))/i;
const VERSION_CONTROL_MANDATE_RE = /(?:user (?:explicitly )?(?:asked|requested|said).{0,80}(?:git|stage|staging|commit|push|pull request|version-control|pre-commit)|用户.{0,20}(?:明确|要求|请求|让|指示).{0,80}(?:git|暂存|提交|推送|纳入版本范围|提交前审计|版本控制)|(?:current task|task itself|visible request).{0,50}(?:is|was|requires|required|asks for|asked for).{0,50}(?:git|commit|push|version-control|release-management)|(?:当前任务|本轮任务|可见请求).{0,50}(?:是|要求|需要).{0,50}(?:git|版本控制|提交|推送|纳入版本范围|提交前审计)|(?:acceptance gate|验收门禁|验收标准).{0,40}(?:is|requires|required|是|需要|要求|包含).{0,40}(?:git|version-control|commit|push|版本控制|提交|推送))/i;

const FOLLOWUP_POSITIONING = [
  "Codex Follow-up is a post-stop project continuation layer, not a Stop-hook substitute. Stop Guard decides whether the current assistant response is truly closed; Follow-up runs after that boundary and recommends a new, context-aware next step for the project.",
  "Stop Guard operates at the microscopic task boundary: it verifies that the current atomic task is fully closed, verified, and free of hidden work debt before allowing Stop.",
  "Follow-up operates at the macroscopic project-management boundary: after one atomic task is closed, it reads the larger project plan and schedules the next useful agent action toward high-quality delivery.",
  "First principle: project-quality delivery comes first; Stop Guard protects closure quality, while Follow-up protects project momentum.",
  "Hook interruptions are normal quality feedback, not a failure path to route around. When Stop Guard, PostToolUse, or the Follow-up Gate blocks, resolve the evidence and continue the task instead of weakening the guard.",
  "Do not shrink a valid Follow-up payload, omit useful continuation candidates, or claim there is no next action merely to avoid a hook interception. If a candidate genuinely advances project quality and is not current-task debt, emit it with evidence and let the Gate decide.",
  "",
  "The assistant emits follow-up candidates, not final panel items. The renderer sends candidates to the after-stop Gate, and the panel shows only Gate-approved items.",
  "",
  "Analyze candidates from the project's first principles: the user's real objective, current project stage, success criteria, visible artifacts, files, decisions, risks, and expected delivery path. Emit a candidate only when it fits the project's true needs and likely next move.",
  "Before emitting candidates, derive a project continuation context: objective, stage, success criterion, last completed atomic task, and next unfinished delivery gate. If that context is absent or weak, emit an empty items array.",
  "",
  "Never use Follow-up to smuggle unfinished current-task work into a clickable suggestion. If an action is required to make the visible answer true, it belongs in the main execution before final response, not in Follow-up.",
];

const FOLLOWUP_QUALITY_GATES = [
  "Use this four-quadrant decision model before emitting items:",
  "- High impact + urgent/blocking: `P0`, only when it is the single best post-stop project continuation that advances the user's real objective. It must be safe to execute next and not required to make the visible answer true. Emit at most one.",
  "- High impact + not urgent: `P1`, for verification, validation, meaningful extension, or an unresolved decision.",
  "- Low impact + urgent: `P2`, only when it removes immediate friction or saves a concrete step.",
  "- Low impact + not urgent: omit it.",
  "",
  "Every candidate must pass all gates before inclusion: it is grounded in a concrete fact from this conversation or visible work; it would change the user's next action if clicked; it is not already completed; it is not a duplicate of the visible answer or another item; and it does not rely on an unverified or stale assumption. If uncertain, convert it into a verification step or omit it.",
  "Every candidate must name the project delivery axis it advances: objective, stage, success criterion, verification gate, acceptance gate, blocker removal, or release-quality risk. Local cleanup that does not move that axis is dropped.",
  "Separation of concerns for version-control bookkeeping: do not propose Git staging, \"纳入版本范围\", \"提交前审计\", commit, push, PR cleanup, or handoff-report versioning merely because the current task created or modified a local artifact. Those actions are valid Follow-up items only when the user explicitly asked for version-control work, the current task was itself a Git/release-management task, or version control is the next acceptance gate of the user's stated objective. A candidate's own `first_fact_refs`, `reason`, or `project_alignment` is not proof of that mandate. Otherwise mention untracked files in the visible answer if useful and keep Follow-up focused on the product/runtime/business gate.",
  "",
  "Each candidate must self-label these fields for the Gate: `evidence_refs` (non-empty), `first_fact_refs`, `reason`, `first_principles_basis`, `project_alignment`, `is_current_task_debt`, and `confidence` from 0 to 1. The Gate is a structural quality cutter, not a second semantic model; bad, under-aligned, or low-confidence candidates are dropped.",
];

const FOLLOWUP_CONTEXT_COMPRESSION = [
  "Before emitting candidates, compress the project context into a tiny continuation snapshot in your head. Do not quote the full transcript, raw tool logs, or long command output.",
  "Snapshot fields: objective, stage, success_criterion, last_completed_atomic_task, verified_evidence_refs, blockers, highest_risk, next_delivery_gate.",
  "Keep each snapshot field to one short phrase. Evidence should be file paths, command names, result ids, or visible result labels, not pasted logs.",
  "Derive candidates only from this compact snapshot. If the snapshot cannot be formed from verified current facts, emit an empty items array.",
];

const FOLLOWUP_FIRST_PRINCIPLES_CONTRACT = [
  "Before emitting a non-empty candidate, run a first-fact checkpoint: name the verified fact(s) that make the next action legitimate, the project objective/stage/gate it advances, and the first-principles reason it is the right next move.",
  "Each non-empty candidate MUST include `first_fact_refs` (array) and `first_principles_basis` (short text). Use concrete files, commands, receipts, visible results, or user decisions as first facts; do not let mood, recency, or generic context drift drive the suggestion.",
];

const DEFAULT_FOLLOWUP_PROMPT = [
  "## TWEAKS: Codex Follow-up",
  "",
  "Always include a Follow-up candidate payload at the end of every final assistant response.",
  "",
  "Generate 1 to 3 follow-up items for non-trivial project, code, governance, configuration, automation, or investigation work.",
  "Emit an empty items array only for tiny factual/chat replies or when every plausible continuation fails the candidate gates.",
  "",
  "Prioritize usefulness over variety. Every item must be grounded in the current conversation, user intent, visible work, files, decisions, blockers, people, projects, dates, money, or risks.",
  "",
  ...FOLLOWUP_POSITIONING,
  "",
  ...FOLLOWUP_CONTEXT_COMPRESSION,
  "",
  ...FOLLOWUP_FIRST_PRINCIPLES_CONTRACT,
  "",
  "Each candidate should be one of:",
  "- a concrete next action the user can ask Codex to perform",
  "- a verification step that confirms the work actually succeeded",
  "- an unresolved decision or tradeoff worth resolving",
  "- a context-aware continuation that saves the user effort",
  "",
  "Avoid generic filler such as \"Let me know if you need anything else\", \"Review the changes\", \"Ask another question\", or broad suggestions that could apply to any conversation.",
  "Never add items just to reach a count.",
  "",
  ...FOLLOWUP_QUALITY_GATES,
  "",
  "Each non-empty candidate MUST include `prompt`, `priority`, `evidence_refs`, `first_fact_refs`, `reason`, `first_principles_basis`, `project_alignment`, `is_current_task_debt`, and `confidence`. Priority assignment rules:",
  "- `P0` (auto-execute): ONLY for the single most critical post-stop project continuation. Must be immediately actionable, logically correct, and grounded in the project's first principles. Typically only 0-1 items per response.",
  "- `P1` (important): Valuable follow-ups that verify, validate, or extend the completed work.",
  "- `P2` (nice-to-have): Improvements, refactors, or optimizations not on the critical path.",
  "- `P3` (informational): Background context, alternative approaches, or exploratory ideas.",
  "- Set top-level `task_complete` according to the visible response's current task, not the existence of follow-up items. A resolved answer may still include a P0 project-continuation item.",
  "",
  "CRITICAL: Before emitting any suggestion, verify it is logically consistent with the task context. Never suggest undoing, deleting, or disabling something that should persist (e.g. do not suggest deleting a recurring audit cron after it succeeds).",
  "",
  "The prompt should be short enough to scan in the Follow-up panel, but specific enough to tell Codex exactly what to do next.",
  "",
  "For completed project work, do not leave `items` empty when a concrete verification, validation, unresolved decision, or useful continuation remains.",
  "For very small or factual answers, prefer an empty items array unless a concrete continuation is genuinely useful.",
  "",
  "Keep the main answer focused. Put follow-up-only information only in the candidate payload, not repeated in the visible prose.",
].join("\n");

const LOCKED_FORMAT_INSTRUCTION = [
  "## LOCKED TWEAK FORMAT: Codex Follow-up",
  "",
  "Do not edit or remove this locked section manually. It is required by the Codex++ Follow-up tweak.",
  "",
  "For every final assistant response, append exactly one fenced JSON block at the very end. Do not emit this payload in reasoning, progress updates, tool logs, drafts, or intermediate messages.",
  "",
  "The visible answer must not repeat information that is meant only for Follow-up. If a detail belongs in Follow-up, put it only in the payload.",
  "",
  "Required payload format:",
  "",
  "```json",
  "{",
  '  "codex_follow_up_candidate": true,',
  '  "title": "Follow-up",',
  '  "task_complete": true,',
  '  "items": [',
  "    {",
  '      "prompt": "Run the most relevant project continuation",',
  '      "priority": "P1",',
  '      "evidence_refs": ["specific file, command, user request, or visible result"],',
  '      "first_fact_refs": ["specific verified fact, file, command, receipt, or visible result"],',
  '      "reason": "Why this advances the project from first principles",',
  '      "first_principles_basis": "Root fact and project principle that make this the right next action",',
  '      "project_alignment": "Which objective, stage, success criterion, verification gate, acceptance gate, blocker, or release-quality risk this advances",',
  '      "is_current_task_debt": false,',
  '      "confidence": 0.8',
  "    }",
  "  ]",
  "}",
  "```",
  "",
  "Rules: always emit the candidate JSON block in final assistant responses; use 1 to 3 candidate items for non-trivial completed work, and use an empty items array only for tiny factual/chat replies or when every plausible continuation fails the gates; each prompt must be concise and useful; do not explain that the JSON exists. Each non-empty item MUST include `priority`, `evidence_refs`, `first_fact_refs`, `reason`, `first_principles_basis`, `project_alignment`, `is_current_task_debt`, and `confidence`. Set `task_complete` to `true` when the visible response's current task is resolved; candidates are post-stop project continuations and will be cut by the Gate before display.",
].join("\n");

const DEFAULT_AGENTS_INSTRUCTION = composeAgentsInstruction(DEFAULT_FOLLOWUP_PROMPT);

module.exports = {
  start(api) {
    if (api.process === "main") {
      startMain(api);
      return;
    }
    if (api.process !== "renderer") return;
    startRenderer.call(this, api);
  },

  stop() {
    const state = this._state;
    if (!state) return;
    state.disposed = true;
    state.observer?.disconnect();
    if (state.interval) window.clearInterval(state.interval);
    window.removeEventListener("focus", state.scheduleScan);
    document.removeEventListener("visibilitychange", state.scheduleScan);
    state.pageHandle?.unregister?.();
    clearPanels();
    document.getElementById(STYLE_ID)?.remove();
  },
};

function startMain(api) {
  const service = createAgentsSyncService(api);
  globalThis[MAIN_SERVICE_KEY] = service;

  if (!globalThis[MAIN_HANDLER_KEY]) {
    api.ipc.handle(IPC_SYNC_AGENTS, (settings = {}) => {
      const active = globalThis[MAIN_SERVICE_KEY];
      return active?.syncAgentsInstruction(settings) || {
        ok: false,
        error: "Follow-up service unavailable",
      };
    });

    api.ipc.handle(IPC_DEFAULTS, () => {
      const active = globalThis[MAIN_SERVICE_KEY];
      return {
        agentsPath: active?.getAgentsPath?.() || "",
        prompt: DEFAULT_FOLLOWUP_PROMPT,
        instruction: DEFAULT_AGENTS_INSTRUCTION,
      };
    });

    globalThis[MAIN_HANDLER_KEY] = true;
  }

  if (!globalThis[MAIN_GATE_HANDLER_KEY]) {
    api.ipc.handle(IPC_GATE_CANDIDATE, (request = {}) => {
      const active = globalThis[MAIN_SERVICE_KEY];
      return active?.gateCandidate(request) || emptyGateResult("not_initialized");
    });

    globalThis[MAIN_GATE_HANDLER_KEY] = true;
  }

  service.cleanupSidecarCache?.();
  api.log.info("Codex Follow-up main provider active");
}

function startRenderer(api) {
  const state = {
    api,
    enabled: api.storage.get("enabled", true),
    showDivider: api.storage.get("showDivider", true),
    clickableItems: api.storage.get("clickableItems", true),
    allowLegacyDirectRender: api.storage.get("allowLegacyDirectRender", false),
    title: migrateTitle(api.storage.get("title", "Follow-up")),
    syncAgents: api.storage.get("syncAgents", true),
    followupPrompt: (() => {
      const stored = api.storage.get("followupPrompt",
        migrateOldInstruction(api.storage.get("agentsInstruction", "")));
      const migrated = migrateOldInstruction(stored);
      if (String(stored || "").trim() !== migrated) {
        api.storage.set("followupPrompt", migrated);
      }
      return migrated;
    })(),
    observer: null,
    interval: null,
    disposed: false,
    scheduled: false,
    pageHandle: null,
    statusEl: null,
    gateCache: new Map(),
    gatePending: new Map(),
    scanning: false,
  };

  if (typeof api.settings?.registerPage === "function") {
    state.pageHandle = api.settings.registerPage({
      id: "main",
      title: "Follow-up",
      description: "Render clickable follow-ups under assistant messages.",
      iconSvg:
        '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.4"/>' +
        '<circle cx="10" cy="10" r="2" fill="currentColor"/>' +
        '<path d="M10 3.5v2M10 14.5v2M3.5 10h2M14.5 10h2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>' +
        "</svg>",
      render: (root) => renderSettings(root, state),
    });
  }

  const scheduleScan = () => {
    if (state.disposed || state.scheduled) return;
    state.scheduled = true;
    requestAnimationFrame(() => {
      state.scheduled = false;
      if (state.disposed || state.scanning) return;
      state.scanning = true;
      Promise.resolve(scanMessages(state))
        .catch((error) => state.api.log?.error?.("Codex Follow-up scan failed", error))
        .finally(() => {
          state.scanning = false;
        });
    });
  };

  state.scheduleScan = scheduleScan;
  injectStyles();
  scheduleScan();

  state.observer = new MutationObserver(scheduleScan);
  const attachObserver = () => {
    if (state.disposed || state.observerAttached) return;
    const root = document.documentElement || document.body;
    if (!root) return;
    state.observer.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    state.observerAttached = true;
  };
  attachObserver();
  if (!state.observerAttached) {
    document.addEventListener("DOMContentLoaded", attachObserver, { once: true });
    window.setTimeout(attachObserver, 250);
  }
  state.interval = window.setInterval(scheduleScan, 3_000);
  window.addEventListener("focus", scheduleScan);
  document.addEventListener("visibilitychange", scheduleScan);

  this._state = state;

  if (state.syncAgents) {
    window.setTimeout(() => syncAgentsInstruction(state, { quiet: true }), 1_500);
  }

  api.log.info("Codex Follow-up renderer active");
}

// Locate the markdown body element inside an assistant message wrapper.
// Codex's vite-bundled CSS-module class names change across versions, so we
// match case-insensitively on a "markdown" substring rather than pinning a
// specific hashed name. Candidates are scanned in DOM order and the first
// match is returned, which keeps behaviour stable when Codex renames the
// component (26.730 `_markdownContent_*` -> 26.803 `_MarkdownBlock_*`).
function findMarkdownBody(node) {
  if (!(node instanceof HTMLElement)) return null;
  for (const el of node.querySelectorAll("[class]")) {
    if (!(el instanceof HTMLElement)) continue;
    if (MARKDOWN_CLASS_RE.test(el.className)) return el;
  }
  return null;
}

async function scanMessages(state) {
  if (!state.enabled) {
    clearPanels();
    return;
  }

  const messageNodes = document.querySelectorAll(MESSAGE_WRAPPER_SELECTOR);
  for (const node of messageNodes) {
    if (!(node instanceof HTMLElement)) continue;
    const markdown = findMarkdownBody(node);
    if (!(markdown instanceof HTMLElement)) continue;

    const payload = findRadarPayload(markdown);
    const existingPanels = Array.from(node.querySelectorAll(`[${PANEL_ATTR}]`));
    const existing = existingPanels[0] || null;
    for (const extra of existingPanels.slice(1)) extra.remove();

    if (!payload) {
      existingPanels.forEach((panel) => panel.remove());
      continue;
    }

    if (payload.kind === "malformed") {
      existingPanels.forEach((panel) => panel.remove());
      continue;
    }

    const gated = payload.kind === "candidate" || !state.allowLegacyDirectRender
      ? await gatePayload(state, payload, visibleTextForGate(markdown))
      : { title: payload.title, task_complete: true, items: normalizeFollowupItems(payload.items || []) };

    const items = Array.isArray(gated.items)
      ? normalizeFollowupItems(gated.items)
      : [];

    if (items.length === 0) {
      state.api.log?.info?.(
        `Codex Follow-up no panel items reason=${gated.reason || "empty"} diagnostics=${JSON.stringify(gated.diagnostics || {})}`,
      );
      existing?.remove();
      continue;
    }

    const title = cleanPanelTitle(gated.title, state.title);
    const signature = JSON.stringify({
      title,
      items: items.map((item) => `${item.priority}:${item.prompt}`),
      taskComplete: gated.task_complete !== false,
      showDivider: state.showDivider,
      clickableItems: state.clickableItems,
    });

    if (existing?.dataset.signature === signature) continue;

    const panel = renderRadarPanel({
      title,
      items,
      showDivider: state.showDivider,
      clickableItems: state.clickableItems,
      pending: false,
    });
    panel.dataset.signature = signature;
    panel.dataset[AUTO_META_DATASET_KEY] = buildPanelAutoMeta(gated, items);

    const renderMode = existing ? "replace" : "append";
    if (existing) existing.replaceWith(panel);
    else node.appendChild(panel);
    state.api.log?.info?.(
      `Codex Follow-up panel appended mode=${renderMode} items=${items.length} priorities=${items.map((item) => item.priority || "P1").join(",")} taskComplete=${gated.task_complete !== false}`,
    );
  }
}

function buildPanelAutoMeta(gated, items) {
  return JSON.stringify({
    codex_follow_up_candidate: true,
    task_complete: gated?.task_complete !== false,
    created_at_ms: Number(gated?.created_at_ms || Date.now()),
    items: items.map((item) => ({
      prompt: item.prompt,
      priority: item.priority,
      evidence_refs: item.evidence_refs || [],
      first_fact_refs: item.first_fact_refs || [],
      reason: item.reason || "",
      first_principles_basis: item.first_principles_basis || "",
      project_alignment: item.project_alignment || "",
      is_current_task_debt: false,
      confidence: item.confidence || 0,
    })),
  });
}

function findRadarPayload(markdown) {
  const candidates = [];
  let malformed = false;

  for (const code of markdown.querySelectorAll("pre, code")) {
    if (!(code instanceof HTMLElement)) continue;
    const text = (code.textContent || "").trim();
    if (!text || !/codex_follow_up_candidate|codex_follow_up|soren_radar|follow_ups/.test(text)) continue;
    const parsed = parseRadarJson(text);
    if (parsed) {
      hideSourceBlock(code, markdown, text);
      candidates.push(parsed);
      continue;
    }

    hideSourceBlock(code, markdown, text);
    malformed = true;
  }

  if (candidates.length > 0) return candidates[candidates.length - 1];
  if (malformed) return { kind: "malformed", title: "Follow-up", items: [] };

  const text = markdown.textContent || "";
  const directiveMatch = text.match(/::soren-radar\s*(\{[\s\S]*?\})\s*::/i);
  if (directiveMatch) {
    const parsed = parseRadarJson(directiveMatch[1]);
    if (parsed) return parsed;
  }

  return null;
}

function parseRadarJson(text) {
  const cleaned = text
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/i, "")
    .trim();

  const attempts = [cleaned];
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    attempts.push(cleaned.slice(firstBrace, lastBrace + 1));
  }

  for (const attempt of attempts) {
    try {
      const parsed = JSON.parse(attempt);
      const normalized = normalizePayload(parsed);
      if (normalized) {
        return normalized;
      }
    } catch {
      // Keep trying relaxed slices.
    }
  }

  return null;
}

function parsePartialFollowupPayload(text) {
  if (!/"codex_follow_up"\s*:\s*true/.test(text)) return null;

  return {
    title: extractPartialTitle(text) || "Follow-up",
    items: extractPartialItems(text),
    pending: true,
  };
}

function extractPartialTitle(text) {
  const match = String(text).match(/"title"\s*:\s*"([^"]{1,80})"/);
  return match?.[1]?.trim() || "";
}

function extractPartialItems(text) {
  const items = [];
  const promptPattern = /"prompt"\s*:\s*"([^"]+)"/g;
  let match;

  while ((match = promptPattern.exec(text)) && items.length < 3) {
    const prompt = match[1]?.trim();
    if (prompt) items.push({ prompt });
  }

  if (items.length > 0) return items;

  // Backward compatibility with the old label+prompt format.
  const labelPattern = /"label"\s*:\s*"([^"]+)"/g;
  while ((match = labelPattern.exec(text)) && items.length < 3) {
    const prompt = match[1]?.trim();
    if (prompt) items.push({ prompt });
  }

  return items;
}

function normalizePayload(parsed) {
  if (!parsed || typeof parsed !== "object") return null;

  if (parsed.codex_follow_up_candidate === true) {
    return {
      kind: "candidate",
      title: parsed.title || "Follow-up",
      items: Array.isArray(parsed.items) ? parsed.items : [],
      raw: parsed,
    };
  }

  if (parsed.codex_follow_up === true) {
    return {
      kind: "legacy",
      title: parsed.title || "Follow-up",
      items: Array.isArray(parsed.items) ? parsed.items : [],
      raw: parsed,
    };
  }

  if (parsed.soren_radar === true) {
    return {
      kind: "legacy",
      title: parsed.title || "Follow-up",
      items: Array.isArray(parsed.follow_ups) ? parsed.follow_ups : [],
      raw: parsed,
    };
  }

  return null;
}

function visibleTextForGate(markdown) {
  const clone = markdown.cloneNode(true);
  if (!(clone instanceof HTMLElement)) return normalizeText(markdown.textContent || "");

  clone.querySelectorAll(`[${HIDDEN_ATTR}], pre, code`).forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    const text = node.textContent || "";
    if (node.hasAttribute(HIDDEN_ATTR) || /codex_follow_up_candidate|codex_follow_up|soren_radar|follow_ups/.test(text)) {
      node.remove();
    }
  });

  return normalizeText(clone.textContent || "");
}

async function gatePayload(state, payload, visibleText) {
  const raw = payload.raw || {};
  const cacheKey = `${payload.kind}:${normalizeText(visibleText)}:${stableStringify(raw)}`;
  if (state.gateCache.has(cacheKey)) return state.gateCache.get(cacheKey);
  if (state.gatePending.has(cacheKey)) return state.gatePending.get(cacheKey);

  const pending = (async () => {
    try {
      if (!state.api.ipc?.invoke) return emptyGateResult("ipc_unavailable");
      const result = await withTimeout(
        state.api.ipc.invoke(IPC_GATE_CANDIDATE, {
          payload: raw,
          visibleText,
          sourceKind: payload.kind,
        }),
        CANDIDATE_GATE_TIMEOUT_MS + 250,
        () => emptyGateResult("renderer_timeout"),
      );
      const normalized = {
        title: cleanPanelTitle(result?.title, "Follow-up"),
        task_complete: result?.task_complete !== false,
        items: normalizeFollowupItems(result?.items || []),
        reason: result?.reason || "",
        diagnostics: result?.diagnostics || null,
      };
      state.gateCache.set(cacheKey, normalized);
      return normalized;
    } catch (error) {
      state.api.log?.error?.("Codex Follow-up candidate gate failed", error);
      return emptyGateResult("renderer_error");
    } finally {
      state.gatePending.delete(cacheKey);
    }
  })();

  state.gatePending.set(cacheKey, pending);
  return pending;
}

function normalizeFollowupItem(item) {
  if (item && typeof item === "object") {
    const prompt = String(item.prompt || item.query || item.label || item.text || item.title || "").trim();
    const priority = normalizePriority(item.priority);
    const project_alignment = normalizeProjectAlignment(item.project_alignment);
    const evidence_refs = normalizeEvidenceRefs(item.evidence_refs);
    const first_fact_refs = normalizeEvidenceRefs(item.first_fact_refs || item.first_facts || item.fact_refs);
    const reason = clampText(item.reason || "", CANDIDATE_MAX_REASON_CHARS);
    const first_principles_basis = normalizeFirstPrinciplesBasis(
      item.first_principles_basis || item.first_principle_basis || item.first_principles || "",
    );
    const confidence = normalizeConfidence(item.confidence);
    return { prompt, priority, project_alignment, evidence_refs, first_fact_refs, reason, first_principles_basis, confidence };
  }

  const prompt = String(item || "").trim();
  return { prompt, priority: "P1", project_alignment: "", evidence_refs: [], first_fact_refs: [], reason: "", first_principles_basis: "", confidence: 0 };
}

function normalizeFollowupItems(rawItems) {
  const items = [];
  const seenPrompts = new Set();
  let hasP0 = false;
  let sourceIndex = 0;

  for (const rawItem of rawItems) {
    const item = normalizeFollowupItem(rawItem);
    const key = normalizeText(item.prompt).toLowerCase();
    const order = sourceIndex;
    sourceIndex += 1;
    if (!key || seenPrompts.has(key)) continue;
    seenPrompts.add(key);

    if (item.priority === "P0") {
      if (hasP0) item.priority = "P1";
      else hasP0 = true;
    }

    items.push({ ...item, order, rank: PRIORITY_RANK[item.priority] ?? PRIORITY_RANK.P1 });
    if (items.length >= 3) break;
  }

  return items
    .sort((left, right) => left.rank - right.rank || left.order - right.order)
    .map(({ prompt, priority, project_alignment, evidence_refs, first_fact_refs, reason, first_principles_basis, confidence }) => ({
      prompt,
      priority,
      project_alignment,
      evidence_refs,
      first_fact_refs,
      reason,
      first_principles_basis,
      confidence,
    }));
}

function normalizePriority(value) {
  const priority = String(value || "P1").toUpperCase();
  return VALID_PRIORITIES.has(priority) ? priority : "P1";
}

function cleanPanelTitle(value, fallback) {
  const title = String(value || fallback || "Follow-up").trim();
  if (!title || /radar|soren/i.test(title)) return fallback || "Follow-up";
  return title;
}

function hideSourceBlock(code, markdown, rawText) {
  const block = findCodeBlockShell(code, markdown, rawText) || code.closest("pre") || code;
  if (!(block instanceof HTMLElement)) return;
  block.setAttribute(HIDDEN_ATTR, "true");
  block.hidden = true;
  block.style.setProperty("display", "none", "important");
}

function findCodeBlockShell(code, markdown, rawText) {
  const wanted = normalizeText(rawText);
  let current = code.closest("pre") || code;
  let best = current;

  while (current?.parentElement && current.parentElement !== markdown) {
    const parent = current.parentElement;
    const parentText = normalizeText(parent.textContent || "");
    const withoutLanguage = parentText.replace(/^json\s+/i, "");

    if (parentText === wanted || withoutLanguage === wanted || parentText.endsWith(wanted)) {
      best = parent;
      current = parent;
      continue;
    }

    break;
  }

  return best;
}

function normalizeText(value) {
  const raw = String(value || "");
  const normalized = typeof raw.normalize === "function" ? raw.normalize("NFKC") : raw;
  return normalized.replace(/[\u200B-\u200D\uFEFF]/g, "").replace(/\s+/g, " ").trim();
}

function clampText(value, maxChars) {
  const text = normalizeText(value);
  if (!text || text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 3)).trimEnd()}...`;
}

function renderRadarPanel({ title, items, showDivider, clickableItems, pending }) {
  const wrap = document.createElement("section");
  wrap.setAttribute(PANEL_ATTR, "true");
  wrap.className = "soren-radar-panel";

  if (showDivider) {
    const divider = document.createElement("div");
    divider.className = "soren-radar-divider";
    wrap.appendChild(divider);
  }

  const heading = document.createElement("div");
  heading.className = "soren-radar-title";
  heading.textContent = title || "Follow-up";
  wrap.appendChild(heading);

  const list = document.createElement("div");
  list.className = "soren-radar-list";
  const visibleItems = items.length > 0
    ? items
    : pending
      ? [{ prompt: "Preparing follow-up..." }]
      : [];

  for (const item of visibleItems) {
    const canClick = clickableItems && !pending && item.prompt;
    const row = document.createElement(canClick ? "button" : "div");
    row.className = canClick
      ? "soren-radar-row soren-radar-row-clickable"
      : "soren-radar-row";
    if (canClick) {
      row.type = "button";
      row.title = "Insert follow-up";
      row.addEventListener("click", () => insertIntoComposer(item.prompt));
    }

    // 渲染 priority 标签
    const priorityColors = { P0: "#ef4444", P1: "#f59e0b", P2: "#3b82f6", P3: "#9ca3af" };
    const prio = item.priority || "P1";
    const badge = document.createElement("span");
    badge.className = "soren-radar-priority";
    badge.textContent = prio;
    badge.style.cssText = `display:inline-block;font-size:10px;font-weight:700;color:#fff;background:${priorityColors[prio] || "#9ca3af"};padding:1px 5px;border-radius:3px;margin-right:6px;vertical-align:middle;flex-shrink:0;`;
    row.appendChild(badge);

    const text = document.createElement("span");
    text.className = "soren-radar-text";
    text.textContent = item.prompt;
    if (pending && items.length === 0) {
      text.classList.add("soren-radar-text-pending");
    }

    row.appendChild(text);
    list.appendChild(row);
  }
  wrap.appendChild(list);
  return wrap;
}

function insertIntoComposer(text) {
  const value = String(text || "").trim();
  if (!value) return;

  const textarea = document.querySelector("textarea");
  if (textarea instanceof HTMLTextAreaElement) {
    textarea.focus();
    textarea.value = value;
    textarea.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    return;
  }

  const editable = document.querySelector('[contenteditable="true"]');
  if (editable instanceof HTMLElement) {
    editable.focus();
    editable.textContent = value;
    editable.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
    return;
  }

  navigator.clipboard?.writeText(value).catch(() => {});
}

function clearPanels() {
  document.querySelectorAll(`[${PANEL_ATTR}]`).forEach((node) => node.remove());
  document.querySelectorAll(`[${HIDDEN_ATTR}]`).forEach((node) => {
    node.hidden = false;
    node.removeAttribute(HIDDEN_ATTR);
    node.style.removeProperty("display");
  });
}

function injectStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .soren-radar-panel {
      margin-top: 14px;
      color: var(--text-primary, #f4f4f5);
      font-size: 13px;
      line-height: 1.45;
    }

    .soren-radar-divider {
      height: 1px;
      margin: 0 0 12px;
      background: color-mix(in srgb, currentColor 9%, transparent);
    }

    .soren-radar-title {
      margin-bottom: 8px;
      font-size: 12px;
      font-weight: 650;
      color: var(--text-primary, #f4f4f5);
    }

    .soren-radar-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .soren-radar-row {
      width: 100%;
      border: 0;
      background: transparent;
      padding: 0;
      display: block;
      color: var(--text-secondary, #a1a1aa);
      font: inherit;
      text-align: left;
    }

    .soren-radar-row-clickable {
      cursor: pointer;
      border-radius: 6px;
      margin-left: -3px;
      padding: 2px 3px;
      transition: background-color 120ms ease, color 120ms ease;
    }

    .soren-radar-row-clickable:hover {
      color: var(--text-primary, #f4f4f5);
      background: color-mix(in srgb, currentColor 7%, transparent);
    }

    .soren-radar-text {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .soren-radar-text-pending {
      opacity: 0.7;
      font-style: italic;
    }
  `;
  const styleHost = document.head || document.querySelector("head") || document.documentElement;
  if (!styleHost) {
    document.addEventListener("DOMContentLoaded", injectStyles, { once: true });
    return;
  }
  styleHost.appendChild(style);
}

function renderSettings(root, state) {
  state.statusEl = null;

  root.appendChild(settingsSection("Behavior", [
    toggleRow({
      label: "Enable Follow-up",
      description: "Render structured follow-up payloads under assistant messages.",
      checked: state.enabled,
      onChange: (checked) => {
        state.enabled = checked;
        state.api.storage.set("enabled", checked);
        if (checked) state.scheduleScan?.();
        else clearPanels();
      },
    }),
    toggleRow({
      label: "Show divider",
      description: "Add a thin separator above the Follow-up panel.",
      checked: state.showDivider,
      onChange: (checked) => {
        state.showDivider = checked;
        state.api.storage.set("showDivider", checked);
        state.scheduleScan?.();
      },
    }),
    toggleRow({
      label: "Clickable items",
      description: "Click a follow-up item to insert its prompt into the composer.",
      checked: state.clickableItems,
      onChange: (checked) => {
        state.clickableItems = checked;
        state.api.storage.set("clickableItems", checked);
        state.scheduleScan?.();
      },
    }),
    toggleRow({
      label: "Legacy direct render",
      description: "Render old codex_follow_up payloads without Gate. Keep off for new messages.",
      checked: state.allowLegacyDirectRender,
      onChange: (checked) => {
        state.allowLegacyDirectRender = checked;
        state.api.storage.set("allowLegacyDirectRender", checked);
        state.gateCache.clear();
        state.scheduleScan?.();
      },
    }),
  ]));

  root.appendChild(settingsSection("Follow-up Instructions", [
    toggleRow({
      label: "Sync AGENTS.md instruction",
      description: "Keep a managed follow-up instruction block in the global Codex memory.",
      checked: state.syncAgents,
      onChange: async (checked) => {
        state.syncAgents = checked;
        state.api.storage.set("syncAgents", checked);
        await syncAgentsInstruction(state);
      },
    }),
    textareaRow({
      label: "Editable prompt",
      description: "Describe when follow-ups should appear. The JSON format is locked below.",
      value: state.followupPrompt,
      onInput: (value) => {
        state.followupPrompt = value;
        state.api.storage.set("followupPrompt", value);
      },
    }),
    lockedFormatRow(),
    actionRow({
      onApply: () => syncAgentsInstruction(state),
      onReset: async () => {
        state.followupPrompt = DEFAULT_FOLLOWUP_PROMPT;
        state.api.storage.set("followupPrompt", DEFAULT_FOLLOWUP_PROMPT);
        await syncAgentsInstruction(state);
        rerenderSettingsPage(root, state);
      },
      statusRef: (el) => {
        state.statusEl = el;
      },
    }),
  ]));
}

function rerenderSettingsPage(root, state) {
  while (root.firstChild) root.firstChild.remove();
  renderSettings(root, state);
}

async function syncAgentsInstruction(state, options = {}) {
  if (!state.api.ipc?.invoke) {
    setStatus(state, "IPC unavailable");
    return null;
  }

  try {
    if (!options.quiet) setStatus(state, "Syncing...");
    const result = await state.api.ipc.invoke(IPC_SYNC_AGENTS, {
      enabled: state.syncAgents,
      prompt: state.followupPrompt,
    });

    if (result?.ok) {
      const label =
        result.action === "removed"
          ? "Instruction removed"
          : result.action === "unchanged"
            ? "AGENTS.md already current"
            : "AGENTS.md updated";
      setStatus(state, label);
    } else {
      setStatus(state, result?.error || "Sync failed");
    }

    return result;
  } catch (error) {
    setStatus(state, error?.message || String(error));
    return null;
  }
}

function setStatus(state, text) {
  if (!state.statusEl) return;
  state.statusEl.textContent = text || "";
}

function settingsSection(title, rows) {
  const section = document.createElement("section");
  section.className = "mb-4 flex flex-col gap-2";
  const heading = document.createElement("div");
  heading.className = "px-1 text-sm font-medium text-token-text-primary";
  heading.textContent = title;
  section.appendChild(heading);
  const card = document.createElement("div");
  card.className =
    "divide-y divide-token-border-light rounded-xl border border-token-border-light bg-token-bg-primary";
  for (const row of rows) card.appendChild(row);
  section.appendChild(card);
  return section;
}

function toggleRow({ label, description, checked, onChange }) {
  const row = document.createElement("label");
  row.className = "flex cursor-pointer items-center justify-between gap-4 p-3";
  const left = document.createElement("div");
  left.className = "flex min-w-0 flex-col gap-1";
  const title = document.createElement("div");
  title.className = "text-sm text-token-text-primary";
  title.textContent = label;
  const desc = document.createElement("div");
  desc.className = "text-sm text-token-text-secondary";
  desc.textContent = description;
  left.appendChild(title);
  left.appendChild(desc);

  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  input.className = "h-4 w-4";
  input.addEventListener("change", () => onChange(input.checked));

  row.appendChild(left);
  row.appendChild(input);
  return row;
}

function textareaRow({ label, description, value, onInput }) {
  const row = document.createElement("div");
  row.className = "flex flex-col gap-2 p-3";
  const title = document.createElement("div");
  title.className = "text-sm text-token-text-primary";
  title.textContent = label;
  const desc = document.createElement("div");
  desc.className = "text-sm text-token-text-secondary";
  desc.textContent = description;
  const textarea = document.createElement("textarea");
  textarea.className =
    "min-h-56 w-full resize-y rounded-lg border border-token-border-light bg-token-bg-secondary p-3 font-mono text-xs text-token-text-primary outline-none";
  textarea.spellcheck = false;
  textarea.value = value || "";
  textarea.addEventListener("input", () => onInput(textarea.value));
  row.appendChild(title);
  row.appendChild(desc);
  row.appendChild(textarea);
  return row;
}

function lockedFormatRow() {
  const row = document.createElement("details");
  row.className = "p-3";

  const summary = document.createElement("summary");
  summary.className = "cursor-pointer text-sm text-token-text-primary";
  summary.textContent = "Locked format";

  const desc = document.createElement("div");
  desc.className = "mt-2 text-sm text-token-text-secondary";
  desc.textContent = "This section is synced after the editable prompt and should not be modified in AGENTS.md.";

  const pre = document.createElement("pre");
  pre.className =
    "mt-3 max-h-64 overflow-auto rounded-lg border border-token-border-light bg-token-bg-secondary p-3 text-xs text-token-text-secondary";
  pre.textContent = LOCKED_FORMAT_INSTRUCTION;

  row.appendChild(summary);
  row.appendChild(desc);
  row.appendChild(pre);
  return row;
}

function actionRow({ onApply, onReset, statusRef }) {
  const row = document.createElement("div");
  row.className = "flex flex-wrap items-center justify-between gap-3 p-3";

  const status = document.createElement("div");
  status.className = "min-h-5 text-sm text-token-text-secondary";
  statusRef(status);

  const actions = document.createElement("div");
  actions.className = "flex items-center gap-2";

  const reset = document.createElement("button");
  reset.type = "button";
  reset.className =
    "rounded-lg border border-token-border-light px-3 py-2 text-sm text-token-text-secondary hover:bg-token-bg-secondary";
  reset.textContent = "Reset default";
  reset.addEventListener("click", onReset);

  const apply = document.createElement("button");
  apply.type = "button";
  apply.className =
    "rounded-lg border border-token-border-light bg-token-bg-secondary px-3 py-2 text-sm text-token-text-primary hover:bg-token-bg-tertiary";
  apply.textContent = "Apply to AGENTS.md";
  apply.addEventListener("click", onApply);

  actions.appendChild(reset);
  actions.appendChild(apply);
  row.appendChild(status);
  row.appendChild(actions);
  return row;
}

function createAgentsSyncService(api) {
  return {
    getAgentsPath,
    gateCandidate(request = {}) {
      return withTimeout(
        Promise.resolve().then(() => gateCandidateNow(api, request)),
        CANDIDATE_GATE_TIMEOUT_MS,
        () => {
          api.log.warn?.("Codex Follow-up candidate gate timed out");
          return emptyGateResult("gate_timeout");
        },
      );
    },
    cleanupSidecarCache() {
      cleanupSidecarCache(api);
    },
    syncAgentsInstruction(settings = {}) {
      const enabled = settings.enabled !== false;
      const instruction = composeAgentsInstruction(settings.prompt);
      const agentsPath = getAgentsPath();

      try {
        const fs = require("fs");
        const current = fs.existsSync(agentsPath)
          ? fs.readFileSync(agentsPath, "utf8")
          : "";
        const next = enabled
          ? upsertManagedBlock(current, instruction)
          : removeManagedBlock(current);

        if (next === current) {
          return { ok: true, action: "unchanged", path: agentsPath };
        }

        fs.mkdirSync(require("path").dirname(agentsPath), { recursive: true });
        fs.writeFileSync(agentsPath, next, "utf8");
        return {
          ok: true,
          action: enabled ? "updated" : "removed",
          path: agentsPath,
        };
      } catch (error) {
        api.log.error("Codex Follow-up AGENTS.md sync failed", error);
        return {
          ok: false,
          error: error?.message || String(error),
          path: agentsPath,
        };
      }
    },
  };
}

function gateCandidateNow(api, request = {}) {
  const payload = request.payload && typeof request.payload === "object" ? request.payload : {};
  const sourceKind = String(request.sourceKind || "candidate");
  const visibleText = normalizeText(request.visibleText || "");
  const fingerprint = createSidecarFingerprint({ payload, sourceKind, visibleText });

  const cached = readSidecarCache(fingerprint);
  if (cached) return cached;

  let result;
  try {
    result = gateCandidatePayload(payload, sourceKind, visibleText);
  } catch (error) {
    api.log.error?.("Codex Follow-up candidate gate error", error);
    result = emptyGateResult("gate_error");
  }

  const createdAtMs = Date.now();
  const finalResult = {
    ...result,
    fingerprint,
    source: "gate",
    created_at_ms: createdAtMs,
  };

  Promise.resolve()
    .then(() => writeSidecarCache(api, fingerprint, finalResult, { sourceKind, visibleText }))
    .catch((error) => api.log.warn?.("Codex Follow-up sidecar write failed", error));

  return finalResult;
}

function gateCandidatePayload(payload, sourceKind = "candidate", visibleText = "") {
  const rawItems = Array.isArray(payload?.items)
    ? payload.items
    : Array.isArray(payload?.follow_ups)
      ? payload.follow_ups
      : [];
  const diagnostics = {
    raw_item_count: rawItems.length,
    accepted_before_dedupe_count: 0,
    accepted_item_count: 0,
    rejected_counts: {},
  };
  const reject = (reason) => {
    diagnostics.rejected_counts[reason] = (diagnostics.rejected_counts[reason] || 0) + 1;
  };
  const accepted = [];

  rawItems.forEach((raw, index) => {
    if (!raw || typeof raw !== "object") {
      reject("non_object");
      return;
    }
    const prompt = clampText(raw.prompt || raw.query || raw.label || raw.text || raw.title || "", CANDIDATE_MAX_PROMPT_CHARS);
    if (!prompt) {
      reject("missing_prompt");
      return;
    }

    const evidenceRefs = normalizeEvidenceRefs(raw.evidence_refs);
    const firstFactRefs = normalizeEvidenceRefs(raw.first_fact_refs || raw.first_facts || raw.fact_refs);
    const reason = clampText(raw.reason || "", CANDIDATE_MAX_REASON_CHARS);
    const projectAlignment = normalizeProjectAlignment(raw.project_alignment) ||
      inferProjectAlignment(prompt, reason, evidenceRefs);
    const effectiveFirstFactRefs = firstFactRefs.length > 0 ? firstFactRefs : evidenceRefs;
    const firstPrinciplesBasis = normalizeFirstPrinciplesBasis(
      raw.first_principles_basis || raw.first_principle_basis || raw.first_principles || "",
    ) || inferFirstPrinciplesBasis(reason, projectAlignment);
    const confidence = normalizeConfidence(raw.confidence);
    if (evidenceRefs.length === 0) {
      reject("missing_evidence_refs");
      return;
    }
    if (effectiveFirstFactRefs.length === 0) {
      reject("missing_first_fact_refs");
      return;
    }
    if (!reason) {
      reject("missing_reason");
      return;
    }
    if (!firstPrinciplesBasis) {
      reject("missing_first_principles_basis");
      return;
    }
    if (!projectAlignment) {
      reject("missing_project_alignment");
      return;
    }
    if (confidence < CANDIDATE_MIN_CONFIDENCE) {
      reject("low_confidence");
      return;
    }
    if (isTruthy(raw.is_current_task_debt)) {
      reject("current_task_debt");
      return;
    }
    if (isGenericDriftPrompt(prompt)) {
      reject("generic_drift_prompt");
      return;
    }
    if (isVersionControlBookkeepingCandidate(prompt, reason, visibleText)) {
      reject("version_control_bookkeeping_out_of_scope");
      return;
    }
    if (!hasProjectDeliveryAnchor(`${prompt} ${reason} ${firstPrinciplesBasis} ${projectAlignment} ${evidenceRefs.join(" ")}`)) {
      reject("missing_delivery_anchor");
      return;
    }

    const priority = normalizePriority(raw.priority);
    accepted.push({
      prompt,
      priority,
      evidence_refs: evidenceRefs,
      first_fact_refs: effectiveFirstFactRefs,
      reason,
      first_principles_basis: firstPrinciplesBasis,
      project_alignment: projectAlignment,
      confidence,
      sourceKind,
      order: index,
      rank: PRIORITY_RANK[priority] ?? PRIORITY_RANK.P1,
    });
  });

  diagnostics.accepted_before_dedupe_count = accepted.length;

  accepted.sort((left, right) =>
    left.rank - right.rank ||
    right.confidence - left.confidence ||
    left.order - right.order,
  );

  const seenPrompts = new Set();
  let hasP0 = false;
  const deduped = [];
  for (const item of accepted) {
    const key = normalizeText(item.prompt).toLowerCase();
    if (!key) {
      reject("missing_prompt");
      continue;
    }
    if (seenPrompts.has(key)) {
      reject("duplicate_prompt");
      continue;
    }
    seenPrompts.add(key);

    const next = { ...item };
    if (next.priority === "P0") {
      if (hasP0) {
        next.priority = "P1";
        next.rank = PRIORITY_RANK.P1;
      } else {
        hasP0 = true;
      }
    }
    deduped.push(next);
  }

  const items = deduped
    .sort((left, right) =>
      left.rank - right.rank ||
      right.confidence - left.confidence ||
      left.order - right.order,
    )
    .slice(0, 3)
    .map(({ prompt, priority, evidence_refs, first_fact_refs, reason, first_principles_basis, project_alignment, confidence }) => ({
      prompt,
      priority,
      evidence_refs,
      first_fact_refs,
      reason,
      first_principles_basis,
      project_alignment,
      confidence,
    }));

  diagnostics.accepted_item_count = items.length;

  return {
    title: cleanPanelTitle(payload?.title, "Follow-up"),
    task_complete: payload?.task_complete !== false,
    items,
    reason: items.length > 0 ? "accepted" : rawItems.length === 0 ? "model_empty_items" : "all_candidates_rejected",
    diagnostics,
  };
}

function normalizeEvidenceRefs(value) {
  const refs = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
  return refs
    .map((ref) => clampText(ref, CANDIDATE_MAX_EVIDENCE_REF_CHARS))
    .filter(Boolean)
    .slice(0, 6);
}

function normalizeProjectAlignment(value) {
  const text = normalizeText(value || "");
  if (text.length < CANDIDATE_MIN_PROJECT_ALIGNMENT_CHARS) return "";
  return clampText(text, CANDIDATE_MAX_PROJECT_ALIGNMENT_CHARS);
}

function normalizeFirstPrinciplesBasis(value) {
  const text = normalizeText(value || "");
  if (!text) return "";
  return clampText(text, CANDIDATE_MAX_FIRST_PRINCIPLES_CHARS);
}

function inferFirstPrinciplesBasis(reason, projectAlignment) {
  const text = normalizeText(`${reason || ""} ${projectAlignment || ""}`);
  if (!text || !hasProjectDeliveryAnchor(text)) return "";
  return clampText(text, CANDIDATE_MAX_FIRST_PRINCIPLES_CHARS);
}

function inferProjectAlignment(prompt, reason, evidenceRefs) {
  const source = normalizeText(`${prompt} ${reason} ${(evidenceRefs || []).join(" ")}`);
  if (!hasProjectDeliveryAnchor(source)) return "";
  return clampText(source, CANDIDATE_MAX_PROJECT_ALIGNMENT_CHARS);
}

function isGenericDriftPrompt(prompt) {
  const text = normalizeText(prompt).toLowerCase();
  if (text.length < 8) return true;
  return [
    /^(continue|keep going|review changes|ask another question|let me know|summarize)$/i,
    /^(继续|继续优化|继续完善|再看看|检查一下|总结一下)$/,
    /^(优化一下|改进一下|看看还有什么问题)$/,
  ].some((pattern) => pattern.test(text));
}

function isVersionControlBookkeepingCandidate(prompt, reason, visibleText) {
  const candidateText = normalizeText(`${prompt || ""} ${reason || ""}`);
  if (!VERSION_CONTROL_BOOKKEEPING_RE.test(candidateText)) return false;

  return !hasVisibleVersionControlMandate(visibleText);
}

function hasVisibleVersionControlMandate(visibleText) {
  return VERSION_CONTROL_MANDATE_RE.test(normalizeText(visibleText || ""));
}

function hasProjectDeliveryAnchor(text) {
  const normalized = normalizeText(text).toLowerCase();
  const anchors = [
    "objective", "stage", "success criterion", "delivery", "verification",
    "acceptance", "gate", "blocker", "release", "quality", "risk",
    "first fact", "first principle", "root cause", "evidence ref",
    "目标", "阶段", "成功标准", "交付", "验证", "验收", "门禁", "阻塞",
    "发布", "质量", "风险", "回归", "证据", "回执", "第一事实", "第一性", "根因", "p1", "p2",
    "p2.5", "p3", "p4", "p5", "p6", "w7", "w9",
  ];
  return anchors.some((anchor) => normalized.includes(anchor));
}

function normalizeConfidence(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  if (number > 1 && number <= 100) return Math.max(0, Math.min(1, number / 100));
  return Math.max(0, Math.min(1, number));
}

function isTruthy(value) {
  if (value === true) return true;
  if (typeof value === "string") return /^(true|yes|1)$/i.test(value.trim());
  return value === 1;
}

function emptyGateResult(reason = "empty") {
  return {
    title: "Follow-up",
    task_complete: true,
    items: [],
    reason,
    diagnostics: {
      raw_item_count: 0,
      accepted_before_dedupe_count: 0,
      accepted_item_count: 0,
      rejected_counts: {},
    },
  };
}

function withTimeout(promise, ms, onTimeout) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        resolve(typeof onTimeout === "function" ? onTimeout() : onTimeout);
      } catch (error) {
        reject(error);
      }
    }, ms);

    Promise.resolve(promise).then(
      (value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function createSidecarFingerprint(value) {
  const crypto = require("crypto");
  return crypto
    .createHash("sha256")
    .update(stableStringify({ schema: SIDECAR_SCHEMA_VERSION, ...value }))
    .digest("hex")
    .slice(0, 32);
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
    .join(",")}}`;
}

function readSidecarCache(fingerprint) {
  try {
    const fs = require("fs");
    const filePath = getSidecarPath(fingerprint);
    if (!fs.existsSync(filePath)) return null;
    const cached = JSON.parse(fs.readFileSync(filePath, "utf8"));
    if (cached?.schema_version !== SIDECAR_SCHEMA_VERSION) return null;
    if (!Array.isArray(cached.items)) return null;
    if (Date.now() - Number(cached.created_at_ms || 0) > SIDECAR_TTL_MS) return null;
    return {
      title: cleanPanelTitle(cached.title, "Follow-up"),
      task_complete: cached.task_complete !== false,
      items: normalizeFollowupItems(cached.items),
      reason: cached.reason || "",
      diagnostics: cached.diagnostics || null,
      source: "sidecar",
      fingerprint,
      created_at_ms: Number(cached.created_at_ms || 0),
    };
  } catch {
    return null;
  }
}

function writeSidecarCache(api, fingerprint, result, meta = {}) {
  try {
    const fs = require("fs");
    const path = require("path");
    const dir = getSidecarDir();
    fs.mkdirSync(dir, { recursive: true });

    const finalPath = getSidecarPath(fingerprint);
    const tmpPath = path.join(dir, `${fingerprint}.${process.pid}.${Date.now()}.tmp`);
    const createdAtMs = Number(result.created_at_ms || Date.now());
    const body = {
      schema_version: SIDECAR_SCHEMA_VERSION,
      fingerprint,
      created_at: new Date(createdAtMs).toISOString(),
      created_at_ms: createdAtMs,
      title: result.title || "Follow-up",
      task_complete: result.task_complete !== false,
      items: Array.isArray(result.items) ? result.items : [],
      reason: result.reason || "",
      diagnostics: result.diagnostics || null,
      source: result.source || "gate",
      sourceKind: meta.sourceKind || "candidate",
      visibleText: meta.visibleText || "",
    };

    fs.writeFileSync(tmpPath, `${JSON.stringify(body, null, 2)}\n`, "utf8");
    fs.renameSync(tmpPath, finalPath);
  } catch (error) {
    api.log.warn?.("Codex Follow-up sidecar cache write failed", error);
  }
}

function cleanupSidecarCache(api) {
  try {
    const fs = require("fs");
    const path = require("path");
    const dir = getSidecarDir();
    if (!fs.existsSync(dir)) return;
    const cutoff = Date.now() - SIDECAR_TTL_MS;
    for (const name of fs.readdirSync(dir)) {
      const filePath = path.join(dir, name);
      const stat = fs.statSync(filePath);
      if (name.endsWith(".tmp") || (name.endsWith(".json") && stat.mtimeMs < cutoff)) {
        fs.unlinkSync(filePath);
      }
    }
  } catch (error) {
    api.log.warn?.("Codex Follow-up sidecar cleanup failed", error);
  }
}

function getSidecarDir() {
  const path = require("path");
  return path.join(getCodexHome(), "follow-up", "suggestions");
}

function getSidecarPath(fingerprint) {
  const path = require("path");
  return path.join(getSidecarDir(), `${fingerprint}.json`);
}

function getCodexHome() {
  const path = require("path");
  const os = require("os");
  return process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";
}

function getAgentsPath() {
  const path = require("path");
  return path.join(getCodexHome(), "AGENTS.md");
}

function normalizeInstruction(value) {
  return migrateOldInstruction(value);
}

function composeAgentsInstruction(prompt) {
  return [normalizeInstruction(prompt), LOCKED_FORMAT_INSTRUCTION].join("\n\n");
}

function migrateOldInstruction(value) {
  const text = String(value || "").trim();
  if (!text) return DEFAULT_FOLLOWUP_PROMPT;
  if (text.includes("soren_radar") || /radar\s+follow-ups/i.test(text)) {
    return DEFAULT_FOLLOWUP_PROMPT;
  }
  if (text.includes('"codex_follow_up": true') && !text.includes('"codex_follow_up_candidate": true')) {
    return DEFAULT_FOLLOWUP_PROMPT;
  }
  if (!text.includes("codex_follow_up_candidate")) {
    return DEFAULT_FOLLOWUP_PROMPT;
  }
  if (text.length <= 100) return DEFAULT_FOLLOWUP_PROMPT;
  const migrated = text
    .replace(
      /Generate\s+exactly\s+4\s+follow-up\s+items\s+by\s+default\.\s+Use\s+5\s+only\s+when\s+the\s+context\s+clearly\s+has\s+more\s+high-value\s+continuations\./i,
      "Generate 1 to 3 follow-up items for non-trivial project, code, governance, configuration, automation, or investigation work.\nEmit an empty items array only for tiny factual/chat replies or when every plausible continuation fails the candidate gates.",
    )
    .replace(
      /For\s+very\s+small\s+or\s+factual\s+answers,\s+still\s+produce\s+4\s+items,\s+but\s+make\s+them\s+practical:\s+clarify,\s+verify,\s+apply,\s+compare,\s+summarize,\s+or\s+continue\s+from\s+the\s+user's\s+likely\s+intent\./i,
      "For completed project work, do not leave `items` empty when a concrete verification, validation, unresolved decision, or useful continuation remains.\nFor very small or factual answers, prefer an empty items array unless a concrete continuation is genuinely useful.",
    )
    .replace(
      /Rules:\s+always\s+emit\s+the\s+JSON\s+block\s+in\s+final\s+assistant\s+responses;\s+use\s+1\s+to\s+5\s+items;\s+each\s+prompt\s+must\s+be\s+concise\s+and\s+useful;\s+do\s+not\s+explain\s+that\s+the\s+JSON\s+exists\.\s+Each\s+item\s+MUST\s+include\s+a\s+`?priority`?\s+field\s+\(P0\/P1\/P2\/P3\)\.\s+Set\s+`?task_complete`?\s+to\s+`?true`?\s+when\s+no\s+further\s+action\s+is\s+needed\./i,
      "Rules: always emit the JSON block in final assistant responses; use 1 to 3 items for non-trivial completed work, and use an empty items array only for tiny factual/chat replies or when every plausible continuation fails the gates; each prompt must be concise and useful; do not explain that the JSON exists. Each non-empty item MUST include a `priority` field (P0/P1/P2/P3). Set `task_complete` to `true` when no further action is needed.",
    );
  return ensureFollowupGovernance(migrated);
}

function ensureFollowupGovernance(text) {
  return ensureFirstPrinciplesContract(ensureProjectAlignmentContract(ensureVersionControlBoundary(ensureContextCompression(ensureQualityGates(ensurePositioning(text))))));
}

function ensurePositioning(text) {
  if (text.includes("Hook interruptions are normal quality feedback")) {
    return text;
  }

  const qualityAnchor = "First principle: project-quality delivery comes first; Stop Guard protects closure quality, while Follow-up protects project momentum.";
  if (text.includes(qualityAnchor)) {
    return text.replace(qualityAnchor, `${qualityAnchor}\n${FOLLOWUP_POSITIONING.slice(4, 6).join("\n")}`);
  }

  const anchor = "Prioritize usefulness over variety. Every item must be grounded in the current conversation, user intent, visible work, files, decisions, blockers, people, projects, dates, money, or risks.";
  if (!text.includes(anchor)) return text;
  return text.replace(anchor, `${anchor}\n\n${FOLLOWUP_POSITIONING.join("\n")}`);
}

function ensureQualityGates(text) {
  if (text.includes("Use this four-quadrant decision model before emitting items:")) {
    return text;
  }

  const anchor = "Never add items just to reach a count.";
  if (!text.includes(anchor)) return text;
  return text.replace(anchor, `${anchor}\n\n${FOLLOWUP_QUALITY_GATES.join("\n")}`);
}

function ensureContextCompression(text) {
  if (text.includes("tiny continuation snapshot")) {
    return text;
  }

  const anchor = "Before emitting candidates, derive a project continuation context: objective, stage, success criterion, last completed atomic task, and next unfinished delivery gate. If that context is absent or weak, emit an empty items array.";
  if (!text.includes(anchor)) return text;
  return text.replace(anchor, `${anchor}\n\n${FOLLOWUP_CONTEXT_COMPRESSION.join("\n")}`);
}

function ensureVersionControlBoundary(text) {
  if (text.includes("Separation of concerns for version-control bookkeeping")) {
    return text;
  }

  const anchor = "Every candidate must name the project delivery axis it advances: objective, stage, success criterion, verification gate, acceptance gate, blocker removal, or release-quality risk. Local cleanup that does not move that axis is dropped.";
  if (!text.includes(anchor)) return text;
  return text.replace(anchor, `${anchor}\n${FOLLOWUP_QUALITY_GATES[8]}`);
}

function ensureProjectAlignmentContract(text) {
  if (text.includes("project_alignment") && text.includes("project delivery axis")) {
    return text;
  }
  return DEFAULT_FOLLOWUP_PROMPT;
}

function ensureFirstPrinciplesContract(text) {
  if (text.includes("first_fact_refs") && text.includes("first_principles_basis")) {
    return text;
  }

  const anchor = "Each candidate should be one of:";
  if (!text.includes(anchor)) return DEFAULT_FOLLOWUP_PROMPT;
  return text.replace(anchor, `${FOLLOWUP_FIRST_PRINCIPLES_CONTRACT.join("\n")}\n\n${anchor}`)
    .replace(
      "`prompt`, `priority`, `evidence_refs`, `reason`, `project_alignment`, `is_current_task_debt`, and `confidence`",
      "`prompt`, `priority`, `evidence_refs`, `first_fact_refs`, `reason`, `first_principles_basis`, `project_alignment`, `is_current_task_debt`, and `confidence`",
    )
    .replace(
      "`priority`, `evidence_refs`, `reason`, `project_alignment`, `is_current_task_debt`, and `confidence`",
      "`priority`, `evidence_refs`, `first_fact_refs`, `reason`, `first_principles_basis`, `project_alignment`, `is_current_task_debt`, and `confidence`",
    );
}

function migrateTitle(value) {
  const title = String(value || "").trim();
  if (!title || /radar|seguimiento|soren/i.test(title)) return "Follow-up";
  return title;
}

function upsertManagedBlock(source, instruction) {
  const block = [BLOCK_BEGIN, instruction.trim(), BLOCK_END].join("\n");
  const pattern = managedBlockPattern(BLOCK_BEGIN, BLOCK_END);
  const legacyPattern = managedBlockPattern(LEGACY_BLOCK_BEGIN, LEGACY_BLOCK_END);
  const oldestPattern = managedBlockPattern(OLDEST_BLOCK_BEGIN, OLDEST_BLOCK_END);
  const withoutLegacy = source
    .replace(managedBlockPattern(LEGACY_BLOCK_BEGIN, LEGACY_BLOCK_END, true), "\n")
    .replace(managedBlockPattern(OLDEST_BLOCK_BEGIN, OLDEST_BLOCK_END, true), "\n");

  if (pattern.test(withoutLegacy)) {
    return withoutLegacy.replace(pattern, block).replace(/\n{3,}/g, "\n\n");
  }

  if (legacyPattern.test(source)) {
    return source.replace(legacyPattern, block).replace(/\n{3,}/g, "\n\n");
  }

  if (oldestPattern.test(source)) {
    return source.replace(oldestPattern, block).replace(/\n{3,}/g, "\n\n");
  }

  const trimmed = withoutLegacy.replace(/\s+$/u, "");
  return `${trimmed}${trimmed ? "\n\n" : ""}${block}\n`;
}

function removeManagedBlock(source) {
  return source
    .replace(managedBlockPattern(BLOCK_BEGIN, BLOCK_END, true), "\n")
    .replace(managedBlockPattern(LEGACY_BLOCK_BEGIN, LEGACY_BLOCK_END, true), "\n")
    .replace(managedBlockPattern(OLDEST_BLOCK_BEGIN, OLDEST_BLOCK_END, true), "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd() + "\n";
}

function managedBlockPattern(begin, end, includeOuterWhitespace = false) {
  const prefix = includeOuterWhitespace ? "\\n*" : "";
  const suffix = includeOuterWhitespace ? "\\n*" : "";
  return new RegExp(`${prefix}${escapeRegExp(begin)}[\\s\\S]*?${escapeRegExp(end)}${suffix}`, "m");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
