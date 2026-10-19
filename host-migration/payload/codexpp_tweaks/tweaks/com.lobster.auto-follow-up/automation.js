(function() {
  const sessionInteractions = {};
  const sessionFingerprints = {};
  const recentPromptFingerprints = new Map();
  const pendingPromptKeys = new Map();
  const submittedPromptKeys = new Map();
  const RECENT_PROMPT_TTL_MS = 30 * 60 * 1000;
  const SUBMITTED_PROMPT_TTL_MS = 24 * 60 * 60 * 1000;
  const MAX_SUBMITTED_PROMPT_KEYS = 200;
  const SUBMITTED_PROMPT_STORAGE_KEY = "autoFollowupSubmittedPromptKeys.v1";
  let submittedPromptKeysLoaded = false;
  let autoSendTimeout = null;
  let activePendingPromptKey = null;
  let activePendingPromptKeys = new Set();

  const STABLE_SESSION_KEY_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
  const INVALID_SESSION_KEY_RE = /^(default-session|active-tab-|first-msg-|未识别当前会话)$/i;

  function normalizeSessionKey(value) {
    const raw = String(value || "").trim().replace(/^local:/i, "");
    if (!raw || raw.length > 128 || raw.startsWith("home:") || /\s/.test(raw) || INVALID_SESSION_KEY_RE.test(raw)) return null;
    return raw;
  }

  function getReactFiber(node) {
    try {
      const key = Object.keys(node).find((name) => name.startsWith("__reactFiber$") || name.startsWith("__reactInternalInstance"));
      return key ? node[key] : null;
    } catch (error) {
      return null;
    }
  }

  function findSessionKeyInValue(value, seen, depth = 0) {
    if (depth > 5 || value == null) return null;
    if (typeof value === "string") return value.match(STABLE_SESSION_KEY_RE)?.[0] || null;
    if (typeof value !== "object") return null;
    if (seen.has(value)) return null;
    seen.add(value);
    const entries = Array.isArray(value) ? value.entries() : Object.entries(value);
    for (const [key, child] of entries) {
      const keyText = String(key).toLowerCase();
      if (/thread|conversation|session|chat/.test(keyText) && typeof child === "string") {
        const found = child.match(STABLE_SESSION_KEY_RE)?.[0] || null;
        if (found) return found;
      }
    }
    for (const [, child] of entries) {
      const found = findSessionKeyInValue(child, seen, depth + 1);
      if (found) return found;
    }
    return null;
  }

  function findSessionKeyFromNode(node) {
    if (!node || node.nodeType !== 1) return null;
    let fiber = getReactFiber(node);
    const seen = new Set();
    while (fiber && !seen.has(fiber)) {
      seen.add(fiber);
      const found = findSessionKeyInValue(fiber.memoizedProps, new Set()) ||
        findSessionKeyInValue(fiber.pendingProps, new Set()) ||
        findSessionKeyInValue(fiber.memoizedState, new Set());
      if (found) return found;
      fiber = fiber.return;
    }
    return null;
  }

  function findStableSessionKey() {
    try {
      const locationText = `${window.location.pathname || ""} ${window.location.hash || ""} ${window.location.search || ""}`;
      const uuid = locationText.match(STABLE_SESSION_KEY_RE)?.[0];
      if (uuid) return uuid;
      const href = window.location.href || "";
      const urlMatch = href.match(/\/chat\/([^\/?#]+)/) || href.match(/\/c\/([^\/?#]+)/) || href.match(/\/conversation\/([^\/?#]+)/);
      const fromUrl = normalizeSessionKey(urlMatch?.[1] || "");
      if (fromUrl) return fromUrl;
    } catch (error) {}

    try {
      const activeRow = document.querySelector('[data-app-action-sidebar-thread-active="true"][data-app-action-sidebar-thread-id], [data-app-action-sidebar-thread-row][aria-current="page"][data-app-action-sidebar-thread-id]');
      const fromSidebar = normalizeSessionKey(activeRow?.getAttribute("data-app-action-sidebar-thread-id") || "");
      if (fromSidebar) return fromSidebar;
    } catch (error) {}

    try {
      const candidates = [
        document.querySelector(".composer-footer"),
        document.querySelector("textarea"),
        document.querySelector("[contenteditable='true']"),
        document.querySelector(".ProseMirror"),
        document.querySelector('[data-app-action-sidebar-thread-active="true"][data-app-action-sidebar-thread-id]'),
      ].filter((node) => node instanceof HTMLElement);
      for (const node of candidates) {
        const fromFiber = findSessionKeyFromNode(node);
        if (fromFiber) return fromFiber;
      }
    } catch (error) {}

    return null;
  }

  function getSessionKey() {
    return findStableSessionKey();
  }

  function getSessionFingerprints(key) {
    if (!key) return null;
    if (!sessionFingerprints[key]) {
      sessionFingerprints[key] = new Set();
    }
    return sessionFingerprints[key];
  }

  function cleanPromptText(text) {
    return String(text || "")
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^P[0-3]\s*:?\s*/i, "")
      .replace(/^[:：]\s*/, "")
      .trim();
  }

  function normalizePromptText(text) {
    const cleaned = cleanPromptText(text);
    const normalized = typeof cleaned.normalize === "function" ? cleaned.normalize("NFKC") : cleaned;
    return normalized.replace(/\s+/g, " ").trim();
  }

  function loadSubmittedPromptKeys() {
    if (submittedPromptKeysLoaded) return;
    submittedPromptKeysLoaded = true;
    try {
      const raw = localStorage.getItem(SUBMITTED_PROMPT_STORAGE_KEY);
      const entries = JSON.parse(raw || "[]");
      if (!Array.isArray(entries)) return;
      for (const [promptKey, timestamp] of entries) {
        const key = String(promptKey || "");
        const time = Number(timestamp || 0);
        if (key && Number.isFinite(time)) submittedPromptKeys.set(key, time);
      }
    } catch (error) {}
  }

  function persistSubmittedPromptKeys() {
    try {
      localStorage.setItem(SUBMITTED_PROMPT_STORAGE_KEY, JSON.stringify([...submittedPromptKeys.entries()]));
    } catch (error) {}
  }

  function pruneRecentPromptFingerprints(now = Date.now()) {
    loadSubmittedPromptKeys();
    let submittedChanged = false;
    for (const [fingerprint, timestamp] of recentPromptFingerprints) {
      if (now - timestamp > RECENT_PROMPT_TTL_MS) {
        recentPromptFingerprints.delete(fingerprint);
      }
    }
    for (const [promptKey, timestamp] of pendingPromptKeys) {
      if (now - timestamp > RECENT_PROMPT_TTL_MS) {
        pendingPromptKeys.delete(promptKey);
      }
    }
    for (const [promptKey, timestamp] of submittedPromptKeys) {
      if (now - timestamp > SUBMITTED_PROMPT_TTL_MS) {
        submittedPromptKeys.delete(promptKey);
        submittedChanged = true;
      }
    }
    while (submittedPromptKeys.size > MAX_SUBMITTED_PROMPT_KEYS) {
      const firstKey = submittedPromptKeys.keys().next().value;
      if (!firstKey) break;
      submittedPromptKeys.delete(firstKey);
      submittedChanged = true;
    }
    if (submittedChanged) persistSubmittedPromptKeys();
  }

  function hasRecentPromptFingerprint(fingerprint) {
    pruneRecentPromptFingerprints();
    return recentPromptFingerprints.has(fingerprint);
  }

  function markRecentPromptFingerprint(fingerprint) {
    pruneRecentPromptFingerprints();
    recentPromptFingerprints.set(fingerprint, Date.now());
  }

  function clearRecentPromptFingerprints() {
    recentPromptFingerprints.clear();
    pendingPromptKeys.clear();
  }

  function normalizePromptKey(text) {
    return normalizePromptText(text).toLowerCase();
  }

  function hasPendingPromptKey(promptKey) {
    pruneRecentPromptFingerprints();
    return pendingPromptKeys.has(promptKey);
  }

  function markPendingPromptKey(promptKey) {
    pruneRecentPromptFingerprints();
    pendingPromptKeys.set(promptKey, Date.now());
  }

  function clearPendingPromptKey(promptKey = null) {
    if (!promptKey) {
      if (activePendingPromptKey) pendingPromptKeys.delete(activePendingPromptKey);
      for (const activeKey of activePendingPromptKeys) pendingPromptKeys.delete(activeKey);
      activePendingPromptKey = null;
      activePendingPromptKeys.clear();
      return;
    }
    pendingPromptKeys.delete(promptKey);
    activePendingPromptKeys.delete(promptKey);
    if (promptKey === activePendingPromptKey) {
      activePendingPromptKey = activePendingPromptKeys.values().next().value || null;
    }
  }

  function hasSubmittedPromptKey(promptKey) {
    pruneRecentPromptFingerprints();
    return submittedPromptKeys.has(promptKey);
  }

  function markSubmittedPromptKey(promptKey) {
    pruneRecentPromptFingerprints();
    submittedPromptKeys.set(promptKey, Date.now());
    while (submittedPromptKeys.size > MAX_SUBMITTED_PROMPT_KEYS) {
      const firstKey = submittedPromptKeys.keys().next().value;
      if (!firstKey) break;
      submittedPromptKeys.delete(firstKey);
    }
    persistSubmittedPromptKeys();
  }

  function allSelectionPromptsAlreadySubmitted(items) {
    if (!Array.isArray(items) || items.length === 0) return false;
    return items.every((item) => {
      const promptKey = normalizePromptKey(item?.prompt || "");
      return promptKey && (hasSubmittedPromptKey(promptKey) || hasExistingUserPromptKey(promptKey));
    });
  }

  function hasExistingUserPromptKey(promptKey) {
    if (!promptKey) return false;
    const nodes = [];
    try {
      nodes.push(...document.querySelectorAll("[data-message-author-role='user'], [data-message-role='user']"));
      for (const node of document.querySelectorAll("div")) {
        const className = String(node.className || "");
        if (className.includes("bg-token-foreground/5") && className.includes("break-words")) {
          nodes.push(node);
        }
      }
    } catch (error) {}

    for (const node of nodes) {
      if (!(node instanceof HTMLElement)) continue;
      if (node.closest?.(".soren-radar-panel")) continue;
      const key = normalizePromptKey(node.textContent || "");
      if (key && key === promptKey) return true;
    }
    return false;
  }



  // 计算文本的 SHA-256 指纹（返回 hex 字符串）
  async function computeFingerprint(text) {
    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(text);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      // SubtleCrypto 不可用时降级为简单字符串哈希
      let hash = 0;
      for (let i = 0; i < text.length; i++) {
        const char = text.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash |= 0;
      }
      return "fallback-" + Math.abs(hash).toString(16);
    }
  }

  function visible(node) {
    if (!node) return false;
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }

  function findComposerInput(scope = document) {
    const root = scope instanceof Element ? scope : document;
    const nodes = Array.from(root.querySelectorAll?.([
      "textarea",
      "input[type='text']",
      "[contenteditable='true']",
      "[role='textbox']",
    ].join(",")) || []);
    const visibleNodes = nodes.filter((node) => node instanceof HTMLElement && visible(node));
    return visibleNodes.find((node) => {
      const label = String(node.getAttribute("aria-label") || "" + " " + node.getAttribute("placeholder") || "").toLowerCase();
      return label.includes("message") ||
        label.includes("prompt") ||
        label.includes("ask") ||
        node.closest("[data-testid*='composer' i]") ||
        node.closest("[class*='composer' i]") ||
        node.tagName === "TEXTAREA";
    }) || visibleNodes[0] || null;
  }

  function findComposerSendButton() {
    const buttons = Array.from(document.querySelectorAll("button"))
      .filter((node) => node instanceof HTMLElement && visible(node));
    return buttons.find((button) =>
      button.closest(".composer-footer") &&
      String(button.className || "").includes("bg-token-foreground")
    ) || buttons
      .filter((button) => button.closest(".composer-footer"))
      .sort((a, b) => b.getBoundingClientRect().x - a.getBoundingClientRect().x)[0] || null;
  }

  const activateSession = () => {
    const key = getSessionKey();
    if (!key) return;
    if (!sessionInteractions[key]) {
      sessionInteractions[key] = true;
      console.log(`[自动连击v2] 检测到活跃交互，成功激活会话 [${key}] 的自动发送闸`);
    }
  };

  // 监听用户手动发送消息（composer submit），清空指纹集合以开启新轮次
  function monitorComposerSubmit() {
    document.addEventListener("click", (e) => {
      if (!e.isTrusted) return; // 跳过程序化 .click() 触发，只响应人类真实点击
      const btn = e.target?.closest?.("button");
      if (!btn) return;
      const isInComposer = btn.closest(".composer-footer");
      const isSendLike = String(btn.className || "").includes("bg-token-foreground") ||
        btn.getAttribute("aria-label")?.toLowerCase().includes("send");
      if (isInComposer && isSendLike) {
        const key = getSessionKey();
        if (!key) return;
        getSessionFingerprints(key).clear();
        clearRecentPromptFingerprints();
        console.log(`[自动连击v2] 检测到用户手动提交，已清空会话 [${key}] 的指纹集合`);
      }
    }, { capture: true, passive: true });

    document.addEventListener("keydown", (e) => {
      if (!e.isTrusted) return; // 跳过程序化键盘事件
      if (e.key === "Enter" && !e.shiftKey) {
        const textarea = e.target?.closest?.("textarea");
        if (textarea && textarea.closest(".composer-footer, [class*='composer' i]")) {
          const key = getSessionKey();
          if (!key) return;
          getSessionFingerprints(key).clear();
          clearRecentPromptFingerprints();
          console.log(`[自动连击v2] 检测到用户 Enter 提交，已清空会话 [${key}] 的指纹集合`);
        }
      }
    }, { capture: true, passive: true });
  }

  // 绑定全局交互监听
  document.addEventListener("input", activateSession, { capture: true, passive: true });
  document.addEventListener("keydown", activateSession, { capture: true, passive: true });
  document.addEventListener("focusin", activateSession, { capture: true, passive: true });
  monitorComposerSubmit();

  // 尝试从 follow-up 面板附近的隐藏 JSON 中提取 priority 和 task_complete 信息
  function cleanPanelPrompt(text) {
    return cleanPromptText(text);
  }

  function promptFromPanelButton(btn) {
    const promptNode = btn.querySelector?.(".soren-radar-text");
    return cleanPanelPrompt(promptNode?.textContent || btn.textContent || "");
  }

  function normalizePriority(value) {
    const priority = String(value || "P1").trim().toUpperCase();
    return /^(P0|P1|P2|P3)$/.test(priority) ? priority : "P1";
  }

  const AUTO_SUBMIT_PRIORITY_RANK = { P0: 0, P1: 1 };

  function isTruthy(value) {
    return value === true || value === 1 || String(value || "").trim().toLowerCase() === "true";
  }

  function parsePayloadText(text) {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start < 0 || end <= start) return null;
    try {
      return JSON.parse(text.slice(start, end + 1));
    } catch (e) {
      return null;
    }
  }

  function metaFromPayloadData(data) {
    const isFollowupPayload = data?.codex_follow_up_candidate === true || data?.codex_follow_up === true;
    if (!isFollowupPayload) return null;

    const rawItems = Array.isArray(data.items) ? data.items : [];
    return {
      items: rawItems
        .map(item => ({
          prompt: cleanPanelPrompt(item?.prompt || item?.query || item?.label || item?.text || item?.title || ""),
          priority: normalizePriority(item?.priority),
          isCurrentTaskDebt: isTruthy(item?.is_current_task_debt),
          confidence: Number.isFinite(Number(item?.confidence)) ? Number(item.confidence) : null
        }))
        .filter(item => item.prompt && !item.isCurrentTaskDebt),
      taskComplete: data.task_complete === true,
      createdAtMs: Number.isFinite(Number(data.created_at_ms)) ? Number(data.created_at_ms) : null,
      source: "payload"
    };
  }

  function itemFromSignatureEntry(entry) {
    const raw = String(entry || "").trim();
    const match = raw.match(/^(P0|P1|P2|P3)\s*:\s*(.+)$/i);
    if (match) {
      return {
        prompt: cleanPanelPrompt(match[2]),
        priority: normalizePriority(match[1])
      };
    }
    const text = cleanPanelPrompt(raw);
    return text ? { prompt: text, priority: "P3" } : null;
  }

  function extractPayloadMeta(panel) {
    const result = { items: [], taskComplete: false, source: "none" };

    const datasetPayload = panel?.dataset?.followupMeta;
    if (datasetPayload) {
      const meta = metaFromPayloadData(parsePayloadText(datasetPayload));
      if (meta) return meta;
    }

    // 向上查找被隐藏的原始 JSON pre 块
    let sibling = panel.previousElementSibling;
    for (let i = 0; i < 5 && sibling; i++) {
      const text = sibling.textContent?.trim() || "";
      if (text.includes("codex_follow_up")) {
        const meta = metaFromPayloadData(parsePayloadText(text));
        if (meta) return meta;
      }
      sibling = sibling.previousElementSibling;
    }

    try {
      const signature = JSON.parse(panel.dataset.signature || "{}");
      if (Array.isArray(signature.items) && signature.items.length > 0) {
        result.items = signature.items
          .map(itemFromSignatureEntry)
          .filter(Boolean);
        result.source = "signature";
        if (result.items.length > 0) return result;
      }
    } catch (e) { /* ignore signature parse errors */ }

    // 如果找不到隐藏 JSON，从面板按钮文本推断（降级方案，无优先级信息）
    const buttons = Array.from(panel.querySelectorAll(".soren-radar-row-clickable"));
    result.items = buttons.map(btn => ({
      prompt: promptFromPanelButton(btn),
      priority: "P3" // 降级信息只展示，不自动提交
    })).filter(item => item.prompt);
    result.source = result.items.length > 0 ? "buttons" : "none";
    return result;
  }

  function selectAutoSubmitPrompts(meta) {
    if (meta.source !== "payload") {
      return { items: [], prompt: "", reason: "unstructured_payload", priority: "", candidateCount: 0 };
    }
    if (meta.taskComplete !== true) {
      return { items: [], prompt: "", reason: "task_incomplete", priority: "", candidateCount: 0 };
    }

    const sortedItems = meta.items
      .map((item, index) => ({ ...item, index }))
      .filter(item => item.priority === "P0" || item.priority === "P1")
      .sort((a, b) => (AUTO_SUBMIT_PRIORITY_RANK[a.priority] - AUTO_SUBMIT_PRIORITY_RANK[b.priority]) || (a.index - b.index));

    const seenPromptKeys = new Set();
    const items = [];
    for (const { index, ...item } of sortedItems) {
      const promptKey = normalizePromptKey(item.prompt);
      if (!promptKey || seenPromptKeys.has(promptKey)) continue;
      seenPromptKeys.add(promptKey);
      items.push(item);
    }

    const first = items[0];
    return {
      items,
      prompt: first?.prompt || "",
      reason: first ? "p0_p1_queue" : "no_p0_or_p1",
      priority: first?.priority || "",
      candidateCount: items.length
    };
  }

  function selectAutoSubmitPrompt(meta) {
    const selection = selectAutoSubmitPrompts(meta);
    const first = selection.items[0];
    return {
      prompt: first?.prompt || "",
      reason: first ? first.priority.toLowerCase() : selection.reason,
      priority: first?.priority || "",
      candidateCount: selection.items.length
    };
  }

  function autoSubmitBudgetDecision(selection, budget) {
    if (!selection?.prompt) {
      return { allowed: true, reason: "no_selection" };
    }
    if (!budget || budget.known !== true) {
      return { allowed: true, reason: "budget_unknown" };
    }
    if (selection.priority === "P1" && budget.safeForP1 === false) {
      return { allowed: false, reason: "p1_budget_soft_limit", budget };
    }
    if (selection.priority === "P0" && budget.safeForP0 === false) {
      return { allowed: false, reason: "p0_budget_hard_limit", budget };
    }
    return { allowed: true, reason: "budget_ok", budget };
  }

  function filterAutoSubmitQueueByBudget(items, budget) {
    if (!Array.isArray(items) || items.length === 0) {
      return { items: [], reason: "empty_queue", blockedCount: 0 };
    }
    if (budget?.known === true && budget.safeForP0 === false) {
      return { items: [], reason: "p0_budget_hard_limit", blockedCount: items.length };
    }

    const allowed = [];
    let blockedReason = "";
    for (const item of items) {
      const decision = autoSubmitBudgetDecision(item, budget);
      if (decision.allowed) {
        allowed.push(item);
      } else {
        blockedReason = blockedReason || decision.reason;
      }
    }
    return {
      items: allowed,
      reason: allowed.length > 0 ? "budget_ok" : (blockedReason || "budget_blocked"),
      blockedCount: items.length - allowed.length
    };
  }

  function budgetPausePanelText(reason) {
    return reason === "p1_budget_soft_limit" ? "预算保护暂停(P1)" : "预算保护暂停(P0)";
  }

  async function readAutoSubmitBudget(api, sessionKey) {
    try {
      if (typeof api?.ipc?.invoke !== "function") {
        return { known: false, reason: "ipc_unavailable" };
      }
      return await api.ipc.invoke("auto-follow-up-session-budget", { sessionKey });
    } catch (error) {
      return { known: false, reason: "budget_probe_failed", message: String(error?.message || error) };
    }
  }

  // 核心触发发送逻辑
  async function triggerSubmit(api, promptText) {
    const textarea = findComposerInput();
    if (!textarea) {
      api.log.error("[自动连击v2] 未能找到输入框");
      return false;
    }

    // 写入 prompt 文本
    if (textarea.tagName === "TEXTAREA") {
      textarea.value = promptText;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      textarea.textContent = promptText;
      textarea.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: promptText }));
    }
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
    textarea.focus();
    await new Promise(r => setTimeout(r, 300));

    const sendBtn = findComposerSendButton();
    if (sendBtn && !sendBtn.disabled) {
      api.log.info("[自动连击v2] 触发发送按钮点击");
      sendBtn.click();
      return true;
    }

    // 降级：Enter 键盘模拟
    api.log.warn("[自动连击v2] 未能定位到发送按钮，降级采用 Enter 键盘模拟");
    textarea.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true
    }));
    textarea.dispatchEvent(new KeyboardEvent("keyup", {
      key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true
    }));
    return true;
  }

  globalThis.automation = {
    __test: {
      extractPayloadMeta,
      metaFromPayloadData,
      selectAutoSubmitPrompts,
      selectAutoSubmitPrompt,
      allSelectionPromptsAlreadySubmitted,
      autoSubmitBudgetDecision,
      filterAutoSubmitQueueByBudget,
      budgetPausePanelText
    },

    run({ api, isAutoEnabled, maxDepth, debounceMs, currentDepth, updateDepth, updateFloatingPanel, isAiGenerating, sessionKey }) {
      const key = sessionKey || getSessionKey();
      if (!key) {
        return true;
      }
      // 1. 如果 AI 正在生成中，标记为当前 session 活跃，并取消可能存在的倒计时
      if (isAiGenerating()) {
        if (!sessionInteractions[key]) {
          sessionInteractions[key] = true;
          api.log.info(`[自动连击v2] 检测到 AI 处于生成中状态，成功激活会话 [${key}] 的自动发送闸`);
        }
        if (autoSendTimeout) {
          clearTimeout(autoSendTimeout);
          autoSendTimeout = null;
          clearPendingPromptKey();
          updateFloatingPanel();
        }
        return true;
      }

      // 2. 扫描 co.Arconte112.followup 渲染出的面板
      const panels = Array.from(document.querySelectorAll(".soren-radar-panel"));
      if (panels.length === 0) {
        return true;
      }

      // 获取最新的面板
      const latestPanel = panels[panels.length - 1];

      // 如果这个最新的面板还没有加载完成，跳过
      const isPending = latestPanel.querySelector(".soren-radar-text-pending");
      if (isPending) {
        return true;
      }

      // 如果最新面板已经处理过（老逻辑 dataset 标记保留作为第一道快速跳过）
      if (latestPanel.dataset.autoFollowupTriggered === "true") {
        return true;
      }

      // 3. 提取 payload 元数据（优先级 + 完成标记）
      const meta = extractPayloadMeta(latestPanel);

      // 4. 执行自动连击核心逻辑
      if (!isAutoEnabled) {
        latestPanel.dataset.autoFollowupTriggered = "true";
        return true;
      }

      if (!sessionInteractions[key]) {
        sessionInteractions[key] = true;
        api.log.info(`[自动连击v2] 当前会话 [${key}] 自动提交已开启，按轮次限制激活自动发送闸`);
      }

      const selection = selectAutoSubmitPrompts(meta);
      if (selection.items.length === 0) {
        const reasonText = {
          unstructured_payload: "未拿到结构化 Follow-up payload，停止自动提交",
          task_incomplete: "task_complete 不是 true，停止自动提交",
          no_p0_or_p1: "没有 P0/P1 候选，停止自动提交"
        }[selection.reason] || "未满足自动提交条件，停止自动提交";
        api.log.info(`[自动连击v2] ${reasonText}`);
        latestPanel.dataset.autoFollowupTriggered = "true";
        sessionInteractions[key] = false;
        clearRecentPromptFingerprints();
        updateDepth(0);
        updateFloatingPanel();
        return true;
      }
      if (allSelectionPromptsAlreadySubmitted(selection.items)) {
        api.log.info("[自动连击v2] 当前 Follow-up 候选已在会话中提交过，判定为历史面板重扫，保留自动提交轮次");
        latestPanel.dataset.autoFollowupTriggered = "true";
        sessionInteractions[key] = false;
        clearRecentPromptFingerprints();
        updateFloatingPanel();
        return true;
      }

      // 安全阀：绝对轮次上限
      if (currentDepth >= maxDepth) {
        api.log.warn(`[自动连击v2] 已达到绝对安全阀上限: ${maxDepth} 轮，强制停止`);
        latestPanel.dataset.autoFollowupTriggered = "true";
        sessionInteractions[key] = false;
        clearRecentPromptFingerprints();
        updateDepth(0);
        updateFloatingPanel();
        return true;
      }

      const remainingDepth = Math.max(0, maxDepth - currentDepth);
      const depthLimitedItems = selection.items.slice(0, remainingDepth);
      if (depthLimitedItems.length < selection.items.length) {
        api.log.warn(`[自动连击v2] P0/P1 候选 ${selection.items.length} 条，剩余深度只允许提交 ${depthLimitedItems.length} 条`);
      }
      const prioritySummary = depthLimitedItems.map(item => item.priority).join(",");
      api.log.info(`[自动连击v2] 检测到 ${depthLimitedItems.length} 条 P0/P1 候选，准备逐条入队: ${prioritySummary}`);

      // 标记为已处理（防止 DOM 重建前的重复扫描）
      latestPanel.dataset.autoFollowupTriggered = "true";

      // 内容指纹去重：异步计算哈希后决定是否触发
      (async () => {
        let promptQueue = [];
        try {
          const budget = await readAutoSubmitBudget(api, key);
          const budgetDecision = filterAutoSubmitQueueByBudget(depthLimitedItems, budget);
          if (budgetDecision.items.length === 0) {
            const bytes = Number.isFinite(Number(budget?.bytes)) ? Number(budget.bytes) : 0;
            const maxLineChars = Number.isFinite(Number(budget?.maxLineChars)) ? Number(budget.maxLineChars) : 0;
            const reasonText = budgetDecision.reason === "p1_budget_soft_limit"
              ? `P1 会话预算达到 90% 软阈值，停止自动提交 (bytes=${bytes}, max_line_chars=${maxLineChars})`
              : `P0 会话预算达到硬阈值，停止自动提交 (bytes=${bytes}, max_line_chars=${maxLineChars})`;
            api.log.warn(`[自动连击v2] ${reasonText}`);
            latestPanel.dataset.autoFollowupTriggered = "true";
            sessionInteractions[key] = false;
            clearRecentPromptFingerprints();
            updateDepth(0);
            updateFloatingPanel(budgetPausePanelText(budgetDecision.reason));
            return;
          }
          if (budgetDecision.blockedCount > 0) {
            api.log.warn(`[自动连击v2] 预算保护跳过 ${budgetDecision.blockedCount} 条候选，继续提交 ${budgetDecision.items.length} 条`);
          }

          const fingerprints = getSessionFingerprints(key);
          if (!fingerprints) {
            return;
          }

          for (const item of budgetDecision.items) {
            const promptKey = normalizePromptKey(item.prompt);
            if (promptKey && hasExistingUserPromptKey(promptKey)) {
              markSubmittedPromptKey(promptKey);
              api.log.info(`[自动连击v2] 会话中已存在同文案用户消息，跳过重复自动提交 (key: ${promptKey.slice(0, 48)}...)`);
              continue;
            }
            if (promptKey && hasSubmittedPromptKey(promptKey)) {
              api.log.info(`[自动连击v2] 已提交 prompt key 命中，跳过跨会话重复触发 (key: ${promptKey.slice(0, 48)}...)`);
              continue;
            }
            if (promptKey && hasPendingPromptKey(promptKey)) {
              api.log.info(`[自动连击v2] 内容指纹命中去重集合，跳过重复触发 (key: ${promptKey.slice(0, 48)}...)`);
              continue;
            }

            const fingerprint = await computeFingerprint(item.prompt);
            if (fingerprints.has(fingerprint) || hasRecentPromptFingerprint(fingerprint)) {
              api.log.info(`[自动连击v2] 内容指纹命中去重集合，跳过重复触发 (hash: ${fingerprint.slice(0, 12)}...)`);
              continue;
            }
            fingerprints.add(fingerprint);
            markRecentPromptFingerprint(fingerprint);
            if (promptKey) {
              markPendingPromptKey(promptKey);
              activePendingPromptKey = promptKey;
              activePendingPromptKeys.add(promptKey);
            }
            promptQueue.push({ ...item, promptKey });
          }

          if (promptQueue.length === 0) {
            api.log.info("[自动连击v2] P0/P1 候选均已被去重保护跳过");
            sessionInteractions[key] = false;
            clearRecentPromptFingerprints();
            updateDepth(0);
            updateFloatingPanel();
            return;
          }
        } catch (error) {
          for (const item of promptQueue) clearPendingPromptKey(item.promptKey);
          throw error;
        }

        // 开始倒计时
        let countdown = Math.ceil(debounceMs / 1000);
        const tick = () => {
          if (countdown > 0) {
            const label = promptQueue.length > 1
              ? `逐条提交 ${promptQueue.length} 个 P0/P1 候选... (${countdown}s)`
              : `${promptQueue[0].priority} 自动运行... (${countdown}s)`;
            updateFloatingPanel(label);
            countdown--;
            autoSendTimeout = setTimeout(tick, 1000);
          } else {
            autoSendTimeout = null;
            updateFloatingPanel(`正在逐条入队 0/${promptQueue.length}`);

            api.log.info(`[自动连击v2] 倒计时结束，开始逐条提交 ${promptQueue.length} 个候选`);
            (async () => {
              let submittedCount = 0;
              for (const item of promptQueue) {
                updateFloatingPanel(`正在逐条入队 ${submittedCount + 1}/${promptQueue.length} · ${item.priority}`);
                const submitted = await triggerSubmit(api, item.prompt);
                if (submitted) {
                  submittedCount++;
                  if (item.promptKey) markSubmittedPromptKey(item.promptKey);
                  updateDepth(currentDepth + submittedCount);
                }
                if (submittedCount < promptQueue.length) {
                  await new Promise(resolve => setTimeout(resolve, 800));
                }
              }
              return submittedCount;
            })()
              .then((submittedCount) => {
                api.log.info(`[自动连击v2] 已逐条提交 ${submittedCount}/${promptQueue.length} 个 Follow-up 候选`);
              })
              .catch((error) => {
                api.log.error("[自动连击v2] 自动提交失败", error);
              })
              .finally(() => {
                for (const item of promptQueue) clearPendingPromptKey(item.promptKey);
                updateFloatingPanel();
              });
          }
        };

        api.log.info(`[自动连击v2] 触发 ${countdown} 秒倒计时`);
        tick();
      })();

      return true;
    },

    cancelCountdown() {
      if (autoSendTimeout) {
        clearTimeout(autoSendTimeout);
        autoSendTimeout = null;
        clearPendingPromptKey();
        return true;
      }
      return false;
    },

    isCountingDown() {
      return autoSendTimeout !== null;
    },

    cleanup() {
      document.removeEventListener("input", activateSession, { capture: true });
      document.removeEventListener("keydown", activateSession, { capture: true });
      document.removeEventListener("focusin", activateSession, { capture: true });
      if (autoSendTimeout) {
        clearTimeout(autoSendTimeout);
        autoSendTimeout = null;
      }
      activePendingPromptKey = null;
      activePendingPromptKeys.clear();
      for (const k in sessionInteractions) {
        sessionInteractions[k] = false;
      }
      for (const k in sessionFingerprints) {
        sessionFingerprints[k].clear();
      }
      clearRecentPromptFingerprints();
    }
  };
})();
