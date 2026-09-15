import { describe, expect, it } from "vitest";
import { isMermaidSource, quoteFlowchartLabels } from "./diagram";

describe("diagram recognition", () => {
  it("recognizes a flowchart mislabeled as CSS without treating CSS as a diagram", () => {
    expect(isMermaidSource("flowchart TD\nA --> B")).toBe(true);
    expect(isMermaidSource(".flowchart { display: flex; }")).toBe(false);
    expect(isMermaidSource("flowchart TD { color: red; }")).toBe(false);
  });
  it("quotes punctuation in rectangular labels without changing shapes or edges", () => {
    expect(
      quoteFlowchartLabels(
        'flowchart TD\nF1[Linear (d → d_ff)] --> N[Add & Norm]\nD[(Database)]\nQ["Already quoted"]',
      ),
    ).toBe(
      'flowchart TD\nF1["Linear (d → d_ff)"] --> N["Add & Norm"]\nD[(Database)]\nQ["Already quoted"]',
    );
  });
  it("does not repair incomplete syntax or rewrite other diagram types", () => {
    expect(quoteFlowchartLabels('flowchart TD\nA["Unfinished')).toBe(
      'flowchart TD\nA["Unfinished',
    );
    expect(quoteFlowchartLabels("sequenceDiagram\nA->>B: data[x]")).toBe(
      "sequenceDiagram\nA->>B: data[x]",
    );
  });
});
