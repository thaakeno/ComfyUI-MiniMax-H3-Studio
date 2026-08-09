const ANNOTATION = /\s+\[(input|output|temp)\]$/i;

export function parseStorageName(value) {
  const raw = String(value || "").trim();
  const match = raw.match(ANNOTATION);
  const type = match?.[1]?.toLowerCase() || "input";
  const relative = raw.replace(ANNOTATION, "").replaceAll("\\", "/").replace(/^\/+/, "");
  const parts = relative.split("/").filter(Boolean);
  const filename = parts.pop() || "";
  return { filename, subfolder: parts.join("/"), type };
}

export function storageNameFromUpload(result) {
  const filename = String(result?.name || "").replaceAll("\\", "/").split("/").pop();
  if (!filename) throw new Error("ComfyUI accepted the upload but returned no filename.");
  const subfolder = String(result?.subfolder || "").replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
  const type = String(result?.type || "input").toLowerCase();
  const relative = [subfolder, filename].filter(Boolean).join("/");
  return type === "input" ? relative : `${relative} [${type}]`;
}

export function previewUrlForStorage(storageName) {
  const { filename } = parseStorageName(storageName);
  if (!filename) return "";
  const query = new URLSearchParams({ storage: String(storageName), size: "112" });
  return `/h3studio/thumbnail?${query.toString()}`;
}

export async function uploadImage(api, file, subfolder = "h3studio") {
  if (!(file instanceof File) || !String(file.type || "").startsWith("image/")) {
    throw new Error(`${file?.name || "Selected file"} is not a supported image.`);
  }
  const form = new FormData();
  form.append("image", file, file.name);
  form.append("type", "input");
  form.append("subfolder", subfolder);
  const response = await api.fetchApi("/upload/image", { method: "POST", body: form });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Upload failed (${response.status})${detail ? `: ${detail}` : "."}`);
  }
  const result = await response.json();
  return {
    filename: String(result.name || file.name),
    storage_name: storageNameFromUpload(result),
    preview_url: previewUrlForStorage(storageNameFromUpload(result)),
  };
}

export function chooseImageFiles({ multiple = true } = {}) {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.multiple = multiple;
    input.style.display = "none";
    input.addEventListener("change", () => {
      const files = [...(input.files || [])];
      input.remove();
      resolve(files);
    }, { once: true });
    input.addEventListener("cancel", () => {
      input.remove();
      resolve([]);
    }, { once: true });
    document.body.append(input);
    input.click();
  });
}

export function imageFilesFromTransfer(transfer) {
  return [...(transfer?.files || [])].filter((file) => String(file.type || "").startsWith("image/"));
}

export async function uploadImages(api, files, { concurrency = 3, onProgress = () => {} } = {}) {
  const source = [...files];
  const results = new Array(source.length);
  let cursor = 0;
  let completed = 0;
  const worker = async () => {
    while (cursor < source.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await uploadImage(api, source[index]);
      completed += 1;
      onProgress(completed, source.length);
    }
  };
  await Promise.all(Array.from({ length: Math.min(Math.max(1, concurrency), source.length) }, worker));
  return results;
}
