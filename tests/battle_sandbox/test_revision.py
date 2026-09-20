# -*- coding: utf-8 -*-
"""F02-005 tests: StateRevision value object.

Acceptance criteria: round trip and stale comparison.  The suite also proves the
counter is monotonic, that no wall-clock or object-address input exists, and
that cross-snapshot comparison is refused rather than guessed.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_sandbox.revision import (  # noqa: E402
    REVISION_SCHEMA,
    StateRevision,
    StateRevisionError,
)


def rev(counter=0, snapshot_id="snap-1", lineage="default"):
    return StateRevision(counter=counter, snapshot_id=snapshot_id, lineage=lineage)


class TestConstruction(unittest.TestCase):
    def test_initial_is_the_zero_revision(self):
        initial = StateRevision.initial("snap-1")
        self.assertEqual(initial.counter, 0)
        self.assertEqual(initial.snapshot_id, "snap-1")
        self.assertEqual(initial.lineage, "default")

    def test_counter_must_be_a_non_negative_int(self):
        for counter in (-1, 1.0, "0", None, True, False):
            with self.subTest(counter=repr(counter)):
                with self.assertRaises(StateRevisionError):
                    rev(counter=counter)

    def test_snapshot_id_must_be_non_empty(self):
        for snapshot_id in ("", None, 1, []):
            with self.subTest(snapshot_id=repr(snapshot_id)):
                with self.assertRaises(StateRevisionError):
                    rev(snapshot_id=snapshot_id)

    def test_lineage_must_be_non_empty(self):
        for lineage in ("", None, 1):
            with self.subTest(lineage=repr(lineage)):
                with self.assertRaises(StateRevisionError):
                    rev(lineage=lineage)

    def test_revision_is_immutable(self):
        revision = rev()
        with self.assertRaises(Exception):
            revision.counter = 9

    def test_no_truthiness(self):
        for counter in (0, 1):
            with self.subTest(counter=counter):
                with self.assertRaises(StateRevisionError):
                    bool(rev(counter=counter))


class TestMonotonicAdvancement(unittest.TestCase):
    def test_advance_moves_forward_by_exactly_one(self):
        self.assertEqual(rev(counter=4).advance(contract="c").counter, 5)

    def test_repeated_advance_is_strictly_monotonic(self):
        revision = StateRevision.initial("snap-1")
        seen = [revision.counter]
        for _ in range(10):
            revision = revision.advance(contract="step")
            seen.append(revision.counter)
        self.assertEqual(seen, list(range(11)))
        self.assertEqual(len(set(seen)), len(seen))

    def test_advance_requires_a_named_contract(self):
        for contract in ("", None, 1):
            with self.subTest(contract=repr(contract)):
                with self.assertRaises(StateRevisionError):
                    rev().advance(contract=contract)

    def test_advance_by_requires_positive_steps_and_a_contract(self):
        for steps in (0, -1, 1.0, "1", None, True):
            with self.subTest(steps=repr(steps)):
                with self.assertRaises(StateRevisionError):
                    rev().advance_by(steps, contract="c")
        with self.assertRaises(StateRevisionError):
            rev().advance_by(1, contract="")
        self.assertEqual(rev(counter=2).advance_by(3, contract="c").counter, 5)

    def test_advance_may_issue_a_new_snapshot_token(self):
        advanced = rev(counter=1).advance(contract="c", snapshot_id="snap-2")
        self.assertEqual(advanced.snapshot_id, "snap-2")
        self.assertEqual(advanced.counter, 2)

    def test_advance_preserves_lineage(self):
        self.assertEqual(rev(lineage="L").advance(contract="c").lineage, "L")

    def test_advance_never_goes_backwards(self):
        revision = rev(counter=7)
        for _ in range(5):
            newer = revision.advance(contract="c")
            self.assertGreater(newer.counter, revision.counter)
            revision = newer


class TestNoClockOrAddressInput(unittest.TestCase):
    def test_wall_clock_construction_is_refused(self):
        with self.assertRaises(StateRevisionError):
            StateRevision.from_wall_clock()
        with self.assertRaises(StateRevisionError):
            StateRevision.from_wall_clock(1234567890.0)

    def test_object_address_construction_is_refused(self):
        with self.assertRaises(StateRevisionError):
            StateRevision.from_object_address(object())
        with self.assertRaises(StateRevisionError):
            StateRevision.from_object_address()

    def test_module_imports_no_clock_and_no_object_address(self):
        # AST-based so that prose in docstrings can never trip the scan.
        import ast

        source = (
            REPO / "src" / "hsr_battle_agent" / "battle_sandbox" / "revision.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")

        forbidden_modules = ("time", "datetime", "uuid", "os", "secrets")
        for module in forbidden_modules:
            with self.subTest(module=module):
                self.assertNotIn(module, imported)

        called: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                value = func.value
                if isinstance(value, ast.Name):
                    called.add(f"{value.id}.{func.attr}")
                else:
                    called.add(func.attr)

        for forbidden in (
            "id",
            "time.time",
            "time.monotonic",
            "perf_counter",
            "monotonic",
            "datetime.now",
            "now",
            "uuid4",
            "getpid",
        ):
            with self.subTest(called=forbidden):
                self.assertNotIn(forbidden, called)

    def test_module_may_import_only_pure_stdlib(self):
        import ast

        source = (
            REPO / "src" / "hsr_battle_agent" / "battle_sandbox" / "revision.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for module in imported:
            with self.subTest(module=module):
                self.assertTrue(
                    module in {"__future__", "copy", "dataclasses", "typing"},
                    f"unexpected import in revision.py: {module}",
                )

    def test_no_clock_helper_exists(self):
        for name in ("now", "from_now", "from_clock", "from_time",
                     "from_identity", "from_id"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(StateRevision, name))


class TestStaleComparison(unittest.TestCase):
    def test_compare_orders_by_counter(self):
        self.assertEqual(rev(counter=1).compare(rev(counter=2)), -1)
        self.assertEqual(rev(counter=2).compare(rev(counter=2)), 0)
        self.assertEqual(rev(counter=3).compare(rev(counter=2)), 1)

    def test_stale_detection(self):
        older = rev(counter=1)
        newer = rev(counter=5)
        self.assertTrue(older.is_stale_against(newer))
        self.assertFalse(newer.is_stale_against(older))
        self.assertFalse(older.is_stale_against(older))

    def test_supersedes_and_current(self):
        older = rev(counter=1)
        newer = rev(counter=2)
        self.assertTrue(newer.supersedes(older))
        self.assertFalse(older.supersedes(newer))
        self.assertTrue(older.is_current_for(rev(counter=1)))
        self.assertFalse(older.is_current_for(newer))

    def test_stale_comparison_across_snapshots_is_refused(self):
        with self.assertRaises(StateRevisionError):
            rev(counter=1, snapshot_id="a").compare(rev(counter=2, snapshot_id="b"))
        with self.assertRaises(StateRevisionError):
            rev(counter=1, snapshot_id="a").is_stale_against(
                rev(counter=2, snapshot_id="b")
            )

    def test_stale_comparison_across_lineages_is_refused(self):
        with self.assertRaises(StateRevisionError):
            rev(counter=1, lineage="a").compare(rev(counter=2, lineage="b"))

    def test_same_snapshot_helper(self):
        self.assertTrue(rev().same_snapshot(rev()))
        self.assertFalse(rev(snapshot_id="a").same_snapshot(rev(snapshot_id="b")))
        self.assertFalse(rev(lineage="a").same_snapshot(rev(lineage="b")))
        self.assertFalse(rev().same_snapshot("not-a-revision"))

    def test_compare_requires_a_revision(self):
        for value in (None, 1, "x", {}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(StateRevisionError):
                    rev().compare(value)

    def test_require_same_snapshot_requires_a_revision(self):
        with self.assertRaises(StateRevisionError):
            rev().require_same_snapshot("nope")


class TestSerialization(unittest.TestCase):
    def test_schema_constant(self):
        self.assertEqual(REVISION_SCHEMA, "state_revision/1")
        self.assertEqual(rev().to_dict()["schema"], REVISION_SCHEMA)

    def test_round_trip(self):
        revision = rev(counter=12, snapshot_id="snap-x", lineage="L")
        payload = revision.to_dict()
        restored = StateRevision.from_dict(payload)
        self.assertEqual(restored, revision)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.counter, 12)
        self.assertEqual(restored.snapshot_id, "snap-x")
        self.assertEqual(restored.lineage, "L")

    def test_json_round_trip(self):
        revision = rev(counter=3)
        text = json.dumps(revision.to_dict(), sort_keys=True)
        self.assertEqual(StateRevision.from_dict(json.loads(text)), revision)

    def test_default_lineage_is_recorded_explicitly(self):
        payload = rev().to_dict()
        self.assertEqual(payload["lineage"], "default")
        self.assertEqual(StateRevision.from_dict(payload).lineage, "default")

    def test_serialization_does_not_alias_the_model(self):
        revision = rev(counter=3)
        payload = revision.to_dict()
        payload["counter"] = 99
        self.assertEqual(revision.counter, 3)

    def test_malformed_documents_are_rejected(self):
        for broken in (
            None,
            [],
            "x",
            {},
            {"schema": "state_revision/2"},
            {"counter": 0},
            {"snapshot_id": "s"},
            {"counter": -1, "snapshot_id": "s"},
            {"counter": 0, "snapshot_id": ""},
        ):
            with self.subTest(broken=repr(broken)):
                with self.assertRaises(StateRevisionError):
                    StateRevision.from_dict(broken)

    def test_identity_label_is_stable(self):
        self.assertEqual(rev(counter=2, snapshot_id="s").identity(), "default:s@2")

    def test_no_execution_permission(self):
        with self.assertRaises(StateRevisionError):
            rev().execution_permitted()
        for name in ("executable", "is_executable", "can_execute", "as_bool"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(StateRevision, name))


if __name__ == "__main__":
    unittest.main()
