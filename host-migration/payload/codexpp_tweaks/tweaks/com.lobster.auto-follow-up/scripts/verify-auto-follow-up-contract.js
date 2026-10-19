const cp = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const sourceRoot = path.resolve(__dirname, "..");
const contractPath = path.join(sourceRoot, "auto-follow-up.contract.json");
const failures = [];
const repair = process.argv.includes("--repair");

function fail(message) {
  failures.push(message);
}

function readJson(filePath, label) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    fail(`${label} is not readable JSON: ${filePath}: ${error.message}`);
    return {};
  }
}

function realPath(filePath, label) {
  try {
    return fs.realpathSync.native(filePath);
  } catch (error) {
    fail(`${label} is not reachable: ${filePath}: ${error.message}`);
    return "";
  }
}

function samePath(left, right) {
  return path.normalize(left).toLowerCase() === path.normalize(right).toLowerCase();
}

function runNode(args, label) {
  const result = cp.spawnSync(process.execPath, args, {
    cwd: sourceRoot,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    fail(`${label} failed with exit ${result.status}\n${result.stdout || ""}${result.stderr || ""}`);
  }
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

function assertSafeInstalledPath(filePath, tweakId) {
  const normalized = path.normalize(filePath).toLowerCase();
  const expectedSuffix = path.normalize(path.join("codex-plusplus", "tweaks", tweakId)).toLowerCase();
  if (!normalized.endsWith(expectedSuffix)) {
    throw new Error(`refusing to repair unexpected installed path: ${filePath}`);
  }
}

function ensureInstalledLink(contractData) {
  const installedPath = contractData.installed_path;
  assertSafeInstalledPath(installedPath, contractData.tweak_id);

  const source = realPath(sourceRoot, "source root");
  if (!source) return;

  if (fs.existsSync(installedPath)) {
    const installed = realPath(installedPath, "installed tweak path");
    if (installed && samePath(installed, source)) return;

    const backupPath = `${installedPath}.overwritten-${new Date().toISOString().replace(/[:.]/g, "-")}`;
    fs.renameSync(installedPath, backupPath);
    console.log(`verify-auto-follow-up-contract: moved overwritten install to ${backupPath}`);
  }

  fs.mkdirSync(path.dirname(installedPath), { recursive: true });
  fs.symlinkSync(sourceRoot, installedPath, process.platform === "win32" ? "junction" : "dir");
  console.log(`verify-auto-follow-up-contract: restored install link ${installedPath}`);
}

function ensureConfigEnabled(contractData) {
  const configPath = contractData.codex_plusplus_config_path;
  const config = readJson(configPath, "Codex++ config");
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    fail("Codex++ config is not an object; repair skipped");
    return;
  }
  if (!config.tweaks || typeof config.tweaks !== "object" || Array.isArray(config.tweaks)) {
    config.tweaks = {};
  }
  let changed = false;
  if (!config.tweaks[contractData.tweak_id] || typeof config.tweaks[contractData.tweak_id] !== "object") {
    config.tweaks[contractData.tweak_id] = {};
    changed = true;
  }
  if (config.tweaks[contractData.tweak_id].enabled !== contractData.required_enabled) {
    config.tweaks[contractData.tweak_id].enabled = contractData.required_enabled;
    changed = true;
  }
  if (changed) {
    writeJson(configPath, config);
  }
}

function touchReloadMarker() {
  fs.writeFileSync(path.join(sourceRoot, ".codexpp-dev-reload"), new Date().toISOString(), "utf8");
}

const contract = readJson(contractPath, "contract");

if (repair) {
  ensureInstalledLink(contract);
  ensureConfigEnabled(contract);
  touchReloadMarker();
}

const sourceReal = realPath(sourceRoot, "source root");
const expectedSourceReal = realPath(contract.source_path || "", "contract source_path");
if (sourceReal && expectedSourceReal && !samePath(sourceReal, expectedSourceReal)) {
  fail(`contract source_path drifted: expected ${expectedSourceReal}, running ${sourceReal}`);
}

const installedReal = realPath(contract.installed_path || "", "installed tweak path");
if (installedReal && sourceReal && !samePath(installedReal, sourceReal)) {
  fail(`installed tweak path is not linked to source: installed realpath ${installedReal}, source ${sourceReal}`);
}

const config = readJson(contract.codex_plusplus_config_path || "", "Codex++ config");
const tweakConfig = config.tweaks && config.tweaks[contract.tweak_id];
if (!tweakConfig || tweakConfig.enabled !== contract.required_enabled) {
  fail(`Codex++ tweak enablement drifted for ${contract.tweak_id}`);
}

const state = readJson(contract.codex_plusplus_state_path || "", "Codex++ state");
const sourceTree = path.resolve(sourceRoot, "..", "..");
if (state.sourceRoot) {
  const stateSourceReal = realPath(state.sourceRoot, "state sourceRoot");
  const sourceTreeReal = realPath(sourceTree, "expected source tree");
  if (stateSourceReal && sourceTreeReal && !samePath(stateSourceReal, sourceTreeReal)) {
    fail(`Codex++ watcher sourceRoot drifted: ${state.sourceRoot}`);
  }
}

const selfUpdateState = readJson(contract.self_update_state_path || "", "self-update state");
if (selfUpdateState.sourceRoot) {
  const updateSourceReal = realPath(selfUpdateState.sourceRoot, "self-update sourceRoot");
  const sourceTreeReal = realPath(sourceTree, "expected self-update source tree");
  if (updateSourceReal && sourceTreeReal && !samePath(updateSourceReal, sourceTreeReal)) {
    fail(`Codex++ self-update sourceRoot drifted: ${selfUpdateState.sourceRoot}`);
  }
}

const manifest = readJson(path.join(sourceRoot, "manifest.json"), "manifest");
if (manifest.id !== contract.tweak_id) {
  fail(`manifest id drifted: ${manifest.id}`);
}
if (manifest.main !== "index.js") {
  fail(`manifest main drifted: ${manifest.main}`);
}
if (manifest.scope !== "both") {
  fail(`manifest scope drifted: ${manifest.scope}`);
}

const automationPath = path.join(sourceRoot, "automation.js");
const automationSource = fs.readFileSync(automationPath, "utf8");
[
  'item.priority === "P0"',
  'item.priority === "P1"',
  "selectAutoSubmitPrompts",
  "filterAutoSubmitQueueByBudget",
  "p0_p1_queue",
  "逐条提交",
  "followupMeta",
  "no_p0_or_p1",
  "unstructured_payload",
  "budgetPausePanelText",
].forEach((needle) => {
  if (!automationSource.includes(needle)) {
    fail(`automation.js is missing required contract token: ${needle}`);
  }
});

const indexPath = path.join(sourceRoot, "index.js");
const indexSource = fs.readFileSync(indexPath, "utf8");
[
  'id: "auto-follow-up-general"',
  'id: "auto-follow-up"',
  "function getFloatingPanelStatus()",
  "dataset.autoFollowupEnabled",
  "dataset.autoFollowupDepth",
  "dataset.autoFollowupMaxDepth",
  "自动提交:",
].forEach((needle) => {
  if (!indexSource.includes(needle)) {
    fail(`index.js is missing required UI contract token: ${needle}`);
  }
});

runNode(["--check", automationPath], "node --check automation.js");
runNode(["--check", indexPath], "node --check index.js");
runNode([path.join(sourceRoot, "tests", "automation-meta.test.js")], "automation-meta.test.js");
runNode([path.join(sourceRoot, "tests", "index-ui-init.test.js")], "index-ui-init.test.js");

if (failures.length > 0) {
  console.error("verify-auto-follow-up-contract: FAIL");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("verify-auto-follow-up-contract: PASS");
