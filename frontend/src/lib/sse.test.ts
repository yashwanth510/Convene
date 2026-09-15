import { describe, it, expect } from "vitest";
import { SSEDecoder, type StreamEvent } from "./sse";
describe("SSE decoding", () => {
  it("survives every possible network boundary", () => {
    const input =
      'id: 1\r\nevent: answer\r\ndata: {"content":"hello"}\r\n\r\nid: 2\nevent: finished\ndata: {}\n\n';
    for (let split = 0; split <= input.length; split++) {
      const output: StreamEvent[] = [];
      const decoder = new SSEDecoder((e) => output.push(e));
      decoder.push(input.slice(0, split));
      decoder.push(input.slice(split));
      expect(output.map((e) => e.event)).toEqual(["answer", "finished"]);
      expect(JSON.parse(output[0].data).content).toBe("hello");
      expect(output[1].id).toBe("2");
    }
  });
  it("supports multiline data, comments and one-character chunks", () => {
    const output: StreamEvent[] = [];
    const decoder = new SSEDecoder((e) => output.push(e));
    const input = ": heartbeat\n\nid: 4\ndata: first\ndata: second\n\n";
    for (const c of input) decoder.push(c);
    expect(output).toEqual([
      { id: "4", event: "message", data: "first\nsecond" },
    ]);
  });
  it("does not publish an incomplete event", () => {
    const output: StreamEvent[] = [];
    const decoder = new SSEDecoder((e) => output.push(e));
    decoder.push("event: answer\ndata: partial");
    expect(output).toEqual([]);
    decoder.push("\n\n");
    expect(output).toHaveLength(1);
  });
});
