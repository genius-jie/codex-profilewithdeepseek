/**
 * Codex Tab Switcher
 *
 * A Ctrl-Tab recent-chat switcher with tiny chat-pane previews.
 *
 * Renderer owns keyboard handling, overlay DOM, and storage. Main owns local
 * session-index reads and Electron capturePage access.
 */

const IPC_RECENT_CHATS = "recent-chats";
const IPC_CAPTURE_CHAT_PREVIEW = "capture-chat-preview";
const IPC_NAVIGATE_CHAT = "navigate-chat";
const PREVIEW_STORAGE_VERSION = 3;
const PREVIEW_WIDTH = 384;
const PREVIEW_HEIGHT = 224;

/** @type {import("@codex-plusplus/sdk").Tweak} */
module.exports = {
  start(api) {
    if (api.process === "main") {
      startMain(api);
      return;
    }
    startRenderer(this, api);
  },

  stop() {
    const state = this._state;
    if (!state) return;
    state.disposed = true;
    document.removeEventListener("keydown", state.onKeyDown, true);
    document.removeEventListener("keyup", state.onKeyUp, true);
    document.removeEventListener("pointerdown", state.onPointerDown, true);
    document.removeEventListener("pointermove", state.onOverlayPointerEvent, true);
    document.removeEventListener("mouseover", state.onOverlayPointerEvent, true);
    document.removeEventListener("mousemove", state.onOverlayPointerEvent, true);
    window.removeEventListener("popstate", state.onRouteChange);
    window.removeEventListener("hashchange", state.onRouteChange);
    window.removeEventListener("codexpp-tab-switcher-before-route", state.onBeforeRoute);
    window.removeEventListener("codexpp-tab-switcher-route", state.onRouteChange);
    if (state.routePoll) window.clearInterval(state.routePoll);
    if (state.captureTimer) window.clearTimeout(state.captureTimer);
    if (window.__codexppTabSwitcherState === state) {
      window.__codexppTabSwitcherState = null;
    }
    removeOverlay(state);
  },
};

// ---------------------------------------------------------------- renderer --

function startRenderer(self, api) {
  const state = {
    api,
    disposed: false,
    overlay: null,
    items: [],
    selected: 0,
    isOpen: false,
    opening: false,
    controlDown: false,
    switching: false,
    previewCache: new Map(),
    pendingChatId: null,
    keyboardCycleUntil: 0,
    lastUrl: window.location.href,
    currentChatId: getCurrentChatId(),
    captureTimer: null,
    routePoll: null,
    onKeyDown: null,
    onKeyUp: null,
    onPointerDown: null,
    onOverlayPointerEvent: null,
    onBeforeRoute: null,
    onRouteChange: null,
  };
  self._state = state;
  window.__codexppTabSwitcherState = state;

  state.onKeyDown = (event) => handleKeyDown(state, event);
  state.onKeyUp = (event) => handleKeyUp(state, event);
  state.onPointerDown = (event) => handlePointerDown(state, event);
  state.onOverlayPointerEvent = (event) => handleOverlayPointerEvent(state, event);
  state.onBeforeRoute = () => handleBeforeRoute(state);
  state.onRouteChange = () => handleRouteChange(state);

  document.addEventListener("keydown", state.onKeyDown, true);
  document.addEventListener("keyup", state.onKeyUp, true);
  document.addEventListener("pointerdown", state.onPointerDown, true);
  document.addEventListener("pointermove", state.onOverlayPointerEvent, true);
  document.addEventListener("mouseover", state.onOverlayPointerEvent, true);
  document.addEventListener("mousemove", state.onOverlayPointerEvent, true);
  window.addEventListener("popstate", state.onRouteChange);
  window.addEventListener("hashchange", state.onRouteChange);
  window.addEventListener("codexpp-tab-switcher-before-route", state.onBeforeRoute);
  patchHistory(state);
  state.routePoll = window.setInterval(state.onRouteChange, 700);

  api.log.info("[tab-switcher] renderer active");
}

function handleKeyDown(state, event) {
  if (state.isOpen && (event.key === "Escape" || event.key === "Enter")) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.key === "Escape") cancelSwitcher(state);
    else void commitSelection(state);
    return;
  }

  if (event.defaultPrevented && !state.isOpen) return;
  if (event.key !== "Tab" || !event.ctrlKey || event.altKey || event.metaKey) return;

  event.preventDefault();
  event.stopImmediatePropagation();
  state.controlDown = true;

  if (!state.isOpen) {
    void openSwitcher(state, event.shiftKey ? -1 : 1);
    return;
  }
  moveSelection(state, event.shiftKey ? -1 : 1);
}

