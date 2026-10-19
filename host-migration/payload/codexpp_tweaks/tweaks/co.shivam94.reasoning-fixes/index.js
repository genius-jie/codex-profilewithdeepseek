/**
 * Reasoning & Exploration Fixes
 *
 * A Codex++ tweak (https://github.com/b-nnett/codex-plusplus) that improves
 * Codex Desktop's conversation UI.
 *
 * Features
 * --------
 *  • Exploration accordion stays open (fiber hook, live)
 *  • Reasoning items visible in conversation (source patch)
 *  • Reasoning display: scrollable or fully expanded (CSS injection, live)
 *  • File edits stay visible as main-chat items (source patch)
 *  • Tool outputs stay visible (source patch)
 *
 * Acknowledgments
 *  • codex++: https://github.com/b-nnett/codex-plusplus
 *  • Original source-patch inspiration:
 *    https://gist.github.com/andrew-kramer-inno/3fa1063b967cfad2bc6f7cd9af1249fd
 * License: MIT
 */

let mainStop = null;
let rendererState = null;
let settingsPageHandle = null;

/** @type {import("@codex-plusplus/sdk").Tweak} */
module.exports = {
  start(api) {
    try {
      if (api.process === "main") {
        mainStop = startMainHandler(api);
        return;
      }
    } catch (e) {
      api.log.error("[reasoning-fixes] start failed in main:", e?.message || String(e), e?.stack || "");
      return;
    }

    const state = {
      api,
      features: new Map(),
      cssInjections: new Map(),
      sourceStatus: null,
      sourceStatusSubscribers: new Set(),
      defaults: {
        "exploration-keep-open": true,
        "show-reasoning": true,
        "disable-shimmer": true,
        "reasoning-style": "expanded",  // "expanded" or "scroll"
        "show-file-edits": true,
        "show-exploration-items": true,
        "auto-expand-exec": true,
        "expand-tool-activity": true,
        "collapse-all-toggle": true,
      },
    };
    rendererState = state;
    syncSourceBackedSettings(state);

    if (typeof api.settings?.registerPage === "function") {
      settingsPageHandle = api.settings.registerPage({
        id: "main",
        title: "Reasoning & Exploration Fixes",
        description: "Improve how reasoning, exploration, file edits, and tool outputs display in the conversation.",
        iconSvg:
          '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" class="icon-sm inline-block align-middle">' +
          '<path d="M10 3v14M3 10h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
          '<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5" fill="none"/>' +
          "</svg>",
        render: (root) => renderSettings(root, state),
      });
    }

    // Floating collapse/expand all button
    setupCollapseAllButton(state);

    // Activate live features
    rendererState.reasoningStyle = readStyle(state.api, "reasoning-style", "expanded");
    applyReasoningStyle(state, rendererState.reasoningStyle);
    applyDisableShimmerStyle(state, readFlag(state.api, "disable-shimmer", true));

    if (readFlag(state.api, "exploration-keep-open", true)) {
      activateFeature(state, "exploration-keep-open");
    }
  },

  stop() {
    if (mainStop) {
      try { mainStop(); } catch (e) {}
      mainStop = null;
    }
    const s = rendererState;
    if (!s) return;
    for (const [, f] of s.features) {
      try { f.dispose?.(); } catch (e) { s.api.log.warn("dispose failed", e); }
    }
    s.features.clear();
    for (const [, dispose] of s.cssInjections) {
      try { dispose?.(); } catch (e) {}
    }
    s.cssInjections.clear();
    s.sourceStatusSubscribers?.clear();
    if (s._collapseCleanup) { try { s._collapseCleanup(); } catch(e) {} }
    settingsPageHandle?.unregister();
    settingsPageHandle = null;
    rendererState = null;
  },
};

// ─────────────────────────────────────────────────────────── settings UI ──

