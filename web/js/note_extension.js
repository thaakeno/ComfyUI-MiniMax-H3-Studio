import { app } from "../../../scripts/app.js";

import { parseInlineMarkdown, parseMarkdown } from "./core/markdown.js";
import { noteViewportHeight, noteWidgetSizing } from "./core/note_layout.js";

const TARGET = "H3StudioWorkflowNote";

function widget(node, name) {
  return node.widgets?.find((candidate) => candidate.name === name);
}

function hideWidget(target) {
  if (!target || target.__h3studioNoteHidden) return;
  target.__h3studioNoteHidden = true;
  target.computeSize = () => [0, -4];
  target.hidden = true;
  target.type = "h3studio_note_hidden";
}

function appendInline(parent, value) {
  for (const token of parseInlineMarkdown(value)) {
    if (token.type === "text") parent.append(document.createTextNode(token.text));
    else if (token.type === "strong") {
      const element = document.createElement("strong");
      element.textContent = token.text;
      parent.append(element);
    } else if (token.type === "em") {
      const element = document.createElement("em");
      element.textContent = token.text;
      parent.append(element);
    } else if (token.type === "code") {
      const element = document.createElement("code");
      element.textContent = token.text;
      parent.append(element);
    } else if (token.type === "link") {
      const element = document.createElement(token.url ? "a" : "span");
      element.textContent = token.text;
      if (token.url) {
        element.href = token.url;
        element.target = "_blank";
        element.rel = "noopener noreferrer";
        element.addEventListener("click", (event) => event.stopPropagation());
      }
      parent.append(element);
    }
  }
}

function renderMarkdown(root, value) {
  root.replaceChildren();
  for (const block of parseMarkdown(value)) {
    let element;
    if (block.type === "heading") element = document.createElement(`h${Math.min(4, block.level + 1)}`);
    else if (block.type === "list") {
      element = document.createElement(block.ordered ? "ol" : "ul");
      for (const item of block.items) {
        const listItem = document.createElement("li");
        appendInline(listItem, item);
        element.append(listItem);
      }
      root.append(element);
      continue;
    } else if (block.type === "codeblock") {
      element = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = block.text;
      if (block.language) code.dataset.language = block.language;
      element.append(code);
      root.append(element);
      continue;
    } else if (block.type === "callout") {
      element = document.createElement("aside");
      element.className = `h3s-note-callout is-${block.kind}`;
      const label = document.createElement("strong");
      label.textContent = block.kind;
      element.append(label, document.createTextNode(" "));
    } else if (block.type === "quote") element = document.createElement("blockquote");
    else element = document.createElement("p");
    appendInline(element, block.text);
    root.append(element);
  }
}

function installNote(node) {
  if (node.__h3studioNoteInstalled || typeof node.addDOMWidget !== "function") return;
  node.__h3studioNoteInstalled = true;
  const sectionWidget = widget(node, "section");
  const textWidget = widget(node, "text");
  if (!textWidget) return;
  hideWidget(sectionWidget);
  hideWidget(textWidget);

  const panel = document.createElement("div");
  panel.className = "h3s-note-card";
  const toolbar = document.createElement("div");
  toolbar.className = "h3s-note-toolbar";
  const section = document.createElement("span");
  section.className = "h3s-note-section";
  const controls = document.createElement("div");
  controls.className = "h3s-note-controls";
  const previewButton = document.createElement("button");
  previewButton.type = "button";
  previewButton.textContent = "Preview";
  const editButton = document.createElement("button");
  editButton.type = "button";
  editButton.textContent = "Edit";
  controls.append(previewButton, editButton);
  toolbar.append(section, controls);
  const preview = document.createElement("div");
  preview.className = "h3s-note-markdown";
  const editor = document.createElement("textarea");
  editor.className = "h3s-note-editor";
  editor.hidden = true;
  panel.append(toolbar, preview, editor);

  const render = () => {
    section.textContent = String(sectionWidget?.value || "note");
    panel.dataset.section = String(sectionWidget?.value || "note");
    editor.value = String(textWidget.value || "");
    renderMarkdown(preview, textWidget.value);
  };
  const setMode = (editing) => {
    editor.hidden = !editing;
    preview.hidden = editing;
    editButton.classList.toggle("is-active", editing);
    previewButton.classList.toggle("is-active", !editing);
    if (editing) editor.focus({ preventScroll: true });
  };
  previewButton.addEventListener("click", (event) => {
    event.stopPropagation();
    setMode(false);
  });
  editButton.addEventListener("click", (event) => {
    event.stopPropagation();
    setMode(true);
  });
  editor.addEventListener("input", () => {
    textWidget.value = editor.value;
    textWidget.callback?.(editor.value, app.canvas, node, [0, 0], {});
    renderMarkdown(preview, editor.value);
    app.graph?.setDirtyCanvas?.(true, true);
  });
  for (const target of [sectionWidget, textWidget]) {
    if (!target) continue;
    const previous = target.callback;
    target.callback = function (...args) {
      const result = previous?.apply(this, args);
      render();
      return result;
    };
  }
  const display = node.addDOMWidget("h3studio_markdown_note", "h3studio_markdown_note", panel, {
    serialize: false,
    hideOnZoom: false,
    ...noteWidgetSizing(node),
  });
  // Legacy frontend fallback. Nodes 2.0 uses the sizing callbacks passed to
  // addDOMWidget above and ignores this post-creation computeSize override.
  display.computeSize = (width) => [width, noteViewportHeight(node.size?.[1])];
  render();
  setMode(false);
}

