from __future__ import annotations

import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from hsr_battle_agent.battle_ir.evidence import EvidenceMode
from hsr_battle_agent.battle_sandbox.custom_scenario import (
    CustomScenario,
    CustomTerminalRule,
    EmptySidePolicy,
    ResultPolicy,
    ScenarioParticipant,
    SimultaneousExhaustionPolicy,
)
from hsr_battle_agent.battle_sandbox.evidence_boundary import GateCertificate
from hsr_battle_agent.battle_sandbox.legal_actions import (
    LegalActionsStatus,
    LegalActionsView,
    PlayerLegalAction,
)
from hsr_battle_agent.battle_sandbox.sandbox_transition import (
    SandboxActionRule,
    SandboxResourceContract,
    SandboxTransitionError,
    initialize_sandbox_resource_state,
    plan_sandbox_resource_transition,
    query_sandbox_legal_actions,
    read_sandbox_resource_state,
)
from tests.battle_sandbox.test_transaction_plan import make_state


def make_contract() -> SandboxResourceContract:
    return SandboxResourceContract(
        namespace="tests.m5-recovery",
        version="1",
        contract_id="declared-energy-actions",
        owner_id="actor-left",
        resource_id="declared-energy",
        actions=(
            SandboxActionRule("action-a", "candidate-a", "actor-left", ("target",), Decimal("1")),
            SandboxActionRule("action-b", "candidate-b", "actor-left", ("target",), Decimal("2")),
            SandboxActionRule("action-c", "candidate-c", "actor-left", ("target",), Decimal("3")),
            SandboxActionRule("action-d", "candidate-d", "actor-left", ("target",), Decimal("4")),
        ),
    )


def make_policy(state):
    scenario = CustomScenario(
        stage_id=None,
        participants=(
            ScenarioParticipant("left", "left", 0),
            ScenarioParticipant("right", "right", 0),
        ),
        initial_state=state,
        terminal_rule=CustomTerminalRule(
            "tests.m5-recovery",
            "1",
            "explicit-local-terminal",
            EmptySidePolicy.TERMINAL,
            SimultaneousExhaustionPolicy.DRAW,
            ResultPolicy.REPORT_CUSTOM_OUTCOME,
        ),
    )
    return scenario.policy_identity()


def initialized(amount="10"):
    contract = make_contract()
    state = initialize_sandbox_resource_state(
        make_state(), contract, amount=amount, maximum="10"
    )
    return state, contract, make_policy(state)


