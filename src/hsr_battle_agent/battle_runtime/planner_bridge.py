"""R26 deterministic, simulator-backed planning over public R22/R25 APIs.

All tactical weights, partial-result assumptions and budgets are caller inputs.
This adapter owns search bookkeeping only; BehaviorRuntime owns every transition.
"""
from __future__ import annotations

import copy
import itertools
import json
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
import hashlib

from hsr_battle_agent.battle_ir.behavior import stable_hash
from .behavior import BehaviorRuntime
from .battle_turn import KEY, ADAPTER, PROVIDERS, TurnError

VERSION = 'r26_beam_search_reference/1'
ALGORITHMS = ('FIRST_LEGAL_REFERENCE', 'ONE_STEP_GREEDY_REFERENCE', 'BEAM_SEARCH_REFERENCE')
METRICS = ('team_hp', 'enemy_hp', 'resources', 'normal_turns', 'av', 'enemies_remaining', 'waves_completed', 'shield')
STATUSES = ('TERMINAL_VICTORY', 'TERMINAL_DEFEAT', 'RUNNING_EVALUABLE',
            'SEARCH_BUDGET_TRUNCATED', 'SIMULATOR_SEMANTIC_GAP', 'OPPONENT_POLICY_MISSING',
            'UNSUPPORTED_DECISION_BOUNDARY', 'ACTION_ADMISSION_REJECTED', 'POLICY_MISMATCH', 'REPLAY_MISMATCH')


class PlannerGap(ValueError):
    def __init__(self, code, detail):
        self.code, self.detail = code, str(detail)
        super().__init__(code + ': ' + self.detail)


@dataclass(frozen=True)
class PlannerRequest:
    runtime_hash: str
    decision_id: str
    controlled_side: str
    controlled_actors: tuple[str, ...]
    algorithm: str
    beam_width: int
    max_player_decisions: int
    budgets: dict
    scoring_policy: dict
    opponent_policy: dict
    tie_breaking_policy: str
    branch_status_policy: dict
    source_authority: dict
    runtime_policy_hash: str

    def to_dict(self):
        d = copy.deepcopy(asdict(self)); d['controlled_actors'] = list(self.controlled_actors)
        return d

    @classmethod
    def from_dict(cls, d):
        try:
            fields = copy.deepcopy(d); fields['controlled_actors'] = tuple(fields['controlled_actors'])
            return cls(**fields)
        except (KeyError, TypeError, ValueError) as exc:
            raise PlannerGap('PLANNER_POLICY_MISSING', exc) from exc

    def validate(self):
        if any(not isinstance(v, dict) for v in (self.budgets, self.scoring_policy, self.opponent_policy,
                                                 self.branch_status_policy, self.source_authority)):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'explicit policy documents required')
        required = ('max_total_nodes', 'max_simulated_actions', 'max_simulator_transitions',
                    'max_scheduler_work', 'max_encounter_transitions', 'max_opponent_actions',
                    'max_candidates', 'max_trace_bytes', 'max_branch_actions',
                    'scheduler_quantum', 'transition_quantum', 'max_yields')
        if set(self.budgets) != set(required) or any(type(v) is not int or v < 1 for v in self.budgets.values()):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'explicit positive integer budgets required: ' + str(required))
        if (self.algorithm not in ALGORITHMS or type(self.beam_width) is not int or self.beam_width < 1 or
                type(self.max_player_decisions) is not int or self.max_player_decisions < 1):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'algorithm, beam width and horizon required')
        s = self.scoring_policy
        if (set(s) != {'identity', 'terminal_order', 'partial_assumption', 'weights'} or not s['identity'] or
                s['terminal_order'] != ['VICTORY', 'PARTIAL', 'DEFEAT', 'BLOCKED'] or
                s['partial_assumption'] != 'UNCERTAIN_ABOVE_DEFEAT_REFERENCE' or
                set(s['weights']) != set(METRICS) or any(type(x) is not int for x in s['weights'].values())):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'explicit terminal/partial order and integer metric weights required')
        if (self.tie_breaking_policy != 'ACTION_TARGET_UTF8_ASC' or
                self.branch_status_policy != {'truncated': 'SCORE_PARTIAL_UNCERTAIN', 'blocked': 'RETAIN_REPORT_BELOW_DEFEAT',
                                              'budget_yield': 'RESUME_BOUNDED', 'unsupported': 'STOP_TYPED'}):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'unsupported or absent tie/status policy')
        if (not self.runtime_hash or not self.decision_id or not self.runtime_policy_hash or not self.controlled_side or
                not self.controlled_actors or len(set(self.controlled_actors)) != len(self.controlled_actors) or
                not self.source_authority.get('evidence') or self.source_authority.get('authority') != 'REFERENCE_MODEL'):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'state, controller and source authority required')
        if (set(self.opponent_policy) != {'identity', 'missing'} or self.opponent_policy['missing'] != 'STOP_TYPED' or
                (self.opponent_policy['identity'] is not None and not isinstance(self.opponent_policy['identity'], dict))):
            raise PlannerGap('PLANNER_POLICY_MISSING', 'explicit opponent identity or STOP_TYPED absence required')


