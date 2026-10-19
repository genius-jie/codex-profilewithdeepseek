/**
 * Session Path Normalizer
 *
 * Keeps persisted rollout paths in the same Windows extended-path form that
 * Codex uses for active running sessions.
 */

// Database triggers handle new/updated rows. The periodic pass is only a
// recovery sweep for rows created while the database was unavailable, so keep
// it bounded instead of polling the whole database every two seconds.
const NORMALIZE_INTERVAL_MS = 30_000;
const INITIAL_DELAY_MS = 500;
const STALE_PATH_SCAN_INTERVAL_MS = 1_000;
const STALE_PATH_SCAN_DEBOUNCE_MS = 100;
const NORMALIZE_LOG_INTERVAL_MS = 60_000;
const EXTENDED_PREFIX = "\\\\?\\";
const DRIVE_PATH_RE = /^[A-Za-z]:\\/;
const CANONICAL_PROFILE_ROOT = "@@CODEXPP_PROFILE:escaped@@";
const CANONICAL_CODEX_HOME = "@@CODEXPP_HOME:escaped@@";
const LEGACY_PROFILE_ROOT = "@@USERPROFILE:escaped@@\\AppData\\Roaming\\CodexPlusPlusProfile";
const LEGACY_CODEX_HOME = "@@PROFILE_REPO:escaped@@";
let activeState = null;

/** @type {import("@codex-plusplus/sdk").Tweak} */
module.exports = {
  start(api) {
    // The host normally calls stop() before a reload. Keep start idempotent as
    // a safety net so a duplicate lifecycle event cannot orphan old timers.
    if (activeState) stopState(activeState);
    const state = {};
    if (api.process === "main") state.main = startMain(api);
    if (api.process === "renderer") state.renderer = startRenderer(api);
    activeState = state;
    this._state = state;
  },

  stop() {
    // Keep the state in a module closure as well as on the tweak object. This
    // lets cleanup succeed even when an older host calls stop() unbound.
    const state = activeState || this._state;
    if (!state) return;
    stopState(state);
    activeState = null;
    this._state = null;
  },

  _internals: {
    toExtendedWinPath: toCanonicalWinPath,
    toCanonicalWinPath,
    normalizeRows,
    ensureNormalizationTriggers,
    shouldReplaceNormalizationTriggers,
  },
};

function stopState(state) {
  if (state.main) stopMain(state.main);
  if (state.renderer) stopRenderer(state.renderer);
}

function startMain(api) {
  const state = {
    api,
    db: null,
    initialTimer: null,
    interval: null,
    warned: false,
    running: false,
    lastNormalizeLogAt: 0,
  };

  const run = () => {
    if (state.running) return;
    state.running = true;
    try {
      const changed = normalizeStateDb(state);
      const now = Date.now();
      if (changed > 0 && now - state.lastNormalizeLogAt >= NORMALIZE_LOG_INTERVAL_MS) {
        state.lastNormalizeLogAt = now;
        api.log.info(`[session-path-normalizer] normalized ${changed} thread rollout path(s)`);
      }
      state.warned = false;
    } catch (error) {
      if (!state.warned) {
        state.warned = true;
        api.log.warn("[session-path-normalizer] failed to normalize rollout paths", error);
      }
    } finally {
      state.running = false;
    }
  };

  state.initialTimer = setTimeout(run, INITIAL_DELAY_MS);
  state.interval = setInterval(run, NORMALIZE_INTERVAL_MS);
  state.initialTimer.unref?.();
  state.interval.unref?.();
  api.log.info("[session-path-normalizer] active");
  return state;
}

function stopMain(state) {
  if (state.initialTimer) clearTimeout(state.initialTimer);
  if (state.interval) clearInterval(state.interval);
  try {
    state.db?.close();
  } catch {}
}

