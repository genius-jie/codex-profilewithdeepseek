---
domain: codex-plusplus
tier: L0
doc_status: active-reference
related:
  - @@CODEXPP_HOME:win@@\AGENTS.md
  - @@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1
  - @@CODEXPP_HOME:win@@\config.toml
birth_ceremony_id: bc-codexplusplusconfig-agents-reference-20260522
birth_ceremony_date: 2026-05-22
---

# Codex++ Launcher Directory Entry

## Current D-only runtime boundary (2026-09-22)

The active Codex++ mutable data route is physical @@CODEXPP_PROFILE:win@@:

- CODEX_HOME: @@CODEXPP_HOME:win@@
- runtime and tweaks: @@CODEXPP_RUNTIME:win@@
- OpenCLI adapters: @@CODEXPP_PROFILE:win@@\.opencli\clis
- Electron user-data-dir: @@CODEXPP_PROFILE:win@@

The former C Profile/runtime/source entries and old D-side reparse paths are
retired. @@CODEX_HOME:win@@,
the Windows Store app mirror, General OS SSOT, and external OpenClaw state
remain outside this Codex++ mutable-data boundary.

This launcher directory is part of the Codex++ isolated environment.

The live Codex++ profile overlay and prompt instructions are maintained at:

`@@CODEXPP_HOME:win@@\AGENTS.md`

Do not duplicate the full overlay here. This file exists only to keep
`@@LAUNCHER_ROOT:win@@` discoverable as a Codex++
entry surface and to prevent the launcher directory from looking ungoverned.

Operational boundary:

- Codex++ HOME and Electron user-data-dir are the physical `@@CODEXPP_PROFILE:win@@`; no C Profile alias is part of the runtime.
- Codex++ config is `@@CODEXPP_HOME:win@@`.
- Codex++ launcher scripts live in `@@LAUNCHER_ROOT:win@@`.
- Ordinary Codex config at `@@CODEX_HOME:win@@` is a separate surface and must not be modified unless the user explicitly names ordinary Codex.
- The Codex++ profile is a physical D directory with no C alias or runtime Junction. Start and the sole maintenance writer Sync must verify the D root and nested `.codex` before their first write; Repair/Updater stay thin and enter through Sync. Any reparse path must fail closed before ordinary Codex or another directory can be touched.
- Codex++ supports dual authentication modes: Official Account Mode (`# model_provider = "cm"` + `auth_mode = "chatgpt"`) and CodexManager Proxy Mode (`model_provider = "cm"` + `auth_mode = "apikey"`). Never force proxy mode when the user is using official account login.
- When launching or testing Codex++ GUI from an agent shell, always target `WinSta0\Default` via Win32 `CreateProcess`. Never allow GUI processes to run in the background `exebox-*` virtual desktop.

Host Capability Projection boundary:

