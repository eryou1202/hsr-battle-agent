# resolve_il2cpp_get_api_table.py
#
# Resolve the real PE export `il2cpp_get_api_table` from GameAssembly.dll and
# perform a minimal, automatic static analysis of its entry point.
#
# This tool deliberately does NOT inherit any table RVA or slot semantics from
# previous experiments. It only answers:
#
#   1. does the export exist in the PE export directory (name-exact)?
#   2. what are ordinal / export RVA / containing section / forwarder status?
#   3. what does the minimal entry control flow look like?
#   4. what is the real return source (global / direct address / initializer
#      helper / wrapper / dispatcher)?
#
# It has no hard-coded 4.4.54 RVAs and performs no remote calls.
#
# Usage:
#   python tools/reverse/scripts/resolve_il2cpp_get_api_table.py \
#       --game D:\StarRail_4.4.53\GameAssembly.dll \
#       [--json data\raw\4.4.54\il2cpp\real_il2cpp_api_root_4.4.54.json]
#       [--max-bytes 4096] [--max-insns 512]

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXPORT_NAME = "il2cpp_get_api_table"

IMAGE_SCN_CNT_CODE = 0x00000020
IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_MEM_WRITE = 0x80000000
IMAGE_SCN_MEM_READ = 0x40000000

# ---------------------------------------------------------------------------
# Minimal PE parser (file-backed; GameAssembly.dll is ~535 MB, so we do not
# read the whole file into memory).
# ---------------------------------------------------------------------------


@dataclass
class PeSection:
    name: str
    rva: int
    vsize: int
    raw_size: int
    raw_offset: int
    characteristics: int

    @property
    def size(self) -> int:
        return max(self.vsize, self.raw_size, 0x1000)

    @property
    def is_executable(self) -> bool:
        return bool(self.characteristics & IMAGE_SCN_MEM_EXECUTE)

    @property
    def is_writable(self) -> bool:
        return bool(self.characteristics & IMAGE_SCN_MEM_WRITE)


class PeImage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.f = open(self.path, "rb")
        data = self.f.read(0x1000)
        if data[:2] != b"MZ":
            raise ValueError(f"not a PE file: {self.path}")
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        pe_sig = self._read(e_lfanew, 4)
        if pe_sig != b"PE\0\0":
            raise ValueError(f"bad PE signature: {self.path}")
        coff = self._read(e_lfanew + 4, 20)
        self.machine = struct.unpack_from("<H", coff, 0)[0]
        self.num_sections = struct.unpack_from("<H", coff, 2)[0]
        self.time_date_stamp = struct.unpack_from("<I", coff, 4)[0]
        self.opt_size = struct.unpack_from("<H", coff, 16)[0]
        self.opt_offset = e_lfanew + 24
        opt = self._read(self.opt_offset, self.opt_size)
        self.magic = struct.unpack_from("<H", opt, 0)[0]
        if self.magic != 0x20B:
            raise ValueError(f"not PE32+: {self.path}")
        self.image_base = struct.unpack_from("<Q", opt, 24)[0]
        self.size_of_image = struct.unpack_from("<I", opt, 56)[0]
        self.checksum = struct.unpack_from("<I", opt, 64)[0]
        self.data_directories = []
        for i in range(16):
            off = 112 + i * 8
            rva, size = struct.unpack_from("<II", opt, off)
            self.data_directories.append((rva, size))
        self.sections: list[PeSection] = []
        sec_off = self.opt_offset + self.opt_size
        for i in range(self.num_sections):
            s = self._read(sec_off + i * 40, 40)
            name = s[:8].rstrip(b"\0").decode("latin1")
            vsize, rva = struct.unpack_from("<II", s, 8)
            raw_size, raw_offset = struct.unpack_from("<II", s, 16)
            chars = struct.unpack_from("<I", s, 36)[0]
            self.sections.append(PeSection(name, rva, vsize, raw_size, raw_offset, chars))

    def _read(self, file_offset: int, size: int) -> bytes:
        self.f.seek(file_offset)
        return self.f.read(size)

    def section_at_rva(self, rva: int) -> PeSection | None:
        for s in self.sections:
            if s.rva <= rva < s.rva + s.size:
                return s
        return None

    def rva_to_file_offset(self, rva: int) -> int | None:
        s = self.section_at_rva(rva)
        if s is None:
            return None
        return s.raw_offset + (rva - s.rva)

    def read_rva(self, rva: int, size: int) -> bytes | None:
        off = self.rva_to_file_offset(rva)
        if off is None:
            return None
        return self._read(off, size)

    def sha256(self, chunk_size: int = 1 << 20) -> str:
        h = hashlib.sha256()
        self.f.seek(0)
        while True:
            chunk = self.f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
        return h.hexdigest()


@dataclass
class ExportRecord:
    name: str
    ordinal: int
    rva: int
    forwarder: bool
    section: str | None
    section_is_executable: bool
    entry_bytes: bytes


