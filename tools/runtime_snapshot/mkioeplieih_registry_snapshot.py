#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External read-only snapshot of the MKIOEPLIEIH polymorphic parser registry.

Static code evidence (4.4.54):
  * MKIOEPLIEIH.cctor (method 132205, RVA 0x1CB745A0) allocates a 0x27C
    (636) entry array and stores it in:
        mov rcx, [rip+disp]            ; registry_global = 0x95B1518
        mov [rcx + 0x6990], rax        ; static array slot
  * MKIOEPLIEIH.OJNNBEJLDIJ (method 132840, RVA 0x1CB743F0) is a generated
    polymorphic dispatcher:
        code  = ULEB128(reader)
        base  = [[0x95B1518] + 0x6990] ; runtime array pointer
        entry = [base + 0x20 + code*8]
        call  [entry + 8](reader)      ; concrete parser
  * Therefore entry_count == 0x27C and the on-disk .data qwords are encrypted
    placeholders; only the initialized runtime values are meaningful.

This tool reads exactly the code-proven chain:
    GameAssembly.base + 0x95B1518
    -> manager object (+0x6990 array pointer)
    -> managed array (length at +0x18, entries at +0x20 + i*8)
    -> per entry: [+0x08] parser code pointer, [+0x00..0x0F] context.

Boundary: OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ),
PSAPI EnumProcessModulesEx, ReadProcessMemory on this static-derived chain
only. No writes, no remote code, no address-space scanning.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_snapshot import (  # noqa: E402
    CANONICAL_USER_MAX,
    MIN_USER_POINTER,
    RemoteModule,
    describe_pointer,
    enumerate_modules,
    find_process_pid,
    read_qword,
    rpm,
    set_api,
    win_error,
    PeFile,
    PROCESS_QUERY_INFORMATION,
    PROCESS_VM_READ,
)

REGISTRY_GLOBAL_RVA = 0x95B1518
REGISTRY_SLOT_OFFSET = 0x6990
ENTRY_COUNT = 0x27C
ARRAY_LENGTH_OFFSET = 0x18
ARRAY_ENTRIES_OFFSET = 0x20


