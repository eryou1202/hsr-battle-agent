"""Fetch the small, pinned public-reference snapshot for external reconstruction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_reconstruction import (
    ExternalReferenceFetcher,
    default_external_root,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=default_external_root())
    parser.add_argument("--source", action="append", dest="sources", help="Repeat to fetch only selected source names")
    args = parser.parse_args()
    print(json.dumps(ExternalReferenceFetcher(args.root).fetch(args.sources), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
