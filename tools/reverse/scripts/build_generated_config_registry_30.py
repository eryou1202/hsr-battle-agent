#!/usr/bin/env python3
"""Build a generated polymorphic-config discriminator registry statically."""
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


def table_offsets(pe: PeImage, template_rva: int) -> dict[int, int]:
    block = pe.read_rva(template_rva, 0x208)
    result = {}
    for field, (operation, constant) in RULES.items():
        raw = struct.unpack_from("<I", block, field)[0]
        value = (raw + constant) & M32 if operation == "add" else raw ^ constant
        result[field] = FILE_HEADER + signed32(value)
    return result


def extract_slots(
    pe: PeImage, cctor_rva: int, cctor_end_rva: int, entry_count: int
) -> list[dict]:
    raw = pe.read_rva(cctor_rva, cctor_end_rva - cctor_rva)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    pending: dict[int, int] = {}
    slots: dict[int, dict] = {}
    for ins in md.disasm(raw, pe.image_base + cctor_rva):
        if ins.address >= pe.image_base + cctor_end_rva:
            break
        if ins.mnemonic != "mov" or len(ins.operands) != 2:
            continue
        destination, source = ins.operands
        if (
            destination.type == x86.X86_OP_REG
            and source.type == x86.X86_OP_MEM
            and source.mem.base == x86.X86_REG_RIP
        ):
            pending[destination.reg] = ins.address + ins.size + source.mem.disp - pe.image_base
            continue
        if (
            destination.type != x86.X86_OP_MEM
            or destination.mem.base != x86.X86_REG_RAX
            or destination.mem.disp < 0x20
            or (destination.mem.disp - 0x20) % 8
        ):
            continue
        discriminator = (destination.mem.disp - 0x20) // 8
        if discriminator >= entry_count:
            continue
        row = {
            "discriminator": discriminator,
            "array_slot_offset": f"0x{destination.mem.disp:X}",
            "cctor_store_rva": f"0x{ins.address - pe.image_base:X}",
            "descriptor_global_rva": None,
            "slot_kind": None,
        }
        if source.type == x86.X86_OP_IMM and int(source.imm) == 0:
            row["slot_kind"] = "NULL"
        elif source.type == x86.X86_OP_REG and source.reg in pending:
            row["slot_kind"] = "DESCRIPTOR"
            row["descriptor_global_rva"] = f"0x{pending[source.reg]:X}"
        else:
            row["slot_kind"] = "UNRESOLVED_STORE"
        slots[discriminator] = row
    return [slots[index] for index in sorted(slots)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--code-table-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--template-rva", type=lambda value: int(value, 0), default=None)
    parser.add_argument("--version", default="4.4.54")
    parser.add_argument("--registry-label", required=True)
    parser.add_argument("--registry-type-index", required=True, type=int)
    parser.add_argument("--cctor-method-index", required=True, type=int)
    parser.add_argument("--first-helper-method-index", required=True, type=int)
    parser.add_argument("--dispatcher-method-index", required=True, type=int)
    parser.add_argument("--cctor-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--cctor-end-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--dispatcher-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--registry-global-rva", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--registry-slot-offset", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--entry-count", required=True, type=int)
    parser.add_argument("--spot-type", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pe = PeImage(args.game)
    template_rva = args.template_rva or locate_template_rva(pe)
    offsets = table_offsets(pe, template_rva)
    type_base = offsets[0x84]
    method_base = offsets[0x14C]
    method_count = (offsets[0x160] - method_base) // 26
    region_base = offsets[0x1B4]
    raw_table = pe.read_rva(args.code_table_rva, method_count * 8)
    by_rva: dict[int, int] = {}
    for method_index in range(method_count):
        pointer = struct.unpack_from("<Q", raw_table, method_index * 8)[0]
        if pointer:
            by_rva.setdefault(pointer - pe.image_base, method_index)

    slots = extract_slots(pe, args.cctor_rva, args.cctor_end_rva, args.entry_count)
    if len(slots) != args.entry_count:
        raise RuntimeError(f"cctor slot coverage {len(slots)} != {args.entry_count}")
    descriptors = [row for row in slots if row["slot_kind"] == "DESCRIPTOR"]
    nulls = [row for row in slots if row["slot_kind"] == "NULL"]
    unresolved = [row for row in slots if row["slot_kind"] == "UNRESOLVED_STORE"]
    helpers = list(range(args.first_helper_method_index, args.dispatcher_method_index))
    if unresolved:
        raise RuntimeError(f"unresolved cctor stores: {len(unresolved)}")
    if len(descriptors) != len(helpers):
        raise RuntimeError(
            f"descriptor/helper mismatch: {len(descriptors)} != {len(helpers)}; "
            f"null_slots={len(nulls)}"
        )

    mappings = []
    size = args.metadata.stat().st_size
    with args.metadata.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as metadata:
        region = metadata[region_base : region_base + min(size - region_base, 1 << 26)]
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True

        def method_row(method_index: int, native_rva: int) -> dict:
            type_index = decode_declaring_type(metadata, method_base, method_index)
            return {
                "method_index": method_index,
                "method_name": decode_method_name(metadata, method_base, method_index, region),
                "native_rva": f"0x{native_rva:X}",
                "declaring_type_index": type_index,
                "declaring_type": resolve_type_name(metadata, type_base, type_index, region),
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
            helper_index = helpers[helper_cursor]
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
                (call for call in reversed(calls) if call["declaring_type_index"] != args.registry_type_index),
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

    spot_types = set(args.spot_type)
    result = {
        "schema": "generated_config_registry/1",
        "game_version": args.version,
        "status": "GENERATED_CONFIG_DISCRIMINATOR_REGISTRY_CONFIRMED",
        "registry": {
            "label": args.registry_label,
            "runtime_type_index": args.registry_type_index,
            "cctor_method_index": args.cctor_method_index,
            "cctor_rva": f"0x{args.cctor_rva:X}",
            "cctor_end_rva_exclusive": f"0x{args.cctor_end_rva:X}",
            "dispatcher_method_index": args.dispatcher_method_index,
            "dispatcher_rva": f"0x{args.dispatcher_rva:X}",
            "registry_global_rva": f"0x{args.registry_global_rva:X}",
            "registry_slot_offset": f"0x{args.registry_slot_offset:X}",
            "entry_count": args.entry_count,
            "discriminator_reader": "ULEB128",
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
        "spot_mappings": [
            row for row in mappings if row["concrete_runtime_type_name"] in spot_types
        ],
        "mappings": mappings,
        "claims_not_made": [
            "field-level payload boundaries for every concrete subtype",
            "runtime execution semantics",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} slots={len(mappings)} nulls={len(nulls)} "
        f"concrete={result['statistics']['concrete_parser_recovered']}"
    )
    for row in result["spot_mappings"]:
        print(
            f"  discriminator={row['discriminator']} "
            f"{row['concrete_runtime_type_name']} {row['concrete_parser_native_rva']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
