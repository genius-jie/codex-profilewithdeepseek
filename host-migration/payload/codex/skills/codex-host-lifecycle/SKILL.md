---
name: codex-host-lifecycle
description: "Manage Codex host lifecycle boundaries for threads, goals, hooks, instruction files, skills, and automations. Use when a Codex-hosted object must be created, verified ready, operated, retired, or diagnosed without adding an Agent OS control plane."
---

# Codex Host Lifecycle

## Purpose

This Skill is the **execution companion** for the active
[`Codex Host Lifecycle Contract v1`](@@CODEX_HOME:win@@\contracts\codex-host-lifecycle-contract.yaml).
Codex host objects are outside Automation Core Runtime. The Contract defines
the lifecycle rule; this Skill selects the native Codex action and collects the
required evidence.

Authority is fixed: the Contract is the normative SSOT, this Skill is its
execution companion, and Automation prompts are thin consumers. A Prompt or
Skill wording conflict never overrides the Contract.

## Apply When

- A Thread, Goal, Hook, instruction file, Skill, or Automation is created, updated,
  checked for readiness, retired, or diagnosed.
- A Scope-bound cron needs to create, reuse, or retire a Review Thread.
- A native host action reports a concrete lifecycle fault.
- The ordinary Codex desktop start entry or its Manifest-selected Skill projection is changed or repaired.

## Execution Method

1. Read the Contract and select the one object class in scope.
2. Apply its `create`, `ready`, `operate`, or `retire` rule through the native
   Codex entrypoint named there.
3. Capture the Contract's required observable evidence before moving to the
   next operation.
4. Keep the target identity exact. For Review Threads, use
   `target_os + package_id + package_approval_sha256 + purpose=review`, rendered
   as `OS-REVIEW-CARD-v1|<target_os>|<package_id>|<package_sha256>|review`.

## Review Thread Presentation Flow

This section applies only to detached review tasks. General, Testing and Core
Heartbeats use **One Fixed OS Evolution Task** below.

1. Read the OS-local Tick first. A matching formal Decision advances to its
   returned action; `review_request_incomplete` creates no Review Thread. Chat
   text is never Decision Evidence.
2. For `review_card`, query the exact review marker in active Threads and then,
   only after a complete zero match, in archived Threads. Reuse one active
   match, respect any archived match, and stop on ambiguity or query failure.
3. When neither query matches, create one Review Thread with a visible
   `[AUTOMATION_REVIEW_BOOTSTRAP_V1]` carrying the exact review marker and the
   frozen `content_markdown`. It instructs the Agent to output that card and
   stop; the bootstrap is transport, not a Human Decision.
   Native Host entrypoints do not provide deterministic Agent-role static
   message injection, so the Agent presentation plus exact-read is the current
   minimal native path. The Agent may display Package-frozen 7+1 and
   anti-overdesign content, but must not perform a new audit or alter it.
4. Exact-read the Thread with turns. Apply the Contract's three ready proofs:
   an Agent message exists; it contains the same review marker, all OS-contract
   sections and exact decision strings; its turn has no tool or permission
   activity. If still pending, preserve the Thread and retry only exact-read.
5. A new Human reply matching an exact Package-ID/SHA choice invokes the
   OS-local formal Decision entry once with frozen static/raw SHA and required
   feedback. Report only `decision_ref`; Owner and Validator remain later Tick
   actions.
6. For later actions, exact-read the same active Thread and dedupe by the Tick's
   `action_key` plus immutable Decision/Evidence refs. Send only the existing
   Owner, Validator or result notification; do not execute that work.
7. After a terminal result is presented and read back, archive only that exact
   Review Thread. A Decision alone is not terminal.
8. If an exact archived match exists while the current Package action is still
   non-terminal, fail closed and ask the Human to restore that exact Thread.
   Do not unarchive it automatically and do not create a replacement.

Owner and Validator notifications have concrete consumers. `dispatch_to_owner`
is consumed by the exact ready Review Task's next Agent turn through the
Package-declared OS-local implementation entry. `validation_required` is
consumed through the Package-declared independent validation entry and must
bind the exact Owner Evidence. The cron only delivers these notifications.

