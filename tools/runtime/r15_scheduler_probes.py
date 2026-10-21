"""R15 frozen-control baseline and explicit synthetic scheduler corpus probes.
No source payload decoding, capture, native legality, or character execution rules.
"""
from __future__ import annotations
import collections
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).parent)]
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, ExecutionStatus
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID, reference_policy
from r13_reference_fixtures import fixture

AUDIT = ROOT / 'tmp/audit/r15_action_scheduler_20261008_001'
SUFFIX = '20261008_001'
COMBAT = {'ABILITY_CORPUS', 'PASSIVE_CORPUS', 'MODIFIER_CORPUS'}
CR = 'CR-R15-ACTION-EXECUTION-SCHEDULER-LIFECYCLE-20261008-001'
SCHEDULER = {'TriggerAbility', 'WaitSecond', 'WaitAnimState', 'WaitTimelineFinish', 'SkillPerformFinish'}
# These are authored assumptions for this synthetic scenario, each individually
# declared. R14 taxonomy is structural/planning evidence, never irrelevance proof.
INSTANT = ['TriggerAnimState', 'TriggerEffect', 'CharacterPlayVO', 'LookAt', 'HeadLookAt',
    'GlobalMainIntensityEffect', 'RadialBlurEffect', 'SyncCharLightAndCameraDir',
    'VCameraConfigChange', 'PlayTimeline', 'RemoveEffect', 'ShowBattleUI', 'ShowBonusUIEffect',
    'HideLevelStage', 'SetEnergyBarState']


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def probe_policy():
    p = reference_policy()
    p['role_bindings'] = {
        'RPG.GameCore.TriggerAbility': {'slots': {'2': 'TargetType', '16': 'AbilityName'},
            'structure_only_masks': ['32'], 'authority': 'EXPLICIT_SYNTHETIC_REFERENCE_SLOT_BINDING',
            'native_names_or_resume_mode_claimed': False},
        'RPG.GameCore.WaitSecond': {'slots': {'2': 'duration'}, 'authority': 'EXPLICIT_SYNTHETIC_REFERENCE_SLOT_BINDING'}}
    p['waits'] = {'WaitSecond': {'classification': 'LOGICAL_DELAY_REFERENCE', 'duration_units': 'SERIALIZED_RAW_REFERENCE_UNITS'},
        'WaitAnimState': {'classification': 'BARRIER_ONLY_REFERENCE'},
        'WaitTimelineFinish': {'classification': 'BARRIER_ONLY_REFERENCE'}}
    p['presentation'] = {name: {'classification': 'PRESENTATION_INSTANT_REFERENCE',
        'authority': 'EXPLICIT_SYNTHETIC_SCENARIO_ASSUMPTION', 'native_relevance': 'UNKNOWN',
        'evidence': 'R14 serialized task identity and planning taxonomy; no native irrelevance claim'} for name in INSTANT}
    return p


def summary(probes):
    total = collections.Counter()
    for row in probes:
        total.update(row['metrics'])
    return {'roots': len(probes), 'roots_starting_execution': sum(r['started'] for r in probes),
        'first_gap_distribution': dict(collections.Counter(r['required_capability'] for r in probes if r['required_capability'])),
        'first_gap_primitive_distribution': dict(collections.Counter(r['primitive'] for r in probes if r['primitive'])),
        'first_gap_family_distribution': dict(collections.Counter(r['first_gap_family'] for r in probes if r['first_gap_family'])),
        'status_distribution': dict(collections.Counter(r['status'] for r in probes)),
        'metrics': dict(total), 'actions_reference_complete': sum(r['status'] == 'ACTION_REFERENCE_COMPLETE' for r in probes),
        'roots_reaching_child': sum(r['metrics']['abilities_invoked'] > 0 for r in probes),
        'roots_reaching_damage': sum('DamageByAttackProperty' in r['reached_types'] for r in probes),
        'roots_reaching_heal': sum('HealHP' in r['reached_types'] for r in probes),
        'roots_reaching_modifiers': sum(any(n in r['reached_types'] for n in ('AddModifier', 'RemoveModifier', 'modifier_apply', 'modifier_event_dispatch')) for r in probes),
        'roots_reaching_finish': sum('SkillPerformFinish' in r['reached_types'] for r in probes)}