@dataclass(frozen=True)
class PlannerResult:
    document: dict

    def to_dict(self): return copy.deepcopy(self.document)

    @classmethod
    def from_dict(cls, d):
        raw = copy.deepcopy(d); seal = raw.pop('result_hash', None)
        if raw.get('schema') != 'reference_planner_result/1' or stable_hash(raw) != seal:
            raise PlannerGap('REPLAY_MISMATCH', 'planner result seal')
        return cls(copy.deepcopy(d))


def _encoded(d): return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def facts(r, side):
    """Read stores without inferring native resource/defense rules."""
    state, turn = r.state, r.state.mechanics[KEY]
    players = sorted(a for a, e in state.entities.items() if e.get('team') == side)
    enemies = sorted(a for a, e in state.entities.items() if e.get('team') != side)
    encounter = r.current_encounter()
    defense = state.mechanics.get('r24_defense_break_reference_v1', {}).get('actors', {})
    shield_rows = [defense.get(a, {}).get('shields', {}) for a in players]
    shield_known = all('value' in row and all('value' in s['capacity'] for s in row['value']) for row in shield_rows)
    shield = sum(s['capacity']['value'] for row in shield_rows for s in row['value']) if shield_known else None
    return {'hp': {a: p.get('hp') for a, p in sorted(state.properties.items())},
            'actor_resources': copy.deepcopy(state.actor_resources), 'team_resources': copy.deepcopy(state.team_resources),
            'clock': copy.deepcopy(turn['clock']['now']), 'normal_turns': turn['normal_turn_count'],
            'actions': turn['action_count'], 'wave_index': turn['stage']['wave_index'],
            'encounter_phase': encounter['phase'], 'rng_draws': state.rng.draws,
            'metrics': {'team_hp': sum(state.properties[a]['hp'] for a in players),
                        'enemy_hp': sum(state.properties[a]['hp'] for a in enemies),
                        'resources': sum(sum(state.actor_resources.get(a, {}).values()) for a in players) +
                                     sum(state.team_resources.get(side, {}).values()),
                        'normal_turns': turn['normal_turn_count'], 'av': copy.deepcopy(turn['clock']['now']),
                        'enemies_remaining': sum(bool(state.entities[a].get('alive')) for a in enemies),
                        'waves_completed': sum(e['kind'] == 'WAVE_CLEAR' and e['status'] == 'COMMITTED' for e in encounter['events']),
                        'shield': shield}}


