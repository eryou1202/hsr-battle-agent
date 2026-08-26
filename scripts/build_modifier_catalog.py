"""Build the auditable canonical Modifier catalog used by reference execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hsr_battle_agent.game_data.modifier_catalog import modifier_catalog_from_corpus
from hsr_battle_agent.game_data.nanoka_content import stable_hash, write_json


parser = argparse.ArgumentParser()
parser.add_argument("--corpus", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/external_behavior_corpus_v1.json"))
parser.add_argument("--output", type=Path, default=Path("data/semantics/4.4.54/full_reconstruction/modifier_catalog_001.json"))
arguments = parser.parse_args()
corpus = json.loads(arguments.corpus.read_text(encoding="utf-8"))
catalog = modifier_catalog_from_corpus(corpus)
payload = {
    "catalog_id": "MODIFIER-CATALOG-001",
    "game_version": corpus.get("game_version"),
    "input_corpus_sha256": corpus.get("corpus_sha256"),
    "scope": "Only canonical Modifier records with explicit source Stacking values selected by PRIM-MODIFIER-001.",
    "unsupported_policy": "Missing/unsupported/conflicting Stacking is omitted; AddModifier must remain structural rather than receiving an inferred default.",
    "definitions": [definition.as_json() for _name, definition in sorted(catalog.items())],
}
payload["catalog_sha256"] = stable_hash(payload)
write_json(arguments.output, payload)
print(json.dumps({"output_path": str(arguments.output), "definitions": len(catalog), "catalog_sha256": payload["catalog_sha256"]}, sort_keys=True))
