import json
from dotenv import load_dotenv
load_dotenv()

import gradio as gr
import anthropic

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

CLIENT = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"


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


# ── Gradio handlers ──────────────────────────────────────────


def chat(message: str, chat_history: list[dict], conv_id: str):
    """Handle a chat message."""
    if not conv_id:
        conn = get_connection()
        try:
            conv_id = create_conversation(conn)
        finally:
            conn.close()

    # Auto-title from first real message
    if not chat_history:
        _auto_title(conv_id, message)

    # Show user message + thinking placeholder
    chat_history = chat_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "Thinking... (calling tools as needed)"},
    ]
    yield chat_history, conv_id, ""

    # Run agent loop
    try:
        response = run_agent_loop(message, conv_id)
        chat_history[-1]["content"] = response
    except Exception as e:
        chat_history[-1]["content"] = f"Error: {e}"

    yield chat_history, conv_id, ""


def new_chat():
    """Start a new conversation."""
    conn = get_connection()
    try:
        conv_id = create_conversation(conn)
    finally:
        conn.close()
    return [], conv_id, refresh_conversation_list()


def load_conversation(conv_id: str):
    """Load an existing conversation."""
    if not conv_id:
        return [], "", refresh_conversation_list()
    conn = get_connection()
    try:
        display_msgs = get_display_messages(conn, conv_id)
    finally:
        conn.close()
    return display_msgs, conv_id, refresh_conversation_list()


def delete_chat(conv_id: str):
    """Delete a conversation."""
    if conv_id:
        conn = get_connection()
        try:
            delete_conversation(conn, conv_id)
        finally:
            conn.close()
    return [], "", refresh_conversation_list()


def refresh_conversation_list() -> list[list]:
    """Get conversation list for the dataframe display."""
    conn = get_connection()
    try:
        convos = list_conversations(conn, limit=30)
    finally:
        conn.close()
    if not convos:
        return []
    return [[c["id"], c["title"], c["updated_at"][:16]] for c in convos]


def get_match_counts_display() -> str:
    conn = get_connection()
    try:
        lines = [f"{u}: {get_match_count(conn, u)} matches" for u in TRACKED_PLAYERS]
    finally:
        conn.close()
    return "\n".join(lines)


def on_conversation_select(evt: gr.SelectData, conv_list):
    """Handle clicking a row in the conversation list."""
    import pandas as pd
    if isinstance(conv_list, pd.DataFrame):
        if conv_list.empty or evt.index[0] >= len(conv_list):
            return [], "", refresh_conversation_list()
        conv_id = str(conv_list.iloc[evt.index[0], 0])
    else:
        if not conv_list or evt.index[0] >= len(conv_list):
            return [], "", refresh_conversation_list()
        conv_id = conv_list[evt.index[0]][0]
    return load_conversation(conv_id)


def build_ui():
    with gr.Blocks(title="Valorant Squad Analyst") as app:
        # State for current conversation ID
        conv_id_state = gr.State("")

        gr.Markdown("# Valorant Squad Analyst")

        with gr.Row():
            # Sidebar
            with gr.Column(scale=1):
                new_chat_btn = gr.Button("+ New Chat", variant="primary")
                gr.Markdown("### History")
                conv_list = gr.Dataframe(
                    headers=["ID", "Title", "Updated"],
                    col_count=(3, "fixed"),
                    datatype=["str", "str", "str"],
                    value=refresh_conversation_list,
                    interactive=False,
                    column_widths=["0%", "70%", "30%"],
                )
                delete_btn = gr.Button("Delete Chat", variant="stop", size="sm")

                gr.Markdown("---")
                gr.Markdown("### Stored Matches")
                match_counts = gr.Textbox(
                    value=get_match_counts_display,
                    interactive=False,
                    lines=len(TRACKED_PLAYERS) + 1,
                    show_label=False,
                )
                refresh_btn = gr.Button("Refresh", size="sm")

            # Main chat area
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(height=750)
                msg_input = gr.Textbox(
                    placeholder="Ask about stats, performance, agent picks...",
                    label="Message",
                    lines=1,
                )

        # Chat submission
        msg_input.submit(
            chat,
            inputs=[msg_input, chatbot, conv_id_state],
            outputs=[chatbot, conv_id_state, msg_input],
        ).then(
            refresh_conversation_list,
            outputs=[conv_list],
        )

        # New chat
        new_chat_btn.click(
            new_chat,
            outputs=[chatbot, conv_id_state, conv_list],
        )

        # Load conversation from history
        conv_list.select(
            on_conversation_select,
            inputs=[conv_list],
            outputs=[chatbot, conv_id_state, conv_list],
        )

        # Delete chat
        delete_btn.click(
            delete_chat,
            inputs=[conv_id_state],
            outputs=[chatbot, conv_id_state, conv_list],
        )

        # Refresh match counts
        refresh_btn.click(get_match_counts_display, outputs=[match_counts])

    return app


def main():
    print("Initializing database...")
    init_db()
    print("Database ready.\n")

    print("Launching UI...")
    app = build_ui()
    app.launch(theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
