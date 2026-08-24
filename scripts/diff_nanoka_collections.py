"""Write a compact raw-collection delta; it never imports newer values."""
from __future__ import annotations

import argparse
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import (
    default_snapshot_root,
    diff_collection_snapshots,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("from_version")
    parser.add_argument("to_version")
    parser.add_argument("--from-root", type=Path)
    parser.add_argument("--to-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = diff_collection_snapshots(
        args.from_root or default_snapshot_root(args.from_version),
        args.to_root or default_snapshot_root(args.to_version),
        from_version=args.from_version,
        to_version=args.to_version,
    )
    output = args.output or Path("data") / "content" / "diffs" / f"{args.from_version}_to_{args.to_version}.json"
    write_json(output, result)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