function renderSettings(root, state) {
  const container = el("div", "flex flex-col gap-4");

  // Section: Exploration
  const expSection = el("section", "flex flex-col gap-2");
  expSection.appendChild(sectionTitle("Exploration"));
  const expCard = roundedCard();
  expCard.appendChild(featureRow(state, {
    id: "exploration-keep-open",
    label: "Keep accordion open",
    desc: "Exploration panel stays expanded after Codex finishes searching and reading files. No restart needed.",
  }));
  expSection.appendChild(expCard);
  container.appendChild(expSection);

  const rsnSection = el("section", "flex flex-col gap-2");
  rsnSection.appendChild(sectionTitle("Reasoning"));
  const rsnCard = roundedCard();

  const showReasoningGroup = el("div", "flex flex-col");
  showReasoningGroup.appendChild(featureRow(state, {
    id: "show-reasoning",
    label: "Show reasoning",
    desc: "Adds thinking and reasoning entries to the chat.",
    source: true,
  }));

  showReasoningGroup.appendChild(styleChoiceRow(state, {
    id: "reasoning-style",
    label: "Reasoning display",
    desc: "Choose whether reasoning opens fully or stays in a compact scroll area.",
    nested: true,
    choices: [
      { value: "expanded", label: "Expanded" },
      { value: "scroll", label: "Scroll" },
    ],
  }));
  rsnCard.appendChild(showReasoningGroup);

  rsnCard.appendChild(featureRow(state, {
    id: "disable-shimmer",
    label: "Disable thinking animation",
    desc: "Keeps the Thinking label steady instead of pulsing.",
    source: true,
  }));

  rsnSection.appendChild(rsnCard);
  container.appendChild(rsnSection);

  const fileEditSection = el("section", "flex flex-col gap-2");
  fileEditSection.appendChild(sectionTitle("File Edits"));
  const fileEditCard = roundedCard();
  fileEditCard.appendChild(featureRow(state, {
    id: "show-file-edits",
    label: "Show file edits in chat",
    desc: "Keeps file-edit cards in the main chat instead of grouping them into tool activity.",
    source: true,
  }));
  fileEditSection.appendChild(fileEditCard);
  container.appendChild(fileEditSection);

  const explSection = el("section", "flex flex-col gap-2");
  explSection.appendChild(sectionTitle("Exploration Items"));
  const explCard = roundedCard();
  explCard.appendChild(featureRow(state, {
    id: "show-exploration-items",
    label: "Show exploration details",
    desc: "Show individual exploration file commands (read, list, search) instead of collapsing them into summaries.",
    source: true,
  }));
  explSection.appendChild(explCard);
  container.appendChild(explSection);

  const caSection = el("section", "flex flex-col gap-2");
  caSection.appendChild(sectionTitle("Collapse All"));
  const caCard = roundedCard();
  caCard.appendChild(featureRow(state, {
    id: "collapse-all-toggle",
    label: "Show collapse/expand button",
    desc: "Adds a floating button to collapse or expand all reasoning items and tool calls at once.",
    source: false,
  }));
  caSection.appendChild(caCard);
  container.appendChild(caSection);

  root.appendChild(container);
}

function featureRow(state, f) {
  const row = el("div", "flex items-center justify-between gap-4 p-3");
  const left = el("div", "flex min-w-0 flex-1 flex-col gap-1");
  const label = el("div", "min-w-0 text-sm text-token-text-primary");
  label.textContent = f.label;
  left.appendChild(label);
  if (f.desc) {
    const desc = el("div", "text-token-text-secondary min-w-0 text-sm");
    desc.textContent = f.desc;
    left.appendChild(desc);
  }
  if (f.source) {
    const warning = sourceWarningLine();
    left.appendChild(warning);
    const updateWarning = () => updateSourceFeatureWarning(state, f.id, warning);
    state.sourceStatusSubscribers?.add(updateWarning);
    updateWarning();
  }
  row.appendChild(left);

  const initial = readFlag(state.api, f.id, state.defaults[f.id] === true);
  const sw = switchControl(initial, async (next) => {
    writeFlag(state.api, f.id, next);
    if (f.source) {
      state.api.log.info("feature selection changed", f.id, next);
      if (f.id === "show-reasoning") state.updateReasoningStyleAvailability?.();
      if (f.id === "disable-shimmer") applyDisableShimmerStyle(state, next);
      await setSourceFeature(state, f.id, next);
    } else {
      if (next) activateFeature(state, f.id);
      else deactivateFeature(state, f.id);
    }
  });
  row.appendChild(sw);
  return row;
}

