import type { Conversation, Message, MatchCounts } from "../types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function listConversations(limit = 30): Promise<Conversation[]> {
  return request(`/conversations?limit=${limit}`);
}

export function createConversation(): Promise<Conversation> {
  return request("/conversations", { method: "POST" });
}

export function deleteConversation(id: string): Promise<void> {
  return request(`/conversations/${id}`, { method: "DELETE" });
}

export function getMessages(convId: string): Promise<Message[]> {
  return request(`/conversations/${convId}/messages`);
}

export function sendMessage(
  convId: string,
  message: string
): Promise<{ response: string }> {
  return request(`/conversations/${convId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function getMatchCounts(): Promise<MatchCounts> {
  return request("/match-counts");
}
