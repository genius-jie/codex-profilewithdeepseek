# Contributing: Fixing Codex UI Behavior via Source Patching

This documents the methodology used in v1.0. Read it before starting a new fix so
you don't retry approaches already ruled out in `docs/INVESTIGATION_LOG.md`.

## The Full Loop

### 1. Get the reference code

Always extract the current Codex ASAR before looking for patterns:

```bash
npx asar extract /Applications/Codex.app/Contents/Resources/app.asar /tmp/asar
```

The chunks you'll most often target live under `/tmp/asar/webview/assets/`:

| Chunk pattern | What it contains |
|---|---|
| `composer-*.js` | Turn renderer (`TF`), reasoning item renderer (`XM`), markdown renderer props |
| `split-items-into-render-groups-*.js` | Item categorizer (`ct`), render-group builder (`at`) |
| `thinking-shimmer-*.js` | Shimmer component for "Thinking" label |

### 2. Trace the data flow

Search the chunk for keywords matching what the user described (CSS class
names, prop names like `fadeType`, variable patterns, item types).

Key Codex variable naming patterns in minified code:

| Name pattern | Meaning |
|---|---|
| `o = !n.completed` | `isStreaming` (true while item is being generated) |
| `e.type === \`reasoning\`` | Item type check |
| `fadeType: o ? \`indexed\` : \`none\`` | Streaming animation control |
| `at` (function) | Render-group builder in split-items chunk |
| `ct` (function, exported as `Dp`) | Turn item categorizer |
| `r = []` | Result array being built |
| `i = null` | Current exploration buffer |

### 3. Design the regex patch

All patches live in the `PATCHES` object in `source-patcher.js`:

```javascript
"patch-name": {
    name: "descriptive_function_name",
    bundle: "composer",           // which chunk to target
    unpatched: /original_pattern/,
    patched: /expected_pattern_after_replacement/,
    replacement: "replacement_string",
},
```

**Critical rule:** the `replacement` string must NOT contain the `unpatched`
pattern as a substring. Otherwise `inspectRule()` returns `"mixed"` on the next
reload and the patch stops applying. Restructure the condition instead
(e.g. `_am.length>0` → `0<_am.length`).

**Bundle mapping** is in `bundleForUrl()`:
- `composer-*.js` → `"composer"`
- `split-items-*.js` → `"split-items"`
- `thinking-shimmer-*.js` → `"shimmer"`

### 4. Test the regex against the real chunk

Before committing, verify the regex matches exactly 1 occurrence:

```bash
python3 -c "
import re
t = open('/tmp/asar/webview/assets/composer-xxx.js').read()
u = re.compile(r'unpatched_pattern')
p = re.compile(r'patched_pattern')
print('unpatched:', len(u.findall(t)), 'patched:', len(p.findall(t)))
t2 = u.sub('replacement', t)
print('after replace - unpatched:', len(u.findall(t2)), 'patched:', len(p.findall(t2)))
"
```

Expected output: `unpatched: 1 patched: 0` → `after replace - unpatched: 0 patched: 1`

### 5. Wire it up

If the patch needs a toggle:
- Add the setting ID to `DEFAULTS` and `SETTING_FEATURES` in `source-patcher.js`
- Add the setting ID to `state.defaults` and the toggle UI in `index.js`
- Add the setting ID to the sync arrays in `index.js` (lines 489, 523)

If the patch is always-on (no toggle):
- Just add it to an existing `SETTING_FEATURES` list (e.g. `show-reasoning`)

### 6. Sync and restart

```bash
# Copy files to the tweaks directory Codex++ actually reads from
cp source-patcher.js ~/Library/Application\ Support/codex-plusplus/tweaks/co.shivam94.reasoning-fixes/
cp index.js ~/Library/Application\ Support/codex-plusplus/tweaks/co.shivam94.reasoning-fixes/

# Restart Codex
pkill -x "Codex" && sleep 2 && open /Applications/Codex.app
```

### 7. Test via CDP before deploying to the tweaks directory

Before asking the user to restart Codex, test changes on the running app:

```bash
# Open Codex with debug port
osascript -e 'quit app "Codex"' && sleep 2 && \
  open -a Codex --args --remote-debugging-port=9222

# Connect with agent-browser
npx agent-browser connect 9222

# Evaluate JavaScript in the renderer context
npx agent-browser eval 'document.querySelectorAll("[data-testid=...]").length'

# Or inject a test button/UI to preview changes before committing
npx agent-browser eval '(function() { /* test code */ })()'
```

This catches issues before they reach the tweaks directory.

### 8. When a source patch crashes the main process

The main process crashes on load when `source-patcher.js` has a syntax error.
The most common cause: **bare double quotes inside a double-quoted string**
in a `replacement` value:

```javascript
// BROKEN — kills Codex on startup
replacement: "V=...pb-0`,"data-reasoning-item":"true",children:...}"

// FIXED — escaped double quotes
replacement: "V=...pb-0`,\"data-reasoning-item\":\"true\",children:...}"
```

In the JavaScript source file, when the `replacement` string is evaluated,
`\"` produces `"` in the string VALUE, which is correct.

Always test with `node -e 'require("./source-patcher.js"); console.log("OK")'`
before deploying. A bad replacement string crashes the renderer.

### 9. When there's a tradeoff between two fixes

If removing one behavior reintroduces another (e.g. reordering fixes
single-pair but breaks multi-pair), don't toggle on/off — find the
**condition that distinguishes the two cases**. In v1.0 we used:
"only reorder when the first item is an output" instead of "always reorder"
or "never reorder".

## Architecture decisions

## Prefer CSS toggles over fiber dispatch for UI state

CSS-based toggles (a class on `document.body` that triggers `max-height: 0`,
`overflow: hidden`, `opacity: 0`) survive React re-renders, streaming updates,
and component unmount/remount cycles. Fiber dispatch
(`hook.queue.dispatch()`) changes React state temporarily, but gets overridden
when components re-render.

Use fiber dispatch only when React needs to actually process the state change
(e.g., collapsing a reasoning item affects its children rendering).

## Avoid source patches when DOM selectors work

Reasoning item headers can be identified by DOM structure:
`[class*="cursor-interaction"]` with a next sibling that has inline `opacity`
from framer-motion. No source patch needed. Use existing `data-testid`
attributes for exploration panels
(`[data-testid="exploration-accordion-body"]`).

Source patches are necessary when you need to add a new `data-*` attribute
or modify React props that affect rendering behavior.

## Settings toggle for every user-facing feature

Every feature the user can see or interact with should have a toggle in the
tweak settings. Pattern:

1. Add to `state.defaults` in `start()`
2. Add a `featureRow` in `renderSettings()`
3. Guard feature initialization with `readFlag(state.api, "id", default)`

## Lifecycle: cleanup in stop() for every injected feature

Any DOM element, event listener, or interval added during `start()` must be
removed in `stop()`. Store cleanup handles on `rendererState` (e.g.,
`rendererState._myCleanup = function() { ... }`) and call them in `stop()`.

## Icon selection for UI elements

Use semantically clear icons:
- **Collapse/expand**: `unfold-vertical` (arrows toward/away from center)
- Avoid directional chevrons (chevrons-up/down look like scroll-to-top/bottom)

## Branch & Release

```bash
git checkout -b fix/descriptive-name
# ... implement ...
git commit -m "description"
git checkout main && git merge fix/descriptive-name && git branch -d fix/descriptive-name
git push origin main
git tag v1.x.x   # after significant feature additions
```

Log failed attempts in `docs/INVESTIGATION_LOG.md` with the patch name,
why it was tried, and why it didn't work.