## Native Entrypoints

Use the matching host entrypoint rather than direct storage edits:

- Thread: `create_thread`, `send_message_to_thread`, `set_thread_title`,
  `set_thread_archived`, and list operations. For an automation's thread
  discovery and every exact Thread read, use the Contract-declared read-only helper
  `@@CODEX_HOME:win@@\automation-tools\codex_host_thread_query.py`.
  The exact Thread read form is `--read-thread-id <exact-thread-id> --include-turns`.
  It uses the official `codex app-server --stdio` thread/list and thread/read
  protocols rather than a renderer callback, follows every list page, reports
  query completeness and match cardinality, returns every declared thread
  source, and does not edit the thread store.
- Native Thread prompts are always user-visible transport. There is no hidden
  assistant-message injection step in this Skill; the passive bootstrap causes
  the existing Review Task Agent to render the card, and exact-read verifies
  that Agent output without introducing a renderer, adapter or permission layer.
- A custom app-tool pipe/client/adapter is not an active Host entrypoint.
- Goal: current-task `create_goal` / `get_goal` / `update_goal`, or
  `@@CODEX_HOME:win@@\automation-tools\codex_host_thread_query.py
  --goal-thread-id <exact_thread_id>` for native app-server `thread/goal/get`
  readback. A Core Human Gate keeps an existing active Goal; it does not create a new task or send a
  second `turn/start`. Human confirmation itself begins the current task turn,
  which resumes the Core successor checkpoint in the same task.
- Automation: `automation_update`, followed by a read-back of the persisted
  definition.
- Hook, instruction, and Skill: their declared file entry plus the Contract's
  effective-load verification.
- Ordinary Host start projection: the fixed PowerShell 7 child call declared by
  `host_capability_projection`; keep the General writer unique, run it before
  Host start, preserve Manifest-external catalog entries, and report projection
  failure without redirecting ordinary Codex into the Codex++ profile.

## One Fixed OS Evolution Task

For the General, Testing, and Core recurring evolution automations, bind one
native Heartbeat to one fixed OS Task. That same visible Task carries periodic
Tick projection, Package review cards, exact Human choices, Owner/Validator
progress, and final results. Do not create a per-Package Review Task.

1. Keep the title fixed: `[GENERAL-OS] 自进化`, `[TESTING-OS] 自进化`, or
   `[CORE-OS] 自进化`. Status and Package topics stay in message bodies.
2. Every heartbeat reruns the OS-local formal Tick. Current Package state comes
   only from Package, Decision, Owner Evidence, Validation Evidence, and that
   Tick. Transcript history is Host Evidence and action-key dedupe context only.
   When a source OS already has an Evidence-backed Observation/Candidate, the
   same wake must deliver its bounded input reference to the existing local
   Experience Owner workflow before the Package projection. This handoff only
   wakes/routes the owner; semantic analysis, reflection and Package composition
   remain with the declared OS owner. The formal Tick stays read-only.
   The awakened Agent executes that existing Owner workflow in the same Task
   and records its native analysis/disposition before a fresh local projection.
   An owner label or a message saying "handed off" is not execution evidence.
   Use the linked `owner_execution` and `input_closure` contract for the result;
   notification dedupe never suppresses unfinished Owner work.
3. Multiplex Packages by `target_os + package_id + package approval SHA +
   action_key`. An exact Human choice advances only that Package revision.
4. Human text in the fixed Task becomes Decision Evidence only after the
   OS-local formal decide entry verifies the exact Package ID/SHA and writes the
   immutable Decision. Ordinary chat never authorizes Owner work.
5. After a formal owner action, the Agent in the same visible Task may assume
   the declared Owner role and link strict Owner Evidence. Validation uses a
   distinct Validator role or subagent and binds the exact Owner Evidence SHA;
   one role must not impersonate both producers.
6. Final and return actions are shown once in the same Task. Keep the Task
   active for later Packages; never archive it merely because one Package ends.
7. The invariant is exactly one active OS evolution Task, not permanent physical
   Thread identity. Target loss fails closed; the Host owner may explicitly
   archive the old Task and rebind the existing Automation to one replacement.
