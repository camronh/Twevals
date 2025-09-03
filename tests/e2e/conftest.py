import threading
import time
from contextlib import contextmanager

import uvicorn


@contextmanager
def run_server(app, host: str = "127.0.0.1", port: int = 8765):
    """Run a uvicorn server in a background thread for the duration of the context."""
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait briefly for startup
    time.sleep(0.5)
    try:
        yield f"http://{host}:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=3)

