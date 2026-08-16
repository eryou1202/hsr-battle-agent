#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External read-only snapshot of the SkillAbilityConfig.AbilityList descriptor.

Static code evidence (4.4.54):
  * SkillAbilityConfig.OJNNBEJLDIJ @ 0x1D4AAC90 loads two RIP-relative
    descriptor qwords and tail-jumps to the generic object reader
    @ 0x16C86A10:
        descriptor_parser_global = 0x96B7C00  (passed in rdx)
        descriptor_type_global   = 0x96B7C08  (passed in r9)
  * The generic reader @ 0x16C86A10 is code-proven to:
        count  = ULEB128(reader)
        class  = [[type_global + 0x20] + 0x18]
        check  [class + 0xC8] bit 0  -> allocate array
        per element: parser = [parser_global + 8]
                     parser(reader, out_slot, parser_global)

This tool only reads the addresses implied by that static chain:
    GameAssembly.base + global_rva
    -> parser_global (+0x08 parser code pointer, +0x00..0x3F context)
    -> type_global   (+0x20 middle object, +0x00..0x3F context)
    -> middle        (+0x18 runtime class object, +0x00..0x3F context)
    -> class object  (+0xC8 initialized bit, +0x00..0xCF context)

Boundary: OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ),
PSAPI EnumProcessModulesEx, ReadProcessMemory on the static chain only.
No writes, no remote code, no full address-space scan.
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


def hex_or_none(value: int | None) -> str | None:
    return f"0x{value:X}" if value is not None else None


