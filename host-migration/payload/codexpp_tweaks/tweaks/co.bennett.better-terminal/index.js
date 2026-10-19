/**
 * Better Terminal
 *
 * Terminal actions belong on terminal tabs. This tweak adds a tab context menu
 * and only uses live Codex terminal surfaces, never copied terminal snapshots.
 */

const STYLE_ID = "codexpp-better-terminal-style";
const MENU_ATTR = "data-codexpp-better-terminal-menu";
const RENAME_DIALOG_ATTR = "data-codexpp-better-terminal-rename-dialog";
const TITLE_ATTR = "data-codexpp-better-terminal-title";
const ORIGINAL_TEXT_ATTR = "data-codexpp-better-terminal-original-text";
const TAB_KEY_ATTR = "data-codexpp-better-terminal-tab-key";
const AUTOSCROLL_LOCK_ATTR = "data-codexpp-better-terminal-autoscroll-lock";
const SPLIT_ACTIVE_ATTR = "data-codexpp-better-terminal-split-active";
const SPLIT_DRAGGING_ATTR = "data-codexpp-better-terminal-split-dragging";
const SPLIT_DROP_ATTR = "data-codexpp-better-terminal-split-drop";
const TAB_DRAG_SOURCE_ATTR = "data-codexpp-better-terminal-tab-drag-source";
const SPLIT_TAB_ATTR = "data-codexpp-better-terminal-split-tab";
const SPLIT_ORIGINAL_TEXT_ATTR = "data-codexpp-better-terminal-split-original-text";
const RUNNING_TERMINAL_ATTR = "data-codexpp-better-terminal-running";
const FINISHED_TERMINAL_ATTR = "data-codexpp-better-terminal-finished";
const FROZEN_TERMINAL_ATTR = "data-codexpp-better-terminal-frozen";
const TERMINAL_WINDOW_ATTR = "data-codexpp-better-terminal-window";
const TERMINAL_WINDOW_CHROME_ATTR = "data-codexpp-better-terminal-window-chrome";
const TERMINAL_POPOUT_PLACEHOLDER_ATTR = "data-codexpp-better-terminal-popout-placeholder";
const TERMINAL_POPOUT_PARKED_ATTR = "data-codexpp-better-terminal-popout-parked";
const TERMINAL_MANAGER_SNAPSHOT_ATTR = "data-codexpp-better-terminal-manager-snapshot";
const SPLIT_MODE_KEY = "codexpp:better-terminal:split-mode";
const SPLIT_PAIR_KEY = "codexpp:better-terminal:split-pair";
const SPLIT_PRESERVE_UNMOUNTED_MS = 15_000;
const TERMINAL_WINDOW_PENDING_KEY = "codexpp:better-terminal:pending-window";
const TERMINAL_POPOUTS_KEY = "codexpp:better-terminal:popouts-v1";
const TERMINAL_SNAPSHOT_KEY_PREFIX = "codexpp:better-terminal:snapshot:";
const MAIN_STATE_KEY = "__codexppBetterTerminalMainState";
const OPEN_TERMINAL_WINDOW_CHANNEL = "open-terminal-window-v3";
const LEGACY_OPEN_TERMINAL_WINDOW_CHANNEL = "open-terminal-window-v2";
const TERMINAL_OPEN_HANDLER_VERSION = "terminal-popout-overlay-v5";
const RAW_OPEN_CHANNEL = "codexpp:co.bennett.better-terminal:open-terminal-window-from-sender-v2";
const LEGACY_RAW_OPEN_CHANNEL = "codexpp:co.bennett.better-terminal:open-terminal-window-from-sender";
const RAW_OPEN_HANDLER_VERSION = "terminal-popout-raw-overlay-v5";
const TERMINAL_FOCUS_CHANNEL = "terminal-focus-state";
const TERMINAL_CLEAR_SHORTCUT_CHANNEL = "terminal-clear-shortcut";
const TERMINAL_CLOSE_PANE_SHORTCUT_CHANNEL = "terminal-close-pane-shortcut";
const TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL = "terminal-toggle-shortcut-v1";
const TERMINAL_TOGGLE_SHORTCUT_CHANNEL = "codexpp:co.bennett.better-terminal:toggle-terminal-shortcut-v1";
const TERMINAL_ALWAYS_ON_TOP_CHANNEL = "terminal-always-on-top-v1";
const TERMINAL_POPOUT_REVEAL_CHANNEL = "terminal-popout-reveal-v1";
const TERMINAL_POPOUT_RETURN_CHANNEL = "terminal-popout-return-v1";
const TERMINAL_MEMORY_WATCHDOG_CHANNEL = "terminal-memory-watchdog-v6";
const TERMINAL_MEMORY_WATCHDOG_VERSION = 6;
const TERMINAL_WINDOW_REPORT_API_CHANNEL = "terminal-window-report-v1";
const TERMINAL_WINDOW_REPORT_CHANNEL = "codexpp:co.bennett.better-terminal:terminal-window-report-v1";
const TERMINAL_WINDOW_BACKGROUND = "#202020";
const TERMINAL_POPOUT_STALE_MS = 30_000;
const SCROLL_STICKINESS_PX = 8;
const APPLY_POLL_INTERVAL_MS = 5000;
const MAX_SPLIT_SESSIONS = 6;
const DEFAULT_MEMORY_WATCHDOG_ENABLED = true;
const DEFAULT_MEMORY_WATCHDOG_THRESHOLD_PERCENT = 75;
const MEMORY_WATCHDOG_INTERVAL_MS = 5000;
const FILLED_TERMINAL_ICON_MARK = "data-codexpp-better-terminal-filled-icon";
const TERMINAL_ICON_ORIGINAL_ATTR = "data-codexpp-better-terminal-icon-original";
const RUNNING_TERMINAL_BADGE_ATTR = "data-codexpp-better-terminal-running-badge";
const FILLED_TERMINAL_ICON_INNER = [
  '<path fill="currentColor" d="M7.33008 2.66504H12.6602C13.3492 2.66504 13.9062 2.66439 14.3564 2.70117C14.8142 2.73859 15.2201 2.81796 15.5967 3.00977C16.1922 3.31321 16.677 3.79805 16.9805 4.39356C17.1722 4.77014 17.2517 5.17604 17.2891 5.63379C17.3258 6.08402 17.3252 6.64102 17.3252 7.33008V12.6602C17.3252 13.3492 17.3258 13.9062 17.2891 14.3564C17.2516 14.8142 17.1723 15.2201 16.9805 15.5967C16.677 16.1922 16.1922 16.677 15.5967 16.9805C15.2201 17.1723 14.8142 17.2516 14.3564 17.2891C13.9062 17.3258 13.3492 17.3252 12.6602 17.3252H7.33008C6.64102 17.3252 6.08402 17.3258 5.63379 17.2891C5.17604 17.2517 4.77014 17.1722 4.39356 16.9805C3.79805 16.677 3.31321 16.1922 3.00977 15.5967C2.81796 15.2201 2.73859 14.8142 2.70117 14.3564C2.66439 13.9062 2.66504 13.3492 2.66504 12.6602V7.33008C2.66504 6.64101 2.66439 6.08402 2.70117 5.63379C2.73858 5.17601 2.81797 4.77016 3.00977 4.39356C3.31321 3.79802 3.79802 3.31321 4.39356 3.00977C4.77016 2.81797 5.17601 2.73858 5.63379 2.70117C6.08402 2.66439 6.64101 2.66504 7.33008 2.66504Z"/>',
  '<path fill="var(--color-token-main-surface-primary, Canvas)" d="M6.19629 7.86231C6.42357 7.63534 6.7752 7.60692 7.0332 7.77734L7.1377 7.86231L8.80371 9.5293C9.06329 9.78889 9.06307 10.21 8.80371 10.4697L7.1377 12.1367C6.878 12.3964 6.45599 12.3964 6.19629 12.1367C5.93686 11.8771 5.93697 11.456 6.19629 11.1963L7.39258 9.99902L6.19629 8.80371L6.11133 8.69922C5.94087 8.4411 5.96904 8.08955 6.19629 7.86231Z"/>',
  '<path fill="var(--color-token-main-surface-primary, Canvas)" d="M13.4668 11.0156C13.7699 11.0776 13.998 11.3456 13.998 11.667C13.9979 11.9883 13.7698 12.2564 13.4668 12.3184L13.333 12.332H10.833C10.466 12.3319 10.1682 12.034 10.168 11.667C10.168 11.2998 10.4659 11.0021 10.833 11.002H13.333L13.4668 11.0156Z"/>',
].join("");

/** @type {import("@codex-plusplus/sdk").Tweak} */
module.exports = {
  start(api) {
    if (api.process === "main") {
      startMain(this, api);
      return;
    }
    if (api.process === "renderer") startRenderer(this, api);
  },

  stop() {
    const state = this._state;
    state?.dispose?.();
  },
};

function startMain(self, api) {
  const mainState = globalThis[MAIN_STATE_KEY] || {};
  ensureRawOpenHandler(api, mainState);
  ensureFocusedOpenHandler(api, mainState);
  ensureTerminalOpenHandler(api, mainState);
  ensureTerminalShortcutHandler(api, mainState);
  ensureTerminalToggleShortcutHandler(api, mainState);
  ensureTerminalAlwaysOnTopHandler(api, mainState);
  ensureTerminalPopoutControlHandler(api, mainState);
  ensureTerminalWindowReportHandler(api, mainState);
  ensureTerminalMemoryWatchdog(api, mainState);
  globalThis[MAIN_STATE_KEY] = mainState;

  if (mainState.registered) {
    self._state = { dispose: () => {} };
    api.log.info("[better-terminal] main handler already registered");
    return;
  }

  const disposers = [];
  try {
    api.ipc.handle?.("open-terminal-window", async (payload) => {
      const conversationId = typeof payload?.conversationId === "string" ? payload.conversationId : "";
      if (typeof api.codex?.createWindow !== "function") {
        throw new Error("Codex++ native window API is unavailable");
      }

      const result = await openTerminalWindow(api, {
        conversationId,
        route: typeof payload?.route === "string" ? payload.route : "",
        title: typeof payload?.title === "string" ? payload.title : "Terminal",
        hostId: typeof payload?.hostId === "string" ? payload.hostId : "local",
        bounds: payload?.bounds,
      });
      return result.ref;
    });
  } catch (error) {
    mainState.registered = true;
    globalThis[MAIN_STATE_KEY] = mainState;
    self._state = { dispose: () => {} };
    api.log.warn("[better-terminal] main handler already exists; keeping existing handler", String(error));
    return;
  }

  mainState.registered = true;
  globalThis[MAIN_STATE_KEY] = mainState;
  self._state = { dispose: () => disposers.splice(0).forEach((dispose) => dispose()) };
}

function ensureTerminalShortcutHandler(api, mainState) {
  if (!mainState.terminalFocusRegistered) {
    try {
      api.ipc.handle?.(TERMINAL_FOCUS_CHANNEL, async (payload) => {
        mainState.terminalPaneFocused = Boolean(payload?.focused);
        mainState.terminalSplitActive = Boolean(payload?.splitActive);
        mainState.terminalWindowMode = Boolean(payload?.terminalWindowMode);
        return { ok: true };
      });
    } catch (error) {
      api.log.warn("[better-terminal] terminal focus handler already exists", String(error));
    }
    mainState.terminalFocusRegistered = true;
  }

  if (mainState.terminalShortcutRegistered) return;
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal shortcuts", String(error));
    return;
  }

  const clearChannel = `codexpp:${api.manifest.id}:${TERMINAL_CLEAR_SHORTCUT_CHANNEL}`;
  const closePaneChannel = `codexpp:${api.manifest.id}:${TERMINAL_CLOSE_PANE_SHORTCUT_CHANNEL}`;
  const attach = (webContents) => {
    if (!webContents || webContents.isDestroyed?.()) return;
    if (mainState.shortcutWebContentsIds?.has?.(webContents.id)) return;
    mainState.shortcutWebContentsIds ||= new Set();
    mainState.shortcutWebContentsIds.add(webContents.id);
    webContents.on("destroyed", () => mainState.shortcutWebContentsIds.delete(webContents.id));
    webContents.on("before-input-event", (event, input) => {
      if ((mainState.terminalSplitActive || mainState.terminalWindowMode) && isTerminalClosePaneInput(input)) {
        event.preventDefault();
        webContents.send(closePaneChannel, {});
        return;
      }
      if (!mainState.terminalPaneFocused) return;
      if (isTerminalClearInput(input)) {
        event.preventDefault();
        webContents.send(clearChannel, {});
        clearFocusedTerminalInWebContents(webContents, api);
      }
    });
  };

  electron.BrowserWindow.getAllWindows().forEach((window) => attach(window.webContents));
  electron.app?.on?.("browser-window-created", (_event, window) => attach(window.webContents));
  mainState.terminalShortcutRegistered = true;
}

function ensureTerminalOpenHandler(api, mainState) {
  if (mainState.terminalOpenHandlerVersion === TERMINAL_OPEN_HANDLER_VERSION) return;
  for (const channel of [LEGACY_OPEN_TERMINAL_WINDOW_CHANNEL, OPEN_TERMINAL_WINDOW_CHANNEL]) {
    replaceNamespacedIpcHandler(api, channel);
    try {
      api.ipc.handle?.(channel, async (payload = {}) => {
        return createTerminalPopoutWindow(api, payload);
      });
    } catch (error) {
      api.log.warn("[better-terminal] terminal popout handler already exists", channel, String(error));
    }
  }
  mainState.terminalOpenHandlerVersion = TERMINAL_OPEN_HANDLER_VERSION;
}

function ensureTerminalPopoutControlHandler(api, mainState) {
  if (mainState.terminalPopoutControlRegistered) return;
  for (const channel of [TERMINAL_POPOUT_REVEAL_CHANNEL, TERMINAL_POPOUT_RETURN_CHANNEL]) {
    replaceNamespacedIpcHandler(api, channel);
  }
  try {
    api.ipc.handle?.(TERMINAL_POPOUT_REVEAL_CHANNEL, async (payload = {}) => {
      const win = findTerminalPopoutWindowBySourceSession(payload?.sourceSessionId);
      if (!win || win.isDestroyed?.()) return { ok: false };
      if (win.isMinimized?.()) win.restore?.();
      win.show?.();
      win.focus?.();
      return { ok: true };
    });
  } catch (error) {
    api.log.warn("[better-terminal] terminal popout reveal handler already exists", String(error));
  }
  try {
    api.ipc.handle?.(TERMINAL_POPOUT_RETURN_CHANNEL, async (payload = {}) => {
      const win = findTerminalPopoutWindowBySourceSession(payload?.sourceSessionId);
      if (!win || win.isDestroyed?.()) return { ok: false };
      win.close?.();
      return { ok: true };
    });
  } catch (error) {
    api.log.warn("[better-terminal] terminal popout return handler already exists", String(error));
  }
  mainState.terminalPopoutControlRegistered = true;
}

function findTerminalPopoutWindowBySourceSession(sourceSessionId) {
  if (typeof sourceSessionId !== "string" || !sourceSessionId) return null;
  let electron;
  try {
    electron = require("electron");
  } catch {
    return null;
  }
  const windows = electron.BrowserWindow?.getAllWindows?.() || [];
  for (const win of windows) {
    const url = win?.webContents?.getURL?.() || "";
    if (!url) continue;
    try {
      const parsed = new URL(url);
      const route = parsed.searchParams.get("initialRoute");
      const routeUrl = route ? new URL(route, "app://codex") : null;
      const isTerminalWindow =
        parsed.searchParams.get("codexppTerminalWindow") === "1" ||
        routeUrl?.searchParams?.get("codexppTerminalWindow") === "1";
      const candidate =
        parsed.searchParams.get("codexppTerminalSourceSessionId") ||
        routeUrl?.searchParams?.get("codexppTerminalSourceSessionId");
      if (isTerminalWindow && candidate === sourceSessionId) return win;
    } catch {}
  }
  return null;
}

async function createTerminalPopoutWindow(api, payload = {}, sourceWebContents = null) {
  const conversationId = typeof payload.conversationId === "string" ? payload.conversationId : "";
  if (typeof api.codex?.createWindow !== "function") {
    throw new Error("Codex++ native window API is unavailable");
  }

  const title = typeof payload.title === "string" && payload.title.trim() ? payload.title.trim() : "Terminal";
  const result = await openTerminalWindow(api, {
    conversationId,
    route: typeof payload.route === "string" ? payload.route : "",
    title,
    hostId: typeof payload.hostId === "string" ? payload.hostId : "local",
    bounds: payload.bounds,
    sourceSessionId: typeof payload.sourceSessionId === "string" ? payload.sourceSessionId : null,
    popoutId: typeof payload.popoutId === "string" ? payload.popoutId : null,
  }, sourceWebContents);
  return { conversationId, webContentsId: result.ref.webContentsId };
}

function ensureTerminalWindowReportHandler(api, mainState) {
  if (mainState.terminalWindowReportApiChannel !== TERMINAL_WINDOW_REPORT_API_CHANNEL) {
    try {
      api.ipc.handle?.(TERMINAL_WINDOW_REPORT_API_CHANNEL, (payload = {}) => {
        recordTerminalWindowReport(mainState, null, payload);
        return { ok: true };
      });
      mainState.terminalWindowReportApiChannel = TERMINAL_WINDOW_REPORT_API_CHANNEL;
    } catch (error) {
      mainState.terminalWindowReportApiChannel = TERMINAL_WINDOW_REPORT_API_CHANNEL;
      api.log.warn("[better-terminal] terminal window report API handler already exists", String(error));
    }
  }
  if (mainState.terminalWindowReportChannel === TERMINAL_WINDOW_REPORT_CHANNEL) return;
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal window reports", String(error));
    return;
  }

  try {
    electron.ipcMain.handle(TERMINAL_WINDOW_REPORT_CHANNEL, (event, payload = {}) => {
      recordTerminalWindowReport(mainState, event.sender, payload);
      return { ok: true };
    });
    mainState.terminalWindowReportChannel = TERMINAL_WINDOW_REPORT_CHANNEL;
  } catch (error) {
    mainState.terminalWindowReportChannel = TERMINAL_WINDOW_REPORT_CHANNEL;
    api.log.warn("[better-terminal] terminal window report handler already exists", String(error));
  }
}

function recordTerminalWindowReport(mainState, webContents, payload = {}) {
  if (webContents?.isDestroyed?.()) return;
  mainState.terminalWindowReports ||= new Map();
  mainState.terminalSessionWebContents ||= new Map();
  const webContentsId = webContents?.id || Number(payload.webContentsId) || null;
  if (!webContentsId) return;
  const sessionIds = Array.isArray(payload.sessionIds)
    ? payload.sessionIds.filter((value) => typeof value === "string" && value.length > 0)
    : [];
  const report = {
    webContentsId,
    focused: Boolean(payload.focused),
    hasTerminal: Boolean(payload.hasTerminal || sessionIds.length),
    sessionIds,
    conversationId: typeof payload.conversationId === "string" ? payload.conversationId : null,
    updatedAt: Date.now(),
  };
  mainState.terminalWindowReports.set(webContentsId, report);
  for (const sessionId of sessionIds) mainState.terminalSessionWebContents.set(sessionId, webContentsId);
}

function ensureTerminalToggleShortcutHandler(api, mainState) {
  if (mainState.terminalToggleShortcutApiChannel !== TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL) {
    try {
      api.ipc.handle?.(TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL, async () => {
        let electron;
        try {
          electron = require("electron");
        } catch {
          return { ok: false };
        }
        const window = await terminalToggleTargetWindow(electron);
        sendTrustedTerminalToggle(window?.webContents);
        return { ok: true };
      });
      mainState.terminalToggleShortcutApiChannel = TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL;
    } catch (error) {
      mainState.terminalToggleShortcutApiChannel = TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL;
      api.log.warn("[better-terminal] terminal toggle shortcut API handler already exists", String(error));
    }
  }

  if (mainState.terminalToggleShortcutChannel === TERMINAL_TOGGLE_SHORTCUT_CHANNEL) return;
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal toggle shortcut", String(error));
    return;
  }

  try {
    electron.ipcMain.handle(TERMINAL_TOGGLE_SHORTCUT_CHANNEL, (event) => {
      sendTrustedTerminalToggle(event.sender);
      return { ok: true };
    });
    mainState.terminalToggleShortcutChannel = TERMINAL_TOGGLE_SHORTCUT_CHANNEL;
  } catch (error) {
    mainState.terminalToggleShortcutChannel = TERMINAL_TOGGLE_SHORTCUT_CHANNEL;
    api.log.warn("[better-terminal] terminal toggle shortcut handler already exists", String(error));
  }
}

function ensureTerminalAlwaysOnTopHandler(api, mainState) {
  if (mainState.terminalAlwaysOnTopChannel === TERMINAL_ALWAYS_ON_TOP_CHANNEL) return;
  try {
    api.ipc.handle?.(TERMINAL_ALWAYS_ON_TOP_CHANNEL, async (payload = {}) => {
      let electron;
      try {
        electron = require("electron");
      } catch {
        return { ok: false, alwaysOnTop: false };
      }
      const wc = Number(payload.webContentsId)
        ? electron.webContents?.fromId?.(Number(payload.webContentsId))
        : null;
      const window = (wc && !wc.isDestroyed?.() ? electron.BrowserWindow?.fromWebContents?.(wc) : null) ||
        electron.BrowserWindow?.getFocusedWindow?.();
      if (!window || window.isDestroyed?.()) return { ok: false, alwaysOnTop: false };
      const next = !window.isAlwaysOnTop?.();
      window.setAlwaysOnTop?.(next);
      return { ok: true, alwaysOnTop: next };
    });
    mainState.terminalAlwaysOnTopChannel = TERMINAL_ALWAYS_ON_TOP_CHANNEL;
  } catch (error) {
    mainState.terminalAlwaysOnTopChannel = TERMINAL_ALWAYS_ON_TOP_CHANNEL;
    api.log.warn("[better-terminal] terminal always-on-top handler already exists", String(error));
  }
}

function sendTrustedTerminalToggle(webContents) {
  if (!webContents || webContents.isDestroyed?.()) return;
  try {
    const electron = require("electron");
    const window = electron.BrowserWindow?.fromWebContents?.(webContents);
    if (invokeTerminalMenuToggle(electron, window)) return;
  } catch {}
  webContents.sendInputEvent({ type: "keyDown", keyCode: "J", modifiers: ["meta"] });
  webContents.sendInputEvent({ type: "keyUp", keyCode: "J", modifiers: ["meta"] });
}

function invokeTerminalMenuToggle(electron, window) {
  const menu = electron.Menu?.getApplicationMenu?.();
  if (!menu || !window || window.isDestroyed?.()) return false;
  const items = [];
  const visit = (children) => {
    for (const item of children || []) {
      items.push(item);
      if (item?.submenu?.items) visit(item.submenu.items);
    }
  };
  visit(menu.items);
  const target = items.find((item) => {
    if (!item || typeof item.click !== "function" || item.enabled === false) return false;
    const label = compactText(`${item.label || ""} ${item.sublabel || ""} ${item.role || ""}`);
    const accelerator = String(item.accelerator || "");
    if (/terminal/i.test(label) && /\b(toggle|show|hide|open|panel|pane|terminal)\b/i.test(label)) return true;
    return /(?:CommandOrControl|Cmd|Command|Control)\\+J/i.test(accelerator);
  });
  if (!target) return false;
  try {
    window.show?.();
    window.focus?.();
  } catch {}
  try {
    target.click(target, window, { type: "keyDown", modifiers: ["meta"], keyCode: "J" });
    return true;
  } catch {
    return false;
  }
}

async function terminalToggleTargetWindow(electron) {
  const focused = electron.BrowserWindow?.getFocusedWindow?.() || null;
  if (await windowHasTerminalWindowMode(focused)) return focused;
  for (const window of electron.BrowserWindow?.getAllWindows?.() || []) {
    if (await windowHasTerminalWindowMode(window)) return window;
  }
  return focused || electron.BrowserWindow?.getAllWindows?.()?.[0] || null;
}

async function windowHasTerminalWindowMode(window) {
  try {
    if (!window || window.isDestroyed?.() || window.webContents?.isDestroyed?.()) return false;
    return Boolean(await window.webContents.executeJavaScript(
      `document.documentElement.getAttribute(${JSON.stringify(TERMINAL_WINDOW_ATTR)}) === "true"`,
      true,
    ));
  } catch {
    return false;
  }
}

function isTerminalClearInput(input) {
  if (!input || input.type !== "keyDown") return false;
  const hasPrimary = Boolean(input.meta || input.control);
  if (!hasPrimary || (input.meta && input.control) || input.alt || input.shift) return false;
  return String(input.code || "") === "KeyK" || String(input.key || "").toLowerCase() === "k";
}

function isTerminalClosePaneInput(input) {
  if (!input || input.type !== "keyDown") return false;
  const hasPrimary = Boolean(input.meta || input.control);
  if (!hasPrimary || (input.meta && input.control) || input.alt || input.shift) return false;
  return String(input.code || "") === "KeyW" || String(input.key || "").toLowerCase() === "w";
}

function clearFocusedTerminalInWebContents(webContents, api) {
  webContents.executeJavaScript(
    `(() => {
      const panel = document.activeElement?.closest?.("[data-codex-terminal][id^='terminal-panel-'], [id^='terminal-panel-']") ||
        document.querySelector("[data-codex-terminal][id^='terminal-panel-'], [id^='terminal-panel-']");
      const sessionId = panel?.id?.replace(/^terminal-panel-/, "");
      const manager = globalThis.__codexppTerminalManager;
      if (!sessionId || !manager) return false;
      manager.replaceSnapshotBuffer?.(sessionId, "");
      const listener = manager.listeners?.get?.(sessionId);
      if (listener?.onData) {
        listener.onData("\\x1b[3J\\x1b[H\\x1b[2J");
        return true;
      }
      manager.write?.(sessionId, "\\x0c");
      return true;
    })()`,
    true,
  ).catch((error) => {
    api.log.warn("[better-terminal] failed to clear terminal from main", String(error));
  });
}

