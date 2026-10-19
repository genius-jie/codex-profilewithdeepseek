const assert = require("node:assert");
const path = require("node:path");

const sourcePath = path.resolve(__dirname, "..", "index.js");
const tweak = require(sourcePath);

const calls = [];
const fakeElement = () => ({
  style: { setProperty() {} },
  dataset: {},
  className: "",
  textContent: "",
  innerHTML: "",
  isConnected: true,
  appendChild() {},
  append() {},
  addEventListener() {},
  remove() {},
  setAttribute() {},
  getAttribute() {
    return "";
  },
});

global.HTMLElement = function HTMLElement() {};
global.document = {
  readyState: "complete",
  body: fakeElement(),
  documentElement: fakeElement(),
  createElement: fakeElement,
  addEventListener() {},
  removeEventListener() {},
  getElementById() {
    return null;
  },
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
};
global.window = {
  location: { pathname: "", hash: "", search: "", href: "" },
  addEventListener() {},
  removeEventListener() {},
};

let intervalCallback = null;
global.setInterval = (fn) => {
  intervalCallback = fn;
  return 1;
};
global.clearInterval = () => {};

tweak.start({
  process: "renderer",
  ipc: {
    async invoke() {
      return "globalThis.automation={run(){},cleanup(){},cancelCountdown(){return true},isCountingDown(){return false}};";
    },
  },
  storage: {
    get(_key, fallback) {
      return fallback;
    },
    set() {},
  },
  settings: {
    register(options) {
      calls.push(["register", options.id]);
    },
    registerPage(options) {
      calls.push(["registerPage", options.id]);
      return { unregister() {} };
    },
  },
  log: {
    info(...args) {
      calls.push(["info", args[0]]);
    },
    warn(...args) {
      calls.push(["warn", args[0]]);
    },
    error(...args) {
      calls.push(["error", args[0]]);
    },
  },
});

setTimeout(() => {
  assert.ok(calls.some((call) => call[0] === "register" && call[1] === "auto-follow-up-general"));
  assert.ok(calls.some((call) => call[0] === "registerPage" && call[1] === "auto-follow-up"));
  assert.ok(!calls.some((call) => call[0] === "error"));
  assert.equal(typeof intervalCallback, "function");
  tweak.stop();
  console.log("index-ui-init.test.js: PASS");
}, 0);
