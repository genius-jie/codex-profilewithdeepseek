const EVENT_TYPES = ["keydown", "keyup", "keypress"];

let installed = false;

function isEscapeEvent(event) {
  return event && event.key === "Escape";
}

function stopEscape(event) {
  if (!isEscapeEvent(event)) return;
  event.stopImmediatePropagation();
  event.stopPropagation();
}

function addGuards() {
  for (const type of EVENT_TYPES) {
    window.addEventListener(type, stopEscape, true);
    document.addEventListener(type, stopEscape, true);
  }
}

function removeGuards() {
  for (const type of EVENT_TYPES) {
    window.removeEventListener(type, stopEscape, true);
    document.removeEventListener(type, stopEscape, true);
  }
}

module.exports = {
  start(api) {
    if (installed) return;
    installed = true;
    addGuards();

    api.settings.register({
      id: "main",
      title: "Disable Escape",
      description:
        "Escape key events are blocked in Codex renderer windows while this tweak is enabled.",
      render(root) {
        root.innerHTML =
          '<p style="margin:0;color:var(--color-token-text-secondary,inherit)">Escape key events are being consumed before Codex shortcut handlers can see them.</p>';
      },
    });

    api.log.info("renderer Escape guard active");
  },

  stop() {
    if (!installed) return;
    installed = false;
    removeGuards();
  },
};
