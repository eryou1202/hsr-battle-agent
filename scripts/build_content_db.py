"""Build deterministic Canonical JSONL and SQLite from a local raw snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import (
    build_from_snapshot,
    default_canonical_root,
    default_db_path,
    default_snapshot_root,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Content version, e.g. 4.4.54")
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--canonical-root", type=Path)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    result = build_from_snapshot(
        args.version,
        snapshot_root=args.snapshot_root or default_snapshot_root(args.version),
        canonical_root=args.canonical_root or default_canonical_root(args.version),
        database_path=args.database or default_db_path(args.version),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
