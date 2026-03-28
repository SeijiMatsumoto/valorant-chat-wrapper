# Valorant Squad Analyst

A local chat app that wraps Claude with a Valorant MCP integration and a SQLite database, enabling deep match history analysis beyond the API's 10-match limit.

## How It Works

1. **You ask a question** about any player's stats, performance, or the squad
2. **Claude calls MCP tools** to fetch live data from the Valorant API (match history, rank, agent stats, etc.)
3. **Match data is auto-stored** in a local SQLite database on every fetch
4. **History accumulates** over time — each session adds new matches, building a dataset far beyond the API's 10-match cap
5. **Claude queries the database** for the full picture when analyzing trends

Chat conversations are also persisted, so you can revisit or continue past analyses.

## Stack

| Layer | Technology |
|---|---|
| UI | Gradio |
| LLM | Claude (Anthropic API) |
| Valorant data | [Valorant Analyzer MCP](https://github.com/seijimatsumoto/valorant-mcp) (stdio, local via uv) |
| Database | SQLite (local file) |
| Language | Python 3.11+ |

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your Anthropic API key** to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Set up tracked players** — copy the example and add your Riot IDs:
   ```bash
   cp players.example.py players.py
   ```
   Then edit `players.py` with your squad's Riot IDs.

4. **Ensure the Valorant MCP server** is available locally (configured in `sync/client.py`).

4. **Run:**
   ```bash
   python3 main.py
   ```

   The Gradio UI will open in your browser.

## Project Structure

```
valorant-chat-wrapper/
├── main.py              # Gradio UI + agentic chat loop with tool use
├── analyst/
│   └── context.py       # System prompt + Claude tool definitions
├── db/
│   ├── schema.py        # SQLite tables (matches, teammates, opponents, conversations, messages)
│   └── queries.py       # All DB read/write functions
├── sync/
│   └── client.py        # MCP client proxy + auto-store logic
├── requirements.txt
├── .env                 # API key (not tracked)
└── valorant.db          # Auto-created on first run (not tracked)
```

## Tools Available to the Agent

**Live API (via MCP):**
- `get_match_history` — fetch recent matches (max 10), auto-saved to DB
- `get_agent_stats` — per-agent performance breakdown
- `get_map_stats` — per-map win rates and scores
- `get_weapon_stats` — weapon kill distribution
- `get_rank_progression` — current rank, MMR, peak rank, season history
- `get_player_info` — basic account info
- `get_match_details` — full match details by match ID

**Local Database:**
- `get_stored_matches` — query historical matches with filters (agent, map, result) and column selection
- `get_stored_player_summary` — match count, streaks, frequent teammates, agent stats

## Tracked Players

Configured in `players.py` (gitignored). Copy `players.example.py` to get started.
