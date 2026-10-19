const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { exportPreferences, importPreferences } = require("../tweak-setup/portable-preferences.js");
const auto = "com.lobster.auto-follow-up", follow = "co.Arconte112.followup";
const key = id => "codexpp:storage:" + id;
function storage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { data, getItem: k => data.has(k) ? data.get(k) : null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) };
}
const source = storage({
  [key(auto)]: JSON.stringify({ autoEnabled: false, maxDepth: 15, debounceMs: 2100, sessionDepths: { "old-private-session": 9 }, sessionEnabledMap: { "old-private-session": true } }),
  [key(follow)]: JSON.stringify({ title: "Follow-up", followupPrompt: "My private local strategy", syncAgents: true, credential: "private-value-excluded" }),
  unrelated: "do not read or export",
});
const before = [...source.data];
const browser = { window: {}, localStorage: source, module: { exports: {} } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../tweak-setup/portable-preferences.js"), "utf8"), browser);
assert.equal(typeof browser.CodexPlusPlusMigration.exportPreferences, "function");
assert.equal(browser.CodexPlusPlusMigration.exportPreferences().preferences[auto].maxDepth, 15);
assert.deepEqual([...source.data], before);
const exported = exportPreferences(source);
assert.deepEqual([...source.data], before);
assert.equal(exported.preferences[auto].maxDepth, 15);
assert.equal(exported.preferences[follow].followupPrompt, "My private local strategy");
assert(!JSON.stringify(exported).includes("old-private-session"));
assert(!JSON.stringify(exported).includes("private-value-excluded"));
assert(!JSON.stringify(exported).includes("unrelated"));
const legacy = exportPreferences(storage({ [key(follow)]: JSON.stringify({ agentsInstruction: "Older custom prompt" }) }));
assert.equal(legacy.preferences[follow].followupPrompt, "Older custom prompt");
const target = storage({ [key(auto)]: JSON.stringify({ maxDepth: 5, sessionDepths: { "new-session": 1 } }), otherPlugin: "preserved" });
const result = importPreferences(JSON.stringify(exported), target);
assert.equal(JSON.parse(target.getItem(key(auto))).maxDepth, 15);
assert.deepEqual(JSON.parse(target.getItem(key(auto))).sessionDepths, { "new-session": 1 });
assert.equal(target.getItem("otherPlugin"), "preserved");
assert(!JSON.stringify(result).includes("My private local strategy"));
const after = [...target.data];
for (const bad of [
  { schema_version: exported.schema_version, preferences: { [auto]: { sessionDepths: {} } } },
  { schema_version: exported.schema_version, preferences: { "unrelated.plugin": {} } },
  { schema_version: exported.schema_version, preferences: { [auto]: { autoEnabled: "true" } } },
  { schema_version: exported.schema_version, preferences: { [auto]: { maxDepth: 0 } } },
  { schema_version: exported.schema_version, preferences: { [auto]: { constructor: "unsupported" } } },
  { ...exported, extra: "unsupported" },
]) {
  assert.throws(() => importPreferences(bad, target));
  assert.deepEqual([...target.data], after);
}
const originalWrite = target.setItem;
let attempts = 0;
target.setItem = (k, v) => { if (++attempts === 2) throw new Error("fixture quota failure"); originalWrite(k, v); };
assert.throws(() => importPreferences(exported, target), /previous settings were restored/);
assert.deepEqual([...target.data], after);
console.log("PASS: native renderer preference export/import, private-state exclusion, preflight rejection and rollback");
