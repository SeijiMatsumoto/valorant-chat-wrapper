import { useState, useCallback } from "react";
import type { Message } from "../types";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import * as api from "../api/client";
import logo from "../assets/logo.webp";

interface Props {
  conversationId: string | null;
  onConversationCreated: (id: string) => void;
  onMessageSent: () => void;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export default function ChatArea({
  conversationId,
  onConversationCreated,
  onMessageSent,
  messages,
  setMessages,
}: Props) {
  const [loading, setLoading] = useState(false);

  const handleSend = useCallback(
    async (text: string) => {
      let convId = conversationId;

      if (!convId) {
        const conv = await api.createConversation();
        convId = conv.id;
        onConversationCreated(convId);
      }

      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "Thinking... (calling tools as needed)" },
      ]);
      setLoading(true);

      try {
        const { response } = await api.sendMessage(convId, text);
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: "assistant", content: response };
          return updated;
        });
      } catch (err) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
          };
          return updated;
        });
      } finally {
        setLoading(false);
        onMessageSent();
      }
    },
    [conversationId, onConversationCreated, onMessageSent, setMessages]
  );

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-bg-primary">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-6 py-3.5 border-b border-border-primary shrink-0">
        <img src={logo} alt="logo" className="w-7 h-7 rounded-md" />
        <span className="text-base font-semibold text-text-primary">Valorant Squad Analyst</span>
      </div>

      <MessageList messages={messages} />
      <ChatInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
