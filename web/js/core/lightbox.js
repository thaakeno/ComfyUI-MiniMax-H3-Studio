export function openImageLightbox(source, label = "Expanded image") {
  if (!source || typeof document === "undefined") return;
  document.querySelector(".h3s-preview-lightbox")?.remove();
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
  const dismiss = () => overlay.remove();
  close.addEventListener("click", dismiss);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) dismiss();
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") dismiss();
  });
  overlay.append(image, close);
  document.body.append(overlay);
  overlay.focus();
}
