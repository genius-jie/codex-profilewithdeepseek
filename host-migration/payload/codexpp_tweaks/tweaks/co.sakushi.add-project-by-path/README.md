# Add Project by Path

![Add Project by Path menu and modal](assets/add-project-by-path.jpg)

Add Project by Path is a [Codex++](https://github.com/b-nnett/codex-plusplus) tweak that adds a native-looking **Enter project path** action to Codex's project menu.

It lets you add a project without opening the system folder picker. Paste a path, drop a folder, or reuse a shell command like `cd /path && ...`, and Codex adds that folder as the active project.

## Features

- Add projects from a typed local path
- Paste `file://` URLs or shell commands like `cd /path && ...`
- Drag and drop a folder onto the modal
- Expand `~` to your home directory
- Automatically create the target folder when it does not exist
- Show precise validation errors for permissions, files, relative paths, read-only locations, and broken paths
- Use Codex-style UI so the action feels native in the project menu

## Install

Clone this repository into your [Codex++](https://github.com/b-nnett/codex-plusplus) tweaks directory:

```sh
cd "$HOME/Library/Application Support/codex-plusplus/tweaks"
git clone https://github.com/ImSakushi/codex-plusplus-add-project-path.git co.sakushi.add-project-by-path
```

Then enable **Add Project by Path** from [Codex++](https://github.com/b-nnett/codex-plusplus) Tweaks.

## Configure

Open Codex's project menu and choose **Enter project path**. Paste a folder path or drop a folder into the modal, then confirm to add it as the active Codex project.

The tweak accepts absolute paths, `~/` paths, `file://` URLs, and common copied terminal commands. Relative paths are rejected so Codex does not add the wrong folder by accident.