def parse_export(pe: PeImage, wanted: str) -> dict[str, Any]:
    """Re-verify a named export straight from the PE export directory."""
    exp_rva, exp_size = pe.data_directories[0]
    result: dict[str, Any] = {
        "export_directory_rva": exp_rva,
        "export_directory_size": exp_size,
        "name_exact_match": None,
        "matches": [],
    }
    if exp_rva == 0 or exp_size == 0:
        result["error"] = "no export directory"
        return result

    hdr = pe.read_rva(exp_rva, 40)
    if hdr is None:
        result["error"] = "export directory header unreadable"
        return result
    (_, _, _, _, _dll_name_rva, ordinal_base,
     num_functions, num_names, addr_rva, name_ptr_rva, ordinal_rva) = struct.unpack(
        "<IIHHIIIIIII", hdr)

    for i in range(num_names):
        ptr_off = pe.rva_to_file_offset(name_ptr_rva + i * 4)
        if ptr_off is None:
            continue
        ptr_bytes = pe._read(ptr_off, 4)
        if len(ptr_bytes) != 4:
            continue
        name_rva = struct.unpack("<I", ptr_bytes)[0]
        raw = pe.read_rva(name_rva, 256)
        if raw is None:
            continue
        end = raw.find(b"\0")
        if end < 0:
            continue
        name = raw[:end].decode("utf-8", errors="replace")
        if name != wanted:
            continue
        ord_off = pe.rva_to_file_offset(ordinal_rva + i * 2)
        addr_idx = struct.unpack("<H", pe._read(ord_off, 2))[0] if ord_off is not None else 0
        addr_off = pe.rva_to_file_offset(addr_rva + addr_idx * 4)
        func_rva = struct.unpack("<I", pe._read(addr_off, 4))[0] if addr_off is not None else 0
        section = pe.section_at_rva(func_rva)
        forwarder = exp_rva <= func_rva < exp_rva + exp_size
        entry_bytes = pe.read_rva(func_rva, 64) or b""
        result["matches"].append({
            "name": name,
            "name_index": i,
            "ordinal_index": addr_idx,
            "ordinal": ordinal_base + addr_idx,
            "rva": func_rva,
            "forwarder": forwarder,
            "section": section.name if section else None,
            "section_is_executable": bool(section and section.is_executable),
            "entry_bytes_hex": entry_bytes.hex(" "),
        })
    result["name_exact_match"] = bool(result["matches"])
    return result


# ---------------------------------------------------------------------------
# Minimal x86-64 length/operand decoder.
#
# This is intentionally small: it is enough to walk common prologues,
# RIP-relative loads / LEAs / stores, direct calls/jumps and terminators.
# Unknown encodings are reported as undecodable instead of guessed.
# ---------------------------------------------------------------------------

REX = "rex"
LEGACY_PREFIXES = {0x66: "66", 0x67: "67", 0xF0: "f0", 0xF2: "f2", 0xF3: "f3"}


@dataclass
class Insn:
    address: int
    length: int
    raw: bytes
    mnemonic: str = "db"
    op_str: str = ""
    prefixes: list[str] = field(default_factory=list)
    rex: int | None = None
    modrm: dict[str, Any] | None = None
    immediate: int | None = None
    rip_relative: bool = False
    rip_target: int | None = None
    mem_access: str | None = None  # read / write / rmw / address / none
    direct_call_target: int | None = None
    direct_jump_target: int | None = None
    is_conditional_jump: bool = False
    is_ret: bool = False
    reg_text: str | None = None


def reg_name(reg: int, rex: int | None, width: int = 64) -> str:
    names64 = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
               "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
    names32 = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi",
               "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"]
    names8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh",
              "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"]
    # Callers already applied REX.B/R/X extensions when constructing the
    # register index; do not apply extensions again here.
    if width == 8:
        return names8[reg & 0xF]
    if width == 32:
        return names32[reg & 0xF]
    return names64[reg & 0xF]


def parse_modrm(data: bytes, pos: int, rex: int | None) -> tuple[dict[str, Any], int, int | None, bool, int | None]:
    """Parse ModRM + SIB + displacement.

    Returns (info, consumed, disp_value, rip_relative, rip_target_abs).
    rip_target_abs is meaningful only for mod=00 rm=101.
    """
    info: dict[str, Any] = {}
    b = data[pos]
    mod = (b >> 6) & 3
    reg_field = (b >> 3) & 7
    rm_field = b & 7
    if rex:
        if rex & 0x04:  # REX.R extends the reg field to 4 bits (+8)
            reg_field += 8
        if rex & 0x01:  # REX.B extends the r/m field to 4 bits (+8)
            rm_field += 8
    info["mod"] = mod
    info["reg"] = reg_field
    info["rm"] = rm_field
    consumed = 1
    disp = None
    rip = False
    rip_target = None

    if mod == 3:
        info["rm_is_reg"] = True
        return info, consumed, disp, rip, rip_target

    info["rm_is_reg"] = False
    base = rm_field
    index = None
    scale = 1
    if rm_field == 4:
        sib = data[pos + 1]
        consumed += 1
        scale = 1 << ((sib >> 6) & 3)
        idx_field = (sib >> 3) & 7
        base_field = sib & 7
        if rex:
            if rex & 0x02:
                idx_field += 8  # REX.X -> +8
            if rex & 0x01:
                base_field += 8  # REX.B -> +8
        index = idx_field if idx_field != 4 or (rex and rex & 0x02) else None
        base = base_field
        info["sib"] = {"scale": scale, "index": index, "base": base}
        if mod == 0 and base == 5:
            disp = struct.unpack_from("<i", data, pos + consumed)[0]
            consumed += 4
            # mod=00 base=101 is RIP-relative regardless of SIB/REX details.
            rip = True
            info["rip_disp"] = disp
        else:
            if mod == 1:
                disp = struct.unpack_from("<b", data, pos + consumed)[0]
                consumed += 1
            elif mod == 2:
                disp = struct.unpack_from("<i", data, pos + consumed)[0]
                consumed += 4
    else:
        if mod == 0 and rm_field == 5:
            disp = struct.unpack_from("<i", data, pos + consumed)[0]
            consumed += 4
            rip = True
            info["rip_disp"] = disp
        else:
            if mod == 1:
                disp = struct.unpack_from("<b", data, pos + consumed)[0]
                consumed += 1
            elif mod == 2:
                disp = struct.unpack_from("<i", data, pos + consumed)[0]
                consumed += 4
    info["disp"] = disp
    return info, consumed, disp, rip, None