app.registerExtension({
  name: "h3studio.markdown-notes",
  async setup() {
    if (document.getElementById("h3studio-note-style")) return;
    const style = document.createElement("style");
    style.id = "h3studio-note-style";
    style.textContent = `
      .h3s-note-card { box-sizing: border-box; display: flex; flex-direction: column; width: 100%; height: 100%; min-height: 160px; overflow: hidden; border: 1px solid rgba(255,255,255,.13); border-radius: 8px; color: #e8ecef; background: #17211f; font: 12px/1.55 ui-sans-serif, system-ui; }
      .h3s-note-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 9px; border-bottom: 1px solid rgba(255,255,255,.11); background: rgba(255,255,255,.035); }
      .h3s-note-section { color: #71dbc6; font-size: 9px; font-weight: 760; letter-spacing: .08em; text-transform: uppercase; }
      .h3s-note-controls { display: flex; gap: 3px; }
      .h3s-note-controls button { padding: 3px 6px; border: 1px solid rgba(255,255,255,.12); border-radius: 4px; color: #aeb8c1; background: transparent; cursor: pointer; font: 9px ui-sans-serif, system-ui; }
      .h3s-note-controls button.is-active { color: #eafffa; border-color: rgba(52,211,181,.5); background: rgba(52,211,181,.12); }
      .h3s-note-markdown, .h3s-note-editor { box-sizing: border-box; flex: 1; min-height: 0; overflow: auto; padding: 12px 14px; }
      .h3s-note-editor { width: 100%; resize: none; border: 0; outline: none; color: #e8ecef; background: #111816; font: 11px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; }
      .h3s-note-markdown h2, .h3s-note-markdown h3, .h3s-note-markdown h4, .h3s-note-markdown h5 { margin: 0 0 8px; color: #f4f7f8; line-height: 1.25; }
      .h3s-note-markdown h2 { font-size: 18px; } .h3s-note-markdown h3 { font-size: 15px; } .h3s-note-markdown h4, .h3s-note-markdown h5 { font-size: 13px; }
      .h3s-note-markdown p { margin: 0 0 9px; } .h3s-note-markdown p:last-child { margin-bottom: 0; }
      .h3s-note-markdown ul, .h3s-note-markdown ol { margin: 0 0 10px; padding-left: 22px; } .h3s-note-markdown li { margin: 3px 0; }
      .h3s-note-markdown a { color: #67e8d0; text-underline-offset: 2px; }
      .h3s-note-markdown code { padding: 1px 4px; border-radius: 4px; color: #b8f5e8; background: rgba(0,0,0,.28); font: 10px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace; }
      .h3s-note-markdown pre { overflow: auto; margin: 0 0 10px; padding: 9px; border: 1px solid rgba(255,255,255,.1); border-radius: 6px; background: #0d1312; } .h3s-note-markdown pre code { padding: 0; background: transparent; }
      .h3s-note-markdown blockquote, .h3s-note-callout { margin: 0 0 10px; padding: 8px 10px; border-left: 3px solid #66717c; border-radius: 4px; background: rgba(255,255,255,.04); }
      .h3s-note-callout { border-left-color: #34d3b5; } .h3s-note-callout.is-warning { border-left-color: #f59e0b; }
      .h3s-note-callout > strong { color: #8debd9; font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
    `;
    document.head.append(style);
  },
  async nodeCreated(node) {
    if (node.comfyClass === TARGET) installNote(node);
  },
});
