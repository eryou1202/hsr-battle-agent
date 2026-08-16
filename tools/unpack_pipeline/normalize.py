# -*- coding: utf-8 -*-
"""STAGE 9 - NORMALIZATION.

Stable normalized registries are written as records-array JSON files:

    types.json, methods.json, fields.json, parameters.json

Evidence fields (`structure_status`, `semantic_status`) and UNKNOWN values are
preserved.  Method rows receive the native RVA / mapping kind recovered by the
method code registry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from .common import utc_now, write_json
from .mhy_core import MhyModel


def _write_records(path: Path, schema: str, metadata: dict[str, Any],
                   records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("{\n")
        fh.write(f'  "schema": {json.dumps(schema)},\n')
        for key, value in metadata.items():
            fh.write(f'  {json.dumps(key)}: {json.dumps(value)},\n')
        fh.write('  "records": [\n')
        first = True
        for record in records:
            if not first:
                fh.write(",\n")
            first = False
            fh.write("    " + json.dumps(record, separators=(",", ":"), ensure_ascii=False))
        fh.write("\n  ]\n}\n")


def _native_array(table_path: Path, nmethods: int):
    import struct
    raw = Path(table_path).read_bytes()
    values = []
    for i in range(nmethods):
        q = struct.unpack_from("<Q", raw, i * 8)[0]
        values.append(q)
    return values


def _iter_methods_with_native(model: MhyModel, native: list[int]) -> Iterator[dict[str, Any]]:
    for mi in range(model.nmethods):
        q = native[mi]
        slot = int(model.m_slot14[mi])
        if q:
            native_rva = q - model.pe.image_base
            mapping_kind = "DIRECT_NATIVE"
        else:
            native_rva = None
            mapping_kind = "VIRTUAL_VTABLE" if slot >= 0 else "NO_BODY"
        yield {
            "method_index": mi,
            "declaring_type_index": int(model.m_declaring_type[mi]),
            "name": model.identifier(int(model.m_name_key[mi])),
            "parameter_start": int(model.m_param_start[mi]),
            "parameter_count": int(model.m_param_count[mi]),
            "return_type_reference": int(model.m_return_ref[mi]),
            "slot_0x14_decoded": slot,
            "flags_0x0E_decoded": int(model.m_flags0e[mi]),
            "flags_0x0C_decoded": f"0x{int(model.m_flags0c[mi]):08X}",
            "field_0x16_decoded": int(model.m_generic16[mi]),
            "flags_0x19_decoded": int(model.m_flags19[mi]),
            "native_rva": native_rva,
            "native_va": q or None,
            "mapping_kind": mapping_kind,
            "structure_status": "CONFIRMED",
            "semantic_status": "METHOD_IDENTITY_CONFIRMED",
        }


def normalize(model: MhyModel, code_table_path: Path, output_dir: Path) -> dict[str, Any]:
    native = _native_array(Path(code_table_path), model.nmethods)
    counts = {
        "types": model.ntypes,
        "methods": model.nmethods,
        "fields": model.nfields,
        "parameters": model.nparams,
    }
    _write_records(
        output_dir / "types.json",
        "unpack_pipeline_normalized_types/1",
        {
            "generated_at": utc_now(),
            "pipeline_schema_version": 1,
            "count": counts["types"],
            "columns": ["type_index", "namespace", "name", "full_name", "parent_base",
                        "method_start", "method_count", "field_start", "field_count",
                        "type_descriptor_start", "type_descriptor_count",
                        "type_relation_index_0xF0"],
            "evidence_fields": ["structure_status", "semantic_status"],
        },
        model.iter_types(),
    )
    _write_records(
        output_dir / "methods.json",
        "unpack_pipeline_normalized_methods/1",
        {
            "generated_at": utc_now(),
            "pipeline_schema_version": 1,
            "count": counts["methods"],
            "columns": ["method_index", "declaring_type_index", "name",
                        "parameter_start", "parameter_count", "return_type_reference",
                        "native_rva", "mapping_kind"],
            "evidence_fields": ["structure_status", "semantic_status"],
        },
        _iter_methods_with_native(model, native),
    )
    _write_records(
        output_dir / "fields.json",
        "unpack_pipeline_normalized_fields/1",
        {
            "generated_at": utc_now(),
            "pipeline_schema_version": 1,
            "count": counts["fields"],
            "columns": ["field_index", "declaring_type_index", "name", "type_reference"],
            "evidence_fields": ["structure_status", "semantic_status"],
        },
        model.iter_fields(),
    )
    _write_records(
        output_dir / "parameters.json",
        "unpack_pipeline_normalized_parameters/1",
        {
            "generated_at": utc_now(),
            "pipeline_schema_version": 1,
            "count": counts["parameters"],
            "columns": ["parameter_index", "method_index", "name_key", "type_reference"],
            "evidence_fields": ["structure_status", "semantic_status"],
        },
        model.iter_parameters(),
    )
    summary = {
        "schema": "unpack_pipeline_normalization_summary/1",
        "generated_at": utc_now(),
        "counts": counts,
        "files": {
            "types.json": str(output_dir / "types.json"),
            "methods.json": str(output_dir / "methods.json"),
            "fields.json": str(output_dir / "fields.json"),
            "parameters.json": str(output_dir / "parameters.json"),
        },
        "evidence_policy": "UNKNOWN values and structure/semantic statuses are preserved",
    }
    write_json(output_dir / "normalization_summary.json", summary)
    return summary
