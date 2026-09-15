import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "neutral",
  fontFamily: "system-ui, sans-serif",
  flowchart: { htmlLabels: false },
});
export default function MermaidBlock({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void mermaid
      .render(`diagram${id}`, chart)
      .then(({ svg }) => {
        if (!cancelled) {
          setError(false);
          if (ref.current) ref.current.innerHTML = svg;
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [chart, id]);
  return (
    <>
      <div ref={ref} className="mermaid-inline" hidden={error} />
      {error && (
        <pre>
          <code>{chart}</code>
          <span className="mermaid-error-msg">
            Diagram could not be rendered. Its source is shown above.
          </span>
        </pre>
      )}
    </>
  );
}
