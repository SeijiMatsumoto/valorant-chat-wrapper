import type { Message } from "../types";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MessageBubble({ role, content }: Message) {
  if (role === "user") {
    return (
      <div className="flex justify-end mb-4">
        <div className="bg-bg-user-bubble rounded-2xl rounded-br-sm px-4 py-3 max-w-[75%] text-[15px] leading-relaxed text-text-primary">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[85%] text-[15px] leading-relaxed text-text-muted prose-invert">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ children, ...props }) => (
              <a {...props} className="text-link hover:underline">{children}</a>
            ),
            code: ({ children, className, ...props }) => {
              const isBlock = className?.includes("language-");
              if (isBlock) {
                return (
                  <code {...props} className={`${className ?? ""} block`}>
                    {children}
                  </code>
                );
              }
              return (
                <code {...props} className="bg-bg-card text-text-muted rounded px-1.5 py-0.5 text-[13px] font-mono">
                  {children}
                </code>
              );
            },
            pre: ({ children }) => (
              <pre className="bg-bg-card border border-border-primary rounded-lg p-3 overflow-x-auto text-[13px] my-2 font-mono">
                {children}
              </pre>
            ),
            table: ({ children }) => (
              <table className="border-collapse my-2 text-sm w-full">{children}</table>
            ),
            th: ({ children }) => (
              <th className="border border-border-secondary px-3 py-2 text-left text-text-secondary bg-bg-card font-semibold">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border border-border-primary px-3 py-2 text-text-muted">
                {children}
              </td>
            ),
            h1: ({ children }) => <h1 className="text-xl font-bold text-text-primary mt-4 mb-2">{children}</h1>,
            h2: ({ children }) => <h2 className="text-lg font-bold text-text-primary mt-3 mb-2">{children}</h2>,
            h3: ({ children }) => <h3 className="text-base font-semibold text-text-primary mt-3 mb-1">{children}</h3>,
            strong: ({ children }) => <strong className="text-text-primary font-semibold">{children}</strong>,
            ul: ({ children }) => <ul className="list-disc list-outside pl-5 my-1 space-y-0.5">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-outside pl-5 my-1 space-y-0.5">{children}</ol>,
            li: ({ children }) => <li className="text-text-muted">{children}</li>,
            p: ({ children }) => <p className="my-1.5">{children}</p>,
          }}
        >
          {content}
        </Markdown>
      </div>
    </div>
  );
}
