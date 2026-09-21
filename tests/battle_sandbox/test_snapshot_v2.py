# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode  # noqa: E402
from hsr_battle_agent.battle_sandbox.identity import ENTITY, IdentityAllocator  # noqa: E402
from hsr_battle_agent.battle_sandbox.revision import (  # noqa: E402
    RevisionAndTransactionSequence,
    StateRevision,
)
from hsr_battle_agent.battle_sandbox.rng import SandboxRng  # noqa: E402
from hsr_battle_agent.battle_sandbox.snapshot_v2 import (  # noqa: E402
    SnapshotPolicyIdentity,
    SnapshotV2Error,
    TerraSnapshotV2,
    capture_snapshot_v2,
)
from hsr_battle_agent.battle_sandbox.state_v2 import (  # noqa: E402
    TERRA_TYPED_STORE_FAMILIES,
    TerraBattleState,
)
from hsr_battle_agent.battle_sandbox.stores.protocols import FROZEN_FIELD_FAMILIES  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64


def policy(**changes) -> SnapshotPolicyIdentity:
    values = {
        "evidence_mode": EvidenceMode.SANDBOX_EXTENSION,
        "evidence_vocabulary_version": "evidence/1",
        "profile_id": "sandbox/full-content",
        "profile_version": "1",
        "profile_content_sha256": HASH_A,
        "rule_set_id": "sandbox/rules",
        "rule_set_version": "1",
        "rule_set_content_sha256": HASH_B,
    }
    values.update(changes)
    return SnapshotPolicyIdentity(**values)


def state() -> TerraBattleState:
    allocator = IdentityAllocator()
    allocator.allocate(ENTITY, "entity")
    return TerraBattleState(
        revision_sequence=RevisionAndTransactionSequence(
            published_revision=StateRevision(7, "snapshot-7", "battle-A"),
            replay_sequence=11,
            committed_effect_sequence=13,
        ),
        allocator=allocator,
        rng_state=SandboxRng(55),
    )


class TestSnapshotV2(unittest.TestCase):
    def test_round_trip_covers_every_owned_component(self):
        original = capture_snapshot_v2(state(), policy())
        document = json.loads(json.dumps(original.to_dict(), sort_keys=True))
        restored = TerraSnapshotV2.from_dict(document)
        self.assertEqual(restored, original)
        self.assertEqual(restored.restore_state(), state())
        represented = set(restored.state.owned_field_families())
        self.assertEqual(represented, set(FROZEN_FIELD_FAMILIES))
        self.assertEqual(set(restored.state.stores), set(TERRA_TYPED_STORE_FAMILIES))
        payload = restored.to_dict()["state"]
        self.assertIn("revision_and_transaction_sequence", payload)
        self.assertIn("allocator", payload)
        self.assertIn("rng_state", payload)
        self.assertIn("opaque_stores", payload)

    def test_absent_snapshot_components_never_default(self):
        document = capture_snapshot_v2(state(), policy()).to_dict()
        for key in ("state", "policy_identity"):
            with self.subTest(key=key):
                broken = copy.deepcopy(document)
                broken.pop(key)
                with self.assertRaises(SnapshotV2Error):
                    TerraSnapshotV2.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["state"]["stores"].pop()
        with self.assertRaises(SnapshotV2Error):
            TerraSnapshotV2.from_dict(broken)
        broken = copy.deepcopy(document)
        broken["policy_identity"].pop("rule_set_version")
        with self.assertRaises(SnapshotV2Error):
            TerraSnapshotV2.from_dict(broken)

    def test_profile_rule_and_evidence_identity_change_snapshot(self):
        base = capture_snapshot_v2(state(), policy())
        variants = (
            policy(profile_version="2"),
            policy(rule_set_content_sha256="c" * 64),
            policy(evidence_mode=EvidenceMode.REFERENCE_MODEL),
        )
        for variant in variants:
            with self.subTest(variant=variant.to_dict()):
                self.assertNotEqual(
                    base,
                    capture_snapshot_v2(state(), variant),
                )

    def test_snapshot_and_exports_are_mutation_isolated(self):
        source = state()
        snapshot = capture_snapshot_v2(source, policy())
        source.allocator.allocate(ENTITY, "external")
        exported = snapshot.to_dict()
        exported["state"]["allocator"]["namespaces"][0]["issued"].append(99)
        self.assertEqual(snapshot, snapshot.clone())
        restored = snapshot.restore_state()
        restored.allocator.allocate(ENTITY, "other")
        self.assertEqual(snapshot, snapshot.clone())

    def test_evidence_mode_is_classification_not_execution_permission(self):
        native = capture_snapshot_v2(
            state(), policy(evidence_mode=EvidenceMode.NATIVE_EVIDENCED)
        )
        self.assertFalse(hasattr(native, "execute"))
        self.assertFalse(hasattr(native.policy_identity, "can_execute"))

    def test_hash_only_definition_shortcut_is_not_present(self):
        snapshot = capture_snapshot_v2(state(), policy())
        self.assertFalse(hasattr(snapshot, "resolve_definitions"))
        self.assertIn("stores", snapshot.to_dict()["state"])


if __name__ == "__main__":
    unittest.main()