def make_operand_text(modrm: dict[str, Any], rex: int | None, rex_w: bool, size_hint: int = 64) -> str:
    """Return a compact operand string for one ModRM side."""
    if modrm.get("rm_is_reg"):
        return reg_name(modrm["rm"] & 0xF, rex, size_hint)
    parts = []
    base = modrm.get("rm")
    sib = modrm.get("sib")
    if sib is not None:
        if sib["base"] == 5 and modrm["mod"] == 0:
            parts.append("rip")
        else:
            parts.append(reg_name(sib["base"], rex, 64))
        if sib["index"] is not None:
            parts.append(reg_name(sib["index"], rex, 64))
            if sib["scale"] != 1:
                parts[-1] += f"*{sib['scale']}"
    else:
        if modrm["mod"] == 0 and base == 5:
            parts.append("rip")
        else:
            parts.append(reg_name(base, rex, 64))
    disp = modrm.get("disp")
    if disp is not None and disp != 0:
        parts.append(f"{disp:+d}")
    if not parts:
        return "?"
    if len(parts) == 1 and parts[0] in ("rip",):
        return f"[rip{modrm.get('disp', 0):+d}]"
    return "[" + "+".join(parts) + "]"


def decode_one(data: bytes, address: int) -> Insn | None:
    """Decode one common x86-64 instruction. Return None if unsupported."""
    if not data:
        return None
    ip = 0
    prefixes: list[str] = []
    while ip < len(data) and data[ip] in LEGACY_PREFIXES:
        prefixes.append(LEGACY_PREFIXES[data[ip]])
        ip += 1
    rex: int | None = None
    if ip < len(data) and 0x40 <= data[ip] <= 0x4F:
        rex = data[ip]
        prefixes.append(f"rex{data[ip]:02x}")
        ip += 1
    if ip >= len(data):
        return None
    op = data[ip]
    ip += 1
    rex_w = bool(rex and rex & 0x08)
    insn = Insn(address=address, length=0, raw=b"", prefixes=prefixes, rex=rex)
    modrm: dict[str, Any] | None = None
    disp = None
    rip = False
    rip_disp = None
    imm: int | None = None
    mnemonic = ""
    op_str = ""
    mem_access = None
    direct_call = None
    direct_jump = None
    is_jcc = False
    is_ret = False
    reg_text = None

    def read_modrm(size_hint: int = 64):
        nonlocal modrm, disp, rip, rip_disp
        info, consumed, d, is_rip, _ = parse_modrm(data, ip, rex)
        modrm = info
        disp = d
        rip = is_rip
        if is_rip:
            rip_disp = d
        return consumed

    # --- 1-byte opcodes ---------------------------------------------------
    if 0x50 <= op <= 0x57:
        mnemonic = "push"
        reg = op - 0x50 + (8 if rex and rex & 1 else 0)
        op_str = reg_name(reg, None, 64)
    elif 0x58 <= op <= 0x5F:
        mnemonic = "pop"
        reg = op - 0x58 + (8 if rex and rex & 1 else 0)
        op_str = reg_name(reg, None, 64)
    elif op == 0x68:
        mnemonic = "push"
        imm = struct.unpack_from("<i", data, ip)[0]
        ip += 4
        op_str = f"0x{imm & 0xFFFFFFFF:x}"
    elif op == 0x6A:
        mnemonic = "push"
        imm = struct.unpack_from("<b", data, ip)[0]
        ip += 1
        op_str = f"0x{imm & 0xFF:x}"
    elif 0x70 <= op <= 0x7F:
        mnemonic = f"jcc_{op:02x}"
        off = struct.unpack_from("<b", data, ip)[0]
        ip += 1
        direct_jump = address + ip + off
        is_jcc = True
        op_str = f"0x{direct_jump:x}"
    elif op in (0x80, 0x81, 0x83):
        ip += read_modrm()
        group1_names = {0: "add", 1: "or", 2: "adc", 3: "sbb",
                        4: "and", 5: "sub", 6: "xor", 7: "cmp"}
        mnemonic = group1_names.get(modrm["reg"], "alu_group1")
        if op == 0x80:
            imm = data[ip]; ip += 1
        elif op == 0x81:
            imm = struct.unpack_from("<i", data, ip)[0] if "66" not in prefixes else struct.unpack_from("<h", data, ip)[0]
            ip += 2 if "66" in prefixes else 4
        else:
            imm = struct.unpack_from("<b", data, ip)[0]; ip += 1
        mem_access = ("read" if modrm["reg"] == 7 else "rmw") if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, 8 if op == 0x80 else 64)}, 0x{imm & ((1 << (8 if op in (0x80, 0x83) else 32)) - 1):x}"
    elif op in (0x84, 0x85):
        mnemonic = "test"
        ip += read_modrm(8 if op == 0x84 else 64)
        mem_access = "read" if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, 8 if op == 0x84 else 64)}, {reg_name(modrm['reg'], rex, 8 if op == 0x84 else 64)}"
    elif op in (0x86, 0x87):
        mnemonic = "xchg"
        ip += read_modrm(8 if op == 0x86 else 64)
        mem_access = "rmw" if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, 8 if op == 0x86 else 64)}, {reg_name(modrm['reg'], rex, 8 if op == 0x86 else 64)}"
    elif op in (0x88, 0x89, 0x8A, 0x8B):
        mnemonic = "mov"
        width = 8 if op in (0x88, 0x8A) else 64
        ip += read_modrm(width)
        if op in (0x88, 0x89):
            # mov r/m, reg
            op_str = f"{make_operand_text(modrm, rex, rex_w, width)}, {reg_name(modrm['reg'], rex, width)}"
            mem_access = "write" if not modrm.get("rm_is_reg") else None
            reg_text = reg_name(modrm["reg"], rex, width)
        else:
            # mov reg, r/m
            op_str = f"{reg_name(modrm['reg'], rex, width)}, {make_operand_text(modrm, rex, rex_w, width)}"
            mem_access = "read" if not modrm.get("rm_is_reg") else None
            reg_text = reg_name(modrm["reg"], rex, width)
    elif op == 0x8D:
        mnemonic = "lea"
        ip += read_modrm()
        mem_access = "address"
        op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, 64)}"
        reg_text = reg_name(modrm["reg"], rex, 64)
    elif op == 0x8F:
        mnemonic = "pop"
        ip += read_modrm()
        mem_access = "write" if not modrm.get("rm_is_reg") else None
        op_str = make_operand_text(modrm, rex, rex_w, 64)
    elif op == 0x90:
        mnemonic = "nop"
        op_str = ""
    elif op in (0x9C, 0x9D, 0xF5, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xF4):
        mnemonic = {0x9C: "pushfq", 0x9D: "popfq", 0xF5: "cmc", 0xF8: "clc",
                    0xF9: "stc", 0xFA: "cli", 0xFB: "sti", 0xFC: "cld",
                    0xFD: "std", 0xF4: "hlt"}[op]
        op_str = ""
    elif op == 0xCC:
        mnemonic = "int3"
        op_str = ""
    elif op == 0xCD:
        mnemonic = "int"
        imm = data[ip]; ip += 1
        op_str = f"0x{imm:x}"
    elif 0xB0 <= op <= 0xB7:
        mnemonic = "mov"
        imm = data[ip]; ip += 1
        reg = op - 0xB0 + (8 if rex and rex & 1 else 0)
        op_str = f"{reg_name(reg, None, 8)}, 0x{imm:x}"
        reg_text = reg_name(reg, None, 8)
    elif 0xB8 <= op <= 0xBF:
        mnemonic = "mov"
        reg = op - 0xB8 + (8 if rex and rex & 1 else 0)
        imm = struct.unpack_from("<Q" if rex_w else "<I", data, ip)[0]
        ip += 8 if rex_w else 4
        op_str = f"{reg_name(reg, None, 64 if rex_w else 32)}, 0x{imm:x}"
        reg_text = reg_name(reg, None, 64 if rex_w else 32)
    elif op in (0xC0, 0xC1):
        mnemonic = "shift_group2"
        ip += read_modrm(8 if op == 0xC0 else 64)
        imm = data[ip]; ip += 1
        mem_access = "rmw" if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, 8 if op == 0xC0 else 64)}, 0x{imm:x}"
    elif op == 0xC2:
        mnemonic = "ret"
        imm = struct.unpack_from("<H", data, ip)[0]
        ip += 2
        is_ret = True
        op_str = f"0x{imm:x}"
    elif op == 0xC3:
        mnemonic = "ret"
        is_ret = True
        op_str = ""
    elif op in (0xC6, 0xC7):
        mnemonic = "mov"
        width = 8 if op == 0xC6 else 64
        ip += read_modrm(width)
        imm = data[ip] if op == 0xC6 else struct.unpack_from("<I", data, ip)[0]
        ip += 1 if op == 0xC6 else 4
        mem_access = "write" if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, width)}, 0x{imm:x}"
    elif op in (0xD0, 0xD1, 0xD2, 0xD3):
        mnemonic = "shift_group2"
        width = 8 if op in (0xD0, 0xD2) else 64
        ip += read_modrm(width)
        mem_access = "rmw" if not modrm.get("rm_is_reg") else None
        op_str = f"{make_operand_text(modrm, rex, rex_w, width)}, 1/cl"
    elif op == 0xE8:
        mnemonic = "call"
        off = struct.unpack_from("<i", data, ip)[0]
        ip += 4
        direct_call = address + ip + off
        op_str = f"0x{direct_call:x}"
    elif op == 0xE9:
        mnemonic = "jmp"
        off = struct.unpack_from("<i", data, ip)[0]
        ip += 4
        direct_jump = address + ip + off
        op_str = f"0x{direct_jump:x}"
    elif op == 0xEB:
        mnemonic = "jmp"
        off = struct.unpack_from("<b", data, ip)[0]
        ip += 1
        direct_jump = address + ip + off
        op_str = f"0x{direct_jump:x}"
    elif op in (0xF6, 0xF7):
        mnemonic = "group3"
        width = 8 if op == 0xF6 else 64
        ip += read_modrm(width)
        regop = modrm["reg"]
        if regop in (0, 1):
            imm = data[ip] if op == 0xF6 else struct.unpack_from("<I", data, ip)[0]
            ip += 1 if op == 0xF6 else 4
        mem_access = "rmw" if not modrm.get("rm_is_reg") and regop not in (0, 1) else ("read" if not modrm.get("rm_is_reg") else None)
        op_str = make_operand_text(modrm, rex, rex_w, width)
    elif op == 0xFF:
        ip += read_modrm()
        group = modrm["reg"]
        names = {0: "inc", 1: "dec", 2: "call", 3: "callf", 4: "jmp", 5: "jmpf", 6: "push"}
        mnemonic = names.get(group, f"group5_{group}")
        if group == 2:
            mem_access = "read" if not modrm.get("rm_is_reg") else None
        elif group == 4:
            mem_access = "read" if not modrm.get("rm_is_reg") else None
        elif group == 6:
            mem_access = "read" if not modrm.get("rm_is_reg") else None
        else:
            mem_access = "rmw" if not modrm.get("rm_is_reg") else None
        op_str = make_operand_text(modrm, rex, rex_w, 64)
    elif 0x00 <= op <= 0x3B and op != 0x0F:
        base = (op >> 3) & 3
        mnemonic = ["add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"][base]
        width = 8 if (op & 1) == 0 else 64
        ip += read_modrm(width)
        # low two bits: 0/1 => r/m is destination; 2/3 => reg is destination.
        r_m_dest = (op & 3) < 2
        if r_m_dest:
            mem_access = "rmw" if not modrm.get("rm_is_reg") else None
            op_str = f"{make_operand_text(modrm, rex, rex_w, width)}, {reg_name(modrm['reg'], rex, width)}"
        else:
            mem_access = "read" if not modrm.get("rm_is_reg") else None
            op_str = f"{reg_name(modrm['reg'], rex, width)}, {make_operand_text(modrm, rex, rex_w, width)}"
        if mnemonic == "cmp":
            mem_access = "read" if not modrm.get("rm_is_reg") else None
    elif op == 0x63:
        mnemonic = "movsxd"
        ip += read_modrm(64)
        mem_access = "read" if not modrm.get("rm_is_reg") else None
        op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, 32)}"
        reg_text = reg_name(modrm["reg"], rex, 64)
    elif op in (0x69, 0x6B):
        mnemonic = "imul"
        ip += read_modrm()
        imm = struct.unpack_from("<i", data, ip)[0] if op == 0x69 else struct.unpack_from("<b", data, ip)[0]
        ip += 4 if op == 0x69 else 1
        mem_access = "read" if not modrm.get("rm_is_reg") else None
        op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, 64)}, 0x{imm & 0xffffffff:x}"
        reg_text = reg_name(modrm["reg"], rex, 64)
    else:
        # --- 2-byte opcodes -------------------------------------------------
        if op == 0x0F and ip < len(data):
            op2 = data[ip]
            ip += 1
            if 0x80 <= op2 <= 0x8F:
                mnemonic = f"jcc_{op2:02x}"
                off = struct.unpack_from("<i", data, ip)[0]
                ip += 4
                direct_jump = address + ip + off
                is_jcc = True
                op_str = f"0x{direct_jump:x}"
            elif 0x40 <= op2 <= 0x4F:
                mnemonic = "cmovcc"
                ip += read_modrm()
                mem_access = "read" if not modrm.get("rm_is_reg") else None
                op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, 64)}"
            elif 0x90 <= op2 <= 0x9F:
                mnemonic = "setcc"
                ip += read_modrm(8)
                mem_access = "write" if not modrm.get("rm_is_reg") else None
                op_str = make_operand_text(modrm, rex, rex_w, 8)
            elif op2 == 0xAF:
                mnemonic = "imul"
                ip += read_modrm()
                mem_access = "read" if not modrm.get("rm_is_reg") else None
                op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, 64)}"
                reg_text = reg_name(modrm["reg"], rex, 64)
            elif op2 in (0xB6, 0xB7, 0xBE, 0xBF):
                mnemonic = "movzx" if op2 in (0xB6, 0xB7) else "movsx"
                width = {0xB6: 8, 0xB7: 16, 0xBE: 8, 0xBF: 16}[op2]
                ip += read_modrm(width)
                mem_access = "read" if not modrm.get("rm_is_reg") else None
                op_str = f"{reg_name(modrm['reg'], rex, 64)}, {make_operand_text(modrm, rex, rex_w, width)}"
                reg_text = reg_name(modrm["reg"], rex, 64)
            elif op2 == 0x1F:
                mnemonic = "nop"
                ip += read_modrm()
                op_str = make_operand_text(modrm, rex, rex_w, 64)
            elif op2 == 0x05:
                mnemonic = "syscall"
            elif op2 == 0x0B:
                mnemonic = "ud2"
            elif op2 == 0xBA:
                mnemonic = "group8"
                ip += read_modrm()
                imm = data[ip]; ip += 1
                mem_access = "rmw" if not modrm.get("rm_is_reg") else None
                op_str = f"{make_operand_text(modrm, rex, rex_w, 64)}, 0x{imm:x}"
            elif op2 in (0xA3, 0xAB, 0xB3, 0xBB):
                mnemonic = {0xA3: "bt", 0xAB: "bts", 0xB3: "btr", 0xBB: "btc"}[op2]
                ip += read_modrm()
                mem_access = "rmw" if not modrm.get("rm_is_reg") and op2 != 0xA3 else ("read" if not modrm.get("rm_is_reg") else None)
                op_str = f"{make_operand_text(modrm, rex, rex_w, 64)}, {reg_name(modrm['reg'], rex, 64)}"
            elif op2 in (0xB1, 0xC1):
                mnemonic = "cmpxchg" if op2 == 0xB1 else "xadd"
                ip += read_modrm()
                mem_access = "rmw" if not modrm.get("rm_is_reg") else None
                op_str = f"{make_operand_text(modrm, rex, rex_w, 64)}, {reg_name(modrm['reg'], rex, 64)}"
            elif 0xC8 <= op2 <= 0xCF:
                mnemonic = "bswap"
                reg = op2 - 0xC8 + (8 if rex and rex & 1 else 0)
                op_str = reg_name(reg, None, 64)
            elif op2 == 0x31:
                mnemonic = "rdtsc"
            elif op2 == 0xA2:
                mnemonic = "cpuid"
            else:
                insn.raw = data[:ip]
                insn.length = ip
                insn.mnemonic = "db"
                insn.op_str = "unsupported 2-byte opcode"
                return insn
        else:
            insn.raw = data[:ip]
            insn.length = ip
            insn.mnemonic = "db"
            insn.op_str = "unsupported opcode"
            return insn

    length = ip
    insn.length = length
    insn.raw = data[:length]
    insn.mnemonic = mnemonic
    insn.op_str = op_str
    insn.modrm = modrm
    insn.immediate = imm
    insn.mem_access = mem_access
    insn.direct_call_target = direct_call
    insn.direct_jump_target = direct_jump
    insn.is_conditional_jump = is_jcc
    insn.is_ret = is_ret
    insn.reg_text = reg_text
    if rip:
        if rip_disp is None:
            return insn
        insn.rip_relative = True
        insn.rip_target = address + length + rip_disp
        if modrm and modrm.get("disp") is not None:
            modrm["disp"] = rip_disp
    return insn


