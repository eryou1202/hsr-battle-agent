"""Publish conservative static-content to canonical-behavior coverage mapping."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.content_behavior_mapping import (
    build_content_behavior_mapping,
    character_tag_index,
    file_sha256,
    static_family_ids,
)
from hsr_battle_agent.game_data.nanoka_content import write_json


parser = argparse.ArgumentParser()
parser.add_argument("--database", type=Path, default=Path("data/db/hsr_content_4.4.54.sqlite"))
parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json"))
parser.add_argument("--compiler-report", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_002.json"))
parser.add_argument("--starrail-characters", type=Path, default=Path(".external_refs/StarRailRes/files/index_new/cn/characters.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/content_behavior_mapping_001.json"))
parser.add_argument("--game-version", default="4.4.54")
arguments = parser.parse_args()

corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
compiler_report = json.loads(arguments.compiler_report.read_text(encoding="utf-8"))
characters = json.loads(arguments.starrail_characters.read_text(encoding="utf-8"))
payload = build_content_behavior_mapping(
    corpus,
    compiler_report,
    static_family_ids(arguments.database, arguments.game_version),
    character_tag_index(characters),
    source_metadata={
        "canonical_behavior_corpus_sha256": corpus.get("corpus_sha256"),
        "canonical_behavior_corpus_path": str(arguments.corpus).replace("\\", "/"),
        "compiler_report_sha256": compiler_report.get("report_sha256"),
        "compiler_report_path": str(arguments.compiler_report).replace("\\", "/"),
        "content_database_path": str(arguments.database).replace("\\", "/"),
        "content_database_sha256": file_sha256(arguments.database),
        "starrailres_character_index_path": str(arguments.starrail_characters).replace("\\", "/"),
        "starrailres_character_index_sha256": file_sha256(arguments.starrail_characters),
        "starrailres_relation": "CLIENT_DUMP_DERIVED_DATA_CACHED_PINNED_SOURCE",
    },
)
write_json(arguments.output, payload)
print(json.dumps({
    "output_path": str(arguments.output),
    "report_sha256": payload["report_sha256"],
    "static_family_coverage": payload["static_family_coverage"],
}, ensure_ascii=False, sort_keys=True))
