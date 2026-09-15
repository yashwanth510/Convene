import { useEffect, useState } from "react";
import mermaid from "mermaid";
import { quoteFlowchartLabels } from "../lib/diagram";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  suppressErrorRendering: true,
  theme: "neutral",
  fontFamily: "system-ui, sans-serif",
  flowchart: { htmlLabels: false },
});

let nextDiagram = 0;

export default function MermaidBlock({ chart }: { chart: string }) {
  const [result, setResult] = useState<{ source: string; svg: string } | null>(
    null,
  );
  useEffect(() => {
    let cancelled = false;
    // Streaming Markdown can contain an unfinished fence or half a node label.
    const timer = setTimeout(async () => {
      let staging: HTMLDivElement | undefined;
      try {
        let source = chart;
        let valid = await mermaid.parse(source, { suppressErrors: true });
        if (!valid) {
          const quoted = quoteFlowchartLabels(source);
          if (quoted !== source) {
            source = quoted;
            valid = await mermaid.parse(source, { suppressErrors: true });
          }
        }
        if (cancelled) return;
        if (!valid) {
          setResult({ source: chart, svg: "" });
          return;
        }
        staging = document.createElement("div");
        staging.dataset.conveneDiagram = "staging";
        staging.style.cssText =
          "position:absolute;left:-100000px;visibility:hidden;pointer-events:none";
        document.body.append(staging);
        const { svg } = await mermaid.render(
          `conveneDiagram${++nextDiagram}`,
          source,
          staging,
        );
        if (!cancelled) setResult({ source: chart, svg });
      } catch {
        if (!cancelled) setResult({ source: chart, svg: "" });
      } finally {
        staging?.remove();
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [chart]);

  if (result?.source === chart && result.svg) {
    return (
      <div
        className="mermaid-inline"
        dangerouslySetInnerHTML={{ __html: result.svg }}
      />
    );
  }
  return (
    <div className="diagram-source">
      <pre>
        <code>{chart}</code>
      </pre>
      <p className="quiet small">
        {result?.source === chart
          ? "This diagram has invalid syntax. Its source is shown above."
          : "Preparing diagram…"}
      </p>
    </div>
  );
}