def evaluate(r, status, policy, side):
    f = facts(r, side); components = {}; total = Fraction(0)
    for name, weight in policy['weights'].items():
        value = f['metrics'][name]
        if value is None:
            if weight:
                raise PlannerGap('SIMULATOR_SEMANTIC_GAP', 'scoring metric unknown: ' + name)
            components[name] = {'value': None, 'weight': 0, 'weighted': {'n': 0, 'd': 1}, 'known': False}
            continue
        value = Fraction(value['n'], value['d']) if isinstance(value, dict) else Fraction(value)
        component = value * weight; total += component
        components[name] = {'value': {'n': value.numerator, 'd': value.denominator}, 'weight': weight,
                            'weighted': {'n': component.numerator, 'd': component.denominator}}
    group = ('VICTORY' if status == 'TERMINAL_VICTORY' else 'DEFEAT' if status == 'TERMINAL_DEFEAT'
             else 'PARTIAL' if status in ('RUNNING_EVALUABLE', 'SEARCH_BUDGET_TRUNCATED') else 'BLOCKED')
    return {'classification': group, 'terminal_rank': len(policy['terminal_order']) - policy['terminal_order'].index(group),
            'partial_uncertain': group == 'PARTIAL', 'score': {'n': total.numerator, 'd': total.denominator},
            'components': components, 'predicted': f, 'native_correctness': 'NOT_CLAIMED'}


def _choice_key(choice): return (choice['action_id'].encode('utf-8'), tuple(t.encode('utf-8') for t in choice['targets']))


def enumerate_choices(r, decision_id, limit):
    """Fresh R22 permissions validate IR, revision, generation and R20 costs.

    Target cardinality comes from that permission's exact R22 availability row;
    permissions deliberately do not carry min/max cardinality themselves.
    """
    permissions = sorted(r.legal_action_candidates(decision_id), key=lambda p: p['action_id'].encode('utf-8'))
    choices = []; total = 0
    for p in permissions:
        actor = r.policies[PROVIDERS]['availability']['actors'][p['actor_id']]
        spec = next(x for x in actor['actions'] if x['action_id'] == p['action_id'])
        import math
        total += sum(math.comb(len(p['target_ids']), n) for n in range(spec['target_min'], spec['target_max'] + 1))
        for count in range(spec['target_min'], spec['target_max'] + 1):
            for targets in itertools.combinations(sorted(p['target_ids'], key=lambda x: x.encode('utf-8')), count):
                if len(choices) >= limit: break
                choices.append({'action_id': p['action_id'], 'targets': list(targets), 'actor_id': p['actor_id'],
                                'action_ir_hash': p['action_ir_hash'], 'cost_policy_hash': p['cost_policy_hash'],
                                'source_authority': r.actions[p['action_id']].authority.to_dict()})
            if len(choices) >= limit: break
    choices.sort(key=_choice_key)
    return choices, total


@dataclass
class _Branch:
    identity: str
    parent: str | None
    runtime: BehaviorRuntime
    depth: int = 0
    choices: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    status: str = 'RUNNING_EVALUABLE'
    reason: str | None = None
    boundary: dict | None = None
    evaluation: dict | None = None
    work: dict = field(default_factory=lambda: {'actions': 0, 'opponent_actions': 0, 'advance_calls': 0, 'yields': 0})