function ensureTerminalMemoryWatchdog(api, mainState) {
  mainState.memoryWatchdogSettings ||= readMemoryWatchdogSettings(api);
  mainState.memoryWatchdogFrozen ||= new Map();

  if (mainState.memoryWatchdogVersion !== TERMINAL_MEMORY_WATCHDOG_VERSION) {
    if (mainState.memoryWatchdogTimer) clearInterval(mainState.memoryWatchdogTimer);
    mainState.memoryWatchdogTimer = null;
    mainState.memoryWatchdogHandlerRegistered = false;
    mainState.memoryWatchdogFrozen = new Map();
    mainState.memoryWatchdogSettings = readMemoryWatchdogSettings(api);
    mainState.memoryWatchdogVersion = TERMINAL_MEMORY_WATCHDOG_VERSION;
  }

  if (!mainState.memoryWatchdogHandlerRegistered) {
    try {
      api.ipc.handle?.(TERMINAL_MEMORY_WATCHDOG_CHANNEL, async (payload = {}) => {
        const action = typeof payload.action === "string" ? payload.action : "status";
        if (action === "settings") {
          updateMemoryWatchdogSettings(api, mainState, payload);
        } else if (action === "freeze") {
          const usage = terminalUsageForSession(String(payload.sessionId || ""));
          if (usage) freezeTerminalProcessTree(api, mainState, usage, "manual");
        } else if (action === "resume") {
          resumeFrozenTerminal(api, mainState, String(payload.sessionId || ""));
        } else if (action === "kill") {
          killTerminalProcessTree(api, mainState, String(payload.sessionId || ""));
        }
        return memoryWatchdogStatus(mainState);
      });
      mainState.memoryWatchdogHandlerChannel = TERMINAL_MEMORY_WATCHDOG_CHANNEL;
    } catch (error) {
      api.log.warn("[better-terminal] memory watchdog handler already exists", String(error));
    }
    mainState.memoryWatchdogHandlerRegistered = true;
  }

  if (mainState.memoryWatchdogTimer) return;
  mainState.memoryWatchdogTimer = setInterval(() => {
    sampleTerminalMemoryWatchdog(api, mainState);
  }, MEMORY_WATCHDOG_INTERVAL_MS);
  mainState.memoryWatchdogTimer.unref?.();
  sampleTerminalMemoryWatchdog(api, mainState);
}

function readMemoryWatchdogSettings(api) {
  return {
    enabled: mainReadBool(api, "memory-watchdog-enabled", DEFAULT_MEMORY_WATCHDOG_ENABLED),
    thresholdPercent: mainReadNumber(api, "memory-watchdog-threshold-percent", DEFAULT_MEMORY_WATCHDOG_THRESHOLD_PERCENT),
  };
}

function mainReadBool(api, key, fallback) {
  try {
    const value = api.storage?.get?.(key, fallback);
    return typeof value === "boolean" ? value : Boolean(value ?? fallback);
  } catch {
    return fallback;
  }
}

function mainReadNumber(api, key, fallback) {
  try {
    const value = Number(api.storage?.get?.(key, fallback));
    return Number.isFinite(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

function updateMemoryWatchdogSettings(api, mainState, payload) {
  const enabled = typeof payload.enabled === "boolean" ? payload.enabled : mainState.memoryWatchdogSettings.enabled;
  const thresholdPercent = clampMemoryThreshold(payload.thresholdPercent ?? mainState.memoryWatchdogSettings.thresholdPercent);
  mainState.memoryWatchdogSettings = { enabled, thresholdPercent };
  try {
    api.storage?.set?.("memory-watchdog-enabled", enabled);
    api.storage?.set?.("memory-watchdog-threshold-percent", thresholdPercent);
  } catch {}
}

function sampleTerminalMemoryWatchdog(api, mainState) {
  const settings = mainState.memoryWatchdogSettings || {};
  if (!settings.enabled) return;
  const thresholdBytes = Math.floor(totalSystemMemoryBytes() * clampMemoryThreshold(settings.thresholdPercent) / 100);
  if (!thresholdBytes) return;
  const usages = terminalProcessUsages();
  pruneStaleFrozenTerminals(mainState, usages);
  for (const usage of usages) {
    if (!usage.sessionId || !usage.pid) continue;
    if (usage.rssBytes >= thresholdBytes && !mainState.memoryWatchdogFrozen.has(usage.sessionId)) {
      freezeTerminalProcessTree(api, mainState, { ...usage, thresholdBytes }, "threshold");
    }
  }
}

function pruneStaleFrozenTerminals(mainState, usages) {
  const currentPids = new Set(usages.flatMap((usage) => usage.pids || []));
  for (const [sessionId, record] of mainState.memoryWatchdogFrozen || []) {
    const stillPresent = (record.pids || []).every((pid) => currentPids.has(pid));
    if (!stillPresent) mainState.memoryWatchdogFrozen.delete(sessionId);
  }
}

function memoryWatchdogStatus(mainState) {
  const settings = mainState.memoryWatchdogSettings || {};
  const table = processTable();
  return {
    enabled: Boolean(settings.enabled),
    thresholdPercent: clampMemoryThreshold(settings.thresholdPercent),
    thresholdBytes: Math.floor(totalSystemMemoryBytes() * clampMemoryThreshold(settings.thresholdPercent) / 100),
    frozen: Array.from((mainState.memoryWatchdogFrozen || new Map()).values()),
    sessions: terminalProcessUsages(table),
  };
}

function terminalProcessUsages(table = processTable()) {
  return terminalProcessSessions(table).map((session) => {
    const pid = terminalSessionPid(session);
    const tree = pid ? processTreeUsage(table, pid) : { pids: [], rssBytes: 0 };
    return {
      sessionId: String(session?.id || session?.sessionId || ""),
      pid,
      pids: tree.pids,
      rssBytes: tree.rssBytes,
      cwd: typeof session?.cwd === "string" ? session.cwd : "",
      shell: typeof session?.shell === "string" ? session.shell : "",
      title: typeof session?.title === "string" ? session.title : "",
    };
  }).filter((usage) => usage.sessionId);
}

function terminalUsageForSession(sessionId) {
  return terminalProcessUsages().find((usage) => usage.sessionId === sessionId) || null;
}

function terminalProcessSessions(table) {
  const manager = globalThis.__codexppTerminalProcessManager;
  const sessions = manager?.sessions;
  if (sessions instanceof Map && sessions.size > 0) return Array.from(sessions.values());
  return fallbackTerminalProcessSessions(table);
}

function fallbackTerminalProcessSessions(table) {
  const shells = new Set(["bash", "fish", "sh", "zsh"]);
  return (table || [])
    .filter((row) => row.ppid === process.pid && shells.has(processCommandName(row.command)))
    .map((row) => ({
      id: `pid:${row.pid}`,
      sessionId: `pid:${row.pid}`,
      cwd: "",
      shell: processCommandName(row.command),
      title: "",
      backend: { pty: { pid: row.pid } },
    }));
}

function processCommandName(command) {
  const first = String(command || "").trim().split(/\s+/)[0] || "";
  return first.split(/[\\/]/).pop() || first;
}

function terminalSessionPid(session) {
  const direct = Number(session?.backend?.pty?.pid);
  if (Number.isInteger(direct) && direct > 0) return direct;
  return findPidInObject(session?.backend, new Set());
}

function findPidInObject(value, seen) {
  if (!value || typeof value !== "object" || seen.has(value)) return null;
  seen.add(value);
  const pid = Number(value.pid);
  if (Number.isInteger(pid) && pid > 0) return pid;
  for (const next of Object.values(value)) {
    const found = findPidInObject(next, seen);
    if (found) return found;
  }
  return null;
}

function processTable() {
  try {
    const { execFileSync } = require("node:child_process");
    const output = execFileSync("ps", ["-axo", "pid=,ppid=,rss=,command="], {
      encoding: "utf8",
      timeout: 1500,
      maxBuffer: 1024 * 1024 * 8,
    });
    return output.split(/\r?\n/).map((line) => {
      const match = line.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s*(.*)$/);
      if (!match) return null;
      return { pid: Number(match[1]), ppid: Number(match[2]), rssBytes: Number(match[3]) * 1024, command: match[4] || "" };
    }).filter(Boolean);
  } catch {
    return [];
  }
}

function processTreeUsage(table, rootPid) {
  const children = new Map();
  const byPid = new Map();
  for (const row of table) {
    byPid.set(row.pid, row);
    if (!children.has(row.ppid)) children.set(row.ppid, []);
    children.get(row.ppid).push(row.pid);
  }
  const pids = [];
  const queue = [rootPid];
  const seen = new Set();
  let rssBytes = 0;
  while (queue.length > 0) {
    const pid = queue.shift();
    if (!pid || seen.has(pid)) continue;
    seen.add(pid);
    pids.push(pid);
    rssBytes += byPid.get(pid)?.rssBytes || 0;
    queue.push(...(children.get(pid) || []));
  }
  return { pids, rssBytes };
}

function freezeTerminalProcessTree(api, mainState, usage, reason) {
  const pids = Array.isArray(usage.pids) && usage.pids.length ? usage.pids : [usage.pid].filter(Boolean);
  for (const pid of pids.slice().reverse()) sendSignal(pid, "SIGSTOP");
  const record = {
    sessionId: usage.sessionId,
    pid: usage.pid,
    pids,
    rssBytes: usage.rssBytes || 0,
    thresholdBytes: usage.thresholdBytes || memoryWatchdogStatus(mainState).thresholdBytes,
    reason,
    frozenAt: Date.now(),
  };
  mainState.memoryWatchdogFrozen.set(usage.sessionId, record);
  api.log.warn("[better-terminal] froze terminal process tree for excessive memory", JSON.stringify(record));
  if (reason === "threshold") showTerminalMemoryWatchdogAlert(api, mainState, record);
}

function showTerminalMemoryWatchdogAlert(api, mainState, record) {
  const used = formatMemoryBytes(record?.rssBytes || 0);
  const threshold = formatMemoryBytes(record?.thresholdBytes || 0);
  const title = "Terminal paused to protect Codex";
  const message = "Codex paused a terminal using too much memory.";
  const detail = `This terminal reached ${used}, above your ${threshold} limit. The process tree is paused so Codex stays responsive. You can resume it or end it from Better Terminal settings.`;

  try {
    const electron = require("electron");
    Promise.resolve(terminalAlertWindow(electron, mainState, record)).then((window) => {
      const options = {
        type: "warning",
        title,
        message,
        detail,
        buttons: ["OK"],
        defaultId: 0,
        noLink: true,
      };
      const shown = window
        ? electron.dialog?.showMessageBox?.(window, options)
        : electron.dialog?.showMessageBox?.(options);
      if (shown) {
        shown.catch?.((error) => {
          api.log.warn("[better-terminal] failed to show memory watchdog alert", String(error));
        });
      }
    }).catch((error) => {
      api.log.warn("[better-terminal] failed to resolve memory watchdog alert window", String(error));
    });
    return;
  } catch (error) {
    api.log.warn("[better-terminal] failed to show memory watchdog alert", String(error));
  }

  try {
    const electron = require("electron");
    if (electron.Notification?.isSupported?.()) {
      new electron.Notification({ title, body: `${message}. ${detail}` }).show();
    }
  } catch (error) {
    api.log.warn("[better-terminal] failed to show memory watchdog notification", String(error));
  }
}

async function terminalAlertWindow(electron, mainState, record) {
  const reports = freshTerminalWindowReports(mainState);
  const mappedWebContentsId = mainState.terminalSessionWebContents?.get?.(record?.sessionId);
  const mapped = mappedWebContentsId ? electron.webContents?.fromId?.(mappedWebContentsId) : null;
  if (mapped && !mapped.isDestroyed?.()) return electron.BrowserWindow?.fromWebContents?.(mapped) || null;

  const focusedTerminalReport = reports.find((report) => report.focused && report.hasTerminal);
  const terminalReport = focusedTerminalReport || reports.find((report) => report.hasTerminal);
  const wc = terminalReport ? electron.webContents?.fromId?.(terminalReport.webContentsId) : null;
  if (wc && !wc.isDestroyed?.()) return electron.BrowserWindow?.fromWebContents?.(wc) || null;
  const inspected = await inspectTerminalWindows(electron, record?.sessionId);
  if (inspected) return inspected;
  return electron.BrowserWindow?.getFocusedWindow?.() || electron.BrowserWindow?.getAllWindows?.()?.[0] || null;
}

async function inspectTerminalWindows(electron, sessionId) {
  const windows = electron.BrowserWindow?.getAllWindows?.() || [];
  const candidates = [];
  for (const window of windows) {
    if (!window || window.isDestroyed?.() || window.webContents?.isDestroyed?.()) continue;
    try {
      const info = await window.webContents.executeJavaScript(terminalWindowInspectionExpression(sessionId), true);
      if (info?.hasSession) return window;
      if (info?.focusedTerminal) candidates.unshift(window);
      else if (info?.hasTerminal) candidates.push(window);
    } catch {}
  }
  return candidates[0] || null;
}

function terminalWindowInspectionExpression(sessionId) {
  return `(() => {
    const wanted = ${JSON.stringify(sessionId || "")};
    const sessionIdFromNode = (node) => {
      const raw =
        node?.id ||
        node?.getAttribute?.("id") ||
        node?.closest?.("[id^='terminal-panel-']")?.id ||
        node?.closest?.("[data-tab-id^='terminal:']")?.getAttribute("data-tab-id") ||
        "";
      const match = /^terminal(?::|-panel-)(.+)$/.exec(raw);
      return match?.[1] || null;
    };
    const nodes = Array.from(document.querySelectorAll("[data-codex-terminal], [id^='terminal-panel-'], .xterm, [data-tab-id^='terminal:']"));
    const sessionIds = nodes.map(sessionIdFromNode).filter(Boolean);
    const focused = document.activeElement?.closest?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm, [data-tab-id^='terminal:']");
    return {
      hasTerminal: nodes.length > 0,
      focusedTerminal: Boolean(focused),
      hasSession: Boolean(wanted && sessionIds.includes(wanted)),
    };
  })()`;
}

function freshTerminalWindowReports(mainState) {
  const now = Date.now();
  const reports = Array.from((mainState.terminalWindowReports || new Map()).values())
    .filter((report) => now - report.updatedAt < 30_000);
  const liveWebContentsIds = new Set(reports.map((report) => report.webContentsId));
  for (const key of mainState.terminalWindowReports?.keys?.() || []) {
    if (!liveWebContentsIds.has(key)) mainState.terminalWindowReports.delete(key);
  }
  for (const [sessionId, webContentsId] of mainState.terminalSessionWebContents || []) {
    if (!liveWebContentsIds.has(webContentsId)) mainState.terminalSessionWebContents.delete(sessionId);
  }
  return reports;
}

function formatMemoryBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  if (value >= 1024 ** 2) return `${Math.round(value / 1024 ** 2)} MB`;
  if (value >= 1024) return `${Math.round(value / 1024)} KB`;
  return `${Math.round(value)} B`;
}

function resumeFrozenTerminal(api, mainState, sessionId) {
  const record = mainState.memoryWatchdogFrozen.get(sessionId);
  if (!record) return;
  for (const pid of record.pids || []) sendSignal(pid, "SIGCONT");
  mainState.memoryWatchdogFrozen.delete(sessionId);
  api.log.info("[better-terminal] resumed frozen terminal process tree", sessionId);
}

function killTerminalProcessTree(api, mainState, sessionId) {
  const record = mainState.memoryWatchdogFrozen.get(sessionId);
  const usage = record || terminalUsageForSession(sessionId);
  if (!usage) return;
  const pids = Array.isArray(usage.pids) && usage.pids.length ? usage.pids : [usage.pid].filter(Boolean);
  for (const pid of pids.slice().reverse()) sendSignal(pid, "SIGTERM");
  mainState.memoryWatchdogFrozen.delete(sessionId);
  api.log.warn("[better-terminal] killed terminal process tree", sessionId);
}

function sendSignal(pid, signal) {
  try {
    process.kill(pid, signal);
  } catch {}
}

function totalSystemMemoryBytes() {
  try {
    return require("node:os").totalmem();
  } catch {
    return 0;
  }
}

function clampMemoryThreshold(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return DEFAULT_MEMORY_WATCHDOG_THRESHOLD_PERCENT;
  return Math.max(1, Math.min(95, Math.round(number)));
}

function ensureFocusedOpenHandler(api, mainState) {
  if (mainState.focusedOpenMessageRegistered) return;
  try {
    api.ipc.handle?.("open-terminal-window-focused-message", async (payload) => {
      let electron;
      try {
        electron = require("electron");
      } catch (error) {
        throw new Error(`Cannot require electron: ${String(error)}`);
      }

      const wc =
        electron.BrowserWindow.getFocusedWindow()?.webContents ||
        electron.webContents
          ?.getAllWebContents?.()
          ?.find((candidate) => {
            try {
              const url = candidate.getURL();
              return url.startsWith("app://-/index.html") && !url.includes("initialRoute=");
            } catch {
              return false;
            }
          });

      if (!wc || wc.isDestroyed()) throw new Error("No focused Codex webContents for terminal popout");
      const metadata = await wc.executeJavaScript(
        pageWorldTerminalMetadataExpression(),
        true,
      );
      const conversationId =
        typeof payload?.conversationId === "string" && payload.conversationId
          ? payload.conversationId
          : typeof metadata?.conversationId === "string" ? metadata.conversationId : "";
      if (typeof api.codex?.createWindow !== "function") {
        throw new Error("Codex++ native window API is unavailable");
      }

      const result = await openTerminalWindow(api, {
        conversationId,
        route: typeof payload?.route === "string" ? payload.route : "",
        title: typeof payload?.title === "string" ? payload.title : "Terminal",
        hostId: typeof metadata?.hostId === "string" ? metadata.hostId : "local",
        bounds: payload?.bounds,
      }, wc);
      return { conversationId, webContentsId: result.ref.webContentsId };
    });
    mainState.focusedOpenMessageRegistered = true;
  } catch (error) {
    mainState.focusedOpenMessageRegistered = true;
    api.log.warn("[better-terminal] focused terminal popout handler already exists", String(error));
  }
}

function ensureRawOpenHandler(api, mainState) {
  if (mainState.rawOpenVersion === RAW_OPEN_HANDLER_VERSION) return;
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for raw terminal popout handler", String(error));
    return;
  }

  const handler = async (event, payload) => {
      let conversationId = typeof payload?.conversationId === "string" ? payload.conversationId : "";
      if (!conversationId) {
        conversationId = await event.sender.executeJavaScript(pageWorldConversationIdExpression(), true);
      }
      if (typeof api.codex?.createWindow !== "function") {
        throw new Error("Codex++ native window API is unavailable");
      }

      const result = await openTerminalWindow(api, {
        conversationId,
        route: typeof payload?.route === "string" ? payload.route : "",
        title: typeof payload?.title === "string" ? payload.title : "Terminal",
        hostId: typeof payload?.hostId === "string" ? payload.hostId : "local",
        bounds: payload?.bounds,
        sourceSessionId: typeof payload?.sourceSessionId === "string" ? payload.sourceSessionId : null,
        popoutId: typeof payload?.popoutId === "string" ? payload.popoutId : null,
      }, event.sender);
      return { webContentsId: result.ref.webContentsId };
  };

  for (const channel of [LEGACY_RAW_OPEN_CHANNEL, RAW_OPEN_CHANNEL]) {
    try {
      electron.ipcMain.removeHandler?.(channel);
    } catch {}
    try {
      electron.ipcMain.handle(channel, handler);
    } catch (error) {
      api.log.warn("[better-terminal] raw terminal popout handler already exists", channel, String(error));
    }
  }
  mainState.rawOpenVersion = RAW_OPEN_HANDLER_VERSION;
}

function replaceNamespacedIpcHandler(api, channel) {
  try {
    const { ipcMain } = require("electron");
    ipcMain.removeHandler?.(`codexpp:${api.manifest.id}:${channel}`);
  } catch {}
}

async function openTerminalWindow(api, payload, sourceWebContents = null) {
  const title = typeof payload?.title === "string" && payload.title.trim() ? payload.title.trim() : "Terminal";
  const conversationId = typeof payload?.conversationId === "string" ? payload.conversationId : "";
  const route = terminalWindowInitialRoute(conversationId, title, payload);

  const overlayResult = null;
  if (overlayResult) {
    prepareTerminalPopoutPresentation(api, overlayResult.ref.webContentsId);
    notifyTerminalPopoutWindow(api, overlayResult.ref.webContentsId, {
      conversationId,
      title,
      sourceSessionId: typeof payload?.sourceSessionId === "string" ? payload.sourceSessionId : null,
      popoutId: typeof payload?.popoutId === "string" ? payload.popoutId : null,
    });
    return overlayResult;
  }

  if (typeof api.codex?.createWindow !== "function") {
    throw new Error("Codex++ native window API is unavailable");
  }

  const directResult = null;
  if (directResult) {
    prepareTerminalPopoutPresentation(api, directResult.ref.webContentsId, { title });
    notifyTerminalPopoutWindow(api, directResult.ref.webContentsId, {
      conversationId,
      title,
      sourceSessionId: typeof payload?.sourceSessionId === "string" ? payload.sourceSessionId : null,
      popoutId: typeof payload?.popoutId === "string" ? payload.popoutId : null,
    });
    return directResult;
  }

  const ref = await api.codex.createWindow({
    route,
    hostId: typeof payload?.hostId === "string" ? payload.hostId : "local",
    appearance: "primary",
    bounds: payload?.bounds,
    titleBarStyle: "hidden",
    trafficLightPosition: { x: 14, y: 13 },
    backgroundColor: TERMINAL_WINDOW_BACKGROUND,
    title,
    show: false,
  });

  loadTerminalWindowUrl(api, ref.webContentsId, {
    conversationId,
    route,
    title,
    hostId: typeof payload?.hostId === "string" ? payload.hostId : "local",
    sourceSessionId: typeof payload?.sourceSessionId === "string" ? payload.sourceSessionId : null,
    popoutId: typeof payload?.popoutId === "string" ? payload.popoutId : null,
  });
  prepareTerminalPopoutPresentation(api, ref.webContentsId, { title });
  notifyTerminalPopoutWindow(api, ref.webContentsId, {
    conversationId,
    title,
    sourceSessionId: typeof payload?.sourceSessionId === "string" ? payload.sourceSessionId : null,
    popoutId: typeof payload?.popoutId === "string" ? payload.popoutId : null,
  });
  return { ref };
}

async function createDirectTerminalWindow(api, payload, sourceWebContents = null) {
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for direct terminal window", String(error));
    return null;
  }
  const services = globalThis.__codexpp_window_services__;
  const windowManager = services?.windowManager;
  const preload = windowManager?.options?.preloadPath;
  if (!services || !windowManager || !preload || typeof electron.BrowserWindow !== "function") return null;

  const title = typeof payload?.title === "string" && payload.title.trim() ? payload.title.trim() : "Terminal";
  const conversationId = typeof payload?.conversationId === "string" ? payload.conversationId : "";
  const hostId = typeof payload?.hostId === "string" ? payload.hostId : "local";
  const bounds = payload?.bounds || centeredBounds(940, 660);
  const parent = sourceWebContents && !sourceWebContents.isDestroyed?.()
    ? electron.BrowserWindow?.fromWebContents?.(sourceWebContents)
    : electron.BrowserWindow?.getFocusedWindow?.();

  let win = null;
  try {
    win = new electron.BrowserWindow({
      x: bounds.x,
      y: bounds.y,
      width: bounds.width,
      height: bounds.height,
      minWidth: 420,
      minHeight: 300,
      show: false,
      title,
      parent: parent && !parent.isDestroyed?.() ? parent : undefined,
      backgroundColor: TERMINAL_WINDOW_BACKGROUND,
      titleBarStyle: "hidden",
      trafficLightPosition: { x: 14, y: 13 },
      webPreferences: {
        preload,
        contextIsolation: true,
        nodeIntegration: false,
        spellcheck: false,
        devTools: Boolean(windowManager.options?.allowDevtools),
      },
    });
    windowManager.registerWindow?.(win, hostId, false, "secondary");
    services.getContext?.(hostId)?.registerWindow?.(win);
    await win.loadURL(terminalWindowAppUrl(conversationId, title, hostId, payload));
    return { ref: { windowId: win.id, webContentsId: win.webContents.id } };
  } catch (error) {
    api.log.warn("[better-terminal] direct terminal window failed", String(error));
    try {
      if (win && !win.isDestroyed?.()) win.destroy();
    } catch {}
    return null;
  }
}

function loadTerminalWindowUrl(api, webContentsId, payload) {
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal URL load", String(error));
    return;
  }

  const wc = electron.webContents?.fromId?.(webContentsId);
  if (!wc || wc.isDestroyed?.()) return;
  try {
    wc.loadURL(terminalWindowAppUrl(payload.conversationId, payload.title, payload.hostId, payload)).then?.(() => {
      prepareTerminalPopoutPresentation(api, webContentsId, { title: payload.title || "Terminal" });
    }).catch?.((error) => {
      api.log.warn("[better-terminal] failed to load terminal popout URL", String(error));
    });
  } catch (error) {
    api.log.warn("[better-terminal] failed to load terminal popout URL", String(error));
  }
}

async function openTerminalThreadOverlay(api, payload, sourceWebContents) {
  const manager = globalThis.__codexpp_window_services__?.threadOverlayManager;
  if (typeof manager?.open !== "function") return null;
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for thread overlay popout", String(error));
    return null;
  }

  const conversationId = typeof payload?.conversationId === "string" ? payload.conversationId : "";
  const sender = sourceWebContents && !sourceWebContents.isDestroyed?.()
    ? sourceWebContents
    : electron.BrowserWindow?.getFocusedWindow?.()?.webContents;
  if (!sender || sender.isDestroyed?.()) return null;

  const beforeIds = new Set((electron.webContents?.getAllWebContents?.() || []).map((wc) => wc.id));
  try {
    await manager.open(sender, {
      hostId: typeof payload?.hostId === "string" ? payload.hostId : "local",
      conversationId,
      title: typeof payload?.title === "string" ? payload.title : "Terminal",
    });
  } catch (error) {
    api.log.warn("[better-terminal] thread overlay popout failed", String(error));
    return null;
  }

  const wc = await waitForThreadOverlayWebContents(electron, conversationId, beforeIds);
  if (wc && !wc.isDestroyed?.()) {
    try {
      await wc.loadURL(terminalWindowAppUrl(
        conversationId,
        typeof payload?.title === "string" ? payload.title : "Terminal",
        typeof payload?.hostId === "string" ? payload.hostId : "local",
        payload,
      ));
    } catch (error) {
      api.log.warn("[better-terminal] failed to load terminal route in overlay popout", String(error));
    }
  }
  return wc ? { ref: { webContentsId: wc.id } } : null;
}

function waitForThreadOverlayWebContents(electron, conversationId, beforeIds) {
  const encoded = encodeURIComponent(conversationId);
  const matches = (wc) => {
    try {
      const url = wc.getURL?.() || "";
      return (
        url.includes(`/thread-overlay/${conversationId}`) ||
        url.includes(`/thread-overlay/${encoded}`) ||
        url.includes(`%2Fthread-overlay%2F${encoded}`)
      );
    } catch {
      return false;
    }
  };
  return new Promise((resolve) => {
    let attempts = 0;
    const poll = () => {
      attempts += 1;
      const all = electron.webContents?.getAllWebContents?.() || [];
      const fresh = all.find((wc) => !beforeIds.has(wc.id) && matches(wc));
      if (fresh) return resolve(fresh);
      const existing = all.find(matches);
      if (existing || attempts >= 80) return resolve(existing || null);
      setTimeout(poll, 50);
    };
    poll();
  });
}

