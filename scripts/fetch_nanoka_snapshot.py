"""Fetch a resumable, version-locked Nanoka raw snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import (
    DEFAULT_LOCALE,
    NanokaSnapshotFetcher,
    default_snapshot_root,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Nanoka HSR content version, e.g. 4.4.54")
    parser.add_argument("--locale", default=DEFAULT_LOCALE)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--workers", type=int, default=3, help="1..4; default 3")
    parser.add_argument("--refresh", action="store_true", help="conditional refresh; raw changes are rejected")
    parser.add_argument("--collections-only", action="store_true")
    args = parser.parse_args()
    result = NanokaSnapshotFetcher(
        args.version,
        locale=args.locale,
        root=args.root or default_snapshot_root(args.version),
        workers=args.workers,
        refresh=args.refresh,
    ).fetch(include_details=not args.collections_only)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
