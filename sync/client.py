import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import sys

from db.schema import get_connection
from db.queries import (
    insert_match,
    get_match_count,
    get_frequent_teammates,
    get_win_loss_streak,
    get_agent_stats as get_db_agent_stats,
    query_matches,
)

try:
    from players import TRACKED_PLAYERS
except ImportError:
    print("ERROR: players.py not found. Copy players.example.py to players.py and add your Riot IDs.")
    sys.exit(1)

if not TRACKED_PLAYERS:
    print("WARNING: TRACKED_PLAYERS is empty in players.py. The agent can still look up any player, but the UI won't show stored match counts.")

MCP_SERVER_DIR = "/Users/seijimatsumoto/Documents/Coding/valorant-mcp"

SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "--directory", MCP_SERVER_DIR, "valorant-mcp"],
    env={
        "HENRIK_API_KEY": "HDEV-da07930f-5016-4b87-a1b8-8f91204df98d",
        "VALORANT_REGION": "na",
    },
)


def _auto_store_matches(raw_json: str, username: str) -> int:
    """Parse match history JSON and store new matches in DB. Returns count of new matches."""
    try:
        matches = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return 0

    if not isinstance(matches, list):
        return 0

    conn = get_connection()
    new_count = 0
    try:
        for match in matches:
            if insert_match(conn, match, username):
                new_count += 1
        conn.commit()
    finally:
        conn.close()

    return new_count


async def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call an MCP tool and return the result. Auto-stores match data."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            if result.isError:
                error_msg = result.content[0].text if result.content else "Unknown error"
                return json.dumps({"error": error_msg})

            text = result.content[0].text

            # Auto-store matches, return API result + DB status
            if tool_name == "get_match_history" and "username" in arguments:
                username = arguments["username"]
                new = _auto_store_matches(text, username)

                conn = get_connection()
                try:
                    total = get_match_count(conn, username)
                finally:
                    conn.close()

                # Return the raw API matches plus a note about DB state
                return text + f"\n\n[Sync: {new} new matches saved. Total in DB: {total}. Use get_stored_matches to query full history with filters.]"

            return text


def call_mcp_tool_sync(tool_name: str, arguments: dict) -> str:
    """Synchronous wrapper for call_mcp_tool."""
    return asyncio.run(call_mcp_tool(tool_name, arguments))


def handle_db_tool(tool_name: str, arguments: dict) -> str:
    """Handle tools that read from the local database."""
    conn = get_connection()
    try:
        if tool_name == "get_stored_matches":
            result = query_matches(
                conn,
                username=arguments["username"],
                limit=arguments.get("limit", 20),
                columns=arguments.get("columns"),
                agent=arguments.get("agent"),
                map_name=arguments.get("map_name"),
                result=arguments.get("result"),
            )
            return json.dumps(result, indent=2)

        elif tool_name == "get_stored_player_summary":
            username = arguments["username"]
            total = get_match_count(conn, username)
            teammates = get_frequent_teammates(conn, username)
            streak = get_win_loss_streak(conn, username)
            agent_stats = get_db_agent_stats(conn, username)

            return json.dumps({
                "username": username,
                "total_matches_stored": total,
                "current_streak": streak.get("current_streak", "N/A"),
                "last_10_results": streak.get("last_results", []),
                "frequent_teammates": teammates,
                "agent_stats": agent_stats,
            }, indent=2)

        else:
            return json.dumps({"error": f"Unknown DB tool: {tool_name}"})
    finally:
        conn.close()
