"""Authored multi-choice encounters. Never native character planning rules."""
import copy
from hsr_battle_agent.battle_ir.behavior import stable_hash, TargetSelectorIR
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.planner_bridge import PlannerRequest, METRICS
from hsr_battle_agent.battle_runtime.battle_turn import PROVIDERS
from hsr_battle_agent.battle_runtime.resource_engine import POLICY_ID as RESOURCE, reference_policy
from tests.battle_runtime.test_behavior_r15 import ability, finish, task, expr, A
from tests.battle_runtime.test_behavior_r24 import initial, shield
from r25_reference_fixtures import setup, hit, provenance
from r20_reference_fixtures import resource_spec


def request(r, *, algorithm='BEAM_SEARCH_REFERENCE', horizon=5, width=8, weights=None, budgets=None, opponent=True):
    b = r.state.mechanics['battle_turn_v1']['decision']
    weights = weights if weights is not None else {'team_hp': 1, 'enemy_hp': -1, 'resources': 0,
        'normal_turns': -SCALE, 'av': 0, 'enemies_remaining': 0, 'waves_completed': 100*SCALE, 'shield': 0}
    assert set(weights) == set(METRICS)
    caps = {'max_total_nodes': 200, 'max_simulated_actions': 400, 'max_simulator_transitions': 1200,
        'max_scheduler_work': 200000, 'max_encounter_transitions': 200000, 'max_opponent_actions': 200,
        'max_candidates': 500, 'max_trace_bytes': 4000000, 'max_branch_actions': 30,
        'scheduler_quantum': 256, 'transition_quantum': 128, 'max_yields': 30}
    caps.update(budgets or {})
    return PlannerRequest(r.stable_hash(), b['decision_id'], 'players',
        tuple(sorted(a for a,e in r.state.entities.items() if e.get('team') == 'players')),
        algorithm, width, horizon, caps,
        {'identity': 'r26.authored.terminal_hp_turn_wave/1', 'terminal_order': ['VICTORY','PARTIAL','DEFEAT','BLOCKED'],
         'partial_assumption': 'UNCERTAIN_ABOVE_DEFEAT_REFERENCE', 'weights': weights},
        {'identity': copy.deepcopy(r.policies[PROVIDERS].get('monster_decision')) if opponent else None, 'missing': 'STOP_TYPED'},
        'ACTION_TARGET_UTF8_ASC', {'truncated': 'SCORE_PARTIAL_UNCERTAIN', 'blocked': 'RETAIN_REPORT_BELOW_DEFEAT',
                                  'budget_yield': 'RESUME_BOUNDED', 'unsupported': 'STOP_TYPED'},
        {'authority': 'REFERENCE_MODEL', 'source_version': '4.6.51',
         'evidence': 'R26 authored encounter and scoring; native tactical correctness not claimed'},
        stable_hash(r.policies))


def spec(r, name, targets, cost=None):
    return {'action_id': name, 'ir_hash': r.actions[name].stable_hash(), 'target_ids': list(targets),
            'target_min': 1, 'target_max': 1, 'categories': ['NORMAL_TURN'],
            'cost': cost or {'mode': 'EXPLICIT_NO_COST_REFERENCE', 'authority': 'EXPLICIT_SCENARIO_INPUT'}}


def cost(r, identity, amount):
    r.policies.setdefault(RESOURCE, reference_policy())
    row = resource_spec(amount=amount*SCALE, operation='SUBTRACT')
    row.update(cost_authority='EXPLICIT_SCENARIO_INPUT', cost_source='R26 authored limited resource')
    r.policies[RESOURCE]['bindings'][identity] = row
    return {'mode': 'R20_COST_TASKS_REFERENCE', 'authority': 'EXPLICIT_SCENARIO_INPUT',
            'tasks': [task(identity, 'resource_cost_reference', binding=identity).to_dict()]}