# ---------------------------------------------------------------------------
# Minimal CFG extraction
# ---------------------------------------------------------------------------


@dataclass
class CfgStep:
    address: int
    size: int
    bytes: str
    mnemonic: str
    op_str: str
    kind: str = "insn"
    call_target: int | None = None
    jump_target: int | None = None
    rip_target: int | None = None
    rip_access: str | None = None


def analyze_entry(pe: PeImage, rva: int, max_bytes: int = 4096,
                  max_insns: int = 512, follow_calls: bool = True,
                  stop_at_first_call: bool = False) -> dict[str, Any]:
    section = pe.section_at_rva(rva)
    section_limit = (section.rva + section.size) if section else rva + max_bytes
    limit = min(rva + max_bytes, section_limit)
    raw = pe.read_rva(rva, limit - rva)
    if not raw:
        return {"error": "entry bytes unreadable", "steps": []}

    steps: list[CfgStep] = []
    cur = 0
    addr = rva
    stop_reason = "max_instructions"
    saw_ret = False
    saw_terminal_jump = False
    while cur < len(raw) and len(steps) < max_insns:
        insn = decode_one(raw[cur:], addr)
        if insn is None or insn.length == 0:
            stop_reason = "undecodable"
            steps.append(CfgStep(
                address=addr, size=len(raw) - cur,
                bytes=raw[cur:cur + 16].hex(" "),
                mnemonic="db", op_str="<undecodable>", kind="stop"))
            break
        kind = "insn"
        if insn.is_ret:
            kind = "ret"
            saw_ret = True
        elif insn.mnemonic == "jmp" and insn.direct_jump_target is not None:
            kind = "terminal_jump"
            saw_terminal_jump = True
        elif insn.is_conditional_jump:
            kind = "jcc"
        elif insn.direct_call_target is not None:
            kind = "call"
        elif insn.mnemonic == "jmp":
            kind = "indirect_jump"
        elif insn.direct_jump_target is not None:
            kind = "jump"
        steps.append(CfgStep(
            address=addr,
            size=insn.length,
            bytes=insn.raw.hex(" "),
            mnemonic=insn.mnemonic,
            op_str=insn.op_str,
            kind=kind,
            call_target=insn.direct_call_target,
            jump_target=insn.direct_jump_target,
            rip_target=insn.rip_target,
            rip_access=insn.mem_access if insn.rip_relative else None,
        ))
        cur += insn.length
        addr += insn.length
        if saw_ret:
            stop_reason = "ret"
            break
        if saw_terminal_jump:
            stop_reason = "terminal_jump"
            break
        if stop_at_first_call and kind == "call":
            stop_reason = "first_call"
            break
        if insn.mnemonic == "db":
            stop_reason = "undecodable"
            break

    direct_calls: list[dict[str, Any]] = []
    rip_reads: list[dict[str, Any]] = []
    rip_writes: list[dict[str, Any]] = []
    rip_leas: list[dict[str, Any]] = []
    for s in steps:
        if s.kind == "call" and s.call_target is not None:
            tsec = pe.section_at_rva(s.call_target)
            direct_calls.append({
                "at": s.address,
                "target": s.call_target,
                "target_section": tsec.name if tsec else None,
                "target_is_executable": bool(tsec and tsec.is_executable),
            })
        if s.rip_target is None:
            continue
        rec = {
            "at": s.address,
            "mnemonic": s.mnemonic,
            "operands": s.op_str,
            "target": s.rip_target,
            "target_section": pe.section_at_rva(s.rip_target).name if pe.section_at_rva(s.rip_target) else None,
        }
        if s.mnemonic == "lea" or s.rip_access == "address":
            rip_leas.append(rec)
        elif s.rip_access == "write":
            rip_writes.append(rec)
        elif s.rip_access == "read":
            rip_reads.append(rec)
        elif s.rip_access == "rmw":
            rip_writes.append({**rec, "note": "read-modify-write; recorded under writes"})
            rip_reads.append({**rec, "note": "read-modify-write; recorded under reads"})

    # Unique candidate globals: every RIP-relative read target that lies in a
    # known section, plus RIP-relative LEA targets (address-only, separate).
    candidate_globals: list[dict[str, Any]] = []
    seen = set()
    for rec in rip_reads:
        key = ("read", rec["target"])
        if key in seen:
            continue
        seen.add(key)
        candidate_globals.append({**rec, "kind": "rip_relative_read"})
    for rec in rip_leas:
        key = ("lea", rec["target"])
        if key in seen:
            continue
        seen.add(key)
        candidate_globals.append({**rec, "kind": "rip_relative_lea"})

    # Bounded follow-up of unique direct call targets (no execution, read-only
    # file analysis). This is what turns "there is a call" into evidence about
    # whether the call target is a plain helper or a protected dispatcher.
    direct_call_target_analyses: dict[str, Any] = {}
    followed = set()
    if follow_calls:
        for call in direct_calls[:4]:
            target = call["target"]
            if target in followed or pe.section_at_rva(target) is None:
                continue
            followed.add(target)
            target_bytes = pe.read_rva(target, 64) or b""
            sub = analyze_entry(
                pe, target,
                max_bytes=min(max_bytes, 512),
                max_insns=min(max_insns, 96),
                follow_calls=False,
                stop_at_first_call=True,
            )
            direct_call_target_analyses[f"0x{target:X}"] = {
                "target_rva": target,
                "target_section": call["target_section"],
                "target_is_executable": call["target_is_executable"],
                "target_entry_bytes_hex": target_bytes.hex(" "),
                "decoded_instructions": sub.get("instruction_count", 0),
                "stop_reason": sub.get("stop_reason"),
                "direct_calls": sub.get("direct_calls", []),
                "rip_relative_reads": sub.get("rip_relative_reads", []),
                "rip_relative_writes": sub.get("rip_relative_writes", []),
                "rip_relative_leas": sub.get("rip_relative_leas", []),
            }

    # Basic blocks by terminators (linear sweep only).
    blocks: list[list[CfgStep]] = []
    current: list[CfgStep] = []
    for s in steps:
        if s.kind == "stop":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(s)
        if s.kind in ("ret", "terminal_jump", "jcc"):
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    return {
        "entry_rva": rva,
        "entry_section": section.name if section else None,
        "entry_bytes_hex": raw[:64].hex(" "),
        "steps": [s.__dict__ for s in steps],
        "instruction_count": len([s for s in steps if s.kind != "stop"]),
        "stop_reason": stop_reason,
        "basic_blocks": [[s.address for s in b] for b in blocks],
        "direct_calls": direct_calls,
        "direct_call_target_analyses": direct_call_target_analyses,
        "rip_relative_reads": rip_reads,
        "rip_relative_writes": rip_writes,
        "rip_relative_leas": rip_leas,
        "candidate_global_rvas": sorted({c["target"] for c in candidate_globals}),
        "candidate_globals": candidate_globals,
    }


