import { SSEDecoder, type StreamEvent } from "./sse";
const BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "https://convene-qgfr.onrender.com/api";
export function getToken() {
  return sessionStorage.getItem("convene-session") || "";
}
export function setToken(token: string) {
  if (token) sessionStorage.setItem("convene-session", token);
  else sessionStorage.removeItem("convene-session");
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (getToken()) headers.set("Authorization", `Bearer ${getToken()}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(BASE + path, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* Cold-start responses may be HTML. */
    }
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("convene-session-expired"));
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function events(
  run: string,
  after: number,
  signal: AbortSignal,
  receive: (e: StreamEvent) => void,
) {
  const response = await fetch(`${BASE}/runs/${run}/events?after=${after}`, {
    signal,
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok || !response.body)
    throw new Error(`Could not connect to progress (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEDecoder(receive);
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        parser.push(decoder.decode());
        break;
      }
      parser.push(decoder.decode(value, { stream: true }));
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
export async function download(id: string) {
  const response = await fetch(`${BASE}/conversations/${id}/download`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok) throw new Error("Could not export this conversation");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "convene-conversation.md";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
