# SITREP: Reasoning & Exploration Fixes

## Current State: 2026-05-02

The tweak no longer contains or invokes an app-bundle patcher. Source-backed behavior
now follows the regular Codex++ shape:

- `index.js` owns the renderer settings page, live CSS, and the exploration
  fiber hook.
- `source-patcher.js` owns main-process source transformation.
- The main-process tweak wraps Electron's `protocol.handle("app", handler)`
  registration and patches matching JavaScript responses in memory.
- Source-backed setting changes are stored through the main-process tweak and
  schedule a Codex window reload when the already-loaded source needs to be
  refetched.
- Disable thinking animation also injects a narrow renderer CSS fallback so the
  current Thinking label stops shimmering before the reload completes.
- Unsupported source rules are reported back to the settings page and rendered
  as warnings near the affected toggle.

## Source-Backed Features

The source patcher currently targets these Codex chunks:

- `split-items-into-render-groups-*.js`
- `composer-*.js`
- `thinking-shimmer-*.js`

The strict rules preserve the old behavior set:

- render reasoning outside the exploration buffer
- let standalone reasoning items reach Codex's reasoning renderer
- keep reasoning expanded after thinking completes
- start reasoning expanded
- keep the agent item body expanded above the assistant response
- disable streaming blink
- optionally disable the thinking shimmer
- keep file-edit cards as standalone main-chat items instead of collapsed tool
  activity by classifying `patch` as recognized but non-groupable

`reasoning-full-expand` was intentionally not carried forward as a source rule
because the settings page already provides the same user-facing choice with live
CSS while preserving Scroll mode.

## Compatibility Model

Each source rule is exact-match and version-sensitive. When Codex serves a
target chunk, the patcher records one low-level status per rule:

- `active`
- `available`
- `bundled_active`
- `unsupported`
- `mixed`

The renderer groups low-level statuses by setting. If a selected setting depends
on an unsupported or mixed rule, that setting displays:

> This Codex version does not match the known source shape for this feature. The
> tweak likely needs an update.

This is deliberate. The tweak should fail visibly when Codex changes the
minified source shape instead of applying guessed replacements.

## Files

```text
manifest.json
index.js
source-patcher.js
README.md
SITREP.md
```
