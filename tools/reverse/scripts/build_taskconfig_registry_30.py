#!/usr/bin/env python3
"""Build the 4.4.54 TaskConfig discriminator registry statically.

The generated BEMKAFNMJIK dispatcher reads a ULEB discriminator and dispatches
through a 3915-entry array.  Its cctor stores one descriptor per non-null slot;
the generated helper methods are emitted in the same non-null slot order.  This
tool joins that order to the recovered MethodDefinition/code registries and
reports the concrete TaskConfig parser reached by each discriminator.
"""
from __future__ import annotations

import argparse
import json
import mmap
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "vendor" / "capstone"))

from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # noqa: E402
from capstone import x86  # noqa: E402
from analyze_mhy_definition_candidate import (  # noqa: E402
    FILE_HEADER,
    locate_template_rva,
    resolve_identifier,
    signed32,
)
from analyze_mhy_method_candidate import RULES  # noqa: E402
from build_method_code_registry import (  # noqa: E402
    M32,
    decode_declaring_type,
    decode_method_name,
    resolve_type_name,
)
from resolve_il2cpp_get_api_table import PeImage  # noqa: E402


REGISTRY_TYPE = "BEMKAFNMJIK"
REGISTRY_TYPE_INDEX = 23435
CCTOR_METHOD_INDEX = 128295
FIRST_HELPER_METHOD_INDEX = 128296
DISPATCHER_METHOD_INDEX = 132199
CCTOR_RVA = 0x1D028DE0
CCTOR_END_RVA = 0x1D041A24
DISPATCHER_RVA = 0x1D028C30
REGISTRY_GLOBAL_RVA = 0x95B1518
REGISTRY_SLOT_OFFSET = 0x41850
ENTRY_COUNT = 0xF4B


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    out = {}
    for field, (op, const) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        value = (raw + const) & M32 if op == "add" else raw ^ const
        out[field] = FILE_HEADER + signed32(value)
    return out