function notifySourceStatusSubscribers(state) {
  for (const cb of state.sourceStatusSubscribers || []) {
    try { cb(); } catch (e) { state.api.log.warn("source status subscriber failed", e); }
  }
}

function sourceWarningLine() {
  const line = el("div", "hidden rounded-md bg-token-editor-warning-background px-2 py-1 text-xs text-token-editor-warning-foreground");
  return line;
}

function updateSourceFeatureWarning(state, id, line) {
  const group = state.sourceStatus?.groups?.[id];
  const message = group?.status === "unsupported" || group?.status === "forced_active" ? group.message : "";
  line.textContent = message || "";
  line.classList.toggle("hidden", !message);
}

function styleChoiceRow(state, f) {
  const row = el(
    "div",
    f.nested
      ? "ml-3 flex flex-col gap-2 border-l border-token-border px-3 py-3"
      : "flex flex-col gap-2 p-3",
  );

  const left = el("div", "flex flex-col gap-1");
  const label = el("div", "text-sm text-token-text-primary");
  label.textContent = f.label;
  left.appendChild(label);
  const desc = el("div", "text-token-text-secondary min-w-0 text-sm");
  desc.textContent = f.desc || "";
  left.appendChild(desc);
  row.appendChild(left);

  const current = readStyle(state.api, "reasoning-style", "expanded");
  const segGroup = el("div", "flex gap-1");
  const buttons = [];

  for (const choice of f.choices) {
    const isSelected = current === choice.value;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
      (isSelected
        ? "bg-token-charts-blue text-white"
        : "bg-token-foreground/5 text-token-text-secondary hover:bg-token-foreground/10");
    btn.textContent = choice.label;

    btn.addEventListener("click", () => {
      if (!isReasoningDisplayEnabled(state)) return;
      const oldVal = readStyle(state.api, "reasoning-style", "expanded");
      if (choice.value === oldVal) return;
      writeStyle(state.api, "reasoning-style", choice.value);
      applyReasoningStyle(state, choice.value);
      row.replaceWith(styleChoiceRow(state, f));
    });

    buttons.push({ btn, isSelected });
    segGroup.appendChild(btn);
  }
  row.appendChild(segGroup);

  const updateAvailability = () => {
    const enabled = isReasoningDisplayEnabled(state);
    row.classList.toggle("opacity-50", !enabled);
    desc.textContent = enabled
      ? (f.desc || "")
      : reasoningDisplayDisabledText(state);
    for (const { btn, isSelected } of buttons) {
      btn.disabled = !enabled;
      btn.className =
        "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed " +
        (!enabled
          ? "bg-token-foreground/5 text-token-text-tertiary"
          : isSelected
            ? "bg-token-charts-blue text-white"
            : "bg-token-foreground/5 text-token-text-secondary hover:bg-token-foreground/10");
    }
  };

  state.updateReasoningStyleAvailability = updateAvailability;
  state.sourceStatusSubscribers?.add(updateAvailability);
  updateAvailability();
  return row;
}

function isReasoningDisplayEnabled(state) {
  if (!readFlag(state.api, "show-reasoning", true)) return false;
  const group = state.sourceStatus?.groups?.["show-reasoning"];
  return !group || group.status === "active" || group.status === "unknown";
}

function reasoningDisplayDisabledText(state) {
  if (!readFlag(state.api, "show-reasoning", true)) return "Turn on Show reasoning first.";
  if (!state.sourceStatus) return "Checking whether reasoning is available.";
  return "This Codex version needs a tweak update before reasoning display can be controlled.";
}

// ───────────────────────────────────────────────────── CSS injection ──