function handleKeyUp(state, event) {
  if (!state.isOpen) return;

  if (event.key === "Escape") {
    event.preventDefault();
    event.stopImmediatePropagation();
    cancelSwitcher(state);
    return;
  }

  if (event.key === "Enter") {
    event.preventDefault();
    event.stopImmediatePropagation();
    void commitSelection(state);
    return;
  }

  if (event.key === "Control") {
    event.preventDefault();
    event.stopImmediatePropagation();
    state.controlDown = false;
    void commitSelection(state);
  }
}

async function openSwitcher(state, direction) {
  if (state.isOpen || state.opening || state.disposed) return;
  state.opening = true;
  const currentId = getCurrentChatId() || state.currentChatId;
  let pendingCurrentPreview = null;
  try {
    if (currentId) {
      await capturePreviewForChat(state, currentId);
    } else {
      pendingCurrentPreview = await captureVisiblePreview(state);
    }

    let items;
    try {
      items = await state.api.ipc.invoke(IPC_RECENT_CHATS);
    } catch (error) {
      state.api.log.warn("[tab-switcher] recent chats unavailable", error);
      return;
    }
    if (!Array.isArray(items) || items.length === 0) return;

    if (!currentId && pendingCurrentPreview && items[0]?.id) {
      state.currentChatId = items[0].id;
      state.previewCache.set(items[0].id, pendingCurrentPreview);
      state.api.storage.set(previewKey(items[0].id), {
        dataUrl: pendingCurrentPreview,
        capturedAt: Date.now(),
      });
      state.api.log.info("[tab-switcher] preview captured for first recent chat", {
        chatId: items[0].id,
        bytes: pendingCurrentPreview.length,
      });
    }

    state.items = attachSidebarIndicators(attachPreviews(state, items.slice(0, 5)));
    prunePreviewStorage(state, state.items.map((item) => item.id));

    if (state.items.length > 1) {
      state.selected = direction >= 0 ? 1 : state.items.length - 1;
    } else {
      state.selected = 0;
    }

    state.isOpen = true;
    renderOverlay(state);
  } finally {
    state.opening = false;
  }
}

function moveSelection(state, delta) {
  if (!state.items.length) return;
  state.keyboardCycleUntil = Date.now() + 250;
  state.selected = wrapIndex(state.selected + delta, state.items.length);
  renderItems(state);
}

async function commitSelection(state) {
  if (state.switching) return;
  const item = state.items[state.selected];
  removeOverlay(state);
  if (!item) return;

  const currentId = getCurrentChatId() || state.currentChatId;
  if (currentId && currentId !== item.id) {
    await waitForNextPaint();
    await capturePreviewForChat(state, currentId);
  }
  if (item.id === currentId) return;

  state.switching = true;
  await navigateToChat(state, item.id);
  state.currentChatId = item.id;
  window.setTimeout(() => {
    state.switching = false;
    state.currentChatId = getCurrentChatId() || state.currentChatId;
  }, 400);
}

function cancelSwitcher(state) {
  removeOverlay(state);
}

function renderOverlay(state) {
  if (!state.overlay) {
    const overlay = el(
      "div",
      "fixed inset-0 flex items-center justify-center bg-token-bg-primary/70 p-6 backdrop-blur-sm",
    );
    overlay.dataset.codexppTabSwitcher = "true";
    overlay.style.zIndex = "2147483647";
    overlay.style.pointerEvents = "auto";
    overlay.addEventListener("mousedown", (event) => {
      if (event.target === overlay) cancelSwitcher(state);
    });

    const panel = el(
      "div",
      "border-token-border flex w-[min(980px,calc(100vw-48px))] flex-col overflow-hidden rounded-lg border bg-token-bg-primary shadow-2xl",
    );
    const list = el("div", "flex min-w-0 gap-3 overflow-x-auto p-3");
    list.dataset.codexppTabSwitcherList = "true";
    panel.appendChild(list);
    overlay.appendChild(panel);
    state.overlay = overlay;
    document.body.appendChild(overlay);
  }
  renderItems(state);
}

