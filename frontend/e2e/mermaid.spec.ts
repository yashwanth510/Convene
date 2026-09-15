import { test, expect } from "@playwright/test";

test("incomplete diagrams recover without leaking Mermaid error banners", async ({
  page,
}) => {
  await page.goto("/");
  await page.evaluate(async () => {
    const { default: React } =
      await import("/node_modules/.vite/deps/react.js");
    const { default: ReactDOM } =
      await import("/node_modules/.vite/deps/react-dom_client.js");
    const { default: Markdown } = await import("/src/components/Markdown.tsx");
    const host = document.createElement("div");
    host.dataset.testid = "diagram-fixture";
    document.body.append(host);
    const root = ReactDOM.createRoot(host);
    Object.assign(window, {
      updateDiagram: (content: string) =>
        root.render(
          React.createElement(
            React.StrictMode,
            null,
            React.createElement(Markdown, { content }),
          ),
        ),
      removeDiagram: () => {
        root.unmount();
        host.remove();
      },
    });
  });
  const update = async (text: string) =>
    page.evaluate((value) => Reflect.get(window, "updateDiagram")(value), text);
  await update('```mermaid\nflowchart TD\nA["Unfinished');
  await expect(
    page.getByTestId("diagram-fixture").locator("pre"),
  ).toContainText("Unfinished");
  await expect(page.getByTestId("diagram-fixture")).toContainText(
    "This diagram has invalid syntax.",
  );
  await expect(page.locator("body")).not.toContainText("Syntax error in text");
  await update('```mermaid\nflowchart TD\nA["Frontend"] --> B["Backend"]\n```');
  await expect(page.getByTestId("diagram-fixture").locator("svg")).toHaveCount(
    1,
  );
  await expect(page.getByTestId("diagram-fixture")).toContainText("Backend");
  await expect(
    page.getByTestId("diagram-fixture").locator("svg"),
  ).toBeVisible();
  await update('```mermaid\nflowchart TD\nA["Broken');
  await expect(
    page.getByTestId("diagram-fixture").locator("pre"),
  ).toContainText("Broken");
  await update('```Mermaid\nflowchart LR\nA["Recovered"] --> B["Answer"]\n```');
  await expect(page.getByTestId("diagram-fixture").locator("svg")).toHaveCount(
    1,
  );
  await expect(page.getByTestId("diagram-fixture")).toContainText("Recovered");
  await expect(
    page.getByTestId("diagram-fixture").locator("svg"),
  ).toBeVisible();
  await update(`\`\`\`css
flowchart TD
    subgraph Input
        A[Embedding + Positional Encoding]
    end
    subgraph SA[Multi‑head Self‑Attention]
        Q[Query Linear]
        K[Key Linear]
        V[Value Linear]
        M[Scaled Dot‑Product]
        C[Concat Heads]
        O[Linear Projection]
    end
    subgraph FFN[Feed‑Forward Network]
        F1[Linear (d → d_ff)]
        ReLU[ReLU]
        F2[Linear (d_ff → d)]
    end
    subgraph Norm1[Add & Norm]
        N1[LayerNorm]
    end
    subgraph Norm2[Add & Norm]
        N2[LayerNorm]
    end
    A --> SA
    SA --> Norm1
    Norm1 --> FFN
    FFN --> Norm2
    Norm2 --> Output[Block Output]
    %% Residual connections
    A -.-> Norm1
    Norm1 -.-> Norm2
\`\`\``);
  await expect(
    page.getByTestId("diagram-fixture").locator("svg"),
  ).toBeVisible();
  await expect(page.getByTestId("diagram-fixture")).toContainText(
    "Linear (d → d_ff)",
  );
  await expect(page.getByTestId("diagram-fixture")).toContainText(
    "Block Output",
  );
  await expect(page.getByTestId("diagram-fixture").locator("pre")).toHaveCount(
    0,
  );
  await expect(page.locator("[data-convene-diagram=staging]")).toHaveCount(0);
  await page.evaluate(() => Reflect.get(window, "removeDiagram")());
  await expect(page.locator("body > div[id^='ddiagram']")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("Syntax error in text");
});
