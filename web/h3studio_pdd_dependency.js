import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TARGET = "H3StudioModelSetup";
const STATUS_URL = "/h3studio/dependencies/status";
const INSTALL_URL = "/h3studio/dependencies/pdd/install";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const className = (node) => String(node?.comfyClass || node?.type || "");

async function jsonFetch(path, options = {}) {
  const response = await api.fetchApi(path, options);
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!response.ok || data?.ok === false) throw new Error(data?.error || text || `HTTP ${response.status}`);
  return data;
}

async function dependencyInstalled() {
  try {
    const status = await jsonFetch(STATUS_URL);
    return Boolean(status?.pdd?.installed);
  } catch {
    return false;
  }
}

function log(node, text) {
  const target = node?.__h3ModelSetup?.root?.querySelector?.("[data-log]");
  if (target) target.textContent = text;
}

function badge(node, installed) {
  const root = node?.__h3ModelSetup?.root;
  const target = root?.querySelector?.(".h3ms-pdd-links .h3ms-pdd-badge");
  if (!target || /PDD node loaded/i.test(target.textContent || "")) return;
  target.textContent = installed ? "PDD node installed · restart" : "PDD node missing";
  target.classList.toggle("ok", installed);
  target.classList.toggle("warn", !installed);
}

async function installDependency(node) {
  if (node.__h3PddDependencyReady || await dependencyInstalled()) {
    node.__h3PddDependencyReady = true;
    badge(node, true);
    return;
  }
  if (node.__h3PddDependencyInstalling) {
    while (node.__h3PddDependencyInstalling) await sleep(100);
    if (!node.__h3PddDependencyReady) throw new Error("PDD dependency install did not complete.");
    return;
  }
  node.__h3PddDependencyInstalling = true;
  log(node, "Installing the Mamad8 PDD custom node first…");
  try {
    const result = await jsonFetch(INSTALL_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    node.__h3PddDependencyReady = true;
    badge(node, true);
    log(node, `PDD custom node ${result.action || "installed"}. Installing the selected LoRA + heads pair now…`);
  } finally {
    node.__h3PddDependencyInstalling = false;
  }
}

function attach(node) {
  if (!node || className(node) !== TARGET || node.__h3PddDependencyHooked) return;
  const wait = () => {
    const root = node?.__h3ModelSetup?.root;
    if (!root) { setTimeout(wait, 50); return; }
    node.__h3PddDependencyHooked = true;

    dependencyInstalled().then((installed) => {
      node.__h3PddDependencyReady = installed;
      if (installed) badge(node, true);
    });

    // Model Setup and the Smart PDD panel both rerender their own markup. Keep
    // the dependency badge truthful even after those remounts.
    const observer = new MutationObserver(() => {
      if (node.__h3PddDependencyReady) queueMicrotask(() => badge(node, true));
    });
    observer.observe(root, { childList: true, subtree: true });
    node.__h3PddDependencyObserver = observer;

    root.addEventListener("click", async (event) => {
      const button = event.target?.closest?.("[data-pdd-install],[data-pdd-repair]");
      if (!button || button.dataset.h3DependencyResume === "1") {
        if (button) delete button.dataset.h3DependencyResume;
        return;
      }
      if (node.__h3PddDependencyReady) return;

      // Capture the original click before the weight installer handles it. Once
      // the fixed PDD repo is present, replay the exact button click so the
      // existing UAD pair installer continues unchanged.
      event.preventDefault();
      event.stopImmediatePropagation();
      button.disabled = true;
      try {
        await installDependency(node);
        button.disabled = false;
        button.dataset.h3DependencyResume = "1";
        button.click();
      } catch (error) {
        button.disabled = false;
        log(node, `PDD custom-node install failed: ${error.message}`);
        app.extensionManager?.toast?.add?.({
          severity: "error",
          summary: "PDD dependency install failed",
          detail: String(error?.message || error),
          life: 7000,
        });
      }
    }, true);
  };
  setTimeout(wait, 0);
}

app.registerExtension({
  name: "H3Studio.PDDDependencyInstaller",
  afterConfigureGraph() {
    for (const node of app.graph?._nodes || []) if (className(node) === TARGET) attach(node);
  },
  nodeCreated(node) {
    if (className(node) === TARGET) attach(node);
  },
});