function renderItems(state) {
  const list = state.overlay?.querySelector("[data-codexpp-tab-switcher-list]");
  if (!list) return;
  list.replaceChildren();

  state.items.forEach((item, index) => {
    const selected = index === state.selected;
    const row = el(
      "button",
      "focus-visible:outline-token-border relative flex h-[190px] w-44 shrink-0 flex-col gap-2 overflow-hidden rounded-lg px-row-x py-row-y text-left cursor-interaction focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 " +
        (selected
          ? "bg-token-list-hover-background text-token-list-active-selection-foreground"
          : "text-token-foreground"),
    );
    row.type = "button";
    row.setAttribute("aria-selected", String(selected));
    row.addEventListener("mouseenter", () => {
      if (Date.now() < state.keyboardCycleUntil) return;
      state.selected = index;
      renderItems(state);
    });
    row.addEventListener("click", () => {
      state.selected = index;
      void commitSelection(state);
    });

    row.appendChild(previewNode(item));

    const body = el("div", "flex min-w-0 flex-1 flex-col gap-1");
    const titleLine = el(
      "div",
      "line-clamp-2 min-h-[2.5rem] overflow-hidden text-sm font-medium leading-5",
    );
    titleLine.textContent = item.title || "Untitled chat";
    const meta = el("div", "min-w-0 flex-1 truncate text-xs text-token-text-secondary");
    meta.textContent = formatMetadata(item);
    const footer = el("div", "mt-auto flex min-h-4 min-w-0 items-end justify-between gap-2");
    const indicators = sidebarIndicatorsNode(item);
    body.append(titleLine);
    const spacer = el("div", "min-h-0 flex-1");
    footer.append(meta, indicators);
    body.append(spacer, footer);
    row.appendChild(body);

    list.appendChild(row);
  });
}

function sidebarIndicatorsNode(item) {
  const wrap = el("div", "flex shrink-0 items-center justify-end gap-1.5");
  if (item.hasProgress || item.isRunning) {
    const progress = el(
      "span",
      "h-3 w-3 rounded-full border border-token-text-secondary border-t-transparent animate-spin",
    );
    progress.setAttribute("aria-label", "Running");
    wrap.appendChild(progress);
  }
  if (item.hasUnread) {
    const unread = el("span", "h-2 w-2 rounded-full bg-token-charts-blue");
    unread.setAttribute("aria-label", "Unread");
    wrap.appendChild(unread);
  }
  return wrap;
}

function previewNode(item) {
  const wrap = el(
    "div",
    "border-token-border flex w-full shrink-0 items-center justify-center overflow-hidden rounded-md border bg-token-foreground/5",
  );
  wrap.style.height = "104px";
  if (item.preview) {
    const img = document.createElement("img");
    img.src = item.preview;
    img.alt = "";
    img.className = "h-full w-full object-cover";
    wrap.appendChild(img);
    return wrap;
  }

  const initials = el("div", "text-sm font-medium text-token-text-secondary");
  initials.textContent = initialsFor(item.title);
  wrap.appendChild(initials);
  return wrap;
}

function removeOverlay(state) {
  state.overlay?.remove();
  state.overlay = null;
  state.isOpen = false;
  state.items = [];
  state.selected = 0;
}

async function capturePreviewForChat(state, chatId) {
  if (!chatId || state.disposed || state.isOpen) return null;
  await waitForNextPaint();
  const dataUrl = await captureVisiblePreview(state);
  if (!dataUrl) return null;
  state.previewCache.set(chatId, dataUrl);
  state.api.storage.set(previewKey(chatId), {
    dataUrl,
    capturedAt: Date.now(),
  });
  state.api.log.info("[tab-switcher] preview captured", {
    chatId,
    bytes: dataUrl.length,
  });
  return dataUrl;
}

async function captureVisiblePreview(state) {
  if (state.disposed || state.isOpen) return null;
  const rect = findChatPaneRect() || fallbackContentRect();
  if (!rect) return null;
  try {
    const dataUrl = await state.api.ipc.invoke(IPC_CAPTURE_CHAT_PREVIEW, rect);
    if (typeof dataUrl === "string" && dataUrl.startsWith("data:image/")) {
      return dataUrl;
    }
    state.api.log.warn("[tab-switcher] preview capture returned empty", {
      rect,
      type: typeof dataUrl,
    });
  } catch (error) {
    state.api.log.warn("[tab-switcher] preview capture failed", error);
  }
  return null;
}

