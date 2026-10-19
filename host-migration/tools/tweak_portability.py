"""Export-only path fixes for the existing Auto Follow-up verification entry."""
from __future__ import annotations

import json

AUTO_ID = "com.lobster.auto-follow-up"
COPY_MODE = "source_or_identical_copy"


def transform_tweak(label, text):
    roots = ("codexpp_source/tweaks/auto-follow-up/", "codexpp_tweaks/" + AUTO_ID + "/")
    prefix = next((root for root in roots if label.startswith(root)), None)
    if prefix is None:
        return text, []
    relative = label[len(prefix):]
    if relative == "auto-follow-up.contract.json":
        obj = json.loads(text)
        obj.update({
            "source_path": "@@CODEXPP_SOURCE:escaped@@\\tweaks\\auto-follow-up",
            "installed_path": "@@CODEXPP_RUNTIME:escaped@@\\tweaks\\" + AUTO_ID,
            "codex_plusplus_config_path": "@@CODEXPP_RUNTIME:escaped@@\\config.json",
            "codex_plusplus_state_path": "@@CODEXPP_RUNTIME:escaped@@\\state.json",
            "self_update_state_path": "@@CODEXPP_RUNTIME:escaped@@\\self-update-state.json",
            "required_install_realpath": COPY_MODE,
            "required_companion_tweak_id": "co.Arconte112.followup",
        })
        return json.dumps(obj, ensure_ascii=False, indent=2) + "\n", ["bind Auto Follow-up verification to the selected isolated source/runtime and identical packaged copies"]
    if relative != "scripts/verify-auto-follow-up-contract.js":
        return text, []
    if "// Host migration: allow an identical physical snapshot." in text:
        return text, []
    old = '''const sourceReal = realPath(sourceRoot, "source root");
const expectedSourceReal = realPath(contract.source_path || "", "contract source_path");
if (sourceReal && expectedSourceReal && !samePath(sourceReal, expectedSourceReal)) {
  fail(`contract source_path drifted: expected ${expectedSourceReal}, running ${sourceReal}`);
}

const installedReal = realPath(contract.installed_path || "", "installed tweak path");
if (installedReal && sourceReal && !samePath(installedReal, sourceReal)) {
  fail(`installed tweak path is not linked to source: installed realpath ${installedReal}, source ${sourceReal}`);
}'''
    new = '''// Host migration: allow an identical physical snapshot.
const sourceReal = realPath(sourceRoot, "source root");
const expectedSourceReal = realPath(contract.source_path || "", "contract source_path");
const installedReal = realPath(contract.installed_path || "", "installed tweak path");
const packagedCopy = contract.required_install_realpath === "source_or_identical_copy";
if (sourceReal && expectedSourceReal && !samePath(sourceReal, expectedSourceReal)
    && !(packagedCopy && installedReal && samePath(sourceReal, installedReal))) {
  fail(`contract source_path drifted: expected ${expectedSourceReal}, running ${sourceReal}`);
}
if (installedReal && expectedSourceReal && packagedCopy) {
  const files = ["manifest.json", "index.js", "automation.js", "auto-follow-up.contract.json",
    "package.json", "scripts/verify-auto-follow-up-contract.js",
    "tests/automation-meta.test.js", "tests/index-ui-init.test.js"];
  for (const name of files) {
    try {
      if (!fs.readFileSync(path.join(installedReal, name)).equals(fs.readFileSync(path.join(expectedSourceReal, name)))) {
        fail(`installed packaged copy differs from source: ${name}`);
      }
    } catch (error) {
      fail(`packaged file is missing or unreadable: ${name}`);
    }
  }
} else if (installedReal && sourceReal && !samePath(installedReal, sourceReal)) {
  fail(`installed tweak path is not linked to source: installed realpath ${installedReal}, source ${sourceReal}`);
}'''
    if old not in text:
        raise ValueError("Auto Follow-up verification source changed; review before exporting")
    text = text.replace(old, new)
    text = text.replace("if (repair) {", '''if (repair && contract.required_install_realpath === "source_or_identical_copy") {
  console.error("Packaged migration copies use read-only verification; repair is a separate developer-link operation.");
  process.exit(1);
}

if (repair) {''', 1)
    text = text.replace('const state = readJson(contract.codex_plusplus_state_path || "", "Codex++ state");', '''// Install/update state is created by the target installer, never copied from the old host.
function readNativeState(filePath, label) {
  return filePath && fs.existsSync(filePath) ? readJson(filePath, label) : {};
}
const state = readNativeState(contract.codex_plusplus_state_path, "Codex++ state");''')
    text = text.replace('const sourceTree = path.resolve(sourceRoot, "..", "..");', 'const sourceTree = path.resolve(contract.source_path || sourceRoot, "..", "..");')
    text = text.replace('const selfUpdateState = readJson(contract.self_update_state_path || "", "self-update state");', 'const selfUpdateState = readNativeState(contract.self_update_state_path, "self-update state");')
    marker = 'const state = readNativeState(contract.codex_plusplus_state_path, "Codex++ state");'
    text = text.replace(marker, '''if (contract.required_companion_tweak_id && config.tweaks?.[contract.required_companion_tweak_id]?.enabled !== true) {
  fail(`required Follow-up companion is disabled: ${contract.required_companion_tweak_id}`);
}
''' + marker)
    return text, ["verify identical installed snapshots through the existing entry; keep target install state local and block developer-link repair on migration copies"]
