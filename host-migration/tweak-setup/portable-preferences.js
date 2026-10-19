/* Run in the isolated Codex++ renderer console only when exporting/importing.
 * Loading this helper performs no storage writes and sends no requests.
 */
(function (root, factory) {
  const api = factory();
  if (typeof window === "undefined" && typeof module === "object" && module.exports) module.exports = api;
  else root.CodexPlusPlusMigration = api;
})(globalThis, function () {
  "use strict";
  const schema = "codexpp-tweak-preferences.v1";
  const rules = {
    "com.lobster.auto-follow-up": {
      autoEnabled: "boolean", maxDepth: "depth", debounceMs: "delay",
    },
    "co.Arconte112.followup": {
      enabled: "boolean", showDivider: "boolean", clickableItems: "boolean",
      allowLegacyDirectRender: "boolean", title: "title", syncAgents: "boolean", followupPrompt: "prompt",
    },
  };
  function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
  function store(value) {
    const result = value || globalThis.localStorage;
    if (!result || typeof result.getItem !== "function" || typeof result.setItem !== "function") throw new Error("Open the isolated Codex++ renderer console first.");
    return result;
  }
  function key(id) { return "codexpp:storage:" + id; }
  function read(storage, id) {
    const value = JSON.parse(storage.getItem(key(id)) || "{}");
    if (!object(value)) throw new Error("Invalid native preference object: " + id);
    return value;
  }
  function valid(type, value) {
    if (type === "boolean") return typeof value === "boolean";
    if (type === "depth") return Number.isInteger(value) && value >= 1 && value <= 1000;
    if (type === "delay") return Number.isInteger(value) && value >= 0 && value <= 60000;
    return typeof value === "string" && value.length <= (type === "title" ? 256 : 100000);
  }
  function select(id, source, strict) {
    if (!object(source)) throw new Error("Invalid preference object: " + id);
    const result = {};
    for (const name of Object.keys(source)) {
      const type = Object.prototype.hasOwnProperty.call(rules[id], name) ? rules[id][name] : null;
      if (!type) {
        if (strict) throw new Error("Unrecognized preference field: " + name);
        continue;
      }
      if (!valid(type, source[name])) throw new Error("Invalid preference field: " + name);
      result[name] = source[name];
    }
    return result;
  }
  function exportPreferences(storage) {
    storage = store(storage);
    const preferences = {};
    for (const id of Object.keys(rules)) {
      const native = read(storage, id);
      preferences[id] = select(id, native, false);
      if (id === "co.Arconte112.followup" && !("followupPrompt" in preferences[id]) && typeof native.agentsInstruction === "string") {
        preferences[id].followupPrompt = select(id, { followupPrompt: native.agentsInstruction }, true).followupPrompt;
      }
    }
    return { schema_version: schema, preferences };
  }
  function importPreferences(input, storage) {
    storage = store(storage);
    const doc = typeof input === "string" ? JSON.parse(input) : input;
    if (!object(doc) || doc.schema_version !== schema || !object(doc.preferences)
        || Object.keys(doc).some(name => !["schema_version", "preferences"].includes(name))) throw new Error("Unrecognized migration preference format.");
    const pending = [];
    for (const id of Object.keys(doc.preferences)) {
      if (!Object.prototype.hasOwnProperty.call(rules, id)) throw new Error("Unrecognized plugin id.");
      const selected = select(id, doc.preferences[id], true);
      const previous = storage.getItem(key(id));
      pending.push({ id, previous, next: JSON.stringify({ ...read(storage, id), ...selected }) });
    }
    const written = [];
    try {
      for (const item of pending) {
        written.push(item);
        storage.setItem(key(item.id), item.next);
      }
    } catch (error) {
      let rollbackFailed = false;
      for (const item of written.reverse()) {
        try {
          if (item.previous === null) storage.removeItem(key(item.id));
          else storage.setItem(key(item.id), item.previous);
        } catch (_) { rollbackFailed = true; }
      }
      throw new Error(rollbackFailed ? "Preference write failed; restore the saved private backup before retrying." : "Preference write failed; previous settings were restored.");
    }
    return { imported_plugins: pending.map(item => item.id), restart_codex_plus_plus: true };
  }
  return Object.freeze({ exportPreferences, importPreferences });
});
