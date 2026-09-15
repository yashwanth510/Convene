import { useEffect, useRef, useState } from "react";
import { events, request } from "./api";
import type { Result, Run } from "./types";
const terminal = new Set([
  "complete",
  "partial",
  "failed",
  "cancelled",
  "interrupted",
]);
const initial: Result = {
  content: "",
  positions: [],
  sources: [],
  rounds: [],
  warnings: [],
};
function pause(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const done = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
    if (signal.aborted) done();
  });
}
export function useRun(
  id: string | null,
  onFinished: (result: Result, status: string) => void,
) {
  const [result, setResult] = useState<Result>(initial);
  const [progress, setProgress] = useState("Getting ready");
  const callback = useRef(onFinished);
  useEffect(() => {
    callback.current = onFinished;
  }, [onFinished]);
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    let cursor = 0;
    let finished = false;
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setResult(initial);
        setProgress("Connecting to your question");
      }
    });
    function finish(data: Result, status: string) {
      if (!controller.signal.aborted && !finished) {
        finished = true;
        callback.current(data, status);
      }
    }
    async function connect() {
      let attempts = 0;
      while (!controller.signal.aborted && !finished) {
        try {
          await events(id!, cursor, controller.signal, (event) => {
            const seq = Number(event.id);
            if (!Number.isFinite(seq) || seq <= cursor) return;
            const data = JSON.parse(event.data);
            cursor = seq;
            attempts = 0;
            if (event.event === "finished") {
              finish(data.result, data.status);
              return;
            }
            if (data.message) setProgress(data.message);
            if (event.event === "answer")
              setResult((r) => ({ ...r, content: r.content + data.content }));
            if (event.event === "plan")
              setResult((r) => ({ ...r, mode: data.mode }));
            if (event.event === "research")
              setResult((r) => ({ ...r, sources: data.sources }));
            if (event.event === "position")
              setResult((r) => ({
                ...r,
                positions: [...(r.positions || []), data],
              }));
            if (event.event === "round")
              setResult((r) => ({ ...r, rounds: [...(r.rounds || []), data] }));
            if (event.event === "evidence")
              setResult((r) => ({ ...r, evidence: data }));
            if (event.event === "warning")
              setResult((r) => ({
                ...r,
                warnings: [...(r.warnings || []), data.message],
              }));
          });
          if (!finished && !controller.signal.aborted) {
            const run = await request<Run>(`/runs/${id}`, {
              signal: controller.signal,
            });
            if (terminal.has(run.status))
              finish(run.result || initial, run.status);
          }
        } catch {
          if (controller.signal.aborted) return;
        }
        if (!finished && !controller.signal.aborted) {
          attempts += 1;
          setProgress("Reconnecting… your progress is saved");
          await pause(
            Math.min(1000 * 2 ** Math.min(attempts, 4), 15000),
            controller.signal,
          );
        }
      }
    }
    void connect();
    return () => controller.abort();
  }, [id]);
  return { result, progress };
}