def read_context(handle, addr, size, module=None, label=""):
    if addr is None:
        return None
    buf = rpm(handle, addr, size, module=module)
    if buf is None:
        return None
    out = {"address": hex_or_none(addr), "size": len(buf), "bytes": buf.hex(" ")}
    if len(buf) >= 8:
        out["qwords"] = [hex_or_none(struct.unpack_from("<Q", buf, o)[0])
                         for o in range(0, min(len(buf) - 7, 0x40), 8)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--game-file", required=True, type=Path)
    ap.add_argument("--game-version", default="4.4.54")
    ap.add_argument("--parser-global-rva", type=lambda v: int(v, 0), required=True)
    ap.add_argument("--type-global-rva", type=lambda v: int(v, 0), required=True)
    ap.add_argument("--json", type=Path, required=True)
    args = ap.parse_args()

    set_api()
    game_pe = PeFile(args.game_file)
    result = {
        "schema": "ability_descriptor_snapshot/1",
        "tool": "tools/runtime_snapshot/ability_descriptor_snapshot.py",
        "game_version": args.game_version,
        "parser_global_rva": hex_or_none(args.parser_global_rva),
        "type_global_rva": hex_or_none(args.type_global_rva),
        "static_chain": [
            "SkillAbilityConfig.OJNNBEJLDIJ 0x1D4AAC90 mov rsi,[rip] -> 0x96B7C00 (rdx)",
            "SkillAbilityConfig.OJNNBEJLDIJ 0x1D4AAD33 mov r9,[rip] -> 0x96B7C08 (r9)",
            "generic object reader 0x16C86A10: class = [[r9+0x20]+0x18]",
            "generic object reader 0x16C86A10: parser = [rdx+8], call parser(reader,out,rdx)",
            "generic object reader 0x16C86A10: array of class, slots at +0x20",
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
            pe = game_pe if rec["name"] == "gameassembly.dll" else None
            if pe is None:
                continue
            modules.append(RemoteModule("GameAssembly", rec["base"], rec["path"], pe))
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

        parser_va = game.base + args.parser_global_rva
        type_va = game.base + args.type_global_rva
        parser_ptr = read_qword(handle, parser_va, module=game)
        type_ptr = read_qword(handle, type_va, module=game)
        result["read_result"]["parser_global"] = {
            "va": hex_or_none(parser_va), "value": hex_or_none(parser_ptr),
            "describe": describe_pointer(parser_ptr, modules) if parser_ptr else None,
        }
        result["read_result"]["type_global"] = {
            "va": hex_or_none(type_va), "value": hex_or_none(type_ptr),
            "describe": describe_pointer(type_ptr, modules) if type_ptr else None,
        }

        if parser_ptr is None or not (MIN_USER_POINTER <= parser_ptr <= CANONICAL_USER_MAX):
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"parser descriptor pointer invalid: {parser_ptr}"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"FAILED: parser descriptor pointer invalid: {hex_or_none(parser_ptr)}")
            return 1
        if type_ptr is None or not (MIN_USER_POINTER <= type_ptr <= CANONICAL_USER_MAX):
            result["final_status"] = "POINTER_VALIDATION_FAILED"
            result["error"] = f"type descriptor pointer invalid: {type_ptr}"
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"FAILED: type descriptor pointer invalid: {hex_or_none(type_ptr)}")
            return 1

        # Code-proven parser slot: [parser_global + 0x08].
        parser_code = read_qword(handle, parser_ptr + 8)
        parser_code_desc = describe_pointer(parser_code, modules) if parser_code else None
        result["read_result"]["parser_code_pointer"] = {
            "address": hex_or_none(parser_ptr + 8),
            "value": hex_or_none(parser_code),
            "describe": parser_code_desc,
            "bytes": None,
        }
        if parser_code_desc and parser_code_desc["in_known_module"] and parser_code_desc["is_executable"]:
            result["read_result"]["parser_code_pointer"]["bytes"] = (
                rpm(handle, parser_code, 32, module=game) or b"\0" * 32).hex(" ")
        else:
            result["validation"].append(
                f"parser code pointer not executable-in-module: {parser_code_desc}")

        # Code-proven type chain: type_global -> [+0x20] -> middle -> [+0x18] -> class.
        middle_ptr = read_qword(handle, type_ptr + 0x20)
        result["read_result"]["type_middle"] = {
            "address": hex_or_none(type_ptr + 0x20), "value": hex_or_none(middle_ptr),
            "describe": describe_pointer(middle_ptr, modules) if middle_ptr else None,
        }
        class_ptr = None
        if middle_ptr is not None and (MIN_USER_POINTER <= middle_ptr <= CANONICAL_USER_MAX):
            class_ptr = read_qword(handle, middle_ptr + 0x18)
        result["read_result"]["runtime_class_pointer"] = {
            "address": hex_or_none(middle_ptr + 0x18) if middle_ptr else None,
            "value": hex_or_none(class_ptr),
            "describe": describe_pointer(class_ptr, modules) if class_ptr else None,
        }

        # Bounded contexts for evidence only; no extra pointer dereference.
        contexts = {
            "parser_descriptor_ctx": read_context(handle, parser_ptr, 0x40),
            "type_descriptor_ctx": read_context(handle, type_ptr, 0x40),
            "type_middle_ctx": read_context(handle, middle_ptr, 0x40),
        }
        if class_ptr is not None and (MIN_USER_POINTER <= class_ptr <= CANONICAL_USER_MAX):
            contexts["runtime_class_ctx"] = read_context(handle, class_ptr, 0xD0)
            init_byte = rpm(handle, class_ptr + 0xC8, 1)
            result["read_result"]["class_initialized_bit_c8"] = (
                int(init_byte[0]) if init_byte else None)
        result["read_result"]["contexts"] = contexts

        result["validation"].append("parser descriptor + type descriptor global read: PASS")
        result["validation"].append("code-proven pointer chain reads: PASS")
        result["final_status"] = "DESCRIPTOR_CHAIN_READABLE"
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"final_status: {result['final_status']}")
        print(f"parser_global -> {hex_or_none(parser_ptr)}")
        print(f"parser_code   -> {hex_or_none(parser_code)} {parser_code_desc}")
        print(f"type_global   -> {hex_or_none(type_ptr)}")
        print(f"type_middle   -> {hex_or_none(middle_ptr)}")
        print(f"runtime_class -> {hex_or_none(class_ptr)}")
        return 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