function applyReasoningStyle(state, style) {
  // Remove any previous CSS injection
  const prev = state.cssInjections.get("reasoning-style");
  if (prev) { try { prev(); } catch(e) {} state.cssInjections.delete("reasoning-style"); }

  const api = state.api;

  if (style === "expanded") {
    // Remove max-height from the reasoning item body container only.
    // Codex ships with max-h-35 overflow-y-auto by default (Scroll baseline).
    // We inject a style that overrides it for Expanded mode.
    const styleEl = document.createElement("style");
    styleEl.id = "reasoning-fixes-expanded";
    styleEl.textContent = `
      [class~="vertical-scroll-fade-mask"][class~="max-h-35"] {
        max-height: none !important;
        overflow: visible !important;
      }
    `;
    document.head.appendChild(styleEl);

    state.cssInjections.set("reasoning-style", () => {
      styleEl.remove();
    });
    api.log.info("reasoning style: expanded");
  } else {
    // Scroll mode — Codex's baseline already has max-h-35.
    // Just clean up any injected CSS (done above).
    api.log.info("reasoning style: scroll (baseline)");
  }
}

function applyDisableShimmerStyle(state, disabled) {
  const prev = state.cssInjections.get("disable-shimmer");
  if (prev) { try { prev(); } catch(e) {} state.cssInjections.delete("disable-shimmer"); }
  if (!disabled) return;

  const styleEl = document.createElement("style");
  styleEl.id = "reasoning-fixes-disable-shimmer";
  styleEl.textContent = `
    .loading-shimmer-pure-text.text-size-chat.select-none.truncate {
      animation: none !important;
      transition: none !important;
      background: none !important;
      -webkit-text-fill-color: var(--text-primary, currentColor) !important;
      text-fill-color: var(--text-primary, currentColor) !important;
    }

    .loading-shimmer-pure-text.text-size-chat.select-none.truncate[class*="cadencedShimmer"] {
      animation: none !important;
    }
  `;
  document.head.appendChild(styleEl);

  state.cssInjections.set("disable-shimmer", () => {
    styleEl.remove();
  });
  state.api.log.info("thinking animation disabled");
}

// ─────────────────────────────────────────────────────────── feature reg ──

function activateFeature(state, id) {
  if (state.features.has(id)) return;
  const fn = FEATURES[id];
  if (!fn) { state.api.log.warn("unknown feature", id); return; }
  try {
    const dispose = fn(state.api);
    state.features.set(id, { dispose });
    state.api.log.info("activated", id);
  } catch (e) {
    state.api.log.error("activate failed", id, e);
  }
}

function deactivateFeature(state, id) {
  const f = state.features.get(id);
  if (!f) return;
  try { f.dispose?.(); } finally {
    state.features.delete(id);
    state.api.log.info("deactivated", id);
  }
}

const FEATURES = {
  "collapse-all-toggle"(api) {
    // Show/hide the collapse button. Button is always created by
    // setupCollapseAllButton at start(); this just toggles visibility.
    const btn = document.getElementById("rft-btn");
    const css = document.getElementById("rft-css");
    if (btn) btn.style.display = "flex";
    if (css) css.disabled = false;
    return () => {
      const b = document.getElementById("rft-btn");
      const c = document.getElementById("rft-css");
      if (b) b.style.display = "none";
      if (c) c.disabled = true;
    };
  },
  "exploration-keep-open"(api) {
    const SEL = '[data-testid="exploration-accordion-body"]';
    let disposed = false;
    let retryCount = 0;

    const tryHook = () => {
      if (disposed) return;
      const domEl = document.querySelector(SEL);
      if (!domEl) {
        if (retryCount < 20) { retryCount++; setTimeout(tryHook, 1000); }
        return;
      }
      retryCount = 0;

      const allKeys = Object.keys(domEl);
      const reactKeys = allKeys.filter(k => k.startsWith("__"));
      let fiber = api.react.getFiber(domEl);
      if (!fiber) {
        for (const k of reactKeys) {
          if (k.startsWith("__reactFiber$")) { fiber = domEl[k]; if (fiber) break; }
        }
        if (!fiber) { setTimeout(tryHook, 2000); return; }
      }

      let depth = 0;
      while (fiber && depth < 20) {
        const hookVals = [];
        let h = fiber.memoizedState;
        while (h) { const v = h.memoizedState; if (typeof v === "string") hookVals.push(v); h = h.next; }
        for (const val of hookVals) {
          if (val === "preview" || val === "collapsed" || val === "expanded") {
            let hook = fiber.memoizedState;
            while (hook) {
              if (hook.memoizedState === val) {
                if (val === "collapsed") { try { hook.queue.dispatch("preview"); } catch(e) {} }
                const orig = hook.queue.dispatch;
                hook.queue.dispatch = (nv) => { if (nv === "collapsed" && !window.__reasoningFixesForceOverride) nv = "preview"; orig(nv); };
                return;
              }
              hook = hook.next;
            }
          }
        }
        fiber = fiber.return; depth++;
      }
    };

    setTimeout(tryHook, 500);
    const iv = setInterval(() => {
      if (disposed) { clearInterval(iv); return; }
      if (document.querySelector(SEL)) tryHook();
    }, 3000);

    return () => { disposed = true; };
  },
};

