import { useState } from "react";
import { Copy, Check, ExternalLink, ThumbsUp, ThumbsDown } from "lucide-react";
import MarkdownContent from "../MarkdownContent";
import { request } from "../lib/api";
import type { Result } from "../lib/types";
export default function ResultView({
  result,
  runId,
}: {
  result: Result;
  runId?: string;
}) {
  const [tab, setTab] = useState("answer");
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(0);
  const [error, setError] = useState("");
  const sources = result.sources || [];
  const content = result.content.replace(
    /\[([SD]\d+)\](?!\()/g,
    (match, id) => {
      const source = sources.find((s) => s.id === id);
      return source?.url && /^https?:\/\//.test(source.url)
        ? `[${id}](${source.url})`
        : match;
    },
  );
  async function copy() {
    try {
      await navigator.clipboard.writeText(result.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(
        "Copy is unavailable in this browser. Select the answer text to copy it.",
      );
    }
  }
  async function rate(value: number) {
    if (!runId) return;
    try {
      await request(`/runs/${runId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ value }),
      });
      setFeedback(value);
    } catch {
      setError("Feedback could not be saved. Please try again.");
    }
  }
  return (
    <div className="result-view">
      <div className="result-tabs" role="tablist" aria-label="Answer details">
        {["answer", "evidence", "perspectives"].map((name) => (
          <button
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            key={name}
          >
            {name}
            {name === "evidence" && sources.length > 0 && (
              <span>{sources.length}</span>
            )}
            {name === "perspectives" && !!result.positions?.length && (
              <span>{result.positions.length}</span>
            )}
          </button>
        ))}
      </div>
      {result.notice && <div className="notice">{result.notice}</div>}
      <div role="tabpanel">
        {tab === "answer" && <MarkdownContent content={content} />}
        {tab === "evidence" && (
          <div className="evidence-panel">
            <p className="quiet">
              {result.evidence?.note ||
                "Evidence checks are still pending. A source link alone does not verify a claim."}
            </p>
            {sources.map((source) => (
              <details className="source-card" key={source.id}>
                <summary>
                  <span className="source-id">{source.id}</span>
                  <span>{source.title}</span>
                </summary>
                <p>{source.content}</p>
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Read source <ExternalLink size={13} />
                  </a>
                )}
              </details>
            ))}
            {result.evidence?.claims.map((claim, i) => (
              <div className="claim-card" key={i}>
                <span className={`status-label ${claim.status}`}>
                  {claim.status.replace("_", " ")}
                </span>
                <p>{claim.claim}</p>
                {claim.excerpt && (
                  <blockquote>
                    {claim.excerpt}
                    <small>Source {claim.source_id}</small>
                  </blockquote>
                )}
                <small className="quiet">{claim.note}</small>
              </div>
            ))}
            {!sources.length && (
              <div className="empty-detail">
                No web or document sources were used for this answer.
              </div>
            )}
          </div>
        )}
        {tab === "perspectives" && (
          <div>
            {result.rounds?.map((round) => (
              <div className="round-summary" key={round.round}>
                Round {round.round} · {round.reviewers} reviewers ·{" "}
                {Math.round(round.agreement * 100)}% ranking agreement{" "}
                <span className="quiet">
                  Agreement is not factual certainty.
                </span>
              </div>
            ))}
            {result.positions?.map((p) => (
              <details className="perspective-card" key={p.id}>
                <summary>
                  <span className="model-dot" />
                  <strong>{p.model_name}</strong>
                  <span className="quiet">{p.id}</span>
                </summary>
                <p className="small quiet">Resolved model: {p.actual_model}</p>
                <MarkdownContent content={p.content} />
              </details>
            ))}
            {!result.positions?.length && (
              <div className="empty-detail">
                This question used the quick path with one model.
              </div>
            )}
            {result.warnings?.map((warning, i) => (
              <p className="notice" key={i}>
                {warning}
              </p>
            ))}
          </div>
        )}
      </div>
      <footer className="answer-footer">
        <span>
          {result.mode === "fast" ? "Quick answer" : "Council answer"}
          {result.usage && (
            <>
              {" "}
              · {result.usage.calls} calls ·{" "}
              {result.usage.estimated_tokens ? "~" : ""}
              {result.usage.total_tokens.toLocaleString()} tokens
            </>
          )}
          {result.duration_seconds !== undefined && (
            <> · {Math.round(result.duration_seconds)}s</>
          )}
        </span>
        <div>
          <button
            className="icon-button"
            aria-label="Copy answer"
            onClick={copy}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
          {runId && (
            <>
              <button
                className={`icon-button ${feedback === 1 ? "selected" : ""}`}
                aria-label="Helpful answer"
                onClick={() => rate(1)}
              >
                <ThumbsUp size={16} />
              </button>
              <button
                className={`icon-button ${feedback === -1 ? "selected" : ""}`}
                aria-label="Unhelpful answer"
                onClick={() => rate(-1)}
              >
                <ThumbsDown size={16} />
              </button>
            </>
          )}
        </div>
      </footer>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
