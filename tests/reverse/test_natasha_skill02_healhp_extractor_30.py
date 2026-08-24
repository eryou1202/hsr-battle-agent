"""Tests for the bounded Natasha Skill02 HealHP extractor."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools" / "reverse" / "scripts" / "extract_natasha_skill02_healhp_30.py"
ARTIFACT = REPO / "data" / "raw" / "4.4.54" / "natasha_skill02_healhp_content_30.json"

SPEC = importlib.util.spec_from_file_location("extract_natasha_skill02_healhp_30", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestNatashaSkill02HealHPExtractor30(unittest.TestCase):
    def test_dynamic_float_formula_layout_and_signed_zigzag(self) -> None:
        # bitmap=1; three opcode bytes; zero qwords; one int32; operand=-7.
        reader = MODULE.Reader(bytes.fromhex("01 03 01 00 11 00 01 0D"), 0, 8)
        value = MODULE._dynamic_float(reader, "test")
        self.assertEqual(value["opcodes"], [1, 0, 17])
        self.assertEqual(value["qword_operands"], [])
        self.assertEqual(value["int32_operands"][0]["signed_value"], -7)
        self.assertEqual(reader.offset, 8)

    def test_target_config_named_alias_layout(self) -> None:
        raw = bytes([12, 1, 19]) + b"AbilityTargetEntity"
        reader = MODULE.Reader(raw, 0, len(raw))
        value = MODULE._target_config(reader, "test")
        self.assertEqual(value["discriminator"], 12)
        self.assertEqual(value["field_presence_bitmap"], 1)
        self.assertEqual(value["name"], "AbilityTargetEntity")
        self.assertEqual(reader.offset, len(raw))

    def test_committed_artifact_has_exact_heal_boundary_and_operands(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(
            artifact["status"],
            "REAL_SKILL_HEALHP_NODE_AND_FORMULA4_CONFIG_CONFIRMED",
        )
        heal = artifact["recovered_subtree"]["success_tasks"][1]
        self.assertEqual((heal["start"], heal["end_exclusive"]), ("0xBC9A4B", "0xBC9A7E"))
        self.assertEqual(heal["discriminator"], 1481)
        self.assertEqual(heal["formula_type"]["value"], 4)
        self.assertEqual(
            heal["heal_percentage"]["int32_operands"][0]["signed_value"],
            -1544075911,
        )
        self.assertEqual(
            heal["modify_value"]["int32_operands"][0]["signed_value"],
            -203632277,
        )
        boundary = artifact["recovered_subtree"]["boundary_proof"]
        self.assertEqual(boundary["next_outer_task_start"], "0xBC9A7E")
        self.assertEqual(boundary["next_outer_task_discriminator"], 1960)


if __name__ == "__main__":
    unittest.main()
