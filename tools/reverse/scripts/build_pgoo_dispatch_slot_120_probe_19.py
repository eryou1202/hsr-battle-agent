#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the PGOOHIHKHNJ dispatch slot +0x120 probe artifact."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "raw" / "4.4.54" / "pgoo_dispatch_slot_120_probe_19.json"

DATA = {
    "schema": "pgoo_dispatch_slot_120_probe/1",
    "game_version": "4.4.54",
    "status": "PREPROCESS_TOPOLOGY",
    "type_identity": {
        "runtime_type": "PGOOHIHKHNJ",
        "type_index": 55138,
        "method_count": 31,
        "field_count": 6,
    },
    "class_root": {
        "typeinfo_global": "UNKNOWN; type-token globals such as 0x9788B90 are runtime/encrypted class-descriptor pointers, not statically readable TypeInfo roots",
        "instance_header_relation": "[PGOOHIHKHNJ instance + 0x0] is the runtime class/header pointer used by M507304",
        "classification": "RUNTIME_TYPE_HEADER",
        "note": "Compatible with an IL2CPP class pointer, but this binary's class descriptor is runtime-initialized/encrypted in the static image.",
    },
    "slot_0x120": {
        "layout_role": "UNKNOWN",
        "initialization_class": "METADATA_DRIVEN_RUNTIME_INIT / EXTERNAL_RUNTIME_INIT",
        "writer_or_initializer": "NONE_FOUND_IN_PGOOHIHKHNJ_METHODS",
        "source_value": "UNKNOWN",
        "source_table_or_metadata": "UNKNOWN",
        "concrete_pointer_if_known": None,
        "evidence": "The only +0x120 accesses in PGOOHIHKHNJ methods are reads at M507304 0xC30F033/0xC30F07D and stack-local writes in M507308/M507312/M507313/M507315; no class-header write is present in the type's own methods.",
    },
    "method_resolution": {
        "native_rva": None,
        "method_index": None,
        "declaring_type": None,
        "abi_status": "NOT_APPLICABLE",
    },
    "static_resolution_status": "INSUFFICIENT",
    "runtime_observation_contract": {
        "required": True,
        "steps": [
            "Obtain a live PGOOHIHKHNJ instance (for example the r15 value at M507304 0xC30F0BC).",
            "Read qword at [instance + 0x0] to get the runtime class/header pointer C.",
            "Read qword at [C + 0x120] to get the function pointer F.",
            "F is a VA in GameAssembly; normalize to RVA with F - 0x180000000.",
            "Class initialization must have occurred before the read; M507304 itself gates on byte [C+0xCA] & 4 before the call.",
            "Pointer width is 8 bytes.",
        ],
        "purpose": "Reduce later runtime observation to exactly one known pointer read: [ [PGOOHIHKHNJ instance] + 0x0 + 0x120 ].",
    },
    "remaining_unknown": [
        "Concrete runtime class/header pointer C for PGOOHIHKHNJ.",
        "Layout role of class slot +0x120 (virtual invoke data, interface dispatch, generated function-pointer field, or other).",
        "The initialization writer/helper that populates [C+0x120].",
        "The concrete function pointer and method_index/RVA at that slot.",
        "Whether B returned by that pointer is the request object consumed by M507308.",
    ],
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