class SandboxTransitionContractTests(unittest.TestCase):
    def test_initialization_changes_actual_resources_store_without_revision_advance(self):
        base = make_state()
        contract = make_contract()
        state = initialize_sandbox_resource_state(base, contract, amount="10", maximum="10")
        self.assertTrue(base.stores["resources"].is_empty())
        self.assertFalse(state.stores["resources"].is_empty())
        self.assertEqual(state.revision_sequence, base.revision_sequence)
        self.assertEqual(read_sandbox_resource_state(state, contract).amount, Decimal("10"))

    def test_initial_state_and_contract_are_sandbox_extension_only(self):
        state, contract, _policy = initialized()
        resource = read_sandbox_resource_state(state, contract)
        self.assertIs(contract.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertIs(resource.evidence_mode, EvidenceMode.SANDBOX_EXTENSION)
        self.assertNotIsInstance(contract, GateCertificate)
        self.assertNotIsInstance(resource, GateCertificate)

    def test_complete_legal_view_is_reference_model_and_exact_declared_order(self):
        _state, contract, _policy = initialized()
        candidates = tuple(rule.candidate_occurrence_id for rule in contract.actions)
        view = query_sandbox_legal_actions(contract, candidates)
        self.assertIs(view.status, LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE)
        self.assertIs(view.evidence_mode, EvidenceMode.REFERENCE_MODEL)
        self.assertEqual(tuple(action.action_id for action in view.actions),
                         ("action-a", "action-b", "action-c", "action-d"))

    def test_missing_candidate_blocks_without_returning_partial_actions(self):
        _state, contract, _policy = initialized()
        view = query_sandbox_legal_actions(contract, ("candidate-a",))
        self.assertIs(view.status, LegalActionsStatus.BLOCKED)
        self.assertEqual(view.actions, ())
        self.assertTrue(view.blockers)

    def test_extra_or_reordered_candidate_scope_cannot_masquerade_as_complete(self):
        _state, contract, _policy = initialized()
        expected = tuple(rule.candidate_occurrence_id for rule in contract.actions)
        for candidate_scope in (expected + ("candidate-extra",), tuple(reversed(expected))):
            view = query_sandbox_legal_actions(contract, candidate_scope)
            self.assertIs(view.status, LegalActionsStatus.BLOCKED)
            self.assertEqual(view.actions, ())
            self.assertEqual(view.blockers, ("CANDIDATE_SCOPE_MISMATCH",))

    def test_partial_or_reordered_complete_view_cannot_plan(self):
        state, contract, policy = initialized()
        view = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        incomplete = type(view)(view.status, view.actions[:-1], (), view.evidence_mode)
        with self.assertRaises(SandboxTransitionError):
            plan_sandbox_resource_transition(state, policy, contract, incomplete, "action-a")
        reordered = type(view)(view.status, tuple(reversed(view.actions)), (), view.evidence_mode)
        with self.assertRaises(SandboxTransitionError):
            plan_sandbox_resource_transition(state, policy, contract, reordered, "action-a")

    def test_noncanonical_player_action_shape_cannot_cross_local_gate(self):
        state, contract, policy = initialized()
        canonical = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        first = canonical.actions[0]
        malformed = PlayerLegalAction(
            first.action_id,
            first.candidate_occurrence_id,
            first.actor_id,
            list(first.target_ids),  # type: ignore[arg-type]
            first.resource_cost,
        )
        view = LegalActionsView(
            LegalActionsStatus.COMPLETE_FOR_SUPPORTED_SCOPE,
            (malformed,) + canonical.actions[1:],
            (),
        )
        with self.assertRaisesRegex(SandboxTransitionError, "canonical tuple"):
            plan_sandbox_resource_transition(state, policy, contract, view, "action-a")

    def test_planning_is_pure_for_state_rng_allocator_and_stores(self):
        state, contract, policy = initialized()
        view = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        before = copy.deepcopy(state.to_dict())
        plan = plan_sandbox_resource_transition(state, policy, contract, view, "action-b")
        self.assertEqual(state.to_dict(), before)
        self.assertEqual(plan.amount_before, Decimal("10"))
        self.assertEqual(plan.amount_after, Decimal("8"))
        self.assertEqual(plan.declared_reads, ("resources",))
        self.assertEqual(plan.declared_writes, ("resources",))

    def test_insufficient_resource_rejects_before_any_publication(self):
        state, contract, policy = initialized("1")
        view = query_sandbox_legal_actions(
            contract, tuple(rule.candidate_occurrence_id for rule in contract.actions)
        )
        before = copy.deepcopy(state.to_dict())
        with self.assertRaisesRegex(SandboxTransitionError, "insufficient"):
            plan_sandbox_resource_transition(state, policy, contract, view, "action-d")
        self.assertEqual(state.to_dict(), before)

    def test_constructor_input_sequences_do_not_alias_contract(self):
        actions = [SandboxActionRule("a", "c", "owner", [], "1")]
        contract = SandboxResourceContract("n", "1", "id", "owner", "r", actions)
        actions.append(SandboxActionRule("b", "d", "owner", [], "1"))
        self.assertEqual(tuple(action.action_id for action in contract.actions), ("a",))

    def test_resource_read_is_detached_from_owned_store(self):
        state, contract, _policy = initialized()
        first = read_sandbox_resource_state(state, contract)
        document = first.to_dict()
        document["amount"] = "0"
        self.assertEqual(read_sandbox_resource_state(state, contract).amount, Decimal("10"))

    def test_contract_rejects_native_or_reference_evidence_mode(self):
        values = make_contract().__dict__.copy()
        values["evidence_mode"] = EvidenceMode.NATIVE_EVIDENCED
        with self.assertRaises(SandboxTransitionError):
            SandboxResourceContract(**values)
        values["evidence_mode"] = EvidenceMode.REFERENCE_MODEL
        with self.assertRaises(SandboxTransitionError):
            SandboxResourceContract(**values)


if __name__ == "__main__":
    unittest.main()
