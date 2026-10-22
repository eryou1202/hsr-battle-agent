"""P01-P20 simulator-backed planner evidence; no native tactical claim."""
import copy
import json
import sys
import unittest
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from hsr_battle_agent.battle_ir.behavior import stable_hash, walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.battle_turn import KEY, PROVIDERS, TurnError
from hsr_battle_agent.battle_runtime.planner_bridge import (
    plan, PlannerRequest, PlannerResult, PlannerGap, enumerate_choices,
    validate_recommendation, replay_principal_variation, ALGORITHMS)
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from r26_reference_fixtures import encounter, request


@lru_cache(maxsize=20)
def sample(kind='choice', algorithm='BEAM_SEARCH_REFERENCE', horizon=4, width=4):
    r, original = encounter(kind)
    result = plan(r, request(r, algorithm=algorithm, horizon=horizon, width=width)).to_dict()
    return r.snapshot(), result, original


def cached(kind='choice', algorithm='BEAM_SEARCH_REFERENCE', horizon=4, width=4):
    s, d, source = sample(kind, algorithm, horizon, width)
    return BehaviorRuntime.from_snapshot(copy.deepcopy(s)), copy.deepcopy(d), source


def comparison(kind):
    """Same initial snapshot, scoring, AI, RNG and four controlled decisions.

    Greedy repeats actual one-step recommendations to the same evaluation cap.
    All measurements come from R22/R25 execution, including its enemy provider.
    """
    initial, _, _ = cached(kind)
    rows = []
    for algorithm in ALGORITHMS:
        r = initial.clone(); steps = []; used = 0; counters = {}; incomplete = 0
        while used < 4:
            d = plan(r, request(r, algorithm=algorithm, horizon=4-used, width=4)).to_dict()
            for key, value in d['counts'].items(): counters[key] = counters.get(key,0)+value
            incomplete += d['incomplete_rollouts']
            if not d['chosen_action']: break
            r = replay_principal_variation(r, d)
            used += d['chosen_branch']['depth']; steps.append(d)
            if r.encounter_result() or algorithm != 'ONE_STEP_GREEDY_REFERENCE': break
        assert steps
        last = steps[-1]['chosen_branch']
        rows.append({'algorithm': algorithm, 'initial_hash': initial.stable_hash(),
            'scoring_hash': stable_hash(steps[0]['request']['scoring_policy']),
            'opponent_hash': stable_hash(steps[0]['opponent_policy_identity']),
            'chosen_first_action': steps[0]['chosen_action'], 'terminal': r.encounter_result(),
            'evaluation': last['evaluation'], 'normal_turns': r.state.mechanics[KEY]['normal_turn_count'],
            'hp': copy.deepcopy(r.state.properties), 'resources': copy.deepcopy(r.state.actor_resources),
            'counts': counters, 'incomplete_branches': incomplete, 'searches': steps})
    return rows


