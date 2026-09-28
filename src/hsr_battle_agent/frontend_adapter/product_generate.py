"""Offline P5A generator; this is not a dynamic transport or a startup hook."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from hsr_battle_agent.content_support import load_registry
from hsr_battle_agent.game_data.content_product import ContentProductService
from hsr_battle_agent.game_data.nanoka_content import ContentDatabase, stable_bytes, stable_hash
from . import product_render as render

DEFAULT_CHUNK_BYTES = 1_048_576


def _bytes(document: Any) -> bytes:
    return stable_bytes(document) + b"\n"


def pack_details(version: str, collection: str, documents: list[dict[str, Any]], *,
                 chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Pack intact backend documents in order, with a measured byte ceiling.

    One document larger than the ceiling gets its own explicitly marked chunk.
    No semantic fields are removed or shortened to fit the target.
    """
    if version != "4.4.54" or collection not in render.COLLECTIONS or chunk_bytes < 256:
        raise ValueError("INVALID_DETAIL_TRANSPORT_PARAMETERS")
    key_field = render.KEY_FIELDS[collection]
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    envelope = {"schema": render.DETAIL_CHUNK_SCHEMA, "content_version": version,
                "collection": collection, "document_schema": render.PRODUCT_SCHEMAS[collection],
                "documents": []}
    # Replacing [] by N serialized documents adds sum(lengths) + N-1 commas.
    current_size = len(_bytes(envelope))
    keys = set()
    total_product_bytes = 0
    for document in documents:
        if document["schema"] != render.PRODUCT_SCHEMAS[collection] or document["game_version"] != version:
            raise ValueError("INVALID_PRODUCT_DOCUMENT")
        key = document["identity"]["requested_id" if collection == "monsters" else key_field]
        if key in keys:
            raise ValueError("DUPLICATE_PRODUCT_KEY")
        keys.add(key)
        size = len(stable_bytes(document))
        total_product_bytes += size + 1
        if current and current_size + size + 1 > chunk_bytes:
            groups.append(current)
            current = []
            current_size = len(_bytes(envelope))
        current_size += size + int(bool(current))
        current.append(document)
    if current:
        groups.append(current)
    files = {}
    locations = {}
    chunks = []
    for number, group in enumerate(groups):
        location = f"{collection}/details-{number:04d}.json"
        payload = _bytes({**envelope, "documents": group})
        files[location] = payload
        chunks.append({"location": location, "size_bytes": len(payload),
                       "sha256": sha256(payload).hexdigest(), "document_count": len(group),
                       "oversize_single_document": len(payload) > chunk_bytes})
        for document in group:
            key = document["identity"]["requested_id" if collection == "monsters" else key_field]
            locations[key] = location
    index = {"schema": render.DETAIL_INDEX_SCHEMA, "content_version": version,
             "collection": collection, "document_schema": render.PRODUCT_SCHEMAS[collection],
             "key_field": key_field, "count": len(documents), "locations": locations,
             "chunks": chunks, "chunk_target_bytes": chunk_bytes,
             "product_documents_total_bytes": total_product_bytes,
             "transport_total_bytes": sum(len(payload) for payload in files.values())}
    return index, files


