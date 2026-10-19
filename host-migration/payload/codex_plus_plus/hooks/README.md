---
domain: codex-plusplus
tier: L1
doc_status: active-reference
status: active
related:
  - '@@CODEXPP_HOME:win@@\AGENTS.md'
  - '@@CODEXPP_HOME:win@@\hooks\stop_guard.py'
  - '@@CODEXPP_HOME:win@@\hooks\post_tool_use_audit.py'
  - '@@CODEXPP_HOME:win@@\hooks\hook_common.py'
  - '@@CODEXPP_HOME:win@@\hooks\tests\test_stop_guard.py'
birth_ceremony_id: bc-codexpphooksreadme-8a7d2c6f
birth_ceremony_date: 2026-05-20
---

# Codex++ Hook Maintenance Notes

This file records maintenance rules for the Codex++ isolated hook runtime at `@@CODEXPP_HOME:win@@\hooks`.

Scope boundary:

- This note applies to Codex++ only.
- Do not sync changes into ordinary Codex at `@@CODEX_HOME:win@@\hooks` unless the user explicitly names ordinary Codex or a shared SSOT requires it.
- Runtime truth is the hook code, tests, and hook-state evidence under the Codex++ profile.

## Codex++ / Ordinary Codex Sync Boundary Checklist

Current snapshot as of 2026-05-20:

- Identical hook code in both profiles: `hook_common.py`, `hook_runner.py`, `permission_request_guard.py`, `pre_tool_use_guard.py`, and `session_start_context.py`.
- Divergent hook code: Codex++ `stop_guard.py` includes Stop-before-Follow parsing and transcript fallback that ordinary Codex does not currently have.
- Divergent hook code: Codex++ `post_tool_use_audit.py` includes semantic failure-fingerprint keys for boolean spelling variants that ordinary Codex does not currently have.
- Divergent config: `hooks.json` exists in both profiles but contains profile-specific absolute paths and must not be copied across profiles.
- Codex++ local-only maintenance doc: this `README.md` has no ordinary Codex counterpart.

Default decision rule:

- Patch Codex++ first when the defect appears in a Codex++ session, hook-state file, transcript, Follow-up panel, or profile-specific runtime.
- Inspect ordinary Codex before declaring a shared hook fix complete, but do not edit it unless the user explicitly names ordinary Codex or the defect is proven to live in shared hook logic.
- Treat Python hook logic as sync-candidate material only after checking profile schema, profile HOME, hook-state layout, and live event shape for both profiles.
- Treat `hooks.json`, hook-state files, session logs, cache directories, plugin tweak files, auth/proxy settings, and Codex++ identity docs as profile-owned material, not sync targets.
- Keep human-readable pending fingerprints stable while adding machine-readable comparison keys where needed; do not rewrite old evidence strings just to make profiles look symmetrical.

Safe sync candidates after review:

- Pure classifier fixes in `hook_common.py`, `stop_guard.py`, `post_tool_use_audit.py`, `pre_tool_use_guard.py`, `permission_request_guard.py`, and `session_start_context.py`.
- Tests that encode shared behavior such as structured tool failure handling, Stop receipt parsing, pending-state closure, and W1 prompt gates.
- Windows shell robustness fixes that do not depend on Codex++ HOME, CodexManager, Follow-up UI, plugin storage, or profile-specific tool paths.

Do not sync blindly:

- `@@CODEXPP_HOME:win@@\hooks.json` to `@@CODEX_HOME:win@@\hooks.json`, or the reverse.
- Any path containing `CodexPlusPlusProfile`, CodexManager provider assumptions, isolated `auth.json`, `CODEX_HOME`, `USERPROFILE`, or profile-local `Path.home()` behavior.
- `hook-state`, `sessions`, `archived_sessions`, `logs`, `cache`, and runtime receipt artifacts.
- Codex++ Follow-up tweak/plugin behavior unless ordinary Codex has the same plugin and the same panel-to-prompt injection path.
- Documentation that identifies the executor as Codex++ or assumes Codex++ startup/authentication rules.

