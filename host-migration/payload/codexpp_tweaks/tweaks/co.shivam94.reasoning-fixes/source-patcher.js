const STATE_KEY = "__reasoningFixesSourcePatcherV1";
const IPC_KEY = "__reasoningFixesSourcePatcherIpcV1";
const RELOAD_TOKEN_KEY = "__reasoningFixesSourceReloadTokenV1";

const DEFAULTS = {
  "show-reasoning": true,
  "disable-shimmer": true,
  "show-file-edits": true,
  "show-exploration-items": true,
  "auto-expand-exec": true,
  "expand-tool-activity": true,
};

const SETTING_FEATURES = {
  "show-reasoning": [
    "show-reasoning",
    "render-standalone-reasoning",
    "reasoning-start-expanded",
    "reasoning-no-autocollapse",
    "reasoning-no-blink",
    "no-layout-position",
    "reasoning-no-blink-fade",
    "reasoning-no-animate-height",
    "fix-assistant-order",
    "auto-expand-exec",
    "expand-tool-activity",
  ],
  "show-exploration-items": [
    "show-exploration-items",
  ],
  "auto-expand-exec": ["auto-expand-exec"],
  "expand-tool-activity": ["expand-tool-activity"],
  "disable-shimmer": ["disable-shimmer"],
  "show-file-edits": ["file-edits-no-tool-group"],
};

const PATCHES = {
  "show-reasoning": {
    name: "split_items_drop_reasoning_from_exploration",
    bundle: "split-items",
    unpatched: /if\(t\.type===`reasoning`\)\{i&&i\.push\(t\);continue\}/,
    patched: /if\(t\.type===`reasoning`\)\{i&&s\(`explored`\);r\.push\(\{kind:`item`,item:t\}\);continue\}/,
    replacement: "if(t.type===`reasoning`){console.log('[reasoning-fixes:Ge] reasoning item standalone',t.type);i&&s(`explored`);r.push({kind:`item`,item:t});continue}",
  },
  "disable-shimmer": {
    name: "disable_thinking_shimmer",
    bundle: "shimmer",
    unpatched: /!\((\w+)===void 0\|\|\1\)/,
    patched: /,true\)\{/,
    replacement: "true",
  },
  "render-standalone-reasoning": {
    name: "agent_item_render_reasoning_via_default_renderer",
    bundle: "thread",
    unpatched: /}else if\(e\.type===`reasoning`\)F=null;/,
    patched: /}else if\(false\){}/,
    replacement: "}else if(false){}",
  },
  "reasoning-start-expanded": {
    name: "reasoning_start_expanded_useState",
    bundle: "thread",
    unpatched: /\[d,f\]=\(0,Q\.useState\)\(o\)/,
    patched: /\[d,f\]=\(0,Q\.useState\)\(!0\)/,
    replacement: "[d,f]=(0,Q.useState)(!0)",
  },
  "reasoning-no-autocollapse": {
    name: "reasoning_no_autocollapse_on_finish",
    bundle: "thread",
    unpatched: /if\(!o\)\{S\(!1\);return\}/,
    patched: /if\(!o\)\{return\}/,
    replacement: "if(!o){return}",
  },
  "reasoning-no-blink": {
    name: "reasoning_no_blink_during_stream",
    bundle: "thread",
    unpatched: /g=o\?!!h:d/,
    patched: /g=o\?!0:d/,
    replacement: "g=o?!0:d",
  },
  "no-layout-position": {
    name: "framer_motion_layout_position_off_thread",
    bundle: "thread",
    unpatched: /layout:`position`,/,
    patched: /layout:!1,/,
    replacement: "layout:!1,",
  },
  "reasoning-no-blink-fade": {
    name: "reasoning_no_blink_markdown_fade",
    bundle: "thread",
    unpatched: /fadeType:o\?`indexed`:`none`/,
    patched: /fadeType:`none`/,
    replacement: "fadeType:`none`",
  },
  "reasoning-no-animate-height": {
    name: "reasoning_no_height_transition",
    bundle: "thread",
    unpatched: /initial:!1,animate:P,transition:yo/,
    patched: /initial:!1,animate:P,transition:{duration:0}/,
    replacement: "initial:!1,animate:P,transition:{duration:0}",
  },
  "show-exploration-items": {
    name: "exploration_items_as_standalone",
    bundle: "split-items",
    unpatched: /function (\w+)\(e\)\{return e\.type!==`exec`\|\|e\.parsedCmd\.type===`read`&&!e\.parsedCmd\.isFinished&&\w+\(\{summary:e\.parsedCmd,cwd:e\.cwd\}\)\?!1:e\.parsedCmd\.type===`list_files`\|\|e\.parsedCmd\.type===`search`\|\|e\.parsedCmd\.type===`read`\}/,
    patched: /function \w+\(e\)\{return false\}/,
    replacement: "function $1(e){console.log('[reasoning-fixes:Ke] exploration item prevented');return false}",
  },
  "fix-assistant-order": {
    name: "find_assistant_anywhere_in_agent_items",
    bundle: "split-items",
    unpatched: /D=E\[E\.length-1\],O=Xe\(D\)\?D:null,k=\(O\?\.content\?\.trim\(\)\.length\?\?0\)>0\|\|!!O\?\.structuredOutput;O\?\(E\.pop\(\),g\.push\(\.\.\.T\)\):E\.push\(\.\.\.T\);/,
    patched: /let O=null;for\(let i=E\.length-1;i>=0;--i\)if\(Xe\(E\[i\]\)\)\{O=E\.splice\(i,1\)\[0\];break\}/,
    replacement: "O=null;for(let i=E.length-1;i>=0;--i)if(Xe(E[i])){O=E.splice(i,1)[0];break}let k=(O?.content?.trim().length??0)>0||!!O?.structuredOutput;O?g.push(...T):E.push(...T);",
  },
  "file-edits-no-tool-group": {
    name: "file_edits_not_collapsed_tool_activity",
    bundle: "split-items",
    // Keep patch as a recognized case; making it fall through triggers Codex's
    // exhaustive unexpected-value throw and breaks conversation rendering.
    unpatched: /e\.type===`exploration`\|\|e\.type===`patch`\|\|e\.type===`exec`/,
    patched: /e\.type===`exploration`\?!0:e\.type===`patch`\?!1:e\.type===`exec`/,
    replacement: "e.type===`exploration`?!0:e.type===`patch`?!1:e.type===`exec`",
  },
  "auto-expand-exec": {
    name: "auto_expand_exec_shells_by_default",
    bundle: "thread",
    unpatched: /defaultExpandExecShell:\w+!==[^,}]+/,
    patched: /defaultExpandExecShell:!0/,
    replacement: "defaultExpandExecShell:!0",
  },
  "expand-tool-activity": {
    name: "expand_tool_activity_sections",
    bundle: "thread",
    unpatched: /defaultExpanded:!1,onExpand:/g,
    patched: /defaultExpanded:!0,onExpand:/g,
    replacement: "defaultExpanded:!0,onExpand:",
  },
};