def generate(version: str, database: ContentDatabase, output: Path, *,
             starting_head: str, authority_root: Path, p4_examples: Path,
             chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> dict[str, Any]:
    """Generate a complete explicitly versioned static transport and measurements."""
    if version != "4.4.54" or database.game_version != version:
        raise ValueError("EXPLICIT_4_4_54_REQUIRED")
    if output.exists() and any(output.iterdir()):
        raise ValueError("OUTPUT_MUST_BE_EMPTY_TO_PRESERVE_EXISTING_DOCUMENTS")
    started = perf_counter()
    service = ContentProductService(database, registry=load_registry(version))
    authority_names = (
        "content_product_projection_20260928_001.json",
        "stage_encounter_product_projection_20260928_001.json",
        "scenario_support_report_20260929_001.json",
    )
    authorities = [{"path": f"data/control/{name}",
                    "sha256": sha256((authority_root / name).read_bytes()).hexdigest()}
                   for name in authority_names]
    p4 = json.loads((authority_root / authority_names[-1]).read_text(encoding="utf-8"))
    files: dict[str, bytes] = {}
    examples = []
    for key in ("A_free", "B_stage_backed", "C_m14_missing"):
        source = p4_examples / f"p4_example_{key}.json"
        payload = source.read_bytes()
        document = json.loads(payload)
        expected = p4["fixtures"][key]
        if (document["schema"] != render.REPORT_SCHEMA
                or document["identity"]["content_version"] != version
                or document["report_sha256"] != expected["report_sha256"]
                or document["report_sha256"] != stable_hash(
                    {k: v for k, v in document.items() if k != "report_sha256"})
                or document["identity"]["scenario_package_sha256"] != expected["scenario_package_sha256"]):
            raise ValueError("P4_EXAMPLE_AUTHORITY_MISMATCH")
        location = f"examples/p4_{key}.json"
        files[location] = payload  # Preserve P4 authority byte for byte.
        examples.append({"key": key, "location": location, "examples_only": True,
                         "production_default": False, "document_schema": render.REPORT_SCHEMA,
                         "sha256": sha256(payload).hexdigest()})
    timings = {}
    catalogs = {}
    family_metrics = {}
    catalog_emitters = (render.emit_character_catalog, render.emit_monster_catalog,
                        render.emit_stage_catalog, render.emit_encounter_catalog)
    detail_emitters = (render.emit_character_detail, render.emit_monster_detail,
                       render.emit_stage_detail, render.emit_encounter_detail)
    for name, catalog_emitter, detail_emitter in zip(render.COLLECTIONS, catalog_emitters, detail_emitters):
        before = perf_counter()
        catalog = catalog_emitter(version, service)
        catalogs[name] = catalog
        files[f"{name}/catalog.json"] = _bytes(catalog)
        timings[f"{name}_catalog_seconds"] = round(perf_counter() - before, 6)
        before = perf_counter()
        documents = [detail_emitter(version, service, row[render.KEY_FIELDS[name]]) for row in catalog["rows"]]
        index, chunks = pack_details(version, name, documents, chunk_bytes=chunk_bytes)
        files.update(chunks)
        files[f"{name}/detail-index.json"] = _bytes(index)
        timings[f"{name}_details_seconds"] = round(perf_counter() - before, 6)
        family_metrics[name] = {"count": len(documents), "chunk_count": len(chunks),
                                "catalog_bytes": len(files[f"{name}/catalog.json"]),
                                "detail_index_bytes": len(files[f"{name}/detail-index.json"]),
                                "product_documents_total_bytes": index["product_documents_total_bytes"],
                                "detail_transport_bytes": index["transport_total_bytes"],
                                "max_chunk_bytes": max((len(b) for b in chunks.values()), default=0)}
    root = render.emit_product_catalog(version, service, catalogs=catalogs, examples=tuple(examples),
                                      provenance={"starting_head": starting_head, "authorities": authorities,
                                                  "generator": "hsr_battle_agent.frontend_adapter.product_generate",
                                                  "content_version": version, "locale": None,
                                                  "m14_registry_supplied": True})
    files["catalog.json"] = _bytes(root)
    output.mkdir(parents=True, exist_ok=True)
    for relative, payload in files.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    timings["total_seconds"] = round(perf_counter() - started, 6)
    return {"content_version": version, "catalog_root_bytes": len(files["catalog.json"]),
            "all_browse_catalog_bytes": len(files["catalog.json"]) + sum(m["catalog_bytes"] for m in family_metrics.values()),
            "chunk_target_bytes": chunk_bytes, "families": family_metrics,
            "generation_timings": timings,
            "files": {name: {"size_bytes": len(payload), "sha256": sha256(payload).hexdigest()}
                      for name, payload in sorted(files.items())}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-version", required=True, choices=["4.4.54"])
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--starting-head", required=True)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--p4-examples", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    args = parser.parse_args()
    metrics = generate(args.content_version, ContentDatabase(args.database, args.content_version),
                       args.output, starting_head=args.starting_head, authority_root=args.authority_root,
                       p4_examples=args.p4_examples)
    args.measurements.write_bytes(_bytes(metrics))
    print(json.dumps({key: value for key, value in metrics.items() if key != "files"}, indent=2))


if __name__ == "__main__":
    main()