class R26Scenarios(unittest.TestCase):
    def capture(self, d, **extra): self.observation = {'result': d, **extra}

    def test_P01_two_actions_victory_vs_defeat(self):
        r, d, _ = cached()
        self.assertEqual(d['chosen_action']['action_id'], '10-fast')
        self.assertEqual([x['status'] for x in d['ranked_alternatives']], ['TERMINAL_VICTORY','TERMINAL_DEFEAT'])
        self.assertEqual(replay_principal_variation(r,d).encounter_result()['result'], 'VICTORY')
        self.capture(d)

    def test_P02_two_winning_policies_fewer_turns(self):
        _, d, _ = cached('turns', horizon=3)
        self.assertTrue(all(x['status'] == 'TERMINAL_VICTORY' for x in d['ranked_alternatives']))
        self.assertEqual(d['chosen_action']['action_id'], '10-fast')
        turns = [x['evaluation']['predicted']['normal_turns'] for x in d['ranked_alternatives']]
        self.assertLess(turns[0], turns[1]); self.capture(d)

    def test_P03_two_wave_resource_conservation(self):
        r, d, _ = cached('resource')
        self.assertEqual(d['chosen_action']['action_id'], '10-save:b')
        end = replay_principal_variation(r,d)
        self.assertEqual(end.encounter_result()['result'], 'VICTORY')
        self.assertEqual(end.state.actor_resources['a']['reference_actor_counter'], 0)
        self.assertEqual(end.state.mechanics[KEY]['stage']['wave_index'],1)
        self.capture(d)

    def test_P04_beam_beats_one_step_greedy(self):
        rows = comparison('resource')
        self.assertEqual(len({x['initial_hash'] for x in rows}),1)
        self.assertEqual(len({x['scoring_hash'] for x in rows}),1)
        self.assertEqual(len({x['opponent_hash'] for x in rows}),1)
        self.assertEqual([x['terminal']['result'] for x in rows], ['DEFEAT','DEFEAT','VICTORY'])
        self.assertEqual(rows[1]['chosen_first_action']['action_id'],'00-burst:b')
        self.capture(rows[-1]['searches'][0], comparative_benchmarks=rows)

    def test_P05_distinct_targets_distinct_outcomes(self):
        r, d, source = cached('targets', horizon=3)
        self.assertEqual(d['chosen_action']['targets'], ['b','c'])
        self.assertEqual({x['status'] for x in d['ranked_alternatives']}, {'TERMINAL_VICTORY','TERMINAL_DEFEAT'})
        choices, total = enumerate_choices(r, d['decision_id'],10)
        self.assertEqual(total,3); self.assertEqual([x['targets'] for x in choices],[['b'],['b','c'],['c']])
        self.capture(d, source_hash=source)

    def test_P06_stale_permission_clone_parent_isolation(self):
        r, _ = encounter(); before = r.snapshot(); q = request(r)
        branch = r.clone(); p = branch.legal_action_candidates(q.decision_id)[0]
        branch.submit_action(p,p['target_ids'],p['state_revision'])
        prior = branch.snapshot()
        with self.assertRaises(TurnError): branch.submit_action(p,p['target_ids'],p['state_revision'])
        self.assertEqual(branch.snapshot(),prior); self.assertEqual(r.snapshot(),before)
        self.observation = {'parent_hash': r.stable_hash(), 'stale_rejected':True, 'parent_unchanged':True}

    def test_P07_external_enemy_provider_deterministic(self):
        r, _ = encounter(); identity = copy.deepcopy(r.policies[PROVIDERS]['monster_decision'])
        class Provider:
            def choose(self, **kw):
                self.calls += 1
                p = kw['permissions'][0]
                return {'permission':p,'targets':p['target_ids'][:1]}
        provider = Provider(); provider.identity=identity; provider.calls=0
        one = plan(r,request(r),opponent_provider=provider).to_dict()
        calls=provider.calls
        two = plan(r,request(r),opponent_provider=provider).to_dict()
        self.assertGreater(calls,0); self.assertEqual(provider.calls,2*calls); self.assertEqual(one,two)
        replay_principal_variation(r,one,opponent_provider=provider)
        self.capture(one, provider_calls=calls)

    def test_P08_missing_opponent_typed_incomplete(self):
        r,_=encounter(); d=plan(r,request(r,opponent=False)).to_dict()
        blocked=[b for b in d['ranked_alternatives'] if b['status']=='OPPONENT_POLICY_MISSING']
        self.assertEqual(len(blocked),1); self.assertEqual(blocked[0]['evaluation']['classification'],'BLOCKED')
        self.assertEqual(d['opponent_policy_identity'],None); self.capture(d)

    def test_P09_semantic_gap_alternative_retained(self):
        _,d,_=cached('gap',horizon=2)
        self.assertEqual(d['chosen_action']['action_id'],'10-fast')
        self.assertEqual(len(d['semantic_gaps']),1)
        self.assertEqual(d['semantic_gaps'][0]['evaluation']['classification'],'BLOCKED')
        self.assertEqual(len(d['ranked_alternatives']),2)
        self.assertFalse(d['coverage']['globally_optimal']); self.capture(d)

    def test_P10_budget_yield_resumes_without_double_actions(self):
        r,_=encounter(); q=request(r,horizon=2,budgets={'scheduler_quantum':8,'transition_quantum':8,'max_yields':150})
        d=plan(r,q).to_dict(); self.assertGreater(d['counts']['budget_yields'],0)
        self.assertEqual(d['predicted_terminal_result'],'VICTORY')
        end=replay_principal_variation(r,d)
        self.assertEqual(end.state.mechanics[KEY]['action_count'],1)
        self.capture(d)

    def test_P11_beam_width_reproducible_pruning(self):
        r,_=encounter('resource'); q=request(r,horizon=3,width=1)
        d=plan(r,q).to_dict(); self.assertEqual(plan(r.clone(),q).to_dict(),d)
        self.assertTrue(d['coverage']['pruned_branch_ids'])
        _,wide,_=cached('resource')
        self.assertEqual(wide['predicted_terminal_result'],'VICTORY')
        self.assertNotEqual(d['chosen_branch']['status'],wide['chosen_branch']['status'])
        self.capture(d, wide_chosen=wide['chosen_action'])

    def test_P12_stable_ties_and_input_permutations(self):
        weights={k:0 for k in request(encounter()[0]).scoring_policy['weights']}
        outcomes=[]
        for reverse in (False,True):
            r,_=encounter('tie',permute=reverse)
            d=plan(r,request(r,horizon=1,weights=weights)).to_dict()
            outcomes.append((d['chosen_action'],[x['evaluation'] for x in d['ranked_alternatives']]))
        self.assertEqual(outcomes[0],outcomes[1]); self.assertEqual(d['chosen_action']['action_id'],'00-slow'); self.capture(d)

    def test_P13_persistent_shield_changes_downstream_value(self):
        r,d,_=cached('defense',horizon=3)
        self.assertEqual(d['predicted_terminal_result'],'VICTORY')
        self.assertEqual(d['chosen_branch']['depth'],2)
        end=replay_principal_variation(r,d)
        actor=end.state.mechanics['r24_defense_break_reference_v1']['actors']['b']
        self.assertEqual(actor['shields']['value'],[])
        self.assertEqual(end.state.properties['b']['hp'],0)
        self.assertTrue(any(s['before']['hp']['b']==s['after']['hp']['b'] for s in d['principal_variation']))
        self.capture(d)

    def test_P14_R20_costs_gains_change_permissions(self):
        r,_=encounter('resource'); before=r.snapshot(); b=r.state.mechanics[KEY]['decision']
        choices,total=enumerate_choices(r,b['decision_id'],10); self.assertEqual(total,2)
        p=next(p for p in r.legal_action_candidates(b['decision_id']) if p['action_id']=='00-burst:b')
        r.submit_action(p,['b'],p['state_revision']); next_b=r.run_until_encounter_boundary()
        self.assertEqual(r.state.actor_resources['a']['reference_actor_counter'],0)
        self.assertEqual([p['action_id'] for p in r.legal_action_candidates(next_b['decision_id'])],['10-save:c'])
        # R20 gain runs through R15 in a separately authored fixture action.
        from tests.battle_runtime.test_behavior_r15 import task,ability,finish
        from r20_reference_fixtures import resource_spec
        from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE
        from r26_reference_fixtures import spec,provenance,cost
        from r25_reference_fixtures import setup
        g,args,_=setup(waves=1,initialize=False,player_damage=1)
        g.policies[RESOURCE]={'identity':RESOURCE,'authority':'REFERENCE_MODEL','evidence':'R26 explicit gain','bindings':{'gain':resource_spec(amount=SCALE)}}
        g.actions['gain']=ability('gain-reference',task('gain','resource_mutation_reference',binding='gain'),finish())
        binding=args['actor_inputs']['a']
        binding['actor_binding']['fields']['actor_resources']['value']['reference_actor_counter']=0
        args['definition']['actors']['a']['binding_hash']=stable_hash(binding)
        row=args['definition']['waves'][0]['availability']['a']
        row['actions']=[spec(g,'gain',['b']),spec(g,'player:b',['b'],cost(g,'after-gain-cost',1))]
        args['provider_contracts']['availability']['actors']['a']=copy.deepcopy(row); provenance(args['definition'])
        g.initialize_encounter(**args); b=g.run_until_encounter_boundary(); p=g.legal_action_candidates(b['decision_id'])[0]
        self.assertEqual([x['action_id'] for x in g.legal_action_candidates(b['decision_id'])],['gain'])
        g.submit_action(p,['b'],p['state_revision']); b=g.run_until_encounter_boundary()
        if b.kind=='ENEMY_AI_DECISION': g.request_enemy_decision(); b=g.run_until_encounter_boundary()
        self.assertEqual(g.state.actor_resources['a']['reference_actor_counter'],SCALE)
        unlocked=[x['action_id'] for x in g.legal_action_candidates(b['decision_id'])]
        self.assertEqual(unlocked,['gain','player:b'])
        self.observation={'cost_balance':0,'gain_balance':SCALE,'gain_unlocked_permissions':unlocked,
                          'next_wave_permissions':['10-save:c'],'initial_hash':stable_hash(before)}

    def test_P15_wave_targets_refresh_permissions(self):
        r,d,_=cached('resource'); steps=d['principal_variation']
        submits=[s for s in steps if s['kind']=='submit']
        self.assertEqual([s['arguments']['targets'] for s in submits],[['b'],['b'],['c']])
        self.assertNotEqual(submits[0]['arguments']['permission']['permission_id'],submits[-1]['arguments']['permission']['permission_id'])
        self.assertEqual(replay_principal_variation(r,d).encounter_result()['wave_index'],1); self.capture(d)

    def test_P16_midpoint_snapshot_request_replay(self):
        r,_=encounter('resource'); b=r.state.mechanics[KEY]['decision']
        p=next(p for p in r.legal_action_candidates(b['decision_id']) if p['action_id']=='10-save:b')
        r.submit_action(p,['b'],p['state_revision']); r.run_until_encounter_boundary()
        q=PlannerRequest.from_dict(json.loads(json.dumps(request(r,horizon=3).to_dict())))
        restored=BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot())))
        one=plan(r,q).to_dict(); two=plan(restored,q).to_dict()
        self.assertEqual(one,two); self.assertEqual(plan(r.clone(),q).to_dict(),one)
        replay_principal_variation(restored,one); self.capture(one)

    def test_P17_original_complete_snapshot_immutable(self):
        r,_=encounter(); before=json.dumps(r.snapshot(),sort_keys=True).encode(); prior=r.stable_hash()
        d=plan(r,request(r,horizon=2)).to_dict()
        self.assertEqual(before,json.dumps(r.snapshot(),sort_keys=True).encode()); self.assertEqual(prior,r.stable_hash())
        self.assertEqual(validate_recommendation(r,d)['status'],'PLAN_VALID_REFERENCE')
        p=validate_recommendation(r,d); r.submit_action(p['permission'],p['targets'],p['expected_revision'])
        self.assertEqual(validate_recommendation(r,d)['status'],'PLAN_STALE_REFERENCE')
        self.capture(d,complete_snapshot_byte_equal=True)

    def test_P18_original_real_damage_primitive(self):
        r,d,original=cached('real',horizon=2)
        self.assertEqual(d['chosen_action']['action_id'],'player:b')
        self.assertEqual(d['predicted_terminal_result'],'VICTORY')
        nodes=list(walk_nodes(r.actions['player:b']))
        self.assertTrue(any(n.stable_hash()==original for n in nodes))
        end=replay_principal_variation(r,d)
        self.assertGreater(len(end.state.damage_history),0)
        self.capture(d,cohort='REAL_PRIMITIVE_REFERENCE_PLANNING',source_hash=original,
                     full_joined_skill_planning=0,native_validated_planning=0)

    def test_P19_terminal_no_recommendation(self):
        r,d,_=cached(); end=replay_principal_variation(r,d)
        final=plan(end,request(end,horizon=2)).to_dict()
        self.assertIsNone(final['chosen_action']); self.assertEqual(final['root_status'],'TERMINAL_VICTORY')
        self.assertEqual(end.state.mechanics[KEY]['permissions'],[]); self.capture(final)

    def test_P20_multi_actor_three_actions_bounded(self):
        r,_=encounter('multi'); q=request(r,horizon=3,width=3,budgets={'max_total_nodes':15,'max_candidates':30})
        d=plan(r,q).to_dict()
        self.assertEqual(len(q.controlled_actors),2)
        self.assertFalse(d['semantic_gaps'],[(g['status'],g['reason']) for g in d['semantic_gaps']])
        self.assertEqual(d['coverage']['enumerations'][0]['legal_choices'],3)
        self.assertLessEqual(d['counts']['nodes_expanded'],15); self.assertLessEqual(d['counts']['candidates_enumerated'],30)
        self.assertLessEqual(d['counts']['simulated_actions'],q.budgets['max_simulated_actions'])
        self.assertLessEqual(d['counts']['scheduler_work_reserved'],q.budgets['max_scheduler_work'])
        self.assertLessEqual(d['counts']['encounter_transitions_reserved'],q.budgets['max_encounter_transitions'])
        self.assertEqual(PlannerResult.from_dict(json.loads(json.dumps(d))).to_dict(),d)
        self.capture(d)


