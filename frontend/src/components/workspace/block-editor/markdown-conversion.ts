"use client";

import { marked } from "marked";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

marked.setOptions({
  breaks: true,
  gfm: true,
});

const turndown = new TurndownService({
  codeBlockStyle: "fenced",
  headingStyle: "atx",
  bulletListMarker: "-",
});

turndown.use(gfm);

export function markdownToHtml(markdown: string): string {
  const rendered = marked.parse(markdown || "");
  return typeof rendered === "string" ? rendered : "";
}

export function htmlToMarkdown(html: string): string {
  return turndown.turndown(html).trim();
}

export function extractHeadings(markdown: string): Array<{ level: number; text: string; anchor: string }> {
  return markdown.split("\n").flatMap((line) => {
    const match = /^(#{1,6})\s+(.*)$/.exec(line);
    if (!match) {
      return [];
    }
      const hashes = match[1] ?? "#";
      const text = (match[2] ?? "").trim();
      return [{
        level: hashes.length,
        text,
        anchor: text
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, ""),
      }];
  });
}