def extract_cctor_slots(pe: PeImage) -> list[dict]:
    raw = pe.read_rva(CCTOR_RVA, CCTOR_END_RVA - CCTOR_RVA)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    pending: dict[int, int] = {}
    slots: dict[int, dict] = {}
    for ins in md.disasm(raw, pe.image_base + CCTOR_RVA):
        if ins.address >= pe.image_base + CCTOR_END_RVA:
            break
        if ins.mnemonic != "mov" or len(ins.operands) != 2:
            continue
        dst, src = ins.operands
        if (
            dst.type == x86.X86_OP_REG
            and src.type == x86.X86_OP_MEM
            and src.mem.base == x86.X86_REG_RIP
        ):
            pending[dst.reg] = ins.address + ins.size + src.mem.disp - pe.image_base
            continue
        if (
            dst.type != x86.X86_OP_MEM
            or dst.mem.base != x86.X86_REG_RAX
            or dst.mem.disp < 0x20
            or (dst.mem.disp - 0x20) % 8
        ):
            continue
        discriminator = (dst.mem.disp - 0x20) // 8
        if discriminator >= ENTRY_COUNT:
            continue
        row = {
            "discriminator": discriminator,
            "array_slot_offset": f"0x{dst.mem.disp:X}",
            "cctor_store_rva": f"0x{ins.address - pe.image_base:X}",
            "descriptor_global_rva": None,
            "slot_kind": None,
        }
        if src.type == x86.X86_OP_IMM and int(src.imm) == 0:
            row["slot_kind"] = "NULL"
        elif src.type == x86.X86_OP_REG and src.reg in pending:
            row["slot_kind"] = "DESCRIPTOR"
            row["descriptor_global_rva"] = f"0x{pending[src.reg]:X}"
        else:
            row["slot_kind"] = "UNRESOLVED_STORE"
        slots[discriminator] = row
    return [slots[index] for index in sorted(slots)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--code-table-rva", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--template-rva", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--version", default="4.4.54")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pe = PeImage(args.game)
    template_rva = args.template_rva or locate_template_rva(pe)
    offsets = table_offsets(pe, template_rva)
    type_base = offsets[0x84]
    method_base = offsets[0x14C]
    method_next = offsets[0x160]
    method_count = (method_next - method_base) // 26
    region_base = offsets[0x1B4]

    raw_table = pe.read_rva(args.code_table_rva, method_count * 8)
    by_rva: dict[int, int] = {}
    for method_index in range(method_count):
        pointer = struct.unpack_from("<Q", raw_table, method_index * 8)[0]
        if pointer:
            by_rva.setdefault(pointer - pe.image_base, method_index)

    slots = extract_cctor_slots(pe)
    if len(slots) != ENTRY_COUNT:
        raise RuntimeError(f"cctor slot coverage {len(slots)} != {ENTRY_COUNT}")
    descriptors = [row for row in slots if row["slot_kind"] == "DESCRIPTOR"]
    nulls = [row for row in slots if row["slot_kind"] == "NULL"]
    unresolved = [row for row in slots if row["slot_kind"] == "UNRESOLVED_STORE"]
    helper_indices = list(range(FIRST_HELPER_METHOD_INDEX, DISPATCHER_METHOD_INDEX))
    if unresolved:
        raise RuntimeError(f"unresolved cctor stores: {len(unresolved)}")
    if len(descriptors) != len(helper_indices):
        raise RuntimeError(
            f"descriptor/helper mismatch: {len(descriptors)} != {len(helper_indices)}; "
            f"null_slots={len(nulls)}"
        )

    size = args.metadata.stat().st_size
    mappings = []
    with args.metadata.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as metadata:
        region = metadata[region_base : region_base + min(size - region_base, 1 << 26)]
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True

        def method_row(method_index: int, native_rva: int) -> dict:
            declaring_type_index = decode_declaring_type(metadata, method_base, method_index)
            return {
                "method_index": method_index,
                "method_name": decode_method_name(metadata, method_base, method_index, region),
                "native_rva": f"0x{native_rva:X}",
                "declaring_type_index": declaring_type_index,
                "declaring_type": resolve_type_name(metadata, type_base, declaring_type_index, region),
            }

        helper_cursor = 0
        for slot in slots:
            mapping = dict(slot)
            mapping.update(
                {
                    "helper_method_index": None,
                    "helper_native_rva": None,
                    "concrete_parser_method_index": None,
                    "concrete_parser_method_name": None,
                    "concrete_parser_native_rva": None,
                    "concrete_runtime_type_index": None,
                    "concrete_runtime_type_name": None,
                    "internal_method_calls": [],
                    "mapping_status": "NULL_SLOT" if slot["slot_kind"] == "NULL" else None,
                }
            )
            if slot["slot_kind"] == "NULL":
                mappings.append(mapping)
                continue

            helper_index = helper_indices[helper_cursor]
            helper_cursor += 1
            pointer = struct.unpack_from("<Q", raw_table, helper_index * 8)[0]
            helper_rva = pointer - pe.image_base if pointer else None
            mapping["helper_method_index"] = helper_index
            mapping["helper_native_rva"] = f"0x{helper_rva:X}" if helper_rva is not None else None
            if helper_rva is None:
                mapping["mapping_status"] = "HELPER_HAS_NO_NATIVE_BODY"
                mappings.append(mapping)
                continue

            calls = []
            code = pe.read_rva(helper_rva, 0x120)
            for ins in md.disasm(code, pe.image_base + helper_rva):
                if ins.address - pe.image_base > helper_rva + 0x100:
                    break
                if ins.mnemonic in ("call", "jmp") and ins.operands:
                    operand = ins.operands[0]
                    if operand.type == x86.X86_OP_IMM:
                        target_rva = int(operand.imm) - pe.image_base
                        target_index = by_rva.get(target_rva)
                        if target_index is not None and target_index != helper_index:
                            calls.append(method_row(target_index, target_rva))
                if ins.mnemonic == "ret":
                    break
            mapping["internal_method_calls"] = calls
            concrete = next(
                (call for call in reversed(calls) if call["declaring_type"] != REGISTRY_TYPE),
                None,
            )
            if concrete is None:
                mapping["mapping_status"] = "ALLOCATION_ONLY_OR_UNRESOLVED"
            else:
                mapping.update(
                    {
                        "concrete_parser_method_index": concrete["method_index"],
                        "concrete_parser_method_name": concrete["method_name"],
                        "concrete_parser_native_rva": concrete["native_rva"],
                        "concrete_runtime_type_index": concrete["declaring_type_index"],
                        "concrete_runtime_type_name": concrete["declaring_type"],
                        "mapping_status": "CONCRETE_PARSER_RECOVERED",
                    }
                )
            mappings.append(mapping)

    direct_hp_names = {
        "RPG.GameCore.HealHP",
        "RPG.GameCore.SetHP",
        "RPG.GameCore.LoseHP",
        "RPG.GameCore.LoseHPByRatio",
    }
    direct_hp = [
        {
            "discriminator": row["discriminator"],
            "runtime_type_name": row["concrete_runtime_type_name"],
            "parser_method_index": row["concrete_parser_method_index"],
            "parser_native_rva": row["concrete_parser_native_rva"],
        }
        for row in mappings
        if row["concrete_runtime_type_name"] in direct_hp_names
    ]
    result = {
        "schema": "taskconfig_registry/1",
        "game_version": args.version,
        "status": "TASKCONFIG_DISCRIMINATOR_REGISTRY_CONFIRMED",
        "registry": {
            "runtime_type": REGISTRY_TYPE,
            "runtime_type_index": REGISTRY_TYPE_INDEX,
            "cctor_method_index": CCTOR_METHOD_INDEX,
            "cctor_rva": f"0x{CCTOR_RVA:X}",
            "dispatcher_method_index": DISPATCHER_METHOD_INDEX,
            "dispatcher_rva": f"0x{DISPATCHER_RVA:X}",
            "registry_global_rva": f"0x{REGISTRY_GLOBAL_RVA:X}",
            "registry_slot_offset": f"0x{REGISTRY_SLOT_OFFSET:X}",
            "entry_count": ENTRY_COUNT,
            "discriminator_reader": "ULEB128",
            "dispatch": "entry=[[[global]+slot]+0x20+discriminator*8]; call [entry+8]",
        },
        "statistics": {
            "slot_count": len(mappings),
            "descriptor_slots": len(descriptors),
            "null_slots": len(nulls),
            "concrete_parser_recovered": sum(
                row["mapping_status"] == "CONCRETE_PARSER_RECOVERED" for row in mappings
            ),
            "allocation_only_or_unresolved": sum(
                row["mapping_status"] == "ALLOCATION_ONLY_OR_UNRESOLVED" for row in mappings
            ),
        },
        "direct_hp_mappings": sorted(direct_hp, key=lambda row: row["discriminator"]),
        "mappings": mappings,
        "claims_not_made": [
            "field-level payload boundaries for every TaskConfig subtype",
            "task execution semantics",
            "damage or healing arithmetic",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} slots={len(mappings)} nulls={len(nulls)} "
        f"concrete={result['statistics']['concrete_parser_recovered']}"
    )
    for row in result["direct_hp_mappings"]:
        print(
            f"  discriminator={row['discriminator']} "
            f"{row['runtime_type_name']} {row['parser_native_rva']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