def family(primitive, capability):
    op = (primitive or '').rsplit('.', 1)[-1]
    if 'catalog' in (capability or ''): return 'CONTENT_CATALOG_BINDING'
    if op == 'structure_record': return 'MODIFIER_EVENT'
    if op in ('DispelStatus', 'SetDynamicValueByModifierValue'): return 'MODIFIER_EVENT'
    if op in SCHEDULER or 'SCHEDULER_' in (capability or ''): return 'ACTION_EXECUTION_SCHEDULER'
    if op.startswith('Damage') or 'DAMAGE' in (capability or ''): return 'DAMAGE'
    if op in ('SetDynamicValue', 'SetDynamicValueByProperty', 'StackProperty'): return 'PROPERTY_DYNAMIC_PROVIDER'
    if op in ('AddModifier', 'RemoveModifier', 'SetDynamicValueByModifierValue') or 'modifier/event root' in (capability or ''): return 'MODIFIER_EVENT'
    if op == 'HealHP': return 'HEAL'
    if op == 'ModifySPNew': return 'RESOURCE'
    if op.startswith('By') or 'progression' in (capability or ''): return 'PREDICATE_PROGRESSION'
    if op.startswith('Move') or op == 'TriggerAnimStateWithMove': return 'POSITION'
    if 'catalog' in (capability or '') or op == 'IncludeTaskListTemplate': return 'CONTENT_CATALOG_BINDING'
    return 'OTHER_SEMANTICS'


