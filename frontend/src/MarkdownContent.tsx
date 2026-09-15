import { lazy, Suspense } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
const MermaidBlock = lazy(() => import("./components/MermaidBlock"));
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
export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          a: ({ children, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          img: ({ alt }) => <span>{alt}</span>,
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children, ...props }) => {
            const code = String(children).replace(/\n$/, "");
            const lang = /language-(\w+)/.exec(className || "")?.[1];
            if (lang === "mermaid")
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
        }}
      >
        {normalizeMathDelimiters(content)}
      </ReactMarkdown>
    </div>
  );
}
