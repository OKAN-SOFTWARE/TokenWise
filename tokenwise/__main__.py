"""Launch: python -m tokenwise --port 8765"""
import argparse
from pathlib import Path

from .server import TokenWiseServer


def main():
    parser = argparse.ArgumentParser(description="TokenWise local operator deck")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1",
                        help="Use 0.0.0.0 only behind a localhost-only Docker port mapping")
    parser.add_argument("--db", type=Path, default=Path(".tokenwise-data") / "runs.sqlite3")
    args = parser.parse_args()
    with TokenWiseServer((args.host, args.port), args.db) as http:
        print(f"TokenWise ready → http://127.0.0.1:{args.port}")
        print("Synthetic pricing only · Local requests only · No AWS calls")
        if args.host == "0.0.0.0":
            print("WARNING: bound to all interfaces; not authenticated or production hardened")
        try:
            http.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:
            print("\nTokenWise stopped")


if __name__ == "__main__":
    main()