function handleOverlayPointerEvent(state, event) {
  if (!state.isOpen || state.disposed) return;
  const overlay = state.overlay;
  if (!overlay) return;
  const target = event.target;
  if (target instanceof Node && overlay.contains(target)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function handleRouteChange(state) {
  const nextUrl = window.location.href;
  if (nextUrl === state.lastUrl) return;

  state.lastUrl = nextUrl;
  state.currentChatId = getCurrentChatId() || state.pendingChatId || state.currentChatId;
  state.pendingChatId = null;
}

function handleBeforeRoute(state) {
  if (state.isOpen || state.disposed) return;
  const currentId = getCurrentChatId() || state.currentChatId;
  if (currentId) void capturePreviewForChat(state, currentId);
}

function handlePointerDown(state, event) {
  if (state.isOpen || state.disposed) return;
  const currentId = getCurrentChatId() || state.currentChatId;
  if (!currentId) return;
  const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!(anchor instanceof HTMLAnchorElement)) return;
  const href = new URL(anchor.href, window.location.href);
  const nextId = chatIdFromPathname(href.pathname);
  if (nextId && nextId !== currentId) {
    void waitForNextPaint().then(() => capturePreviewForChat(state, currentId));
    state.pendingChatId = nextId;
  }
}

function patchHistory(state) {
  window.addEventListener("codexpp-tab-switcher-route", state.onRouteChange);
  if (window.__codexppTabSwitcherHistoryPatchVersion !== 2) {
    window.__codexppTabSwitcherHistoryPatched = true;
    window.__codexppTabSwitcherHistoryPatchVersion = 2;
    for (const method of ["pushState", "replaceState"]) {
      const previous = history[method];
      history[method] = function patchedHistoryMethod() {
        window.dispatchEvent(new Event("codexpp-tab-switcher-before-route"));
        const result = previous.apply(this, arguments);
        window.dispatchEvent(new Event("codexpp-tab-switcher-route"));
        return result;
      };
    }
  }
}

function findChatPaneRect() {
  const candidates = [];
  const selectors = [
    "main",
    '[role="main"]',
    '[data-testid*="conversation" i]',
    '[data-testid*="chat" i]',
  ];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      if (!(node instanceof HTMLElement)) continue;
      const rect = node.getBoundingClientRect();
      if (rect.width < 320 || rect.height < 240) continue;
      candidates.push({ node, rect, score: scoreChatPane(node, rect) });
    }
  }
  candidates.sort((a, b) => b.score - a.score);
  const rect = candidates[0]?.rect || fallbackContentRect();
  if (!rect) return null;
  return {
    x: Math.max(0, Math.round(rect.left)),
    y: Math.max(0, Math.round(rect.top)),
    width: Math.max(1, Math.round(Math.min(rect.width, window.innerWidth - rect.left))),
    height: Math.max(1, Math.round(Math.min(rect.height, window.innerHeight - rect.top))),
  };
}

function scoreChatPane(node, rect) {
  let score = 0;
  if (node.tagName === "MAIN") score += 5;
  if (node.getAttribute("role") === "main") score += 4;
  if (rect.left > 120) score += 2;
  if (rect.width > window.innerWidth * 0.45) score += 2;
  if (node.querySelector("textarea, [contenteditable='true']")) score += 2;
  return score;
}

function fallbackContentRect() {
  const left = Math.min(320, Math.max(0, Math.round(window.innerWidth * 0.22)));
  return {
    x: left,
    left,
    y: 0,
    top: 0,
    width: window.innerWidth - left,
    height: window.innerHeight,
  };
}

function attachPreviews(state, items) {
  return items.map((item) => {
    const memoryPreview = state.previewCache.get(item.id);
    const stored = state.api.storage.get(previewKey(item.id), null);
    return {
      ...item,
      preview: typeof memoryPreview === "string"
        ? memoryPreview
        : typeof stored?.dataUrl === "string"
          ? stored.dataUrl
          : null,
    };
  });
}

function attachSidebarIndicators(items) {
  return items.map((item) => {
    const sidebarNode = findSidebarChatNode(item);
    const indicators = readSidebarIndicators(sidebarNode);
    return {
      ...item,
      hasUnread: indicators.hasUnread,
      hasProgress: item.isRunning || indicators.hasProgress,
    };
  });
}

