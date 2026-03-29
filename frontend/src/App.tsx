import { useState, useEffect, useCallback } from "react";
import type { Conversation, Message } from "./types";
import * as api from "./api/client";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const refreshConversations = useCallback(() => {
    api.listConversations().then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  const handleSelect = useCallback(async (id: string) => {
    setActiveId(id);
    try {
      const msgs = await api.getMessages(id);
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setActiveId(null);
    setMessages([]);
  }, []);

  const handleDelete = useCallback(
    async (id: string) => {
      await api.deleteConversation(id);
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
      refreshConversations();
    },
    [activeId, refreshConversations]
  );

  const handleConversationCreated = useCallback(
    (id: string) => {
      setActiveId(id);
      refreshConversations();
    },
    [refreshConversations]
  );

  return (
    <div className="flex h-screen">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
      />
      <ChatArea
        conversationId={activeId}
        onConversationCreated={handleConversationCreated}
        onMessageSent={refreshConversations}
        messages={messages}
        setMessages={setMessages}
      />
    </div>
  );
}
