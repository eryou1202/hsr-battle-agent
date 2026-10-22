"""R23 explicit actor/availability inputs; original joined content is unchanged."""
from __future__ import annotations
import copy
from functools import lru_cache
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r21_checks import read
from r16_dependency_closure import load_catalog, R14
from r13_reference_fixtures import fixture
from r19_reference_fixtures import extend as property_extend
from r20_reference_fixtures import extend, actor_binding
from r22_reference_fixtures import inputs
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
from hsr_battle_agent.battle_ir.content_catalog import references, source_key
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.action_scheduler import POLICY_ID as SCHEDULER
from hsr_battle_agent.battle_runtime.damage_pipeline import POLICY_ID as DAMAGE


@lru_cache(maxsize=1)
def skill_reader():
    from r23_discovery import machinery
    from r14_corpus import Assets
    assets=Assets()
    entry=assets.lookup('BakedConfig/ExcelOutputGameCore/AvatarSkillConfig.bytes')
    data,pin=assets.source(entry)
    schemas,dispatch=machinery()
    return data,pin,schemas,dispatch


def decoded_skill(skill):
    from r14_corpus import Reader
    data,pin,schemas,dispatch=skill_reader()
    assert skill['source_shard_sha256']==pin['sha256']
    reader=Reader(data,skill['start'],skill['end'],schemas,dispatch)
    graph=reader.read(0x1e36ca80)
    assert reader.cursor==skill['end']
    return {**skill,'graph':graph}


@lru_cache(maxsize=1)
def content():
    return (load_catalog(), read(R14/'owner_tables.json'), read(R14/'character_records.json'),
        read(ROOT/'data/control/generic_runtime_skill_root_join_census_v1_20261008_001.json'),
        read(ROOT/'data/control/generic_runtime_real_combat_corpus_v2_20261008_001.json'))


def owner_binding(graph, catalog=None):
    c,owners,characters,joins,_ = content()
    c = catalog or c
    key = graph['source_identity']
    joined = [j for j in joins['rows'] if j.get('exact_root_identity') and
              [j['exact_root_identity'][k] for k in ('source_shard_sha256','record_start','record_end')]==key]
    if not joined: raise ValueError('canonical source owner join absent')
    j = joined[0]
    avatar = next(a for a in owners['avatars'] if a['graph']['fields'][0]['values'][0]['value']==j['avatar_id'])
    skill = decoded_skill(next(s for s in owners['skills'] if s['skill_id']==j['skill_id'] and s['level']==1))
    path = next(f['values'][0]['value'] for f in avatar['graph']['fields'] if f['mask']==256)
    char = next(c for c in characters if c['path']=='BakedConfig/'+path.removesuffix('.json')+'.bytes')
    return c.canonical_skill(avatar,skill,char,source_version='4.6.51')


def reachable(catalog, source):
    """Only exact, decoded dependencies; missing content remains missing."""
    queue=[tuple(source)];seen=set();records=[]
    while queue:
        key=queue.pop(0)
        if key in seen: continue
        seen.add(key);r=catalog.records.get(key)
        if not r or not r.get('ir'): continue
        records.append(r)
        for site in references(r['graph']):
            if site.get('inline'): continue
            resolved=catalog.resolve(site)
            if resolved.get('target_source_identity'):
                queue.append(tuple(resolved['target_source_identity']))
    return records


def template_bindings(catalog, records, policies, templates):
    receipts=[]
    p=policies[SCHEDULER]
    for record in records:
        parent=IRNode.from_dict(record['ir']);parent_key=list(source_key(record))
        # Hash-based dedup keeps duplicate canonical decoded/task views harmless.
        nodes={n.stable_hash():n for n in walk_nodes(parent) if n.op=='RPG.GameCore.IncludeTaskListTemplate'}
        for node in nodes.values():
            identity=node.payload.get('fields',{}).get('unbound_bit_0')
            if not isinstance(identity,str): continue
            try:
                key,ir,receipt=catalog.scoped_template(identity,parent_key,
                    {'authority':'REFERENCE_MODEL','scope':'EXACT_PARENT_ONLY_REFERENCE','parent_source_identity':parent_key})
            except ValueError:
                continue
            templates[key]=ir
            p.setdefault('template_call_bindings',{})[node.stable_hash()]={
                'authority':'REFERENCE_MODEL','mode':'SERIALIZED_DICTIONARIES_REFERENCE',
                'caller_context':'INHERIT_EXPLICIT','provider_inheritance':'INHERIT_EXPLICIT',
                'dictionary_masks':{'4':'numeric','8':'string','32':'sequence'},
                'template_catalog_key':key,'source_template_identity':identity,
                'caller_root_IR_hash':parent.stable_hash(),
                'evidence':'exact serialized dictionaries; explicit parent-only reference scope; native inheritance UNKNOWN'}
            p.setdefault('template_entry_bindings',{})[ir.stable_hash()]={
                'authority':'REFERENCE_MODEL','task_list_mask':2,'parameter_context':'EXPLICIT_CALLER_MAPPING_ONLY'}
            receipts.append({'call_node_hash':node.stable_hash(),'node_id':node.node_id,
                'call_source_span':node.payload.get('span'),**receipt})
    return receipts


