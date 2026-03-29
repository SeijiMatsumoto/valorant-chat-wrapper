import { useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (text.trim() && !disabled) {
        onSend(text.trim());
        setText("");
      }
    }
  }

  return (
    <div className="px-6 pb-5 pt-2 shrink-0">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        placeholder={disabled ? "Thinking..." : "Ask about stats, performance, agent picks..."}
        disabled={disabled}
        rows={1}
        className="w-full bg-bg-input border border-border-secondary rounded-xl px-4 py-3.5 text-[15px] text-text-primary placeholder-text-secondary resize-none outline-none focus:border-[#777] transition-colors disabled:opacity-50"
      />
    </div>
  );
}