def encounter(kind='choice', *, permute=False):
    """Build via unchanged R25 initializer with explicit per-wave availability."""
    two_wave = kind in ('resource', 'multi')
    targeted = kind == 'targets'
    real = kind == 'real' or targeted
    r, args, original = setup(waves=2 if two_wave or targeted else 1, initialize=False,
                            enemy_damage=100 if kind in ('choice','resource','targets') else 0, real=real)
    definition = args['definition']; providers = args['provider_contracts']
    if targeted:
        # Only the reference alias binding changes; original decoded IR stays byte-identical.
        r.aliases = {key: TargetSelectorIR('r26-selected-targets', 'SkillTargetEntityList', A, {}) for key in r.aliases}
        r.actions['strike'] = r.actions.pop('player:b')
        r.actions.pop('player:c', None)
        r.actions['monster:b'] = ability('harmless-reference', hit('harmless', 'b', 'a', 0), finish())
        wave = definition['waves'][0]
        wave['actor_refs'] = ['b','c']
        wave['availability']['a']['actions'] = [spec(r, 'strike', ['b','c'])]
        # R22 validates the permission's full pool during candidate retrieval.
        # Its currently supported pool therefore also permits the full selection.
        wave['availability']['a']['actions'][0]['target_max'] = 2
        wave['availability']['b']['actions'] = [spec(r, 'monster:b', ['a'])]
        wave['availability']['c'] = copy.deepcopy(definition['waves'][1]['availability']['c'])
        definition['waves'] = [wave]
    elif real:
        r.actions['00-wait'] = ability('reference-wait', finish())
        wave = definition['waves'][0]
        wave['availability']['a']['actions'] = [spec(r, '00-wait', ['b']), spec(r, 'player:b', ['b'])]
    else:
        for i, wave in enumerate(definition['waves']):
            enemy = wave['actor_refs'][0]
            if kind in ('resource','multi'):
                r.actions['00-burst:'+enemy] = ability('authored-burst-'+enemy, hit('burst-'+enemy, 'a', enemy, 30), finish())
                r.actions['10-save:'+enemy] = ability('authored-save-'+enemy, hit('save-'+enemy, 'a', enemy, 5), finish())
                c = cost(r, 'cost-'+enemy, 4)
                actions = [spec(r, '00-burst:'+enemy, [enemy], c), spec(r, '10-save:'+enemy, [enemy])]
                if enemy == 'b':
                    r.actions['monster:b'] = ability('reference-harmless-first-wave', hit('enemy-hit-b','b','a',0), finish())
                    wave['availability']['b']['actions'] = [spec(r,'monster:b',['a'])]
                else:
                    args['actor_inputs'][enemy]['actor_binding']['fields']['base_properties']['value']['hp'] = 30*SCALE
            else:
                low, high = (10,20) if kind == 'turns' else (1,10)
                if kind == 'tie': low, high = 1,1
                r.actions['00-slow'] = ability('authored-slow', hit('slow', 'a', enemy, low), finish())
                r.actions['10-fast'] = ability('authored-fast', hit('fast', 'a', enemy, high), finish())
                if kind == 'turns': args['actor_inputs'][enemy]['actor_binding']['fields']['base_properties']['value']['hp'] = 20*SCALE
                if kind == 'gap': r.actions['00-slow'] = ability('authored-gap', task('gap','r26_deliberately_unsupported'), finish())
                actions = [spec(r, '00-slow', [enemy]), spec(r, '10-fast', [enemy])]
            if kind == 'defense':
                args['actor_inputs'][enemy]['actor_binding']['fields']['defense']['value'] = initial([shield(capacity=10, owner=enemy)])
            wave['availability']['a']['actions'] = actions
    if kind == 'multi':
        from r22_reference_fixtures import inputs
        from hsr_battle_agent.battle_runtime.actor_binding import supplied
        rows, _, extra = inputs(r, speeds=(('d',180),))
        d = rows[0]; d['participant']['registration_ordinal'] = 1
        # Initial players precede every later spawn in R22's monotonic domain.
        args['actor_inputs']['b']['participant']['registration_ordinal'] = 2
        args['actor_inputs']['c']['participant']['registration_ordinal'] = 3
        d['actor_binding']['fields']['entity_state'] = supplied({'alive':True})
        d['actor_binding']['fields']['team'] = supplied('players')
        d['actor_binding']['fields']['defense'] = supplied(initial())
        args['actor_inputs']['d'] = d; definition['initial_actor_refs'].append('d')
        providers['speeds']['d'] = extra['speeds']['d']
        for wave in definition['waves']:
            enemy = wave['actor_refs'][0]
            r.actions['20-poke:'+enemy] = ability('poke-'+enemy, hit('poke-'+enemy,'d',enemy,2), finish())
            wave['availability']['a']['actions'].append(spec(r,'20-poke:'+enemy,[enemy]))
            wave['availability']['d'] = copy.deepcopy(wave['availability']['a'])
    for actor, binding in args['actor_inputs'].items():
        definition['actors'][actor] = {'side': 'players' if actor in ('a','d') else 'targets', 'binding_hash': stable_hash(binding)}
    for wave in definition['waves']:
        if permute:
            for row in wave['availability'].values(): row['actions'].reverse()
        for actor, row in wave['availability'].items():
            providers['availability']['actors'][actor] = copy.deepcopy(row)
    providers['availability']['actors'].update(copy.deepcopy(definition['waves'][0]['availability']))
    provenance(definition)
    r.initialize_encounter(**args)
    r.run_until_encounter_boundary()
    return r, original