class _Search:
    def __init__(self, request, provider):
        self.q, self.provider = request, provider
        self.count = dict.fromkeys(('nodes_expanded', 'clones', 'simulated_actions', 'simulator_transitions',
            'scheduler_work_reserved', 'encounter_transitions_reserved', 'opponent_actions', 'candidates_enumerated',
            'trace_bytes', 'budget_yields', 'snapshot_restores', 'r15_history_records', 'r25_lifecycle_transitions'), 0)
        self.branches = []; self.pruned = []; self.omitted = 0; self.enumerations = []

    def stop(self, branch, status, reason):
        branch.status, branch.reason = status, str(reason)

    def command(self, branch, kind, arguments, permission=None):
        q, count, r = self.q, self.count, branch.runtime
        if count['simulator_transitions'] >= q.budgets['max_simulator_transitions']:
            self.stop(branch, 'SEARCH_BUDGET_TRUNCATED', 'max_simulator_transitions'); return None
        before = r.snapshot(); prehash = r.stable_hash(); pre = facts(r, q.controlled_side)
        count['simulator_transitions'] += 1
        try:
            if kind == 'advance': out = r.run_until_encounter_boundary(**arguments)
            elif kind == 'enemy': out = r.request_enemy_decision(self.provider)
            else: out = r.submit_action(**arguments)
        except TurnError as exc:
            self.stop(branch, 'ACTION_ADMISSION_REJECTED' if kind != 'advance' else 'SIMULATOR_SEMANTIC_GAP', exc)
            return None
        receipt = {'kind': kind, 'arguments': copy.deepcopy(arguments), 'prehash': prehash, 'posthash': r.stable_hash(),
                   'before': pre, 'after': facts(r, q.controlled_side),
                   'permission_provenance': copy.deepcopy(permission), 'authority': 'REFERENCE_MODEL'}
        if kind in ('submit', 'enemy'):
            selected = r.state.mechanics[ADAPTER]['selected_action']
            receipt['selected_action'] = {'action_id': selected['permission']['action_id'],
                'actor_id': selected['permission']['actor_id'], 'targets': selected['targets'],
                'action_ir_hash': selected['permission']['action_ir_hash'],
                'permission': copy.deepcopy(selected['permission'])}
        size = len(_encoded(receipt))
        if count['trace_bytes'] + size > q.budgets['max_trace_bytes']:
            branch.runtime = BehaviorRuntime.from_snapshot(before, registry=r.registry)
            count['snapshot_restores'] += 1
            self.stop(branch, 'SEARCH_BUDGET_TRUNCATED', 'max_trace_bytes'); return None
        count['trace_bytes'] += size; branch.trace.append(receipt)
        old_adapter = before['state']['mechanics'][ADAPTER]
        old_encounter = before['state']['mechanics']['reference_encounter_v1']
        ordinary_before = sum(old_adapter.get('scheduler_history_cursor', {}).values())
        ordinary_after = sum(r.state.mechanics[ADAPTER].get('scheduler_history_cursor', {}).values())
        encounter_after = r.current_encounter()
        count['r15_history_records'] += max(0, ordinary_after-ordinary_before) + max(0,
            encounter_after['counters']['scheduler_steps']-old_encounter['counters']['scheduler_steps'])
        count['r25_lifecycle_transitions'] += max(0,len(encounter_after['transitions'])-len(old_encounter['transitions']))
        return out

    def advance(self, branch):
        q, count = self.q, self.count
        while branch.status == 'RUNNING_EVALUABLE':
            scheduler = min(q.budgets['scheduler_quantum'], q.budgets['max_scheduler_work'] - count['scheduler_work_reserved'])
            transitions = min(q.budgets['transition_quantum'], q.budgets['max_encounter_transitions'] - count['encounter_transitions_reserved'])
            if scheduler <= 0 or transitions <= 0:
                self.stop(branch, 'SEARCH_BUDGET_TRUNCATED', 'max_scheduler_work' if scheduler <= 0 else 'max_encounter_transitions'); return
            # Conservative reservations are never refunded. R22 owns actual work.
            count['scheduler_work_reserved'] += scheduler; count['encounter_transitions_reserved'] += transitions
            b = self.command(branch, 'advance', {'budget': {'scheduler_work': scheduler, 'decision_transitions': transitions,
                'normal_turns': transitions, 'queue_pops': transitions, 'zero_time_insertions': transitions,
                'boundary_callbacks': scheduler}})
            branch.work['advance_calls'] += 1
            if b is None: return
            branch.boundary = copy.deepcopy(b.boundary)
            kind = b.kind
            if kind == 'BUDGET_YIELD':
                branch.work['yields'] += 1; count['budget_yields'] += 1
                if branch.work['yields'] >= q.budgets['max_yields']:
                    self.stop(branch, 'SEARCH_BUDGET_TRUNCATED', 'max_yields / ' + str(b['input_request'])); return
                continue
            if kind == 'BATTLE_TERMINAL':
                result = branch.runtime.encounter_result()
                status = {'VICTORY': 'TERMINAL_VICTORY', 'DEFEAT': 'TERMINAL_DEFEAT'}.get((result or {}).get('result'))
                self.stop(branch, status or 'UNSUPPORTED_DECISION_BOUNDARY', (result or {}).get('result')); return
            if kind == 'SEMANTIC_GAP':
                self.stop(branch, 'SIMULATOR_SEMANTIC_GAP', b['failure']); return
            if kind == 'ENEMY_AI_DECISION':
                identity = q.opponent_policy['identity']
                actual = branch.runtime.policies[PROVIDERS].get('monster_decision')
                if identity is None:
                    self.stop(branch, 'OPPONENT_POLICY_MISSING', 'caller declared STOP_TYPED'); return
                if identity != actual or (self.provider is not None and getattr(self.provider, 'identity', None) != identity):
                    self.stop(branch, 'POLICY_MISMATCH', 'opponent provider identity'); return
                if self.provider is None and identity.get('mode') != 'FIRST_PERMISSION_REFERENCE':
                    self.stop(branch, 'OPPONENT_POLICY_MISSING', 'provider implementation absent'); return
                if not self.action_budget(branch, enemy=True): return
                permissions = branch.runtime.legal_action_candidates(b['decision_id'])
                if not permissions:
                    self.stop(branch, 'ACTION_ADMISSION_REJECTED', 'no opponent permissions'); return
                if self.command(branch, 'enemy', {}, {'provider_identity': identity, 'permissions': permissions}) is None: return
                continue
            if kind == 'PLAYER_NORMAL_TURN' and b['actor_id'] in q.controlled_actors:
                return
            # Forced/interrupt/suspended inputs require a separate explicit policy.
            self.stop(branch, 'UNSUPPORTED_DECISION_BOUNDARY', kind); return

    def action_budget(self, branch, enemy=False):
        count, budgets = self.count, self.q.budgets
        checks = [(count['simulated_actions'], budgets['max_simulated_actions'], 'max_simulated_actions'),
                  (branch.work['actions'], budgets['max_branch_actions'], 'max_branch_actions')]
        if enemy: checks.append((count['opponent_actions'], budgets['max_opponent_actions'], 'max_opponent_actions'))
        for value, cap, name in checks:
            if value >= cap:
                self.stop(branch, 'SEARCH_BUDGET_TRUNCATED', name); return False
        count['simulated_actions'] += 1; branch.work['actions'] += 1
        if enemy: count['opponent_actions'] += 1; branch.work['opponent_actions'] += 1
        return True

    def score(self, branch):
        try:
            branch.evaluation = evaluate(branch.runtime, branch.status, self.q.scoring_policy, self.q.controlled_side)
        except PlannerGap as exc:
            self.stop(branch, 'SIMULATOR_SEMANTIC_GAP', exc)
            # Unknown nonzero-weight metrics block the branch. Only the BLOCKED
            # diagnostic score omits them; it can never become a recommended win.
            diagnostic = copy.deepcopy(self.q.scoring_policy)
            values = facts(branch.runtime, self.q.controlled_side)['metrics']
            for key in diagnostic['weights']:
                if values[key] is None: diagnostic['weights'][key] = 0
            branch.evaluation = evaluate(branch.runtime, branch.status, diagnostic, self.q.controlled_side)
            branch.evaluation['unscored_policy_gap'] = exc.detail
        for index, row in enumerate(self.branches):
            if row['branch_id'] == branch.identity:
                self.branches[index] = self.row(branch)
                break

    def key(self, branch):
        e = branch.evaluation; score = e['score']
        return (-e['terminal_rank'], -Fraction(score['n'], score['d']), tuple(_choice_key(c) for c in branch.choices), branch.identity)

    def row(self, branch, snapshot=False):
        row = {'branch_id': branch.identity, 'parent_branch_id': branch.parent, 'choices': copy.deepcopy(branch.choices),
               'runtime_hash': branch.runtime.stable_hash(), 'depth': branch.depth, 'work': copy.deepcopy(branch.work),
               'status': branch.status, 'reason': branch.reason, 'evaluation': branch.evaluation,
               'decision': branch.boundary}
        if snapshot: row['runtime_snapshot'] = branch.runtime.snapshot()
        return row

    def run(self, runtime):
        q = self.q; root = _Branch('branch:0', None, runtime.clone()); self.count['clones'] += 1
        self.advance(root); self.score(root)
        if root.boundary and root.boundary['decision_id'] != q.decision_id:
            self.stop(root, 'POLICY_MISMATCH', 'decision identity differs'); self.score(root)
        beam, leaves, root_choices = [root], [], []
        horizon = 1 if q.algorithm == 'ONE_STEP_GREEDY_REFERENCE' else q.max_player_decisions
        for _ in range(horizon):
            children = []
            for parent in beam:
                if parent.status != 'RUNNING_EVALUABLE': leaves.append(parent); continue
                limit = q.budgets['max_candidates'] - self.count['candidates_enumerated']
                if limit <= 0:
                    self.stop(parent, 'SEARCH_BUDGET_TRUNCATED', 'max_candidates'); self.score(parent); leaves.append(parent); continue
                choices, total = enumerate_choices(parent.runtime, parent.boundary['decision_id'], limit)
                self.count['candidates_enumerated'] += len(choices)
                self.enumerations.append({'branch_id': parent.identity, 'legal_choices': total, 'enumerated': len(choices)})
                if not parent.choices: root_choices = choices
                self.omitted += total - len(choices)
                if q.algorithm == 'FIRST_LEGAL_REFERENCE':
                    self.omitted += max(0, len(choices) - 1); choices = choices[:1]
                if not choices:
                    self.stop(parent, 'ACTION_ADMISSION_REJECTED', 'no legal supported candidate'); self.score(parent); leaves.append(parent)
                for index, choice in enumerate(choices):
                    if self.count['nodes_expanded'] >= q.budgets['max_total_nodes']:
                        self.omitted += len(choices)-index
                        self.stop(parent, 'SEARCH_BUDGET_TRUNCATED', 'max_total_nodes')
                        self.score(parent); leaves.append(parent); break
                    child = _Branch('branch:' + str(self.count['clones']), parent.identity, parent.runtime.clone(),
                        parent.depth+1, parent.choices+[choice], list(parent.trace), work=copy.deepcopy(parent.work))
                    self.count['clones'] += 1; self.count['nodes_expanded'] += 1
                    try:
                        ps = child.runtime.legal_action_candidates(parent.boundary['decision_id'])
                        permission = next(p for p in ps if p['action_id'] == choice['action_id'])
                        if self.action_budget(child):
                            out = self.command(child, 'submit', {'permission': permission, 'targets': choice['targets'],
                                'expected_revision': permission['state_revision']}, permission)
                            if out is not None: self.advance(child)
                            else: child.choices = list(parent.choices)
                        else: child.choices = list(parent.choices)
                    except (TurnError, StopIteration) as exc:
                        self.stop(child, 'ACTION_ADMISSION_REJECTED', exc)
                    self.score(child); self.branches.append(self.row(child)); children.append(child)
            if not children: break
            children.sort(key=self.key)
            running = [c for c in children if c.status == 'RUNNING_EVALUABLE']
            leaves.extend(c for c in children if c.status != 'RUNNING_EVALUABLE')
            width = 1 if q.algorithm == 'FIRST_LEGAL_REFERENCE' else q.beam_width
            beam = running[:width]
            for c in running[width:]:
                self.stop(c, 'SEARCH_BUDGET_TRUNCATED', 'beam_width pruning'); self.score(c)
                self.pruned.append(c.identity); leaves.append(c)
            if not beam: break
        else:
            leaves.extend(beam)
        if not leaves: leaves = [root]
        # Best descendant per first move, retaining blocked and pruned alternatives.
        ranked = {}
        for branch in sorted(leaves, key=self.key):
            if branch.choices:
                ranked.setdefault(_choice_key(branch.choices[0]), branch)
        alternatives = sorted(ranked.values(), key=self.key)
        selectable = [b for b in alternatives if b.status in ('TERMINAL_VICTORY', 'TERMINAL_DEFEAT', 'RUNNING_EVALUABLE', 'SEARCH_BUDGET_TRUNCATED')]
        best = selectable[0] if selectable else None
        observed = best or (alternatives[0] if alternatives else sorted(leaves, key=self.key)[0])
        statuses = [row['status'] for row in self.branches] or [root.status]
        result = {'schema': 'reference_planner_result/1', 'algorithm': q.algorithm, 'version': VERSION,
            'status': observed.status,
            'implementation_hash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'request': q.to_dict(), 'starting_runtime_hash': q.runtime_hash, 'decision_id': q.decision_id,
            'reference_policy_hashes': {'runtime': q.runtime_policy_hash, 'scoring': stable_hash(q.scoring_policy),
                'opponent': stable_hash(q.opponent_policy), 'branch_status': stable_hash(q.branch_status_policy)},
            'chosen_action': copy.deepcopy(best.choices[0]) if best else None,
            'predicted_terminal_result': observed.evaluation['classification'],
            'unselectable_branches': [self.row(b) for b in leaves if not b.choices],
            'ranked_alternatives': [self.row(b) for b in alternatives],
            'principal_variation': best.trace if best else [], 'chosen_branch': self.row(best, snapshot=True) if best else None,
            'search_trace': self.branches, 'root_status': root.status, 'root_reason': root.reason,
            'counts': self.count, 'search_depth': max((b.depth for b in leaves), default=0),
            'clone_snapshot_overhead': {'runtime_clones': self.count['clones'],
                'command_checkpoints': self.count['simulator_transitions'], 'restores': self.count['snapshot_restores'],
                'starting_snapshot_bytes': len(_encoded(runtime.snapshot()))},
            'completed_rollouts': sum(b.status in ('TERMINAL_VICTORY', 'TERMINAL_DEFEAT') for b in leaves),
            'truncated_rollouts': sum(b.status == 'SEARCH_BUDGET_TRUNCATED' for b in leaves),
            'incomplete_rollouts': sum(b.status not in ('TERMINAL_VICTORY', 'TERMINAL_DEFEAT') for b in leaves),
            'semantic_gaps': ([self.row(root)] if root.status == 'SIMULATOR_SEMANTIC_GAP' else []) +
                [row for row in self.branches if row['status'] == 'SIMULATOR_SEMANTIC_GAP'],
            'coverage': {'root_candidates_enumerated': len(root_choices), 'enumerations': self.enumerations,
                'root_choices_total': self.enumerations[0]['legal_choices'] if self.enumerations else 0,
                'root_choices_simulated': sum(row['parent_branch_id']=='branch:0' and bool(row['choices']) for row in self.branches),
                'unexplored_choices': self.omitted, 'pruned_branch_ids': self.pruned,
                'classification': 'BOUNDED_REFERENCE_SEARCH', 'globally_optimal': False,
                'assumptions': 'Explicit uncertain partial ranking and declared opponent; native correctness NOT CLAIMED'},
            'opponent_policy_identity': q.opponent_policy['identity'], 'source_authority': q.source_authority,
            'branch_status_counts': {s: statuses.count(s) for s in STATUSES},
            'budget_accounting': 'Global conservative R22 scheduler/decision transition reservations; no refund; trace bytes count unique command receipts'}
        result['result_hash'] = stable_hash(result)
        return PlannerResult(result)