function startReasoningFixesMain(api) {
  // Reset state on each start to ensure protocol handler re-installs
  const old = globalThis[STATE_KEY];
  if (old && old.disposeProtocol) {
    try { old.disposeProtocol(); } catch(e) {}
  }
  const state = {
    protocolPatched: false,
    observations: Object.create(null),
    patchedAssets: new Set(),
  };
  state.api = api;
  state.enabled = true;
  globalThis[STATE_KEY] = state;

  installProtocolPatch(state);
  installIpc(state);
  api.log.info("[reasoning-fixes] source patcher ready");
  return () => {
    state.enabled = false;
    if (state.reloadTimer) {
      clearTimeout(state.reloadTimer);
      state.reloadTimer = null;
    }
    api.log.info("[reasoning-fixes] source patcher disabled");
  };
}

function installProtocolPatch(state) {
  if (state.protocolPatched) return;
  const { protocol } = require("electron");
  const originalHandle = protocol.handle;

  const reasoningFixesProtocolHandle = function reasoningFixesProtocolHandle(scheme, handler) {
    if (scheme !== "app" || typeof handler !== "function") {
      return originalHandle.apply(this, arguments);
    }

    const wrappedHandler = async (request) => {
      const response = await handler(request);
      const bundle = bundleForUrl(request?.url);
      if (!bundle || !state.enabled) return response;

      let originalText = null;
      try {
        originalText = await response.text();
        state.api.log.info("[reasoning-fixes] patching " + bundle + " bundle (" + originalText.length + " bytes)");
        const result = patchSource(state, request.url, originalText, bundle);
        if (result.changed) {
          state.api.log.info("[reasoning-fixes] " + bundle + " bundle changed: " + originalText.length + " -> " + result.text.length + " bytes");
        }
        const headers = new Headers(response.headers);
        headers.delete("content-length");
        headers.set("content-type", "text/javascript; charset=utf-8");
        return new Response(result.text, {
          status: response.status,
          statusText: response.statusText,
          headers,
        });
      } catch (error) {
        state.api.log.warn("[reasoning-fixes] failed to patch renderer asset", {
          url: request?.url,
          error: error?.stack || error?.message || String(error),
        });
        if (originalText != null) {
          const headers = new Headers(response.headers);
          headers.delete("content-length");
          return new Response(originalText, {
            status: response.status,
            statusText: response.statusText,
            headers,
          });
        }
        return response;
      }
    };

    return originalHandle.call(this, scheme, wrappedHandler);
  };
  protocol.handle = reasoningFixesProtocolHandle;

  state.protocolPatched = true;
  state.disposeProtocol = () => {
    try {
      if (protocol.handle === reasoningFixesProtocolHandle) {
        protocol.handle = originalHandle;
      }
    } catch(e) {}
    state.protocolPatched = false;
  };
  
  // If there are existing windows, reload them to apply patches
  // Handle both app://- and about:blank windows
  try {
    const { BrowserWindow } = require("electron");
    for (const window of BrowserWindow.getAllWindows()) {
      if (window.isDestroyed()) continue;
      const url = window.webContents.getURL();
      if (url.startsWith("app://-/") || url === "about:blank") {
        state.api.log.info("[reasoning-fixes] reloading window for new patches, url=" + url);
        window.webContents.reloadIgnoringCache();
      }
    }
  } catch(e) {
    // Ignore errors during reload (windows may not exist yet)
  }
}