function startRenderer(api) {
  const state = {
    api,
    dismissed: new WeakSet(),
    interval: null,
    scanTimer: null,
    scanQueued: false,
    observer: null,
    attachObserver: null,
    scan: null,
  };

  state.scan = () => {
    if (state.scanQueued) return;
    state.scanQueued = true;
    state.scanTimer = setTimeout(() => {
      state.scanTimer = null;
      state.scanQueued = false;
      scanStalePathToasts(state);
    }, STALE_PATH_SCAN_DEBOUNCE_MS);
    state.scanTimer.unref?.();
  };
  state.attachObserver = () => {
    if (state.observer || !document.documentElement) return;
    state.observer = new MutationObserver(state.scan);
    state.observer.observe(document.documentElement, { childList: true, subtree: true });
  };

  state.attachObserver();
  document.addEventListener("DOMContentLoaded", state.attachObserver, { once: true });
  state.interval = setInterval(state.scan, STALE_PATH_SCAN_INTERVAL_MS);
  setTimeout(state.scan, 0);
  api.log.info("[session-path-normalizer] renderer stale-path guard active");
  return state;
}

function stopRenderer(state) {
  if (state.interval) clearInterval(state.interval);
  if (state.scanTimer) clearTimeout(state.scanTimer);
  if (state.observer) state.observer.disconnect();
  if (state.attachObserver) document.removeEventListener("DOMContentLoaded", state.attachObserver);
}

function scanStalePathToasts(state) {
  try {
    const body = document.body;
    if (!body) return;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let node;
    while (node = walker.nextNode()) {
      const text = node.textContent || "";
      if (!text.includes("stale path") && !text.includes("cannot resume running thread")) continue;
      const root = toastRootFor(node);
      const full = root?.textContent || "";
      if (stalePathFalsePositiveText(full)) {
        dismissToast(state, root);
        return;
      }
    }
  } catch {}
}

