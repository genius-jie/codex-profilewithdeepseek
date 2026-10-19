import assert from "node:assert/strict";
import test from "node:test";
import {
  apiKeyRecentsFetchGuardSource,
  isApiKeyAuthMode,
  isChatGptBackendApiUrl,
} from "../src/api-key-recents-guard";

test("recognizes explicit API key auth mode and cm model_provider", () => {
  assert.equal(isApiKeyAuthMode('auth_mode = "apikey"'), true);
  assert.equal(isApiKeyAuthMode("auth_mode = 'APIKEY'"), true);
  assert.equal(isApiKeyAuthMode('model_provider = "cm"'), true);
  assert.equal(isApiKeyAuthMode("[model_providers.cm]"), true);
  assert.equal(isApiKeyAuthMode("", '{"auth_mode":"apikey"}'), true);
  assert.equal(isApiKeyAuthMode("", '{"OPENAI_API_KEY":"sk-123456"}'), true);
  assert.equal(isApiKeyAuthMode('auth_mode = "chatgpt"'), false);
  assert.equal(isApiKeyAuthMode('# auth_mode = "apikey"'), false);
  assert.equal(isApiKeyAuthMode('# model_provider = "cm"'), false);
});

test("matches only the ChatGPT backend API that API key mode cannot use", () => {
  assert.equal(isChatGptBackendApiUrl("https://chatgpt.com/backend-api/conversations"), true);
  assert.equal(isChatGptBackendApiUrl("https://chatgpt.com/backend-api"), true);
  assert.equal(isChatGptBackendApiUrl("https://chatgpt.com/"), false);
  assert.equal(isChatGptBackendApiUrl("https://api.openai.com/backend-api/conversations"), false);
  assert.equal(isChatGptBackendApiUrl("http://127.0.0.1:48760/v1/responses"), false);
});

test("the page-world guard responds with empty conversations and injects visibility CSS", async () => {
  const calls: string[] = [];
  const styles: Array<{ id: string; textContent: string }> = [];
  const page: Record<string, unknown> = {
    URL,
    Error,
    Response,
    location: { href: "app://-/index.html" },
    document: {
      readyState: "complete",
      getElementById: (id: string) => styles.find((s) => s.id === id) || null,
      createElement: () => ({ id: "", textContent: "" }),
      head: {
        appendChild: (el: { id: string; textContent: string }) => styles.push(el),
      },
    },
    fetch: async (input: string) => {
      calls.push(input);
      return { ok: true };
    },
  };
  page.globalThis = page;

  Function("globalThis, document", apiKeyRecentsFetchGuardSource())(page, page.document);
  const guardedFetch = page.fetch as (input: string) => Promise<Response>;

  const chatGptRes = await guardedFetch("https://chatgpt.com/backend-api/conversations");
  assert.equal(chatGptRes.status, 200);
  const json = await chatGptRes.json();
  assert.deepEqual(json, {
    items: [],
    total: 0,
    limit: 20,
    offset: 0,
    has_missing_conversations: false,
  });

  await guardedFetch("http://127.0.0.1:48760/v1/responses");
  assert.deepEqual(calls, ["http://127.0.0.1:48760/v1/responses"]);
  assert.equal(styles.length, 1);
  assert.equal(styles[0].id, "codexpp-hide-recents-spinner");
});
