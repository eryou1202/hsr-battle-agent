"""Authored encounter inputs. Source actor identities are fixtures, never engine logic."""
import copy
from hsr_battle_agent.battle_ir.behavior import stable_hash
from hsr_battle_agent.battle_runtime.actor_binding import supplied
from hsr_battle_agent.battle_runtime.encounter_runtime import reference_policy, _pointer_leaves
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.defense_break import reference_policy as defense_policy, POLICY_ID as DEFENSE
from hsr_battle_agent.battle_runtime.modifier_lifecycle import reference_policy as modifier_policy, POLICY_ID as MODIFIER
from tests.battle_runtime.test_behavior_r15 import R15Tests, ability, finish, task, expr
from tests.battle_runtime.test_behavior_r24 import initial, settlement
from r22_reference_fixtures import inputs

def provenance(d):
    d['provenance'] = {p: {'authority': 'EXPLICIT_SCENARIO_INPUT', 'source_version': d['source_version'],
        'evidence': 'R25 authored reference encounter; native value/rule not claimed'}
        for p in _pointer_leaves({k: v for k, v in d.items() if k != 'provenance'})}
    return d

def hit(name, actor, target, amount):
    return task(name, 'reference_defense_request', authority='EXPLICIT_SCENARIO_INPUT', actor=actor, target=target,
        source='R25 authored reference damage', amount_raw=amount*SCALE, shield='APPLY_REFERENCE',
        toughness=None, hp_settlement=settlement())

def flag(key='abort', expected=True):
    return {'kind': 'EXPLICIT_OBJECTIVE_FLAG_REFERENCE', 'scope': 'encounter_flags', 'key': key, 'expected': expected}

def setup(*, waves=2, player_damage=10, enemy_damage=3, player_hp=100, enemy_hp=10,
          player_suffix=(), initialize=True, real=False):
    enemies = [chr(ord('b')+i) for i in range(waves)]
    r = R15Tests().runtime(ability('placeholder', finish()))
    r.actions = {}
    for enemy in enemies:
        r.actions['player:'+enemy] = ability('reference-player-'+enemy, hit('hit-'+enemy, 'a', enemy, player_damage),
            task('counter', 'resource_write', scope='actor', owner='a', key='reference_actor_counter',
                 operation='add', value=expr(SCALE, True)), *player_suffix, finish())
        r.actions['monster:'+enemy] = ability('reference-monster-'+enemy, hit('enemy-hit-'+enemy, enemy, 'a', enemy_damage), finish())
    real_hash = None
    if real:
        from tests.battle_runtime.test_behavior_r24 import R24Scenarios
        source, nodes = R24Scenarios().real()
        r.actions['player:b'] = ability('reference-wrapper-real-primitive', *nodes, finish())
        r.policies.update(copy.deepcopy(source.policies))
        r.aliases = copy.deepcopy(source.aliases)
        r.state.dynamic_values.update(copy.deepcopy(source.state.dynamic_values))
        real_hash = nodes[0].stable_hash()
    if not real: r.policies[DEFENSE] = defense_policy()
    r.policies[MODIFIER] = modifier_policy()
    r.state.dynamic_values['encounter_flags'] = {'abort': False}
    speeds = [('a', 200)] + [(a, 150) for a in enemies]
    bindings, p, providers = inputs(r, speeds, controllers={a: 'MONSTER_AI' for a in enemies})
    providers['stage']['stage_id'] = 'r25-authored-reference-encounter'
    providers['monster_decision'] = {'provider_id': 'r25.first_permission', 'version': '1',
        'authority': 'REFERENCE_MODEL', 'mode': 'FIRST_PERMISSION_REFERENCE'}
    actor_inputs = {}
    for b in bindings:
        actor = b['participant']['actor_id']
        fields = b['actor_binding']['fields']
        fields['entity_state'] = supplied({'alive': True}, 'R25 explicit initial life state')
        fields['team'] = supplied('players' if actor == 'a' else 'targets')
        fields['base_properties']['value']['hp'] = (player_hp if actor == 'a' else enemy_hp)*SCALE
        fields['base_properties']['value']['reference_atk'] = 10*SCALE
        fields['defense'] = supplied(initial(current=10, maximum=10), 'R25 explicit R24 initial defense')
        actor_inputs[actor] = b
    def availability(actor, name, target):
        row = copy.deepcopy(providers['availability']['actors'][actor])
        row['actions'] = [x for x in row['actions'] if x['action_id'] == name]
        row['actions'][0]['target_ids'] = [target]
        return row
    wave_rows = []
    for i, enemy in enumerate(enemies):
        active = {'a': availability('a', 'player:'+enemy, enemy), enemy: availability(enemy, 'monster:'+enemy, 'a')}
        wave_rows.append({'wave_id': 'authored-wave-'+str(i), 'actor_refs': [enemy], 'availability': active,
            'objective': {'kind': 'ALL_TARGET_SIDE_DEFEATED_REFERENCE'}})
        providers['availability']['actors'][enemy] = active[enemy]
    providers['availability']['actors']['a'] = copy.deepcopy(wave_rows[0]['availability']['a'])
    policy = reference_policy()
    definition = provenance({'schema': 'reference_encounter_definition/1',
        'encounter_id': providers['stage']['stage_id'], 'content_version': '4.6.51', 'source_version': '4.6.51',
        'policy_hash': stable_hash(policy), 'sides': ['players', 'targets'], 'player_side': 'players', 'target_side': 'targets',
        'actors': {a: {'side': 'players' if a == 'a' else 'targets', 'binding_hash': stable_hash(b)} for a, b in actor_inputs.items()},
        'initial_actor_refs': ['a'], 'waves': wave_rows,
        'terminal_rules': {'victory': 'LAST_WAVE_OBJECTIVE_REFERENCE',
            'defeat': {'kind': 'ALL_PLAYER_SIDE_DEFEATED_REFERENCE'}, 'abort': flag(), 'conflict': 'SEMANTIC_GAP_REFERENCE'},
        'limits': {k: None for k in ('actor_registrations', 'wave_transitions', 'objective_evaluations',
            'stage_callbacks', 'normal_turns', 'scheduler_steps', 'zero_time_transitions')}})
    args = {'definition': definition, 'actor_inputs': actor_inputs, 'turn_policy': p,
            'provider_contracts': providers, 'policy': policy}
    if initialize: r.initialize_encounter(**args)
    return r, args, real_hash

def complete(r, max_commands=100, command=None, budget=10000):
    command = command or (lambda kind, **kwargs: r.record_encounter_command(kind, kwargs)[1])
    for _ in range(max_commands):
        b = command('advance', budget=budget)
        if b.kind == 'BUDGET_YIELD': continue
        if b.kind == 'BATTLE_TERMINAL': return b
        if b.kind == 'ENEMY_AI_DECISION':
            before = r.stable_hash()
            out = command('enemy')
            if before == r.stable_hash(): return out
        elif b.kind == 'PLAYER_NORMAL_TURN':
            candidate = r.legal_action_candidates(b['decision_id'])[0]
            command('submit', permission=candidate, targets=candidate['target_ids'], expected_revision=b['state_revision'])
        else: return b
    raise AssertionError('reference command bound exhausted')
