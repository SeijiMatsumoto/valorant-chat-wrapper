import json
import sqlite3
import uuid
from datetime import datetime, timezone


def match_exists(conn: sqlite3.Connection, match_id: str, username: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM matches WHERE match_id = ? AND username = ?",
        (match_id, username),
    ).fetchone()
    return row is not None


def insert_match(conn: sqlite3.Connection, match: dict, username: str):
    """Insert a match row plus its teammates and opponents.

    `match` is expected to be a single entry from the match history JSON
    returned by the MCP get_match_history tool.
    """
    if match_exists(conn, match["match_id"], username):
        return False

    player = match["player"]
    rounds_parts = match["rounds"].split("-")

    conn.execute(
        """INSERT INTO matches
           (match_id, username, map, date, result, rounds_won, rounds_lost,
            agent, rank, kills, deaths, assists, score,
            headshot_pct, damage_made, damage_received, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            match["match_id"],
            username,
            match["map"],
            match["date"],
            match["result"],
            int(rounds_parts[0]),
            int(rounds_parts[1]),
            player["agent"],
            player.get("rank", ""),
            int(player["kda"].split("/")[0]),
            int(player["kda"].split("/")[1]),
            int(player["kda"].split("/")[2]),
            player.get("score", 0),
            player.get("headshot_pct", "0%"),
            player.get("damage_made", 0),
            player.get("damage_received", 0),
            json.dumps(match),
        ),
    )

    for tm in match.get("teammates", []):
        kda_parts = tm["kda"].split("/")
        conn.execute(
            """INSERT INTO teammates
               (match_id, player_username, username, agent, rank, kills, deaths, assists, score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match["match_id"],
                username,
                tm["name"],
                tm["agent"],
                tm.get("rank", ""),
                int(kda_parts[0]),
                int(kda_parts[1]),
                int(kda_parts[2]),
                tm.get("score", 0),
            ),
        )

    for opp in match.get("opponents", []):
        # opponents are formatted as "Agent (Name#Tag): K/D/A"
        agent_part, rest = opp.split(" (", 1)
        name_kda = rest.split("): ")
        conn.execute(
            """INSERT INTO opponents (match_id, player_username, username, agent, kda)
               VALUES (?, ?, ?, ?, ?)""",
            (match["match_id"], username, name_kda[0], agent_part, name_kda[1]),
        )

    return True


def upsert_agent_stats(conn: sqlite3.Connection, username: str, agent_stats: dict):
    """Upsert agent_stats rows from the MCP get_agent_stats response (parsed JSON dict)."""
    now = datetime.now(timezone.utc).isoformat()
    for agent, stats in agent_stats.items():
        conn.execute(
            """INSERT INTO agent_stats
               (username, agent, games, wins, losses, win_rate,
                avg_kills, avg_deaths, avg_assists, avg_score, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(username, agent) DO UPDATE SET
                 games=excluded.games, wins=excluded.wins, losses=excluded.losses,
                 win_rate=excluded.win_rate, avg_kills=excluded.avg_kills,
                 avg_deaths=excluded.avg_deaths, avg_assists=excluded.avg_assists,
                 avg_score=excluded.avg_score, last_updated=excluded.last_updated""",
            (
                username, agent,
                stats["games"], stats["wins"], stats["losses"], stats["win_rate"],
                stats["avg_kills"], stats["avg_deaths"], stats["avg_assists"],
                stats["avg_score"], now,
            ),
        )


# ── Read helpers ──────────────────────────────────────────────