def plan(runtime: BehaviorRuntime, request: PlannerRequest, *, opponent_provider=None) -> PlannerResult:
    """Read-only on caller runtime, including permissions, RNG and owned work."""
    if not isinstance(request, PlannerRequest): raise PlannerGap('PLANNER_POLICY_MISSING', 'PlannerRequest required')
    request.validate()
    before = runtime.snapshot()
    if runtime.stable_hash() != request.runtime_hash or stable_hash(runtime.policies) != request.runtime_policy_hash:
        raise PlannerGap('POLICY_MISMATCH', 'starting runtime or policies changed')
    if runtime.current_encounter() is None:
        raise PlannerGap('UNSUPPORTED_DECISION_BOUNDARY', 'R25 encounter required')
    if any(runtime.state.entities.get(a, {}).get('team') != request.controlled_side for a in request.controlled_actors):
        raise PlannerGap('POLICY_MISMATCH', 'controlled actors do not belong to side')
    try: return _Search(request, opponent_provider).run(runtime)
    finally:
        if before != runtime.snapshot(): raise AssertionError('planner mutated caller runtime')


def validate_recommendation(runtime, result):
    """Return fresh permissions without submitting; R22 owns actual admission."""
    d = PlannerResult.from_dict(result.to_dict() if isinstance(result, PlannerResult) else result).to_dict()
    if runtime.stable_hash() != d['starting_runtime_hash']:
        return {'status': 'PLAN_STALE_REFERENCE'}
    turn = runtime.state.mechanics[KEY]; boundary = turn['decision']; choice = d['chosen_action']
    if not choice or not boundary or boundary['decision_id'] != d['decision_id']:
        return {'status': 'PLAN_STALE_REFERENCE'}
    try:
        choices, _ = enumerate_choices(runtime, boundary['decision_id'], d['request']['budgets']['max_candidates'])
        if choice not in choices: return {'status': 'PLAN_STALE_REFERENCE'}
        permission = next(p for p in runtime.legal_action_candidates(boundary['decision_id']) if p['action_id'] == choice['action_id'])
        return {'status': 'PLAN_VALID_REFERENCE', 'permission': permission, 'targets': choice['targets'],
                'expected_revision': boundary['state_revision']}
    except (TurnError, StopIteration): return {'status': 'PLAN_STALE_REFERENCE'}