def joined_runtime(graph, *, templates_enabled=False, template_provider_inputs=False, turn=True):
    catalog,_,_,_,_=content()
    binding=owner_binding(graph)
    records=reachable(catalog,graph['source_identity'])
    compiled={tuple(source_key(r)):IRNode.from_dict(r['ir']) for r in records}
    ir=compiled[tuple(graph['source_identity'])]
    abilities={r['identity']:compiled[tuple(source_key(r))] for r in records if r['entry']['type']==1
               and catalog.resolve({'reference_type':'ABILITY_REFERENCE','identity':r['identity']})['status']=='EXACT_RESOLVED_COMPILED'}
    templates={r['identity']:compiled[tuple(source_key(r))] for r in records if r['entry']['type']==2}
    nodes=list({n.stable_hash():n for v in compiled.values() for n in walk_nodes(v)}.values())
    original=read(ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001/joined_explicit_inputs.json')
    state=BehaviorBattleState.from_snapshot(original['state'])
    _,aliases,_=fixture({n.payload['alias'] for n in nodes if n.op=='RPG.GameCore.TargetAlias'})
    policies=copy.deepcopy(original['policies'])
    hashes={n.stable_hash() for n in nodes}
    policies[DAMAGE]['tasks']={k:v for k,v in policies[DAMAGE]['tasks'].items() if k in hashes}
    state,policies=property_extend(state,policies,nodes)
    provider_receipts=[]
    if template_provider_inputs:
        for n in nodes:
            if n.op!='RPG.GameCore.IncludeTaskListTemplate':continue
            for operand in walk_nodes(n.payload.get('fields',{})):
                if operand.op!='lookup':continue
                scope,key=operand.payload['scope'],str(operand.payload['key'])
                if key in state.dynamic_values.get(scope,{}):continue
                state.dynamic_values.setdefault(scope,{})[key]=SCALE
                provider_receipts.append({'source_operand':operand.to_dict(),'scope':scope,'key':key,'value':SCALE,
                    'authority':'EXPLICIT_SYNTHETIC_R23_INPUT','reason':'unit-valued template numeric parameter fixture; native effective value UNKNOWN'})
    receipts=template_bindings(catalog,records,policies,templates) if templates_enabled else []
    if provider_receipts:receipts.append({'explicit_template_provider_inputs':provider_receipts})
    r=BehaviorRuntime(state,actions={'canonical':ir},aliases=aliases,abilities=abilities,templates=templates,policies=policies)
    extend(r,nodes,avatar_id=binding['avatar_id'],activation=False,rank=0)
    r.state.properties['a']['speed']=100*SCALE
    r.bind_actor(actor_binding('b',1001,base_properties={'speed':100*SCALE,'hp':100*SCALE,
        'max_hp':100*SCALE,'reference_atk':10*SCALE},actor_resources={'reference_actor_counter':0}))
    r.state.target_context['current_ability']=binding['entry_ability']
    if turn:
        participants,p,providers=inputs(r,(('a',100),('b',100)))
        for participant in participants: participant['actor_binding']=None
        providers['source']='R23 exact canonical source join; explicit synthetic actor/availability/cost inputs'
        providers['availability']['actors']['a']['actions'][0].update(canonical_skill_binding=binding,target_ids=['b'])
        # The other participant has no invented canonical skill permission.
        providers['availability']['actors']['b']['actions']=[]
        r.initialize_turns(participants,p,providers)
    return r,binding,receipts