Required review before syncing a hook fix:

- Confirm the event schema in both profiles, especially Stop output shape and whether `continue + decision:block + reason` is valid.
- Confirm pending-state keys and file locations for both profiles.
- Confirm whether the defect came from visible assistant prose, a tool event, a hook-state file, a transcript fallback, or a UI plugin layer.
- Confirm that any new code avoids profile-specific absolute paths unless they are intentionally injected by `hooks.json`.
- Confirm the ordinary Codex tree has the same tests or add a profile-local probe before changing behavior.

Verification checklist after any sync:

- Run `python -m py_compile` on every touched hook file in each modified profile.
- Run the profile-local unit/probe tests for the touched hook surface.
- Rerun the exact failed command or Stop/UserPromptSubmit replay that justified the change.
- Inspect the profile-local pending state and confirm unresolved keys are absent or explicitly explained.
- Recheck `hooks.json` after edits and verify every command still points to the intended profile directory.

## Stop-before-Follow Boundary

Stop Guard runs before the Codex++ Follow-up UI layer is acted on. Therefore Stop Guard must classify only the assistant's visible final answer and live pending hook state. It must not treat the Follow-up payload as unresolved work.

Maintenance contract:

- Strip the fenced JSON block whose payload contains `codex_follow_up: true` before any unresolved-action scan.
- Do not block solely because the Follow-up payload has `task_complete: false`, `P0`, `P1`, `P2`, or concrete prompt text.
- Do not scan Follow-up items as if they were assistant promises, deferred work, or pending execution commands.
- A valid Follow-up payload can contain useful clickable continuations while Stop still allows completion.
- If Stop blocks, the reason must come from visible final prose, live pending hook state, invalid completion receipt, or an actual unresolved tool failure.

Allowed Stop blockers:

- The visible final answer says the current requested work is still pending or intentionally deferred.
- Hook state contains unresolved `pending_failure_review`, `pending_w1_review`, or another active pending key.
- The required completion receipt is missing, invalid, or contradicts the visible outcome.
- A tool failure remains unresolved and has no S12/W9 evidence.

Disallowed Stop blockers:

- Follow-up item text after `codex_follow_up: true`.
- Follow-up priorities such as `P0` or `P1`.
- Follow-up `task_complete: false` by itself.
- A visible explanation that says the Follow-up payload is optional or post-completion.

Regression probes:

```powershell
python -m py_compile @@CODEXPP_HOME:win@@\hooks\stop_guard.py
python @@CODEXPP_HOME:win@@\hooks\tests\test_stop_guard.py
```

A live replay final that contains a valid completion receipt followed by a fenced `codex_follow_up` JSON block must return no Stop output and must not mention Follow-up as the block reason.

The replay must also cover this real Codex++ shape:

- The `codex_follow_up` fenced JSON block is followed by another machine-readable block such as `<oai-mem-citation>`.
- `STOP_COMPLETION_RECEIPT` appears as inline code or without a colon after the marker.
- Visible explanatory prose may mention terms such as `pending hook state`, `Stop blocker`, or `codex_follow_up`; those terms are not unresolved work when the completion receipt is valid.
- Stop hook event payloads may truncate `last_assistant_message`; when `transcript_path` is present, recover the full assistant final by matching the truncated prefix against the session log before parsing receipts.
- Placeholder examples such as `STOP_COMPLETION_RECEIPT {"..."}` are not receipts.

## Failure Fingerprint Normalization

PostToolUse and Stop must preserve the human-readable command fingerprint while using a semantic comparison key for boolean spelling variants such as `False` and `false`. This prevents the same failed command from staying pending only because Python source text and JSON text spell booleans differently.

Maintenance contract:

- Display the original command fingerprint when reporting pending state.
- Compare rerun evidence through the normalized semantic key.
- Prefer structured tool status over raw source-text keywords when deciding whether a command failed.
- Treat resolved pending state as closed only after a passing rerun or explicit S12/W9 evidence.
