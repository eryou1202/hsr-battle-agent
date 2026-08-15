# test_find_il2cpp_api_table.py
#
# find_il2cpp_api_table.py 的集成验证。
#
# 安全边界：测试只在本地文件上 LoadLibrary + 只读扫描；不调用游戏逻辑、
# 不注入、不修改文件。
#
# EXPECTED_TABLE_RVA 仅作为验证基准，不是 locator 的输入。
# 若客户端不存在，测试自动跳过。

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS_REVERSE_SCRIPTS = REPO / "tools" / "reverse" / "scripts"
sys.path.insert(0, str(TOOLS_REVERSE_SCRIPTS))

import find_il2cpp_api_table as locator_mod  # noqa: E402

GAME_DIRS = [
    Path(os.environ.get("HSR_GAME_DIR", "")),
    Path(r"D:\StarRail_4.4.53"),
]
UNITY = next((p / "UnityPlayer.dll" for p in GAME_DIRS if (p / "UnityPlayer.dll").is_file()), None)

# 4.4.54 已知正确位置（验证基准；绝不允许出现在 locator 源码中）
EXPECTED_TABLE_RVA = 0x1A36480


@unittest.skipUnless(UNITY is not None, "UnityPlayer.dll not found (set HSR_GAME_DIR)")
class TestApiTableLocatorIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.locator = locator_mod.Locator(UNITY)
        cls.result = cls.locator.locate()

    def test_locator_source_has_no_hardcoded_table_offset(self):
        src = (TOOLS_REVERSE_SCRIPTS / "find_il2cpp_api_table.py").read_text(encoding="utf-8")
        self.assertNotIn("1A36480", src.upper(), "locator source must not contain the validation address")
        self.assertNotIn("if version ==", src, "locator must not branch on game version")

    def test_best_candidate_is_expected_table(self):
        self.assertIsNotNone(self.result["best_candidate"])
        best = self.result["best_candidate"]
        self.assertEqual(int(best["rva"], 16), EXPECTED_TABLE_RVA)
        self.assertEqual(best["section"], ".rdata")

    def test_unique_high_confidence(self):
        self.assertEqual(self.result["confidence"], "high")
        self.assertIsNotNone(self.result["runner_up"])
        self.assertNotEqual(
            int(self.result["runner_up"]["rva"], 16), EXPECTED_TABLE_RVA
        )
        self.assertGreater(self.result["score"], self.result["runner_up"]["score"] + 1.0)

    def test_required_output_fields_and_values(self):
        self.assertEqual(self.result["known_slots_matched"], len(locator_mod.KNOWN_SLOTS))
        self.assertEqual(self.result["wrapper_matches"], 240)
        self.assertEqual(self.result["descriptor_matches"], 237)
        self.assertEqual(self.result["failed_constraints"], [])
        for key in ("best_candidate", "runner_up", "score", "known_slots_matched",
                    "wrapper_matches", "descriptor_matches", "failed_constraints",
                    "confidence"):
            self.assertIn(key, self.result)

    def test_known_slot_descriptor_alignment(self):
        best = self.result["best_candidate"]
        # 双子对（63/65 与 10/12）的 descriptor 间隔 0x58 是结构指纹的一部分
        self.assertEqual(best["twin_relations"], 3)


if __name__ == "__main__":
    unittest.main()