function prepareTerminalPopoutPresentation(api, webContentsId, options = {}) {
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal popout presentation", String(error));
    return;
  }

  const wc = electron.webContents?.fromId?.(webContentsId);
  const window = wc ? electron.BrowserWindow?.fromWebContents?.(wc) : null;
  if (!wc || wc.isDestroyed?.() || !window || window.isDestroyed?.()) return;

  try {
    window.setTitle?.(typeof options.title === "string" && options.title.trim() ? options.title.trim() : "Terminal");
    window.setBackgroundColor?.(TERMINAL_WINDOW_BACKGROUND);
    window.setWindowButtonVisibility?.(true);
    window.setWindowButtonPosition?.({ x: 14, y: 13 });
    window.setAutoHideMenuBar?.(true);
    window.setMenuBarVisibility?.(false);
  } catch {}

  try {
    window.setOpacity?.(0);
    window.hide?.();
  } catch {}

  try {
    wc.insertCSS?.(`
      html[${TERMINAL_WINDOW_ATTR}="true"] {
        --codexpp-terminal-window-bg: var(--vscode-terminal-background, var(--color-background-surface, ${TERMINAL_WINDOW_BACKGROUND}));
        background: var(--codexpp-terminal-window-bg) !important;
        overflow: hidden !important;
        overscroll-behavior: none !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"]:not([data-codexpp-better-terminal-ready="true"]) body {
        opacity: 0 !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"] body {
        background: var(--codexpp-terminal-window-bg) !important;
        overflow: hidden !important;
        overscroll-behavior: none !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] body > * {
        visibility: hidden !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"],
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"] *,
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [data-codex-terminal],
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [data-codex-terminal] *,
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [id^="terminal-panel-"],
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [id^="terminal-panel-"] *,
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] .xterm,
      html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] .xterm * {
        visibility: visible !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"] {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 38px;
        z-index: 2147483647;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        padding: 0 74px 0 84px;
        background: var(--codexpp-terminal-window-bg) !important;
        border-bottom: 1px solid var(--color-token-border-default, rgb(127 127 127 / 0.18));
        color: var(--color-token-text-primary, #f4f4f4);
        font: 600 14px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        -webkit-app-region: drag;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"] [data-codex-terminal],
      html[${TERMINAL_WINDOW_ATTR}="true"] [id^="terminal-panel-"] {
        position: fixed !important;
        inset: 38px 0 0 0 !important;
        z-index: 2147483646 !important;
        width: 100vw !important;
        height: calc(100vh - 38px) !important;
        box-sizing: border-box !important;
        padding: 0 12px !important;
        background: var(--codexpp-terminal-window-bg) !important;
        overflow: hidden !important;
      }

      html[${TERMINAL_WINDOW_ATTR}="true"] .xterm,
      html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-screen,
      html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-viewport,
      html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-rows {
        background: var(--codexpp-terminal-window-bg) !important;
        overscroll-behavior: none !important;
      }
    `);
  } catch {}

  let attempts = 0;
  const reveal = () => {
    attempts += 1;
    if (wc.isDestroyed?.() || window.isDestroyed?.()) return;

    const shouldToggle = attempts === 1 || attempts % 10 === 0;
    if (shouldToggle) {
      try {
        window.show?.();
        window.focus?.();
      } catch {}
      sendTrustedTerminalToggle(wc);
    }

    let settled = false;
    const finish = (ready) => {
      if (settled) return;
      settled = true;
      if (ready || attempts >= 240) {
        try {
          window.setOpacity?.(1);
          window.show?.();
          window.focus?.();
        } catch {}
      } else {
        setTimeout(reveal, 50);
      }
    };
    const timeout = setTimeout(() => finish(false), 150);

    wc.executeJavaScript(
      `(() => {
        const attempt = ${attempts};
        document.documentElement.setAttribute(${JSON.stringify(TERMINAL_WINDOW_ATTR)}, "true");
        if (!document.querySelector(${JSON.stringify(`[${TERMINAL_WINDOW_CHROME_ATTR}="root"]`)})) {
          const chrome = document.createElement("div");
          chrome.setAttribute(${JSON.stringify(TERMINAL_WINDOW_CHROME_ATTR)}, "root");
          chrome.textContent = ${JSON.stringify(typeof options.title === "string" && options.title.trim() ? options.title.trim() : "Terminal")};
          document.body?.appendChild(chrome);
        }
        const ready = Boolean(document.querySelector(".xterm"));
        if (ready) {
          document.documentElement.setAttribute("data-codexpp-better-terminal-ready", "true");
          document.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea")?.focus();
          try {
            const url = new URL(location.href);
            const sourceSessionId = url.searchParams.get("codexppTerminalSourceSessionId") || "";
            if (sourceSessionId) {
              const entries = JSON.parse(localStorage.getItem(${JSON.stringify(TERMINAL_POPOUTS_KEY)}) || "{}");
              entries[sourceSessionId] = {
                ...(entries[sourceSessionId] || { sourceSessionId, createdAt: Date.now() }),
                sourceSessionId,
                popoutId: url.searchParams.get("codexppTerminalPopoutId") || "",
                title: url.searchParams.get("codexppTerminalTitle") || document.title || "Terminal",
                status: "open",
                updatedAt: Date.now(),
              };
              localStorage.setItem(${JSON.stringify(TERMINAL_POPOUTS_KEY)}, JSON.stringify(entries));
              if (!window.__codexppTerminalPopoutCloseHeartbeat) {
                window.__codexppTerminalPopoutCloseHeartbeat = true;
                window.addEventListener("beforeunload", () => {
                  try {
                    const latest = JSON.parse(localStorage.getItem(${JSON.stringify(TERMINAL_POPOUTS_KEY)}) || "{}");
                    latest[sourceSessionId] = { ...(latest[sourceSessionId] || { sourceSessionId }), sourceSessionId, status: "closed", closedAt: Date.now(), updatedAt: Date.now() };
                    localStorage.setItem(${JSON.stringify(TERMINAL_POPOUTS_KEY)}, JSON.stringify(latest));
                  } catch {}
                });
              }
            }
          } catch {}
        }
        if (!ready && (attempt === 1 || attempt % 10 === 0)) {
          const toggle = Array.from(document.querySelectorAll("button, [role='button']"))
            .find((node) => /\\btoggle terminal\\b/i.test([node.textContent, node.getAttribute("aria-label"), node.getAttribute("title")].filter(Boolean).join(" ")));
          if (toggle instanceof HTMLElement) toggle.click();
          else {
            for (const target of [window, document, document.body].filter(Boolean)) {
              target.dispatchEvent(new KeyboardEvent("keydown", { key: "j", code: "KeyJ", metaKey: true, bubbles: true, cancelable: true, composed: true }));
              target.dispatchEvent(new KeyboardEvent("keyup", { key: "j", code: "KeyJ", metaKey: true, bubbles: true, cancelable: true, composed: true }));
            }
          }
        }
        return ready;
      })()`,
      true,
    ).then((ready) => {
      clearTimeout(timeout);
      finish(Boolean(ready));
    }).catch(() => {
      clearTimeout(timeout);
      finish(false);
    });
  };
  setTimeout(reveal, 50);
}

function notifyTerminalPopoutWindow(api, webContentsId, payload) {
  let electron;
  try {
    electron = require("electron");
  } catch (error) {
    api.log.warn("[better-terminal] cannot require electron for terminal popout notification", String(error));
    return;
  }

  const channel = `codexpp:${api.manifest.id}:terminal-popout-window`;
  let attempts = 0;
  const send = () => {
    attempts += 1;
    const wc = electron.webContents?.fromId?.(webContentsId);
    if (!wc || wc.isDestroyed()) return;
    try {
      wc.send(channel, payload);
    } catch (error) {
      api.log.warn("[better-terminal] failed to notify terminal popout window", String(error));
    }
    if (attempts < 12) setTimeout(send, 100);
  };
  setTimeout(send, 50);
}

function startRenderer(self, api) {
  globalThis.__codexppBetterTerminalState?.dispose?.();

  const state = {
    api,
    disposed: false,
    contextMenuEnabled: readBool(api, "context-menu-enabled", true),
    autoscrollLocked: readBool(api, "autoscroll-locked", false),
    memoryWatchdogEnabled: readBool(api, "memory-watchdog-enabled", DEFAULT_MEMORY_WATCHDOG_ENABLED),
    memoryWatchdogThresholdPercent: readNumber(api, "memory-watchdog-threshold-percent", DEFAULT_MEMORY_WATCHDOG_THRESHOLD_PERCENT),
    memoryWatchdogStatus: null,
    memoryWatchdogTimer: null,
    titleAliases: readJson(api, "title-aliases", {}),
    defaultTitles: readJson(api, "default-titles", {}),
    observer: null,
    interval: null,
    menu: null,
    renameDialog: null,
    activeRoot: null,
    activeTab: null,
    activeSessionId: null,
    activeConversationId: null,
    scrollPositions: new WeakMap(),
    pageHandle: null,
    terminalWindowMode: false,
    terminalWindowConversationId: null,
    terminalWindowSourceSessionId: null,
    terminalWindowPopoutId: null,
    terminalWindowReturning: false,
    pendingTerminalPopoutId: null,
    terminalWindowTimer: null,
    terminalWindowAttempts: 0,
    terminalWindowLastToggleAt: 0,
    offTerminalWindow: null,
    splitDrag: null,
    tabSplitDrag: null,
    runningSessionIds: new Set(),
    finishedSessionIds: new Set(),
    onTerminalManagerSnapshots: null,
    terminalManagerSnapshotCache: null,
    terminalPaneFocused: false,
    terminalSplitActive: false,
    terminalFocusTimer: null,
    offTerminalClearShortcut: null,
    offTerminalClosePaneShortcut: null,
    dispose: null,
  };
  state.dispose = () => stopRenderer(state);
  self._state = state;
  globalThis.__codexppBetterTerminalState = state;

  installStyles();
  registerSettingsPage(state);
  clearLegacySplitMode();

  state.onContextMenu = (event) => handleContextMenu(state, event);
  state.onPointerDown = (event) => {
    if (suppressTerminalTabSecondaryPress(state, event)) return;
    const divider = splitDividerFromEventTarget(event.target);
    if (divider) {
      beginSplitResize(state, event);
      return;
    }
    if (state.renameDialog?.contains(event.target)) return;
    beginTabSplitDrag(state, event);
    if (!state.menu?.contains(event.target)) closeContextMenu(state);
    scheduleTerminalFocusStateUpdate(state);
  };
  state.onMouseDown = (event) => {
    suppressTerminalTabSecondaryPress(state, event);
  };
  state.onKeyDown = (event) => {
    markRunningTerminalOnSubmit(state, event);
    const terminalOrdinal = terminalTabShortcutOrdinal(event);
    if (terminalOrdinal != null && terminalPaneHasFocus(state, event)) {
      if (activateTerminalTabByOrdinal(state, terminalOrdinal)) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
        return;
      }
    }
    if (terminalRenameShortcut(event) && terminalPaneHasFocus(state, event)) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      setActiveTabTitle(state);
      return;
    }
    if (terminalClearShortcut(event) && terminalPaneHasFocus(state, event)) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      clearFocusedTerminal(state, event);
      return;
    }
    if (terminalClosePaneShortcut(event) && state.terminalWindowMode) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      returnTerminalPopoutToTab(state);
      return;
    }
    if (terminalClosePaneShortcut(event) && closeFocusedSplitPane(state, event)) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      return;
    }
    if (
      event.metaKey &&
      !event.altKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      (event.key?.toLowerCase() === "d" || event.code === "KeyD") &&
      terminalPaneHasFocus(state, event)
    ) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      clearActiveSessionOverride(state);
      splitTerminalRight(state);
      return;
    }
    if (event.key === "Escape") {
      if (state.renameDialog) {
        event.preventDefault();
        event.stopPropagation();
        closeRenameDialog(state);
        return;
      }
      closeContextMenu(state);
    }
  };
  state.onPointerMove = (event) => {
    updateTabSplitDrag(state, event);
    updateSplitResize(state, event);
  };
  state.onPointerUp = (event) => {
    endTabSplitDrag(state, event);
    endSplitResize(state);
  };
  state.onScroll = onScrollCapture(state);
  state.onTerminalManagerSnapshots = () => {
    state.terminalManagerSnapshotCache = null;
    scheduleApply(state);
  };
  state.onStorage = (event) => {
    if (event.key === TERMINAL_POPOUTS_KEY) scheduleApply(state);
  };
  state.onPageHide = () => {
    syncTerminalPopoutClose(state);
  };
  state.offTerminalWindow = api.ipc.on("terminal-popout-window", (payload) => {
    const routePayload = terminalWindowPayloadFromLocation();
    if (!routePayload) return;
    activateTerminalWindowMode(state, {
      ...routePayload,
      ...payload,
    });
  });
  state.offTerminalClearShortcut = api.ipc.on(TERMINAL_CLEAR_SHORTCUT_CHANNEL, () => {
    clearFocusedTerminal(state);
  });
  state.offTerminalClosePaneShortcut = api.ipc.on(TERMINAL_CLOSE_PANE_SHORTCUT_CHANNEL, () => {
    if (state.terminalWindowMode) {
      returnTerminalPopoutToTab(state);
      return;
    }
    closeFocusedSplitPane(state, null);
  });
  state.onFocusIn = () => scheduleTerminalFocusStateUpdate(state);
  state.onFocusOut = () => scheduleTerminalFocusStateUpdate(state);

  document.addEventListener("contextmenu", state.onContextMenu, true);
  document.addEventListener("pointerdown", state.onPointerDown, true);
  document.addEventListener("mousedown", state.onMouseDown, true);
  document.addEventListener("pointermove", state.onPointerMove, true);
  document.addEventListener("pointerup", state.onPointerUp, true);
  document.addEventListener("pointercancel", state.onPointerUp, true);
  window.addEventListener("keydown", state.onKeyDown, true);
  document.addEventListener("keydown", state.onKeyDown, true);
  document.addEventListener("focusin", state.onFocusIn, true);
  document.addEventListener("focusout", state.onFocusOut, true);
  document.addEventListener("scroll", state.onScroll, true);
  window.addEventListener("codexpp:terminal-manager-snapshots", state.onTerminalManagerSnapshots);
  window.addEventListener("storage", state.onStorage);
  window.addEventListener("pagehide", state.onPageHide);
  window.addEventListener("beforeunload", state.onPageHide);

  state.observer = new MutationObserver((mutations) => {
    if (isPureTerminalRenderMutationBatch(mutations)) return;
    scheduleApply(state);
  });
  state.observer.observe(document.documentElement, { childList: true, subtree: true });
  state.interval = window.setInterval(() => apply(state), APPLY_POLL_INTERVAL_MS);
  activateTerminalWindowFromRoute(state);
  activateTerminalWindowFromPendingMarker(state);
  syncMemoryWatchdogSettingsToMain(state);
  refreshMemoryWatchdogStatus(state);
  state.memoryWatchdogTimer = window.setInterval(() => refreshMemoryWatchdogStatus(state), MEMORY_WATCHDOG_INTERVAL_MS);
  apply(state);
  api.log.info("[better-terminal] renderer active");
}

function stopRenderer(state) {
  if (state.disposed) return;
  state.disposed = true;
  state.observer?.disconnect();
  if (state.interval) window.clearInterval(state.interval);
  if (state.memoryWatchdogTimer) window.clearInterval(state.memoryWatchdogTimer);
  if (state.terminalWindowTimer) window.clearInterval(state.terminalWindowTimer);
  if (state.terminalFocusTimer) window.clearTimeout(state.terminalFocusTimer);
  document.removeEventListener("contextmenu", state.onContextMenu, true);
  document.removeEventListener("pointerdown", state.onPointerDown, true);
  document.removeEventListener("mousedown", state.onMouseDown, true);
  document.removeEventListener("pointermove", state.onPointerMove, true);
  document.removeEventListener("pointerup", state.onPointerUp, true);
  document.removeEventListener("pointercancel", state.onPointerUp, true);
  window.removeEventListener("keydown", state.onKeyDown, true);
  document.removeEventListener("keydown", state.onKeyDown, true);
  document.removeEventListener("focusin", state.onFocusIn, true);
  document.removeEventListener("focusout", state.onFocusOut, true);
  document.removeEventListener("scroll", state.onScroll, true);
  window.removeEventListener("codexpp:terminal-manager-snapshots", state.onTerminalManagerSnapshots);
  window.removeEventListener("storage", state.onStorage);
  window.removeEventListener("pagehide", state.onPageHide);
  window.removeEventListener("beforeunload", state.onPageHide);
  state.pageHandle?.unregister();
  state.offTerminalWindow?.();
  state.offTerminalClearShortcut?.();
  state.offTerminalClosePaneShortcut?.();
  closeContextMenu(state);
  closeRenameDialog(state);
  cancelTabSplitDrag(state);
  restoreTabTitles();
  document.documentElement.removeAttribute(AUTOSCROLL_LOCK_ATTR);
  document.querySelectorAll(`[${SPLIT_ACTIVE_ATTR}]`).forEach((node) => {
    node.removeAttribute(SPLIT_ACTIVE_ATTR);
  });
  document.querySelectorAll(`[${SPLIT_TAB_ATTR}]`).forEach((node) => {
    node.removeAttribute(SPLIT_TAB_ATTR);
  });
  document.querySelector(`[${TERMINAL_WINDOW_CHROME_ATTR}="root"]`)?.remove();
  restoreTerminalIcons(document);
  document.documentElement.removeAttribute(SPLIT_DRAGGING_ATTR);
  document.documentElement.removeAttribute(SPLIT_DROP_ATTR);
  document.documentElement.removeAttribute(TERMINAL_WINDOW_ATTR);
  state.runningSessionIds?.clear?.();
  state.finishedSessionIds?.clear?.();
  document.getElementById(STYLE_ID)?.remove();
  if (globalThis.__codexppBetterTerminalState === state) {
    delete globalThis.__codexppBetterTerminalState;
  }
}

let applyScheduled = false;
function scheduleApply(state) {
  if (applyScheduled || state.disposed) return;
  applyScheduled = true;
  requestAnimationFrame(() => {
    applyScheduled = false;
    apply(state);
  });
}

function isPureTerminalRenderMutationBatch(mutations) {
  return Array.isArray(mutations) && mutations.length > 0 && mutations.every(isPureTerminalRenderMutation);
}

function isPureTerminalRenderMutation(mutation) {
  const target =
    mutation?.target instanceof Element
      ? mutation.target
      : mutation?.target?.parentElement instanceof Element
        ? mutation.target.parentElement
        : null;
  if (!target) return false;
  if (!target.closest(".xterm-rows, .xterm-screen, .xterm-viewport, .xterm-accessibility-tree, .xterm-selection")) {
    return false;
  }
  const structuralSelector = [
    "[data-tab-id]",
    "[data-codex-terminal]",
    "[id^='terminal-panel-']",
    `[${TERMINAL_POPOUT_PLACEHOLDER_ATTR}]`,
    ".codexpp-terminal-split-view",
    ".codexpp-terminal-split-pane",
    ".codexpp-terminal-split-divider",
  ].join(",");
  for (const node of [...mutation.addedNodes, ...mutation.removedNodes]) {
    if (!(node instanceof Element)) continue;
    if (node.matches(structuralSelector) || node.querySelector(structuralSelector)) return false;
  }
  return true;
}

function apply(state) {
  if (state.disposed) return;
  if (!state.terminalWindowMode) activateTerminalWindowFromRoute(state);
  document.documentElement.toggleAttribute(AUTOSCROLL_LOCK_ATTR, state.autoscrollLocked);
  const root = findTerminalRoot();
  state.activeRoot = root;
  if (!root) {
    applyRunningTerminalIcons(state, document);
    applyTerminalPopoutPlaceholders(state, document);
    closeContextMenu(state);
    document.querySelectorAll(`[${SPLIT_ACTIVE_ATTR}]`).forEach((node) => {
      node.removeAttribute(SPLIT_ACTIVE_ATTR);
    });
    document.querySelectorAll(`[${SPLIT_TAB_ATTR}]`).forEach((node) => {
      node.removeAttribute(SPLIT_TAB_ATTR);
    });
    if (state.terminalWindowMode) ensureTerminalWindowOpen(state);
    return;
  }
  applyTabTitles(state, root);
  applySplitState(state, root);
  applyRunningTerminalIcons(state, document);
  applyTerminalPopoutPlaceholders(state, root);
  applyAutoscrollLock(state, root);
  updateTerminalFocusState(state, root);
  if (state.terminalWindowMode) applyTerminalWindowMode(state);
}

