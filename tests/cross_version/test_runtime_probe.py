# test_runtime_probe.py
#
# Offline static tests for tools/runtime_probe (no game process, no injection).
# The dynamic self-tests live in tools/runtime_probe/tests/probe_self_tests.cpp
# and are executed by build.ps1 -RunTests.

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME_PROBE = REPO / "tools" / "runtime_probe"
SCRIPTS = RUNTIME_PROBE / "scripts"
sys.path.insert(0, str(SCRIPTS))

import jsonschema  # noqa: E402

import gen_locator_prior as prior_gen  # noqa: E402

LOCATOR_SOURCES = [
    RUNTIME_PROBE / "probe" / "api_locator.cpp",
    RUNTIME_PROBE / "probe" / "api_locator.h",
    RUNTIME_PROBE / "gen" / "locator_prior.h",
]
SCHEMA = RUNTIME_PROBE / "schema" / "health_check_result.schema.json"


def make_step(name, success):
    step = {"step": name, "success": success}
    if success:
        step["details"] = {}
    else:
        step["error_code"] = "TEST_FAILURE"
        step["error"] = "synthetic test failure"
    return step


def make_full_sample():
    return {
        "schema_version": 1,
        "tool": "tools/runtime_probe/probe/hsr_runtime_health_probe.dll",
        "game_version": "4.4.54",
        "version_source": "BinaryVersion.bytes",
        "build_string": "20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb",
        "generated_utc": "2026-08-14T12:00:00Z",
        "pid": 12345,
        "target_pid": 12345,
        "process_name": "StarRail.exe",
        "process_path": r"D:\StarRail_4.4.53\StarRail.exe",
        "steps": [make_step(name, True) for name in [
            "module_discovery",
            "api_table_locator",
            "domain_get",
            "domain_get_assemblies",
            "assembly_get_image",
            "image_name",
            "image_get_class_count",
            "image_get_classes",
            "class_names",
        ]],
        "failure_step": None,
        "error": None,
        "hd2": True,
        "final_status": "PASS",
    }


class TestRuntimeProbeStatic(unittest.TestCase):
    def test_locator_prior_header_in_sync_with_python_locator(self):
        header = RUNTIME_PROBE / "gen" / "locator_prior.h"
        self.assertTrue(header.is_file(), "locator_prior.h must be generated")
        self.assertEqual(
            prior_gen.generate(),
            header.read_text(encoding="utf-8"),
            "regenerate with: python tools/runtime_probe/scripts/gen_locator_prior.py",
        )

    def test_locator_sources_have_no_hardcoded_table_or_version(self):
        for path in LOCATOR_SOURCES:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    "1A36480", source.upper(),
                    f"{path.name} must not contain the validation table address",
                )
                self.assertNotIn(
                    "4.4.54", source,
                    f"{path.name} must not branch on game version",
                )
                self.assertNotIn(
                    "if version ==", source,
                    f"{path.name} must not contain a version branch",
                )

    def test_probe_config_marks_expected_rva_as_verification_only(self):
        config = (RUNTIME_PROBE / "probe_config.ini").read_text(encoding="utf-8")
        self.assertIn("expected_table_rva=0x1A36480", config)
        self.assertIn("COMPARISON-ONLY", config.upper())
        self.assertIn("expect_rva_enabled=1", config)

    def test_json_schema_accepts_full_pass_output(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(make_full_sample(), schema)

    def test_json_schema_accepts_failure_stop_output(self):
        sample = make_full_sample()
        sample["steps"] = [
            make_step("module_discovery", True),
            make_step("api_table_locator", True),
            make_step("domain_get", False),
        ]
        sample["failure_step"] = "domain_get"
        sample["error"] = "il2cpp_domain_get returned null"
        sample["hd2"] = False
        sample["final_status"] = "FAIL_AT_DOMAIN_GET"
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(sample, schema)

    def test_json_schema_rejects_unknown_step_name(self):
        sample = make_full_sample()
        sample["steps"][0]["step"] = "battle_instance"
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(sample, schema)

    def test_build_script_and_loader_exist(self):
        self.assertTrue((RUNTIME_PROBE / "build.ps1").is_file())
        self.assertTrue((RUNTIME_PROBE / "loader" / "load_probe.cpp").is_file())
        self.assertTrue((RUNTIME_PROBE / "probe" / "dll_main.cpp").is_file())


if __name__ == "__main__":
    unittest.main()
