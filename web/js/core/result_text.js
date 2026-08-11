export function splitReferenceMentions(value) {
  const text = String(value || "");
  const parts = [];
  const pattern = /@Image[_\s]*([1-9]\d*)\b/gi;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) parts.push({ type: "text", value: text.slice(cursor, match.index) });
    parts.push({ type: "mention", ordinal: Number(match[1]), value: `@Image${Number(match[1])}` });
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) parts.push({ type: "text", value: text.slice(cursor) });
  return parts;
}
