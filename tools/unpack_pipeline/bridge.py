# -*- coding: utf-8 -*-
"""STAGE 8 - DESIGN_RUNTIME_BRIDGE (static + runtime-optional).

Static:
  * `ability_config`    : RPG.GameCore.AbilityConfig.FromBinary switch factory
  * `modifier_config`   : RPG.GameCore.ModifierConfig.OJNNBEJLDIJ switch factory

Runtime-optional:
  * generated polymorphic registry (MKIOEPLIEIH).  Without a read-only runtime
    snapshot the pipeline reports NOT_RUN; a snapshot JSON produced by
    `tools/runtime_snapshot/mkioeplieih_registry_snapshot.py` can be passed in
    and is mapped back through the method code registry.

Historical correction is recorded, not re-litigated:
  * SkillAbilityConfig.AbilityList == List<string>, not a polymorphic mixin list.
  * Black Swan 2/8/14/16 = STRUCTURAL_VALUE_CONFIRMED,
    SERIALIZER_SEMANTIC_UNRESOLVED.  Registry-range membership is not
    serializer identity.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any

from .common import read_json, utc_now, write_json
from .mhy_core import MhyModel

JUMP_PATTERNS = [
    bytes.fromhex("486304814801c8ffe0"),
    bytes.fromhex("496304814801c8ffe0"),
    bytes.fromhex("486304824801d0ffe0"),
    bytes.fromhex("486304834801d8ffe0"),
    bytes.fromhex("496304804c01c0ffe0"),
    bytes.fromhex("496304814c01c8ffe0"),
    bytes.fromhex("4a6304804c01c0ffe0"),
    bytes.fromhex("4a6304814c01c8ffe0"),
]

STATIC_DOMAINS = [
    {
        "domain": "ability_config",
        "factory_type": "RPG.GameCore.AbilityConfig",
        "factory_method": "FromBinary",
        "discriminator_kind": "serialized type tag (ULEB128)",
        "mechanism": "STATIC_SWITCH_FACTORY",
    },
    {
        "domain": "modifier_config",
        "factory_type": "RPG.GameCore.ModifierConfig",
        "factory_method": "OJNNBEJLDIJ",
        "discriminator_kind": "serialized type tag (ULEB128)",
        "mechanism": "STATIC_SWITCH_FACTORY",
    },
]


# ---------------------------------------------------------------------------
# Byte-level helpers mirroring tools/reverse/scripts/scan_dispatch_tables.py
# (the importing module requires Capstone, so the two proven regex helpers are
# copied here as a thin adapter; no algorithm was changed).
# ---------------------------------------------------------------------------

def _find_lea_before(data: bytes, hit_end: int, window: int = 64) -> tuple[int, int] | None:
    start = max(0, hit_end - window)
    best = None
    for m in re.finditer(
            rb"\x48\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp>.{4})"
            rb"|\x4c\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](?P<disp2>.{4})",
            data[start:hit_end], re.DOTALL):
        disp = m.group("disp") or m.group("disp2")
        off = start + m.start()
        if off + 7 <= hit_end:
            best = (off, off + 7 + struct.unpack("<i", disp)[0])
    return best


def _find_case_bound(data: bytes, hit_start: int, window: int = 80) -> int | None:
    start = max(0, hit_start - window)
    segment = data[start:hit_start]
    branch = -1
    for m in re.finditer(rb"\x0f[\x87\x86\x82\x83]", segment):
        branch = start + m.start()
    if branch < 0:
        return None
    cmp_start = max(start, branch - 16)
    candidate = None
    pos = cmp_start
    while pos < branch:
        b = data[pos]
        if b == 0x83 and pos + 2 < branch and data[pos + 1] in range(0xF8, 0x100):
            candidate = data[pos + 2]
            pos += 3
            continue
        if b == 0x3D and pos + 5 <= branch:
            candidate = struct.unpack("<I", data[pos + 1: pos + 5])[0]
            pos += 5
            continue
        if b == 0x81 and pos + 6 <= branch and data[pos + 1] in range(0xF8, 0x100):
            candidate = struct.unpack("<I", data[pos + 2: pos + 6])[0]
            pos += 6
            continue
        pos += 1
    if candidate is not None and 3 <= candidate <= 4096:
        return candidate
    return None


def _signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _load_code_map(model: MhyModel, table_path: Path) -> tuple[dict[int, int], list[int]]:
    raw = Path(table_path).read_bytes()
    by_rva: dict[int, int] = {}
    rvas: list[int] = []
    for mi in range(model.nmethods):
        q = struct.unpack_from("<Q", raw, mi * 8)[0]
        if q:
            rva = q - model.pe.image_base
            if rva not in by_rva:
                by_rva[rva] = mi
                rvas.append(rva)
    rvas.sort()
    return by_rva, rvas


def _tail_jump_target(model: MhyModel, by_rva: dict[int, int], case_rva: int,
                      max_len: int = 0x180) -> int | None:
    raw = model.pe.read_rva(case_rva, max_len)
    if not raw:
        return None
    # Direct near jumps only; targets must land on a known method entry.
    for i in range(0, len(raw) - 5):
        if raw[i] == 0xE9:
            rel = _signed32(struct.unpack_from("<I", raw, i + 1)[0])
            target = case_rva + i + 5 + rel
            if target in by_rva:
                return target
        if raw[i] == 0xEB:
            rel = struct.unpack_from("b", raw, i + 1)[0]
            target = case_rva + i + 2 + rel
            if target in by_rva:
                return target
    return None


def _extract_static_domain(model: MhyModel, table_path: Path, domain: dict[str, Any],
                           game_version: str) -> dict[str, Any]:
    by_rva, _ = _load_code_map(model, Path(table_path))
    factory_mi = model.find_method(domain["factory_type"], domain["factory_method"])
    if factory_mi is None:
        raise RuntimeError(
            f"factory method not found: {domain['factory_type']}.{domain['factory_method']}")
    raw_table = Path(table_path).read_bytes()
    factory_q = struct.unpack_from("<Q", raw_table, factory_mi * 8)[0]
    factory_rva = factory_q - model.pe.image_base
    if factory_q == 0:
        raise RuntimeError(f"factory has no direct native code: {domain['domain']}")
    code = model.pe.read_rva(factory_rva, 0x800) or b""
    switch = None
    for pattern in JUMP_PATTERNS:
        p = code.find(pattern)
        if p < 0:
            continue
        lea = _find_lea_before(code, p)
        bound = _find_case_bound(code, p)
        if lea is None or bound is None:
            continue
        _, table_off = lea
        table_va = model.pe.image_base + factory_rva + table_off
        table_raw = model.pe.read_rva(table_va - model.pe.image_base, (bound + 1) * 4)
        if table_raw is None:
            continue
        entries = struct.unpack(f"<{bound + 1}i", table_raw)
        switch = {
            "pattern_offset": p,
            "jump_table_rva": table_va - model.pe.image_base,
            "case_bound": bound,
            "entries": entries,
        }
        break
    if switch is None:
        raise RuntimeError(f"static switch dispatcher not found in {domain['domain']} factory")

    mappings = []
    for case, entry in enumerate(switch["entries"]):
        case_rva = (switch["jump_table_rva"] + model.pe.image_base + entry
                    - model.pe.image_base) & 0xFFFFFFFF
        tail = _tail_jump_target(model, by_rva, case_rva)
        tail_mi = by_rva.get(tail) if tail is not None else None
        runtime_type = model.type_name(int(model.m_declaring_type[tail_mi])) if tail_mi is not None else None
        parser_name = model.identifier(int(model.m_name_key[tail_mi])) if tail_mi is not None else None
        mappings.append({
            "serialized_discriminator": case,
            "case_block_rva": f"0x{case_rva:X}",
            "parser_method_index": tail_mi,
            "parser_method_name": parser_name,
            "parser_native_rva": f"0x{tail:X}" if tail is not None else None,
            "runtime_type": runtime_type,
            "mapping_kind": "SWITCH_CASE_TO_METHOD" if tail_mi is not None else "UNRESOLVED_TAIL",
            "mapping_source": "static factory switch (E4 machine-code shape) + E3 MHY registries",
            "evidence_status": "CONFIRMED" if tail_mi is not None else "UNRESOLVED",
        })
    factory_type_name = model.type_name(int(model.m_declaring_type[factory_mi]))
    return {
        "domain": domain["domain"],
        "status": "PASS",
        "factory": {
            "runtime_type": factory_type_name,
            "method_name": domain["factory_method"],
            "method_index": factory_mi,
            "native_rva": f"0x{factory_rva:X}",
        },
        "mechanism": {
            "kind": domain["mechanism"],
            "type_tag_reader": "ULEB128 (MOMNMLHNPLH.BIKABOFADBP)",
            "dispatch_shape": "cmp eax, N; ja default; movsxd [table + idx*4]; add table; jmp",
            "jump_table_rva": f"0x{switch['jump_table_rva']:X}",
            "case_bound": switch["case_bound"],
        },
        "mappings": mappings,
        "statistics": {
            "mapping_count": len(mappings),
            "resolved": sum(1 for m in mappings if m["parser_method_index"] is not None),
            "unresolved": sum(1 for m in mappings if m["parser_method_index"] is None),
        },
        "game_version": game_version,
    }


def _generated_registry_from_snapshot(model: MhyModel, table_path: Path,
                                      snapshot_path: Path,
                                      game_version: str) -> dict[str, Any]:
    snap = read_json(snapshot_path)
    entries = snap.get("read_result", {}).get("entries", [])
    if not entries:
        raise RuntimeError("runtime snapshot contains no registry entries")
    runtime_base = int(snap["modules"]["GameAssembly"]["base"], 16)
    by_rva, _ = _load_code_map(model, Path(table_path))
    mappings = []
    for entry in entries:
        disc = int(entry.get("discriminator"))
        parser = entry.get("parser_pointer")
        desc = entry.get("parser_describe") or {}
        if not parser or not (desc.get("in_known_module") and desc.get("is_executable")):
            mappings.append({
                "serialized_discriminator": disc,
                "runtime_type": None,
                "parser_method_index": None,
                "parser_native_rva": None,
                "mapping_source": "runtime registry slot",
                "evidence_status": "NULL_OR_NON_EXECUTABLE_SLOT",
            })
            continue
        rva = int(parser, 16) - runtime_base
        mi = by_rva.get(rva)
        runtime_type = model.type_name(int(model.m_declaring_type[mi])) if mi is not None else None
        parser_name = model.identifier(int(model.m_name_key[mi])) if mi is not None else None
        mappings.append({
            "serialized_discriminator": disc,
            "runtime_type": runtime_type,
            "parser_method_index": mi,
            "parser_method_name": parser_name,
            "parser_native_rva": f"0x{rva:X}",
            "mapping_source": ("code-guided ReadProcessMemory -> exact method code table entry"
                               if mi is not None else "code-guided ReadProcessMemory"),
            "evidence_status": "CONFIRMED" if mi is not None else "UNRESOLVED",
        })
    stats = snap.get("read_result", {}).get("statistics", {})
    return {
        "domain": "generated_polymorphic_registry",
        "status": "PASS",
        "runtime": True,
        "registry": {
            "builder_type": "MKIOEPLIEIH",
            "builder_method": ".cctor",
            "dispatcher_type": "MKIOEPLIEIH",
            "dispatcher_method": "OJNNBEJLDIJ",
            "registry_global_rva": snap.get("registry_global_rva"),
            "registry_slot_offset": snap.get("registry_slot_offset"),
            "entry_count": snap.get("expected_entry_count"),
        },
        "statistics": stats,
        "mappings": mappings,
        "snapshot": str(snapshot_path),
        "game_version": game_version,
    }


def build_bridge_registry(model: MhyModel, table_path: Path, output_dir: Path,
                          game_version: str,
                          design_structural: dict[str, Any] | None = None,
                          runtime_snapshot: Path | None = None) -> dict[str, Any]:
    domains = []
    for domain in STATIC_DOMAINS:
        domains.append(_extract_static_domain(model, Path(table_path), domain, game_version))

    generated: dict[str, Any]
    if runtime_snapshot is not None:
        generated = _generated_registry_from_snapshot(
            model, table_path, runtime_snapshot, game_version)
    else:
        generated = {
            "domain": "generated_polymorphic_registry",
            "status": "RUNTIME_OPTIONAL_NOT_RUN",
            "runtime": True,
            "note": ("requires an already-initialized local client and a snapshot from "
                     "tools/runtime_snapshot/mkioeplieih_registry_snapshot.py using only "
                     "PROCESS_QUERY_INFORMATION|PROCESS_VM_READ + PSAPI + ReadProcessMemory"),
            "mappings": [],
        }

    black_swan = []
    if design_structural:
        for prefix in design_structural.get("record_prefixes", []):
            black_swan.append({
                "record_name": prefix.get("record_name"),
                "structural_code": prefix.get("structural_code"),
                "structure_status": "STRUCTURAL_VALUE_CONFIRMED",
                "semantic_status": "SERIALIZER_SEMANTIC_UNRESOLVED",
                "raw_value_prefix_hex": prefix.get("raw_value_prefix_hex"),
                "note": "range membership != serializer identity",
            })

    result: dict[str, Any] = {
        "schema": "unpack_pipeline_design_runtime_registry/1",
        "generated_at": utc_now(),
        "game_version": game_version,
        "domains": domains + [generated],
        "correction": {
            "SkillAbilityConfig.AbilityList": {
                "resolved_type": "List<string>",
                "historical_label": "polymorphic Ability Mixin list",
                "status": "DISPROVEN",
                "evidence": "SkillAbilityConfig parser reads bit 0 Skill:string and bit 1 list reader "
                           "0x16C86A10 with string element descriptor -> UTF-8 string materializer",
            },
            "historical_ability_mixin_registry_name": (
                "interpreted as generated/polymorphic DesignData runtime registry; "
                "not a Black Swan ability-mixin subtype semantic proof"),
        },
        "black_swan_observations": black_swan,
        "unknown_field_discipline": {
            "outer_tag": "field_0_uleb; semantic_status UNKNOWN",
            "bitfield": "field_1_uleb; semantic_status UNKNOWN",
            "structural_value_2_8_14_16": "structural_code; STRUCTURAL_VALUE_CONFIRMED / "
                                          "SERIALIZER_SEMANTIC_UNRESOLVED",
        },
        "evidence_level": "E3 MHY registry + E4 static factory machine code; runtime snapshot E5",
    }
    write_json(output_dir / "design_runtime_registry.json", result)
    return result