def get_recent_matches(conn: sqlite3.Connection, username: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT raw_json FROM matches
           WHERE username = ?
           ORDER BY date DESC LIMIT ?""",
        (username, limit),
    ).fetchall()
    return [json.loads(row["raw_json"]) for row in rows]


# All columns available in the matches table
MATCH_COLUMNS = [
    "match_id", "username", "map", "date", "result",
    "rounds_won", "rounds_lost", "agent", "rank",
    "kills", "deaths", "assists", "score",
    "headshot_pct", "damage_made", "damage_received",
]


def query_matches(
    conn: sqlite3.Connection,
    username: str,
    limit: int = 20,
    columns: list[str] | None = None,
    agent: str | None = None,
    map_name: str | None = None,
    result: str | None = None,
) -> dict:
    """Flexible match query with optional filters and column selection."""
    # Validate/default columns
    if columns:
        cols = [c for c in columns if c in MATCH_COLUMNS]
        if not cols:
            cols = MATCH_COLUMNS
    else:
        cols = MATCH_COLUMNS

    select_clause = ", ".join(cols)
    where_parts = ["username = ?"]
    params: list = [username]

    if agent:
        where_parts.append("LOWER(agent) = LOWER(?)")
        params.append(agent)
    if map_name:
        where_parts.append("LOWER(map) = LOWER(?)")
        params.append(map_name)
    if result:
        where_parts.append("LOWER(result) = LOWER(?)")
        params.append(result)

    where_clause = " AND ".join(where_parts)
    params.append(limit)

    rows = conn.execute(
        f"SELECT {select_clause} FROM matches WHERE {where_clause} ORDER BY date DESC LIMIT ?",
        params,
    ).fetchall()

    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM matches WHERE {' AND '.join(where_parts[:-0] or where_parts)}",
        params[:-1],
    ).fetchone()["cnt"]

    return {
        "total_matching": total,
        "returned": len(rows),
        "columns": cols,
        "matches": [dict(row) for row in rows],
    }


def get_agent_stats(conn: sqlite3.Connection, username: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM agent_stats WHERE username = ? ORDER BY games DESC",
        (username,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_match_count(conn: sqlite3.Connection, username: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM matches WHERE username = ?",
        (username,),
    ).fetchone()
    return row["cnt"]


def get_all_match_counts(conn: sqlite3.Connection, usernames: list[str]) -> dict[str, int]:
    return {u: get_match_count(conn, u) for u in usernames}


def get_frequent_teammates(conn: sqlite3.Connection, username: str, limit: int = 5) -> list[dict]:
    """Find who this player queues with most based on teammate co-occurrence."""
    rows = conn.execute(
        """SELECT t.username as teammate, COUNT(*) as games_together,
                  ROUND(AVG(t.kills), 1) as avg_kills,
                  ROUND(AVG(t.deaths), 1) as avg_deaths,
                  ROUND(AVG(t.assists), 1) as avg_assists
           FROM teammates t
           WHERE t.player_username = ?
           GROUP BY t.username
           ORDER BY games_together DESC
           LIMIT ?""",
        (username, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_win_loss_streak(conn: sqlite3.Connection, username: str, limit: int = 20) -> dict:
    rows = conn.execute(
        """SELECT result FROM matches
           WHERE username = ?
           ORDER BY date DESC LIMIT ?""",
        (username, limit),
    ).fetchall()
    if not rows:
        return {"current_streak": "N/A", "results": []}

    results = [row["result"] for row in rows]
    streak_type = results[0]
    streak_count = 0
    for r in results:
        if r == streak_type:
            streak_count += 1
        else:
            break

    return {
        "current_streak": f"{streak_count} {streak_type}{'s' if streak_count > 1 else ''}",
        "last_results": results[:10],
    }


# ── Chat persistence ─────────────────────────────────────────


def create_conversation(conn: sqlite3.Connection, title: str = "New Chat") -> str:
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, title, now, now),
    )
    conn.commit()
    return conv_id


def update_conversation_title(conn: sqlite3.Connection, conv_id: str, title: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, now, conv_id),
    )
    conn.commit()


def touch_conversation(conn: sqlite3.Connection, conv_id: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
    conn.commit()


def list_conversations(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_conversation(conn: sqlite3.Connection, conv_id: str):
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()


def save_message(conn: sqlite3.Connection, conv_id: str, role: str, content) -> int:
    """Save a message. Content can be a string or complex object (tool blocks) — stored as JSON."""
    now = datetime.now(timezone.utc).isoformat()
    content_json = json.dumps(content) if not isinstance(content, str) else json.dumps(content)
    cursor = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (conv_id, role, content_json, now),
    )
    conn.commit()
    touch_conversation(conn, conv_id)
    return cursor.lastrowid


def get_messages(conn: sqlite3.Connection, conv_id: str) -> list[dict]:
    """Load all messages for a conversation, in order."""
    rows = conn.execute(
        "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()
    result = []
    for row in rows:
        result.append({
            "role": row["role"],
            "content": json.loads(row["content"]),
            "timestamp": row["timestamp"],
        })
    return result


def get_display_messages(conn: sqlite3.Connection, conv_id: str) -> list[dict]:
    """Load messages for Gradio display — only user text and assistant text, skip tool blocks."""
    all_msgs = get_messages(conn, conv_id)
    display = []
    for msg in all_msgs:
        role = msg["role"]
        content = msg["content"]

        if role == "user" and isinstance(content, str):
            display.append({"role": "user", "content": content})
        elif role == "assistant" and isinstance(content, str):
            display.append({"role": "assistant", "content": content})

    return display