// ──────────────────────────────────────────────── collapse-all button ──

function setupCollapseAllButton(state) {
  const api = state.api;
  // Idempotent: skip if button already created on this page
  if (document.getElementById("rft-btn")) return;
  let collapsed = false;
  let btn = null;
  let styleEl = null;

  function addStyle() {
    if (document.getElementById("rft-css")) return;
    styleEl = document.createElement("style");
    styleEl.id = "rft-css";
    styleEl.textContent = "#rft-btn{position:fixed;bottom:24px;right:24px;z-index:9999;width:40px;height:40px;border-radius:50%;border:1px solid rgba(255,255,255,0.12);background:#1e1e1e;color:#ccc;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.4);opacity:0.5;transition:opacity 0.2s,transform 0.2s}#rft-btn:hover{opacity:1;transform:scale(1.05)}#rft-btn svg{width:20px;height:20px}body.rft-hide-all [data-testid=exploration-accordion-body]{max-height:0!important;overflow:hidden!important;opacity:0!important;pointer-events:none!important}body.rft-hide-all [class*=cursor-interaction]+[style*=opacity]{max-height:0!important;overflow:hidden!important;opacity:0!important;pointer-events:none!important}";
    document.head.appendChild(styleEl);
  }

  function makeBtn() {
    addStyle();
    btn = document.createElement("button");
    btn.id = "rft-btn";
    setIcon();
    btn.onclick = toggleAll;
    // Start hidden if setting is disabled
    const isEnabled = readFlag(state.api, "collapse-all-toggle", true);
    btn.style.display = isEnabled ? "flex" : "none";
    document.body.appendChild(btn);
  }

  function setIcon() {
    if (!btn) return;
    if (collapsed) {
      btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-6"/><path d="M12 8V2"/><path d="M4 12H2"/><path d="M10 12H8"/><path d="M16 12h-2"/><path d="M22 12h-2"/><path d="m15 19-3 3-3-3"/><path d="m15 5-3-3-3 3"/></svg>';
      btn.title = "Expand all";
    } else {
      btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-6"/><path d="M12 8V2"/><path d="M4 12H2"/><path d="M10 12H8"/><path d="M16 12h-2"/><path d="M22 12h-2"/><path d="m9 19 3-3 3 3"/><path d="m9 5 3 3 3-3"/></svg>';
      btn.title = "Collapse all";
    }
  }

  function toggleAll() {
    collapsed = !collapsed;
    document.body.classList.toggle("rft-hide-all", collapsed);
    setIcon();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", makeBtn);
  } else {
    setTimeout(makeBtn, 1500);
  }

  // Cleanup for stop() — find DOM elements dynamically so it works
  // even when setupCollapseAllButton hits the idempotency guard.
  rendererState._collapseCleanup = function() {
    var b = document.getElementById("rft-btn");
    if (b && b.parentNode) b.parentNode.removeChild(b);
    var s = document.getElementById("rft-css");
    if (s && s.parentNode) s.parentNode.removeChild(s);
  };
}

// ─────────────────────────────────────────────────────── main process ──

function startMainHandler(api) {
  const { startReasoningFixesMain } = require("./source-patcher.js");
  return startReasoningFixesMain(api);
}

// ─────────────────────────────────────────────────────────────── helpers ──