function installStyles() {
  document.getElementById(STYLE_ID)?.remove();
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    [${MENU_ATTR}="root"] {
      position: fixed;
      z-index: 2147483647;
      min-width: 220px;
      padding: 4px;
      border: 1px solid var(--color-token-border-default, rgb(127 127 127 / 0.2));
      border-radius: 10px;
      background: var(--color-token-dropdown-background, var(--color-token-bg-primary, Canvas));
      box-shadow: 0 14px 42px rgb(0 0 0 / 0.22);
      color: var(--color-token-text-primary, CanvasText);
      font: 13px/1.25 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [${MENU_ATTR}="item"] {
      display: flex;
      width: 100%;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border: 0;
      border-radius: 7px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      font: inherit;
      padding: 7px 9px;
      text-align: left;
    }

    [${MENU_ATTR}="item"]:hover {
      background: var(--color-token-list-hover-background, rgb(127 127 127 / 0.12));
    }

    [${MENU_ATTR}="separator"] {
      height: 1px;
      margin: 4px;
      background: var(--color-token-border-default, rgb(127 127 127 / 0.16));
    }

    [${RENAME_DIALOG_ATTR}="backdrop"] {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      pointer-events: auto;
    }

    [${RENAME_DIALOG_ATTR}="close"] svg {
      width: 16px;
      height: 16px;
      display: block;
    }

    [${SPLIT_DROP_ATTR}] {
      cursor: copy !important;
      user-select: none !important;
    }

    [${TAB_DRAG_SOURCE_ATTR}="true"] {
      opacity: 0 !important;
    }

    [${SPLIT_DROP_ATTR}] [data-codex-terminal],
    [${SPLIT_DROP_ATTR}] [id^="terminal-panel-"] {
      position: relative;
    }

    .codexpp-terminal-split-drop-indicator {
      position: fixed;
      z-index: 2147483646;
      pointer-events: none;
      border: 2px solid var(--color-token-focus-border, var(--color-token-foreground, Highlight));
      border-radius: 10px;
      background: color-mix(in srgb, var(--color-token-focus-border, Highlight) 18%, transparent);
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-token-focus-border, Highlight) 45%, transparent);
      transition: left 80ms ease, top 80ms ease, width 80ms ease, height 80ms ease;
    }

    .codexpp-terminal-tab-drag-ghost {
      position: fixed;
      z-index: 2147483647;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      overflow: hidden;
      pointer-events: none;
      contain: layout paint style;
      box-shadow: 0 12px 32px rgb(0 0 0 / 0.22);
      border-radius: 8px !important;
      transform: rotate(1deg);
    }

    .codexpp-terminal-split-view {
      width: 100%;
      height: 100%;
      position: relative;
      box-sizing: border-box;
      margin-inline: -16px;
      padding-inline: 16px;
      width: calc(100% + 32px);
      border-top: 1px solid var(--color-token-border-default, rgb(127 127 127 / 0.2));
    }

    .codexpp-terminal-split-pane [data-codex-terminal] {
      width: 100%;
      height: 100%;
    }

    .codexpp-terminal-split-divider {
      position: relative;
      z-index: 7;
      width: 5px;
      min-width: 5px;
      height: 100%;
      cursor: col-resize;
      background: transparent;
      touch-action: none;
    }

    .codexpp-terminal-split-divider::before {
      content: "";
      position: absolute;
      top: 0;
      bottom: 0;
      left: 2px;
      width: 1px;
      background: var(--color-token-border-default, rgb(127 127 127 / 0.36));
    }

    .codexpp-terminal-split-divider:hover::before,
    html[${SPLIT_DRAGGING_ATTR}="true"] .codexpp-terminal-split-divider::before {
      background: var(--color-token-text-secondary, rgb(127 127 127 / 0.7));
    }

    html[${SPLIT_DRAGGING_ATTR}="true"],
    html[${SPLIT_DRAGGING_ATTR}="true"] * {
      cursor: col-resize !important;
      user-select: none !important;
    }

    [data-tab-id^="terminal:"][${RUNNING_TERMINAL_ATTR}="true"]:not([${SPLIT_TAB_ATTR}="primary"]) {
      display: inline-flex !important;
      align-items: center !important;
      gap: 6px !important;
    }

    [data-tab-id^="terminal:"] svg[${FILLED_TERMINAL_ICON_MARK}] {
      opacity: 0.92;
    }

    [data-tab-id^="terminal:"][${FROZEN_TERMINAL_ATTR}="true"] {
      box-shadow: inset 0 0 0 1px var(--color-token-charts-blue, #1f8fff) !important;
    }

    [${RUNNING_TERMINAL_BADGE_ATTR}="true"] {
      position: relative !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      overflow: visible !important;
    }

    [${RUNNING_TERMINAL_BADGE_ATTR}="true"]::after {
      content: "";
      position: absolute;
      right: 1px;
      bottom: 1px;
      width: 5px;
      height: 5px;
      border-radius: 999px;
      background: var(--color-token-accent-primary, #3b82f6);
      box-shadow: none;
    }

    [data-tab-id^="terminal:"][${SPLIT_TAB_ATTR}="secondary"] {
      display: none !important;
    }

    [${TERMINAL_POPOUT_PARKED_ATTR}="true"] {
      position: relative !important;
    }

    [${TERMINAL_POPOUT_PARKED_ATTR}="true"] > :not([${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="root"]) {
      opacity: 0 !important;
      pointer-events: none !important;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="root"] {
      position: absolute;
      inset: 0;
      z-index: 2147483645;
      display: flex;
      align-items: center;
      justify-content: center;
      box-sizing: border-box;
      padding: 24px;
      background: var(--color-background-surface, ${TERMINAL_WINDOW_BACKGROUND});
      color: var(--color-token-text-primary, CanvasText);
      font: 13px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="card"] {
      display: grid;
      gap: 12px;
      justify-items: center;
      max-width: 360px;
      text-align: center;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="title"] {
      font-size: 14px;
      font-weight: 600;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="actions"] {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="button"] {
      min-height: 30px;
      border: 1px solid var(--color-token-border-default, rgb(127 127 127 / 0.22));
      border-radius: 8px;
      background: var(--color-token-button-secondary-background, rgb(127 127 127 / 0.08));
      color: var(--color-token-text-primary, CanvasText);
      cursor: default;
      font: inherit;
      padding: 5px 10px;
    }

    [${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="button"]:hover {
      background: var(--color-token-button-secondary-hover-background, rgb(127 127 127 / 0.14));
    }

    html[${TERMINAL_WINDOW_ATTR}="true"]:not([data-codexpp-better-terminal-ready="true"]) body {
      opacity: 0 !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] {
      --codexpp-terminal-window-bg: var(--vscode-terminal-background, var(--color-background-surface, ${TERMINAL_WINDOW_BACKGROUND}));
      background: var(--codexpp-terminal-window-bg) !important;
      overflow: hidden !important;
      overscroll-behavior: none !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] body {
      overflow: hidden !important;
      background: var(--codexpp-terminal-window-bg) !important;
      overscroll-behavior: none !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] *,
    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-viewport {
      overscroll-behavior: none !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] body > * {
      visibility: hidden !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"],
    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"] *,
    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [data-codex-terminal],
    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [data-codex-terminal] *,
    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [id^="terminal-panel-"],
    html[${TERMINAL_WINDOW_ATTR}="true"][data-codexpp-better-terminal-ready="true"] [id^="terminal-panel-"] * {
      visibility: visible !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="root"] {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 38px;
      z-index: 2147483647;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      box-sizing: border-box;
      padding: 5px 12px 5px 84px;
      background: var(--codexpp-terminal-window-bg) !important;
      border-bottom: 1px solid var(--color-token-border-default, rgb(127 127 127 / 0.18));
      -webkit-app-region: drag;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="title"] {
      position: absolute;
      inset: 0 74px 0 84px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      min-width: 0;
      overflow: hidden;
      padding: 0 14px;
      color: var(--color-token-text-primary, #f4f4f4);
      font-size: 14px;
      font-weight: 600;
      line-height: 1;
      pointer-events: none;
      text-align: center;
      white-space: nowrap;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="title"] span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="title-muted"] {
      flex: 0 1 auto;
      color: var(--color-token-text-tertiary, #9b9b9b);
      font-weight: 600;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="always-on-top"] {
      width: 28px;
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      border: 0;
      border-radius: 10px;
      background: transparent;
      color: var(--color-token-text-secondary, CanvasText);
      cursor: default;
      -webkit-app-region: no-drag;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="always-on-top"]:hover,
    html[${TERMINAL_WINDOW_ATTR}="true"] [${TERMINAL_WINDOW_CHROME_ATTR}="always-on-top"][aria-pressed="true"] {
      background: var(--color-token-toolbar-hover-background, rgb(127 127 127 / 0.14));
      color: var(--color-token-text-primary, CanvasText);
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [data-codex-terminal],
    html[${TERMINAL_WINDOW_ATTR}="true"] [id^="terminal-panel-"] {
      position: fixed !important;
      inset: 38px 0 0 0 !important;
      z-index: 2147483646 !important;
      width: 100vw !important;
      height: calc(100vh - 38px) !important;
      box-sizing: border-box !important;
      padding: 0 12px !important;
      background: var(--codexpp-terminal-window-bg) !important;
      overflow: hidden !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [data-codex-terminal] .xterm,
    html[${TERMINAL_WINDOW_ATTR}="true"] [id^="terminal-panel-"] .xterm,
    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm {
      width: calc(100vw - 24px) !important;
      height: 100% !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm,
    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-screen,
    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-viewport,
    html[${TERMINAL_WINDOW_ATTR}="true"] .xterm-rows {
      background: var(--codexpp-terminal-window-bg) !important;
    }

    html[${TERMINAL_WINDOW_ATTR}="true"] [data-codex-terminal-window-hidden="true"] {
      opacity: 0 !important;
      pointer-events: none !important;
    }
  `;
  document.head.appendChild(style);
}

function handleContextMenu(state, event) {
  if (!state.contextMenuEnabled) return;
  const root = findTerminalRoot();
  if (!root) return;
  const tab = findTerminalTabFromEvent(root, event);
  const pane = tab ? null : findTerminalPaneFromEvent(root, event);
  if (!tab && !pane) return;

  event.preventDefault();
  event.stopPropagation();
  state.activeRoot = root;
  state.activeTab = tab;
  const session = tab ? terminalSessionFromNode(state, tab) : terminalSessionFromNode(state, pane);
  state.activeSessionId = session?.sessionId || null;
  state.activeConversationId = session?.conversationId || null;
  openContextMenu(state, event.clientX, event.clientY, { source: tab ? "tab" : "pane" });
}

function suppressTerminalTabSecondaryPress(state, event) {
  if (event.button !== 2) return false;
  const root = state.activeRoot || findTerminalRoot();
  if (!root || !findTerminalTabFromEvent(root, event)) return false;
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation?.();
  return true;
}

function openContextMenu(state, x, y, options = {}) {
  closeContextMenu(state);
  const menu = document.createElement("div");
  menu.setAttribute(MENU_ATTR, "root");
  const root = state.activeRoot || findTerminalRoot();
  const splitPair = currentSplitPairForRoot(state, root);
  const activeSession = activeTerminalSession(state);
  const isSplitActive = isSplitPairActiveForSession(splitPair, activeSession);
  const isPaneMenu = options.source === "pane";
  const canAddSplit = !isSplitActive || splitPair.sessions.length < MAX_SPLIT_SESSIONS;
  const canMoveOut = Boolean(isSplitActive && activeSession?.sessionId && splitPair.sessions.includes(activeSession.sessionId));
  menu.append(
    ...[
    isPaneMenu ? menuItem("Cut", () => runEditCommand("cut")) : null,
    isPaneMenu ? menuItem("Copy", () => runEditCommand("copy")) : null,
    isPaneMenu ? menuItem("Paste", () => runEditCommand("paste")) : null,
    isPaneMenu ? separator() : null,
    menuItem("Open new terminal tab", () => openNewTerminalTab(state)),
    isSplitActive ? menuItem("Exit Split View", () => closeSplitView(state)) : null,
    canAddSplit ? menuItem("Add split view to left", () => splitTerminal(state, "left")) : null,
    canAddSplit ? menuItem("Add split view to right", () => splitTerminal(state, "right")) : null,
    canMoveOut ? menuItem("Move to new tab", () => moveTerminalToNewTab(state)) : null,
    menuItem("Pop out terminal window", () => openTerminalPopoutWindow(state)),
    menuItem("Rename title", () => setActiveTabTitle(state)),
    activeSession?.sessionId ? menuItem("Kill terminal", () => killTerminal(state)) : null,
    separator(),
    menuItem(state.autoscrollLocked ? "Enable autoscroll" : "Disable autoscroll", () => {
      state.autoscrollLocked = !state.autoscrollLocked;
      state.api.storage.set("autoscroll-locked", state.autoscrollLocked);
      apply(state);
    }),
    ].filter(Boolean),
  );
  document.body.appendChild(menu);
  const rect = menu.getBoundingClientRect();
  menu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - rect.width - 8))}px`;
  menu.style.top = `${Math.max(8, Math.min(y, window.innerHeight - rect.height - 8))}px`;
  state.menu = menu;
}

function closeContextMenu(state) {
  state.menu?.remove();
  state.menu = null;
}

function menuItem(label, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute(MENU_ATTR, "item");
  button.textContent = label;
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const state = globalThis.__codexppBetterTerminalState;
    if (state) closeContextMenu(state);
    action();
  });
  return button;
}

function separator() {
  const node = document.createElement("div");
  node.setAttribute(MENU_ATTR, "separator");
  return node;
}

function runEditCommand(command) {
  try {
    document.execCommand(command);
  } catch {}
}

function clearFocusedTerminal(state, event) {
  const root = state.activeRoot || findTerminalRoot();
  const session =
    focusedTerminalSession(root || document, state, event) ||
    activeTerminalSession(state) ||
    visibleTerminalSession(root || document, state);
  if (!session?.sessionId) return false;
  clearTerminalSession(session.sessionId);
  state.finishedSessionIds?.delete?.(session.sessionId);
  requestAnimationFrame(() => applyRunningTerminalIcons(state, document));
  return true;
}

function visibleTerminalSession(root, state) {
  const panel = root?.querySelector?.("[data-codex-terminal][id^='terminal-panel-'], [id^='terminal-panel-']");
  const direct = terminalSessionFromNode(state, panel);
  if (direct?.sessionId) return direct;
  const sessionId = terminalSessionIdFromString(panel?.id || "");
  return sessionId ? { sessionId, conversationId: terminalConversationId(root, state) } : null;
}

function clearTerminalSession(sessionId) {
  const script = document.createElement("script");
  script.textContent = `(() => {
    try {
      const sessionId = ${JSON.stringify(sessionId)};
      const manager = globalThis.__codexppTerminalManager;
      manager?.replaceSnapshotBuffer?.(sessionId, "");
      const listener = manager?.listeners?.get?.(sessionId);
      if (listener?.onData) {
        listener.onData("\\x1b[3J\\x1b[H\\x1b[2J");
        return;
      }
      manager?.write?.(sessionId, "\\x0c");
    } catch {}
  })();`;
  try {
    document.documentElement.appendChild(script);
  } finally {
    script.remove();
  }
}

function openNewTerminalTab(state) {
  const root = state.activeRoot || findTerminalRoot();
  const input = root?.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea");
  if (!input) {
    state.api.log.warn("[better-terminal] no terminal input for new terminal tab");
    return;
  }
  const previousSessionIds = new Set(findTerminalTabs(root).map((tab) => terminalSessionFromNode(state, tab)?.sessionId).filter(Boolean));
  input.focus();
  const event = new KeyboardEvent("keydown", {
    key: "t",
    code: "KeyT",
    metaKey: true,
    bubbles: true,
    cancelable: true,
    composed: true,
  });
  input.dispatchEvent(event);
  [80, 180, 360, 700].forEach((delay) => {
    window.setTimeout(() => focusNewestTerminalTab(state, previousSessionIds), delay);
  });
  requestAnimationFrame(() => apply(state));
}

function focusNewestTerminalTab(state, previousSessionIds) {
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return;
  const newTab = findTerminalTabs(root)
    .find((tab) => {
      const session = terminalSessionFromNode(state, tab);
      return session?.sessionId && !previousSessionIds.has(session.sessionId);
    });
  if (newTab instanceof HTMLElement) activateTerminalTabElement(terminalTabActivationTarget(newTab));
  const activePanel = root.querySelector("[data-codex-terminal], [id^='terminal-panel-']");
  const input = activePanel?.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea") ||
    root.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea");
  if (input instanceof HTMLElement) input.focus();
}

function terminalTabShortcutOrdinal(event) {
  const hasTabModifier = event.ctrlKey || event.metaKey;
  if (!hasTabModifier || (event.ctrlKey && event.metaKey) || event.altKey || event.shiftKey) return null;
  if (/^Digit[1-9]$/.test(event.code)) return Number(event.code.slice(5));
  if (/^[1-9]$/.test(event.key || "")) return Number(event.key);
  return null;
}

function terminalRenameShortcut(event) {
  const hasPrimaryModifier = event.ctrlKey || event.metaKey;
  const isRenameKey = event.key?.toLowerCase() === "r" || event.code === "KeyR";
  return Boolean(
    hasPrimaryModifier &&
      !(event.ctrlKey && event.metaKey) &&
      event.altKey &&
      !event.shiftKey &&
      isRenameKey,
  );
}

function terminalClearShortcut(event) {
  const hasPrimaryModifier = event.ctrlKey || event.metaKey;
  const isClearKey = event.key?.toLowerCase() === "k" || event.code === "KeyK";
  return Boolean(
    hasPrimaryModifier &&
      !(event.ctrlKey && event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      isClearKey,
  );
}

function terminalClosePaneShortcut(event) {
  const hasPrimaryModifier = event.ctrlKey || event.metaKey;
  const isCloseKey = event.key?.toLowerCase() === "w" || event.code === "KeyW";
  return Boolean(
    hasPrimaryModifier &&
      !(event.ctrlKey && event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      isCloseKey,
  );
}

function markRunningTerminalOnSubmit(state, event) {
  if (
    event.key !== "Enter" ||
    event.metaKey ||
    event.ctrlKey ||
    event.altKey ||
    event.shiftKey ||
    state.renameDialog ||
    state.menu
  ) {
    return;
  }
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return;
  const target = event.target instanceof Element ? event.target : document.activeElement;
  if (
    !(target instanceof Element) ||
    !root.contains(target) ||
    !target.closest("textarea[aria-label='Terminal input'], .xterm-helper-textarea, .xterm")
  ) {
    return;
  }
  const session = focusedTerminalSession(root, state, event);
  if (!session?.sessionId) return;
  if (!(state.runningSessionIds instanceof Set)) state.runningSessionIds = new Set();
  state.runningSessionIds.add(session.sessionId);
  requestAnimationFrame(() => applyRunningTerminalIcons(state, document));
}

function terminalPaneHasFocus(state, event) {
  if (state.renameDialog || state.menu) return false;
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return false;
  const target = event.target instanceof Element ? event.target : document.activeElement;
  const terminalInput = root.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea");
  if (target instanceof Element && root.contains(target)) {
    return target.closest("textarea[aria-label='Terminal input'], .xterm, [data-codex-terminal], [id^='terminal-panel-']") != null ||
      root.querySelector("[data-codex-terminal]:focus-within, [id^='terminal-panel-']:focus-within, .xterm:focus-within") != null;
  }
  if (document.activeElement === document.body && terminalInput instanceof HTMLElement) return true;
  return root.querySelector("[data-codex-terminal]:focus-within, [id^='terminal-panel-']:focus-within, .xterm:focus-within") != null;
}

function scheduleTerminalFocusStateUpdate(state) {
  if (state.terminalFocusTimer) window.clearTimeout(state.terminalFocusTimer);
  state.terminalFocusTimer = window.setTimeout(() => {
    state.terminalFocusTimer = null;
    updateTerminalFocusState(state);
  }, 0);
}

function updateTerminalFocusState(state, root = state.activeRoot || findTerminalRoot()) {
  const active = document.activeElement;
  const activeIsTerminal =
    active instanceof Element &&
    root instanceof Element &&
    root.contains(active) &&
    active.closest("textarea[aria-label='Terminal input'], .xterm-helper-textarea, .xterm, [data-codex-terminal], [id^='terminal-panel-']") != null;
  const focused = Boolean(
    activeIsTerminal ||
      root?.querySelector?.("[data-codex-terminal]:focus-within, [id^='terminal-panel-']:focus-within, .xterm:focus-within"),
  );
  const splitPair = currentSplitPairForRoot(state, root);
  const splitActive = isSplitPairActiveForSession(splitPair, activeTerminalSessionInRoot(state, root));
  reportTerminalWindowState(state, root, focused);
  if (state.terminalPaneFocused === focused && state.terminalSplitActive === splitActive) return;
  state.terminalPaneFocused = focused;
  state.terminalSplitActive = splitActive;
  state.api.ipc.invoke(TERMINAL_FOCUS_CHANNEL, {
    focused,
    splitActive,
    terminalWindowMode: Boolean(state.terminalWindowMode),
  }).catch(() => {});
}

function reportTerminalWindowState(state, root = state.activeRoot || findTerminalRoot(), focused = state.terminalPaneFocused) {
  const sessions = findTerminalSessions(root || document);
  const payload = {
    focused: Boolean(focused),
    hasTerminal: Boolean(root?.querySelector?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm")),
    sessionIds: sessions.map((session) => session.sessionId).filter(Boolean),
    conversationId: terminalConversationId(root || document, state),
  };
  try {
    const electron = require("electron");
    electron.ipcRenderer?.invoke?.(TERMINAL_WINDOW_REPORT_CHANNEL, payload).catch?.(() => {});
  } catch {
    state.api.ipc.invoke?.(TERMINAL_WINDOW_REPORT_API_CHANNEL, payload).catch?.(() => {});
  }
}

function focusedTerminalSession(root, state, event) {
  const seeds = [];
  const eventTarget = event?.target instanceof Element ? event.target : null;
  if (eventTarget) seeds.push(eventTarget);
  if (document.activeElement instanceof Element) seeds.push(document.activeElement);
  const focusedPanel = root?.querySelector(
    "[data-codex-terminal]:focus-within, [id^='terminal-panel-']:focus-within, .xterm:focus-within",
  );
  if (focusedPanel instanceof Element) seeds.push(focusedPanel);

  for (const seed of seeds) {
    if (!(seed instanceof Element) || (root && !root.contains(seed))) continue;
    const panel =
      seed.closest("[data-codex-terminal], [id^='terminal-panel-'], .xterm, .codexpp-terminal-split-pane") ||
      seed;
    const direct = terminalSessionFromNode(state, panel);
    if (direct?.sessionId) return {
      sessionId: direct.sessionId,
      conversationId: direct.conversationId || terminalConversationId(root, state),
    };
    const child = panel.querySelector?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm");
    const fromChild = terminalSessionFromNode(state, child);
    if (fromChild?.sessionId) return {
      sessionId: fromChild.sessionId,
      conversationId: fromChild.conversationId || terminalConversationId(root, state),
    };
  }
  return null;
}

function activateTerminalTabByOrdinal(state, ordinal) {
  if (!Number.isInteger(ordinal) || ordinal < 1 || ordinal > 9) return false;
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return false;
  const tab = terminalTabsBySession(root, state)[ordinal - 1];
  if (!(tab instanceof HTMLElement)) return false;
  const session = terminalSessionFromNode(state, tab);
  activateTerminalTabElement(terminalTabActivationTarget(tab));
  [30, 90, 180].forEach((delay) => {
    window.setTimeout(() => focusTerminalInputForSession(root, session?.sessionId), delay);
  });
  return true;
}

function terminalTabsBySession(root, state) {
  const tabs = [];
  const seen = new Set();
  for (const tab of findTerminalTabs(root)) {
    const marker = terminalTabMarker(tab);
    if (marker instanceof HTMLElement && marker.getAttribute(SPLIT_TAB_ATTR) === "secondary") continue;
    const session = terminalSessionFromNode(state, tab) || terminalSessionFromNode(state, marker);
    const key =
      session?.sessionId
        ? `session:${session.sessionId}`
        : marker instanceof HTMLElement
          ? marker.getAttribute("data-tab-id") || terminalTabKey(marker, tabs.length)
          : terminalTabKey(tab, tabs.length);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    tabs.push(marker instanceof HTMLElement ? marker : tab);
  }
  return tabs;
}

function focusTerminalInputForSession(root, sessionId) {
  const panel = sessionId ? document.getElementById(`terminal-panel-${sessionId}`) : null;
  const input =
    panel?.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea") ||
    root?.querySelector("[data-codex-terminal] textarea[aria-label='Terminal input'], [id^='terminal-panel-'] textarea[aria-label='Terminal input'], .xterm-helper-textarea");
  if (input instanceof HTMLElement) input.focus();
}

async function splitTerminalRight(state) {
  return splitTerminal(state, "right");
}

async function splitTerminal(state, side = "right") {
  const root = state.activeRoot || findTerminalRoot();
  const existing = currentSplitPairForRoot(state, root);
  let active = activeTerminalSession(state);
  if (active?.sessionId && isTerminalSessionPoppedOut(active.sessionId)) {
    active = visibleTerminalSession(root, state) || firstLocalTerminalSession(state, root, active.sessionId);
  }
  const activeExisting = isSplitPairActiveForSession(existing, active) ? existing : null;
  if (
    activeExisting &&
    active?.sessionId &&
    activeExisting.sessions.includes(active.sessionId)
  ) {
    if (activeExisting.sessions.length < MAX_SPLIT_SESSIONS) {
      const nextSessionId = makeTerminalSessionId();
      const activeIndex = Math.max(0, activeExisting.sessions.indexOf(active.sessionId));
      const sessions = activeExisting.sessions.filter((sessionId) => sessionId !== nextSessionId);
      sessions.splice(side === "left" ? activeIndex : activeIndex + 1, 0, nextSessionId);
      storeTerminalSnapshot(active.sessionId);
      writeSplitPair({
        ...activeExisting,
        anchor: activeExisting.anchor || active.sessionId,
        left: sessions[0],
        right: sessions[1],
        sessions,
        existingSessions: sessions.filter((sessionId) => sessionId !== nextSessionId),
      });
      triggerTerminalRerender(state, active.sessionId);
      window.dispatchEvent(new Event("resize"));
    }
    apply(state);
    return;
  }
  if (!active?.sessionId) {
    state.api.log.warn("[better-terminal] no active terminal session for split view");
    return;
  }

  const existingSessionId = active.sessionId;
  const newSessionId = makeTerminalSessionId();
  const sessions = side === "left" ? [newSessionId, existingSessionId] : [existingSessionId, newSessionId];
  storeTerminalSnapshot(existingSessionId);
  writeSplitPair({
    conversationId: active.conversationId || null,
    anchor: active.sessionId,
    left: sessions[0],
    right: sessions[1],
    sessions,
    existingSessions: [existingSessionId],
    ratio: 0.5,
    createdAt: Date.now(),
  });
  triggerTerminalRerender(state, active.sessionId);
  window.dispatchEvent(new Event("resize"));
  apply(state);
}

function firstLocalTerminalSession(state, root, excludeSessionId = null) {
  for (const tab of terminalTabsBySession(root, state)) {
    const marker = terminalTabMarker(tab);
    const session = terminalSessionFromNode(state, tab) || terminalSessionFromNode(state, marker);
    if (!session?.sessionId || session.sessionId === excludeSessionId || isTerminalSessionPoppedOut(session.sessionId)) continue;
    return session;
  }
  for (const session of findTerminalSessions(root)) {
    if (!session?.sessionId || session.sessionId === excludeSessionId || isTerminalSessionPoppedOut(session.sessionId)) continue;
    return session;
  }
  return null;
}

function moveTerminalToNewTab(state) {
  const active = activeTerminalSession(state);
  const splitPair = currentSplitPairForRoot(state, state.activeRoot || findTerminalRoot());
  if (!active?.sessionId || !splitPair?.sessions.includes(active.sessionId)) return;
  const remaining = splitPair.sessions.filter((sessionId) => sessionId !== active.sessionId);
  if (remaining.length < 2) {
    clearSplitPair();
  } else {
    writeSplitPair({
      ...splitPair,
      left: remaining[0],
      right: remaining[1],
      sessions: remaining,
      existingSessions: splitPair.existingSessions.filter((sessionId) => remaining.includes(sessionId)),
      anchor: remaining.includes(splitPair.anchor) ? splitPair.anchor : remaining[0],
    });
  }
  triggerTerminalRerender(state, active.sessionId);
  window.setTimeout(() => {
    const root = state.activeRoot || findTerminalRoot();
    const tab = findTerminalTabBySessionId(root, active.sessionId);
    if (tab instanceof HTMLElement) activateTerminalTabElement(tab);
    focusTerminalInputForSession(root, active.sessionId);
    apply(state);
  }, 80);
}

function killTerminal(state) {
  const active = activeTerminalSession(state);
  if (!active?.sessionId) return;
  closeTerminalSession(state, active);
}

function closeFocusedSplitPane(state, event) {
  const root = state.activeRoot || findTerminalRoot();
  const splitPair = currentSplitPairForRoot(state, root);
  if (!root || !splitPair) return false;
  const session = focusedTerminalSession(root, state, event) || activeTerminalSession(state);
  if (!session?.sessionId || !splitPair.sessions.includes(session.sessionId)) return false;
  state.activeSessionId = session.sessionId;
  state.activeConversationId = session.conversationId || splitPair.conversationId || null;
  return closeSplitPaneSession(state, session, splitPair);
}

function closeTerminalSession(state, session) {
  if (!session?.sessionId) return;
  const root = state.activeRoot || findTerminalRoot();
  const splitPair = currentSplitPairForRoot(state, root);
  const remaining = splitPair?.sessions?.includes(session.sessionId)
    ? splitPair.sessions.filter((sessionId) => sessionId !== session.sessionId)
    : null;

  if (remaining) {
    if (remaining.length < 2) {
      clearSplitPair();
    } else {
      writeSplitPair({
        ...splitPair,
        left: remaining[0],
        right: remaining[1],
        sessions: remaining,
        existingSessions: splitPair.existingSessions.filter((sessionId) => remaining.includes(sessionId)),
        anchor: remaining.includes(splitPair.anchor) ? splitPair.anchor : remaining[0],
      });
    }
    const nextActive = remaining[0] || null;
    state.activeSessionId = nextActive;
    state.activeConversationId = nextActive ? session.conversationId || splitPair.conversationId || null : null;
    triggerTerminalRerender(state, nextActive || session.sessionId);
    apply(state);
  }

  window.setTimeout(() => {
    const nextRoot = state.activeRoot || findTerminalRoot();
    const tab = findTerminalTabBySessionId(nextRoot, session.sessionId);
    if (tab instanceof HTMLElement && invokeTerminalTabClose(tab)) {
      triggerTerminalRerender(state);
      apply(state);
      if (remaining?.[0]) focusTerminalInputForSession(nextRoot, remaining[0]);
      return;
    }
    const closeControl = terminalCloseControlForSession(nextRoot, session.sessionId);
    closeControl?.click();
    triggerTerminalRerender(state);
    apply(state);
    if (remaining?.[0]) focusTerminalInputForSession(nextRoot, remaining[0]);
  }, remaining ? 80 : 0);
}

function closeSplitPaneSession(state, session, splitPair) {
  if (!session?.sessionId || !splitPair?.sessions?.includes(session.sessionId)) return false;
  const remaining = splitPair.sessions.filter((sessionId) => sessionId !== session.sessionId);
  if (remaining.length < 2) {
    clearSplitPair();
  } else {
    writeSplitPair({
      ...splitPair,
      left: remaining[0],
      right: remaining[1],
      sessions: remaining,
      existingSessions: splitPair.existingSessions.filter((sessionId) => remaining.includes(sessionId)),
      anchor: remaining.includes(splitPair.anchor) ? splitPair.anchor : remaining[0],
    });
  }
  const nextActive = remaining[0] || null;
  state.activeSessionId = nextActive;
  state.activeConversationId = nextActive ? session.conversationId || splitPair.conversationId || null : null;
  triggerTerminalRerender(state, nextActive || session.sessionId);
  window.dispatchEvent(new Event("resize"));
  apply(state);
  window.setTimeout(() => {
    const root = state.activeRoot || findTerminalRoot();
    if (nextActive) focusTerminalInputForSession(root, nextActive);
    apply(state);
  }, 80);
  return true;
}

function closeSplitView(state) {
  clearSplitPair();
  triggerTerminalRerender(state);
  window.dispatchEvent(new Event("resize"));
  apply(state);
}

function beginTabSplitDrag(state, event) {
  if (event.button !== 0 || state.splitDrag || state.renameDialog) return;
  if (isTerminalTabCloseControl(event.target)) return;
  const root = findTerminalRoot();
  if (!root) return;
  const tab = findTerminalTabFromEvent(root, event);
  if (!(tab instanceof HTMLElement)) return;
  const session = terminalSessionFromNode(state, tab);
  if (!session?.sessionId) return;
  const targetSessionBeforeActivation = activeTerminalSessionInRoot(state, root);
  const visualTab = terminalTabVisualNode(tab);
  const dragNode = visualTab instanceof HTMLElement ? visualTab : tab;
  const tabRect = dragNode.getBoundingClientRect();
  state.tabSplitDrag = {
    root,
    tab,
    dragNode,
    tabRect,
    session,
    targetSessionBeforeActivation:
      targetSessionBeforeActivation?.sessionId && targetSessionBeforeActivation.sessionId !== session.sessionId
        ? targetSessionBeforeActivation
        : null,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    active: false,
    drop: null,
    indicator: null,
    ghost: null,
  };
  try {
    tab.setPointerCapture?.(event.pointerId);
  } catch {}
}

function updateTabSplitDrag(state, event) {
  const drag = state.tabSplitDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const deltaX = event.clientX - drag.startX;
  const deltaY = event.clientY - drag.startY;
  const verticalExit = Math.abs(deltaY) > 10 && Math.abs(deltaY) > Math.abs(deltaX) * 1.15;
  const leftTabRow = event.clientY > drag.tabRect.bottom + 6 || event.clientY < drag.tabRect.top - 6;
  if (!drag.active && !(verticalExit || leftTabRow)) return;

  drag.active = true;
  showTabSplitDragGhost(state, event);
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation?.();

  const drop = terminalSplitDropTargetAtPoint(
    state,
    drag.root,
    event.clientX,
    event.clientY,
    drag.session.sessionId,
    drag.targetSessionBeforeActivation,
  );
  if (!drop) {
    hideTabSplitDropIndicator(state);
    return;
  }

  drag.drop = drop;
  document.documentElement.setAttribute(SPLIT_DROP_ATTR, drop.side);
  showTabSplitDropIndicator(state, drop);
}

function endTabSplitDrag(state, event) {
  const drag = state.tabSplitDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const drop = drag.drop;
  const wasActive = drag.active;
  cancelTabSplitDrag(state);
  if (!wasActive || !drop) return;
  event.preventDefault();
  event.stopPropagation();
  createSplitFromDraggedTab(state, drag.session, drop);
}

function cancelTabSplitDrag(state) {
  hideTabSplitDropIndicator(state);
  state.tabSplitDrag?.ghost?.remove();
  state.tabSplitDrag?.dragNode?.removeAttribute(TAB_DRAG_SOURCE_ATTR);
  try {
    state.tabSplitDrag?.tab?.releasePointerCapture?.(state.tabSplitDrag.pointerId);
  } catch {}
  state.tabSplitDrag = null;
  document.documentElement.removeAttribute(SPLIT_DROP_ATTR);
}

function hideTabSplitDropIndicator(state) {
  state.tabSplitDrag?.indicator?.remove();
  if (state.tabSplitDrag) {
    state.tabSplitDrag.indicator = null;
    state.tabSplitDrag.drop = null;
  }
  document.documentElement.removeAttribute(SPLIT_DROP_ATTR);
}

function showTabSplitDropIndicator(state, drop) {
  const drag = state.tabSplitDrag;
  if (!drag) return;
  const indicator = drag.indicator || document.createElement("div");
  if (!drag.indicator) {
    indicator.className = "codexpp-terminal-split-drop-indicator";
    document.body.appendChild(indicator);
    drag.indicator = indicator;
  }
  const halfWidth = drop.rect.width / 2;
  const left = drop.side === "left" ? drop.rect.left : drop.rect.left + halfWidth;
  indicator.style.left = `${Math.round(left + 4)}px`;
  indicator.style.top = `${Math.round(drop.rect.top + 4)}px`;
  indicator.style.width = `${Math.max(0, Math.round(halfWidth - 8))}px`;
  indicator.style.height = `${Math.max(0, Math.round(drop.rect.height - 8))}px`;
}

function showTabSplitDragGhost(state, event) {
  const drag = state.tabSplitDrag;
  if (!drag) return;
  const ghost = drag.ghost || drag.dragNode.cloneNode(true);
  if (!drag.ghost) {
    ghost.classList.add("codexpp-terminal-tab-drag-ghost");
    ghost.setAttribute("aria-hidden", "true");
    ghost.removeAttribute("id");
    ghost.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
    ghost.style.width = `${Math.round(drag.tabRect.width)}px`;
    ghost.style.height = `${Math.round(drag.tabRect.height)}px`;
    document.body.appendChild(ghost);
    drag.ghost = ghost;
    drag.dragNode.setAttribute(TAB_DRAG_SOURCE_ATTR, "true");
  }
  ghost.style.left = `${Math.round(event.clientX - drag.tabRect.width / 2)}px`;
  ghost.style.top = `${Math.round(event.clientY - drag.tabRect.height / 2)}px`;
}

function terminalSplitDropTargetAtPoint(state, root, x, y, draggedSessionId, fallbackTargetSession) {
  const panels = terminalDropPanels(root);
  const fallback = panels.find((panel) => pointInRect(x, y, panel.rect));
  const panel = fallback || panels[0];
  if (!panel || !pointInRect(x, y, panel.rect)) return null;
  let targetSession = terminalSessionFromNode(state, panel.node) || activeTerminalSessionInRoot(state, root);
  if (targetSession?.sessionId === draggedSessionId && fallbackTargetSession?.sessionId !== draggedSessionId) {
    targetSession = fallbackTargetSession;
  }
  if (!targetSession?.sessionId || targetSession.sessionId === draggedSessionId) return null;
  const side = x < panel.rect.left + panel.rect.width / 2 ? "left" : "right";
  return { side, rect: panel.rect, targetSession };
}

function terminalDropPanels(root) {
  const seen = new Set();
  return Array.from(root.querySelectorAll("[id^='terminal-panel-'], [data-codex-terminal]"))
    .filter((node) => node instanceof HTMLElement)
    .map((node) => ({ node, rect: node.getBoundingClientRect() }))
    .filter(({ node, rect }) => {
      if (seen.has(node.id || node)) return false;
      seen.add(node.id || node);
      return rect.width > 160 && rect.height > 100 && rect.bottom > 0 && rect.right > 0;
    });
}

function pointInRect(x, y, rect) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

function createSplitFromDraggedTab(state, draggedSession, drop) {
  const targetSession = drop.targetSession;
  if (!draggedSession?.sessionId || !targetSession?.sessionId || draggedSession.sessionId === targetSession.sessionId) return;
  const left = drop.side === "left" ? draggedSession.sessionId : targetSession.sessionId;
  const right = drop.side === "left" ? targetSession.sessionId : draggedSession.sessionId;
  storeTerminalSnapshot(draggedSession.sessionId);
  storeTerminalSnapshot(targetSession.sessionId);
  const existing = currentSplitPairForRoot(state, state.activeRoot || findTerminalRoot());
  let sessions = [];
  if (existing?.sessions.includes(targetSession.sessionId)) {
    sessions = existing.sessions.filter((sessionId) => sessionId !== draggedSession.sessionId);
    const targetIndex = sessions.indexOf(targetSession.sessionId);
    sessions.splice(drop.side === "left" ? targetIndex : targetIndex + 1, 0, draggedSession.sessionId);
  } else {
    sessions = [left, right];
  }
  sessions = sessions.slice(0, MAX_SPLIT_SESSIONS);
  writeSplitPair({
    conversationId: draggedSession.conversationId || targetSession.conversationId || null,
    anchor: existing?.anchor || targetSession.sessionId,
    left: sessions[0],
    right: sessions[1],
    sessions,
    existingSessions: existing?.sessions || sessions,
    ratio: existing?.ratio || 0.5,
    createdAt: Date.now(),
  });
  state.activeTab = findTerminalTabBySessionId(state.activeRoot || findTerminalRoot(), targetSession.sessionId) || state.activeTab;
  triggerTerminalRerender(state, targetSession.sessionId);
  window.dispatchEvent(new Event("resize"));
  apply(state);
}

function splitDividerFromEventTarget(target) {
  return target instanceof Element ? target.closest(".codexpp-terminal-split-divider") : null;
}

function beginSplitResize(state, event) {
  const root = state.activeRoot || findTerminalRoot();
  const rect = root?.getBoundingClientRect();
  if (!root || !rect || rect.width < 160) return;
  state.splitDrag = { root, rect };
  document.documentElement.setAttribute(SPLIT_DRAGGING_ATTR, "true");
  event.preventDefault();
  event.stopPropagation();
  updateSplitResize(state, event);
}

function updateSplitResize(state, event) {
  if (!state.splitDrag) return;
  const { root, rect } = state.splitDrag;
  const ratio = Math.max(0.2, Math.min(0.8, (event.clientX - rect.left) / rect.width));
  const pair = readSplitPair();
  if (!pair) return;
  pair.ratio = ratio;
  writeSplitPair(pair);
  applySplitRatio(root, ratio);
  window.dispatchEvent(new Event("resize"));
}

function endSplitResize(state) {
  if (!state.splitDrag) return;
  state.splitDrag = null;
  document.documentElement.removeAttribute(SPLIT_DRAGGING_ATTR);
  window.dispatchEvent(new Event("resize"));
}

function storeTerminalSnapshot(sessionId) {
  if (!sessionId) return;
  try {
    localStorage.removeItem(`${TERMINAL_SNAPSHOT_KEY_PREFIX}${sessionId}`);
  } catch {
    // Best effort only; Codex's internal terminal buffer is the primary source.
  }
}

function applySplitRatio(root, ratio) {
  if (!(root instanceof HTMLElement)) return;
  const value = `${(ratio * 100).toFixed(2)}%`;
  root.style.setProperty("--codexpp-terminal-split-left", value);
  root.querySelectorAll(".codexpp-terminal-split-view").forEach((node) => {
    if (node instanceof HTMLElement) node.style.setProperty("--codexpp-terminal-split-left", value);
  });
}

function triggerTerminalRerender(state, preferredSessionId) {
  window.dispatchEvent(new Event("codexpp:better-terminal:split-change"));
  window.dispatchEvent(new Event("resize"));
  if (preferredSessionId) {
    window.setTimeout(() => focusTerminalInputForSession(state.activeRoot || findTerminalRoot(), preferredSessionId), 80);
  }
}

function activateTerminalTabElement(tab) {
  if (invokeTerminalTabActivate(tab)) return;
  tab.dispatchEvent(new MouseEvent("mousedown", {
    bubbles: true,
    cancelable: true,
    composed: true,
    button: 0,
    buttons: 1,
  }));
  tab.dispatchEvent(new MouseEvent("mouseup", {
    bubbles: true,
    cancelable: true,
    composed: true,
    button: 0,
    buttons: 0,
  }));
  tab.dispatchEvent(new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
    composed: true,
    button: 0,
    buttons: 0,
  }));
}

function invokeTerminalTabClose(tab) {
  let fiber = reactFiberFromNode(tab);
  const seen = new Set();
  for (let depth = 0; fiber && depth < 24 && !seen.has(fiber); depth += 1) {
    seen.add(fiber);
    const close =
      fiber.memoizedProps?.onClose ||
      fiber.pendingProps?.onClose ||
      fiber.memoizedProps?.tab?.onClose ||
      fiber.pendingProps?.tab?.onClose;
    if (typeof close === "function") {
      close({
        button: 0,
        preventDefault() {},
        stopPropagation() {},
      });
      return true;
    }
    fiber = fiber.return;
  }
  return false;
}

function invokeTerminalTabActivate(tab) {
  let fiber = reactFiberFromNode(tab);
  const seen = new Set();
  for (let depth = 0; fiber && depth < 24 && !seen.has(fiber); depth += 1) {
    seen.add(fiber);
    const activate =
      fiber.memoizedProps?.onActivate ||
      fiber.pendingProps?.onActivate ||
      fiber.memoizedProps?.onMouseDown ||
      fiber.pendingProps?.onMouseDown ||
      fiber.memoizedProps?.tab?.onActivate ||
      fiber.pendingProps?.tab?.onActivate;
    if (typeof activate === "function") {
      activate({
        button: 0,
        buttons: 1,
        preventDefault() {},
        stopPropagation() {},
      });
      return true;
    }
    fiber = fiber.return;
  }
  return false;
}

function findTerminalTabBySessionId(root, sessionId) {
  if (!root || !sessionId) return null;
  const candidates = root.querySelectorAll("[role='tab'], button, [role='button']");
  for (const node of candidates) {
    const session = terminalSessionFromNode(globalThis.__codexppBetterTerminalState, node);
    if (session?.sessionId === sessionId) return terminalTabActivationTarget(node);
  }
  return null;
}

function terminalCloseControlForSession(root, sessionId) {
  const marker = terminalTabElementsForSession(root || document, sessionId)[0];
  if (!(marker instanceof HTMLElement)) return null;
  const controls = marker.querySelectorAll("button, [role='button'], [aria-label], [title]");
  for (const control of controls) {
    if (!(control instanceof HTMLElement)) continue;
    const label = compactText(`${control.textContent || ""} ${control.getAttribute("aria-label") || ""} ${control.getAttribute("title") || ""}`);
    if (/\b(close|dismiss|remove)\b/i.test(label)) return control;
  }
  return null;
}

function terminalTabActivationTarget(node) {
  if (!(node instanceof HTMLElement)) return node;
  return node.querySelector("button[role='tab'], button") || node;
}

function readTerminalPopoutEntries() {
  try {
    const raw = window.localStorage.getItem(TERMINAL_POPOUTS_KEY);
    const parsed = JSON.parse(raw || "{}");
    if (!parsed || typeof parsed !== "object") return {};
    const now = Date.now();
    const entries = {};
    for (const [sessionId, entry] of Object.entries(parsed)) {
      if (!entry || typeof entry !== "object") continue;
      if (now - Number(entry.updatedAt || entry.createdAt || 0) > 60 * 60 * 1000) continue;
      if (entry.status === "open" && now - Number(entry.updatedAt || entry.createdAt || 0) > TERMINAL_POPOUT_STALE_MS) {
        entries[sessionId] = { ...entry, status: "closed", closedAt: now };
        continue;
      }
      if (entry.status === "open" && Number(entry.closedAt || 0) > 0) {
        entries[sessionId] = { ...entry, status: "closed" };
        continue;
      }
      entries[sessionId] = entry;
    }
    return entries;
  } catch {
    return {};
  }
}

function writeTerminalPopoutEntries(entries) {
  try {
    window.localStorage.setItem(TERMINAL_POPOUTS_KEY, JSON.stringify(entries || {}));
  } catch {}
}

function createTerminalPopoutEntry({ sourceSessionId, conversationId, title }) {
  if (!sourceSessionId) return null;
  const popoutId = `${sourceSessionId}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
  const entries = readTerminalPopoutEntries();
  entries[sourceSessionId] = {
    popoutId,
    sourceSessionId,
    conversationId: conversationId || null,
    title: title || "Terminal",
    status: "open",
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  writeTerminalPopoutEntries(entries);
  return popoutId;
}

function updateTerminalPopoutEntry(sourceSessionId, patch) {
  if (!sourceSessionId) return;
  const entries = readTerminalPopoutEntries();
  entries[sourceSessionId] = {
    ...(entries[sourceSessionId] || { sourceSessionId, createdAt: Date.now() }),
    ...patch,
    sourceSessionId,
    updatedAt: Date.now(),
  };
  writeTerminalPopoutEntries(entries);
}

function clearTerminalPopoutEntry(sourceSessionId) {
  if (!sourceSessionId) return;
  const entries = readTerminalPopoutEntries();
  delete entries[sourceSessionId];
  writeTerminalPopoutEntries(entries);
}

function isTerminalSessionPoppedOut(sessionId) {
  if (!sessionId) return false;
  const entry = readTerminalPopoutEntries()[sessionId];
  return Boolean(entry && entry.status === "open");
}

function syncTerminalPopoutOpen(state) {
  if (!state.terminalWindowMode || !state.terminalWindowSourceSessionId) return;
  const active = visibleTerminalSession(document, state) || activeTerminalSession(state);
  const snapshot = active?.sessionId ? terminalSnapshotForSession(state, active.sessionId) : null;
  updateTerminalPopoutEntry(state.terminalWindowSourceSessionId, {
    popoutId: state.terminalWindowPopoutId || null,
    popoutSessionId: active?.sessionId || null,
    conversationId: state.terminalWindowConversationId || active?.conversationId || null,
    title: document.title || "Terminal",
    status: "open",
    buffer: snapshot?.buffer || "",
  });
}

function syncTerminalPopoutClose(state) {
  if (!state.terminalWindowMode || !state.terminalWindowSourceSessionId) return;
  const active = visibleTerminalSession(document, state) || activeTerminalSession(state);
  const snapshot = active?.sessionId ? terminalSnapshotForSession(state, active.sessionId) : null;
  updateTerminalPopoutEntry(state.terminalWindowSourceSessionId, {
    status: "closed",
    popoutSessionId: active?.sessionId || null,
    buffer: snapshot?.buffer || "",
    closedAt: Date.now(),
  });
}

function returnTerminalPopoutToTab(state) {
  if (!state.terminalWindowMode) return false;
  if (state.terminalWindowReturning) return true;
  state.terminalWindowReturning = true;
  syncTerminalPopoutClose(state);
  const sourceSessionId = state.terminalWindowSourceSessionId;
  if (sourceSessionId) {
    state.api.ipc.invoke?.(TERMINAL_POPOUT_RETURN_CHANNEL, { sourceSessionId }).catch((error) => {
      state.api.log.warn("[better-terminal] failed to close terminal popout on shortcut", String(error));
    });
  }
  window.setTimeout(() => {
    try {
      window.close();
    } catch {}
  }, 80);
  return true;
}

function terminalSnapshotForSession(state, sessionId) {
  if (!sessionId) return null;
  return readPageTerminalManagerSnapshots(state, { includeBuffer: true }).find((snapshot) => snapshot.sessionId === sessionId) || null;
}

function applyTerminalPopoutPlaceholders(state, root) {
  if (state.terminalWindowMode) return;
  const entries = readTerminalPopoutEntries();
  const openEntries = new Map();
  for (const entry of Object.values(entries)) {
    if (!entry?.sourceSessionId) continue;
    if (entry.status === "closed" || entry.status === "returned") {
      restoreTerminalPopoutBuffer(state, entry);
      clearTerminalPopoutEntry(entry.sourceSessionId);
      continue;
    }
    if (entry.status === "open") openEntries.set(entry.sourceSessionId, entry);
  }

  document.querySelectorAll(`[${TERMINAL_POPOUT_PARKED_ATTR}="true"]`).forEach((node) => {
    const sessionId = terminalSessionFromNode(state, node)?.sessionId;
    if (!sessionId || !openEntries.has(sessionId)) {
      node.removeAttribute(TERMINAL_POPOUT_PARKED_ATTR);
      node.querySelector?.(`[${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="root"]`)?.remove();
    }
  });

  for (const [sessionId, entry] of openEntries) {
    const panel = terminalPanelElementForSession(state, root || document, sessionId);
    if (!(panel instanceof HTMLElement)) continue;
    panel.setAttribute(TERMINAL_POPOUT_PARKED_ATTR, "true");
    ensureTerminalPopoutPlaceholder(state, panel, entry);
  }
}

function terminalPanelElementForSession(state, root, sessionId) {
  if (!sessionId) return null;
  const exact = document.getElementById(`terminal-panel-${sessionId}`);
  if (exact instanceof HTMLElement) return exact;
  const scope = root instanceof Element || root === document ? root : document;
  const candidates = Array.from(scope.querySelectorAll?.("[id^='terminal-panel-'], [data-codex-terminal], .xterm") || []);
  for (const candidate of candidates) {
    const session = terminalSessionFromNode(state, candidate);
    if (session?.sessionId !== sessionId) continue;
    const panel = candidate.closest?.("[id^='terminal-panel-']");
    if (panel instanceof HTMLElement) return panel;
    if (candidate.matches?.("[data-codex-terminal]") && candidate.querySelector?.(".xterm")) return candidate;
    const terminalParent = candidate.closest?.("[data-codex-terminal]");
    if (terminalParent instanceof HTMLElement && terminalParent.querySelector?.(".xterm")) return terminalParent;
  }
  return null;
}

function ensureTerminalPopoutPlaceholder(state, panel, entry) {
  let placeholder = panel.querySelector(`[${TERMINAL_POPOUT_PLACEHOLDER_ATTR}="root"]`);
  if (placeholder) return placeholder;
  placeholder = document.createElement("div");
  placeholder.setAttribute(TERMINAL_POPOUT_PLACEHOLDER_ATTR, "root");

  const card = document.createElement("div");
  card.setAttribute(TERMINAL_POPOUT_PLACEHOLDER_ATTR, "card");
  const title = document.createElement("div");
  title.setAttribute(TERMINAL_POPOUT_PLACEHOLDER_ATTR, "title");
  title.textContent = `${entry.title || "Terminal"} is open in a window`;
  const actions = document.createElement("div");
  actions.setAttribute(TERMINAL_POPOUT_PLACEHOLDER_ATTR, "actions");

  const reveal = terminalPopoutPlaceholderButton("Reveal window");
  reveal.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    state.api.ipc.invoke?.(TERMINAL_POPOUT_REVEAL_CHANNEL, { sourceSessionId: entry.sourceSessionId }).catch((error) => {
      state.api.log.warn("[better-terminal] failed to reveal terminal popout", String(error));
    });
  });

  const returnToTab = terminalPopoutPlaceholderButton("Return to tab");
  returnToTab.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    updateTerminalPopoutEntry(entry.sourceSessionId, { status: "returning" });
    state.api.ipc.invoke?.(TERMINAL_POPOUT_RETURN_CHANNEL, { sourceSessionId: entry.sourceSessionId }).catch((error) => {
      state.api.log.warn("[better-terminal] failed to return terminal popout", String(error));
    });
    window.setTimeout(() => {
      const latest = readTerminalPopoutEntries()[entry.sourceSessionId];
      if (latest?.status !== "closed") clearTerminalPopoutEntry(entry.sourceSessionId);
      scheduleApply(state);
    }, 650);
  });

  actions.append(reveal, returnToTab);
  card.append(title, actions);
  placeholder.append(card);
  panel.appendChild(placeholder);
  return placeholder;
}

function terminalPopoutPlaceholderButton(label) {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute(TERMINAL_POPOUT_PLACEHOLDER_ATTR, "button");
  button.textContent = label;
  return button;
}

function restoreTerminalPopoutBuffer(state, entry) {
  if (!entry?.sourceSessionId || !entry.buffer) return;
  const script = document.createElement("script");
  script.textContent = `(() => {
    const sessionId = ${JSON.stringify(entry.sourceSessionId)};
    const buffer = ${JSON.stringify(entry.buffer)};
    try {
      const manager = globalThis.__codexppTerminalManager;
      manager?.replaceSnapshotBuffer?.(sessionId, buffer);
      const listener = manager?.listeners?.get?.(sessionId);
      if (listener?.onData) listener.onData("\\u001b[3J\\u001b[H\\u001b[2J" + buffer);
    } catch {}
  })();`;
  try {
    document.documentElement.appendChild(script);
    script.remove();
  } catch (error) {
    state.api.log.debug("[better-terminal] failed to restore terminal popout buffer", String(error));
  }
}

async function openTerminalPopoutWindow(state) {
  const title = activeTabTitle(state);
  const bounds = centeredBounds(940, 660);
  const root = state.activeRoot || findTerminalRoot();
  const active = activeTerminalSession(state) || visibleTerminalSession(state.activeRoot || findTerminalRoot() || document, state);
  const conversationId = active?.conversationId || findConversationId(state) || (await findConversationIdViaPageWorld(state));
  const route = currentInitialRoute();
  const sourceSessionId = active?.sessionId || null;
  const popoutId = sourceSessionId ? createTerminalPopoutEntry({ sourceSessionId, conversationId, title }) : null;
  const splitPair = currentSplitPairForRoot(state, root);
  const sourceIsSplitPane = Boolean(sourceSessionId && splitPair?.sessions?.includes(sourceSessionId));
  const fallbackSessionId = sourceIsSplitPane || splitPair ? null : fallbackTerminalSessionIdAfterPopout(state, sourceSessionId);
  if (sourceIsSplitPane) {
    writeSplitPair({
      ...splitPair,
      preserveUnmountedUntil: Date.now() + SPLIT_PRESERVE_UNMOUNTED_MS,
    });
  }
  state.pendingTerminalPopoutId = popoutId;
  if (fallbackSessionId) activateTerminalSessionAfterPopout(state, fallbackSessionId);
  if (await openTerminalPopoutViaRawIpc(state, title, bounds, conversationId, sourceSessionId, route)) {
    state.pendingTerminalPopoutId = null;
    if (fallbackSessionId) activateTerminalSessionAfterPopout(state, fallbackSessionId, { extendedFocus: true });
    scheduleApply(state);
    return;
  }
  try {
    await withTimeout(state.api.ipc.invoke(OPEN_TERMINAL_WINDOW_CHANNEL, {
      conversationId,
      route,
      hostId: currentHostId(),
      title,
      bounds,
      sourceSessionId,
      popoutId,
    }), 1500);
    state.pendingTerminalPopoutId = null;
    if (fallbackSessionId) activateTerminalSessionAfterPopout(state, fallbackSessionId, { extendedFocus: true });
    scheduleApply(state);
    return;
  } catch (error) {
    if (sourceSessionId) clearTerminalPopoutEntry(sourceSessionId);
    state.pendingTerminalPopoutId = null;
    state.api.log.warn("[better-terminal] terminal popout failed", String(error));
  }
  if (conversationId && openTerminalOverlayViaMessageBridge(conversationId, title)) return;

  try {
    await state.api.ipc.invoke("open-terminal-window-focused-message", {
      conversationId,
      route: currentInitialRoute(),
      title,
      bounds,
    });
  } catch (error) {
    state.api.log.warn("[better-terminal] focused terminal popout failed", String(error));
  }
}

function withTimeout(promise, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(`Timed out after ${timeoutMs}ms`)), timeoutMs);
    Promise.resolve(promise).then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function fallbackTerminalSessionIdAfterPopout(state, sourceSessionId) {
  if (!sourceSessionId) return null;
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return null;
  const candidate = terminalTabsBySession(root, state)
    .map((tab) => {
      const marker = terminalTabMarker(tab);
      const session = terminalSessionFromNode(state, tab) || terminalSessionFromNode(state, marker);
      return { tab, marker, session };
    })
    .find(({ session }) => session?.sessionId && session.sessionId !== sourceSessionId);
  return candidate?.session?.sessionId || null;
}

function activateTerminalSessionAfterPopout(state, sessionId, options = {}) {
  if (!sessionId) return false;
  const root = state.activeRoot || findTerminalRoot();
  if (!root) return false;
  const tab = findTerminalTabBySessionId(root, sessionId);
  if (!(tab instanceof HTMLElement)) return false;
  clearActiveSessionOverride(state);
  activateTerminalTabElement(terminalTabActivationTarget(tab));
  const delays = options.extendedFocus ? [40, 120, 260, 600, 1100, 1800] : [40, 120, 260];
  delays.forEach((delay) => {
    window.setTimeout(() => {
      const nextRoot = state.activeRoot || findTerminalRoot();
      focusTerminalInputForSession(nextRoot, sessionId);
      scheduleApply(state);
    }, delay);
  });
  return true;
}

function openTerminalOverlayViaMessageBridge(conversationId, title) {
  try {
    const payload = {
      conversationId,
      hostId: currentHostId(),
      title,
      createdAt: Date.now(),
    };
    const message = {
      type: "open-thread-overlay",
      conversationId,
      hostId: payload.hostId,
      title,
    };
    window.localStorage.setItem(TERMINAL_WINDOW_PENDING_KEY, JSON.stringify(payload));
    const bridge = window.electronBridge;
    if (typeof bridge?.sendMessageFromView === "function") {
      bridge.sendMessageFromView(message).catch?.(() => {});
    }

    const script = document.createElement("script");
    script.textContent = `(() => {
      const message = ${JSON.stringify(message)};
      try {
        const result = window.electronBridge?.sendMessageFromView?.(message);
        result?.catch?.(() => {});
      } catch {}
      try {
        window.dispatchEvent(new CustomEvent("codex-message-from-view", { detail: message }));
      } catch {}
    })();`;
    (document.documentElement || document.head || document.body).appendChild(script);
    script.remove();
    return true;
  } catch {
    return false;
  }
}

async function openTerminalPopoutViaRawIpc(state, title, bounds, conversationId, sourceSessionId, route) {
  let electron;
  try {
    electron = require("electron");
  } catch {
    return false;
  }
  try {
    await electron.ipcRenderer.invoke(RAW_OPEN_CHANNEL, {
      conversationId,
      route,
      title,
      bounds,
      hostId: currentHostId(),
      sourceSessionId,
      popoutId: state.pendingTerminalPopoutId || null,
    });
    return true;
  } catch (error) {
    state.api.log.warn("[better-terminal] raw terminal popout failed", String(error));
    return false;
  }
}

function pageWorldConversationIdExpression() {
  return `(() => {
    const metadata = ${pageWorldTerminalMetadataExpression()};
    if (metadata?.conversationId) return metadata.conversationId;
    return ${pageWorldVisibleConversationIdExpression()};
  })();`;
}

function pageWorldVisibleConversationIdExpression() {
  return `(() => {
    const isConversationId = (value) =>
      typeof value === "string" && /^019[0-9a-z-]{20,}$/i.test(value) && !value.startsWith("home:");
    const sidebarRow = document.querySelector("[data-app-action-sidebar-thread-active='true'][data-app-action-sidebar-thread-id], [data-app-action-sidebar-thread-row][aria-current='page'][data-app-action-sidebar-thread-id]");
    const sidebarId = sidebarRow?.getAttribute?.("data-app-action-sidebar-thread-id")?.replace(/^local:/, "");
    if (isConversationId(sidebarId)) return sidebarId;
    const fromProps = (props) => {
      if (!props || typeof props !== "object") return null;
      if (isConversationId(props.conversationId)) return props.conversationId;
      if (isConversationId(props.id) && /conversation|thread|chat/i.test(String(props.type || props.kind || props.__typename || ""))) {
        return props.id;
      }
      return null;
    };
    const fiberForNode = (node) => {
      if (!node) return null;
      for (const key of Object.keys(node)) {
        if (key.startsWith("__reactFiber") || key.startsWith("__reactInternalInstance")) return node[key];
      }
      return null;
    };
    const fromFiber = (fiber) => {
      const seen = new Set();
      let current = fiber;
      for (let depth = 0; current && depth < 140 && !seen.has(current); depth += 1) {
        seen.add(current);
        const id = fromProps(current.memoizedProps) || fromProps(current.pendingProps);
        if (id) return id;
        current = current.return;
      }
      return null;
    };
    const visibleScore = (node) => {
      if (!node?.getBoundingClientRect) return 0;
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.bottom <= 0 || rect.right <= 0) return 0;
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return 0;
      const centerBias = rect.left > 220 ? 2 : 1;
      return rect.width * rect.height * centerBias;
    };
    const seeds = Array.from(document.querySelectorAll("main, [role='main'], textarea, [contenteditable='true'], article, section, div, button"))
      .sort((a, b) => visibleScore(b) - visibleScore(a))
      .slice(0, 250);
    for (const seed of seeds) {
      const id = fromFiber(fiberForNode(seed));
      if (id) return id;
    }
    return null;
  })()`;
}

function pageWorldTerminalMetadataExpression() {
  return `(() => {
    const isConversationId = (value) =>
      typeof value === "string" && value.length > 0 && !value.startsWith("home:");
    const sessionIdFromNode = (node) => {
      const raw =
        node?.id ||
        node?.getAttribute?.("id") ||
        node?.closest?.("[id^='terminal-panel-']")?.id ||
        node?.closest?.("[data-tab-id^='terminal:']")?.getAttribute("data-tab-id") ||
        "";
      const match = /^terminal(?::|-panel-)(.+)$/.exec(raw);
      return match?.[1] || null;
    };
    const fromTerminalManager = (sessionId) => {
      if (!sessionId) return null;
      const manager = globalThis.__codexppTerminalManager;
      const value = manager?.sessionConversations?.get?.(sessionId);
      return isConversationId(value) ? value : null;
    };
    const fromProps = (props) => {
      if (!props || typeof props !== "object") return null;
      return isConversationId(props.conversationId) ? props.conversationId : null;
    };
    const fiberForNode = (node) => {
      if (!node) return null;
      for (const key of Object.keys(node)) {
        if (key.startsWith("__reactFiber") || key.startsWith("__reactInternalInstance")) return node[key];
      }
      return null;
    };
    const visibleScore = (node) => {
      if (!node?.getBoundingClientRect) return 0;
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.bottom <= 0 || rect.right <= 0) return 0;
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return 0;
      return rect.width * rect.height;
    };
    const fromFiber = (fiber) => {
      const seen = new Set();
      let current = fiber;
      for (let depth = 0; current && depth < 120 && !seen.has(current); depth += 1) {
        seen.add(current);
        const id = fromProps(current.memoizedProps) || fromProps(current.pendingProps);
        if (id) return id;
        current = current.return;
      }
      return null;
    };
    const activeTerminal =
      document.activeElement?.closest?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm, [data-tab-id^='terminal:']");
    const seeds = [
      activeTerminal,
      ...Array.from(document.querySelectorAll("[data-codex-terminal], .xterm, [id^='terminal-panel-'], [data-tab-id^='terminal:']"))
        .sort((a, b) => visibleScore(b) - visibleScore(a)),
    ].filter(Boolean);
    for (const seed of seeds) {
      const fromManager = fromTerminalManager(sessionIdFromNode(seed));
      if (fromManager) {
        let hostId = null;
        try {
          hostId = new URL(window.location.href).searchParams.get("hostId");
        } catch {}
        return { conversationId: fromManager, hostId: hostId || "local" };
      }
      let node = seed;
      for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
        const fromAncestorManager = fromTerminalManager(sessionIdFromNode(node));
        if (fromAncestorManager) {
          let hostId = null;
          try {
            hostId = new URL(window.location.href).searchParams.get("hostId");
          } catch {}
          return { conversationId: fromAncestorManager, hostId: hostId || "local" };
        }
        const conversationId = fromFiber(fiberForNode(node));
        if (conversationId) {
          let hostId = null;
          try {
            hostId = new URL(window.location.href).searchParams.get("hostId");
          } catch {}
          return { conversationId, hostId: hostId || "local" };
        }
      }
    }
    return null;
  })();`;
}

function conversationRoute(conversationId) {
  return `/local/${encodeURIComponent(conversationId)}`;
}

function threadOverlayRoute(conversationId) {
  return `/thread-overlay/${encodeURIComponent(conversationId)}`;
}

function terminalWindowRoute(conversationId, title) {
  return terminalWindowInitialRoute(conversationId, title);
}

function terminalWindowInitialRoute(conversationId, title, payload = {}) {
  void title;
  if (typeof payload?.route === "string" && payload.route.trim()) return payload.route.trim();
  if (conversationId && !String(conversationId).startsWith("home:")) return conversationRoute(conversationId);
  return "/";
}

function terminalWindowAppUrl(conversationId, title, hostId = "local", payload = {}) {
  const url = new URL("app://-/index.html");
  url.searchParams.set("initialRoute", terminalWindowInitialRoute(conversationId, title, payload));
  url.searchParams.set("hostId", hostId || "local");
  url.searchParams.set("codexppTerminalWindow", "1");
  if (typeof title === "string" && title.trim()) {
    url.searchParams.set("codexppTerminalTitle", title.trim());
  }
  if (typeof payload?.sourceSessionId === "string" && payload.sourceSessionId) {
    url.searchParams.set("codexppTerminalSourceSessionId", payload.sourceSessionId);
  }
  if (typeof conversationId === "string" && conversationId) {
    url.searchParams.set("codexppTerminalConversationId", conversationId);
  }
  if (typeof payload?.popoutId === "string" && payload.popoutId) {
    url.searchParams.set("codexppTerminalPopoutId", payload.popoutId);
  }
  return String(url);
}

function currentHostId() {
  try {
    return new URL(window.location.href).searchParams.get("hostId") || "local";
  } catch {
    return "local";
  }
}

function currentInitialRoute() {
  try {
    const url = new URL(window.location.href);
    const initialRoute = url.searchParams.get("initialRoute");
    if (initialRoute) return initialRoute;
    const path = `${url.pathname || "/"}${url.search || ""}`;
    if (url.protocol === "app:" && path.startsWith("/index.html")) return "/";
    return path || "/";
  } catch {
    return "/";
  }
}

function activateTerminalWindowMode(state, payload) {
  state.terminalWindowMode = true;
  state.terminalWindowConversationId = payload?.conversationId || null;
  state.terminalWindowSourceSessionId = payload?.sourceSessionId || null;
  state.terminalWindowPopoutId = payload?.popoutId || null;
  document.title = payload?.title || "Terminal";
  document.documentElement.setAttribute(TERMINAL_WINDOW_ATTR, "true");
  document.documentElement.removeAttribute("data-codexpp-better-terminal-ready");
  state.terminalWindowAttempts = 0;
  state.terminalWindowLastToggleAt = 0;
  if (state.terminalWindowTimer) window.clearInterval(state.terminalWindowTimer);
  state.terminalWindowTimer = window.setInterval(() => ensureTerminalWindowOpen(state), 250);
  ensureTerminalWindowOpen(state);
}

function activateTerminalWindowFromRoute(state) {
  const payload = terminalWindowPayloadFromLocation();
  if (payload) activateTerminalWindowMode(state, payload);
}

function activateTerminalWindowFromPendingMarker(state) {
  const conversationId = conversationIdFromCurrentRoute();
  if (!conversationId) return;
  const payload = readPendingTerminalWindowPayload();
  if (!payload || payload.conversationId !== conversationId) return;
  try {
    window.localStorage.removeItem(TERMINAL_WINDOW_PENDING_KEY);
  } catch {}
  activateTerminalWindowMode(state, payload);
}

function readPendingTerminalWindowPayload() {
  try {
    const raw = window.localStorage.getItem(TERMINAL_WINDOW_PENDING_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw);
    if (!payload || typeof payload !== "object") return null;
    if (Date.now() - Number(payload.createdAt || 0) > 30_000) {
      window.localStorage.removeItem(TERMINAL_WINDOW_PENDING_KEY);
      return null;
    }
    return {
      conversationId: typeof payload.conversationId === "string" ? payload.conversationId : null,
      title: typeof payload.title === "string" ? payload.title : "Terminal",
    };
  } catch {
    return null;
  }
}

function conversationIdFromCurrentRoute() {
  try {
    const url = new URL(window.location.href);
    const initialRoute = url.searchParams.get("initialRoute") || "";
    const route = initialRoute ? new URL(initialRoute, "app://codex") : url;
    const match = route.pathname.match(/^\/(?:local|thread-overlay)\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

function terminalWindowPayloadFromLocation() {
  try {
    const url = new URL(window.location.href);
    const initialRoute = url.searchParams.get("initialRoute") || "";
    const route = initialRoute ? new URL(initialRoute, "app://codex") : url;
    if (url.searchParams.get("codexppTerminalWindow") !== "1" && route.searchParams.get("codexppTerminalWindow") !== "1") return null;
    const title = url.searchParams.get("codexppTerminalTitle") || route.searchParams.get("codexppTerminalTitle") || "Terminal";
    const match = route.pathname.match(/^\/(?:local|thread-overlay)\/([^/?#]+)/);
    return {
      title,
      conversationId: url.searchParams.get("codexppTerminalConversationId") || route.searchParams.get("codexppTerminalConversationId") || (match ? decodeURIComponent(match[1]) : null),
      sourceSessionId: url.searchParams.get("codexppTerminalSourceSessionId") || route.searchParams.get("codexppTerminalSourceSessionId") || null,
      popoutId: url.searchParams.get("codexppTerminalPopoutId") || route.searchParams.get("codexppTerminalPopoutId") || null,
    };
  } catch {
    return null;
  }
}

function ensureTerminalWindowOpen(state) {
  state.terminalWindowAttempts += 1;
  const root = findTerminalRoot();
  if (visibleTerminalWindowRoot(root || document)) {
    applyTerminalWindowMode(state);
    if (state.terminalWindowAttempts > 3 && state.terminalWindowTimer) {
      window.clearInterval(state.terminalWindowTimer);
      state.terminalWindowTimer = null;
    }
    return;
  }

  document.documentElement.removeAttribute("data-codexpp-better-terminal-ready");
  const toggle = Array.from(document.querySelectorAll("button, [role='button']"))
    .find((node) => /\btoggle terminal\b/i.test(`${node.textContent || ""} ${node.getAttribute("aria-label") || ""} ${node.getAttribute("title") || ""}`));
  const now = Date.now();
  if (now - (state.terminalWindowLastToggleAt || 0) > 3000) {
    state.terminalWindowLastToggleAt = now;
    if (toggle instanceof HTMLElement) {
      toggle.click();
    } else if (!requestTrustedTerminalToggle() && !requestTerminalMessageBusToggle()) {
      requestSyntheticTerminalToggle();
    }
  }

  if (state.terminalWindowAttempts > 180 && state.terminalWindowTimer) {
    window.clearInterval(state.terminalWindowTimer);
    state.terminalWindowTimer = null;
  }
}

function requestTerminalMessageBusToggle() {
  try {
    window.postMessage({ type: "toggle-terminal" }, window.location.origin || "*");
    return true;
  } catch {
    return false;
  }
}

function requestTrustedTerminalToggle() {
  try {
    const electron = require("electron");
    electron.ipcRenderer?.invoke?.(TERMINAL_TOGGLE_SHORTCUT_CHANNEL).catch?.(() => {});
    return true;
  } catch {
    const invoke = globalThis.__codexppBetterTerminalState?.api?.ipc?.invoke;
    if (typeof invoke !== "function") return false;
    invoke(TERMINAL_TOGGLE_SHORTCUT_API_CHANNEL).catch?.(() => {});
    return true;
  }
}

function requestSyntheticTerminalToggle() {
  try {
    dispatchMetaKey("j", "KeyJ", document.body);
    return true;
  } catch {
    return false;
  }
}

function applyTerminalWindowMode(state) {
  document.documentElement.setAttribute(TERMINAL_WINDOW_ATTR, "true");
  ensureTerminalWindowChrome(state);
  const terminal = visibleTerminalWindowRoot(document);
  if (terminal instanceof HTMLElement) {
    document.documentElement.setAttribute("data-codexpp-better-terminal-ready", "true");
    terminal.removeAttribute("data-codex-terminal-window-hidden");
    terminal.querySelector("textarea[aria-label='Terminal input'], .xterm-helper-textarea")?.focus();
    syncTerminalPopoutOpen(state);
  } else {
    document.documentElement.removeAttribute("data-codexpp-better-terminal-ready");
  }
  requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
}

function ensureTerminalWindowChrome(state) {
  let chrome = document.querySelector(`[${TERMINAL_WINDOW_CHROME_ATTR}="root"]`);
  if (chrome) {
    const title = chrome.querySelector(`[${TERMINAL_WINDOW_CHROME_ATTR}="title"]`);
    const alwaysOnTop = chrome.querySelector(`[${TERMINAL_WINDOW_CHROME_ATTR}="always-on-top"]`);
    if (title && alwaysOnTop) {
      const primaryTitle = title.querySelector(`span:not([${TERMINAL_WINDOW_CHROME_ATTR}="title-muted"])`);
      if (primaryTitle) primaryTitle.textContent = document.title || "Terminal";
      return chrome;
    }
    chrome.replaceChildren();
  } else {
    chrome = document.createElement("div");
    chrome.setAttribute(TERMINAL_WINDOW_CHROME_ATTR, "root");
  }

  const title = document.createElement("div");
  title.setAttribute(TERMINAL_WINDOW_CHROME_ATTR, "title");
  const primaryTitle = document.createElement("span");
  primaryTitle.textContent = document.title || "Terminal";
  const mutedTitle = document.createElement("span");
  mutedTitle.setAttribute(TERMINAL_WINDOW_CHROME_ATTR, "title-muted");
  mutedTitle.textContent = "terminal";
  title.append(primaryTitle, mutedTitle);

  const alwaysOnTop = document.createElement("button");
  alwaysOnTop.type = "button";
  alwaysOnTop.setAttribute(TERMINAL_WINDOW_CHROME_ATTR, "always-on-top");
  alwaysOnTop.setAttribute("aria-label", "Toggle always on top");
  alwaysOnTop.setAttribute("title", "Toggle always on top");
  alwaysOnTop.setAttribute("aria-pressed", "false");
  alwaysOnTop.innerHTML = [
    '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" fill="none" xmlns="http://www.w3.org/2000/svg" class="icon-sm">',
    '<path d="M7.70018 9.5C8.0867 9.5001 8.40037 9.81366 8.40037 10.2002C8.40027 10.5866 8.08663 10.9003 7.70018 10.9004C7.31364 10.9004 7.00009 10.5867 6.99998 10.2002C6.99998 9.8136 7.31358 9.5 7.70018 9.5Z" fill="currentColor"/>',
    '<path d="M9.70018 9.5C10.0867 9.5001 10.4004 9.81366 10.4004 10.2002C10.4003 10.5866 10.0866 10.9003 9.70018 10.9004C9.31364 10.9004 9.00009 10.5867 8.99998 10.2002C8.99998 9.8136 9.31358 9.5 9.70018 9.5Z" fill="currentColor"/>',
    '<path d="M11.7002 9.5C12.0867 9.5001 12.4004 9.81366 12.4004 10.2002C12.4003 10.5866 12.0866 10.9003 11.7002 10.9004C11.3136 10.9004 11.0001 10.5867 11 10.2002C11 9.8136 11.3136 9.5 11.7002 9.5Z" fill="currentColor"/>',
    '<path d="M4.70018 4.5C5.0867 4.5001 5.40037 4.81366 5.40037 5.2002C5.40027 5.58665 5.08663 5.90029 4.70018 5.90039C4.31364 5.90039 4.00009 5.5867 3.99998 5.2002C3.99998 4.8136 4.31358 4.5 4.70018 4.5Z" fill="currentColor"/>',
    '<path d="M6.70018 4.5C7.0867 4.5001 7.40037 4.81366 7.40037 5.2002C7.40027 5.58665 7.08663 5.90029 6.70018 5.90039C6.31364 5.90039 6.00009 5.5867 5.99998 5.2002C5.99998 4.8136 6.31358 4.5 6.70018 4.5Z" fill="currentColor"/>',
    '<path d="M8.70018 4.5C9.0867 4.5001 9.40037 4.81366 9.40037 5.2002C9.40027 5.58665 9.08663 5.90029 8.70018 5.90039C8.31364 5.90039 8.00009 5.5867 7.99998 5.2002C7.99998 4.8136 8.31358 4.5 8.70018 4.5Z" fill="currentColor"/>',
    '<path fill-rule="evenodd" clip-rule="evenodd" d="M11.0605 2.13477C11.6793 2.13477 12.1834 2.13462 12.5918 2.16797C13.008 2.20197 13.3834 2.27391 13.7334 2.45215C14.2818 2.73159 14.7283 3.17814 15.0078 3.72656C15.186 4.07645 15.258 4.45204 15.292 4.86816C15.3253 5.27654 15.3252 5.78074 15.3252 6.39941V7.15137C15.4183 7.1557 15.5071 7.16105 15.5918 7.16797C16.008 7.20197 16.3834 7.27391 16.7334 7.45215C17.2818 7.73159 17.7283 8.17814 18.0078 8.72656C18.186 9.07645 18.258 9.45204 18.292 9.86816C18.3253 10.2765 18.3252 10.7807 18.3252 11.3994V13.5303C18.3252 14.1489 18.3253 14.6531 18.292 15.0615C18.258 15.4777 18.186 15.8532 18.0078 16.2031C17.7283 16.7516 17.2818 17.1981 16.7334 17.4775C16.3834 17.6558 16.008 17.7277 15.5918 17.7617C15.1834 17.7951 14.6793 17.7949 14.0605 17.7949H8.92967C8.31092 17.7949 7.80683 17.7951 7.39842 17.7617C6.98223 17.7277 6.60675 17.6558 6.25682 17.4775C5.70837 17.1981 5.26186 16.7516 4.98241 16.2031C4.80419 15.8532 4.73223 15.4777 4.69823 15.0615C4.66489 14.6531 4.66502 14.149 4.66502 13.5303V12.792C4.46542 12.79 4.30289 12.7856 4.15428 12.7637C2.88267 12.5759 1.88405 11.5773 1.69627 10.3057C1.66325 10.0818 1.66502 9.82621 1.66502 9.45996V6.39941C1.66502 5.78073 1.66488 5.27654 1.69823 4.86816C1.73224 4.45202 1.80418 4.07646 1.98241 3.72656C2.26188 3.17813 2.70837 2.7316 3.25682 2.45215C3.60675 2.27392 3.98223 2.20197 4.39842 2.16797C4.80683 2.13462 5.31091 2.13477 5.92967 2.13477H11.0605ZM8.92967 8.46484C8.28911 8.46484 7.84852 8.46527 7.50682 8.49316C7.1728 8.52045 6.99161 8.57082 6.86033 8.6377C6.56228 8.78961 6.31989 9.03204 6.16795 9.33008C6.10107 9.46133 6.05072 9.64261 6.02342 9.97656C5.99553 10.3182 5.9951 10.7589 5.9951 11.3994V13.5303C5.9951 14.1707 5.99554 14.6114 6.02342 14.9531C6.0507 15.2871 6.1011 15.4683 6.16795 15.5996C6.31988 15.8977 6.56228 16.1401 6.86033 16.292C6.99161 16.3589 7.17277 16.4092 7.50682 16.4365C7.84852 16.4644 8.28912 16.4648 8.92967 16.4648H14.0605C14.7011 16.4648 15.1417 16.4644 15.4834 16.4365C15.8174 16.4092 15.9986 16.3589 16.1299 16.292C16.4279 16.1401 16.6703 15.8977 16.8222 15.5996C16.8891 15.4683 16.9395 15.2871 16.9668 14.9531C16.9947 14.6114 16.9951 14.1707 16.9951 13.5303V11.3994C16.9951 10.7589 16.9947 10.3182 16.9668 9.97656C16.9395 9.64261 16.8891 9.46133 16.8222 9.33008C16.6703 9.03206 16.4279 8.78961 16.1299 8.6377C15.9986 8.57083 15.8174 8.52045 15.4834 8.49316C15.3214 8.47994 15.1371 8.47348 14.9199 8.46973H13.9951V8.46484H8.92967ZM5.92967 3.46484C5.28911 3.46484 4.84852 3.46527 4.50682 3.49316C4.1728 3.52045 3.99161 3.57082 3.86033 3.6377C3.56228 3.78961 3.31989 4.03204 3.16795 4.33008C3.10107 4.46133 3.05072 4.64261 3.02342 4.97656C2.99553 5.31823 2.9951 5.75895 2.9951 6.39941V9.45996C2.9951 9.8734 2.99653 10.0084 3.0117 10.1113C3.11379 10.8028 3.65718 11.3461 4.34862 11.4482C4.41654 11.4583 4.49838 11.4613 4.66502 11.4629V11.3994C4.66502 10.7807 4.66488 10.2765 4.69823 9.86816C4.73224 9.45202 4.80418 9.07646 4.98241 8.72656C5.26188 8.17813 5.70837 7.7316 6.25682 7.45215C6.60675 7.27392 6.98223 7.20197 7.39842 7.16797C7.80683 7.13462 8.31091 7.13477 8.92967 7.13477H13.9951V6.39941C13.9951 5.75895 13.9947 5.31823 13.9668 4.97656C13.9395 4.64261 13.8891 4.46133 13.8222 4.33008C13.6703 4.03206 13.4279 3.78961 13.1299 3.6377C12.9986 3.57083 12.8174 3.52045 12.4834 3.49316C12.1417 3.46527 11.7011 3.46484 11.0605 3.46484H5.92967Z" fill="currentColor"/>',
    '</svg>',
  ].join("");
  alwaysOnTop.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    state.api.ipc.invoke?.(TERMINAL_ALWAYS_ON_TOP_CHANNEL, {}).then((result) => {
      alwaysOnTop.setAttribute("aria-pressed", result?.alwaysOnTop ? "true" : "false");
    }).catch((error) => {
      state.api.log.warn("[better-terminal] failed to toggle always on top", String(error));
    });
  });

  chrome.append(title, alwaysOnTop);
  document.body.appendChild(chrome);
  return chrome;
}

function visibleTerminalWindowRoot(root = document) {
  const candidates = root.querySelectorAll?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm") || [];
  for (const terminal of candidates) {
    if (!(terminal instanceof HTMLElement)) continue;
    if (!terminal.matches(".xterm") && !terminal.querySelector(".xterm")) continue;
    const rect = terminal.getBoundingClientRect();
    if (rect.width < 160 || rect.height < 100 || rect.bottom <= 0 || rect.right <= 0) continue;
    const style = getComputedStyle(terminal);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") continue;
    return terminal.closest?.("[data-codex-terminal], [id^='terminal-panel-']") || terminal;
  }
  return null;
}

function setActiveTabTitle(state) {
  const root = state.activeRoot || findTerminalRoot();
  const tab = state.activeTab || (root ? activeTerminalTab(root) : null);
  if (!tab) return;
  const keys = terminalTabKeys(tab, 0);
  const current = keys.map((key) => state.titleAliases[key]).find(Boolean) || compactText(tab.textContent || "");
  for (const [aliasKey, aliasTitle] of Object.entries(state.titleAliases)) {
    if (aliasTitle === current && !keys.includes(aliasKey)) keys.push(aliasKey);
  }
  openRenameDialog(state, { keys, current });
}

function openRenameDialog(state, { keys, current }) {
  closeRenameDialog(state);

  const backdrop = el("div");
  backdrop.setAttribute(RENAME_DIALOG_ATTR, "backdrop");
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) closeRenameDialog(state);
  });

  const dialog = el("div");
  dialog.setAttribute(RENAME_DIALOG_ATTR, "dialog");
  dialog.className = "codex-dialog left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 outline-none fixed bg-token-dropdown-background text-token-foreground ring-token-border max-w-[92vw] rounded-3xl ring-[0.5px] ring-token-border shadow-2xl";
  dialog.style.width = "min(420px, 92vw)";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "codexpp-terminal-rename-title");

  const form = el("form");
  form.setAttribute(RENAME_DIALOG_ATTR, "form");
  form.className = "flex flex-col gap-0 px-5 py-5 text-base leading-normal tracking-normal";

  const header = el("div", "flex w-full flex-col pt-3 first:pt-0");
  const headerContent = el("div", "flex flex-col items-start gap-3");
  const labelBlock = el("div", "flex min-w-0 flex-1 flex-col gap-1 self-stretch");
  const heading = el("div", "heading-dialog min-w-0 font-semibold");
  heading.id = "codexpp-terminal-rename-title";
  heading.setAttribute(RENAME_DIALOG_ATTR, "heading");
  heading.textContent = "Rename terminal tab";
  labelBlock.append(heading);
  headerContent.append(labelBlock);
  header.append(headerContent);

  const inputSection = el("div", "flex w-full flex-col pt-3 first:pt-0");
  const input = el("input");
  input.setAttribute(RENAME_DIALOG_ATTR, "input");
  input.className = "rounded-xl border border-token-border px-3 py-2 text-base text-token-input-foreground shadow-sm outline-none";
  input.setAttribute("aria-label", "Terminal tab title");
  input.setAttribute("placeholder", "Terminal tab title");
  input.value = current;
  inputSection.append(input);

  const footerSection = el("div", "flex w-full flex-col pt-3 first:pt-0");
  const footer = el("div", "flex w-full items-center justify-end gap-3");
  footer.setAttribute(RENAME_DIALOG_ATTR, "footer");
  const cancel = el("button");
  cancel.type = "button";
  cancel.setAttribute(RENAME_DIALOG_ATTR, "button");
  cancel.className = "border-token-border user-select-none no-drag cursor-interaction flex items-center gap-1 border whitespace-nowrap focus:outline-none disabled:cursor-not-allowed disabled:opacity-40 rounded-lg border-token-border text-token-text-secondary enabled:hover:bg-token-button-secondary-hover-background px-4 py-1.5 text-sm";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => closeRenameDialog(state));
  const save = el("button");
  save.type = "submit";
  save.setAttribute(RENAME_DIALOG_ATTR, "submit");
  save.className = "border-token-border user-select-none no-drag cursor-interaction flex items-center gap-1 border whitespace-nowrap focus:outline-none disabled:cursor-not-allowed disabled:opacity-40 rounded-lg bg-token-foreground enabled:hover:opacity-90 text-token-bg-primary px-4 py-1.5 text-sm";
  save.style.backgroundColor = "var(--color-token-foreground, CanvasText)";
  save.style.color = "var(--color-token-bg-primary, Canvas)";
  save.textContent = "Save";
  footer.append(cancel, save);
  footerSection.append(footer);

  const close = el("button");
  close.type = "button";
  close.setAttribute(RENAME_DIALOG_ATTR, "close");
  close.setAttribute("aria-label", "Close");
  close.className = "no-drag absolute top-4 right-4 cursor-interaction rounded p-1 leading-none text-token-foreground/80 hover:bg-token-toolbar-hover-background focus:ring-1 focus:ring-token-focus-border focus:outline-none";
  close.innerHTML = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M5.636 5.636a.9.9 0 0 1 1.273 0L10 8.727l3.091-3.091a.9.9 0 1 1 1.273 1.273L11.273 10l3.091 3.091a.9.9 0 0 1-1.273 1.273L10 11.273l-3.091 3.091a.9.9 0 1 1-1.273-1.273L8.727 10 5.636 6.909a.9.9 0 0 1 0-1.273Z" fill="currentColor"/></svg>';
  close.addEventListener("click", () => closeRenameDialog(state));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveTerminalTabTitle(state, keys, input.value);
  });

  form.append(header, inputSection, footerSection);
  dialog.append(form, close);
  backdrop.append(dialog);
  document.body.appendChild(backdrop);
  state.renameDialog = backdrop;

  requestAnimationFrame(() => {
    input.focus();
    input.select();
  });
}

function saveTerminalTabTitle(state, keys, next) {
  const [primaryKey] = keys;
  const title = next.trim();
  keys.forEach((key) => {
    delete state.titleAliases[key];
  });
  if (title && primaryKey) state.titleAliases[primaryKey] = title;
  state.api.storage.set("title-aliases", state.titleAliases);
  closeRenameDialog(state);
  apply(state);
}

function closeRenameDialog(state) {
  state.renameDialog?.remove();
  state.renameDialog = null;
}

function applyTabTitles(state, root) {
  const tabs = findTerminalTabs(root);
  tabs.forEach((tab, index) => {
    const key = terminalTabKey(tab, index);
    tab.dataset[camel(TAB_KEY_ATTR)] = key;
    const keys = terminalTabKeys(tab, index);
    const alias = keys.map((key) => state.titleAliases[key]).find(Boolean);
    const visibleTitle = compactText(tab.textContent || "");
    if (!alias && key?.startsWith("session:") && visibleTitle && !tab.hasAttribute(TITLE_ATTR) && !state.defaultTitles[key]) {
      state.defaultTitles[key] = visibleTitle;
      state.api.storage.set("default-titles", state.defaultTitles);
    }
    const stableTitle = alias || keys.map((key) => state.defaultTitles[key]).find(Boolean);
    if (stableTitle && stableTitle !== visibleTitle) {
      if (!tab.dataset[camel(ORIGINAL_TEXT_ATTR)]) {
        tab.dataset[camel(ORIGINAL_TEXT_ATTR)] = visibleTitle;
      }
      setElementLabel(tab, stableTitle);
      tab.setAttribute(TITLE_ATTR, stableTitle);
      return;
    }
    if (!alias) {
      if (tab.hasAttribute(TITLE_ATTR)) {
        const original = tab.dataset[camel(ORIGINAL_TEXT_ATTR)];
        const fallback = keys.map((key) => state.defaultTitles[key]).find(Boolean);
        if (fallback) setElementLabel(tab, fallback);
        else if (original) setElementLabel(tab, original);
        tab.removeAttribute(TITLE_ATTR);
        delete tab.dataset[camel(ORIGINAL_TEXT_ATTR)];
      }
      return;
    }
    if (!tab.dataset[camel(ORIGINAL_TEXT_ATTR)]) {
      tab.dataset[camel(ORIGINAL_TEXT_ATTR)] = compactText(tab.textContent || "");
    }
    setElementLabel(tab, alias);
    tab.setAttribute(TITLE_ATTR, alias);
  });
}

function applySplitState(state, root) {
  const splitPair = currentSplitPairForRoot(state, root);
  document.querySelectorAll(`[${SPLIT_ACTIVE_ATTR}]`).forEach((node) => {
    if (node !== root) node.removeAttribute(SPLIT_ACTIVE_ATTR);
  });
  clearSplitTabPresentation(root);

  const activeSession = activeTerminalSessionInRoot(state, root);
  const isActiveSplit = Boolean(
    splitPair &&
      activeSession?.sessionId &&
      (
        activeSession.sessionId === splitPair.left ||
        activeSession.sessionId === splitPair.right ||
        activeSession.sessionId === splitPair.anchor ||
        splitPair.sessions.includes(activeSession.sessionId)
      ),
  );
  root.toggleAttribute(SPLIT_ACTIVE_ATTR, isActiveSplit);
  if (isActiveSplit) applySplitRatio(root, splitPair.ratio);
  else root.style.removeProperty("--codexpp-terminal-split-left");

  if (!splitPair) return;

  const markersBySession = new Map();
  const tabs = findTerminalTabs(root);
  tabs.forEach((tab) => {
    const marker = terminalTabMarker(tab);
    if (!(marker instanceof HTMLElement) || markersBySession.size > 64) return;
    const session = terminalSessionFromNode(state, marker) || terminalSessionFromNode(state, tab);
    if (session?.sessionId && !markersBySession.has(session.sessionId)) {
      markersBySession.set(session.sessionId, marker);
    }
  });

  const markers = splitPair.sessions
    .map((sessionId) => markersBySession.get(sessionId))
    .filter((marker) => marker instanceof HTMLElement);
  const leftMarker = markersBySession.get(splitPair.left);
  const anchorMarker = splitPair.anchor ? markersBySession.get(splitPair.anchor) : null;
  const primaryMarker =
    anchorMarker instanceof HTMLElement
      ? anchorMarker
      : leftMarker instanceof HTMLElement
        ? leftMarker
        : markers[0] instanceof HTMLElement
          ? markers[0]
        : null;
  if (!(primaryMarker instanceof HTMLElement)) return;
  applyCombinedSplitTab(root, splitPair, primaryMarker, markers);
}

function activeTerminalSessionInRoot(state, root) {
  const tabSession = terminalSessionFromNode(state, activeTerminalTab(root));
  if (tabSession?.sessionId) return tabSession;
  return terminalSessionFromNode(
    state,
    root.querySelector("[data-codex-terminal], [id^='terminal-panel-'], .xterm"),
  );
}

function clearSplitTabPresentation(root = document) {
  root.querySelectorAll(`[${SPLIT_TAB_ATTR}]`).forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    const original = node.dataset[camel(SPLIT_ORIGINAL_TEXT_ATTR)];
    if (original && node.getAttribute(SPLIT_TAB_ATTR) === "primary") {
      setElementLabel(terminalTabActivationTarget(node), original);
    }
    node.removeAttribute(SPLIT_TAB_ATTR);
    node.removeAttribute("aria-hidden");
    delete node.dataset[camel(SPLIT_ORIGINAL_TEXT_ATTR)];
  });
}

function applyCombinedSplitTab(root, splitPair, primaryMarker, markers) {
  const markerBySession = new Map();
  for (const marker of markers) {
    const session = terminalSessionFromNode(globalThis.__codexppBetterTerminalState, marker);
    if (session?.sessionId) markerBySession.set(session.sessionId, marker);
  }
  const titles = splitPair.sessions.map((sessionId) => {
    const marker = markerBySession.get(sessionId);
    return marker instanceof HTMLElement ? splitTabOriginalTitle(marker) : "Split";
  });
  const combinedTitle = `${splitPair.sessions.length} tabs`;
  const fullTitle = titles.filter(Boolean).join(" / ") || combinedTitle;
  terminalTabElementsForSession(root, terminalSessionFromNode(globalThis.__codexppBetterTerminalState, primaryMarker)?.sessionId || splitPair.anchor || splitPair.left).forEach((node) => {
    node.dataset[camel(SPLIT_ORIGINAL_TEXT_ATTR)] = splitTabOriginalTitle(primaryMarker);
    node.setAttribute(SPLIT_TAB_ATTR, "primary");
    node.setAttribute("title", fullTitle);
    terminalTabActivationTarget(node)?.setAttribute("title", fullTitle);
    node.removeAttribute("aria-hidden");
  });
  for (const sessionId of splitPair.sessions) {
    if (sessionId === (terminalSessionFromNode(globalThis.__codexppBetterTerminalState, primaryMarker)?.sessionId || splitPair.anchor || splitPair.left)) continue;
    const marker = markerBySession.get(sessionId);
    terminalTabElementsForSession(root, sessionId).forEach((node) => {
      node.dataset[camel(SPLIT_ORIGINAL_TEXT_ATTR)] = marker instanceof HTMLElement ? splitTabOriginalTitle(marker) : "Split";
      node.setAttribute(SPLIT_TAB_ATTR, "secondary");
      node.setAttribute("aria-hidden", "true");
    });
  }
  setElementLabel(terminalTabActivationTarget(primaryMarker), combinedTitle);
  primaryMarker.setAttribute("title", fullTitle);
}

function applyRunningTerminalIcons(state, root) {
  const runningSessions = state.runningSessionIds instanceof Set ? state.runningSessionIds : new Set();
  state.runningSessionIds = runningSessions;
  const finishedSessions = state.finishedSessionIds instanceof Set ? state.finishedSessionIds : new Set();
  state.finishedSessionIds = finishedSessions;
  const frozenSessions = frozenTerminalSessionIds(state);
  const previouslyRunning = new Set(runningSessions);
  const knownSessions = new Set();

  findTerminalTabs(root).forEach((tab) => {
    const session = terminalSessionFromNode(state, tab);
    if (session?.sessionId) knownSessions.add(session.sessionId);
  });

  for (const snapshot of readPageTerminalManagerSnapshots(state, { includeBuffer: false })) {
    if (!snapshot.sessionId) continue;
    knownSessions.add(snapshot.sessionId);
    if (terminalSnapshotAppearsBusy(snapshot)) {
      runningSessions.add(snapshot.sessionId);
    } else {
      runningSessions.delete(snapshot.sessionId);
    }
  }

  root.querySelectorAll("[data-codex-terminal], [id^='terminal-panel-']").forEach((node) => {
    const session = terminalSessionFromNode(state, node);
    if (!session?.sessionId) return;
    knownSessions.add(session.sessionId);
    if (terminalPanelAppearsBusy(node)) {
      runningSessions.add(session.sessionId);
    } else {
      runningSessions.delete(session.sessionId);
    }
  });
  runningSessions.forEach((sessionId) => {
    if (!knownSessions.has(sessionId)) runningSessions.delete(sessionId);
  });
  finishedSessions.forEach((sessionId) => {
    if (!knownSessions.has(sessionId)) finishedSessions.delete(sessionId);
  });

  runningSessions.forEach((sessionId) => finishedSessions.delete(sessionId));
  const focusedSession = focusedTerminalSession(root, state)?.sessionId || null;
  if (focusedSession) finishedSessions.delete(focusedSession);
  previouslyRunning.forEach((sessionId) => {
    if (
      knownSessions.has(sessionId) &&
      !runningSessions.has(sessionId) &&
      sessionId !== focusedSession
    ) {
      finishedSessions.add(sessionId);
    }
  });

  root.querySelectorAll(`[${RUNNING_TERMINAL_ATTR}]`).forEach((node) => {
    if (node instanceof HTMLElement) node.removeAttribute(RUNNING_TERMINAL_ATTR);
  });
  root.querySelectorAll(`[${FINISHED_TERMINAL_ATTR}]`).forEach((node) => {
    if (node instanceof HTMLElement) node.removeAttribute(FINISHED_TERMINAL_ATTR);
  });
  root.querySelectorAll(`[${FROZEN_TERMINAL_ATTR}]`).forEach((node) => {
    if (node instanceof HTMLElement) node.removeAttribute(FROZEN_TERMINAL_ATTR);
  });
  root.querySelectorAll(`[${RUNNING_TERMINAL_BADGE_ATTR}="true"]`).forEach((node) => {
    if (node instanceof HTMLElement) node.removeAttribute(RUNNING_TERMINAL_BADGE_ATTR);
  });
  root.querySelectorAll(`svg[${FILLED_TERMINAL_ICON_MARK}="true"]`).forEach((svg) => {
    const tab = svg.closest("[data-tab-id^='terminal:']");
    const session = terminalSessionFromNode(state, tab);
    if (
      !session?.sessionId ||
      (
        !runningSessions.has(session.sessionId) &&
        !finishedSessions.has(session.sessionId) &&
        !frozenSessions.has(session.sessionId)
      )
    ) {
      restoreTerminalIcon(svg);
    }
  });

  const splitPair = currentSplitPairForRoot(state, root);
  const splitIsRunning = splitPair?.sessions?.some((sessionId) => runningSessions.has(sessionId));
  const splitIsFinished = !splitIsRunning && splitPair?.sessions?.some((sessionId) => finishedSessions.has(sessionId));
  const splitIsFrozen = splitPair?.sessions?.some((sessionId) => frozenSessions.has(sessionId));
  if (splitIsRunning) {
    root.querySelectorAll(`[data-tab-id^="terminal:"][${SPLIT_TAB_ATTR}="primary"]`).forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      node.setAttribute(RUNNING_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
    });
  } else if (splitIsFinished) {
    root.querySelectorAll(`[data-tab-id^="terminal:"][${SPLIT_TAB_ATTR}="primary"]`).forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      node.setAttribute(FINISHED_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
      applyRunningTerminalBadge(node);
    });
  }
  if (splitIsFrozen) {
    root.querySelectorAll(`[data-tab-id^="terminal:"][${SPLIT_TAB_ATTR}="primary"]`).forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      node.setAttribute(FROZEN_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
    });
  }
  for (const sessionId of runningSessions) {
    terminalTabElementsForSession(root, sessionId).forEach((node) => {
      node.setAttribute(RUNNING_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
    });
  }
  for (const sessionId of finishedSessions) {
    terminalTabElementsForSession(root, sessionId).forEach((node) => {
      node.setAttribute(FINISHED_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
      applyRunningTerminalBadge(node);
    });
  }
  for (const sessionId of frozenSessions) {
    terminalTabElementsForSession(root, sessionId).forEach((node) => {
      node.setAttribute(FROZEN_TERMINAL_ATTR, "true");
      applyFilledTerminalIcon(node);
    });
  }
}

function frozenTerminalSessionIds(state) {
  const frozen = Array.isArray(state.memoryWatchdogStatus?.frozen) ? state.memoryWatchdogStatus.frozen : [];
  return new Set(frozen.map((entry) => String(entry?.sessionId || "")).filter(Boolean));
}

function terminalPanelAppearsBusy(panel) {
  if (!(panel instanceof Element)) return false;
  const rows = panel.querySelector(".xterm-rows") || panel.querySelector(".xterm-screen");
  return terminalTextAppearsBusy(rows?.textContent || "");
}

function terminalSnapshotAppearsBusy(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return false;
  const bufferState = terminalTextBusyState(snapshot.buffer || "");
  if (bufferState != null) return bufferState;
  const title = compactText(snapshot.title || "");
  const cwd = compactText(snapshot.cwd || "");
  if (title && title !== cwd && title !== compactBasename(cwd)) return true;
  return false;
}

function terminalTextAppearsBusy(value) {
  return terminalTextBusyState(value) === true;
}

function terminalTextBusyState(value) {
  const text = normalizeTerminalText(value);
  const lines = text.split(/\n/).map((line) => line.trim()).filter(Boolean);
  const last = lines.at(-1) || "";
  if (!last) return null;
  if (/%\s*$/.test(last) || /\$\s*$/.test(last) || />\s*$/.test(last)) return false;
  if (/^(bash|zsh|sh|fish|pwsh|powershell)(-\d+\.\d+)?[$%>]\s*$/.test(last)) return false;
  return true;
}

function normalizeTerminalText(value) {
  return stripTerminalControlSequences(`${value || ""}`)
    .replace(/\u00a0/g, " ")
    .replace(/[^\S\n\r]+$/gm, "")
    .replace(/.\x08/g, "")
    .replace(/\r+/g, "\n");
}

function stripTerminalControlSequences(value) {
  return `${value || ""}`
    .replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\)/g, "")
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "");
}

function compactBasename(value) {
  const text = compactText(value);
  if (!text) return "";
  return text.split(/[\\/]/).filter(Boolean).at(-1) || text;
}

function readPageTerminalManagerSnapshots(state, options = {}) {
  const includeBuffer = Boolean(options.includeBuffer);
  const cacheKey = includeBuffer ? "with-buffer" : "metadata-only";
  const now = Date.now();
  if (
    state?.terminalManagerSnapshotCache &&
    state.terminalManagerSnapshotCache.cacheKey === cacheKey &&
    now - Number(state.terminalManagerSnapshotCache.readAt || 0) < 1000 &&
    Array.isArray(state.terminalManagerSnapshotCache.snapshots)
  ) {
    return state.terminalManagerSnapshotCache.snapshots;
  }
  const requestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const attr = camel(TERMINAL_MANAGER_SNAPSHOT_ATTR);
  const bridged = parseTerminalManagerSnapshotPayload(document.documentElement.dataset[attr]);
  if (bridged) {
    if (state) state.terminalManagerSnapshotCache = { cacheKey, readAt: now, snapshots: bridged };
    return bridged;
  }
  const script = document.createElement("script");
  const shouldIncludeBuffer = JSON.stringify(includeBuffer);
  script.textContent = `(() => {
    const manager = globalThis.__codexppTerminalManager;
    const includeBuffer = ${shouldIncludeBuffer};
    const snapshots = [];
    try {
      if (manager?.sessionSnapshots instanceof Map) {
        for (const [sessionId, snapshot] of manager.sessionSnapshots.entries()) {
          snapshots.push({
            sessionId,
            cwd: snapshot?.cwd || "",
            shell: snapshot?.shell || "",
            title: snapshot?.title || "",
            rawShellTitle: snapshot?.rawShellTitle || "",
            buffer: includeBuffer ? (snapshot?.buffer || "") : "",
            truncated: Boolean(snapshot?.truncated),
            attached: Boolean(manager.attachedSessionIds?.has?.(sessionId)),
            pending: Boolean(manager.pendingSessionActions?.has?.(sessionId)),
          });
        }
      }
      document.documentElement.dataset.${attr} = JSON.stringify({ requestId: ${JSON.stringify(requestId)}, snapshots });
    } catch (error) {
      document.documentElement.dataset.${attr} = JSON.stringify({ requestId: ${JSON.stringify(requestId)}, snapshots: [], error: String(error) });
    }
  })();`;
  try {
    document.documentElement.appendChild(script);
    script.remove();
    const raw = document.documentElement.dataset[attr];
    delete document.documentElement.dataset[attr];
    const payload = JSON.parse(raw || "null");
    if (payload?.requestId !== requestId || !Array.isArray(payload.snapshots)) return [];
    if (state) state.terminalManagerSnapshotCache = { cacheKey, readAt: now, snapshots: payload.snapshots };
    return payload.snapshots;
  } catch (error) {
    state.api.log.debug("[better-terminal] terminal manager snapshot probe failed", String(error));
    return [];
  }
}

function parseTerminalManagerSnapshotPayload(raw) {
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw);
    if (!Array.isArray(payload?.snapshots)) return null;
    return payload.snapshots;
  } catch {
    return null;
  }
}

function applyFilledTerminalIcon(node) {
  if (!(node instanceof HTMLElement)) return;
  const target = terminalTabActivationTarget(node);
  const svg = target?.querySelector("span[aria-hidden='true'] svg[viewBox='0 0 20 20']") ||
    target?.querySelector("svg[viewBox='0 0 20 20']");
  if (!(svg instanceof SVGElement) || svg.getAttribute(FILLED_TERMINAL_ICON_MARK) === "true") return;
  svg.setAttribute(TERMINAL_ICON_ORIGINAL_ATTR, svg.innerHTML);
  svg.setAttribute(FILLED_TERMINAL_ICON_MARK, "true");
  svg.setAttribute("fill", "none");
  svg.innerHTML = FILLED_TERMINAL_ICON_INNER;
}

function applyRunningTerminalBadge(node) {
  if (!(node instanceof HTMLElement)) return;
  const target = terminalTabActivationTarget(node);
  const wrapper = Array.from(target?.querySelectorAll("span[aria-hidden='true']") || [])
    .find((candidate) => candidate.querySelector?.("svg[viewBox='0 0 20 20']"));
  if (wrapper instanceof HTMLElement) {
    wrapper.setAttribute(RUNNING_TERMINAL_BADGE_ATTR, "true");
    return;
  }
  const svg = target?.querySelector("svg[viewBox='0 0 20 20']");
  const parent = svg?.parentElement;
  if (parent instanceof HTMLElement) parent.setAttribute(RUNNING_TERMINAL_BADGE_ATTR, "true");
}

function restoreTerminalIcons(root) {
  root.querySelectorAll(`svg[${FILLED_TERMINAL_ICON_MARK}="true"]`).forEach((svg) => {
    restoreTerminalIcon(svg);
  });
  root.querySelectorAll(`[${RUNNING_TERMINAL_BADGE_ATTR}="true"]`).forEach((node) => {
    if (node instanceof HTMLElement) node.removeAttribute(RUNNING_TERMINAL_BADGE_ATTR);
  });
}

function restoreTerminalIcon(svg) {
  if (!(svg instanceof SVGElement)) return;
  const original = svg.getAttribute(TERMINAL_ICON_ORIGINAL_ATTR);
  if (original) svg.innerHTML = original;
  svg.removeAttribute(FILLED_TERMINAL_ICON_MARK);
  svg.removeAttribute(TERMINAL_ICON_ORIGINAL_ATTR);
  svg.setAttribute("fill", "none");
}

function terminalTabElementsForSession(root, sessionId) {
  return Array.from(root.querySelectorAll(`[data-tab-id="terminal:${sessionId}"]`))
    .filter((node) => node instanceof HTMLElement);
}

function splitTabOriginalTitle(marker) {
  return compactText(
    marker.dataset[camel(SPLIT_ORIGINAL_TEXT_ATTR)] ||
      marker.dataset[camel(ORIGINAL_TEXT_ATTR)] ||
      marker.textContent ||
      marker.getAttribute("aria-label") ||
      marker.getAttribute("title") ||
      "Terminal",
  );
}

function terminalTabMarker(node) {
  if (!(node instanceof HTMLElement)) return node;
  return node.closest("[data-tab-id^='terminal:']") || node;
}

function terminalTabVisualNode(node) {
  if (!(node instanceof HTMLElement)) return node;
  return (
    node.closest("[data-tab-id^='terminal:'][role='button']") ||
    node.closest("[data-tab-id^='terminal:'] button[role='tab']") ||
    node.closest("[data-tab-id^='terminal:'] button") ||
    terminalTabMarker(node)
  );
}

function restoreTabTitles() {
  clearSplitTabPresentation(document);
  document.querySelectorAll(`[${TITLE_ATTR}]`).forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    const original = node.dataset[camel(ORIGINAL_TEXT_ATTR)];
    if (original) setElementLabel(node, original);
    node.removeAttribute(TITLE_ATTR);
    delete node.dataset[camel(ORIGINAL_TEXT_ATTR)];
    delete node.dataset[camel(TAB_KEY_ATTR)];
  });
}

function findTerminalRoot() {
  const byXterm = document.querySelector(".xterm, .xterm-screen, .xterm-viewport");
  const seed =
    byXterm ||
    Array.from(document.querySelectorAll("button, [role='button'], [title], [aria-label]"))
      .find((el) => /\bterminal\b/i.test(`${el.textContent || ""} ${el.getAttribute("title") || ""} ${el.getAttribute("aria-label") || ""}`));
  if (!seed) return null;

  let node = seed instanceof HTMLElement ? seed : seed.parentElement;
  let best = null;
  const viewport = window.innerHeight || 800;
  while (node && node !== document.body) {
    const rect = node.getBoundingClientRect();
    const text = compactText(node.textContent || "");
    const hasTerminal =
      Boolean(node.querySelector?.(".xterm, .xterm-screen, .xterm-viewport")) ||
      /\b(new terminal|toggle terminal|terminal)\b/i.test(text);
    if (hasTerminal && rect.width > 280 && rect.height > 100 && rect.top > viewport * 0.15) {
      best = node;
    }
    node = node.parentElement;
  }
  return best;
}

function findConversationId(state) {
  const sidebarId = conversationIdFromSidebar();
  if (sidebarId) return sidebarId;

  const candidates = [
    state.activeRoot,
    state.activeTab,
    document.querySelector("[data-codex-terminal]"),
    document.querySelector(".xterm"),
  ].filter(Boolean);

  for (const node of candidates) {
    const id = findConversationIdFromNode(state, node);
    if (id) return id;
  }
  return null;
}

function conversationIdFromSidebar() {
  const row = document.querySelector(
    "[data-app-action-sidebar-thread-active='true'][data-app-action-sidebar-thread-id], [data-app-action-sidebar-thread-row][aria-current='page'][data-app-action-sidebar-thread-id]",
  );
  const value = row?.getAttribute?.("data-app-action-sidebar-thread-id") || "";
  const normalized = value.replace(/^local:/, "");
  return normalized && !normalized.startsWith("home:") ? normalized : null;
}

function findConversationIdFromNode(state, node) {
  if (!node || node.nodeType !== 1) return null;
  let fiber = state.api.react?.getFiber?.(node) || reactFiberFromNode(node);
  const seen = new Set();
  while (fiber && !seen.has(fiber)) {
    seen.add(fiber);
    const id = conversationIdFromProps(fiber.memoizedProps) || conversationIdFromProps(fiber.pendingProps);
    if (id) return id;
    fiber = fiber.return;
  }
  return null;
}

function reactFiberFromNode(node) {
  for (const key of Object.keys(node)) {
    if (key.startsWith("__reactFiber") || key.startsWith("__reactInternalInstance")) return node[key];
  }
  return null;
}

function conversationIdFromProps(props) {
  if (!props || typeof props !== "object") return null;
  const value = props.conversationId;
  return typeof value === "string" && value.length > 0 && !value.startsWith("home:") ? value : null;
}

function activeTerminalSession(state) {
  const root = state.activeRoot || findTerminalRoot();
  if (state.activeSessionId) {
    const overrideStillExists =
      document.getElementById(`terminal-panel-${state.activeSessionId}`) ||
      terminalTabElementsForSession(root || document, state.activeSessionId)[0];
    if (overrideStillExists) {
      return {
        sessionId: state.activeSessionId,
        conversationId: state.activeConversationId || terminalConversationId(root, state),
      };
    }
    clearActiveSessionOverride(state);
  }
  const tab = state.activeTab || (root ? activeTerminalTab(root) : null);
  const fromTab = terminalSessionFromNode(state, tab);
  if (fromTab?.sessionId) {
    return {
      sessionId: fromTab.sessionId,
      conversationId: fromTab.conversationId || terminalConversationId(root, state),
    };
  }

  const activePanel = root?.querySelector("[data-codex-terminal], [id^='terminal-panel-'], .xterm");
  const fromPanel = terminalSessionFromNode(state, activePanel);
  if (fromPanel?.sessionId) return fromPanel;
  return null;
}

function clearActiveSessionOverride(state) {
  state.activeSessionId = null;
  state.activeConversationId = null;
}

function findTerminalSessions(root) {
  const sessions = [];
  const seen = new Set();
  const candidates = [
    ...(root ? Array.from(root.querySelectorAll("[data-codex-terminal], [id^='terminal-panel-'], [role='tab'], button")) : []),
    ...Array.from(document.querySelectorAll("[data-codex-terminal], [id^='terminal-panel-'], [data-tab-id^='terminal:']")),
  ];
  for (const node of candidates) {
    const session = terminalSessionFromNode(globalThis.__codexppBetterTerminalState, node);
    if (!session?.sessionId || seen.has(session.sessionId)) continue;
    seen.add(session.sessionId);
    sessions.push(session);
  }
  return sessions;
}

function terminalConversationId(root, state) {
  const panel = root?.querySelector("[data-codex-terminal], [id^='terminal-panel-'], .xterm");
  return terminalSessionFromNode(state, panel)?.conversationId || findTerminalSessions(root)[0]?.conversationId || null;
}

function terminalSessionFromNode(state, node) {
  if (!node || node.nodeType !== 1) return null;
  const fromDomId = terminalSessionIdFromString(
    node.id ||
      node.getAttribute?.("id") ||
      node.getAttribute?.("data-tab-id") ||
      node.closest?.("[data-tab-id]")?.getAttribute("data-tab-id") ||
      node.dataset?.tabId ||
      "",
  );
  let fiber = state?.api?.react?.getFiber?.(node) || reactFiberFromNode(node);
  const seen = new Set();
  let sessionId = fromDomId;
  let conversationId = null;
  while (fiber && !seen.has(fiber)) {
    seen.add(fiber);
    const fromMemo = terminalSessionFromProps(fiber.memoizedProps);
    const fromPending = terminalSessionFromProps(fiber.pendingProps);
    sessionId ||= fromMemo.sessionId || fromPending.sessionId;
    conversationId ||= fromMemo.conversationId || fromPending.conversationId;
    if (sessionId && conversationId) break;
    fiber = fiber.return;
  }
  return sessionId ? { sessionId, conversationId } : null;
}

function terminalSessionFromProps(props) {
  if (!props || typeof props !== "object") return {};
  return {
    sessionId:
      typeof props.sessionId === "string"
        ? props.sessionId
        : terminalSessionIdFromString(typeof props.id === "string" ? props.id : ""),
    conversationId:
      typeof props.conversationId === "string" && props.conversationId.length > 0
        ? props.conversationId
        : null,
  };
}

function terminalSessionIdFromString(value) {
  const match = /^terminal(?::|-panel-)(.+)$/.exec(value);
  return match?.[1] || null;
}

function makeTerminalSessionId() {
  if (typeof crypto?.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function waitForNewTerminalSession(state, before, conversationId) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    const tick = () => {
      const root = findTerminalRoot();
      const session = findTerminalSessions(root)
        .find((candidate) =>
          !before.has(candidate.sessionId) &&
          (!conversationId || !candidate.conversationId || candidate.conversationId === conversationId),
        );
      if (session) {
        resolve(session);
        return;
      }
      if (Date.now() - startedAt > 2500) {
        resolve(null);
        return;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  });
}

function waitForTerminalSessionReady(sessionId, timeoutMs) {
  return new Promise((resolve) => {
    const startedAt = Date.now();
    const tick = () => {
      const panel = document.getElementById(`terminal-panel-${sessionId}`);
      const xterm = panel?.querySelector(".xterm");
      const rows = panel?.querySelector(".xterm-rows");
      const hasText = Boolean(compactText(rows?.textContent || ""));
      if (xterm && (hasText || Date.now() - startedAt > Math.min(timeoutMs, 1800))) {
        resolve(Boolean(hasText));
        return;
      }
      if (Date.now() - startedAt > timeoutMs) {
        resolve(false);
        return;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  });
}

function findConversationIdViaPageWorld(state) {
  return new Promise((resolve) => {
    const requestId = `bt-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const dataAttr = "codexppBetterTerminalConversationId";
    const requestAttr = "codexppBetterTerminalConversationRequest";
    let settled = false;
    let timeout = null;
    let poll = null;

    const cleanup = (value) => {
      if (settled) return;
      settled = true;
      if (timeout) window.clearTimeout(timeout);
      if (poll) window.clearInterval(poll);
      if (document.documentElement.dataset[requestAttr] === requestId) {
        delete document.documentElement.dataset[requestAttr];
        delete document.documentElement.dataset[dataAttr];
      }
      resolve(value || null);
    };

    document.documentElement.dataset[requestAttr] = requestId;
    poll = window.setInterval(() => {
      if (document.documentElement.dataset[requestAttr] !== requestId) return;
      const value = document.documentElement.dataset[dataAttr];
      if (value) cleanup(value);
    }, 20);
    timeout = window.setTimeout(() => cleanup(null), 350);

    const script = document.createElement("script");
    script.textContent = `(() => {
      const requestId = ${JSON.stringify(requestId)};
      const dataAttr = ${JSON.stringify(dataAttr)};
      const requestAttr = ${JSON.stringify(requestAttr)};
      const isConversationId = (value) =>
        typeof value === "string" && value.length > 0 && !value.startsWith("home:");
      const fromProps = (props) => {
        if (!props || typeof props !== "object") return null;
        return isConversationId(props.conversationId) ? props.conversationId : null;
      };
      const fiberForNode = (node) => {
        if (!node) return null;
        for (const key of Object.keys(node)) {
          if (key.startsWith("__reactFiber") || key.startsWith("__reactInternalInstance")) return node[key];
        }
        return null;
      };
      const fromFiber = (fiber) => {
        const seen = new Set();
        let current = fiber;
        for (let depth = 0; current && depth < 120 && !seen.has(current); depth += 1) {
          seen.add(current);
          const id = fromProps(current.memoizedProps) || fromProps(current.pendingProps);
          if (id) return id;
          current = current.return;
        }
        return null;
      };
      const visibleScore = (node) => {
        if (!node?.getBoundingClientRect) return 0;
        const rect = node.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0 || rect.bottom <= 0 || rect.right <= 0) return 0;
        const style = getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden") return 0;
        return rect.width * rect.height * (rect.left > 220 ? 2 : 1);
      };
      const seeds = [
        document.querySelector("[data-codex-terminal]"),
        document.querySelector(".xterm"),
        document.querySelector("[id^='terminal-panel-']"),
        document.querySelector("[data-tab-id^='terminal:']"),
      ].filter(Boolean);
      let conversationId = null;
      for (const seed of seeds) {
        let node = seed;
        for (let depth = 0; node && depth < 12 && !conversationId; depth += 1, node = node.parentElement) {
          conversationId = fromFiber(fiberForNode(node));
        }
        if (conversationId) break;
      }
      if (!conversationId) {
        const visibleSeeds = Array.from(document.querySelectorAll("main, [role='main'], textarea, [contenteditable='true'], article, section, div, button"))
          .sort((a, b) => visibleScore(b) - visibleScore(a))
          .slice(0, 250);
        for (const seed of visibleSeeds) {
          conversationId = fromFiber(fiberForNode(seed));
          if (conversationId) break;
        }
      }
      if (document.documentElement.dataset[requestAttr] === requestId && conversationId) {
        document.documentElement.dataset[dataAttr] = conversationId;
      }
    })();`;

    try {
      document.documentElement.appendChild(script);
      script.remove();
    } catch (error) {
      state.api.log.warn("[better-terminal] page-world conversation id probe failed", String(error));
      cleanup(null);
    }
  });
}

function findTerminalTabFromEvent(root, event) {
  const path = typeof event.composedPath === "function" ? event.composedPath() : [];
  for (const node of path) {
    if (!(node instanceof HTMLElement) || !root.contains(node)) continue;
    if (isTerminalTabCloseControl(node)) return null;
    if (isTerminalTabCandidate(node)) return node;
  }
  return null;
}

function findTerminalPaneFromEvent(root, event) {
  const path = typeof event.composedPath === "function" ? event.composedPath() : [];
  for (const node of path) {
    if (!(node instanceof HTMLElement) || !root.contains(node)) continue;
    const pane = node.closest?.(".codexpp-terminal-split-pane, [data-codex-terminal], [id^='terminal-panel-'], .xterm");
    if (!(pane instanceof HTMLElement) || !root.contains(pane)) continue;
    if (!pane.matches(".codexpp-terminal-split-pane, [data-codex-terminal], [id^='terminal-panel-'], .xterm")) continue;
    return pane.querySelector?.("[data-codex-terminal], [id^='terminal-panel-'], .xterm") || pane;
  }
  return null;
}

function findTerminalTabs(root) {
  return Array.from(root.querySelectorAll("button, [role='tab'], [role='button']"))
    .filter((node) => node instanceof HTMLElement)
    .filter(isTerminalTabCandidate)
    .slice(0, 48);
}

function isTerminalTabCandidate(node) {
  const text = compactText(node.textContent || node.getAttribute("aria-label") || node.getAttribute("title") || "");
  if (!text) return false;
  if (/\b(new terminal|close|split|pop out|autoscroll|toggle terminal|restore terminal)\b/i.test(text)) return false;
  const rect = node.getBoundingClientRect();
  if (rect.width < 20 || rect.height < 12 || rect.height > 64) return false;
  const nearTerminal = Boolean(node.closest("[role='tablist']")) || /\bterminal\b/i.test(text) || /\$\s*$|%$|zsh|bash|node|npm|pnpm|echo/i.test(text);
  return nearTerminal;
}

function isTerminalTabCloseControl(node) {
  if (!(node instanceof Element)) return false;
  const control = node.closest("button, [role='button'], [aria-label], [title]");
  if (!(control instanceof HTMLElement)) return false;
  const label = compactText(`${control.textContent || ""} ${control.getAttribute("aria-label") || ""} ${control.getAttribute("title") || ""}`);
  if (!/\b(close|dismiss|remove)\b/i.test(label)) return false;
  return Boolean(control.closest("[data-tab-id^='terminal:']"));
}

function activeTerminalTab(root) {
  const tabs = findTerminalTabs(root);
  return (
    tabs.find((tab) => tab.getAttribute("aria-selected") === "true") ||
    tabs.find((tab) => tab.getAttribute("data-state") === "active") ||
    tabs.find((tab) => /\bactive\b|selected/.test(String(tab.className))) ||
    tabs[0] ||
    null
  );
}

function activeTabTitle(state) {
  return compactText((state.activeTab || activeTerminalTab(state.activeRoot || document.body))?.textContent || "Codex Terminal");
}

function terminalTabKey(tab, index) {
  return terminalTabKeys(tab, index)[0];
}

function terminalTabKeys(tab, index) {
  const keys = [];
  const session = terminalSessionFromNode(globalThis.__codexppBetterTerminalState, tab);
  if (session?.sessionId) keys.push(`session:${session.sessionId}`);
  const tabId = tab.closest?.("[data-tab-id]")?.getAttribute("data-tab-id") || tab.getAttribute?.("data-tab-id");
  if (tabId) keys.push(tabId);
  const storedKey = tab.dataset?.[camel(TAB_KEY_ATTR)];
  if (storedKey) keys.push(storedKey);
  const text = compactText(tab.dataset[camel(ORIGINAL_TEXT_ATTR)] || tab.textContent || tab.getAttribute("aria-label") || "");
  keys.push(`${index}:${text || "terminal"}`);
  return Array.from(new Set(keys.filter(Boolean)));
}

function applyAutoscrollLock(state, root) {
  if (!state.autoscrollLocked) return;
  for (const scroller of findTerminalScrollers(root)) {
    const current = state.scrollPositions.get(scroller);
    if (!current) {
      if (!isNearBottom(scroller)) state.scrollPositions.set(scroller, scroller.scrollTop);
      continue;
    }
    if (Math.abs(scroller.scrollTop - current) > SCROLL_STICKINESS_PX) {
      scroller.scrollTop = current;
    }
  }
}

function findTerminalScrollers(root) {
  return Array.from(root.querySelectorAll(".xterm-viewport, [class*='viewport'], [class*='scroll'], div"))
    .filter((node) => node instanceof HTMLElement)
    .filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.width > 180 && rect.height > 80 && node.scrollHeight > node.clientHeight + 20;
    });
}

function onScrollCapture(state) {
  return (event) => {
    if (!state.autoscrollLocked) return;
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const root = state.activeRoot || findTerminalRoot();
    if (!root?.contains(target)) return;
    if (!isNearBottom(target)) state.scrollPositions.set(target, target.scrollTop);
  };
}

function isNearBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_STICKINESS_PX;
}

