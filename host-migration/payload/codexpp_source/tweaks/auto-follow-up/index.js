module.exports = {
  start(api) {
    const isMain = api.process === "main" || (typeof process !== "undefined" && process.type === "browser");
    if (isMain) {
      try {
        const fs = require("fs");
        const path = require("path");
        const SESSION_BUDGET_CACHE_MS = 2000;
        const SESSION_BUDGET_MAX_FILE_BYTES = 2000000;
        const SESSION_BUDGET_MAX_LINE_CHARS = 120000;
        const SESSION_BUDGET_SOFT_RATIO = 0.9;
        const sessionBudgetCache = new Map();

        function normalizeBudgetSessionKey(value) {
          const raw = String(value || "").trim().replace(/^local:/i, "");
          return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(raw) ? raw : "";
        }

        function getCodexPlusPlusHome() {
          return process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";
        }

        function findSessionFile(root, sessionKey) {
          const searchRoots = [path.join(root, "sessions"), path.join(root, "archived_sessions")];
          const seen = new Set();
          const walk = (dir) => {
            if (!dir || seen.has(dir)) return "";
            seen.add(dir);
            let entries = [];
            try {
              entries = fs.readdirSync(dir, { withFileTypes: true });
            } catch (error) {
              return "";
            }
            for (const entry of entries) {
              const fullPath = path.join(dir, entry.name);
              if (entry.isFile() && entry.name.endsWith(".jsonl") && entry.name.includes(sessionKey)) {
                return fullPath;
              }
            }
            for (const entry of entries) {
              if (!entry.isDirectory()) continue;
              const found = walk(path.join(dir, entry.name));
              if (found) return found;
            }
            return "";
          };
          for (const searchRoot of searchRoots) {
            const found = walk(searchRoot);
            if (found) return found;
          }
          return "";
        }

        function getMaxLineChars(filePath) {
          const text = fs.readFileSync(filePath, "utf8");
          let max = 0;
          let current = 0;
          for (const char of text) {
            if (char === "\n") {
              if (current > max) max = current;
              current = 0;
            } else if (char !== "\r") {
              current++;
            }
          }
          return Math.max(max, current);
        }

        function getSessionBudget(sessionKeyValue) {
          const sessionKey = normalizeBudgetSessionKey(sessionKeyValue?.sessionKey || sessionKeyValue);
          const base = {
            schema: "codexpp_auto_followup_session_budget.v1",
            sessionKey,
            known: false,
            maxFileBytes: SESSION_BUDGET_MAX_FILE_BYTES,
            maxLineChars: SESSION_BUDGET_MAX_LINE_CHARS,
            softFileBytes: Math.floor(SESSION_BUDGET_MAX_FILE_BYTES * SESSION_BUDGET_SOFT_RATIO),
            softLineChars: Math.floor(SESSION_BUDGET_MAX_LINE_CHARS * SESSION_BUDGET_SOFT_RATIO),
          };
          if (!sessionKey) return { ...base, reason: "invalid_session_key" };
          const cached = sessionBudgetCache.get(sessionKey);
          if (cached && Date.now() - cached.timestamp < SESSION_BUDGET_CACHE_MS) {
            return cached.value;
          }
          try {
            const filePath = findSessionFile(getCodexPlusPlusHome(), sessionKey);
            if (!filePath) {
              const value = { ...base, reason: "session_file_not_found" };
              sessionBudgetCache.set(sessionKey, { timestamp: Date.now(), value });
              return value;
            }
            const stats = fs.statSync(filePath);
            const maxLineChars = getMaxLineChars(filePath);
            const softBreached = stats.size >= base.softFileBytes || maxLineChars >= base.softLineChars;
            const hardBreached = stats.size >= base.maxFileBytes || maxLineChars >= base.maxLineChars;
            const value = {
              ...base,
              known: true,
              reason: "ok",
              path: filePath,
              bytes: stats.size,
              maxLineChars,
              softBreached,
              hardBreached,
              safeForP1: !softBreached,
              safeForP0: !hardBreached,
            };
            sessionBudgetCache.set(sessionKey, { timestamp: Date.now(), value });
            return value;
          } catch (error) {
            const value = { ...base, reason: "budget_probe_failed", message: String(error?.message || error) };
            sessionBudgetCache.set(sessionKey, { timestamp: Date.now(), value });
            return value;
          }
        }

        if (api.ipc && typeof api.ipc.handle === "function") {
          api.ipc.handle("read-automation", () => {
            const filePath = path.join(__dirname, "automation.js");
            return fs.readFileSync(filePath, "utf8");
          });
          api.ipc.handle("auto-follow-up-session-budget", (_event, request) => getSessionBudget(request));
          console.log("[Auto Follow-up] main IPC handler registered successfully");
        } else {
          console.warn("[Auto Follow-up] api.ipc.handle is not available in main process");
        }
      } catch (err) {
        console.error("Failed to register IPC handler in main process:", err);
      }
      return;
    }

    if (typeof document === "undefined") return;

    // 全局点击事件调试监听
    document.addEventListener("click", (e) => {
      api.log.info(`[自动连击 Debug] 全局点击事件触发! target: ${e.target?.tagName}.${e.target?.className || ""}, coords: (${e.clientX}, ${e.clientY})`);
    }, { capture: true, passive: true });

    (async () => {
      try {
      const code = await api.ipc.invoke("read-automation");
      new Function(code)();
      api.log.info("Auto Follow-up 连击插件已成功启动！");
    } catch (e) {
      api.log.error("Failed to load automation engine via IPC:", e);
    }

    api.log.info("[自动连击] renderer UI init start");
    try {
    const storageGet = (key, fallback) => {
      try {
        return typeof api.storage?.get === "function" ? api.storage.get(key, fallback) : fallback;
      } catch (error) {
        api.log.warn(`[自动连击] 读取配置失败: ${key}`, error);
        return fallback;
      }
    };
    const storageSet = (key, value) => {
      try {
        if (typeof api.storage?.set === "function") {
          api.storage.set(key, value);
        }
      } catch (error) {
        api.log.warn(`[自动连击] 写入配置失败: ${key}`, error);
      }
    };

    // 从存储初始化配置
    let defaultAutoEnabled = storageGet("autoEnabled", true);
    let maxDepth = storageGet("maxDepth", 10);
    let debounceMs = storageGet("debounceMs", 2000);
    const MAX_SESSION_CACHE_ENTRIES = 50;
    let sessionDepths = storageGet("sessionDepths", {});
    let sessionEnabledMap = storageGet("sessionEnabledMap", {});
    let lastSessionKey = "";
    let settingsPageHandle = null;
    const FLOATING_PANEL_ID = "auto-followup-floating-panel";
    const STABLE_SESSION_KEY_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
    const INVALID_SESSION_KEY_RE = /^(default-session|active-tab-|first-msg-|未识别当前会话)$/i;
    sessionDepths = normalizeSessionMap(sessionDepths);
    sessionEnabledMap = normalizeSessionMap(sessionEnabledMap);
    pruneSessionCaches();

    function normalizeSessionMap(map) {
      return map && typeof map === "object" && !Array.isArray(map) ? map : {};
    }

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

    function isValidSessionKey(key) {
      return normalizeSessionKey(key) !== null;
    }

    function touchSessionMapEntry(map, key, value) {
      if (!isValidSessionKey(key)) return;
      if (Object.prototype.hasOwnProperty.call(map, key)) {
        delete map[key];
      }
      map[key] = value;
      pruneSessionMap(map);
    }

    function pruneSessionMap(map) {
      let changed = false;
      for (const key of Object.keys(map)) {
        if (!isValidSessionKey(key)) {
          delete map[key];
          changed = true;
        }
      }
      const keys = Object.keys(map);
      if (keys.length <= MAX_SESSION_CACHE_ENTRIES) return changed;
      for (const key of keys.slice(0, keys.length - MAX_SESSION_CACHE_ENTRIES)) {
        delete map[key];
        changed = true;
      }
      return changed;
    }

    function pruneSessionCaches() {
      if (pruneSessionMap(sessionDepths)) {
        storageSet("sessionDepths", sessionDepths);
      }
      if (pruneSessionMap(sessionEnabledMap)) {
        storageSet("sessionEnabledMap", sessionEnabledMap);
      }
    }

    // 获取当前 session 的开关状态（使用缓存 key，避免 DOM 抖动）
    function isSessionEnabled() {
      const key = lastSessionKey || findStableSessionKey();
      sessionEnabledMap = normalizeSessionMap(sessionEnabledMap);
      if (key in sessionEnabledMap) return sessionEnabledMap[key];
      return defaultAutoEnabled;
    }

    // 设置当前 session 的开关状态
    function setSessionEnabled(enabled) {
      const key = lastSessionKey || findStableSessionKey();
      sessionEnabledMap = normalizeSessionMap(sessionEnabledMap);
      if (!key) {
        defaultAutoEnabled = enabled;
        storageSet("autoEnabled", enabled);
        return;
      }
      touchSessionMapEntry(sessionEnabledMap, key, enabled);
      storageSet("sessionEnabledMap", sessionEnabledMap);
    }

    function getSessionKey() {
      return lastSessionKey || findStableSessionKey() || "未识别当前会话";
    }

    function getSessionDepth() {
      const key = lastSessionKey || findStableSessionKey();
      if (typeof sessionDepths !== "object" || sessionDepths === null) {
        sessionDepths = {};
      }
      if (!key) return 0;
      return typeof sessionDepths[key] === "number" ? sessionDepths[key] : 0;
    }

    function setSessionDepth(depth) {
      const key = lastSessionKey || findStableSessionKey();
      sessionDepths = normalizeSessionMap(sessionDepths);
      if (!key) return;
      touchSessionMapEntry(sessionDepths, key, depth);
      storageSet("sessionDepths", sessionDepths);
    }

    // 缓存一些状态
    let autoSendTimeout = null;
    let floatingPanel = null;
    let hasGeneratedInSession = false;
    const activateSession = () => {
      if (!hasGeneratedInSession) {
        hasGeneratedInSession = true;
        api.log.info("[自动连击] 检测到活跃交互，成功激活当前 Session 自动发送闸");
      }
    };
    document.addEventListener("input", activateSession, { capture: true, passive: true });
    document.addEventListener("keydown", activateSession, { capture: true, passive: true });
    document.addEventListener("focusin", activateSession, { capture: true, passive: true });
    api.log.info("[自动连击] renderer interaction listeners registered");

    // 注册 Tweak Settings 配置面板。配置入口失败不能影响右下角悬浮面板。
    api.log.info("[自动连击] settings API shape", {
      register: typeof api.settings?.register,
      registerPage: typeof api.settings?.registerPage,
    });
    if (typeof api.settings?.register === "function") {
      try {
        api.settings.register({
      id: "auto-follow-up-general",
      title: "自动连击 Follow-up 配置",
      render(root) {
        root.innerHTML = "";

        // 1. 标题组
        const titleRow = document.createElement("div");
        titleRow.className = "flex h-toolbar items-center justify-between gap-2 px-0 py-0 mb-2";
        const innerTitle = document.createElement("div");
        innerTitle.className = "flex min-w-0 flex-1 flex-col gap-1";
        const t = document.createElement("div");
        t.className = "text-base font-medium text-token-text-primary";
        t.textContent = "Auto Follow-up 自动连击";
        const sub = document.createElement("div");
        sub.className = "text-token-text-secondary text-sm";
        sub.textContent = "拦截大模型回复最后的 JSON 负载，并开启无人值守挂机自动执行。";
        innerTitle.append(t, sub);
        titleRow.appendChild(innerTitle);
        root.appendChild(titleRow);

        // 2. 配置卡片
        const card = document.createElement("div");
        card.className = "border-token-border flex flex-col divide-y-[0.5px] divide-token-border rounded-lg border mb-4";
        card.style.backgroundColor = "var(--color-background-panel, var(--color-token-bg-fog))";

        // 第一行：自动执行主开关
        const row1 = document.createElement("div");
        row1.className = "flex items-center justify-between gap-4 p-3";
        const left1 = document.createElement("div");
        left1.className = "flex min-w-0 flex-col gap-1";
        const label1 = document.createElement("div");
        label1.className = "min-w-0 text-sm text-token-text-primary";
        label1.textContent = "启用无人值守自动点击";
        const desc1 = document.createElement("div");
        desc1.className = "text-token-text-secondary min-w-0 text-sm";
        desc1.textContent = "每个会话独立控制。AI生成下一步建议后，无需人工干预，自动连击继续执行。";
        left1.append(label1, desc1);
        row1.appendChild(left1);

        // 构造 Toggle Switch 控件
        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.setAttribute("role", "switch");
        const pill = document.createElement("span");
        const knob = document.createElement("span");
        knob.className = "rounded-full border border-[color:var(--gray-0)] bg-[color:var(--gray-0)] shadow-sm transition-transform duration-200 ease-out h-4 w-4";
        pill.appendChild(knob);
        
        const applyToggle = (on) => {
          toggleBtn.setAttribute("aria-checked", String(on));
          toggleBtn.className = "inline-flex items-center text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-token-focus-border focus-visible:rounded-full cursor-interaction";
          pill.className = "relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 ease-out h-5 w-8 " + (on ? "bg-token-charts-blue" : "bg-token-foreground/20");
          knob.style.transform = on ? "translateX(14px)" : "translateX(2px)";
        };
        applyToggle(isSessionEnabled());
        toggleBtn.appendChild(pill);
        toggleBtn.addEventListener("click", () => {
          const newVal = toggleBtn.getAttribute("aria-checked") !== "true";
          setSessionEnabled(newVal);
          applyToggle(newVal);
          if (!newVal) {
            globalThis.automation?.cancelCountdown();
          }
          updateFloatingPanel();
        });
        row1.appendChild(toggleBtn);
        card.appendChild(row1);

        // 第二行：最大自动连击深度
        const row2 = document.createElement("div");
        row2.className = "flex items-center justify-between gap-4 p-3";
        const left2 = document.createElement("div");
        left2.className = "flex min-w-0 flex-col gap-1";
        const label2 = document.createElement("div");
        label2.className = "min-w-0 text-sm text-token-text-primary";
        label2.textContent = "最大追问深度限制";
        const desc2 = document.createElement("div");
        desc2.className = "text-token-text-secondary min-w-0 text-sm";
        desc2.textContent = "设置允许连续自动执行的最大轮数，防止过度消耗 Token。";
        left2.append(label2, desc2);
        row2.appendChild(left2);

        const selectDepth = document.createElement("select");
        selectDepth.className = "border-token-border bg-token-foreground/5 hover:bg-token-foreground/10 h-token-button-composer inline-flex items-center justify-between gap-2 rounded-md border px-2 text-sm text-token-text-primary cursor-interaction";
        [5, 10, 15, 20].forEach(d => {
          const opt = document.createElement("option");
          opt.value = String(d);
          opt.textContent = `${d} 轮`;
          if (d === maxDepth) opt.selected = true;
          selectDepth.appendChild(opt);
        });
        selectDepth.addEventListener("change", () => {
          maxDepth = parseInt(selectDepth.value, 10);
          storageSet("maxDepth", maxDepth);
        });
        row2.appendChild(selectDepth);
        card.appendChild(row2);

        // 第三行：手动清空计数器
        const row3 = document.createElement("div");
        row3.className = "flex items-center justify-between gap-4 p-3";
        const left3 = document.createElement("div");
        left3.className = "flex min-w-0 flex-col gap-1";
        const label3 = document.createElement("div");
        label3.className = "min-w-0 text-sm text-token-text-primary";
        label3.textContent = "重置当前已连击计数器";
        const desc3 = document.createElement("div");
        desc3.className = "text-token-text-secondary min-w-0 text-sm";
        desc3.textContent = `当前会话 [${getSessionKey().slice(0, 20)}] 已连续自动执行了 ${getSessionDepth()} 轮。`;
        left3.append(label3, desc3);
        row3.appendChild(left3);

        const resetBtn = document.createElement("button");
        resetBtn.type = "button";
        resetBtn.className = "rounded-full px-3 py-1 text-sm bg-token-charts-red/10 text-token-charts-red hover:bg-token-charts-red/20 cursor-interaction";
        resetBtn.textContent = "重置计数";
        resetBtn.addEventListener("click", () => {
          setSessionDepth(0);
          desc3.textContent = `当前会话 [${getSessionKey().slice(0, 20)}] 已连续自动执行了 0 轮。`;
          updateFloatingPanel();
        });
        row3.appendChild(resetBtn);
        card.appendChild(row3);

        root.appendChild(card);
      }
        });
      } catch (error) {
        api.log.warn("[自动连击] Tweaks 嵌套配置注册失败，继续挂载右下角悬浮面板", error);
      }
    } else {
      api.log.warn("[自动连击] 当前 Codex++ runtime 不支持 settings.register，跳过 Tweaks 嵌套配置");
    }

    if (typeof api.settings?.registerPage === "function") {
      try {
        settingsPageHandle = api.settings.registerPage({
        id: "auto-follow-up",
        title: "Auto Follow-up",
        description: "配置 Follow-up 候选的无人值守自动提交。",
        iconSvg:
          '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
          '<path d="M4 10a6 6 0 0 1 10.24-4.24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
          '<path d="M16 10a6 6 0 0 1-10.24 4.24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
          '<path d="M13.5 3.5h2v2M6.5 16.5h-2v-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
          "</svg>",
        render(root) {
          root.innerHTML = "";

          const stack = document.createElement("div");
          stack.className = "flex max-w-2xl flex-col gap-4";

          const title = document.createElement("div");
          title.className = "flex flex-col gap-1";
          const h = document.createElement("div");
          h.className = "text-base font-medium text-token-text-primary";
          h.textContent = "Auto Follow-up 自动提交";
          const sub = document.createElement("div");
          sub.className = "text-sm text-token-text-secondary";
          sub.textContent = "控制当前会话的自动提交开关、连击深度和计数。";
          title.append(h, sub);
          stack.appendChild(title);

          const status = document.createElement("div");
          status.className = "text-sm text-token-text-secondary";

          const toggleButton = document.createElement("button");
          toggleButton.type = "button";
          toggleButton.className = "w-fit rounded-md px-3 py-2 text-sm font-medium text-white cursor-interaction";

          const syncToggle = () => {
            const on = isSessionEnabled();
            toggleButton.textContent = on ? "关闭自动提交" : "开启自动提交";
            toggleButton.style.backgroundColor = on ? "#dc2626" : "#2563eb";
            status.textContent = `当前会话: ${getSessionKey()} · 状态: ${on ? "已开启" : "已关闭"} · 已连击 ${getSessionDepth()}/${maxDepth} 轮`;
          };
          toggleButton.addEventListener("click", () => {
            const next = !isSessionEnabled();
            setSessionEnabled(next);
            if (!next) {
              globalThis.automation?.cancelCountdown();
            }
            updateFloatingPanel();
            syncToggle();
          });

          const depthRow = document.createElement("div");
          depthRow.className = "flex flex-wrap items-center gap-3 text-sm text-token-text-primary";
          const depthLabel = document.createElement("span");
          depthLabel.textContent = "最大追问深度";
          const selectDepth = document.createElement("select");
          selectDepth.className = "border-token-border bg-token-foreground/5 h-token-button-composer rounded-md border px-2 text-sm text-token-text-primary cursor-interaction";
          [5, 10, 15, 20].forEach((d) => {
            const opt = document.createElement("option");
            opt.value = String(d);
            opt.textContent = `${d} 轮`;
            if (d === maxDepth) opt.selected = true;
            selectDepth.appendChild(opt);
          });
          selectDepth.addEventListener("change", () => {
            maxDepth = parseInt(selectDepth.value, 10);
            storageSet("maxDepth", maxDepth);
            updateFloatingPanel();
            syncToggle();
          });
          depthRow.append(depthLabel, selectDepth);

          const resetButton = document.createElement("button");
          resetButton.type = "button";
          resetButton.className = "w-fit rounded-md bg-token-foreground/10 px-3 py-2 text-sm text-token-text-primary hover:bg-token-foreground/20 cursor-interaction";
          resetButton.textContent = "重置当前计数";
          resetButton.addEventListener("click", () => {
            setSessionDepth(0);
            updateFloatingPanel();
            syncToggle();
          });

          stack.append(status, toggleButton, depthRow, resetButton);
          root.appendChild(stack);
          syncToggle();
        }
      });
        api.log.info("[自动连击] Auto Follow-up 设置页已注册");
      } catch (error) {
        api.log.warn("[自动连击] Auto Follow-up 设置页注册失败，继续挂载右下角悬浮面板", error);
      }
    } else {
      api.log.warn("[自动连击] 当前 Codex++ runtime 不支持 settings.registerPage，使用 Tweaks 嵌套配置");
    }

    // 动态渲染优雅的 Glassmorphism 悬浮控制面板在主界面上
    function renderFloatingPanel(reason = "init") {
      const existing = document.getElementById(FLOATING_PANEL_ID);
      if (existing) {
        floatingPanel = existing;
        updateFloatingPanel();
        return;
      }

      floatingPanel = document.createElement("div");
      floatingPanel.id = FLOATING_PANEL_ID;
      floatingPanel.style.position = "fixed";
      floatingPanel.style.bottom = "80px";
      floatingPanel.style.right = "30px";
      floatingPanel.style.zIndex = "2147483647";
      floatingPanel.style.padding = "8px 12px";
      floatingPanel.style.borderRadius = "20px";
      floatingPanel.style.border = "1px solid rgba(255, 255, 255, 0.1)";
      floatingPanel.style.backdropFilter = "blur(12px) saturate(180%)";
      floatingPanel.style.backgroundColor = "rgba(15, 23, 42, 0.75)";
      floatingPanel.style.boxShadow = "0 4px 20px rgba(0, 0, 0, 0.3)";
      floatingPanel.style.display = "flex";
      floatingPanel.style.alignItems = "center";
      floatingPanel.style.gap = "8px";
      floatingPanel.style.color = "#f8fafc";
      floatingPanel.style.fontSize = "12px";
      floatingPanel.style.fontFamily = "system-ui, sans-serif";
      floatingPanel.style.transition = "all 0.3s ease";
      floatingPanel.style.cursor = "pointer";
      floatingPanel.style.userSelect = "none";
      floatingPanel.style.setProperty("-webkit-app-region", "no-drag");
      floatingPanel.style.setProperty("pointer-events", "auto", "important");

      floatingPanel.addEventListener("mouseenter", () => {
        floatingPanel.style.transform = "scale(1.05)";
        floatingPanel.style.backgroundColor = "rgba(30, 41, 59, 0.85)";
        floatingPanel.style.borderColor = "rgba(255, 255, 255, 0.25)";
      });
      floatingPanel.addEventListener("mouseleave", () => {
        floatingPanel.style.transform = "scale(1)";
        floatingPanel.style.backgroundColor = "rgba(15, 23, 42, 0.75)";
        floatingPanel.style.borderColor = "rgba(255, 255, 255, 0.1)";
      });

      floatingPanel.addEventListener("mousedown", (e) => {
        if (e.target.tagName.toLowerCase() === "button") return;
        const newVal = !isSessionEnabled();
        setSessionEnabled(newVal);
        api.log.info(`[自动连击] 用户通过悬浮面板切换当前会话 [${getSessionKey()}] 状态为: ${newVal ? "开启" : "关闭"}`);
        if (!newVal) {
          globalThis.automation?.cancelCountdown();
        }
        updateFloatingPanel();
      }, true);

      const host = document.body || document.documentElement;
      if (!host) {
        floatingPanel = null;
        setTimeout(() => ensureFloatingPanel("deferred-host"), 250);
        return;
      }

      host.appendChild(floatingPanel);
      updateFloatingPanel();
      api.log.info(`[自动连击] 右下角悬浮面板已挂载 (${reason})`);
    }

    function ensureFloatingPanel(reason = "ensure") {
      const existing = document.getElementById(FLOATING_PANEL_ID);
      if (existing) {
        floatingPanel = existing;
        if (!existing.isConnected) {
          (document.body || document.documentElement)?.appendChild(existing);
          api.log.info(`[自动连击] 右下角悬浮面板已重新挂载 (${reason})`);
        }
        updateFloatingPanel();
        return;
      }
      renderFloatingPanel(reason);
    }

    function getFloatingPanelStatus() {
      const sessionKey = lastSessionKey || findStableSessionKey() || "";
      const depth = getSessionDepth();
      const enabled = isSessionEnabled();
      const recognized = Boolean(sessionKey);
      const stateText = !recognized ? "待识别" : (enabled ? "已开启" : "已关闭");
      return {
        sessionKey,
        recognized,
        enabled,
        depth,
        maxDepth,
        stateText,
        label: `自动提交: ${stateText} · ${depth}/${maxDepth} 轮`,
      };
    }

    function updateFloatingPanel(customText = null) {
      if (!floatingPanel || !floatingPanel.isConnected) {
        floatingPanel = document.getElementById(FLOATING_PANEL_ID);
      }
      if (!floatingPanel) return;
      floatingPanel.innerHTML = "";
      const status = getFloatingPanelStatus();
      floatingPanel.dataset.autoFollowupEnabled = String(status.enabled);
      floatingPanel.dataset.autoFollowupRecognized = String(status.recognized);
      floatingPanel.dataset.autoFollowupDepth = String(status.depth);
      floatingPanel.dataset.autoFollowupMaxDepth = String(status.maxDepth);
      floatingPanel.dataset.autoFollowupSessionKey = status.sessionKey;
      floatingPanel.title = `Auto Follow-up ${status.stateText} · ${status.depth}/${status.maxDepth} 轮`;

      // 闪烁的呼吸灯指示器
      const dot = document.createElement("span");
      dot.style.display = "inline-block";
      dot.style.width = "8px";
      dot.style.height = "8px";
      dot.style.borderRadius = "50%";
      dot.style.pointerEvents = "none";
      
      const textSpan = document.createElement("span");
      textSpan.style.fontWeight = "500";
      textSpan.style.pointerEvents = "none";

      if (customText) {
        dot.style.backgroundColor = "#fbbf24";
        dot.style.boxShadow = "0 0 8px #fbbf24";
        textSpan.textContent = `${status.label} · ${customText}`;
      } else if (!status.recognized) {
        dot.style.backgroundColor = "#94a3b8";
        dot.style.boxShadow = "none";
        textSpan.textContent = status.label;
      } else if (!status.enabled) {
        dot.style.backgroundColor = "#94a3b8";
        dot.style.boxShadow = "none";
        textSpan.textContent = status.label;
      } else {
        dot.style.backgroundColor = "#22c55e";
        dot.style.boxShadow = "0 0 8px #22c55e";
        textSpan.textContent = status.label;
      }

      floatingPanel.appendChild(dot);
      floatingPanel.appendChild(textSpan);

      // 如果正在进行自动发送倒计时，添加一个一键"取消"按钮
      if (globalThis.automation?.isCountingDown()) {
        const cancelBtn = document.createElement("button");
        cancelBtn.type = "button";
        cancelBtn.style.border = "none";
        cancelBtn.style.background = "rgba(239, 68, 68, 0.2)";
        cancelBtn.style.color = "#f87171";
        cancelBtn.style.padding = "2px 8px";
        cancelBtn.style.borderRadius = "10px";
        cancelBtn.style.cursor = "pointer";
        cancelBtn.style.fontSize = "11px";
        cancelBtn.style.transition = "all 0.2s";
        cancelBtn.textContent = "取消本次";
        cancelBtn.addEventListener("mousedown", (e) => {
          e.stopPropagation();
          if (globalThis.automation?.cancelCountdown()) {
            api.log.info("[自动连击] 用户手动取消了本次自动点击倒计时");
          }
          updateFloatingPanel();
        });
        floatingPanel.appendChild(cancelBtn);
      }
    }

    // 判断大模型当前是否处于生成中的状态（防抖安全阀）
    function isAiGenerating() {
      const stopBtn = document.querySelector("button[aria-label*='Stop'], button[aria-label*='stop'], .stop-generation-btn");
      if (stopBtn) return true;
      const textarea = document.querySelector("textarea");
      if (textarea && textarea.disabled) return true;
      return false;
    }

    // 核心扫描器：委托给 automation.js 引擎处理 follow-up 面板检测与自动触发
    function scanFollowUpPanels() {
      ensureFloatingPanel("scan");
      // 每个 scan 周期只调一次 getSessionKey()，结果缓存到 lastSessionKey
      // 本周期内所有 isSessionEnabled/getSessionDepth 等函数读 lastSessionKey，避免 DOM 抖动导致跳闪
      const freshKey = findStableSessionKey() || "";
      if (freshKey !== lastSessionKey) {
        const oldKey = lastSessionKey;
        lastSessionKey = freshKey;
        if (oldKey) {
          api.log.info(`[自动连击] 检测到会话切换: ${oldKey} -> ${freshKey || "未识别当前会话"}，取消旧会话倒计时，加载新会话状态`);
          globalThis.automation?.cancelCountdown();
        }
        // 切换会话时立即刷新面板，展示新会话的 enabled/depth 状态
        updateFloatingPanel();
      }

      if (!freshKey) {
        return;
      }

      globalThis.automation?.run({
        api,
        isAutoEnabled: isSessionEnabled(),
        maxDepth,
        debounceMs,
        currentDepth: getSessionDepth(),
        updateDepth: (d) => { setSessionDepth(d); },
        updateFloatingPanel,
        isAiGenerating,
        sessionKey: freshKey
      });
    }

    // 5. 使用低频轮询替代 MutationObserver（治本方案）
    // Follow-up 面板只在 AI 生成完毕后才出现，1.5 秒轮询延迟人类无感知
    // 彻底消除 AI 流式输出时数百次/秒的 DOM 回调对 UI 线程的阻塞
    const _pollIntervalId = setInterval(() => {
      ensureFloatingPanel("poll");
      if (isAiGenerating()) {
        hasGeneratedInSession = true;
        scanFollowUpPanels();
        return;
      }
      scanFollowUpPanels();
    }, 1500);

    // 初始化时注入悬浮面板并主动扫描一次（必须等 body 就绪）
    const _initUI = () => { ensureFloatingPanel("init"); scanFollowUpPanels(); };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", _initUI);
    } else {
      _initUI();
    }

    // 记录热重载销毁器，确保在 tweak 重载时完美清空残留节点和定时器
    globalThis.__autoFollowupCleanup = () => {
      clearInterval(_pollIntervalId);
      globalThis.automation?.cleanup();
      document.removeEventListener("input", activateSession, { capture: true });
      document.removeEventListener("keydown", activateSession, { capture: true });
      document.removeEventListener("focusin", activateSession, { capture: true });
      if (autoSendTimeout) clearTimeout(autoSendTimeout);
      if (floatingPanel) floatingPanel.remove();
      floatingPanel = null;
      settingsPageHandle?.unregister?.();
    };
    } catch (e) {
      api.log.error("[自动连击] renderer UI init failed", e);
    }
    })();
  },

  stop() {
    if (globalThis.__autoFollowupCleanup) {
      try {
        globalThis.__autoFollowupCleanup();
      } catch (e) {}
      globalThis.__autoFollowupCleanup = null;
    }
  }
};
