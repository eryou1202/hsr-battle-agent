"""Original decoded R20 completion roots with additional explicit turn inputs.

No source graph, completion node, native legality or Skill join is invented.
The action and its pinned IR hash are selected from the frozen corpus receipt.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE
from r13_reference_fixtures import fixture
from r19_reference_fixtures import extend as property_extend
from r20_reference_fixtures import extend, actor_binding
from r22_reference_fixtures import inputs

ROOT = Path(__file__).resolve().parents[2]
REAL_ROOTS = ('Avatar_Anaxa_00_Skill01_Phase02', 'Avatar_Lingsha_00_Skill01_Phase02', 'Avatar_Sparkle_00_Skill01_Phase02')


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def real_runtime(name=REAL_ROOTS[0], *, initialize=True):
    corpus = read('data/control/generic_runtime_real_combat_corpus_v2_20261008_001.json')
    graph = next(g for g in corpus['graphs'] if g['record_identity'] == name)
    ir = IRNode.from_dict(read(graph['IR_artifact']))
    if ir.stable_hash() != graph['canonical_IR_hash']:
        raise ValueError('frozen real IR changed')
    prior = read('tmp/audit/r20_actor_resource_progression_20261010_001/actor_cohort_results.json')
    row = next(x for x in prior if x['source_identity'] == graph['source_identity'])
    assert row['status'] == 'ACTION_REFERENCE_COMPLETE' and not row['full_joined_skill_transition']
    original = read('tmp/audit/r18_damage_hp_settlement_20261009_001/joined_explicit_inputs.json')
    state = BehaviorBattleState.from_snapshot(original['state'])
    nodes = list(walk_nodes(ir))
    _, aliases, _ = fixture({n.payload['alias'] for n in nodes if n.op == 'RPG.GameCore.TargetAlias'})
    policies = copy.deepcopy(original['policies'])
    # Keep the approved source-task bindings needed by this exact original IR.
    hashes = {n.stable_hash() for n in nodes}
    policies[DAMAGE]['tasks'] = {k: v for k, v in policies[DAMAGE]['tasks'].items() if k in hashes}
    state, policies = property_extend(state, policies, nodes)
    r = BehaviorRuntime(state, actions={'real': ir}, aliases=aliases, policies=policies)
    extend(r, nodes, avatar_id=row['actor_id'], activation=True)
    # Explicit R22 scenario speed is supplied to the existing authoritative store.
    r.state.properties['a']['speed'] = 200*SCALE
    r.bind_actor(actor_binding('b', 1001, base_properties={'speed': 100*SCALE, 'hp': 100*SCALE,
        'max_hp': 100*SCALE, 'reference_atk': 10*SCALE}, actor_resources={'reference_actor_counter': 0}))
    bindings, p, providers = inputs(r, (('a', 200), ('b', 100)))
    for binding in bindings:
        binding['actor_binding'] = None  # Reuse verified R20 actors without replacing HP/resources.
    providers['availability']['actors']['a']['actions'][0]['target_ids'] = ['b']
    providers['availability']['actors']['b']['actions'][0]['target_ids'] = ['a']
    if initialize:
        r.initialize_turns(bindings, p, providers)
    return r, graph, bindings, p, providers