function registerSettingsPage(state) {
  if (typeof state.api.settings?.registerPage !== "function") return;
  state.pageHandle = state.api.settings.registerPage({
    id: "main",
    title: "Better Terminal",
    description: "Adds a terminal-tab context menu for live terminal actions, titles, and autoscroll.",
    iconSvg:
      '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" class="icon-sm inline-block align-middle" aria-hidden="true">' +
      '<rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>' +
      '<path d="m6 8 2 2-2 2M10 12h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
      "</svg>",
    render(root) {
      root.appendChild(settingsSection(state));
    },
  });
}

function settingsSection(state) {
  const section = el("section", "flex flex-col gap-2");
  section.appendChild(settingsTitle("Behavior"));
  const card = el("div", "rounded-lg border border-token-border-default bg-token-bg-secondary");
  card.append(
    settingsRow(
      "Terminal tab context menu",
      "Right-click a terminal tab to open Better Terminal actions.",
      nativeSwitch("Enable Better Terminal context menu", state.contextMenuEnabled, (next) => {
        state.contextMenuEnabled = next;
        state.api.storage.set("context-menu-enabled", next);
        if (!next) closeContextMenu(state);
      }),
    ),
    settingsRow(
      "Disable autoscroll by default",
      "Keep terminal scroll containers from snapping to the bottom.",
      nativeSwitch("Disable terminal autoscroll by default", state.autoscrollLocked, (next) => {
        state.autoscrollLocked = next;
        state.api.storage.set("autoscroll-locked", next);
        apply(state);
      }),
    ),
    settingsRow(
      "Terminal memory watchdog",
      "Pause terminal process trees that exceed the configured system-memory limit.",
      nativeSwitch("Enable terminal memory watchdog", state.memoryWatchdogEnabled, (next) => {
        state.memoryWatchdogEnabled = next;
        state.api.storage.set("memory-watchdog-enabled", next);
        syncMemoryWatchdogSettingsToMain(state);
      }),
    ),
    settingsRow(
      "Freeze threshold",
      "Percentage of system RAM a terminal process tree can use before it is stopped.",
      nativeNumberInput("Terminal memory freeze threshold", state.memoryWatchdogThresholdPercent, (next) => {
        state.memoryWatchdogThresholdPercent = clampMemoryThreshold(next);
        state.api.storage.set("memory-watchdog-threshold-percent", state.memoryWatchdogThresholdPercent);
        syncMemoryWatchdogSettingsToMain(state);
      }),
    ),
  );
  section.appendChild(card);
  return section;
}

