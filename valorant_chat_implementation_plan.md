# Valorant Chat App — Implementation Plan

## Overview

A local Python chat application that wraps Claude with a Valorant MCP integration and a SQLite database, allowing match history to persist beyond the API's 10-match limit and enabling deep historical analysis.

---

## Stack

| Layer | Technology |
|---|---|
| UI | Gradio (browser-based, fast to set up) |
| LLM | Anthropic Python SDK (`claude-opus-4-5`) |
| Valorant data | Valorant Analyzer MCP (stdio) |
| Database | SQLite (via `sqlite3`, built into Python) |
| Language | Python 3.11+ |

---

## Project Structure

```
valorant-chat/
├── main.py                  # Gradio UI + chat loop
├── db/
│   ├── __init__.py
│   ├── schema.py            # Table definitions + init
│   └── queries.py           # All DB read/write functions
├── mcp/
│   ├── __init__.py
│   └── client.py            # MCP sync logic (fetch + store)
├── analyst/
│   ├── __init__.py
│   └── context.py           # Builds Claude's system prompt from DB
├── valorant_mcp_server.py   # Your existing MCP server
├── requirements.txt
└── valorant.db              # Auto-created on first run
```

---

## Phase 1 — Database

### 1.1 Schema (`db/schema.py`)

Four tables:

**`matches`** — one row per match per tracked player
```
match_id (PK), username, map, date, result, rounds,
agent, rank, kills, deaths, assists, score,
headshot_pct, damage_made, damage_received, raw_json
```

**`teammates`** — one row per teammate per match
```
id (PK autoincrement), match_id (FK), username,
agent, rank, kills, deaths, assists, score
```

**`opponents`** — one row per opponent per match
```
id (PK autoincrement), match_id (FK), username, agent, kda
```

**`agent_stats`** — cached aggregated stats per player per agent
```
username, agent, games, wins, losses, win_rate,
avg_kills, avg_deaths, avg_assists, avg_score,
last_updated
```

### 1.2 Key design decisions

- Store `raw_json` (full API payload) on every match row — future-proofs against schema changes
- `match_id` as primary key prevents duplicate inserts — sync is always idempotent
- `agent_stats` table gets refreshed on each sync, not relied on as source of truth

---

## Phase 2 — MCP Sync Layer

### 2.1 `mcp/client.py`

**`sync_player(username, count=10)`**
- Call `get_match_history` via MCP
- For each match returned, check if `match_id` exists in DB
- Insert only new matches (teammates + opponents rows too)
- Return count of new matches inserted

**`sync_agent_stats(username, count=20)`**
- Call `get_agent_stats` via MCP
- Upsert results into `agent_stats` table

**`sync_all(usernames: list)`**
- Loops `sync_player` + `sync_agent_stats` for all tracked players
- Called once on app startup

### 2.2 Tracked players (hardcoded to start)

```python
TRACKED_PLAYERS = [
    "SayGG#11111",
    "Whae#cat",
    "takoyak11#1111",
    "david#asdf",
    "AltaVeritas#Once",
    "Minion#NA2",
    "xCovert#NA1",
    "Bhasket#ZIGGS",
]
```

---

## Phase 3 — Context Builder

### 3.1 `analyst/context.py`

**`build_system_prompt(username, match_limit=50)`**

Pulls from DB and assembles Claude's system prompt:

1. Player's last N matches (from `matches` table, `raw_json`)
2. Aggregated agent stats (from `agent_stats` table)
3. Teammate history — who they queue with most, their stats
4. Static analyst persona instructions

This replaces calling the MCP API every message — Claude gets full context once per session from the DB.

**`get_squad_context()`**

Builds a summary of all tracked players for squad-wide questions.

---

## Phase 4 — Chat Loop

### 4.1 `main.py`

**Startup sequence:**
1. Initialize DB (create tables if not exist)
2. Run `sync_all()` for all tracked players
3. Launch Gradio UI

**Per-message flow:**
1. User sends message
2. Build system prompt from DB via `build_system_prompt()`
3. Append to conversation history
4. Call Claude API with full history + system prompt
5. Stream response back to UI
6. Append assistant response to history

**MCP usage:**
- MCP is used only during sync (Phase 2), not during chat
- During chat, Claude works from DB context injected into the system prompt
- This avoids MCP latency on every message and removes the 10-match cap

### 4.2 Gradio UI components

- Chat window (main interaction)
- Player selector dropdown (switch focus between squad members)
- "Sync now" button (manual re-sync outside of startup)
- Match count display (shows how many matches are stored per player)

---

## Phase 5 — Enhancements (Post-MVP)

| Feature | Notes |
|---|---|
| Auto-sync on schedule | Run `sync_all()` on a background thread every 30 min |
| Match detail drill-down | Store round-by-round data via `get_match_details` |
| Win/loss streaks | Computed query from `matches` table, injected into context |
| Map stats | Aggregate by map from DB, surface in system prompt |
| Export to Discord | Format DB queries as ready-to-paste Discord blocks |
| Multi-player comparison | `analyst/context.py` builds cross-player context on demand |

---

## Implementation Order

1. `db/schema.py` — tables + init function
2. `db/queries.py` — insert + read helpers
3. `mcp/client.py` — sync logic against live MCP
4. Manual test: run sync, verify DB has rows
5. `analyst/context.py` — system prompt builder
6. `main.py` — wire Gradio UI + Claude API + context builder
7. End-to-end test: chat session using DB context
8. Phase 5 enhancements as desired

---

## Dependencies

```
anthropic
gradio
sqlite3      # built-in
json         # built-in
```

```bash
pip install anthropic gradio
```
