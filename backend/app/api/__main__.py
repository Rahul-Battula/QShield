"""``python -m app.api`` — serve the API and open the dashboard.

    python -m app.api [--host 127.0.0.1] [--port 8000] [--no-open]

Starts the backend (which also serves the frontend at ``/``). Run locally it
opens the dashboard in the default browser once it is answering.

On a hosting platform, set the ``PORT`` environment variable (most set it for
you): the server then binds ``0.0.0.0`` and does not try to open a browser.
"""

from __future__ import annotations

import argparse
import os
import threading
import time
import urllib.request
import webbrowser

import uvicorn

_LOOPBACK = {"127.0.0.1", "localhost", "0.0.0.0"}
_DEPLOYED = bool(os.environ.get("PORT"))


def _open_when_ready(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "api/health", timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.4)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qshield-api", description=__doc__)
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0" if _DEPLOYED else "127.0.0.1"),
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--no-open", dest="open_browser", action="store_false",
                        help="do not open a browser window")
    parser.set_defaults(open_browser=not _DEPLOYED)
    args = parser.parse_args(argv)

    shown = "127.0.0.1" if args.host in ("0.0.0.0", "localhost") else args.host
    url = f"http://{shown}:{args.port}/"
    print(f"QShield dashboard  ->  {url}\n(press Ctrl+C to stop)\n")
    if args.open_browser and args.host in _LOOPBACK:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    uvicorn.run("app.api.app:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
