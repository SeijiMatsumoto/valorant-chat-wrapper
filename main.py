import socket
import threading
import time
import urllib.request
import uvicorn
import webview

from db.schema import init_db

PORT = 8000


def _find_free_port(start: int) -> int:
    """Return start if available, otherwise try the next few ports."""
    for port in range(start, start + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    print("Initializing database...")
    init_db()
    print("Database ready.\n")

    port = _find_free_port(PORT)
    if port != PORT:
        print(f"Port {PORT} in use, using {port} instead.")

    # Start FastAPI in a background thread
    def start_server():
        uvicorn.run("server:app", host="127.0.0.1", port=port, log_level="warning")

    threading.Thread(target=start_server, daemon=True).start()

    # Wait for server to be ready
    print("Starting server...")
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/match-counts")
            break
        except Exception:
            time.sleep(0.5)
    print("Server ready.\n")

    # Open native desktop window
    webview.create_window(
        "Valorant Squad Analyst",
        f"http://127.0.0.1:{port}",
        width=1200,
        height=850,
    )
    webview.start()


if __name__ == "__main__":
    main()
