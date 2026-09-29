"""Explicit two-process local development entry point; no automatic launch."""
from __future__ import annotations

import argparse
import json
import sys

from .contract import CONTENT_VERSION, DEFAULT_ORIGINS, DEFAULT_PORT, bridge_error
from .server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-version", required=True, choices=[CONTENT_VERSION])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--allow-origin", action="append", help="Replace the default allowlist with explicit local development origins.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        server = create_server(args.content_version, port=args.port,
                               allowed_origins=tuple(args.allow_origin) if args.allow_origin else DEFAULT_ORIGINS)
    except Exception:
        print(json.dumps(bridge_error("INTERNAL_ERROR", "STARTUP")))
        sys.exit(2)
    print(f"HSR Scenario bridge: http://127.0.0.1:{args.port} (content 4.4.54, compile/support only)", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
