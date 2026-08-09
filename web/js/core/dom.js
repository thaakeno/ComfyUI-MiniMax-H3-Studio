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

export function selectControl(value, options, label, onChange) {
  const select = element("select", {
    className: "h3s-control h3s-select",
    attrs: { "aria-label": label },
    on: { change: (event) => onChange(event.target.value) },
  });
  for (const option of options) {
    const [key, text] = Array.isArray(option) ? option : [option, option];
    select.append(element("option", { value: key, text }));
  }
  select.value = value;
  return select;
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

export function rangeControl(value, options, label, onInput) {
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

  const synchronize = (nextValue, emit = false) => {
    const bounded = Math.max(minimum, Math.min(maximum, Number(nextValue)));
    const progress = maximum === minimum ? 0 : ((bounded - minimum) / (maximum - minimum)) * 100;
    input.value = String(bounded);
    input.setAttribute("aria-valuenow", String(bounded));
    control.style.setProperty("--h3s-range-progress", `${progress}%`);
    if (emit) onInput(bounded);
  };
  const updateFromPointer = (event) => {
    synchronize(rangeValueFromPointer(event.clientX, control.getBoundingClientRect(), options), true);
  };

  input.addEventListener("input", (event) => synchronize(Number(event.target.value), true));
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
  return element("label", { className: "h3s-field" }, children);
}