function installIpc(state) {
  const shared = globalThis[IPC_KEY] || { registered: false };
  shared.impl = (request) => handleIpc(state, request);
  globalThis[IPC_KEY] = shared;
  if (shared.registered) return;

  state.api.ipc.handle("source-patches-v1", async (request) => {
    try {
      return await globalThis[IPC_KEY].impl(request);
    } catch (error) {
      return { ok: false, error: error?.message || String(error) };
    }
  });
  shared.registered = true;
}

async function handleIpc(state, request) {
  const action = request?.action || "status";
  if (action === "status") return buildStatus(state);
  if (action === "set-feature") {
    const id = request?.id;
    if (!Object.prototype.hasOwnProperty.call(DEFAULTS, id)) {
      return { ok: false, error: `unknown feature: ${id}` };
    }
    state.api.storage.set(`feature:${id}`, !!request.value);
    scheduleCodexWindowReload(state);
    return buildStatus(state);
  }
  if (action === "sync-features") {
    const values = request?.values || {};
    for (const id of Object.keys(DEFAULTS)) {
      if (typeof values[id] === "boolean") state.api.storage.set(`feature:${id}`, values[id]);
    }
    return buildStatus(state);
  }
  if (action === "reload-window") {
    scheduleCodexWindowReload(state);
    return buildStatus(state);
  }
  return { ok: false, error: `unknown action: ${action}` };
}

function patchSource(state, rawUrl, source, bundle) {
  const settings = readSettings(state.api.storage);
  const enabled = enabledLowLevelFeatures(settings);
  const basename = basenameForUrl(rawUrl);
  let text = source;
  let changed = false;

  for (const [feature, rule] of Object.entries(PATCHES)) {
    if (rule.bundle !== bundle) continue;
    const desired = enabled.has(feature);
    const before = inspectRule(text, rule);

    if (!desired) {
      recordObservation(state, feature, rule, before === "already" ? "bundled_active" : before === "not_applied" ? "available" : before, bundle, basename);
      continue;
    }

    if (before === "not_applied") {
      const next = text.replace(rule.unpatched, rule.replacement);
      if (next === text) {
        recordObservation(state, feature, rule, "unsupported", bundle, basename);
        continue;
      }
      text = next;
      changed = true;
      recordObservation(state, feature, rule, "active", bundle, basename);
    } else if (before === "already") {
      recordObservation(state, feature, rule, "active", bundle, basename);
    } else {
      recordObservation(state, feature, rule, "unsupported", bundle, basename);
    }
  }

  if (changed && !state.patchedAssets.has(basename)) {
    state.patchedAssets.add(basename);
    state.api.log.info("[reasoning-fixes] patched renderer asset", { asset: basename, bundle });
  }
  return { text, changed };
}

function inspectRule(source, rule) {
  const unpatchedCount = countMatches(source, rule.unpatched);
  const patchedCount = countMatches(source, rule.patched);
  if (unpatchedCount >= 1 && patchedCount === 0) return "not_applied";
  if (unpatchedCount === 0 && patchedCount >= 1) return "already";
  if (unpatchedCount === 0 && patchedCount === 0) return "unsupported";
  return "mixed";
}

