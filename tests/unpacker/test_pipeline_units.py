# -*- coding: utf-8 -*-
"""Small, stable unit tests for the unpack/reverse pipeline v1.

These tests cover stage parsers without requiring the multi-GB game assets.
The full 4.4.54 smoke run is documented in docs/unpack/README.md.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.unpack_pipeline import PIPELINE_SCHEMA_VERSION  # noqa: E402
from tools.unpack_pipeline.common import Anomaly, StageResult  # noqa: E402
from tools.unpack_pipeline.design_structural import _directory_rows, _record_prefixes  # noqa: E402
from tools.unpack_pipeline.diff import _bridge_identity, _registry_runtime_sequence, compare_normalized  # noqa: E402
from tools.unpack_pipeline.known_invariants import KNOWN_INVARIANTS  # noqa: E402
from tools.unpack_pipeline.mhy_core import (  # noqa: E402
    ID_HASH_ADD,
    ID_HASH_MUL,
    ID_ROLL,
    M32,
    resolve_identifier,
    signed32,
)
from tools.unpack_pipeline.version_discovery import read_binary_version  # noqa: E402


def _uleb(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _write_record_file(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "test", "count": len(records), "records": records}
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestVersionDiscovery(unittest.TestCase):
    def test_version_never_inferred_from_directory_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "StarRail_4.4.53"  # deliberately wrong label
            asset_dir = root / "StarRail_Data" / "StreamingAssets"
            asset_dir.mkdir(parents=True)
            (asset_dir / "BinaryVersion.bytes").write_bytes(
                b"\x00\x08BetaLive\x00\x0020260731-0529-BetaLive-15953205-"
                b"OSBETAWin4.4.54-OSCb\x00")
            info = read_binary_version(root)
            self.assertEqual(info["game_version"], "4.4.54")
            self.assertNotEqual(info["game_version"], root.name.rsplit("_", 1)[-1])
            self.assertIn("BinaryVersion.bytes", info["version_source_rel"])

    def test_missing_binary_version_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                read_binary_version(Path(tmp))


class TestMhyPrimitives(unittest.TestCase):
    def test_signed32(self):
        self.assertEqual(signed32(0xFFFFFFFF), -1)
        self.assertEqual(signed32(0x7FFFFFFF), 0x7FFFFFFF)
        self.assertEqual(signed32(0x80000000), -0x80000000)

    def test_identifier_resolver_roundtrip(self):
        # Non-negative key: offset 0, length 9.
        length = 9
        key = (length << 25) & M32
        seed = ID_HASH_ADD
        region = bytearray(16)
        plain = b"hello-123"
        padded = plain + b"\x00" * (16 - len(plain))
        for qword_off in range(0, 16, 8):
            cipher = int.from_bytes(padded[qword_off:qword_off + 8], "little") ^ seed
            region[qword_off:qword_off + 8] = cipher.to_bytes(8, "little")
            seed = (seed + ID_ROLL) & ((1 << 64) - 1)
        self.assertEqual(resolve_identifier(key, bytes(region)), plain)

    def test_identifier_sentinel_is_empty(self):
        self.assertEqual(resolve_identifier(0xFFFFFFFF, b"anything"), b"")


class TestDesignStructuralPreservesUnknowns(unittest.TestCase):
    def test_record_prefix_uses_neutral_names(self):
        name = "Avatar_BlackSwan_00_Skill01_Phase01"
        raw_name = name.encode("ascii")
        archive_data = _uleb(0x1E) + _uleb(0x13) + bytes([len(raw_name)]) + raw_name \
            + b"\x01" + _uleb(16) + b"\x00" * 32
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "a.bytes"
            archive.write_bytes(archive_data)
            rows = [{"record_start_hex": "0x0", "name": name}]
            prefixes = _record_prefixes(archive, rows, Path(tmp) / "records")
            self.assertEqual(len(prefixes), 1)
            row = prefixes[0]
            self.assertEqual(row["field_0_uleb"], 0x1E)
            self.assertEqual(row["field_1_uleb"], 0x13)
            self.assertEqual(row["structural_code"], 16)
            self.assertEqual(row["structure_status"], "STRUCTURAL_VALUE_CONFIRMED")
            self.assertEqual(row["semantic_status"], "UNKNOWN")

    def test_adaptive_directory_solves_base(self):
        name = "Avatar_BlackSwan_00_Skill01_Phase01"
        raw_name = name.encode("ascii")
        # Directory entry at 0: len+name, 0x01, zigzag(7) -> 0x0E, tail 0x07.
        directory = bytes([len(raw_name)]) + raw_name + b"\x01\x0e\x07"
        # Record start at 7; name occurrence at 9 (name_delta=2).  The record
        # occurrence is deliberately not followed by 0x01 so it is not also
        # classified as a directory entry.
        record = b"\xAA\xBB" + bytes([len(raw_name)]) + raw_name + b"\x00\x10" + b"\x00" * 16
        archive_data = directory + record
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "a.bytes"
            archive.write_bytes(archive_data)
            rows, stats = _directory_rows(archive, "9.9.9")
            self.assertEqual(stats["status"], "OK")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["record_start_hex"], "0x27")
            self.assertEqual(rows[0]["game_version"], "9.9.9")


class TestDiffSemanticAlignment(unittest.TestCase):
    def _make_version(self, tmp: Path, label: str) -> Path:
        version = tmp / label
        version.mkdir()
        _write_record_file(version / "types.json", [
            {"type_index": 0, "namespace": "A", "name": "T", "full_name": "A.T"},
            {"type_index": 1, "namespace": "A", "name": "Old", "full_name": "A.Old"},
        ])
        _write_record_file(version / "methods.json", [
            {"method_index": 0, "declaring_type_index": 0, "name": "M", "parameter_count": 1,
             "return_type_reference": 5, "native_rva": 0x1000},
        ])
        _write_record_file(version / "fields.json", [
            {"field_index": 0, "declaring_type_index": 0, "name": "F", "type_reference": 7},
        ])
        (version / "design_runtime_registry.json").write_text(json.dumps({
            "domains": [{
                "domain": "ability_config", "status": "PASS",
                "mappings": [{"serialized_discriminator": 0, "runtime_type": "A.T",
                              "parser_method_name": "M"}],
            }],
        }), encoding="utf-8")
        return version

    def test_type_method_field_and_bridge_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = self._make_version(root, "old")
            new = self._make_version(root, "new")
            new_types = json.loads((new / "types.json").read_text(encoding="utf-8"))["records"]
            new_types.append({"type_index": 2, "namespace": "A", "name": "New",
                              "full_name": "A.New"})
            _write_record_file(new / "types.json", new_types)
            new_methods = json.loads((new / "methods.json").read_text(encoding="utf-8"))["records"]
            new_methods[0]["native_rva"] = 0x2000
            _write_record_file(new / "methods.json", new_methods)
            diff = compare_normalized(old, new)
            self.assertIn("A.New", diff["type_additions_removals"]["added"])
            self.assertEqual(diff["type_additions_removals"]["removed"], [])
            self.assertEqual(diff["native_rva_changes"]["changed"], 1)
            self.assertEqual(diff["design_runtime_bridge_changes"]["common_unchanged"], 1)

    def test_bridge_identity_accepts_discriminator_zero(self):
        identity = _bridge_identity([{
            "domain": "x", "status": "PASS",
            "mappings": [{"serialized_discriminator": 0, "runtime_type": "A.T"}],
        }])
        self.assertEqual(identity["x/0"]["runtime_type"], "A.T")

    def test_registry_sequence_uses_concrete_runtime_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge.json"
            path.write_text(json.dumps({"mappings": [
                {"discriminator": 1, "runtime_type_name": "MKIOEPLIEIH",
                 "concrete_runtime_type_name": "RPG.GameCore.AdvByCheckGameMode"},
                {"discriminator": 2, "runtime_type_name": None,
                 "concrete_runtime_type_name": None},
            ]}), encoding="utf-8")
            self.assertEqual(_registry_runtime_sequence(path),
                             ["RPG.GameCore.AdvByCheckGameMode"])


class TestExpectedInvariants(unittest.TestCase):
    def test_4_4_54_invariants(self):
        self.assertEqual(KNOWN_INVARIANTS["4.4.54"], {
            "type_count": 80880,
            "method_count": 732328,
            "field_count": 555259,
            "method_code_non_null": 700198,
            "method_code_null": 32130,
        })

    def test_4_4_0_invariants(self):
        self.assertEqual(KNOWN_INVARIANTS["4.4.0"], {
            "type_count": 76921,
            "method_count": 703008,
            "field_count": 526693,
            "method_code_non_null": 676842,
            "method_code_null": 26166,
        })

    def test_archived_4_4_0_raw_matches_invariants(self):
        raw_dir = REPO / "data" / "raw" / "4.4.0"
        if not raw_dir.is_dir():
            self.skipTest("archived 4.4.0 raw evidence not present")
        type_map = json.loads((raw_dir / "il2cpp" / "mhy_0x84_record_access_map_4.4.0.json")
                              .read_text(encoding="utf-8"))
        method_map = json.loads((raw_dir / "il2cpp" / "mhy_method_definition_access_map_4.4.0.json")
                                .read_text(encoding="utf-8"))
        field_map = json.loads((raw_dir / "il2cpp" / "mhy_field_definition_access_map_4.4.0.json")
                               .read_text(encoding="utf-8"))
        code = json.loads((raw_dir / "il2cpp" / "method_code_registry_proof_4.4.0.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(type_map["record_table"]["capacity_to_next_table"],
                         KNOWN_INVARIANTS["4.4.0"]["type_count"])
        self.assertEqual(method_map["method_table"]["record_count"],
                         KNOWN_INVARIANTS["4.4.0"]["method_count"])
        self.assertEqual(field_map["field_table"]["record_count"],
                         KNOWN_INVARIANTS["4.4.0"]["field_count"])
        self.assertEqual(code["statistics"]["direct_native_slots"],
                         KNOWN_INVARIANTS["4.4.0"]["method_code_non_null"])


class TestEntrypointAndReporting(unittest.TestCase):
    def test_powershell_entrypoint_uses_resolver_and_module(self):
        script = (REPO / "scripts" / "unpack_version.ps1").read_text(encoding="utf-8")
        self.assertIn("resolve_python.ps1", script)
        self.assertIn('"-m"', script)
        self.assertIn("tools.unpack_pipeline.run_pipeline", script)
        self.assertNotIn("where.exe", script.lower())
        self.assertNotIn("py.exe", script.lower())

    def test_stage_and_anomaly_serialization(self):
        stage = StageResult("TYPE_REGISTRY", "PASS", counts={"types": 3})
        anomaly = Anomaly("TYPE_REGISTRY", "count > 0", "count == 0", "WARN", "inspect")
        payload = stage.as_dict()
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(anomaly.as_dict()["severity"], "WARN")
        self.assertEqual(PIPELINE_SCHEMA_VERSION, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
