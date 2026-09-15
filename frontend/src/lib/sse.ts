export interface StreamEvent {
  id: string;
  event: string;
  data: string;
}

/** Parse full SSE frames. Network chunk boundaries have no semantic meaning. */
export class SSEDecoder {
  private buffer = "";
  private event = "";
  private id = "";
  private data: string[] = [];
  private emit: (event: StreamEvent) => void;
  constructor(emit: (event: StreamEvent) => void) {
    this.emit = emit;
  }
  push(chunk: string) {
    this.buffer += chunk;
    let end: number;
    while ((end = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, end).replace(/\r$/, "");
      this.buffer = this.buffer.slice(end + 1);
      if (!line) {
        if (this.data.length)
          this.emit({
            id: this.id,
            event: this.event || "message",
            data: this.data.join("\n"),
          });
        this.event = "";
        this.data = [];
        continue;
      }
      if (line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon < 0 ? line : line.slice(0, colon);
      const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "event") this.event = value;
      if (field === "id" && !value.includes("\0")) this.id = value;
      if (field === "data") this.data.push(value);
    }
  }
}
