const CHATGPT_HOST = "chatgpt.com";
const CHATGPT_BACKEND_API_PATH = "/backend-api";
const PAGE_GUARD_MARKER = "__codexpp_api_key_recents_guard__";

/**
 * API-key sessions have no ChatGPT account credential.  The desktop sidebar
 * still probes the ChatGPT conversation endpoint, whose pending request can
 * otherwise keep its combined "Recents" loader active indefinitely.
 */
export function isApiKeyAuthMode(configToml?: string, authJson?: string): boolean {
  if (typeof authJson === "string" && authJson.trim()) {
    try {
      const parsed = JSON.parse(authJson);
      if (parsed.auth_mode === "apikey" || (typeof parsed.OPENAI_API_KEY === "string" && parsed.OPENAI_API_KEY.trim())) {
        return true;
      }
    } catch {
      if (/"auth_mode"\s*:\s*"apikey"/i.test(authJson) || /"OPENAI_API_KEY"/i.test(authJson)) {
        return true;
      }
    }
  }

  if (typeof configToml === "string" && configToml.trim()) {
    const lines = configToml.split(/\r?\n/);
    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      if (/^auth_mode\s*=\s*["']apikey["']\s*(?:#.*)?$/i.test(trimmed)) return true;
      if (/^model_provider\s*=\s*["']cm["']\s*(?:#.*)?$/i.test(trimmed)) return true;
      if (/^\[model_providers\.cm\]/i.test(trimmed)) return true;
    }
  }

  return false;
}

export function isChatGptBackendApiUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      url.hostname === CHATGPT_HOST &&
      (url.pathname === CHATGPT_BACKEND_API_PATH ||
        url.pathname.startsWith(`${CHATGPT_BACKEND_API_PATH}/`));
  } catch {
    return false;
  }
}

/**
 * Runs in Codex's page world before its renderer bundle.  It deliberately
 * rejects only the unavailable ChatGPT conversation transport; all Codex
 * API-key traffic (including the configured local CodexManager endpoint)
 * keeps the original fetch implementation.
 */
export function apiKeyRecentsFetchGuardSource(): string {
  return `(() => {
    const marker = ${JSON.stringify(PAGE_GUARD_MARKER)};
    const root = globalThis;
    if (root[marker]) return;

    const injectRecentsStyle = () => {
      try {
        if (typeof document === "undefined" || document.getElementById("codexpp-hide-recents-spinner")) return;
        const style = document.createElement("style");
        style.id = "codexpp-hide-recents-spinner";
        style.textContent = \`
          div[class*="justify-center"][class*="py-3"] .motion-safe\\\\:animate-spin,
          div.flex.w-full.justify-center.py-3 .motion-safe\\\\:animate-spin {
            visibility: hidden !important;
            opacity: 0 !important;
          }
        \`;
        (document.head || document.documentElement).appendChild(style);
      } catch {}
    };

    if (typeof document !== "undefined") {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", injectRecentsStyle, { once: true });
      } else {
        injectRecentsStyle();
      }
    }

    const originalFetch = root.fetch;
    if (typeof originalFetch !== "function") return;
    const isUnsupportedChatGptRequest = (input) => {
      try {
        const raw = typeof input === "string" ? input : input && input.url;
        if (typeof raw !== "string") return false;
        const url = new URL(raw, root.location && root.location.href);
        return url.protocol === "https:" && url.hostname === "chatgpt.com" &&
          (url.pathname === "/backend-api" || url.pathname.startsWith("/backend-api/"));
      } catch {
        return false;
      }
    };
    Object.defineProperty(root, marker, { value: true, configurable: true });
    Object.defineProperty(root, "fetch", {
      configurable: true,
      writable: true,
      value(input, init) {
        if (isUnsupportedChatGptRequest(input)) {
          const body = JSON.stringify({
            items: [],
            total: 0,
            limit: 20,
            offset: 0,
            has_missing_conversations: false
          });
          const response = new Response(body, {
            status: 200,
            headers: { "Content-Type": "application/json" }
          });
          return Promise.resolve(response);
        }
        return originalFetch.call(this, input, init);
      },
    });
  })();`;
}