function settingsTitle(text) {
  const node = el("div", "text-token-text-secondary px-1 text-xs font-semibold uppercase tracking-wide");
  node.textContent = text;
  return node;
}

function settingsRow(title, description, control) {
  const row = el("div", "flex items-center justify-between gap-4 p-3");
  const left = el("div", "flex min-w-0 flex-col gap-1");
  const label = el("div", "min-w-0 text-sm text-token-text-primary");
  label.textContent = title;
  const desc = el("div", "text-token-text-secondary min-w-0 text-sm");
  desc.textContent = description;
  left.append(label, desc);
  row.append(left, control);
  return row;
}

function nativeSwitch(label, initial, onChange) {
  const button = document.createElement("button");
  button.type = "button";
  button.role = "switch";
  button.setAttribute("aria-label", label);
  button.className = "inline-flex items-center text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-token-focus-border focus-visible:rounded-full cursor-interaction";
  const track = document.createElement("span");
  track.className = "relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 ease-out h-5 w-8";
  const knob = document.createElement("span");
  knob.className = "rounded-full border border-[color:var(--gray-0)] bg-[color:var(--gray-0)] shadow-sm h-4 w-4 translate-x-0.5 transition-transform duration-200 ease-out";
  track.appendChild(knob);
  button.appendChild(track);
  const set = (value) => {
    button.setAttribute("aria-checked", String(value));
    button.dataset.state = value ? "checked" : "unchecked";
    track.dataset.state = button.dataset.state;
    knob.dataset.state = button.dataset.state;
    track.className =
      "relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 ease-out h-5 w-8 " +
      (value ? "bg-token-charts-blue" : "bg-token-foreground/10");
    knob.className =
      "rounded-full border border-[color:var(--gray-0)] bg-[color:var(--gray-0)] shadow-sm transition-transform duration-200 ease-out data-[state=unchecked]:translate-x-0 h-4 w-4 data-[state=unchecked]:translate-x-[2px] data-[state=checked]:translate-x-[14px]";
  };
  set(Boolean(initial));
  button.addEventListener("click", () => {
    const next = button.getAttribute("aria-checked") !== "true";
    set(next);
    onChange(next);
  });
  return button;
}