function stalePathFalsePositiveText(text) {
  if (!text || !text.includes("stale path")) return false;
  const matches = Array.from(text.matchAll(/`([^`]+)`/g)).map((match) => match[1]);
  if (matches.length < 2) return false;
  const normalized = matches.map(stripExtendedPathPrefix).filter(Boolean);
  if (normalized.length < 2) return false;
  return normalized.every((item) => item === normalized[0]);
}

function stripExtendedPathPrefix(value) {
  return String(value || "").trim().replace(/^\\\\\?\\/, "").replace(/\\\\\?\\(?=[A-Za-z]:\\)/g, "").toLowerCase();
}

function toastRootFor(node) {
  let current = node instanceof Element ? node : node?.parentElement || null;
  let best = current;
  for (let i = 0; i < 16 && current; i++) {
    const role = current.getAttribute?.("role");
    const text = current.textContent || "";
    if (role === "alert" || role === "status") best = current;
    if (text.includes("cannot resume running thread") && text.includes("stale path")) best = current;
    current = current.parentElement;
  }
  return best;
}

function dismissToast(state, el) {
  if (!el || state.dismissed.has(el)) return;
  state.dismissed.add(el);
  state.api.log.info("[session-path-normalizer] dismissed stale-path false-positive toast");
  const button = el.querySelector?.("button[aria-label*='close' i], button[aria-label*='dismiss' i], button[data-dismiss]");
  if (button) {
    button.click();
    return;
  }
  for (const candidate of el.querySelectorAll?.("button") || []) {
    const label = (candidate.textContent || "").trim();
    if (label === "\u00D7" || label === "\u2715" || label === "\u2716" || label === "x" || label === "X") {
      candidate.click();
      return;
    }
  }
  el.style.display = "none";
  setTimeout(() => {
    try {
      el.remove();
    } catch {}
  }, 300);
}

function normalizeStateDb(state) {
  const db = openStateDb(state);
  ensureNormalizationTriggers(db);
  const rows = db.prepare(`
    SELECT id, rollout_path AS rolloutPath
    FROM threads
    WHERE rollout_path IS NOT NULL AND rollout_path != ''
  `).all();
  const updates = normalizeRows(rows);
  if (!updates.length) return 0;

  const update = db.prepare("UPDATE threads SET rollout_path = ? WHERE id = ? AND rollout_path = ?");
  const tx = db.transaction((items) => {
    let changed = 0;
    for (const item of items) {
      const result = update.run(item.next, item.id, item.previous);
      changed += result.changes || 0;
    }
    return changed;
  });
  return tx(updates);
}

function ensureNormalizationTriggers(db) {
  const rows = db.prepare(`
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'trigger'
      AND name IN (
        'codexpp_normalize_thread_rollout_path_ai',
        'codexpp_normalize_thread_rollout_path_au'
      )
  `).all();
  if (!shouldReplaceNormalizationTriggers(rows)) return;

  db.exec(`
    DROP TRIGGER IF EXISTS codexpp_normalize_thread_rollout_path_ai;
    DROP TRIGGER IF EXISTS codexpp_normalize_thread_rollout_path_au;
    CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_rollout_path_ai
    AFTER INSERT ON threads
    WHEN substr(NEW.rollout_path, 1, 4) = '\\\\?\\'
    BEGIN
      UPDATE threads
      SET rollout_path = substr(NEW.rollout_path, 5)
      WHERE id = NEW.id;
    END;
    CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_rollout_path_au
    AFTER UPDATE OF rollout_path ON threads
    WHEN substr(NEW.rollout_path, 1, 4) = '\\\\?\\'
    BEGIN
      UPDATE threads
      SET rollout_path = substr(NEW.rollout_path, 5)
      WHERE id = NEW.id;
    END;
  `);
}

function shouldReplaceNormalizationTriggers(rows) {
  const byName = new Map((Array.isArray(rows) ? rows : []).map((row) => [row.name, String(row.sql || "")]));
  return [
    "codexpp_normalize_thread_rollout_path_ai",
    "codexpp_normalize_thread_rollout_path_au",
  ].some((name) => {
    const sql = byName.get(name) || "";
    if (!sql) return true;
    return !sql.includes("SET rollout_path = substr(NEW.rollout_path, 5)");
  });
}

function openStateDb(state) {
  if (state.db) return state.db;
  const path = require("path");
  const os = require("os");
  const Database = requireBetterSqlite3(path);
  const codexHome = process.env.CODEX_HOME || CANONICAL_CODEX_HOME;
  const dbPath = path.join(codexHome, "state_5.sqlite");
  const db = new Database(dbPath);
  db.pragma("busy_timeout = 2000");
  state.db = db;
  return db;
}

function normalizeRows(rows) {
  const fs = require("fs");
  const updates = [];
  for (const row of Array.isArray(rows) ? rows : []) {
    const previous = String(row?.rolloutPath || "");
    const next = toCanonicalWinPath(previous);
    if (!next || next === previous) continue;
    if (!fs.existsSync(next)) continue;
    updates.push({ id: row.id, previous, next });
  }
  return updates;
}

function toCanonicalWinPath(value) {
  let raw = String(value || "").trim();
  if (!raw) return raw;
  raw = raw.replace(/^\\\\\?\\/, "");
  raw = raw.replace(/^\\\\['\"]?\\(?=[A-Za-z]:\\)/, "");
  raw = raw.replace(/^\\\\['\"]?\\/, "");
  if (!DRIVE_PATH_RE.test(raw)) return raw;

  const legacyProfilePrefix = `${LEGACY_PROFILE_ROOT}\\`;
  const legacyCodexPrefix = `${LEGACY_CODEX_HOME}\\`;
  if (raw.toLowerCase().startsWith(legacyProfilePrefix.toLowerCase())) {
    const suffix = raw.slice(legacyProfilePrefix.length);
    if (suffix.toLowerCase() === ".codex" || suffix.toLowerCase().startsWith(".codex\\")) {
      return `${CANONICAL_CODEX_HOME}\\${suffix.slice(7)}`.replace(/\\$/, "");
    }
    return `${CANONICAL_PROFILE_ROOT}\\${suffix}`;
  }
  if (raw.toLowerCase().startsWith(legacyCodexPrefix.toLowerCase())) {
    return `${CANONICAL_CODEX_HOME}\\${raw.slice(legacyCodexPrefix.length)}`;
  }
  return raw;
}

function requireBetterSqlite3(path) {
  try {
    return require("better-sqlite3");
  } catch (firstError) {
    try {
      const { createRequire } = require("module");
      const resourcesPath = process.resourcesPath || process.cwd();
      return createRequire(path.join(resourcesPath, "app.asar", "package.json"))("better-sqlite3");
    } catch {
      throw firstError;
    }
  }
}
