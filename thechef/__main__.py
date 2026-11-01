"""Run with:  uv run python -m thechef  [--host 0.0.0.0] [--port 8000] [--dev]"""

import argparse

from sanic import Sanic
from sanic.worker.loader import AppLoader

from .app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TheChef")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dev", action="store_true", help="auto-reload and debug")
    parser.add_argument("--cert", help="TLS certificate (enables HTTPS, needed for iPhone camera)")
    parser.add_argument("--key", help="TLS private key")
    args = parser.parse_args()

    loader = AppLoader(factory=create_app)
    app = loader.load()
    ssl = {"cert": args.cert, "key": args.key} if args.cert and args.key else None
    app.prepare(host=args.host, port=args.port, dev=args.dev, ssl=ssl)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()