function readFlag(api, id, fallback) {
  const v = api.storage.get(`feature:${id}`, undefined);
  return typeof v === "boolean" ? v : !!fallback;
}
function writeFlag(api, id, on) { api.storage.set(`feature:${id}`, !!on); }

async function syncSourceBackedSettings(state) {
  try {
    const values = {};
    for (const id of ["show-reasoning", "disable-shimmer", "show-file-edits", "show-exploration-items"]) {
      values[id] = readFlag(state.api, id, state.defaults[id] === true);
    }
    const result = await state.api.ipc.invoke("source-patches-v1", { action: "sync-features", values });
    state.sourceStatus = result;
    notifySourceStatusSubscribers(state);
  } catch (e) {
    state.api.log.warn("source settings sync failed", e?.message || String(e));
  }
}

async function refreshSourceStatus(state) {
  try {
    const result = await state.api.ipc.invoke("source-patches-v1", { action: "status" });
    state.sourceStatus = result;
    if (result?.settings) syncRendererFlagsFromSourceStatus(state, result.settings);
    notifySourceStatusSubscribers(state);
  } catch (e) {
    state.api.log.warn("source status refresh failed", e?.message || String(e));
  }
}

async function setSourceFeature(state, id, value) {
  try {
    const result = await state.api.ipc.invoke("source-patches-v1", { action: "set-feature", id, value });
    state.sourceStatus = result;
    await refreshSourceStatus(state);
    notifySourceStatusSubscribers(state);
  } catch (e) {
    state.api.log.warn("source feature update failed", id, e?.message || String(e));
  }
}

function syncRendererFlagsFromSourceStatus(state, settings) {
  for (const id of ["show-reasoning", "disable-shimmer", "show-file-edits", "show-exploration-items"]) {
    if (typeof settings[id] === "boolean") writeFlag(state.api, id, settings[id]);
  }
}

function readStyle(api, id, fallback) {
  const v = api.storage.get(`style:${id}`, undefined);
  return typeof v === "string" ? v : fallback;
}
function writeStyle(api, id, val) { api.storage.set(`style:${id}`, val); }

function el(tag, c) { const n = document.createElement(tag); if (c) n.className = c; return n; }
function sectionTitle(text) {
  const r = el("div", "flex h-toolbar items-center justify-between gap-2 px-0 py-0");
  const inner = el("div", "flex min-w-0 flex-1 flex-col gap-1");
  const t = el("div", "text-base font-medium text-token-text-primary");
  t.textContent = text; inner.appendChild(t); r.appendChild(inner); return r;
}
function roundedCard() {
  const c = el("div", "border-token-border flex flex-col divide-y-[0.5px] divide-token-border rounded-lg border");
  c.style.backgroundColor = "var(--color-background-panel, var(--color-token-bg-fog))";
  return c;
}
function switchControl(initial, onChange) {
  const btn = document.createElement("button");
  btn.type = "button"; btn.setAttribute("role", "switch");
  const pill = document.createElement("span");
  const knob = document.createElement("span");
  knob.className = "rounded-full border border-[color:var(--gray-0)] bg-[color:var(--gray-0)] shadow-sm transition-transform duration-200 ease-out h-4 w-4";
  pill.appendChild(knob);
  const apply = (on) => {
    btn.setAttribute("aria-checked", String(on));
    btn.dataset.state = on ? "checked" : "unchecked";
    btn.className = "inline-flex shrink-0 items-center text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-token-focus-border focus-visible:rounded-full cursor-interaction";
    pill.className = "relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 ease-out h-5 w-8 " + (on ? "bg-token-charts-blue" : "bg-token-foreground/20");
    pill.dataset.state = on ? "checked" : "unchecked";
    knob.dataset.state = on ? "checked" : "unchecked";
    knob.style.transform = on ? "translateX(14px)" : "translateX(2px)";
  };
  apply(initial);
  btn.appendChild(pill);
  btn.addEventListener("click", async (e) => {
    e.preventDefault(); e.stopPropagation();
    const next = btn.getAttribute("aria-checked") !== "true";
    apply(next); btn.disabled = true;
    try { await onChange?.(next); } finally { btn.disabled = false; }
  });
  return btn;
}
