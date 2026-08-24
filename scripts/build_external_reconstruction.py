"""Build external Canonical additions, SQLite augmentation, and evidence artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.external_reconstruction import (
    build_external_reconstruction,
    default_external_artifact_root,
    default_external_canonical_root,
    default_external_root,
)
from hsr_battle_agent.game_data.nanoka_content import default_db_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", default="4.4.54")
    parser.add_argument("--source-root", type=Path, default=default_external_root())
    parser.add_argument("--canonical-root", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    result = build_external_reconstruction(
        args.version,
        source_root=args.source_root,
        canonical_root=args.canonical_root or default_external_canonical_root(args.version),
        artifact_root=args.artifact_root or default_external_artifact_root(args.version),
        database_path=args.database or default_db_path(args.version),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
