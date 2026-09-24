# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import UnknownHandle
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue
from hsr_battle_agent.battle_sandbox.identity import ENTITY
from hsr_battle_agent.battle_sandbox.preflight import ObligationAccess
from hsr_battle_agent.battle_sandbox.transaction import StagedDelta, TransactionError
from tests.battle_sandbox.test_transaction_plan import make_plan


class TestStagedDelta(unittest.TestCase):
    def test_store_write_is_private_and_exactly_authorized(self):
        access = ObligationAccess("store:resources:hp", PresenceValue.present(5))
        live, _, plan = make_plan(writes=(access,))
        before = live.to_dict()
        delta = StagedDelta(plan, live).stage_store_append("resources", "hp", 5)
        self.assertEqual(live.to_dict(), before)
        self.assertEqual(delta.stores["resources"].keys(), ("hp",))
        self.assertEqual([x.target for x in delta.writes], ["store:resources:hp"])

    def test_undeclared_target_extent_and_read_only_permission_reject(self):
        write = ObligationAccess("store:resources:hp", PresenceValue.present(5))
        read = ObligationAccess("store:resources:energy", PresenceValue.present(2))
        live, _, plan = make_plan(writes=(write,), reads=(read,))
        delta = StagedDelta(plan, live)
        for family, key, value in (
            ("resources", "other", 5),
            ("resources", "hp", 6),
            ("resources", "energy", 2),
        ):
            with self.assertRaises(TransactionError):
                delta.stage_store_append(family, key, value)

    def test_absent_extent_is_not_a_wildcard(self):
        access = ObligationAccess("store:resources:hp")
        live, _, plan = make_plan(writes=(access,))
        with self.assertRaises(TransactionError):
            StagedDelta(plan, live).stage_store_append("resources", "hp", 5)

    def test_duplicate_writes_remain_explicit_and_ordered(self):
        access = ObligationAccess("store:resources:hp", PresenceValue.present(5))
        live, _, plan = make_plan(writes=(access, access))
        delta = StagedDelta(plan, live)
        delta = delta.stage_store_append("resources", "hp", 5)
        delta = delta.stage_store_append("resources", "hp", 5)
        self.assertEqual([x.target for x in delta.writes], [access.target, access.target])
        self.assertEqual(delta.stores["resources"].keys(), ("hp", "hp"))

    def test_allocator_publication_material_is_private(self):
        access = ObligationAccess(
            "allocator:entity", PresenceValue.present({"family": "ENTITY"})
        )
        live, _, plan = make_plan(writes=(access,))
        before = live.allocator.to_dict()
        delta, identity = StagedDelta(plan, live).stage_allocation(ENTITY, "entity")
        self.assertEqual(identity.value, 0)
        self.assertEqual(live.allocator.to_dict(), before)
        self.assertNotEqual(delta.allocator.to_dict(), before)

    def test_opaque_write_requires_exact_handle_document(self):
        handle = UnknownHandle(
            blocker_id="U", owner_family="TEST", payload={"items": []},
            provenance={"source": "fixture"}, required_evidence=("e",),
        )
        access = ObligationAccess(
            "opaque:unknown_extensions:U", PresenceValue.present(handle.to_dict())
        )
        live, _, plan = make_plan(writes=(access,))
        delta = StagedDelta(plan, live).stage_opaque_handle("unknown_extensions", handle)
        self.assertEqual(delta.opaque_stores["unknown_extensions"].blocker_ids(), ("U",))
        self.assertTrue(live.opaque_stores["unknown_extensions"].is_empty())

    def test_abort_by_discarding_delta_leaves_complete_live_state_identical(self):
        access = ObligationAccess("store:resources:hp", PresenceValue.present(5))
        live, _, plan = make_plan(writes=(access,))
        before = live.to_dict()
        _discarded = StagedDelta(plan, live).stage_store_append("resources", "hp", 5)
        self.assertEqual(live.to_dict(), before)

    def test_input_and_output_nested_aliases_are_detached(self):
        payload = {"items": []}
        access = ObligationAccess("store:resources:hp", PresenceValue.present(payload))
        live, _, plan = make_plan(writes=(access,))
        delta = StagedDelta(plan, live).stage_store_append("resources", "hp", payload)
        before = delta.to_dict()
        payload["items"].append("input")
        delta.writes[0].payload.require_present()["items"].append("output")
        delta.stores["resources"].entries[0].value.require_present()["items"].append("store")
        self.assertEqual(delta.to_dict(), before)

    def test_no_publication_surface(self):
        live, _, plan = make_plan()
        delta = StagedDelta(plan, live)
        self.assertFalse(hasattr(delta, "publish"))
        self.assertFalse(hasattr(delta, "commit"))
        self.assertEqual(live.to_dict(), make_plan()[0].to_dict())


if __name__ == "__main__":
    unittest.main()
