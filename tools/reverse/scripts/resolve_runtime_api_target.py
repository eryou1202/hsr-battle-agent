# resolve_runtime_api_target.py
#
# RO-RUNTIME static stage: resolve an IL2CPP API table slot through the
# wrapper -> descriptor -> real-target-stub chain, and classify the stub.
#
# Important structural facts (4.4.54, E2):
#   - table entry points at a UnityPlayer wrapper stub;
#   - wrapper shape A: 45 33 C0 | 48 8D 0D <desc> | 33 D2 | E9 <dispatcher>;
#   - descriptor is a 0x58-byte record in UnityPlayer .data; it is only
#     readable from a mapped image (on-disk .data bytes are encrypted);
#   - descriptor q[5] is the real-target stub for shape A records.
#
# The semantic slot name (e.g. slot 63 = domain_get) is an E2 assumption
# inherited from the honkai-dumper index map. This tool reports the stub
# classification separately so the assumption can be falsified.
#
# Boundary: loads UnityPlayer.dll / GameAssembly.dll in THIS process with the
# standard loader for read-only inspection. It never opens the game process,
# never writes memory, never calls remote code.
#
# Usage:
#   python tools/reverse/scripts/resolve_runtime_api_target.py \
#       --unity D:\StarRail_4.4.53\UnityPlayer.dll \
#       --game D:\StarRail_4.4.53\GameAssembly.dll \
#       --slot 63 [--table-rva 0x1A36480] [--json out.json]

import argparse
import ctypes
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_il2cpp_api_table import KNOWN_SLOT_NAMES, Locator, PeImage  # noqa: E402

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    HAVE_CAPSTONE = True
except Exception:  # pragma: no cover - capstone is optional for JSON metadata
    HAVE_CAPSTONE = False

A_STUB_PATTERN = b"\x48\x83\xec\x28"  # sub rsp, 0x28
SENTINEL = 0xFFFFFFFFFFFFFFFF


def load_module(path: Path):
    mod = ctypes.CDLL(str(path.resolve()))
    return mod, int(mod._handle)


def read_mapped(base: int, rva: int, size: int) -> bytes | None:
    try:
        return bytes((ctypes.c_char * size).from_address(base + rva))
    except Exception:
        return None


def read_qword(base: int, rva: int) -> int | None:
    b = read_mapped(base, rva, 8)
    return struct.unpack("<Q", b)[0] if b else None


def rva_in_module(va: int, base: int, pe: PeImage) -> int | None:
    max_rva = max(s.rva + s.size for s in pe.sections)
    if base <= va < base + max_rva:
        rva = va - base
        if pe.section_at_rva(rva) is not None:
            return rva
    return None


def describe(va: int, mods: list[tuple[str, int, PeImage]]) -> dict:
    for name, base, pe in mods:
        rva = rva_in_module(va, base, pe)
        if rva is not None:
            sec = pe.section_at_rva(rva)
            return {
                "module": name,
                "rva": rva,
                "section": sec.name if sec else None,
                "is_executable": bool(sec.is_executable) if sec else False,
            }
    return {"module": "OUTSIDE", "rva": None, "section": None, "is_executable": False}


def describe_by_rva(rva: int, mods: list[tuple[str, int, PeImage]]) -> dict:
    """Describe a file-RVA target by trying it against each loaded module base."""
    for name, base, pe in mods:
        hit = describe(base + rva, mods)
        if hit["module"] == name:
            return hit
    return {"module": "OUTSIDE", "rva": rva, "section": None, "is_executable": False}


def classify_real_stub(base: int, rva: int) -> dict:
    b = read_mapped(base, rva, 64)
    if not b:
        return {"classification": "unreadable", "instruction_bytes": []}

    kind = "other"
    if (len(b) >= 44 and b[0:4] == A_STUB_PATTERN and b[4] == 0xE8
            and b[33:37] == b"\x48\x83\xc4\x28" and b[37] == 0xE9):
        kind = "proxy-registration"
    else:
        # simple global-return patterns: mov/lea rax,[rip+disp] ; ret
        for i in range(0, min(len(b) - 7, 32)):
            if b[i:i+3] in (b"\x48\x8b\x05", b"\x48\x8d\x05"):
                if b"\xc3" in b[i:i+20]:
                    kind = "global-return"
                    break

    insns = []
    if HAVE_CAPSTONE:
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        for insn in md.disasm(b, rva):
            insns.append({
                "address": insn.address,
                "bytes": insn.bytes.hex(" "),
                "mnemonic": insn.mnemonic,
                "op_str": insn.op_str,
            })
            if len(insns) >= 8:
                break

    # Standard proxy-registration stub layout:
    #   sub rsp,0x28 ; call helper ; lea r9,[rip+X] ; mov rcx,rax ;
    #   lea r8,[rip+Y] ; lea rdx,[rip+Z] ; add rsp,0x28 ; jmp append_fn
    triple = {}
    if len(b) >= 44 and b[0:4] == A_STUB_PATTERN and b[4] == 0xE8:
        if b[9:12] == b"\x4c\x8d\x0d":
            disp = struct.unpack_from("<i", b, 12)[0]
            triple["r9_rva"] = rva + 16 + disp
        if b[19:22] == b"\x4c\x8d\x05":
            disp = struct.unpack_from("<i", b, 22)[0]
            triple["r8_rva"] = rva + 26 + disp
        if b[26:29] == b"\x48\x8d\x15":
            disp = struct.unpack_from("<i", b, 29)[0]
            triple["rdx_rva"] = rva + 33 + disp

    return {"classification": kind, "instruction_bytes": insns, "stub_triple": triple}