def main():
    paths = [f'data/control/generic_runtime_{name}_{SUFFIX}.json' for name in [
        'real_combat_corpus_v2', 'skill_root_join_census_v1', 'support_census_v4', 'capability_discovery_v1', 'semantic_gap_ledger_v3']]
    controls = [read(p) for p in paths]
    corpus, joins, census, discovery, ledger = controls
    combat = [g for g in corpus['graphs'] if g['stratum'] in COMBAT]
    unique = {}
    for g in combat:
        for n in g['semantic_instances']:
            if n['family'] == 'task':
                unique[(g['source_shard_sha256'], n['type'], tuple(n['span']))] = n
    scheduler_nodes = [n for n in unique.values() if n['type'].rsplit('.', 1)[-1] in SCHEDULER]
    affected = [g for g in combat if any(n['family'] == 'task' and n['type'].rsplit('.', 1)[-1] in SCHEDULER for n in g['semantic_instances'])]
    baseline = {'control_pins': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        'combat_roots': len(combat), 'task_instances': len(unique),
        'scheduler_lifecycle_counts': dict(collections.Counter(n['type'].rsplit('.', 1)[-1] for n in scheduler_nodes)),
        'scheduler_lifecycle_instances': len(scheduler_nodes), 'graphs_affected': len(affected),
        'skill_roots_containing_scheduler': sum(g['skill_joined'] for g in affected),
        'joined_roots_first_gap_scheduler': sum(g['skill_joined'] and any((r.get('synthetic_reference_prefix_probe', {}).get('primitive') or '').rsplit('.', 1)[-1] in SCHEDULER
             for r in joins['rows'] if r.get('root_reference') == g['record_identity']) for g in combat),
        'frozen_first_gap_distribution': census['first_gap_distribution'],
        'r14_ranking_scheduler': next(r for r in discovery['rankings'] if r['family'] == 'SCHEDULER')}
    write(AUDIT.relative_to(ROOT) / 'r14_scheduler_baseline.json', baseline)
    print('Frozen baseline', json.dumps({k:v for k,v in baseline.items() if k not in ('control_pins', 'frozen_first_gap_distribution')}), flush=True)
    compiled = []
    for g in corpus['graphs']:
        ir = IRNode.from_dict(read(g['IR_artifact']))
        if ir.stable_hash() != g['canonical_IR_hash']:
            raise RuntimeError('frozen R14 IR hash drift: ' + g['IR_artifact'])
        compiled.append((g, ir))
    all_nodes = [n for _, ir in compiled for n in walk_nodes(ir)]
    state, aliases, r13 = fixture({n.payload.get('alias') for n in all_nodes if n.op == 'RPG.GameCore.TargetAlias'},
                                {n.payload['key'] for n in all_nodes if n.op == 'lookup'})
    catalogs = collections.defaultdict(list)
    for g, ir in compiled:
        if g['stratum'] in ('ABILITY_CORPUS', 'PASSIVE_CORPUS'):
            catalogs[g['record_identity']].append(ir)
    catalog = {key: entries[0] for key, entries in catalogs.items() if len(entries) == 1}
    policies = copy.deepcopy(r13); policies[POLICY_ID] = probe_policy()
    write(AUDIT.relative_to(ROOT) / 'reference_policy.json', {'policies': policies, 'scope': 'SYNTHETIC_REFERENCE_ONLY',
        'presentation_assumptions': INSTANT, 'movement_irrelevance_assumed': False,
        'native_equivalence_claimed': False, 'state': state.snapshot()})
    probes = {'before': [], 'after': []}
    elapsed = {}
    for phase in probes:
        start = time.perf_counter()
        for g, ir in compiled:
            if g['stratum'] not in COMBAT: continue
            runtime = BehaviorRuntime(state, actions={'probe': ir}, abilities=catalog, aliases=aliases,
                                      policies=r13 if phase == 'before' else policies)
            runtime.state.target_context['current_ability'] = g['record_identity']
            counter = collections.Counter(); reached = set(); before_calls=[]
            original = runtime.registry.invoke
            if phase == 'before':
                def record(fam, engine, node, local, original=original):
                    if fam == 'task':
                        counter['tasks_reached'] += 1; reached.add(node.op.rsplit('.', 1)[-1])
                    value = original(fam, engine, node, local)
                    if fam == 'task' and value != ExecutionStatus.WAITING_SCHEDULER:
                        counter['tasks_completed'] += 1
                        if node.op.rsplit('.', 1)[-1] == 'TriggerAbility': counter['abilities_invoked'] += 1
                        if node.op == 'reference_return': counter['child_abilities_completed'] += 1
                    return value
                runtime.registry.invoke = record
            adapter_error = None
            try:
                result = runtime.step('probe')
                gap = result.gap
                status = result.status.value
                primitive = gap.task_type if gap else None
                capability = gap.required_capability if gap else None
            except (AttributeError, TypeError, ValueError, KeyError) as exc:
                status = 'REFERENCE_ADAPTER_GAP'; primitive = None
                capability = 'generic reference adapter: ' + str(exc); adapter_error = type(exc).__name__
            if phase == 'after':
                d = runtime.state.scheduler.action_execution
                counter.update(d['metrics'])
                reached = {h['node']['op'].rsplit('.', 1)[-1] for h in d['history'] if h.get('status') == 'TASK_REACHED'}
                if primitive:
                    reached.add(primitive.rsplit('.', 1)[-1])
                    if gap.node['kind'] in ('TaskIR', 'UnsupportedSemanticIR'):
                        counter['tasks_reached'] += 1
            for key in ('tasks_reached', 'tasks_completed', 'abilities_invoked', 'child_abilities_completed', 'barriers_encountered', 'callbacks_completed', 'logical_time_advances'):
                counter.setdefault(key, 0)
            row = {'source_identity': g['source_identity'], 'root': g['record_identity'], 'IR_artifact': g['IR_artifact'],
                'skill_joined': g['skill_joined'], 'started': ir.op == 'ability', 'status': status,
                'primitive': primitive, 'required_capability': capability, 'first_gap_family': family(primitive, capability) if capability else None,
                'metrics': dict(counter), 'reached_types': sorted(reached), 'adapter_error': adapter_error,
                'scope': 'SYNTHETIC_REFERENCE_ONLY', 'native_executable': False}
            if phase == 'after':
                row['logical_time'] = d['logical_time']
                row['top_level_tasks_completed'] = sum(t['status'] == 'TASK_COMPLETE' and not t.get('container') and
                    t['ability_instance_id'] == d['roots'][d['current_root']]['root_ability_id'] and
                    len(d['sequences'][t['sequence_frame_id']]['ancestor_nodes']) == 1 for t in d['tasks'].values())
                row['state_hash'] = runtime.state.stable_hash()
                row['abilities_completed'] = sum(a['status'] == 'ABILITY_COMPLETE' for a in d['abilities'].values())
                row['nested_abilities'] = [a['identity'] for a in d['abilities'].values() if a['parent_ability_id']]
                row['completed_types'] = sorted({t['node']['op'].rsplit('.', 1)[-1] for t in d['tasks'].values() if t['status'] == 'TASK_COMPLETE' and not t.get('container')})
            probes[phase].append(row)
            if len(probes[phase]) % 50 == 0: print(phase, len(probes[phase]), 'roots', flush=True)
        elapsed[phase] = time.perf_counter() - start
        write(AUDIT.relative_to(ROOT) / (phase + '_probes.json'), probes[phase])
    totals = {phase: summary(rows) for phase, rows in probes.items()}
    joined = {phase: summary([r for r in rows if r['skill_joined']]) for phase, rows in probes.items()}
    write(AUDIT.relative_to(ROOT) / 'probe_summary.json', {'combat': totals, 'skill_joined': joined,
        'decoded_joined_rows': sum(r.get('root_ir_compiled', False) for r in joins['rows']), 'timings_seconds': elapsed})
    print(json.dumps({'combat': totals, 'skill_joined': joined, 'timings_seconds': elapsed}, indent=2), flush=True)

if __name__ == '__main__': main()
