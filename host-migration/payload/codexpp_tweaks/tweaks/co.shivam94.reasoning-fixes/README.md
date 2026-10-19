# Reasoning & Exploration Fixes

A [Codex++](https://github.com/b-nnett/codex-plusplus) tweak that patches Codex
Desktop's renderer JavaScript bundles at load time to keep reasoning,
exploration items, file edits, and tool outputs visible — with no app bundle
modifications.

> **New to the tweak?** See the [interactive explainer →](https://shivam2014.github.io/codex-plusplus-reasoning-fixes/) for
> a visual walkthrough: what it does, how source patching works, patch cards,
> and a v1.1 → v1.2 comparison with the full debugging timeline.

---

## Installation

```bash
git clone https://github.com/shivam2014/codex-plusplus-reasoning-fixes.git \
  ~/Library/Application\ Support/codex-plusplus/tweaks/co.shivam94.reasoning-fixes
```

For local development:

```bash
codexplusplus dev . --no-watch --replace
```

---

## Settings

All settings persist across restarts. Source-backed toggles take effect on the
next conversation reload. The UI shows a warning next to any toggle whose
source rule no longer matches the current Codex version.

| Section | Option | Default | Mechanism |
|---|---|---|---|
| Exploration | Keep accordion open | ON | React fiber hook (no reload) |
| Reasoning | Show reasoning | ON | Source patch (split-items) |
| Reasoning | Reasoning display | Expanded | CSS injection (no reload) |
| Reasoning | Disable thinking shimmer | ON | Source patch (shimmer) |
| File Edits | Show file edits in chat | ON | Source patch (split-items) |
| Exploration Items | Show exploration items | ON | Source patch (split-items) |
| Collapse | Show collapse/expand button | ON | DOM / CSS toggle (no reload) |

---

## Files

```
co.shivam94.reasoning-fixes/
├── manifest.json          # Tweak manifest (v1.2.0)
├── index.js               # Renderer settings UI, fiber hook, collapse-all button
├── source-patcher.js      # Main-process protocol-wrapper and source transformer
├── docs/
│   ├── index.html         # Interactive visual explainer
│   └── validate-html.mjs  # HTML validation script
├── SITREP.md              # Architecture notes, patch inventory, compatibility
└── screenshots/           # Settings page and reasoning view screenshots
```

---

## Patch reference

### Source patches (regex-based, applied at window reload)

| Patch | Bundle | What it does |
|---|---|---|
| `show-reasoning` | split-items | Reasoning items as standalone render items |
| `render-standalone-reasoning` | thread | Bypasses null-renderer branch for reasoning |
| `reasoning-start-expanded` | thread | `useState(o)` → `useState(true)` |
| `reasoning-no-autocollapse` | thread | Removes `setExpanded(false)` on finish |
| `reasoning-no-blink` | thread | Disables streaming blink on reasoning label |
| `reasoning-no-blink-fade` | thread | Removes `fadeType` animation |
| `reasoning-no-animate-height` | thread | Zero-duration height transition |
| `no-layout-position` | thread | Disables Framer Motion `layout:"position"` |
| `disable-shimmer` | shimmer | Stops the pulsing text animation |
| `show-exploration-items` | split-items | Standalone exploration entries |
| `fix-assistant-order` | split-items | Corrects agent-item message ordering |
| `file-edits-no-tool-group` | split-items | Keeps patches out of tool-activity grouping |
| `auto-expand-exec` | thread | `defaultExpandExecShell: true` |
| `expand-tool-activity` | thread | `defaultExpanded: true` on tool sections |

### Runtime features (no reload needed)

| Feature | How it works |
|---|---|
| Exploration keep-open | Wraps React fiber `useState` setter for accordion |
| Reasoning display style | Injected `<style>` overriding scrollbox height |
| Collapse-all button | CSS class toggle on `<body>` via floating DOM button |

### Compatibility

`inspectRule()` tests each patch rule against the served source:

| Status | Meaning |
|---|---|
| `not_applied` | Unpatched pattern found → replacement applied |
| `already` | Patched pattern present → skip (idempotent) |
| `unsupported` | Neither pattern matches → warning in UI |
| `mixed` | Ambiguous → treated as unsupported |

---

## Acknowledgments

- **Alex Naidis** ([TheCrazyLex](https://github.com/TheCrazyLex)) — in-memory
  protocol-level source patching architecture; file-edits, shimmer, and
  keep-agent-expanded patches (PR #2).
- **Codex++** ([b-nnett/codex-plusplus](https://github.com/b-nnett/codex-plusplus)) —
  tweak runtime, settings injection, IPC, and React fiber API.
- **Original patch** ([andrew-kramer-inno's gist](https://gist.github.com/andrew-kramer-inno/3fa1063b967cfad2bc6f7cd9af1249fd)) —
  inspiration for the source transformations.