def cstring_at(base: int, rva: int, max_len: int = 192) -> str | None:
    b = read_mapped(base, rva, max_len)
    if not b:
        return None
    end = b.find(b"\0")
    if end < 0:
        return None
    return b[:end].decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unity", required=True, type=Path)
    parser.add_argument("--game", type=Path, default=None)
    parser.add_argument("--slot", type=int, default=63)
    parser.add_argument("--table-rva", type=lambda v: int(v, 0), default=None,
                        help="optional table RVA; when omitted the structural locator is used")
    parser.add_argument("--expect-rva", type=lambda v: int(v, 0), default=None,
                        help="comparison-only validation, never used for resolution")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    result = {
        "tool": "tools/reverse/scripts/resolve_runtime_api_target.py",
        "unity_player": str(args.unity),
        "game_assembly": str(args.game) if args.game else None,
        "slot": args.slot,
        "assumed_slot_name": KNOWN_SLOT_NAMES.get(args.slot),
        "assumed_slot_name_evidence": "E2_honkai_dumper_index_assumption",
    }

    unity_pe = PeImage(args.unity)
    game_pe = PeImage(args.game) if args.game else None

    unity, u_base = load_module(args.unity)
    mods = [("UnityPlayer", u_base, unity_pe)]
    if args.game:
        try:
            game, g_base = load_module(args.game)
            mods.append(("GameAssembly", g_base, game_pe))
        except Exception as exc:
            result["game_assembly_load"] = f"SKIPPED: {exc}"

    if args.table_rva is None:
        locator = Locator(args.unity)
        located = locator.locate()
        best = located["best_candidate"]
        table_rva = int(best["rva"], 16) if best else None
        result["table_location_method"] = "structural_locator"
        result["locator"] = {
            "candidates_scanned": located["candidates_scanned"],
            "score": located["score"],
            "confidence": located["confidence"],
        }
    else:
        table_rva = args.table_rva
        result["table_location_method"] = "caller_supplied_rva"

    if args.expect_rva is not None:
        result["expect_rva"] = args.expect_rva
        result["expect_rva_match"] = (table_rva == args.expect_rva)

    result["api_table"] = {"module": "UnityPlayer", "rva": table_rva}
    entry_va = read_qword(u_base, table_rva + args.slot * 8)
    if entry_va is None:
        result["status"] = "GLOBAL_CHAIN_UNRESOLVED"
        result["error"] = "table entry unreadable"
        _write_json(args, result)
        return 1

    wrapper_rva = rva_in_module(entry_va, u_base, unity_pe)
    if wrapper_rva is None:
        result["status"] = "STATIC_TARGET_UNRESOLVED"
        result["error"] = f"table entry 0x{entry_va:X} is outside UnityPlayer code"
        _write_json(args, result)
        return 1

    wrapper_bytes = read_mapped(u_base, wrapper_rva, 16)
    result["wrapper"] = {
        "rva": wrapper_rva,
        "bytes": wrapper_bytes.hex(" ") if wrapper_bytes else None,
    }
    if not wrapper_bytes or wrapper_bytes[:3] != b"\x45\x33\xc0" \
            or wrapper_bytes[3:6] != b"\x48\x8d\x0d":
        result["status"] = "STATIC_TARGET_UNRESOLVED"
        result["error"] = "wrapper is not shape A"
        _write_json(args, result)
        return 1

    desc_disp = struct.unpack_from("<i", wrapper_bytes, 6)[0]
    desc_rva = wrapper_rva + 10 + desc_disp
    result["descriptor"] = {"rva": desc_rva, "qwords": {}}
    desc = result["descriptor"]
    desc["qwords"] = {
        str(i): read_qword(u_base, desc_rva + i * 8) for i in range(12)
    }
    desc["qwords_described"] = {
        str(i): describe(q, mods) for i, q in desc["qwords"].items()
    }

    q5 = desc["qwords"].get("5")
    if q5 is None:
        result["status"] = "STATIC_TARGET_UNRESOLVED"
        result["error"] = "descriptor q[5] is null"
        _write_json(args, result)
        return 1

    q5_loc = describe(q5, mods)
    real_target = {
        "va": q5,
        "module": q5_loc["module"],
        "rva": q5_loc["rva"],
        "section": q5_loc["section"],
        "classification": {},
    }
    if q5_loc["rva"] is not None and q5_loc["module"] == "UnityPlayer":
        real_target["classification"] = classify_real_stub(u_base, q5_loc["rva"])
        triple = real_target["classification"].get("stub_triple", {})
        for key in ("r8_rva", "r9_rva", "rdx_rva"):
            if key not in triple:
                continue
            if key == "rdx_rva":
                triple[key + "_string"] = cstring_at(u_base, triple[key])
            else:
                triple[key + "_described"] = describe_by_rva(triple[key], mods)
    result["real_target"] = real_target

    result["status"] = "STATIC_CHAIN_RESOLVED"
    _write_json(args, result)
    return 0


def _write_json(args: argparse.Namespace, result: dict) -> None:
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"json: {args.json}")


if __name__ == "__main__":
    raise SystemExit(main())
