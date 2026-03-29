import threading
import time
import urllib.request
import uvicorn
import webview

from db.schema import init_db


def main():
    print("Initializing database...")
    init_db()
    print("Database ready.\n")

    # Start FastAPI in a background thread
    def start_server():
        uvicorn.run("server:app", host="127.0.0.1", port=8000, log_level="warning")

    threading.Thread(target=start_server, daemon=True).start()

    # Wait for server to be ready
    print("Starting server...")
    for _ in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/match-counts")
            break
        except Exception:
            time.sleep(0.5)
    print("Server ready.\n")

    # Open native desktop window
    webview.create_window(
        "Valorant Squad Analyst",
        "http://127.0.0.1:8000",
        width=1200,
        height=850,
    )
    webview.start()


if __name__ == "__main__":
    main()
