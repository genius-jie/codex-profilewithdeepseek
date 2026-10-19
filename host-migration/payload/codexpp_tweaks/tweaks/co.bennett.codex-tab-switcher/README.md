# Codex Tab Switcher

A [Codex++](https://github.com/b-nnett/codex-plusplus) tweak that adds a full-screen `Ctrl+Tab` switcher for recent Codex chats.

It behaves like macOS app switching: hold Control, press Tab to cycle through recent chats, and release Control to switch.

<img width="2196" height="1726" alt="image" src="https://github.com/user-attachments/assets/5062df5e-93d9-49f5-ac4a-3477147c1ad3" />

## Features

- Full-screen recent chat overlay
- Shows the 5 most recent unique chats
- `Ctrl+Tab` cycles forward
- `Ctrl+Shift+Tab` cycles backward
- Release Control to switch to the selected chat
- `Escape` cancels
- Click or `Enter` switches immediately
- Tiny saved chat-pane previews
- Sidebar-style running spinner and unread indicator
- Preview storage is pruned to the current recent chats

## Install

Clone this repo into your Codex++ tweaks folder:

```sh
cd "$HOME/Library/Application Support/codex-plusplus/tweaks"
git clone https://github.com/b-nnett/codex-plusplus-tab-switcher.git codex-tab-switcher
```

Then reload Codex++ tweaks from Codex settings.

## Usage

Press `Ctrl+Tab` while Codex is focused.

The first item is the current chat. The first `Ctrl+Tab` press selects the second item so releasing Control switches to the previous recent chat.

## Preview Notes

Previews are captured from the visible chat pane. A chat needs to have been visited in the current window before it can have a real screenshot preview.

Captured previews are stored as compressed data URLs in Codex++ tweak storage and are kept only for the 5 recent chats.

## Manifest

```json
{
  "id": "co.bennett.codex-tab-switcher",
  "name": "Codex Tab Switcher",
  "version": "1.0.0",
  "githubRepo": "b-nnett/codex-plusplus-tab-switcher",
  "scope": "both",
  "main": "index.js"
}
```

## License

MIT
