import test from "node:test";
import assert from "node:assert/strict";

import { parseInlineMarkdown, parseMarkdown, safeMarkdownUrl } from "../../web/js/core/markdown.js";

test("workflow notes parse headings lists code and callouts", () => {
  const blocks = parseMarkdown("# Setup\n\n- One\n- Two\n\n> [!TIP] Fast path\n\n```bash\nuv sync\n```");
  assert.deepEqual(blocks.map((block) => block.type), ["heading", "list", "callout", "codeblock"]);
  assert.deepEqual(blocks[1].items, ["One", "Two"]);
  assert.equal(blocks[3].language, "bash");
});

test("inline markdown supports useful formatting without unsafe links", () => {
  const tokens = parseInlineMarkdown("Use **Base** with `@Image1` and [docs](https://docs.comfy.org).");
  assert.deepEqual(tokens.filter((token) => token.type !== "text").map((token) => token.type), ["strong", "code", "link"]);
  assert.equal(safeMarkdownUrl("javascript:alert(1)"), "");
  assert.equal(safeMarkdownUrl("/view?filename=x.png"), "/view?filename=x.png");
  assert.equal(parseInlineMarkdown("https://docs.comfy.org")[0].type, "link");
});