- Before changing any Codex++ start, one-shot update, basic repair, desktop shortcut, or launcher file, read `@@CODEXPP_HOME:win@@\skills\S34_Codex认证切换\SKILL.md`, especially `Host Capability Projection 生命周期调用契约`. S34 is only the lifecycle caller contract; it does not own or duplicate the publication schema, eligibility rules, or Junction algorithm.
- General OS Publication Policy/Manifest has one SSOT: `@@GENERAL_ROOT:win@@\control\host-capability-publication-manifest.yaml`. Canonical Skill bodies have one root: `@@GENERAL_ROOT:win@@\assets\skills`.
- The graph is fixed at `lifecycle_ingress_count=3`, `direct_projection_caller_count=2`, and `projection_writer_count=1`. Start and Sync call the General-owned `@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1` directly; Repair is a thin Sync proxy and this Host directory must not retain a writer copy. `Protect-CodexPlusPlusGovernance.ps1` must derive these counts from active files, not hard-code a passing result.
- The writer is stateless and idempotent and performs only `Manifest -> canonical Skill root -> Host Junction`, while preserving entries outside the Manifest. A directory, file, or unknown-target Junction collision blocks overwrite of that item and is reported; it is not a Host-global gate and must not block unaffected entries or basic start/repair.
- Never restore `skills/extraRoots` Replay, a Host adapter tweak, activation/cutover/rollback, an Adapter-specific ASAR baseline, a background worker/loop/watchdog, generation/journal/receipt/state, or transaction fixtures as a production dependency.
- Manifest-selected canonical Junctions are the formal projection. Do not delete them, move them into a rollback package, or copy Skill bodies into a second tree.
- The only physical PowerShell executable for formal launch and maintenance calls is `@@POWERSHELL_EXE:win@@`. PATH lookup and aliases are forbidden. CMD entrypoints must preserve the child `%ERRORLEVEL%` with `exit /b %CODEXPP_EXIT%`.
- Basic repair remains independent: resolve the current official package, repair only the Codex++ fixed store, and never touch ordinary Codex. Chrome Native Messaging Host restoration remains compare-and-set through `Restore-CodexPlusPlusNativeMessagingHost.ps1`; session-path normalization must not own that registry state.
- `Sync-CodexPlusPlusLatest.ps1` is the sole one-shot owner of native repair cleanup. Keep exactly the current official package mirror. An old direct child of the fixed `store-apps` root may be removed only when it is a recognized physical `OpenAI.Codex_*` directory, is not the current package, and no process executable is inside it. Start calls this owner only when the current store is missing, injection has drifted, or `-ForceRepair` is explicit; a healthy restart must not run full `/MIR`. Repair remains a thin Sync proxy.
- Native installer source replacement has one external, one-shot owner: `Update-CodexPlusPlusInstaller.ps1`. Keep `codexPlusPlus.autoUpdate=false`; scheduled installer watcher tasks and `watcher.cmd`/`watcher.vbs` must remain absent. The updater alone may call native `update --no-repair`, then reapply the PowerShell 7 overlay, build, run targeted tests, force the app lifecycle repair, validate the boundary, and delete the transient `source.previous` rollback copy.
- The two public CLI shims must exactly match `CodexPlusPlus-ControlledCliShim.cmd.template`, and their WindowsApps links must target those runtime shims. `update`, `self-update`, and `repair` route to controlled one-shot entries. Public `install` is blocked because native install defaults to creating a watcher and rewrites launchers. A controlled first install may call the fixed Node/native CLI with `install --no-watcher` only under S34, followed immediately by `Sync-CodexPlusPlusLatest.ps1 -Once -ForceRepair` and the manual lifecycle audit.
- `@@CODEXPP_SOURCE:win@@.previous*` is transient rollback material, not a retained archive. After a successful controlled update it must be absent. The WCU tweak is a physical Store deployment protected from silent auto-overwrite by its local-change fence; manual uninstall/reinstall is a reviewed S34 operation because it can remove the PowerShell 7 migration.
- Installer source has one identity: canonical `@@CODEXPP_SOURCE_PARENT:win@@`; `@@CODEX_HOME:win@@-plusplus` is retired and must not be recreated. All managed writes, hashes, logs, audit and rollback use D. `Test-CodexPlusPlusTweakLinks.ps1` is read-only; never restore the retired startup-time backup-copy writer `Repair-CodexPlusPlusTweakLinks.ps1`.
- The only user launcher is physical `@@USERPROFILE:win@@\Desktop\Codex++ 启动.lnk` targeting `Start-CodexPlusPlus-Proxy.vbs`. The vbs shim runs the fixed PowerShell 7 launch chain in a hidden window (no console flash) and shows an error dialog only on a nonzero exit; `Start-CodexPlusPlus-Proxy.cmd` stays as the visible-console diagnostic entry. Native installer shortcuts named `Codex++.lnk` are removed only after their target is proven to be a Codex/ChatGPT executable inside the fixed Codex++ store. `Protect-CodexPlusPlusGovernance.ps1` is a manual read-only audit, never a Host startup gate.
- The desktop entry guard has three outcomes: wake the healthy running instance and exit; fall through into the designed startup cleanup and relaunch when no main window can be presented (window-crashed residue); or proceed with a fresh start. `-Restart` forces the cleanup-and-relaunch path. A healthy running instance is never stopped by a repeated click.
- Session SQLite access remains fixed to `@@CODEXPP_PROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` plus `@@LAUNCHER_ROOT:win@@\Invoke-CodexPlusPlusSqlite.py`. The helper accepts only canonical `@@CODEXPP_HOME:win@@\state_5.sqlite`; C aliases are rejected, and ordinary Codex is rejected before database open.
- Background `Watch-CodexPlusPlusSessionPaths.ps1 -Watch` is retired and the expected live count is zero. The legacy filename may run only one explicit maintenance batch; SQLite triggers, cold storage, and the reader remain independent session-lifecycle capabilities and must not grow into another watcher, PID file, or state machine.
- Completion verification must use `PASS_WITHIN_DECLARED_SCOPE` and enumerate the checked files, commands, runtime version, and unobserved paths. It means no known unregistered debt inside that scope; it never means that future upstream versions or unexecuted paths have no hidden debt.
- Workspace `.codex-evidence/**/*.json` files are consumable Hook failure-review receipts, not durable General/Host Evidence. After the matching pending item is cleared by a passing rerun or S12/W9 receipt they need not be restored; durable conclusions belong to the real owner's Evidence path, and immutable history is corrected additively.
- Profile identity remains the fixed Codex++ store executable plus exact isolated physical `--user-data-dir=@@CODEXPP_PROFILE:win@@`; maintenance commands are not profile owners. The D profile and nested `.codex` must be physical directories and validated before writes.

Git status probe boundary:

- This launcher directory and the Codex++ profile config directory are not Git worktrees.
- Use `@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusGitStatus.ps1` for Git status probes on Codex++ launcher/profile paths.
- Expected non-Git output is `NOT_GIT_WORKTREE` with exit code 0; do not use raw `git status --short` failure here as worktree evidence.

Stop Guard and Follow-up boundary:

- Stop Guard runs first and only decides whether the current atomic task is genuinely closed.
- Follow-up runs after Stop and only proposes project-level continuation candidates.
- Follow-up candidates must not be used to smuggle unfinished current-task work past Stop Guard.
- Follow-up must not recommend Git staging, "纳入版本范围", or "提交前审计" just because a deliverable was created; version-control bookkeeping is a candidate only when the user explicitly asks for it or it is the current task's acceptance gate.
- Hook interruptions are normal quality feedback. Resolve the evidence and continue; do not route around the hook.
- Do not shrink a valid Follow-up payload or omit useful continuation candidates merely to avoid interception.
