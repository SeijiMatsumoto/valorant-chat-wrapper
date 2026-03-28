import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "valorant.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None):
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id    TEXT    NOT NULL,
            username    TEXT    NOT NULL,
            map         TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            result      TEXT    NOT NULL,
            rounds_won  INTEGER NOT NULL,
            rounds_lost INTEGER NOT NULL,
            agent       TEXT    NOT NULL,
            rank        TEXT    NOT NULL DEFAULT '',
            kills       INTEGER NOT NULL,
            deaths      INTEGER NOT NULL,
            assists     INTEGER NOT NULL,
            score       INTEGER NOT NULL,
            headshot_pct TEXT   NOT NULL DEFAULT '0%',
            damage_made  INTEGER NOT NULL DEFAULT 0,
            damage_received INTEGER NOT NULL DEFAULT 0,
            raw_json    TEXT    NOT NULL,
            PRIMARY KEY (match_id, username)
        );

        CREATE TABLE IF NOT EXISTS teammates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        TEXT    NOT NULL,
            player_username TEXT    NOT NULL,
            username        TEXT    NOT NULL,
            agent           TEXT    NOT NULL,
            rank            TEXT    NOT NULL DEFAULT '',
            kills           INTEGER NOT NULL,
            deaths          INTEGER NOT NULL,
            assists         INTEGER NOT NULL,
            score           INTEGER NOT NULL,
            FOREIGN KEY (match_id, player_username) REFERENCES matches(match_id, username)
        );

        CREATE TABLE IF NOT EXISTS opponents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        TEXT    NOT NULL,
            player_username TEXT    NOT NULL,
            username        TEXT    NOT NULL,
            agent           TEXT    NOT NULL,
            kda             TEXT    NOT NULL,
            FOREIGN KEY (match_id, player_username) REFERENCES matches(match_id, username)
        );

        CREATE TABLE IF NOT EXISTS agent_stats (
            username    TEXT    NOT NULL,
            agent       TEXT    NOT NULL,
            games       INTEGER NOT NULL,
            wins        INTEGER NOT NULL,
            losses      INTEGER NOT NULL,
            win_rate    TEXT    NOT NULL,
            avg_kills   REAL    NOT NULL,
            avg_deaths  REAL    NOT NULL,
            avg_assists REAL    NOT NULL,
            avg_score   REAL    NOT NULL,
            last_updated TEXT   NOT NULL,
            PRIMARY KEY (username, agent)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT    PRIMARY KEY,
            title       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT    NOT NULL,
            role            TEXT    NOT NULL,
            content         TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_matches_username ON matches(username);
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
        CREATE INDEX IF NOT EXISTS idx_teammates_player ON teammates(player_username);
        CREATE INDEX IF NOT EXISTS idx_opponents_player ON opponents(player_username);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
    """)

    if close:
        conn.close()
