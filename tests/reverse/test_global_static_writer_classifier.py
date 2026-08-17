# -*- coding: utf-8 -*-
"""Focused synthetic tests for the global/static writer classifier."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "tools" / "reverse" / "scripts"
VENDOR = REPO / "tools" / "reverse" / "vendor" / "capstone"
sys.path.insert(0, str(SCRIPTS))
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from global_static_writer_classifier import (  # noqa: E402
    MethodIndex,
    build_report,
    enrich_rip_refs,
    scan_rip_refs,
)
from resolve_il2cpp_get_api_table import PeSection  # noqa: E402

IMAGE_BASE = 0x140000000
TEXT_RVA = 0x1000
TEXT_OFF = 0x200
TEXT_SIZE = 0x100
DATA_RVA = 0x5000
DATA_OFF = 0x300
DATA_SIZE = 0x100

TEXT_CHARS = 0x60000020  # code | execute | read
DATA_CHARS = 0xC0000040  # read | write


def make_sections() -> list[PeSection]:
    return [
        PeSection(".text", TEXT_RVA, TEXT_SIZE, TEXT_SIZE, TEXT_OFF, TEXT_CHARS),
        PeSection(".data", DATA_RVA, DATA_SIZE, DATA_SIZE, DATA_OFF, DATA_CHARS),
    ]


def rip_disp(target_rva: int, insn_rva: int, insn_len: int) -> int:
    return (IMAGE_BASE + target_rva) - (IMAGE_BASE + insn_rva + insn_len)


def make_raw() -> bytes:
    raw = bytearray(0x400)

    # mov rax, qword ptr [rip + target]  (read)
    insn_rva = TEXT_RVA + 0x00
    raw[TEXT_OFF + 0x00:TEXT_OFF + 0x07] = bytes.fromhex("488b05") + struct.pack(
        "<i", rip_disp(DATA_RVA, insn_rva, 7))

    # mov qword ptr [rip + target], rax  (write)
    insn_rva = TEXT_RVA + 0x10
    raw[TEXT_OFF + 0x10:TEXT_OFF + 0x17] = bytes.fromhex("488905") + struct.pack(
        "<i", rip_disp(DATA_RVA, insn_rva, 7))

    # mov rax, qword ptr [rip + unrelated]  (must be ignored)
    insn_rva = TEXT_RVA + 0x20
    raw[TEXT_OFF + 0x20:TEXT_OFF + 0x27] = bytes.fromhex("488b05") + struct.pack(
        "<i", rip_disp(DATA_RVA + 0x100, insn_rva, 7))

    # lea rax, [rip + target]  (address reference)
    insn_rva = TEXT_RVA + 0x30
    raw[TEXT_OFF + 0x30:TEXT_OFF + 0x37] = bytes.fromhex("488d05") + struct.pack(
        "<i", rip_disp(DATA_RVA, insn_rva, 7))

    return bytes(raw)


class GlobalStaticWriterClassifierTests(unittest.TestCase):
    def test_direct_rip_relative_read_write_and_unrelated_ignored(self):
        raw = make_raw()
        sections = make_sections()
        refs = scan_rip_refs(raw, sections, IMAGE_BASE, DATA_RVA)
        refs = enrich_rip_refs(raw, sections, IMAGE_BASE, refs)

        self.assertEqual(len(refs), 3)
        accesses = sorted(r["access"] for r in refs)
        self.assertEqual(accesses, ["address", "read", "write"])
        self.assertTrue(all(int(r["instruction_rva"], 0) != TEXT_RVA + 0x20
                            for r in refs))

    def test_enclosing_method_resolution(self):
        method_index = MethodIndex([0x1000, 0x2000], [10, 20])
        self.assertEqual(method_index.for_site(0x1005), {
            "method_start_rva": 0x1000,
            "method_index": 10,
            "offset_from_start": 5,
        })
        self.assertEqual(method_index.for_site(0x1FFF)["method_index"], 10)
        self.assertEqual(method_index.for_site(0x2000)["method_index"], 20)
        self.assertIsNone(method_index.for_site(0x0FFF))

    def test_build_report_decorates_read_and_write_methods(self):
        raw = make_raw()
        sections = make_sections()
        method_index = MethodIndex([TEXT_RVA], [123])
        methods_meta = {
            123: {
                "method_index": 123,
                "declaring_type_index": 7,
                "name": "ModifyProperty",
                "native_rva": TEXT_RVA,
                "mapping_kind": "DIRECT_NATIVE",
            }
        }
        types_meta = {
            7: {
                "type_index": 7,
                "full_name": "RPG.GameCore.TurnBasedAbilityComponent",
            }
        }
        report = build_report(
            game_path="synthetic.dll",
            image_base=IMAGE_BASE,
            raw=raw,
            sections=sections,
            data_rva=DATA_RVA,
            method_index=method_index,
            methods_meta=methods_meta,
            types_meta=types_meta,
        )
        self.assertEqual(report["counts"]["read_xrefs"], 1)
        self.assertEqual(report["counts"]["write_xrefs"], 1)
        self.assertEqual(report["counts"]["address_xrefs"], 1)
        self.assertEqual(report["read_xrefs"][0]["enclosing_method"]["name"],
                         "ModifyProperty")
        self.assertEqual(report["write_xrefs"][0]["enclosing_method"]["name"],
                         "ModifyProperty")
        self.assertIn("DIRECT_RUNTIME_WRITTEN_GLOBAL", report["classification"])

    def test_no_writer_result_is_unknown_with_read_consumers(self):
        raw = bytearray(make_raw())
        # Remove the direct write at +0x10 by turning it into an unrelated read.
        insn_rva = TEXT_RVA + 0x10
        raw[TEXT_OFF + 0x10:TEXT_OFF + 0x17] = bytes.fromhex("488b05") + struct.pack(
            "<i", rip_disp(DATA_RVA + 0x200, insn_rva, 7))
        raw = bytes(raw)

        sections = make_sections()
        report = build_report(
            game_path="synthetic.dll",
            image_base=IMAGE_BASE,
            raw=raw,
            sections=sections,
            data_rva=DATA_RVA,
            method_index=None,
            methods_meta={},
            types_meta={},
        )
        self.assertEqual(report["counts"]["write_xrefs"], 0)
        self.assertEqual(report["counts"]["indirect_writer_candidates"], 0)
        self.assertIn("UNKNOWN", report["classification"])
        self.assertTrue(any(i["kind"] == "read_consumer"
                            for i in report["next_inspection"]))

    def test_stable_json_ordering(self):
        raw = make_raw()
        sections = make_sections()
        report = build_report(
            game_path="synthetic.dll",
            image_base=IMAGE_BASE,
            raw=raw,
            sections=sections,
            data_rva=DATA_RVA,
            method_index=None,
            methods_meta={},
            types_meta={},
        )
        first = json.dumps(report, sort_keys=True, indent=2)
        second = json.dumps(report, sort_keys=True, indent=2)
        self.assertEqual(first, second)
        # sort_keys=True means top-level keys are lexicographically ordered in
        # the serialized form.
        loaded = json.loads(first)
        self.assertEqual(list(loaded.keys()), sorted(loaded.keys()))


if __name__ == "__main__":
    unittest.main()