function findSidebarChatNode(item) {
  const path = `/local/${encodeURIComponent(item.id)}`;
  const anchors = [
    ...document.querySelectorAll(`a[href="${path}"], a[href^="${path}?"]`),
    ...document.querySelectorAll(`a[href$="/local/${cssEscape(item.id)}"], a[href*="/local/${cssEscape(item.id)}?"]`),
  ];
  for (const anchor of anchors) {
    const row = closestSidebarItem(anchor);
    if (row) return row;
  }

  const title = normalizeIndicatorText(item.title);
  if (!title) return null;
  const titleMatches = [];
  for (const node of document.querySelectorAll("aside *, nav *")) {
    if (!(node instanceof HTMLElement)) continue;
    const text = normalizeIndicatorText(node.textContent);
    if (!text) continue;
    if (text === title || text.includes(title) || (text.length >= 8 && title.includes(text))) {
      titleMatches.push({ node, textLength: text.length });
    }
  }
  titleMatches.sort((a, b) => a.textLength - b.textLength);
  for (const match of titleMatches) {
    const row = closestSidebarItem(match.node);
    if (row) return row;
  }
  return null;
}

function closestSidebarItem(node) {
  if (!(node instanceof Element)) return null;
  const row = node.closest("a[href*='/local/'], button, [role='link'], [role='button'], [role='treeitem'], [role='listitem']");
  if (!(row instanceof HTMLElement)) return node instanceof HTMLElement ? node : null;
  if (row.querySelectorAll("a[href*='/local/']").length > 1) return null;
  return row;
}

function readSidebarIndicators(node) {
  if (!(node instanceof HTMLElement)) return { hasUnread: false, hasProgress: false };
  const hasProgress = hasMatchingElement(node,
    [
      "[role='progressbar']",
      "[aria-label*='progress' i]",
      "[aria-label*='running' i]",
      "[aria-label*='loading' i]",
      "[data-testid*='progress' i]",
      "[data-testid*='spinner' i]",
      "[data-testid*='loading' i]",
      "[class*='spinner' i]",
      "svg[class*='animate-spin']",
      "[class~='animate-spin']",
    ],
  );
  const hasUnread = unreadScopesForSidebarItem(node).some((scope) => hasUnreadMarker(scope));
  return { hasUnread, hasProgress };
}

function unreadScopesForSidebarItem(node) {
  const scopes = [node];
  const parent = node.parentElement;
  if (parent && parent.querySelectorAll("a[href*='/local/']").length <= 1) scopes.push(parent);
  const grandparent = parent?.parentElement;
  if (grandparent && grandparent.querySelectorAll("a[href*='/local/']").length <= 1) scopes.push(grandparent);
  return scopes;
}

function hasUnreadMarker(scope) {
  if (hasUnreadTitleStyle(scope)) return true;
  return hasMatchingElement(
    scope,
    [
      "[aria-label*='unread' i]",
      "[data-testid*='unread' i]",
      "[class*='unread' i]",
      "[class*='bg-token-charts-blue'][class*='rounded-full']",
      "[class*='bg-token-text-link-foreground'][class*='rounded-full']",
      "[class*='bg-token-text-primary'][class*='rounded-full']",
      "[class*='bg-token-foreground'][class*='rounded-full']",
      "[class*='bg-token-list-active-selection-foreground'][class*='rounded-full']",
      "[class*='opacity-100'][class*='rounded-full']",
    ],
    (candidate) => !isProgressElement(candidate) && looksLikeUnreadMarker(candidate),
  );
}

function hasUnreadTitleStyle(scope) {
  if (!(scope instanceof HTMLElement)) return false;
  const titleNodes = scope.querySelectorAll(
    [
      ".text-token-foreground\\/40",
      "[class*='text-token-foreground/40']",
      "[class*='group-hover:text-token-foreground']",
    ].join(", "),
  );
  for (const node of titleNodes) {
    if (!(node instanceof HTMLElement)) continue;
    const text = normalizeIndicatorText(node.textContent);
    if (text && text.length > 2) return true;
  }
  return false;
}

function hasMatchingElement(root, selectors, predicate) {
  const matches = [];
  for (const selector of selectors) {
    if (root.matches?.(selector)) matches.push(root);
    matches.push(...root.querySelectorAll(selector));
  }
  return matches.some((candidate) => (
    candidate instanceof HTMLElement || candidate instanceof SVGElement
  ) && (!predicate || predicate(candidate)));
}

function isProgressElement(node) {
  if (!(node instanceof Element)) return false;
  const text = `${node.className || ""} ${node.getAttribute("aria-label") || ""} ${node.getAttribute("data-testid") || ""}`.toLowerCase();
  return /\b(progress|running|loading|spinner|animate-spin)\b/.test(text);
}

