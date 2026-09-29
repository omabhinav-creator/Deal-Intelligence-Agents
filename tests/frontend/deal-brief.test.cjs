const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function element() {
  const listeners = new Map();
  return {
    listeners,
    children: [],
    disabled: false,
    hidden: false,
    addEventListener(type, listener) {
      const handlers = listeners.get(type) || [];
      handlers.push(listener);
      listeners.set(type, handlers);
    },
    setAttribute() {},
    removeAttribute() {},
    appendChild(child) { this.children.push(child); },
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
  };
}

test("Deal Brief button has one handler and no second integration request", async () => {
  const root = path.resolve(__dirname, "../..");
  const briefScript = fs.readFileSync(
    path.join(root, "Front End/assets/JS/deal-brief.js"),
    "utf8",
  );
  const integrationScript = fs.readFileSync(
    path.join(root, "Front End/assets/JS/integration.js"),
    "utf8",
  );
  const button = element();
  const panel = element();
  const content = element();
  const closeButton = element();
  const panelMount = {
    set innerHTML(_value) {},
    querySelector(selector) {
      return {
        "#dealBriefPanel": panel,
        "#dealBriefContent": content,
        ".deal-brief-panel__close": closeButton,
      }[selector];
    },
  };
  let apiCalls = 0;
  const window = {
    location: { search: "" },
    DealMindAPI: {
      getSelectedDeal: () => null,
      request: async () => { apiCalls += 1; },
    },
  };
  const document = {
    getElementById: (id) => id === "dealBriefPanelMount" ? panelMount : null,
    querySelectorAll: (selector) => selector === "[data-deal-brief-trigger]" ? [button] : [],
    createElement: () => element(),
  };

  vm.runInNewContext(briefScript, { window, document, URLSearchParams });

  assert.equal(button.listeners.get("click").length, 1);
  assert.doesNotMatch(
    integrationScript,
    /api\.request\(`\/api\/deals\/\$\{encodeURIComponent\(deal\.id\)\}\/brief`\)/,
  );
  await button.listeners.get("click")[0]();
  assert.equal(apiCalls, 0, "missing deal selection must not make an API request");
  assert.equal(button.disabled, false);
});
