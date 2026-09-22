# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.descriptor_registry import (
    DescriptorFamily,
    DescriptorRegistration,
    DescriptorRegistry,
    DescriptorRegistryError,
)
from hsr_battle_agent.battle_ir.descriptors.base import DescriptorBatch
from hsr_battle_agent.battle_ir.resolution_ledger import ResolutionLedgerEntry, ResolutionState
from hsr_battle_agent.battle_sandbox.evidence_boundary import EvidenceBoundaryError, require_native_contract
from hsr_battle_agent.game_data.behavior_compiler import PRIMITIVE_BINDINGS
from hsr_battle_agent.game_data.behavior_descriptor_adapter import (
    BehaviorDescriptorStatus,
    adapt_mapping_entry,
    diagnose_binding_tables,
)
from hsr_battle_agent.game_data.content_behavior_mapping import OWNER_STATIC_FAMILY, STATIC_FAMILIES
from tests.battle_ir.test_descriptor_damage import _item as damage
from tests.battle_ir.test_descriptor_formation import _item as formation
from tests.battle_ir.test_descriptor_invocation import _item as invocation
from tests.battle_ir.test_descriptor_modifier import _item as modifier
from tests.battle_ir.test_descriptor_monster_ai import _item as monster_ai
from tests.battle_ir.test_descriptor_progression import _item as progression
from tests.battle_ir.test_descriptor_scenario import _item as scenario
from tests.battle_ir.test_descriptor_scheduler import _item as scheduler
from tests.battle_ir.test_descriptor_target import _intent as target


FACTORIES = {
    DescriptorFamily.INVOCATION: invocation,
    DescriptorFamily.MODIFIER: modifier,
    DescriptorFamily.FORMATION_TOPOLOGY: formation,
    DescriptorFamily.SCHEDULER: scheduler,
    DescriptorFamily.MONSTER_AI: monster_ai,
    DescriptorFamily.DAMAGE: damage,
    DescriptorFamily.TARGET_RETARGET: target,
    DescriptorFamily.PROGRESSION_LOADOUT: progression,
    DescriptorFamily.SCENARIO_MODE_TERMINAL: scenario,
}


def _registry():
    registrations = tuple(
        DescriptorRegistration(family, f"entity:{index}", factory())
        for index, (family, factory) in enumerate(FACTORIES.items())
    )
    return DescriptorRegistry(registrations)


def _entry(classification, candidates):
    return ResolutionLedgerEntry.from_mapping_record({
        "behavior_id": "behavior:1", "owner_kind": "Avatar",
        "static_link": {
            "classification": classification, "static_family": "Avatar",
            "candidate_entity_ids": candidates, "evidence": "published mapping",
            "mapping_method": "existing report",
        },
    })