function looksLikeUnreadMarker(node) {
  if (!(node instanceof Element)) return false;
  const text = `${node.className || ""} ${node.getAttribute("aria-label") || ""} ${node.getAttribute("data-testid") || ""}`.toLowerCase();
  if (/\bunread\b/.test(text)) return true;
  if (!text.includes("rounded-full")) return false;
  if (!/\b(size|h|w)-\d|h-\[|w-\[/.test(text)) return false;

  const rect = node.getBoundingClientRect?.();
  if (!rect || rect.width === 0 || rect.height === 0) return true;
  return rect.width <= 14 && rect.height <= 14;
}

function normalizeIndicatorText(value) {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

function prunePreviewStorage(state, keepIds) {
  const keep = new Set(keepIds.map(previewKey));
  const all = state.api.storage.all?.() || {};
  for (const key of Object.keys(all)) {
    if (key.startsWith("preview:") && !keep.has(key)) {
      state.api.storage.delete?.(key);
    }
  }
}

function getCurrentChatId() {
  return chatIdFromPathname(window.location.pathname)
    || chatIdFromHref(window.location.href)
    || currentChatIdFromActiveLink();
}

function chatIdFromPathname(pathname) {
  const match = pathname.match(/^\/local\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function chatIdFromHref(href) {
  const match = String(href || "").match(/\/local\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function currentChatIdFromActiveLink() {
  const selectors = [
    'a[aria-current="page"][href*="/local/"]',
    'a[data-state="active"][href*="/local/"]',
    'a[aria-selected="true"][href*="/local/"]',
    'a[href*="/local/"][class*="bg-token-list-hover-background"]',
    'a[href*="/local/"][class*="bg-token-foreground"]',
  ];
  for (const selector of selectors) {
    const anchor = document.querySelector(selector);
    if (anchor instanceof HTMLAnchorElement) {
      const id = chatIdFromHref(anchor.href);
      if (id) return id;
    }
  }
  return null;
}

async function navigateToChat(state, id) {
  const path = `/local/${encodeURIComponent(id)}`;
  try {
    const ok = await state.api.ipc.invoke(IPC_NAVIGATE_CHAT, id);
    if (ok) return;
  } catch (error) {
    state.api.log.warn("[tab-switcher] main navigation failed", error);
  }

  const anchor = document.querySelector(`a[href="${cssEscape(path)}"], a[href^="${cssEscape(path)}?"]`);
  if (anchor instanceof HTMLElement) {
    anchor.click();
    return;
  }
  window.location.assign(path);
}

function previewKey(id) {
  return `preview:v${PREVIEW_STORAGE_VERSION}:${id}`;
}

function waitForNextPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
}

function wrapIndex(index, length) {
  return ((index % length) + length) % length;
}

function formatMetadata(item) {
  const pieces = [];
  if (item.cwdBasename) pieces.push(item.cwdBasename);
  if (item.updatedAt) pieces.push(relativeTime(item.updatedAt));
  return pieces.join(" - ") || "Recent chat";
}

function relativeTime(value) {
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) return "";
  const diff = Date.now() - ms;
  const min = Math.max(0, Math.round(diff / 60000));
  if (min < 1) return "now";
  if (min < 60) return `${min}m ago`;
  const hours = Math.round(min / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function initialsFor(title) {
  const words = String(title || "Chat")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const first = words[0]?.[0] || "C";
  const second = words.length > 1 ? words[1][0] : words[0]?.[1] || "";
  return (first + second).toUpperCase();
}

function cssEscape(value) {
  if (window.CSS?.escape) return window.CSS.escape(value);
  return String(value).replace(/"/g, '\\"');
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

// ------------------------------------------------------------------- main --

const MAIN_GLOBAL_KEY = "__bennettCodexTabSwitcherService";

function startMain(api) {
  const service = createMainService(api);
  globalThis[MAIN_GLOBAL_KEY] = service;

  replaceMainHandler(api, IPC_RECENT_CHATS, () => {
    const active = globalThis[MAIN_GLOBAL_KEY];
    return active?.getRecentChats?.() || [];
  });
  replaceMainHandler(api, IPC_CAPTURE_CHAT_PREVIEW, async (...args) => {
    const active = globalThis[MAIN_GLOBAL_KEY];
    return active?.captureChatPreview?.(...args) || null;
  });
  replaceMainHandler(api, IPC_NAVIGATE_CHAT, (id) => {
    const active = globalThis[MAIN_GLOBAL_KEY];
    return active?.navigateChat?.(id) || false;
  });

  api.log.info("[tab-switcher] main provider active");
}

function replaceMainHandler(api, channel, handler) {
  try {
    const { ipcMain } = require("electron");
    ipcMain.removeHandler(`codexpp:${api.manifest.id}:${channel}`);
  } catch {
    // Older Electron builds may not expose removeHandler; start will then use
    // the runtime's normal handle path.
  }
  api.ipc.handle(channel, handler);
}

function createMainService(api) {
  let cache = { at: 0, value: [] };
  const TTL_MS = 800;

  return {
    getRecentChats() {
      const now = Date.now();
      if (now - cache.at < TTL_MS) return cache.value;
      try {
        cache = { at: now, value: readRecentChats() };
      } catch (error) {
        api.log.warn("[tab-switcher] recent scan failed", error);
        cache = { at: now, value: [] };
      }
      return cache.value;
    },

    async captureChatPreview() {
      try {
        const { event, rect } = normalizeCaptureArgs(arguments);
        return await captureChatPreview(event, rect);
      } catch (error) {
        api.log.warn("[tab-switcher] capture failed", error);
        return null;
      }
    },

    navigateChat(id) {
      try {
        return navigateFocusedWindowToChat(id);
      } catch (error) {
        api.log.warn("[tab-switcher] navigate failed", error);
        return false;
      }
    },
  };
}

function readRecentChats() {
  const fs = require("node:fs");
  const path = require("node:path");
  const os = require("node:os");
  const home = process.env.HOME || os.homedir();
  const indexPath = path.join(home, ".codex", "session_index.jsonl");
  const lines = fs.readFileSync(indexPath, "utf8").split(/\r?\n/);
  const byId = new Map();

  for (const line of lines) {
    if (!line.trim()) continue;
    let row;
    try {
      row = JSON.parse(line);
    } catch {
      continue;
    }
    if (!row || typeof row.id !== "string") continue;
    const updatedAt = typeof row.updated_at === "string" ? row.updated_at : null;
    const prev = byId.get(row.id);
    if (!prev || compareIso(updatedAt, prev.updatedAt) > 0) {
      byId.set(row.id, {
        id: row.id,
        title: typeof row.thread_name === "string" && row.thread_name.trim()
          ? row.thread_name.trim()
          : "Untitled chat",
        updatedAt,
      });
    }
  }

  const sessions = collectSessionFiles(fs, path, home);
  return uniqueByTitle(Array.from(byId.values()))
    .sort((a, b) => compareIso(b.updatedAt, a.updatedAt))
    .slice(0, 5)
    .map((chat) => enrichChat(fs, path, chat, sessions.get(chat.id)));
}

function uniqueByTitle(items) {
  const byTitle = new Map();
  for (const item of items) {
    const key = normalizeTitleKey(item.title);
    const previous = byTitle.get(key);
    if (!previous || compareIso(item.updatedAt, previous.updatedAt) > 0) {
      byTitle.set(key, item);
    }
  }
  return Array.from(byTitle.values());
}

function normalizeTitleKey(title) {
  return String(title || "Untitled chat").trim().replace(/\s+/g, " ").toLowerCase();
}

function enrichChat(fs, path, chat, sessionFile) {
  if (!sessionFile) return { ...chat, cwdBasename: null, isRunning: false };
  const details = readSessionDetails(fs, path, sessionFile);
  return {
    ...chat,
    cwdBasename: details.cwdBasename,
    isRunning: details.isRunning,
  };
}

function collectSessionFiles(fs, path, home) {
  const roots = [
    path.join(home, ".codex", "sessions"),
    path.join(home, ".codex", "archived_sessions"),
  ];
  const out = new Map();
  for (const root of roots) collectJsonlFiles(fs, root, out);
  return out;
}

function collectJsonlFiles(fs, dir, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) {
      collectJsonlFiles(fs, full, out);
    } else if (entry.isFile() && entry.name.endsWith(".jsonl")) {
      const match = entry.name.match(
        /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$/i,
      );
      const id = match?.[1];
      if (id && !out.has(id)) out.set(id, full);
    }
  }
}

function readSessionDetails(fs, path, file) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch {
    return { cwdBasename: null, isRunning: false };
  }

  let cwdBasename = null;
  let isRunning = false;
  const lines = text.split(/\r?\n/);
  for (const line of lines.slice(0, 40)) {
    if (!line.trim()) continue;
    try {
      const row = JSON.parse(line);
      const cwd = row?.payload?.cwd || row?.payload?.session_meta?.cwd;
      if (typeof cwd === "string" && cwd.trim()) {
        cwdBasename = path.basename(cwd);
        break;
      }
    } catch {
      // Ignore malformed session lines.
    }
  }

  for (let i = lines.length - 1, seen = 0; i >= 0 && seen < 80; i -= 1) {
    const line = lines[i];
    if (!line?.trim()) continue;
    seen += 1;
    let row;
    try {
      row = JSON.parse(line);
    } catch {
      continue;
    }
    if (containsInProgress(row)) {
      isRunning = true;
      break;
    }
    if (containsTerminalTurnState(row)) break;
  }
  return { cwdBasename, isRunning };
}

function containsInProgress(value) {
  if (!value || typeof value !== "object") return false;
  if (value.status === "inProgress" || value.status === "in_progress") return true;
  for (const child of Object.values(value)) {
    if (child && typeof child === "object" && containsInProgress(child)) return true;
  }
  return false;
}

function containsTerminalTurnState(value) {
  if (!value || typeof value !== "object") return false;
  const terminal = new Set(["completed", "failed", "cancelled", "canceled"]);
  if (typeof value.status === "string" && terminal.has(value.status)) return true;
  for (const child of Object.values(value)) {
    if (child && typeof child === "object" && containsTerminalTurnState(child)) return true;
  }
  return false;
}

function compareIso(a, b) {
  const at = Date.parse(a || "");
  const bt = Date.parse(b || "");
  const av = Number.isFinite(at) ? at : 0;
  const bv = Number.isFinite(bt) ? bt : 0;
  return av - bv;
}

function normalizeCaptureArgs(argsLike) {
  const args = Array.from(argsLike);
  const first = args[0];
  const second = args[1];
  if (isRect(first)) return { event: null, rect: first };
  if (isRect(second)) return { event: first, rect: second };
  return { event: first && !isRect(first) ? first : null, rect: null };
}

function isRect(value) {
  return (
    value &&
    typeof value === "object" &&
    Number.isFinite(value.x) &&
    Number.isFinite(value.y) &&
    Number.isFinite(value.width) &&
    Number.isFinite(value.height)
  );
}

async function captureChatPreview(event, rect) {
  if (!rect) return null;
  const electron = require("electron");
  const browserWindow = event?.sender
    ? electron.BrowserWindow.fromWebContents(event.sender)
    : getCaptureWindow(electron);
  if (!browserWindow || browserWindow.isDestroyed()) return null;

  const bounds = browserWindow.getContentBounds();
  const safeRect = safeCaptureRect(rect, bounds);
  let image = await browserWindow.capturePage(safeRect);
  if (!image || image.isEmpty()) {
    image = await browserWindow.capturePage(fallbackCaptureRect(bounds));
  }
  if (!image || image.isEmpty()) return null;
  const thumb = image.resize({ width: PREVIEW_WIDTH, height: PREVIEW_HEIGHT, quality: "best" });
  return `data:image/jpeg;base64,${thumb.toJPEG(72).toString("base64")}`;
}

function getCaptureWindow(electron) {
  return electron.BrowserWindow.getFocusedWindow()
    || electron.BrowserWindow.getAllWindows().find((candidate) => (
      !candidate.isDestroyed()
      && candidate.isVisible()
      && candidate.webContents
      && !candidate.webContents.isDestroyed()
    ));
}

function safeCaptureRect(rect, bounds) {
  const safeRect = {
    x: clampInt(rect.x, 0, Math.max(0, bounds.width - 1)),
    y: clampInt(rect.y, 0, Math.max(0, bounds.height - 1)),
    width: clampInt(rect.width, 1, Math.max(1, bounds.width)),
    height: clampInt(rect.height, 1, Math.max(1, bounds.height)),
  };
  safeRect.width = Math.min(safeRect.width, bounds.width - safeRect.x);
  safeRect.height = Math.min(safeRect.height, bounds.height - safeRect.y);
  return safeRect;
}

function fallbackCaptureRect(bounds) {
  const x = Math.min(320, Math.round(bounds.width * 0.22));
  return {
    x,
    y: 0,
    width: Math.max(1, bounds.width - x),
    height: Math.max(1, bounds.height),
  };
}

function navigateFocusedWindowToChat(id) {
  if (typeof id !== "string" || !id.trim()) return false;
  const electron = require("electron");
  const window = electron.BrowserWindow.getFocusedWindow()
    || electron.BrowserWindow.getAllWindows().find((candidate) => !candidate.isDestroyed() && candidate.isVisible());
  if (!window || window.isDestroyed()) return false;
  const path = `/local/${encodeURIComponent(id.trim())}`;
  window.webContents.send("codex_desktop:message-for-view", {
    type: "navigate-to-route",
    path,
  });
  return true;
}

function clampInt(value, min, max) {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}
