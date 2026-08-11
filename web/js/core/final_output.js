export function isNodeDownstream(links, sourceId, targetId) {
  const target = String(targetId ?? "");
  const queue = [String(sourceId ?? "")];
  const visited = new Set();
  const values = links instanceof Map ? [...links.values()] : Array.isArray(links) ? links : Object.values(links || {});
  while (queue.length) {
    const current = queue.shift();
    if (!current || visited.has(current)) continue;
    visited.add(current);
    if (current === target) return true;
    for (const link of values) {
      const origin = String(link?.origin_id ?? link?.source_id ?? link?.[1] ?? "");
      const destination = String(link?.target_id ?? link?.[3] ?? "");
      if (origin === current && destination && !visited.has(destination)) queue.push(destination);
    }
  }
  return false;
}

export function executedImageUrl(item) {
  const filename = String(item?.filename || "").trim();
  if (!filename) return "";
  const query = new URLSearchParams({
    filename,
    subfolder: String(item?.subfolder || ""),
    type: String(item?.type || "output"),
  });
  query.set("rand", String(Date.now()));
  return `/view?${query.toString()}`;
}

export function selectOutputView(requested, hasResult, hasComparison) {
  if (requested === "comparison" && hasComparison) return "comparison";
  if (hasResult) return "result";
  return hasComparison ? "comparison" : "result";
}
