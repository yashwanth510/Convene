import { lazy, Suspense } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { isMermaidSource } from "../lib/diagram";
const MermaidBlock = lazy(() => import("./MermaidBlock"));
function normalizeMathDelimiters(md: string) {
  return md
    .replace(
      /\\\[\s*([\s\S]*?)\s*\\\]/g,
      (_m, expr: string) => `\n$$\n${expr.trim()}\n$$\n`,
    )
    .replace(
      /\\\(\s*([\s\S]*?)\s*\\\)/g,
      (_m, expr: string) => `$${expr.trim()}$`,
    );
}
// Stable renderers preserve diagram components between streamed answer updates.
const markdownComponents: Components = {
  a: ({ children, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  img: ({ alt }) => <span>{alt}</span>,
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children, ...props }) => {
    const code = String(children).replace(/\n$/, "");
    const lang = /language-(\w+)/.exec(className || "")?.[1]?.toLowerCase();
    if (
      lang === "mermaid" ||
      (className !== undefined && isMermaidSource(code))
    )
      return (
        <Suspense fallback={<pre>Loading diagram…</pre>}>
          <MermaidBlock chart={code} />
        </Suspense>
      );
    if (lang || code.includes("\n"))
      return (
        <pre>
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      );
    return <code {...props}>{children}</code>;
  },
};

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={markdownComponents}
      >
        {normalizeMathDelimiters(content)}
      </ReactMarkdown>
    </div>
  );
}
