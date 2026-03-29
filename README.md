# Valorant Squad Analyst

A desktop chat app that wraps Claude with a Valorant MCP integration and a SQLite database, enabling deep match history analysis beyond the API's 10-match limit.

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
| Frontend | React + Tailwind CSS (Vite) |
| Backend | FastAPI (Python) |
| LLM | Claude (Anthropic API) |
| Valorant data | [Valorant Analyzer MCP](https://github.com/seijimatsumoto/valorant-mcp) (stdio, local via uv) |
| Database | SQLite (local file) |
| Desktop wrapper | pywebview |

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install frontend dependencies and build

```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Add your Anthropic API key to `.env`

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Set up tracked players

```bash
cp players.example.py players.py
```

Edit `players.py` with your squad's Riot IDs.

### 5. Ensure the Valorant MCP server is available locally

Configured in `sync/client.py`.

### 6. Run

```bash
python3 main.py
```

This starts the FastAPI backend, serves the React frontend, and opens a native desktop window.

### macOS desktop shortcut

A `.app` bundle is available in `/Applications/ValorantSquadAnalyst.app` for launching from Spotlight or the Dock. See the project wiki or create one manually:

```
ValorantSquadAnalyst.app/
  Contents/
    Info.plist
    MacOS/
      launcher    # shell script that runs `python3 main.py`
    Resources/
      AppIcon.icns
```

### Windows

The app runs on Windows with the same command (`python main.py`). To create a desktop shortcut, make a `.bat` file:

```bat
@echo off
cd /d "C:\path\to\valorant-chat-wrapper"
python main.py
```

Right-click the `.bat` file → **Create shortcut**, then move the shortcut to your Desktop or Start Menu.

## Development

For frontend hot-reload while editing React components, run the backend and frontend separately:

```bash
# Terminal 1 — backend
python3 server.py

# Terminal 2 — frontend dev server (proxies API to :8000)
cd frontend && npm run dev
```

## Project Structure

```
valorant-chat-wrapper/
├── main.py              # Desktop launcher (FastAPI + pywebview)
├── server.py            # FastAPI backend + agentic chat loop
├── analyst/
│   └── context.py       # System prompt + Claude tool definitions
├── db/
│   ├── schema.py        # SQLite tables (matches, teammates, opponents, conversations, messages)
│   └── queries.py       # All DB read/write functions
├── sync/
│   └── client.py        # MCP client proxy + auto-store logic
├── frontend/            # React + Tailwind (Vite)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts
│   │   └── components/  # Sidebar, ChatArea, MessageBubble, etc.
│   └── dist/            # Built static files (served by FastAPI)
├── requirements.txt
├── players.example.py
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
