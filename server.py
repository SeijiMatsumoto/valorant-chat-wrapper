import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db.schema import init_db, get_connection
from db.queries import (
    get_match_count,
    create_conversation,
    update_conversation_title,
    list_conversations,
    delete_conversation,
    save_message,
    get_messages,
    get_display_messages,
)
from sync.client import (
    TRACKED_PLAYERS,
    call_mcp_tool_sync,
    handle_db_tool,
)
from analyst.context import build_system_prompt, TOOLS, MCP_TOOL_NAMES

# ── Claude client ───────────────────────────────────────────────

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"

# ── Agent loop (moved from main.py) ────────────────────────────


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name in MCP_TOOL_NAMES:
        return call_mcp_tool_sync(tool_name, tool_input)
    else:
        return handle_db_tool(tool_name, tool_input)


def _serialize_content(content) -> list:
    """Convert anthropic API content blocks to JSON-serializable format."""
    serialized = []
    for block in content:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return serialized


def run_agent_loop(user_message: str, conv_id: str) -> str:
    """Run the agentic loop, persisting every message to the DB."""
    system_prompt = build_system_prompt()
    conn = get_connection()

    try:
        # Save the user message
        save_message(conn, conv_id, "user", user_message)

        # Load full conversation history for the API
        all_msgs = get_messages(conn, conv_id)
        api_messages = []
        for msg in all_msgs:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Agentic loop
        while True:
            response = CLIENT.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=api_messages,
            )

            if response.stop_reason == "end_turn":
                text_parts = [b.text for b in response.content if b.type == "text"]
                final_text = "\n".join(text_parts)
                save_message(conn, conv_id, "assistant", final_text)
                return final_text

            # Assistant message with tool calls
            assistant_content = _serialize_content(response.content)
            save_message(conn, conv_id, "assistant", assistant_content)
            api_messages.append({"role": "assistant", "content": assistant_content})

            # Execute tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  Tool: {block.name}({json.dumps(block.input)[:80]}...)")
                    try:
                        result = handle_tool_call(block.name, block.input)
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Save and append tool results as a "user" message (that's how the API works)
            save_message(conn, conv_id, "user", tool_results)
            api_messages.append({"role": "user", "content": tool_results})

    finally:
        conn.close()


def _auto_title(conv_id: str, user_message: str):
    """Set conversation title from first message (truncated)."""
    title = user_message[:60] + ("..." if len(user_message) > 60 else "")
    conn = get_connection()
    try:
        update_conversation_title(conn, conv_id, title)
    finally:
        conn.close()


# ── FastAPI app ─────────────────────────────────────────────────

app = FastAPI(title="Valorant Squad Analyst API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    print("Initializing database...")
    init_db()
    print("Database ready.")


# ── Request / Response models ───────────────────────────────────


class SendMessageRequest(BaseModel):
    message: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


# ── Endpoints ───────────────────────────────────────────────────


@app.get("/api/conversations")
def api_list_conversations(limit: int = 30):
    conn = get_connection()
    try:
        convos = list_conversations(conn, limit=limit)
    finally:
        conn.close()
    return convos


@app.post("/api/conversations", response_model=ConversationOut)
def api_create_conversation():
    conn = get_connection()
    try:
        conv_id = create_conversation(conn)
        # Fetch the full row to return
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


@app.delete("/api/conversations/{conv_id}")
def api_delete_conversation(conv_id: str):
    conn = get_connection()
    try:
        # Check it exists
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        delete_conversation(conn, conv_id)
    finally:
        conn.close()
    return {"status": "deleted"}


@app.get("/api/conversations/{conv_id}/messages")
def api_get_messages(conv_id: str):
    conn = get_connection()
    try:
        msgs = get_display_messages(conn, conv_id)
    finally:
        conn.close()
    return msgs


@app.post("/api/conversations/{conv_id}/messages")
def api_send_message(conv_id: str, body: SendMessageRequest):
    conn = get_connection()
    try:
        # Verify conversation exists
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check if this is the first user message (for auto-titling)
        existing = get_display_messages(conn, conv_id)
    finally:
        conn.close()

    is_first_message = len(existing) == 0

    # Auto-title from the first message
    if is_first_message:
        _auto_title(conv_id, body.message)

    # Run the agent loop (blocking — may take a while with tool calls)
    try:
        response_text = run_agent_loop(body.message, conv_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"response": response_text}


@app.get("/api/match-counts")
def api_match_counts():
    conn = get_connection()
    try:
        counts = {username: get_match_count(conn, username) for username in TRACKED_PLAYERS}
    finally:
        conn.close()
    return counts


# ── Static file serving for SPA ─────────────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

try:
    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
        print(f"Serving frontend from {FRONTEND_DIR}")
    else:
        print(f"Frontend directory not found at {FRONTEND_DIR} — skipping static file serving")
except Exception as e:
    print(f"Could not mount frontend static files: {e}")


# ── Main entry point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
