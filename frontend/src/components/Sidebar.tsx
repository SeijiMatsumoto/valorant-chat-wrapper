import { useState, useEffect } from "react";
import type { Conversation, MatchCounts } from "../types";
import * as api from "../api/client";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({ conversations, activeId, onSelect, onNewChat, onDelete }: Props) {
  const [matchCounts, setMatchCounts] = useState<MatchCounts>({});

  const refreshCounts = () => {
    api.getMatchCounts().then(setMatchCounts).catch(() => {});
  };

  useEffect(() => {
    refreshCounts();
  }, []);

  return (
    <div className="w-[260px] min-w-[260px] bg-bg-sidebar border-r border-border-primary flex flex-col h-full p-4">
      {/* New Chat */}
      <button
        onClick={onNewChat}
        className="w-full py-2.5 px-4 border border-border-secondary rounded-lg text-sm text-text-primary hover:bg-bg-card transition-colors cursor-pointer"
      >
        + New Chat
      </button>

      {/* Recents */}
      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary mt-5 mb-2">
        Recents
      </p>
      <div className="flex-1 overflow-y-auto min-h-0">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate cursor-pointer transition-colors mb-0.5 ${
              conv.id === activeId
                ? "bg-bg-card text-text-primary"
                : "text-text-muted hover:bg-bg-card/50"
            }`}
          >
            {conv.title || "New conversation"}
          </button>
        ))}
        {conversations.length === 0 && (
          <p className="text-text-secondary text-xs px-3 py-2">No conversations yet</p>
        )}
      </div>

      {/* Delete */}
      {activeId && (
        <button
          onClick={() => onDelete(activeId)}
          className="w-full py-2 text-xs text-text-secondary border border-border-secondary rounded-lg hover:text-red-400 hover:border-red-400/50 transition-colors mt-2 cursor-pointer"
        >
          Delete Chat
        </button>
      )}

      {/* Stored Matches */}
      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary mt-4 mb-2">
        Stored Matches
      </p>
      <div className="bg-bg-card rounded-lg p-3 text-xs font-mono text-text-secondary space-y-0.5">
        {Object.entries(matchCounts).map(([user, count]) => (
          <div key={user}>{user}: {count} matches</div>
        ))}
        {Object.keys(matchCounts).length === 0 && <div>Loading...</div>}
      </div>
      <button
        onClick={refreshCounts}
        className="w-full py-1.5 text-xs text-text-secondary border border-border-secondary rounded-lg hover:bg-bg-card transition-colors mt-2 cursor-pointer"
      >
        Refresh
      </button>
    </div>
  );
}