function countMatches(source, re) {
  const flags = re.flags.includes("g") ? re.flags : `${re.flags}g`;
  const global = new RegExp(re.source, flags);
  return Array.from(source.matchAll(global)).length;
}

function recordObservation(state, feature, rule, status, bundle, asset) {
  state.observations[feature] = {
    feature,
    rule: rule.name,
    status,
    bundle,
    asset,
    updatedAt: new Date().toISOString(),
  };
}

function buildStatus(state) {
  const settings = readSettings(state.api.storage);
  const groups = {};
  for (const id of Object.keys(SETTING_FEATURES)) {
    groups[id] = aggregateSettingStatus(id, settings[id], state.observations);
  }
  return {
    ok: true,
    settings,
    groups,
    features: Object.values(state.observations),
    patchedAssets: Array.from(state.patchedAssets),
    reloadNeeded: state.api.storage.get("source:reload-needed", false) === true,
  };
}

function aggregateSettingStatus(id, enabled, observations) {
  const features = SETTING_FEATURES[id];
  const seen = features.map((feature) => observations[feature]).filter(Boolean);
  if (!enabled) {
    const bundled = seen.find((item) => item.status === "bundled_active");
    return {
      status: bundled ? "forced_active" : "disabled",
      message: bundled
        ? "Codex's served source already contains this change, so this toggle cannot disable it until Codex is restored or updated."
        : "",
      details: seen,
    };
  }
  const unsupported = seen.find((item) => item.status === "unsupported" || item.status === "mixed");
  if (unsupported) {
    return {
      status: "unsupported",
      message: "This Codex version does not match the known source shape for this feature. The tweak likely needs an update.",
      details: seen,
    };
  }
  if (seen.length < features.length) {
    return {
      status: "unknown",
      message: "Waiting for Codex to load the source chunk for this feature.",
      details: seen,
    };
  }
  return { status: "active", message: "", details: seen };
}

function readSettings(storage) {
  const out = {};
  for (const [id, fallback] of Object.entries(DEFAULTS)) {
    const value = storage.get(`feature:${id}`, undefined);
    out[id] = typeof value === "boolean" ? value : fallback;
  }
  return out;
}

function enabledLowLevelFeatures(settings) {
  const enabled = new Set();
  for (const [setting, features] of Object.entries(SETTING_FEATURES)) {
    if (!settings[setting]) continue;
    for (const feature of features) enabled.add(feature);
  }
  return enabled;
}

function bundleForUrl(rawUrl) {
  const basename = basenameForUrl(rawUrl);
  if (!basename) return null;
  if (/^composer-[A-Za-z0-9_-]+\.js$/.test(basename)) return "composer";
  if (/^split-items-into-render-groups-[A-Za-z0-9_-]+\.js$/.test(basename)) return "split-items";
  if (/^thinking-shimmer-[A-Za-z0-9_-]+\.js$/.test(basename)) return "shimmer";
  if (/^lt-[A-Za-z0-9_-]+\.js$/.test(basename)) return "lt";
  if (/^local-environments-settings-page-[A-Za-z0-9_-]+\.js$/.test(basename)) return "settings-page";
  if (/^local-conversation-thread-[A-Za-z0-9_-]+\.js$/.test(basename)) return "thread";
  return null;
}

function basenameForUrl(rawUrl) {
  if (typeof rawUrl !== "string") return null;
  try {
    const pathname = new URL(rawUrl).pathname;
    return pathname.slice(pathname.lastIndexOf("/") + 1);
  } catch {
    return null;
  }
}

function reloadCodexWindows(state) {
  const { BrowserWindow } = require("electron");
  const token = `${Date.now()}`;
  if (globalThis[RELOAD_TOKEN_KEY] === token) return;
  globalThis[RELOAD_TOKEN_KEY] = token;

  for (const window of BrowserWindow.getAllWindows()) {
    if (window.isDestroyed()) continue;
    const url = window.webContents.getURL();
    if (!url.startsWith("app://-/")) continue;
    state.api.log.info("[reasoning-fixes] reloading Codex window for source patch settings");
    window.webContents.reloadIgnoringCache();
  }
}

function scheduleCodexWindowReload(state) {
  state.api.storage.set("source:reload-needed", false);
  if (state.reloadTimer) clearTimeout(state.reloadTimer);
  state.reloadTimer = setTimeout(() => {
    state.reloadTimer = null;
    reloadCodexWindows(state);
  }, 150);
}

module.exports = {
  startReasoningFixesMain,
};
