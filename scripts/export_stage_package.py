"""Export one self-contained static Scenario Package from local SQLite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, default_db_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("stage_id")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package = ContentDatabase(args.database or default_db_path(args.version), args.version).get_stage_package(args.stage_id)
    if package is None:
        raise SystemExit(f"stage not found: {args.stage_id}")
    rendered = json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
