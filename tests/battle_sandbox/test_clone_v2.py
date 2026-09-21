# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode, UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_sandbox.context_v2 import TerraReadContext  # noqa: E402
from hsr_battle_agent.battle_sandbox.hash_v2 import semantic_hash_v2  # noqa: E402
from hsr_battle_agent.battle_sandbox.identity import ENTITY, IdentityAllocator  # noqa: E402
from hsr_battle_agent.battle_sandbox.opaque import OpaqueUnresolvedStore  # noqa: E402
from hsr_battle_agent.battle_sandbox.revision import (  # noqa: E402
    RevisionAndTransactionSequence,
    StateRevision,
)
from hsr_battle_agent.battle_sandbox.rng import (  # noqa: E402
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG_ALGORITHM,
    SandboxRng,
)
from hsr_battle_agent.battle_sandbox.snapshot_v2 import (  # noqa: E402
    SnapshotPolicyIdentity,
    TerraSnapshotV2,
)
from hsr_battle_agent.battle_sandbox.state_v2 import (  # noqa: E402
    TERRA_TYPED_STORE_FAMILIES,
    TerraBattleState,
)
from hsr_battle_agent.battle_sandbox.stores.core import empty_stores  # noqa: E402
from hsr_battle_agent.battle_sandbox.stores.protocols import OPAQUE_FIELD_FAMILIES  # noqa: E402


def policy() -> SnapshotPolicyIdentity:
    return SnapshotPolicyIdentity(
        evidence_mode=EvidenceMode.SANDBOX_EXTENSION,
        evidence_vocabulary_version="evidence/1",
        profile_id="clone-profile",
        profile_version="1",
        profile_content_sha256="a" * 64,
        rule_set_id="clone-rules",
        rule_set_version="1",
        rule_set_content_sha256="b" * 64,
    )


def state() -> TerraBattleState:
    stores = {
        name: store
        for name, store in empty_stores().items()
        if name in TERRA_TYPED_STORE_FAMILIES
    }
    stores["entities"] = stores["entities"].append(
        "e", {"nested": [1], "targets": [None]}
    )
    opaque = {
        name: OpaqueUnresolvedStore(field_family=name)
        for name in OPAQUE_FIELD_FAMILIES
    }
    opaque["unknown_extensions"] = opaque["unknown_extensions"].with_handle(
        UnknownHandle(
            blocker_id="CLONE-UNKNOWN",
            owner_family="KERNEL",
            payload={"nested": [1]},
            provenance={"source": "clone-test"},
            required_evidence=("evidence",),
        )
    )
    allocator = IdentityAllocator()
    allocator.allocate(ENTITY, "entity")
    return TerraBattleState(
        stores=stores,
        opaque_stores=opaque,
        revision_sequence=RevisionAndTransactionSequence(
            published_revision=StateRevision(4, "s4", "battle"),
            replay_sequence=5,
            committed_effect_sequence=6,
        ),
        allocator=allocator,
        rng_state=SandboxRng(123),
    )


def snapshot(value: TerraBattleState) -> TerraSnapshotV2:
    return TerraSnapshotV2(state=value, policy_identity=policy())


class TestCloneV2(unittest.TestCase):
    def test_equal_clone_has_equal_snapshot_and_hash(self):
        original = state()
        clone = original.clone()
        self.assertEqual(clone, original)
        self.assertEqual(snapshot(clone), snapshot(original))
        self.assertEqual(
            semantic_hash_v2(snapshot(clone)),
            semantic_hash_v2(snapshot(original)),
        )
        self.assertEqual(clone.revision_sequence, original.revision_sequence)
        self.assertEqual(clone.allocator.to_dict(), original.allocator.to_dict())

    def test_exported_typed_store_payload_cannot_mutate_state(self):
        original = state()
        before = original.to_dict()
        exported = original.stores["entities"]
        exported.entries[0].value.value["nested"].append(2)
        self.assertEqual(original.to_dict(), before)

    def test_exported_opaque_payload_cannot_mutate_state(self):
        original = state()
        before = original.to_dict()
        exported = original.opaque_stores["unknown_extensions"]
        exported.handles[0].payload["nested"].append(2)
        exported.handles[0].provenance["source"] = "changed"
        self.assertEqual(original.to_dict(), before)

    def test_rng_export_is_private_and_independent_evolution_changes_hash(self):
        original = state()
        before = original.to_dict()
        private_rng = original.rng_state
        private_rng.next_u64()
        self.assertEqual(original.to_dict(), before)

        evolved_document = original.clone().to_dict()
        evolved_document["rng_state"] = private_rng.to_dict()
        evolved = TerraBattleState.from_dict(evolved_document)
        self.assertNotEqual(
            semantic_hash_v2(snapshot(evolved)),
            semantic_hash_v2(snapshot(original)),
        )
        self.assertEqual(original.to_dict(), before)

    def test_allocator_clone_evolves_without_touching_original(self):
        original = state()
        replacement = original.clone().to_dict()
        allocator = original.allocator
        allocator.allocate(ENTITY, "entity")
        replacement["allocator"] = allocator.to_dict()
        evolved = TerraBattleState.from_dict(replacement)
        self.assertNotEqual(evolved, original)
        self.assertEqual(original.allocator.state_for("entity").next_value, 1)
        self.assertEqual(evolved.allocator.state_for("entity").next_value, 2)

    def test_context_exposes_read_only_rng_observation_only(self):
        context = TerraReadContext(state())
        view = context.rng_state
        self.assertEqual(view.algorithm, SANDBOX_RNG_ALGORITHM)
        self.assertEqual(view.client_algorithm, CLIENT_RNG_ALGORITHM)
        self.assertFalse(hasattr(view, "next_u64"))
        self.assertFalse(hasattr(view, "seed"))
        self.assertFalse(hasattr(context, "commit"))
        self.assertFalse(hasattr(context, "execute"))
        exported = view.to_dict()
        exported["state"]["internal_state"][0] = -1
        self.assertEqual(context.rng_state, view)

    def test_context_and_state_copy_do_not_alias(self):
        original = state()
        context = TerraReadContext(original)
        copy_state = context.state_copy()
        exported = copy_state.stores["entities"]
        exported.entries[0].value.value["nested"].append(9)
        self.assertEqual(context.state_copy(), original)
        self.assertEqual(
            semantic_hash_v2(context.capture_snapshot(policy())),
            semantic_hash_v2(snapshot(original)),
        )


if __name__ == "__main__":
    unittest.main()