8. Never scan same-name Tasks and guess a replacement. Do not add an automatic
   rollover engine, Thread Registry, mapping database, worker, watcher, cleanup
   daemon, or second scheduler.
9. Heartbeat reuses the target Task's native model, reasoning, project, and cwd
   settings. Configure them through native Host controls; do not create a model
   registry or prompt-level authorization layer.
   The three OS lifecycle targets require `gpt-5.6-sol` with `xhigh`; verify the
   effective setting from an observed heartbeat turn, and do not change the
   Host-wide default merely to configure these three tasks.
   When a General input is incomplete, the existing General Owner may use its
   `complete-intake` entrypoint to update that same record after validation;
   Host lifecycle never creates a second record or Package for completion.
10. Verify adoption with the persisted heartbeat definition, one active target
    Task per OS, zero active per-Package Review Tasks, a fresh completed heartbeat
    turn, exact Package decision isolation, and distinct Owner/Validator Evidence.
11. Heartbeat only wakes an idle Task. After an exact Human Decision succeeds,
    continue in the same wake: fresh Tick → Owner → link Owner Evidence → fresh
    Tick → independent Validator → link Validation Evidence → fresh Tick → Final.
    Do not wait for another scheduled heartbeat between those deterministic steps.
12. Allow at most four in-memory transitions per wake and persist no loop counter.
    Continue only after a formal write changes the action/action_key. Stop on a
    Human Gate, identity drift, formal-entry/Owner/Validator failure, incomplete
    material, repeated action_key without progress, or a terminal action.
    Assess no progress after an actual Owner attempt or a concrete blocker.
    A stopped wake is not input closure. Only verified evolution or a reasoned
    native non-adoption disposition that exits the pending projection closes
    an input; preserve its original evidence and reason. Human wait, failure,
    missing material and return-to-proposal remain unfinished work.

## Core Goal Human-Gate Continuity

When a Codex task hosts an Automation Core long-running Goal, apply the
Contract's `objects.goal` rule exactly:

1. Start one Goal only after the Human explicitly asks for continuous work.
   Its terminal condition is Core `COMPLETE`/`STOPPED` or an explicit Human
   Goal clear; a Core `human` or `clarification` packet is never a Goal
   terminal condition.
2. At a Core Human Gate, leave the active Goal intact. Show the Decision card
   and wait for the exact Core response. Do not issue `goal/clear`, mark the
   Goal complete, start a second turn, or create a Cron/Heartbeat/Runner.
3. The Human reply already begins the same Codex task turn. Fresh-inspect the
   exact Human packet, render its complete `human_command_contract`, then
   commit the selected command through
   `@@SUITE_ROOT:win@@\bin\automation-core.cmd human-decision` with that
   exact checkpoint. This entry calls the existing `resume_pipeline()` CAS;
   it does not infer an upstream target from a bare word. When the successor
   is work/review, continue that same task's active Goal from the successor
   checkpoint.
4. A Human packet is a wait boundary, not a polling target. Do not generate
   repeated no-change continuation turns. If `return_upstream` has multiple
   legal targets, show the packet's complete target-bound choices once.
5. Treat a Goal UI pause or clear as an explicit Host decision. Do not revive
   it. If Goal readback is null, complete, blocked, or user-paused, report the
   Host fact rather than creating a replacement Goal.
6. Verify with the exact task's native `thread/goal/get`, Core `inspect`, and
   the successor checkpoint. The evidence must show one Codex task, one Core
   thread lineage, and no new runner task.

## Boundaries

- This Skill executes the Contract and applies its `non_goals` and
  `boundaries`; lifecycle rules remain in the Contract.
- Goal metadata is Host-only. Do not copy it into Core GraphState, checkpoint,
  SQLite, packet, request, continuation receipt, or an automation memory file.
- Distinguish a Core Human Gate from a user pressing the Goal pause control:
  the first pauses LangGraph only; the second is a Host instruction and remains
  respected. Only Core terminal facts or an explicit user clear retire a Goal.