class R26Contracts(unittest.TestCase):
    def test_each_hard_budget_stops_without_fake_terminal(self):
        r,_=encounter(); before=r.snapshot()
        for cap in ({'max_simulator_transitions':1},{'max_simulated_actions':1},
                    {'max_trace_bytes':1},{'max_candidates':1}):
            with self.subTest(cap=cap):
                d=plan(r,request(r,horizon=2,budgets=cap)).to_dict()
                self.assertLessEqual(d['counts']['simulator_transitions'],d['request']['budgets']['max_simulator_transitions'])
                self.assertLessEqual(d['counts']['trace_bytes'],d['request']['budgets']['max_trace_bytes'])
                self.assertLessEqual(d['counts']['candidates_enumerated'],d['request']['budgets']['max_candidates'])
                self.assertEqual(r.snapshot(),before)
                if not d['chosen_action']: self.assertNotEqual(d['predicted_terminal_result'],'VICTORY')

    def test_rng_and_event_queue_branch_isolation(self):
        r,_=encounter(); left=r.clone(); right=r.clone(); before=r.snapshot()
        left.state.rng.index(2); left.state.pending_events.append({'fixture':'left'})
        self.assertNotEqual(left.state.rng.draws,right.state.rng.draws)
        self.assertEqual(right.state.pending_events,r.state.pending_events)
        self.assertEqual(r.snapshot(),before)

    def test_missing_policy_typed(self):
        with self.assertRaises(PlannerGap): PlannerRequest.from_dict({})
        r,_=encounter(); q=request(r)
        for field,value in [('scoring_policy',{}),('opponent_policy',{}),('source_authority',{}),('budgets',{})]:
            with self.subTest(field=field), self.assertRaises(PlannerGap): plan(r,replace(q,**{field:value}))

    def test_budget_truncation_not_victory(self):
        r,_=encounter(); d=plan(r,request(r,budgets={'max_scheduler_work':1,'scheduler_quantum':1,'max_total_nodes':1})).to_dict()
        self.assertNotEqual(d['predicted_terminal_result'],'VICTORY')
        self.assertTrue(d['truncated_rollouts'] or d['root_status']=='SEARCH_BUDGET_TRUNCATED')

    def test_changed_policy_rejected(self):
        r,_=encounter(); q=request(r); r.policies['changed']={}
        with self.assertRaises(PlannerGap) as c: plan(r,q)
        self.assertEqual(c.exception.code,'POLICY_MISMATCH')

    def test_result_tamper_rejected(self):
        _,d,_=cached(); d['chosen_action']['targets']=['wrong']
        with self.assertRaises(PlannerGap): PlannerResult.from_dict(d)


if __name__=='__main__': unittest.main()