def replay_principal_variation(runtime, result, *, opponent_provider=None):
    d = PlannerResult.from_dict(result.to_dict() if isinstance(result, PlannerResult) else result).to_dict()
    branch = runtime.clone()
    if branch.stable_hash() != d['starting_runtime_hash']: raise PlannerGap('REPLAY_MISMATCH', 'initial runtime')
    for step in d['principal_variation']:
        if branch.stable_hash() != step['prehash']: raise PlannerGap('REPLAY_MISMATCH', 'step prehash')
        if step['kind'] == 'advance': branch.run_until_encounter_boundary(**step['arguments'])
        elif step['kind'] == 'enemy': branch.request_enemy_decision(opponent_provider)
        else:
            args = step['arguments']; old = args['permission']
            fresh = next((p for p in branch.legal_action_candidates(old['decision_id']) if p['action_id'] == old['action_id']), None)
            if fresh != old: raise PlannerGap('REPLAY_MISMATCH', 'permission provenance')
            branch.submit_action(fresh, args['targets'], args['expected_revision'])
        if branch.stable_hash() != step['posthash']: raise PlannerGap('REPLAY_MISMATCH', 'step posthash')
    if d['chosen_branch'] and branch.snapshot() != d['chosen_branch']['runtime_snapshot']:
        raise PlannerGap('REPLAY_MISMATCH', 'final snapshot')
    return branch