function nativeNumberInput(label, initial, onChange) {
  const wrapper = el("div", "flex items-center gap-2");
  const input = document.createElement("input");
  input.type = "number";
  input.min = "1";
  input.max = "95";
  input.step = "1";
  input.value = String(clampMemoryThreshold(initial));
  input.setAttribute("aria-label", label);
  input.className = "w-20 rounded-xl border border-token-border bg-token-main-surface-primary px-3 py-2 text-right text-sm text-token-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-token-focus-border";
  const suffix = el("span", "text-token-text-secondary text-sm");
  suffix.textContent = "%";
  input.addEventListener("change", () => {
    input.value = String(clampMemoryThreshold(input.value));
    onChange(Number(input.value));
  });
  wrapper.append(input, suffix);
  return wrapper;
}

function syncMemoryWatchdogSettingsToMain(state) {
  state.api.ipc.invoke?.(TERMINAL_MEMORY_WATCHDOG_CHANNEL, {
    action: "settings",
    enabled: Boolean(state.memoryWatchdogEnabled),
    thresholdPercent: clampMemoryThreshold(state.memoryWatchdogThresholdPercent),
  }).then((status) => {
    state.memoryWatchdogStatus = status || null;
    exposeMemoryWatchdogStatus(status);
    apply(state);
  }).catch((error) => {
    state.api.log.debug("[better-terminal] memory watchdog settings sync failed", String(error));
  });
}