def hex_or_none(value: int | None) -> str | None:
    return f"0x{value:X}" if value is not None else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--game-file", required=True, type=Path)
    ap.add_argument("--game-version", default="4.4.54")
    ap.add_argument("--registry-global-rva", type=lambda v: int(v, 0),
                    default=REGISTRY_GLOBAL_RVA)
    ap.add_argument("--expected-count", type=lambda v: int(v, 0), default=ENTRY_COUNT)
    ap.add_argument("--json", type=Path, required=True)
    args = ap.parse_args()

    set_api()
    game_pe = PeFile(args.game_file)
    result = {
        "schema": "polymorphic_parser_registry_snapshot/1",
        "tool": "tools/runtime_snapshot/mkioeplieih_registry_snapshot.py",
        "game_version": args.game_version,
        "registry_global_rva": hex_or_none(args.registry_global_rva),
        "registry_slot_offset": hex_or_none(REGISTRY_SLOT_OFFSET),
        "expected_entry_count": args.expected_count,
        "static_chain": [
            "MKIOEPLIEIH.cctor 0x1CB745A0 allocates array(0x27C)",
            "MKIOEPLIEIH.cctor 0x1CB784B0 stores array -> [[0x95B1518]+0x6990]",
            "MKIOEPLIEIH.OJNNBEJLDIJ 0x1CB743F0: code=ULEB; entry=[array+0x20+code*8]; call [entry+8]",
        ],
        "final_status": None,
        "read_result": {},
        "validation": [],
    }

    pid = args.pid
    if pid == 0:
        pids = find_process_pid()
        if not pids:
            result["final_status"] = "REMOTE_READ_FAILED"
            result["error"] = "StarRail.exe not running"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print("BLOCKED: StarRail.exe not running")
            return 1
        pid = pids[0]
    result["target_pid"] = pid

    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        result["final_status"] = "REMOTE_READ_FAILED"
        result["error"] = f"OpenProcess failed win32_error={win_error()}"
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"BLOCKED: OpenProcess failed error={win_error()}")
        return 1

    try:
        found = enumerate_modules(handle)
        modules = []
        for rec in found:
            if rec["name"] == "gameassembly.dll":
                modules.append(RemoteModule("GameAssembly", rec["base"], rec["path"], game_pe))
        game = next((m for m in modules if m.name == "GameAssembly"), None)
        result["modules"] = {
            "GameAssembly": {"base": hex_or_none(game.base), "size": game.size} if game else None,
        }
        if game is None:
            result["final_status"] = "REMOTE_READ_FAILED"
            result["error"] = "GameAssembly not found via PSAPI"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print("BLOCKED: GameAssembly not found via PSAPI")
            return 1
        result["validation"].append("OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ): PASS")
        result["validation"].append("PSAPI EnumProcessModulesEx GameAssembly discovery: PASS")

        global_va = game.base + args.registry_global_rva
        manager_ptr = read_qword(handle, global_va, module=game)
        result["read_result"]["registry_global"] = {
            "va": hex_or_none(global_va), "value": hex_or_none(manager_ptr),
            "describe": describe_pointer(manager_ptr, modules) if manager_ptr else None,
        }
        if manager_ptr is None or not (MIN_USER_POINTER <= manager_ptr <= CANONICAL_USER_MAX):
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"registry manager pointer invalid: {manager_ptr}"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"FAILED: registry manager pointer invalid: {hex_or_none(manager_ptr)}")
            return 1

        array_ptr = read_qword(handle, manager_ptr + REGISTRY_SLOT_OFFSET)
        result["read_result"]["registry_array"] = {
            "address": hex_or_none(manager_ptr + REGISTRY_SLOT_OFFSET),
            "value": hex_or_none(array_ptr),
            "describe": describe_pointer(array_ptr, modules) if array_ptr else None,
        }
        if array_ptr is None or not (MIN_USER_POINTER <= array_ptr <= CANONICAL_USER_MAX):
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"registry array pointer invalid: {array_ptr}"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"FAILED: registry array pointer invalid: {hex_or_none(array_ptr)}")
            return 1

        length_raw = rpm(handle, array_ptr + ARRAY_LENGTH_OFFSET, 4)
        length = struct.unpack("<I", length_raw)[0] if length_raw else None
        result["read_result"]["array_length"] = length
        if length is None or length < args.expected_count:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"registry array length invalid: {length}"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"FAILED: registry array length invalid: {length}")
            return 1

        count = min(length, args.expected_count)
        entries_blob = rpm(handle, array_ptr + ARRAY_ENTRIES_OFFSET, count * 8)
        if entries_blob is None or len(entries_blob) != count * 8:
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = "registry entries read failed"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print("FAILED: registry entries read failed")
            return 1

        entries = list(struct.unpack(f"<{count}Q", entries_blob))
        rows = []
        for idx, entry in enumerate(entries):
            row = {
                "discriminator": idx,
                "entry_pointer": hex_or_none(entry),
                "entry_describe": describe_pointer(entry, modules) if entry else None,
                "parser_pointer": None,
                "parser_describe": None,
                "parser_bytes": None,
            }
            if entry and (MIN_USER_POINTER <= entry <= CANONICAL_USER_MAX):
                parser = read_qword(handle, entry + 8)
                row["parser_pointer"] = hex_or_none(parser)
                row["parser_describe"] = describe_pointer(parser, modules) if parser else None
                if row["parser_describe"] and row["parser_describe"]["in_known_module"] \
                        and row["parser_describe"]["is_executable"]:
                    b = rpm(handle, parser, 32, module=game)
                    if b:
                        row["parser_bytes"] = b.hex(" ")
            rows.append(row)

        null_entries = sum(1 for r in rows if r["entry_pointer"] in (None, "0x0"))
        executable_parsers = sum(1 for r in rows if r["parser_describe"]
                                 and r["parser_describe"]["in_known_module"]
                                 and r["parser_describe"]["is_executable"])
        result["read_result"]["entries"] = rows
        result["read_result"]["statistics"] = {
            "entry_count": len(rows),
            "null_entries": null_entries,
            "executable_parser_entries": executable_parsers,
            "non_executable_or_null_parsers": len(rows) - executable_parsers,
        }
        result["validation"].append(f"registry array [{array_ptr:X}+0x20] read: {len(rows)} entries")
        result["final_status"] = "REGISTRY_READABLE"
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"final_status: {result['final_status']}")
        print(f"manager_ptr  -> {hex_or_none(manager_ptr)}")
        print(f"array_ptr    -> {hex_or_none(array_ptr)} length={length}")
        print(f"null_entries -> {null_entries}")
        print(f"exec_parsers -> {executable_parsers}")
        return 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
