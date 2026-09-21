# -*- coding: utf-8 -*-
"""F02-008 acceptance tests for the independent Terra state aggregate."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_sandbox.identity import (  # noqa: E402
    ENTITY,
    IdentityAllocator,
)
from hsr_battle_agent.battle_sandbox.opaque import (  # noqa: E402
    OpaqueUnresolvedStore,
)
from hsr_battle_agent.battle_sandbox.revision import StateRevision  # noqa: E402
from hsr_battle_agent.battle_sandbox.rng import (  # noqa: E402
    SANDBOX_RNG_ALGORITHM,
    SandboxRng,
)
from hsr_battle_agent.battle_sandbox.state import BattleState  # noqa: E402
from hsr_battle_agent.battle_sandbox.state_v2 import (  # noqa: E402
    TERRA_BATTLE_STATE_SCHEMA,
    TERRA_COMPONENT_FIELD_FAMILIES,
    TERRA_TYPED_STORE_FAMILIES,
    TerraBattleState,
    TerraStateError,
)
from hsr_battle_agent.battle_sandbox.stores.core import empty_stores  # noqa: E402
from hsr_battle_agent.battle_sandbox.stores.protocols import (  # noqa: E402
    FROZEN_FIELD_FAMILIES,
    OPAQUE_FIELD_FAMILIES,
)


def unresolved() -> UnknownHandle:
    return UnknownHandle(
        blocker_id="TERRA-UNKNOWN-1",
        owner_family="BATTLE_STATE",
        payload={"tuple": (1, 2), "list": [1, 2], "null": None},
        provenance={"source": "frozen-unknown"},
        required_evidence=("version-qualified native transition",),
    )


def make_state() -> TerraBattleState:
    stores = {
        name: store
        for name, store in empty_stores().items()
        if name in TERRA_TYPED_STORE_FAMILIES
    }
    stores["entities"] = stores["entities"].append(
        "entity-1", {"hp": 0, "tags": [None]}
    )
    opaque = {
        name: OpaqueUnresolvedStore(field_family=name)
        for name in OPAQUE_FIELD_FAMILIES
    }
    opaque["unknown_extensions"] = opaque["unknown_extensions"].with_handle(
        unresolved()
    )
    allocator = IdentityAllocator()
    allocator.allocate(ENTITY, "entity")
    return TerraBattleState(
        stores=stores,
        opaque_stores=opaque,
        revision=StateRevision.initial("snapshot-0", lineage="battle-A"),
        allocator=allocator,
        rng_state=SandboxRng(1234),
    )


class TestTerraOwnership(unittest.TestCase):
    def test_every_frozen_family_has_exactly_one_component_owner(self):
        state = make_state()
        self.assertEqual(state.owned_field_families(), FROZEN_FIELD_FAMILIES)
        represented = (
            set(state.stores)
            | set(state.opaque_stores)
            | set(TERRA_COMPONENT_FIELD_FAMILIES)
        )
        self.assertEqual(represented, set(FROZEN_FIELD_FAMILIES))
        self.assertEqual(
            len(state.stores)
            + len(state.opaque_stores)
            + 3,
            len(FROZEN_FIELD_FAMILIES),
        )

    def test_unclassified_or_missing_typed_family_is_rejected(self):
        state = make_state()
        stores = dict(state.stores)
        stores["invented_extension"] = stores["entities"]
        with self.assertRaises(TerraStateError):
            TerraBattleState(
                stores=stores,
                opaque_stores=state.opaque_stores,
                revision=state.revision,
                allocator=state.allocator,
                rng_state=state.rng_state,
            )
        stores = dict(state.stores)
        stores.pop("entities")
        with self.assertRaises(TerraStateError):
            TerraBattleState(
                stores=stores,
                opaque_stores=state.opaque_stores,
                revision=state.revision,
                allocator=state.allocator,
                rng_state=state.rng_state,
            )

    def test_store_cannot_be_registered_under_another_family(self):
        state = make_state()
        stores = dict(state.stores)
        stores["teams"] = stores["entities"]
        with self.assertRaises(TerraStateError):
            TerraBattleState(
                stores=stores,
                opaque_stores=state.opaque_stores,
                revision=state.revision,
                allocator=state.allocator,
                rng_state=state.rng_state,
            )

    def test_unknown_family_query_fails_closed(self):
        with self.assertRaises(TerraStateError):
            make_state().owner_component_for("extensions")


class TestTerraRoundTrip(unittest.TestCase):
    def test_all_components_round_trip(self):
        state = make_state()
        payload = state.to_dict()
        restored = TerraBattleState.from_dict(payload)
        self.assertEqual(restored, state)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(payload["schema"], TERRA_BATTLE_STATE_SCHEMA)
        self.assertEqual(
            payload["rng_state"]["algorithm"], SANDBOX_RNG_ALGORITHM
        )
        self.assertEqual(
            restored.opaque_stores["unknown_extensions"].blocker_ids(),
            ("TERRA-UNKNOWN-1",),
        )

    def test_json_round_trip_preserves_complete_state(self):
        state = make_state()
        document = json.loads(json.dumps(state.to_dict(), sort_keys=True))
        self.assertEqual(TerraBattleState.from_dict(document), state)

    def test_clone_is_equal_and_independent(self):
        state = make_state()
        clone = state.clone()
        self.assertEqual(clone, state)
        allocated = clone.allocator.allocate(ENTITY, "entity")
        self.assertEqual(allocated.value, 1)
        self.assertEqual(state.allocator.state_for("entity").next_value, 1)

    def test_document_missing_extra_and_duplicate_families_reject(self):
        document = make_state().to_dict()
        for key in ("revision", "allocator", "rng_state", "stores"):
            with self.subTest(missing=key):
                broken = copy.deepcopy(document)
                broken.pop(key)
                with self.assertRaises(TerraStateError):
                    TerraBattleState.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["extra"] = None
        with self.assertRaises(TerraStateError):
            TerraBattleState.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["stores"].append(copy.deepcopy(broken["stores"][0]))
        with self.assertRaises(TerraStateError):
            TerraBattleState.from_dict(broken)

    def test_rng_document_never_defaults_missing_state(self):
        document = make_state().to_dict()
        document["rng_state"]["state"].pop("gauss_next")
        with self.assertRaises(TerraStateError):
            TerraBattleState.from_dict(document)


class TestMutationIsolationAndRng(unittest.TestCase):
    def test_constructor_does_not_draw_or_alias_rng(self):
        rng = SandboxRng(9)
        before = rng.to_dict()
        allocator = IdentityAllocator()
        state = TerraBattleState(
            revision=StateRevision.initial("s"),
            allocator=allocator,
            rng_state=rng,
        )
        self.assertEqual(rng.to_dict(), before)
        rng.next_u64()
        self.assertEqual(state.to_dict()["rng_state"], before)

    def test_allocator_and_serialization_are_isolated(self):
        allocator = IdentityAllocator()
        state = TerraBattleState(
            revision=StateRevision.initial("s"),
            allocator=allocator,
            rng_state=SandboxRng(1),
        )
        allocator.allocate(ENTITY, "external")
        self.assertEqual(state.allocator.namespaces(), ())
        payload = state.to_dict()
        payload["stores"][0]["payload"] = {"kind": "null"}
        payload["rng_state"]["state"]["internal_state"][0] = -1
        self.assertEqual(state, state.clone())

    def test_opaque_payload_is_preserved_losslessly(self):
        restored = TerraBattleState.from_dict(make_state().to_dict())
        handle = restored.opaque_stores["unknown_extensions"].handles[0]
        self.assertEqual(handle.payload["tuple"], (1, 2))
        self.assertEqual(handle.payload["list"], [1, 2])


class TestLegacySeparation(unittest.TestCase):
    def test_legacy_battle_state_behavior_is_unchanged(self):
        legacy = BattleState(extensions={"legacy": {"items": [1]}})
        before = legacy.to_dict()
        make_state()
        self.assertEqual(legacy.to_dict(), before)
        self.assertEqual(BattleState.from_dict(before).to_dict(), before)

    def test_no_automatic_legacy_projection_exists(self):
        state = make_state()
        for name in ("from_legacy", "to_legacy", "as_legacy", "project_legacy"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(state, name))
        with self.assertRaises(TerraStateError):
            TerraBattleState(
                revision=StateRevision.initial("s"),
                allocator=IdentityAllocator(),
                rng_state=SandboxRng(1),
                stores=BattleState(),
            )


if __name__ == "__main__":
    unittest.main()
