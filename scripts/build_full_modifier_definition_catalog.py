"""Build the auditable full-content Modifier definition catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.modifier_catalog import modifier_catalog_report_from_corpus
from hsr_battle_agent.game_data.nanoka_content import write_json


parser = argparse.ArgumentParser()
parser.add_argument(
    "--corpus",
    type=Path,
    default=Path("data/semantics/4.4.54/full_reconstruction/full_content_behavior_corpus_001.json"),
)
parser.add_argument(
    "--output",
    type=Path,
    default=Path("data/semantics/4.4.54/full_reconstruction/full_modifier_definition_catalog_001.json"),
)
arguments = parser.parse_args()

corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
report = modifier_catalog_report_from_corpus(corpus)
report.update({
    "report_id": "FULL-MODIFIER-DEFINITION-CATALOG-001",
    "game_version": corpus.get("game_version"),
    "corpus_id": corpus.get("corpus_id"),
    "corpus_sha256": corpus.get("corpus_sha256"),
})
write_json(arguments.output, report)
print(json.dumps({
    "output_path": str(arguments.output),
    "definition_candidate_count": report["definition_candidate_count"],
    "unique_definition_name_count": report["unique_definition_name_count"],
    "equivalent_duplicate_count": report["equivalent_duplicate_count"],
    "true_conflict_count": report["true_conflict_count"],
    "supported_catalog_definition_count": report["supported_catalog_definition_count"],
    "unsupported_definition_count": report["unsupported_definition_count"],
    "catalog_sha256": report["catalog_sha256"],
}, ensure_ascii=False, sort_keys=True))