class TestDescriptorRegistry(unittest.TestCase):
    def test_registry_resolves_all_nine_families(self):
        registry = _registry()
        self.assertEqual(registry.families_present(), tuple(DescriptorFamily))
        for index, family in enumerate(DescriptorFamily):
            with self.subTest(family=family):
                self.assertEqual(len(registry.resolve_static(family, f"entity:{index}")), 1)

    def test_family_type_mismatch_rejects(self):
        with self.assertRaises(DescriptorRegistryError):
            DescriptorRegistration(DescriptorFamily.DAMAGE, "entity:1", invocation())

    def test_batch_restored_family_descriptor_remains_registerable(self):
        restored = DescriptorBatch.from_dict(
            DescriptorBatch((invocation(),)).to_dict()
        ).occurrences[0]
        registration = DescriptorRegistration(
            DescriptorFamily.INVOCATION, "entity:restored", restored
        )
        registry = DescriptorRegistry((registration,))
        self.assertIs(
            type(registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:restored"
            )[0]),
            type(restored),
        )

    def test_registry_input_output_and_registration_surfaces_are_isolated(self):
        descriptor = invocation()
        registry = DescriptorRegistry((DescriptorRegistration(
            DescriptorFamily.INVOCATION, "entity:isolated", descriptor
        ),))
        before = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0].to_dict()

        descriptor.payload.require_present()["argument_keys"].append("input")
        resolved = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:isolated"
        )[0]
        resolved.fields["context"].require_present()["ability_target"].append(
            "output"
        )
        exposed = registry.registrations[0].descriptor
        exposed.payload.require_present()["argument_keys"].append("registration")

        self.assertEqual(
            registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:isolated"
            )[0].to_dict(),
            before,
        )

    def test_behavior_result_does_not_alias_registry_storage(self):
        registry = _registry()
        before = registry.resolve_static(
            DescriptorFamily.INVOCATION, "entity:0"
        )[0].to_dict()
        result = adapt_mapping_entry(
            _entry("EXACT_ID", ["entity:0"]),
            DescriptorFamily.INVOCATION,
            registry,
        )
        result.descriptors[0].payload.require_present()["argument_keys"].append(
            "adapter"
        )
        self.assertEqual(
            registry.resolve_static(
                DescriptorFamily.INVOCATION, "entity:0"
            )[0].to_dict(),
            before,
        )

    def test_exact_mapping_is_consumed_without_executability(self):
        registry = _registry()
        result = adapt_mapping_entry(
            _entry("EXACT_ID", ["entity:0"]), DescriptorFamily.INVOCATION, registry
        )
        self.assertIs(result.status, BehaviorDescriptorStatus.EXACT_DESCRIPTOR)
        self.assertEqual(len(result.descriptors), 1)
        with self.assertRaises(ValueError): result.execution_permitted()
        with self.assertRaises(EvidenceBoundaryError):
            require_native_contract(result.descriptors[0], role="registry descriptor")

    def test_missing_ambiguous_and_blocked_stay_ledgered(self):
        registry = _registry()
        cases = (
            (_entry("UNMAPPED", []), ResolutionState.MISSING, BehaviorDescriptorStatus.LEDGER_MISSING),
            (_entry("EXACT_ID", ["x", "y"]), ResolutionState.AMBIGUOUS, BehaviorDescriptorStatus.LEDGER_AMBIGUOUS),
            (_entry("OUT_OF_STATIC_FAMILY_SCOPE", []), ResolutionState.BLOCKED, BehaviorDescriptorStatus.LEDGER_BLOCKED),
        )
        for entry, state, expected in cases:
            with self.subTest(state=state):
                result = adapt_mapping_entry(entry, DescriptorFamily.DAMAGE, registry)
                self.assertIs(result.ledger_entry, entry)
                self.assertIs(result.ledger_entry.state, state)
                self.assertIs(result.status, expected)
                self.assertEqual(result.descriptors, ())

    def test_exact_mapping_without_registered_descriptor_fails_closed(self):
        result = adapt_mapping_entry(
            _entry("EXACT_ID", ["not-registered"]), DescriptorFamily.DAMAGE, _registry()
        )
        self.assertIs(result.status, BehaviorDescriptorStatus.EXACT_MAPPING_DESCRIPTOR_MISSING)
        self.assertEqual(result.descriptors, ())

    def test_binding_table_cross_check_is_diagnostic_only(self):
        registry = _registry()
        before = registry.registrations
        diagnostic = diagnose_binding_tables(PRIMITIVE_BINDINGS, STATIC_FAMILIES, OWNER_STATIC_FAMILY)
        self.assertEqual(
            tuple(diagnostic.table_key_counts),
            ("PRIMITIVE_BINDINGS", "STATIC_FAMILIES", "OWNER_STATIC_FAMILY"),
        )
        self.assertEqual(registry.registrations, before)

    def test_adapter_does_not_import_or_inspect_primitive_registry(self):
        path = REPO / "src/hsr_battle_agent/game_data/behavior_descriptor_adapter.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("behavior_compiler", imports)
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        self.assertNotIn("PRIMITIVE_BINDINGS", loaded_names)


if __name__ == "__main__": unittest.main()