def classify_entry(analysis: dict[str, Any], export: dict[str, Any]) -> tuple[str, str, str | None]:
    """Map the minimal CFG evidence to one of the required classes.

    Returns (classification, confidence, candidate_return_source).
    """
    steps = analysis.get("steps", [])
    calls = analysis.get("direct_calls", [])
    reads = analysis.get("rip_relative_reads", [])
    leas = analysis.get("rip_relative_leas", [])

    if not steps:
        return "UNRESOLVED", "none", None

    first = steps[0]
    if first.get("mnemonic") == "mov" and first.get("rip_access") == "read":
        # Direct global return: mov rax,[rip+disp]; ret (allow up to a few
        # padding/junk instructions before ret, but no call in between).
        ret_idx = next((i for i, s in enumerate(steps) if s.get("kind") == "ret"), None)
        call_before_ret = any(s.get("kind") == "call" for s in steps[:ret_idx]) if ret_idx is not None else True
        if ret_idx is not None and ret_idx <= 8 and not call_before_ret:
            target = first.get("rip_target")
            return ("DIRECT_GLOBAL_RETURN", "high",
                    f"mov reg,[rip+{target - first['address']:+d}] -> global @ 0x{target:X}")

    if first.get("mnemonic") == "lea" and first.get("rip_access") == "address":
        ret_idx = next((i for i, s in enumerate(steps) if s.get("kind") == "ret"), None)
        call_before_ret = any(s.get("kind") == "call" for s in steps[:ret_idx]) if ret_idx is not None else True
        if ret_idx is not None and ret_idx <= 8 and not call_before_ret:
            target = first.get("rip_target")
            return ("DIRECT_ADDRESS_RETURN", "high",
                    f"lea rax,[rip+{target - first['address']:+d}] -> address @ 0x{target:X}")

    if first.get("kind") == "terminal_jump":
        target = first.get("jump_target")
        return ("WRAPPER_TO_TARGET", "medium",
                f"entry is a tail jump to 0x{target:X}" if target is not None else None)

    if calls:
        # Initializer pattern: a direct call followed by a RIP-relative global
        # load and a ret.
        ret_idx = next((i for i, s in enumerate(steps) if s.get("kind") == "ret"), None)
        global_after_call = None
        if ret_idx is not None:
            call_idx = min(i for i, s in enumerate(steps) if s.get("kind") == "call")
            for i in range(call_idx + 1, ret_idx):
                if steps[i].get("rip_access") == "read":
                    global_after_call = steps[i].get("rip_target")
                    break
        if global_after_call is not None:
            return ("INITIALIZER_THEN_GLOBAL", "medium",
                    f"call initializer, then load global @ 0x{global_after_call:X} before ret")

        first_call_target = calls[0]["target"]
        tsec = calls[0].get("target_section")
        target_analyses = analysis.get("direct_call_target_analyses", {})
        target_analysis = target_analyses.get(f"0x{first_call_target:X}", {})
        target_is_dispatch_like = (
            bool(target_analysis)
            and not target_analysis.get("rip_relative_reads")
            and not target_analysis.get("rip_relative_leas")
            and not target_analysis.get("rip_relative_writes")
        )
        if tsec is not None and not calls[0].get("target_is_executable"):
            return ("DYNAMIC_DISPATCH", "medium",
                    f"first call target 0x{first_call_target:X} is outside an executable section")
        if target_is_dispatch_like:
            return ("DYNAMIC_DISPATCH", "medium",
                    f"entry stack-machine transfers to 0x{first_call_target:X} "
                    f"({tsec or 'unknown section'}); target CFG shows no static RIP-relative "
                    "return source")
        if reads or leas:
            return ("DYNAMIC_DISPATCH", "low",
                    "call-driven flow with RIP-relative operands; return source not statically reducible")
        return ("DYNAMIC_DISPATCH", "low",
                "entry is call-driven; return source not statically reducible")

    if reads and any(s.get("kind") == "ret" for s in steps):
        target = reads[0]["target"]
        return ("DIRECT_GLOBAL_RETURN", "low",
                f"RIP-relative global load @ 0x{target:X} present before ret, but pattern is not the exact mov;ret form")

    return ("UNRESOLVED", "none", None)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_result(game: Path, max_bytes: int, max_insns: int,
                 game_version: str = "unknown") -> dict[str, Any]:
    pe = PeImage(game)
    export_dir = parse_export(pe, EXPORT_NAME)
    matches = export_dir.get("matches", [])
    export_exists = bool(matches)
    export_name = None
    export_rva = None
    entry_classification = None
    analysis: dict[str, Any] | None = None

    result: dict[str, Any] = {
        "schema": "il2cpp_get_api_table_resolver/1",
        "tool": "tools/reverse/scripts/resolve_il2cpp_get_api_table.py",
        "game_version": game_version,
        "game_assembly": str(game),
        "game_assembly_sha256": pe.sha256(),
        "pe": {
            "machine": pe.machine,
            "magic": pe.magic,
            "image_base": pe.image_base,
            "size_of_image": pe.size_of_image,
            "sections": [
                {
                    "name": s.name,
                    "rva": s.rva,
                    "vsize": s.vsize,
                    "raw_size": s.raw_size,
                    "characteristics": s.characteristics,
                    "is_executable": s.is_executable,
                }
                for s in pe.sections
            ],
        },
        "export_exists": export_exists,
        "export_name": None,
        "ordinal": None,
        "export_rva": None,
        "export_section": None,
        "export_section_is_executable": None,
        "export_is_forwarder": None,
        "entry_bytes": None,
        "minimal_cfg": None,
        "classification": None,
        "confidence": None,
        "candidate_global_rvas": None,
        "candidate_return_source": None,
        "direct_calls": None,
        "rip_relative_reads": None,
        "rip_relative_writes": None,
        "rip_relative_leas": None,
        "pointer_chain": [],
        "runtime_read_result": {
            "performed": False,
            "reason": (
                "static analysis produced no candidate global RVA / pointer chain; "
                "per protocol no external ReadProcessMemory validation was performed"
            ),
        },
        "root_classification": None,
        "root_pointer": None,
        "final_status": None,
    }

    if not export_exists:
        result["final_status"] = "REAL_API_ROOT = EXPORT_NOT_FOUND"
        result["entry_classification"] = "EXPORT_NOT_FOUND"
        result["root_classification"] = "EXPORT_NOT_FOUND"
        return result

    # There must be exactly one matching name; if duplicates exist report all.
    chosen = matches[0]
    result["export_name"] = chosen["name"]
    result["ordinal"] = chosen["ordinal"]
    result["export_rva"] = chosen["rva"]
    result["export_section"] = chosen["section"]
    result["export_section_is_executable"] = chosen["section_is_executable"]
    result["export_is_forwarder"] = chosen["forwarder"]
    result["entry_bytes"] = chosen["entry_bytes_hex"]
    result["export_match_count"] = len(matches)

    analysis = analyze_entry(pe, chosen["rva"], max_bytes=max_bytes, max_insns=max_insns)
    result["minimal_cfg"] = analysis
    result["direct_calls"] = analysis.get("direct_calls", [])
    result["rip_relative_reads"] = analysis.get("rip_relative_reads", [])
    result["rip_relative_writes"] = analysis.get("rip_relative_writes", [])
    result["rip_relative_leas"] = analysis.get("rip_relative_leas", [])
    result["candidate_global_rvas"] = analysis.get("candidate_global_rvas", [])

    classification, confidence, return_source = classify_entry(analysis, chosen)
    entry_classification = classification
    result["classification"] = classification
    result["entry_classification"] = classification
    result["confidence"] = confidence
    result["candidate_return_source"] = return_source
    result["root_classification"] = classification
    result["classification_evidence"] = [
        f"export is named and not a forwarder: {chosen['name']} ordinal={chosen['ordinal']}",
        f"export RVA 0x{chosen['rva']:X} is in {chosen['section']} "
        f"(executable={chosen['section_is_executable']})",
        f"entry linear sweep decoded {analysis.get('instruction_count', 0)} instruction(s), "
        f"stop_reason={analysis.get('stop_reason')}",
        f"direct_calls={len(analysis.get('direct_calls', []))}, "
        f"rip_relative_reads={len(analysis.get('rip_relative_reads', []))}, "
        f"rip_relative_leas={len(analysis.get('rip_relative_leas', []))}",
        f"classification={classification} confidence={confidence}",
    ]

    if not chosen["forwarder"] and not chosen["section_is_executable"]:
        result["final_status"] = "REAL_API_ROOT = STATIC_TARGET_UNRESOLVED"
    elif classification in ("DIRECT_GLOBAL_RETURN", "DIRECT_ADDRESS_RETURN"):
        result["final_status"] = "REAL_API_ROOT = STATIC_ROOT_RECOVERED"
    elif classification == "INITIALIZER_THEN_GLOBAL":
        result["final_status"] = "REAL_API_ROOT = STATIC_ROOT_RECOVERED"
    elif classification == "WRAPPER_TO_TARGET":
        result["final_status"] = "REAL_API_ROOT = STATIC_TARGET_UNRESOLVED"
    elif classification == "DYNAMIC_DISPATCH":
        result["final_status"] = "REAL_API_ROOT = DYNAMIC_DISPATCH_UNRESOLVED"
    else:
        result["final_status"] = "REAL_API_ROOT = STATIC_TARGET_UNRESOLVED"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve real il2cpp_get_api_table export path")
    parser.add_argument("--game", required=True, type=Path, help="GameAssembly.dll")
    parser.add_argument("--game-version", default="unknown", help="logical game version label, e.g. 4.4.54")
    parser.add_argument("--json", type=Path, default=None, help="machine-readable JSON output")
    parser.add_argument("--max-bytes", type=int, default=4096)
    parser.add_argument("--max-insns", type=int, default=512)
    args = parser.parse_args()

    result = build_result(args.game, args.max_bytes, args.max_insns, game_version=args.game_version)

    print(f"GameAssembly: {result['game_assembly']}")
    print(f"game_version: {result['game_version']}")
    print(f"sha256: {result['game_assembly_sha256']}")
    print(f"export_exists: {result['export_exists']}")
    print(f"export_name: {result['export_name']}")
    print(f"ordinal: {result['ordinal']}")
    print(f"export_rva: 0x{result['export_rva']:X}" if result["export_rva"] is not None else "export_rva: None")
    print(f"export_section: {result['export_section']} "
          f"(executable={result['export_section_is_executable']})")
    print(f"export_is_forwarder: {result['export_is_forwarder']}")
    print(f"entry_bytes: {result['entry_bytes']}")
    if result["minimal_cfg"]:
        cfg = result["minimal_cfg"]
        print(f"cfg: decoded={cfg['instruction_count']} stop={cfg['stop_reason']}")
        print(f"direct_calls: {json.dumps(cfg['direct_calls'], indent=2)}")
        print(f"rip_relative_reads: {json.dumps(cfg['rip_relative_reads'], indent=2)}")
        print(f"rip_relative_writes: {json.dumps(cfg['rip_relative_writes'], indent=2)}")
        print(f"rip_relative_leas: {json.dumps(cfg['rip_relative_leas'], indent=2)}")
        print(f"candidate_global_rvas: {[hex(v) for v in cfg['candidate_global_rvas']]}")
    print(f"classification: {result['classification']}")
    print(f"confidence: {result['confidence']}")
    print(f"candidate_return_source: {result['candidate_return_source']}")
    print(f"final_status: {result['final_status']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"json: {args.json}")


if __name__ == "__main__":
    main()
