export function safeMarkdownUrl(value) {
  const url = String(value || "").trim();
  if (/^(https?:|mailto:)/i.test(url) || url.startsWith("#") || url.startsWith("/")) return url;
  return "";
}

export function parseInlineMarkdown(value) {
  const source = String(value || "");
  const pattern = /(\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|\*([^*]+)\*|_([^_]+)_|(https?:\/\/[^\s<]+))/g;
  const tokens = [];
  let cursor = 0;
  for (const match of source.matchAll(pattern)) {
    if (match.index > cursor) tokens.push({ type: "text", text: source.slice(cursor, match.index) });
    if (match[2] || match[3]) tokens.push({ type: "strong", text: match[2] || match[3] });
    else if (match[4]) tokens.push({ type: "code", text: match[4] });
    else if (match[5]) tokens.push({ type: "link", text: match[5], url: safeMarkdownUrl(match[6]) });
    else if (match[9]) tokens.push({ type: "link", text: match[9], url: safeMarkdownUrl(match[9]) });
    else tokens.push({ type: "em", text: match[7] || match[8] });
    cursor = match.index + match[0].length;
  }
  if (cursor < source.length) tokens.push({ type: "text", text: source.slice(cursor) });
  return tokens;
}

export function parseMarkdown(value) {
  const lines = String(value || "").replaceAll("\r\n", "\n").split("\n");
  const blocks = [];
  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const fence = line.match(/^```\s*([\w-]*)\s*$/);
    if (fence) {
      const content = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index])) content.push(lines[index++]);
      if (index < lines.length) index += 1;
      blocks.push({ type: "codeblock", language: fence[1], text: content.join("\n") });
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }
    const callout = line.match(/^>\s*\[!(NOTE|TIP|WARNING|IMPORTANT)\]\s*(.*)$/i);
    if (callout) {
      const content = [callout[2]].filter(Boolean);
      index += 1;
      while (index < lines.length && /^>\s?/.test(lines[index])) content.push(lines[index++].replace(/^>\s?/, ""));
      blocks.push({ type: "callout", kind: callout[1].toLowerCase(), text: content.join("\n") });
      continue;
    }
    const list = line.match(/^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/);
    if (list) {
      const ordered = Boolean(list[2]);
      const items = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/);
        if (!item || Boolean(item[2]) !== ordered) break;
        items.push(item[3]);
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    if (/^>\s?/.test(line)) {
      const content = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) content.push(lines[index++].replace(/^>\s?/, ""));
      blocks.push({ type: "quote", text: content.join("\n") });
      continue;
    }
    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(#{1,4})\s|^```|^>\s|^\s*(?:[-+*]|\d+\.)\s+/.test(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraph.join(" ") });
  }
  return blocks;
}
