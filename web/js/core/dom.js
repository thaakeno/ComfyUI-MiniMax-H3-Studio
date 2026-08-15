export function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs, dataset, on, ...properties } = options;
  if (className) node.className = className;
  if (text != null) node.textContent = String(text);
  if (attrs) for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (dataset) for (const [key, value] of Object.entries(dataset)) node.dataset[key] = String(value);
  if (on) for (const [event, handler] of Object.entries(on)) node.addEventListener(event, handler);
  Object.assign(node, properties);
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child == null) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function normalizedOptions(options) {
  return (options || []).map((option) => {
    const [key, text] = Array.isArray(option) ? option : [option, option];
    return [String(key), String(text)];
  });
}

function closeFloatingChooser(root) {
  const panel = root.__h3ChoicePanel;
  if (!panel) return;
  panel.remove();
  root.__h3ChoicePanel = null;
  root.classList.remove("is-open");
  root.querySelector(".h3s-choice-trigger")?.setAttribute("aria-expanded", "false");
  root.__h3ChoiceCleanup?.();
  root.__h3ChoiceCleanup = null;
}

export function selectControl(value, options, label, onChange) {
  const items = normalizedOptions(options);
  let current = String(value ?? items[0]?.[0] ?? "");
  const root = element("div", { className: "h3s-choice" });
  const currentText = () => items.find(([key]) => key === current)?.[1] || current || "Select";
  const trigger = element("button", {
    className: "h3s-choice-trigger",
    type: "button",
    attrs: { "aria-label": label, "aria-haspopup": "listbox", "aria-expanded": "false" },
  }, [
    element("span", { className: "h3s-choice-value", text: currentText() }),
    element("span", { className: "h3s-choice-chevron", text: "⌄", attrs: { "aria-hidden": "true" } }),
  ]);

  const updateLabel = () => {
    const valueNode = trigger.querySelector(".h3s-choice-value");
    if (valueNode) valueNode.textContent = currentText();
  };

  const open = () => {
    if (trigger.disabled) return;
    if (root.__h3ChoicePanel) { closeFloatingChooser(root); return; }
    document.querySelectorAll(".h3s-choice.is-open").forEach((other) => {
      if (other !== root) closeFloatingChooser(other);
    });
    const panel = element("div", {
      className: "h3s-choice-menu",
      attrs: { role: "listbox", "aria-label": label },
    });
    for (const [key, text] of items) {
      const option = element("button", {
        className: `h3s-choice-option${key === current ? " is-active" : ""}`,
        type: "button",
        text,
        attrs: { role: "option", "aria-selected": String(key === current) },
        on: {
          click: (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (key !== current) {
              current = key;
              updateLabel();
              onChange(key);
            }
            closeFloatingChooser(root);
            trigger.focus({ preventScroll: true });
          },
        },
      });
      panel.append(option);
    }
    document.body.append(panel);
    root.__h3ChoicePanel = panel;
    root.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");

    const place = () => {
      if (!panel.isConnected) return;
      const rect = trigger.getBoundingClientRect();
      const width = Math.max(rect.width, Math.min(420, window.innerWidth - 24));
      const below = window.innerHeight - rect.bottom;
      const estimated = Math.min(320, Math.max(44, panel.scrollHeight));
      const top = below >= estimated || rect.top < below ? rect.bottom + 5 : Math.max(8, rect.top - estimated - 5);
      panel.style.left = `${Math.max(8, Math.min(window.innerWidth - width - 8, rect.left))}px`;
      panel.style.top = `${top}px`;
      panel.style.width = `${width}px`;
      panel.style.maxHeight = `${Math.max(120, Math.min(320, Math.max(rect.top - 16, below - 16)))}px`;
    };
    place();
    requestAnimationFrame(place);

    const outside = (event) => {
      if (root.contains(event.target) || panel.contains(event.target)) return;
      closeFloatingChooser(root);
    };
    const escape = (event) => {
      if (event.key === "Escape") closeFloatingChooser(root);
    };
    const reposition = () => place();
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("keydown", escape, true);
    window.addEventListener("resize", reposition, { passive: true });
    window.addEventListener("scroll", reposition, { passive: true, capture: true });
    root.__h3ChoiceCleanup = () => {
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("keydown", escape, true);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
    panel.querySelector(".is-active")?.scrollIntoView?.({ block: "nearest" });
  };

  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    open();
  });
  trigger.addEventListener("keydown", (event) => {
    if (["ArrowDown", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      open();
      requestAnimationFrame(() => root.__h3ChoicePanel?.querySelector(".is-active,button")?.focus());
    }
  });
  root.append(trigger);

  Object.defineProperty(root, "disabled", {
    get: () => trigger.disabled,
    set: (next) => {
      trigger.disabled = Boolean(next);
      root.classList.toggle("is-disabled", Boolean(next));
      if (next) closeFloatingChooser(root);
    },
    configurable: true,
  });
  Object.defineProperty(root, "value", {
    get: () => current,
    set: (next) => { current = String(next ?? ""); updateLabel(); },
    configurable: true,
  });
  root.__h3ChoiceClose = () => closeFloatingChooser(root);
  return root;
}

