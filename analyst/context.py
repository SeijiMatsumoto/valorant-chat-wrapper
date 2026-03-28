from db.schema import get_connection
from db.queries import get_match_count
from sync.client import TRACKED_PLAYERS

SYSTEM_PROMPT = """You are a Valorant analyst and coach for a friend group's squad. You have deep knowledge of Valorant mechanics, agents, maps, economy, and meta.

Your personality:
- Supportive and constructive — highlight strengths, frame weaknesses as growth opportunities
- Data-driven — back up observations with the stats you fetch
- Casual but knowledgeable — you're talking to friends, not writing a formal report
- Proactive — suggest specific improvements, agent picks, or strategies

When presenting stats, focus on each player's strengths and contributions to the team.
Never label anyone as the "weakest link", "worst performer", or similar negative framing.
Players have different roles — a sentinel with fewer kills is still contributing with site holds and utility.

## How you work

You have two data sources:

1. **Live Valorant API tools** — fetch current data (match history, agent stats, rank, etc.). Match history is limited to 10 most recent matches per call.

2. **Local database** — every time you fetch match history from the API, those matches are automatically saved. Over time this builds up a history beyond the 10-match API limit. Use `get_stored_matches` to access the full history.

**Your workflow when analyzing a player:**
1. Fetch their recent matches from the API (this also saves them to the DB)
2. Check the database for older historical matches to get the full picture
3. Combine both to give a thorough analysis

## Citing your data

ALWAYS show the data behind your conclusions. When you make a claim, include the specific numbers, matches, or stats that support it. For example:
- Instead of "You've been doing well on Jett" → "You're 6-2 on Jett across 8 stored matches, averaging 18.3 kills with a 24% headshot rate"
- Instead of "Your aim has improved" → "Your headshot % went from 12% (Mar 20-22, 3 matches) to 21% (Mar 25-28, 5 matches)"
- Instead of "You struggle on Ascent" → "You're 1-4 on Ascent: losses on Mar 21 (8-13), Mar 23 (10-13), Mar 25 (7-13), Mar 27 (9-13), with your only win on Mar 22 (13-11)"

Always mention how many matches your analysis is based on (e.g. "based on 15 stored matches" or "across your last 10 games"). This helps the user understand the confidence level of your analysis.

## Tracked squad members
{squad_list}
"""

# Tool definitions for the Claude API
TOOLS = [
    {
        "name": "get_player_info",
        "description": "Fetch basic account info for a given Riot ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID (e.g. 'Player#TAG')"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_match_history",
        "description": "Fetch recent match history from the Valorant API. Max 10 matches per call. Results are automatically saved to the local database for future reference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID (e.g. 'Player#TAG')"},
                "count": {"type": "integer", "description": "Number of matches to fetch (max 10)", "default": 5},
                "mode": {"type": "string", "description": "Game mode: competitive, unrated, deathmatch, swiftplay, spikerush, premier", "default": "competitive"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_rank_progression",
        "description": "Get a player's current rank, elo, MMR change, peak rank, and season-by-season rank history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_agent_stats",
        "description": "Get aggregated per-agent stats from a player's recent matches: games played, wins, losses, win rate, avg kills/deaths/assists/score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID"},
                "count": {"type": "integer", "description": "Number of recent matches to analyze (max 10)", "default": 10},
                "mode": {"type": "string", "default": "competitive"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_map_stats",
        "description": "Get aggregated per-map stats from a player's recent matches: games played, wins, losses, win rate, avg score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID"},
                "count": {"type": "integer", "description": "Number of recent matches to analyze (max 10)", "default": 10},
                "mode": {"type": "string", "default": "competitive"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_weapon_stats",
        "description": "Get weapon usage stats from a player's recent matches: kills per weapon, usage percentage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID"},
                "count": {"type": "integer", "description": "Number of recent matches (max 5)", "default": 5},
                "mode": {"type": "string", "default": "competitive"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_match_details",
        "description": "Get full details of a specific match by match ID, including all players, round-by-round data, and kill feed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "The match ID"},
            },
            "required": ["match_id"],
        },
    },
    {
        "name": "get_stored_matches",
        "description": "Query historical matches from the local database. Data accumulates over time beyond the API's 10-match limit. You control how many matches to pull and which columns/filters to use — request only what you need for the analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID (e.g. 'Player#TAG')"},
                "limit": {"type": "integer", "description": "Max matches to return. Choose based on what you need.", "default": 20},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Which columns to return. Options: match_id, username, map, date, result, rounds_won, rounds_lost, agent, rank, kills, deaths, assists, score, headshot_pct, damage_made, damage_received. If omitted, returns all columns.",
                },
                "agent": {"type": "string", "description": "Filter to a specific agent (e.g. 'Jett')"},
                "map_name": {"type": "string", "description": "Filter to a specific map (e.g. 'Ascent')"},
                "result": {"type": "string", "description": "Filter by result: 'Win' or 'Loss'"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "get_stored_player_summary",
        "description": "Get a summary of what's stored in the local database for a player: match count, frequent teammates, win/loss streak, and agent stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Riot ID"},
            },
            "required": ["username"],
        },
    },
]

# Names of tools that get proxied to the MCP server (vs handled locally from DB)
MCP_TOOL_NAMES = {
    "get_player_info",
    "get_match_history",
    "get_rank_progression",
    "get_agent_stats",
    "get_map_stats",
    "get_weapon_stats",
    "get_match_details",
}


def build_system_prompt() -> str:
    conn = get_connection()
    try:
        lines = []
        for username in TRACKED_PLAYERS:
            count = get_match_count(conn, username)
            lines.append(f"- {username} ({count} matches stored in DB)")
    finally:
        conn.close()

    return SYSTEM_PROMPT.format(squad_list="\n".join(lines))
