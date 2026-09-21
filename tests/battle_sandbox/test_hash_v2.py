# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode, UnknownHandle  # noqa: E402
from hsr_battle_agent.battle_sandbox.canonical_v2 import (  # noqa: E402
    CanonicalV2Error,
    canonical_v2_bytes,
)
from hsr_battle_agent.battle_sandbox.hash_v2 import (  # noqa: E402
    SemanticHashV2Error,
    semantic_hash_v2,
)
from hsr_battle_agent.battle_sandbox.identity import ENTITY, IdentityAllocator  # noqa: E402
from hsr_battle_agent.battle_sandbox.opaque import OpaqueUnresolvedStore  # noqa: E402
from hsr_battle_agent.battle_sandbox.revision import (  # noqa: E402
    RevisionAndTransactionSequence,
    StateRevision,
)
from hsr_battle_agent.battle_sandbox.rng import SandboxRng  # noqa: E402
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


def policy(**changes) -> SnapshotPolicyIdentity:
    values = {
        "evidence_mode": EvidenceMode.SANDBOX_EXTENSION,
        "evidence_vocabulary_version": "evidence/1",
        "profile_id": "profile",
        "profile_version": "1",
        "profile_content_sha256": "1" * 64,
        "rule_set_id": "rules",
        "rule_set_version": "1",
        "rule_set_content_sha256": "2" * 64,
    }
    values.update(changes)
    return SnapshotPolicyIdentity(**values)


def snapshot(
    *,
    queue=("a", "b"),
    ai_cursor=0,
    targets=(None,),
    terminal="OPEN",
    opaque_payload="x",
    rng_seed=4,
    allocate_count=1,
    revision=1,
    replay=2,
    effects=3,
    selected_policy=None,
) -> TerraSnapshotV2:
    stores = {
        name: store
        for name, store in empty_stores().items()
        if name in TERRA_TYPED_STORE_FAMILIES
    }
    stores["ordinary_timeline"] = stores["ordinary_timeline"].append(
        "queue", list(queue)
    )
    stores["ai_runtime"] = stores["ai_runtime"].append("cursor", ai_cursor)
    stores["target_contexts"] = stores["target_contexts"].append(
        "selected", list(targets)
    )
    stores["terminal_state"] = stores["terminal_state"].append(
        "state", terminal
    )
    opaque = {
        name: OpaqueUnresolvedStore(field_family=name)
        for name in OPAQUE_FIELD_FAMILIES
    }
    opaque["unknown_extensions"] = opaque["unknown_extensions"].with_handle(
        UnknownHandle(
            blocker_id="OPAQUE-1",
            owner_family="KERNEL",
            payload={"value": opaque_payload},
            provenance={"source": "test"},
            required_evidence=("new evidence",),
        )
    )
    allocator = IdentityAllocator()
    for _ in range(allocate_count):
        allocator.allocate(ENTITY, "entity")
    state = TerraBattleState(
        stores=stores,
        opaque_stores=opaque,
        revision_sequence=RevisionAndTransactionSequence(
            published_revision=StateRevision(revision, f"s-{revision}", "L"),
            replay_sequence=replay,
            committed_effect_sequence=effects,
        ),
        allocator=allocator,
        rng_state=SandboxRng(rng_seed),
    )
    return TerraSnapshotV2(
        state=state,
        policy_identity=selected_policy or policy(),
    )


class TestCanonicalV2(unittest.TestCase):
    def test_mapping_insertion_order_alone_does_not_change_encoding(self):
        self.assertEqual(
            canonical_v2_bytes({"a": 1, "b": [2, 3]}),
            canonical_v2_bytes({"b": [2, 3], "a": 1}),
        )

    def test_list_order_duplicates_null_and_presence_remain_distinct(self):
        self.assertNotEqual(canonical_v2_bytes([1, 2]), canonical_v2_bytes([2, 1]))
        self.assertNotEqual(canonical_v2_bytes([1]), canonical_v2_bytes([1, 1]))
        self.assertNotEqual(canonical_v2_bytes([]), canonical_v2_bytes([None]))
        self.assertNotEqual(canonical_v2_bytes(None), canonical_v2_bytes({}))
        self.assertNotEqual(canonical_v2_bytes(False), canonical_v2_bytes(0))

    def test_tuple_nonfinite_and_ambiguous_numbers_reject(self):
        for value in ((1, 2), math.nan, math.inf, -math.inf, Decimal("1.0")):
            with self.subTest(value=value):
                with self.assertRaises(CanonicalV2Error):
                    canonical_v2_bytes(value)
        self.assertNotEqual(canonical_v2_bytes(1), canonical_v2_bytes(1.0))


class TestSemanticHashV2(unittest.TestCase):
    def test_requires_complete_validated_snapshot(self):
        with self.assertRaises(SemanticHashV2Error):
            semantic_hash_v2(snapshot().to_dict())

    def test_each_decision_affecting_state_family_changes_hash(self):
        base = semantic_hash_v2(snapshot())
        variants = {
            "scheduler_order": snapshot(queue=("b", "a")),
            "ai_cursor": snapshot(ai_cursor=1),
            "target_null_presence": snapshot(targets=()),
            "terminal_state": snapshot(terminal="CLOSED"),
            "opaque_blocker": snapshot(opaque_payload="y"),
            "rng": snapshot(rng_seed=5),
            "allocator": snapshot(allocate_count=2),
            "revision": snapshot(revision=2),
            "replay_sequence": snapshot(replay=8),
            "effect_sequence": snapshot(effects=9),
        }
        for label, candidate in variants.items():
            with self.subTest(label=label):
                self.assertNotEqual(base, semantic_hash_v2(candidate))

    def test_profile_rule_and_evidence_identity_change_hash(self):
        base = semantic_hash_v2(snapshot())
        variants = (
            policy(profile_content_sha256="3" * 64),
            policy(rule_set_version="2"),
            policy(evidence_mode=EvidenceMode.REFERENCE_MODEL),
        )
        for selected in variants:
            with self.subTest(selected=selected.to_dict()):
                self.assertNotEqual(
                    base,
                    semantic_hash_v2(snapshot(selected_policy=selected)),
                )

    def test_equal_round_trip_has_equal_hash(self):
        original = snapshot()
        restored = TerraSnapshotV2.from_dict(original.to_dict())
        self.assertEqual(semantic_hash_v2(original), semantic_hash_v2(restored))


if __name__ == "__main__":
    unittest.main()