export function numberControl(value, options, label, onChange) {
  return element("input", {
    className: "h3s-control h3s-number",
    type: "number",
    value,
    min: options.min,
    max: options.max,
    step: options.step,
    attrs: { "aria-label": label },
    on: { change: (event) => onChange(Number(event.target.value)) },
  });
}

export function rangeValueFromPointer(clientX, rect, options) {
  const minimum = Number(options.min);
  const maximum = Number(options.max);
  const step = Math.max(Number.EPSILON, Number(options.step) || 1);
  const width = Math.max(1, Number(rect.width) || 0);
  const ratio = Math.max(0, Math.min(1, (Number(clientX) - Number(rect.left || 0)) / width));
  const raw = minimum + ratio * (maximum - minimum);
  const snapped = minimum + Math.round((raw - minimum) / step) * step;
  const decimals = String(step).split(".")[1]?.length || 0;
  return Number(Math.max(minimum, Math.min(maximum, snapped)).toFixed(decimals));
}

export function rangeControl(value, options, label, onCommit) {
  const minimum = Number(options.min);
  const maximum = Number(options.max);
  const input = element("input", {
    className: "h3s-range-native",
    type: "range",
    value,
    min: minimum,
    max: maximum,
    step: options.step,
    attrs: { "aria-label": label },
  });
  const control = element("div", { className: "h3s-range" }, [
    element("span", { className: "h3s-range-track" }),
    element("span", { className: "h3s-range-thumb" }),
    input,
  ]);

  let lastCommitted = Number(value);
  const synchronize = (nextValue) => {
    const bounded = Math.max(minimum, Math.min(maximum, Number(nextValue)));
    const progress = maximum === minimum ? 0 : ((bounded - minimum) / (maximum - minimum)) * 100;
    input.value = String(bounded);
    input.setAttribute("aria-valuenow", String(bounded));
    control.style.setProperty("--h3s-range-progress", `${progress}%`);
    return bounded;
  };
  const commit = (nextValue) => {
    const bounded = synchronize(nextValue);
    if (bounded === lastCommitted) return;
    lastCommitted = bounded;
    onCommit(bounded);
  };
  const updateFromPointer = (event) => {
    synchronize(rangeValueFromPointer(event.clientX, control.getBoundingClientRect(), options));
  };

  // Moving a range thumb used to call the Director state callback for every
  // pointer pixel. That callback reconstructs the entire Director DOM, including
  // all reference cards. Keep thumb feedback local and commit once on release.
  input.addEventListener("input", (event) => synchronize(Number(event.target.value)));
  input.addEventListener("change", (event) => commit(Number(event.target.value)));
  input.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    input.focus();
    input.setPointerCapture?.(event.pointerId);
    updateFromPointer(event);
  });
  input.addEventListener("pointermove", (event) => {
    if (!input.hasPointerCapture?.(event.pointerId)) return;
    event.preventDefault();
    updateFromPointer(event);
  });
  const releasePointer = (event) => {
    if (input.hasPointerCapture?.(event.pointerId)) input.releasePointerCapture?.(event.pointerId);
    commit(Number(input.value));
  };
  input.addEventListener("pointerup", releasePointer);
  input.addEventListener("pointercancel", releasePointer);
  synchronize(value);
  return control;
}

export function iconButton(label, glyph, handler, className = "") {
  return element("button", {
    className: `h3s-icon-button ${className}`.trim(),
    type: "button",
    text: glyph,
    title: label,
    attrs: { "aria-label": label },
    on: { click: handler },
  });
}

export function field(label, control, hint = "") {
  const children = [element("span", { className: "h3s-field-label", text: label }), control];
  if (hint) children.push(element("span", { className: "h3s-field-hint", text: hint }));
  return element("div", { className: "h3s-field" }, children);
}