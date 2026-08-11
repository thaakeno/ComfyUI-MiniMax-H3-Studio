export function openImageLightbox(source, label = "Expanded image") {
  if (!source || typeof document === "undefined") return;
  const existing = document.querySelector(".h3s-preview-lightbox");
  if (existing?.__h3studioDismiss) existing.__h3studioDismiss();
  else existing?.remove();
  const previousFocus = document.activeElement;
  const overlay = document.createElement("div");
  overlay.className = "h3s-preview-lightbox";
  overlay.tabIndex = -1;
  const image = document.createElement("img");
  image.src = source;
  image.alt = label;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "h3s-preview-lightbox-close";
  close.textContent = "×";
  close.title = "Close image";
  const dismiss = () => {
    document.removeEventListener("keydown", onKeydown);
    overlay.remove();
    previousFocus?.focus?.({ preventScroll: true });
  };
  const onKeydown = (event) => {
    if (event.key === "Escape") dismiss();
  };
  overlay.__h3studioDismiss = dismiss;
  close.addEventListener("click", dismiss);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) dismiss();
  });
  document.addEventListener("keydown", onKeydown);
  overlay.append(image, close);
  document.body.append(overlay);
  overlay.focus();
}