function refreshMemoryWatchdogStatus(state) {
  reportTerminalWindowState(state);
  state.api.ipc.invoke?.(TERMINAL_MEMORY_WATCHDOG_CHANNEL, { action: "status" }).then((status) => {
    state.memoryWatchdogStatus = status || null;
    exposeMemoryWatchdogStatus(status);
    apply(state);
  }).catch(() => {});
}

function runMemoryWatchdogAction(state, action, sessionId) {
  if (!sessionId) return;
  state.api.ipc.invoke?.(TERMINAL_MEMORY_WATCHDOG_CHANNEL, { action, sessionId }).then((status) => {
    state.memoryWatchdogStatus = status || null;
    exposeMemoryWatchdogStatus(status);
    apply(state);
  }).catch((error) => {
    state.api.log.warn("[better-terminal] terminal memory watchdog action failed", String(error));
  });
}

function exposeMemoryWatchdogStatus(status) {
  try {
    document.documentElement.dataset.codexppBetterTerminalMemoryWatchdogStatus = JSON.stringify(status || null);
  } catch {}
}

function setElementLabel(el, label) {
  const textNode = Array.from(el.childNodes).find((node) => node.nodeType === Node.TEXT_NODE);
  if (textNode) {
    textNode.textContent = label;
    return;
  }
  const labelNode = Array.from(el.querySelectorAll("span, div"))
    .find((node) => node instanceof HTMLElement && compactText(node.textContent || ""));
  if (labelNode) labelNode.textContent = label;
  else el.textContent = label;
}

function readBool(api, key, fallback) {
  return Boolean(api.storage.get(key, fallback));
}

function readNumber(api, key, fallback) {
  const value = Number(api.storage.get(key, fallback));
  return Number.isFinite(value) ? value : fallback;
}

function readJson(api, key, fallback) {
  const value = api.storage.get(key, fallback);
  return value && typeof value === "object" ? value : fallback;
}

function readSplitPair() {
  try {
    const value = JSON.parse(localStorage.getItem(SPLIT_PAIR_KEY) || "null");
    if (
      !value ||
      !(
        typeof value.conversationId === "string" ||
        value.conversationId === null ||
        value.conversationId === undefined
      ) ||
      (value.anchor !== undefined && value.anchor !== null && typeof value.anchor !== "string") ||
      (
        !Array.isArray(value.sessions) &&
        (typeof value.left !== "string" || typeof value.right !== "string")
      )
    ) {
      return null;
    }
    const sessions = Array.from(new Set(
      (Array.isArray(value.sessions) ? value.sessions : [value.left, value.right])
        .filter((sessionId) => typeof sessionId === "string" && sessionId.length > 0),
    )).slice(0, MAX_SPLIT_SESSIONS);
    if (sessions.length < 2) return null;
    const existingSessions = Array.from(new Set(
      (Array.isArray(value.existingSessions) ? value.existingSessions : [])
        .filter((sessionId) => typeof sessionId === "string" && sessions.includes(sessionId)),
    ));
    const ratio = typeof value.ratio === "number" && Number.isFinite(value.ratio) ? value.ratio : 0.5;
    return {
      ...value,
      conversationId: value.conversationId || null,
      left: sessions[0],
      right: sessions[1],
      sessions,
      existingSessions,
      ratio: Math.max(0.2, Math.min(0.8, ratio)),
    };
  } catch {
    return null;
  }
}

function currentSplitPairForRoot(state, root) {
  const pair = readSplitPair();
  if (!pair) return null;
  return pair;
}

function isSplitPairActiveForSession(splitPair, session) {
  return Boolean(
    splitPair &&
      session?.sessionId &&
      (!splitPair.conversationId || !session.conversationId || splitPair.conversationId === session.conversationId) &&
      splitPair.sessions.includes(session.sessionId),
  );
}

function writeSplitPair(pair) {
  try {
    const ratio = typeof pair.ratio === "number" && Number.isFinite(pair.ratio) ? pair.ratio : 0.5;
    const sessions = Array.from(new Set(
      (Array.isArray(pair.sessions) ? pair.sessions : [pair.left, pair.right])
        .filter((sessionId) => typeof sessionId === "string" && sessionId.length > 0),
    )).slice(0, MAX_SPLIT_SESSIONS);
    if (sessions.length < 2) return;
    const existingSessions = Array.from(new Set(
      (Array.isArray(pair.existingSessions) ? pair.existingSessions : [])
        .filter((sessionId) => typeof sessionId === "string" && sessions.includes(sessionId)),
    ));
    localStorage.removeItem(SPLIT_MODE_KEY);
    localStorage.setItem(SPLIT_PAIR_KEY, JSON.stringify({
      ...pair,
      conversationId: pair.conversationId || null,
      left: sessions[0],
      right: sessions[1],
      sessions,
      existingSessions,
      ratio: Math.max(0.2, Math.min(0.8, ratio)),
    }));
    window.dispatchEvent(new Event("codexpp:better-terminal:split-change"));
  } catch {}
}

function clearSplitPair() {
  try {
    localStorage.removeItem(SPLIT_PAIR_KEY);
    localStorage.removeItem(SPLIT_MODE_KEY);
    window.dispatchEvent(new Event("codexpp:better-terminal:split-change"));
  } catch {}
}

function clearLegacySplitMode() {
  try {
    localStorage.removeItem(SPLIT_MODE_KEY);
  } catch {}
}

function dispatchMetaKey(key, code, target) {
  target?.dispatchEvent(new KeyboardEvent("keydown", {
    key,
    code,
    metaKey: true,
    bubbles: true,
    cancelable: true,
    composed: true,
  }));
}

function sendCodexRendererMessage(type, payload) {
  const message = { ...payload, type };
  if (typeof window.electronBridge?.sendMessageFromView === "function") {
    window.electronBridge.sendMessageFromView(message).catch(() => {});
  }
  window.dispatchEvent(new CustomEvent("codex-message-from-view", { detail: message }));
}

function centeredBounds(width, height) {
  const left = Math.max(0, Math.round((window.screen.availWidth - width) / 2));
  const top = Math.max(0, Math.round((window.screen.availHeight - height) / 2));
  return { x: left, y: top, width, height };
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function compactText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function camel(attr) {
  return attr.replace(/^data-/, "").replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}
