import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";

test("README architecture renders as a complete diagram", async ({ page }) => {
  const markdown = readFileSync("../README.md", "utf8");
  const diagram = markdown.match(/```mermaid\n([\s\S]*?)```/)?.[1];
  expect(diagram).toBeTruthy();
  await page.goto("/");
  const svg = await page.evaluate(async (source) => {
    // Use the same installed Mermaid version as the application, inside a browser.
    const { default: mermaid } =
      await import("/node_modules/mermaid/dist/mermaid.esm.min.mjs");
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
    });
    await mermaid.parse(source);
    return (await mermaid.render("readmeArchitecture", source)).svg;
  }, diagram!);
  expect(svg).toContain("<svg");
  expect(svg).toContain("Qwen Plus");
});
