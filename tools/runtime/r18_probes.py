"""R18 exact structural audit, unchanged frozen probes, separate explicit fixtures."""
from __future__ import annotations
import collections
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r18_checks import AUDIT,read,write,sha
from r16_dependency_closure import load_catalog,COMBAT,control
from r16_probes import run_probe
from r15_scheduler_probes import summary
from r18_reference_fixtures import make_runtime,task_binding
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes,encode,stable_hash
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.behavior_state import BehaviorBattleState
from hsr_battle_agent.battle_runtime.behavior_primitives import SCALE
from hsr_battle_agent.battle_runtime.damage_pipeline import attack_fields,source_expression

R17=ROOT/'tmp/audit/r17_modifier_event_20261009_001'
def load():
    corpus=read(control('real_combat_corpus_v2'));roots=[];unique={}
    for g in corpus['graphs']:
        if g['stratum'] not in COMBAT: continue
        ir=IRNode.from_dict(read(ROOT/g['IR_artifact']))
        if ir.stable_hash()!=g['canonical_IR_hash']: raise ValueError('frozen IR drift')
        roots.append((g,ir))
        # Prefer executable task-list pointers over duplicate decoded envelopes.
        for n in [*walk_nodes(ir.payload.get('tasks')),*walk_nodes(ir)]:
            if n.op=='RPG.GameCore.DamageByAttackProperty':
                unique.setdefault((g['source_shard_sha256'],tuple(n.payload['span'])),(g,n))
    return roots,list(unique.values())
def audit(roots,damage):
    shapes=collections.Counter();rows=[];samples={};pins={}
    for g,n in damage:
        raw=n.payload['decoded']['structure'];fields=attack_fields(n,n.payload['fields']['unbound_bit_1'])
        masks=tuple(f['mask'] for f in raw['fields']);shapes[masks]+=1
        expressions=[{'mask':f['mask'],'expression':v.to_dict(),'role':'UNKNOWN_NATIVE_ROLE'}
                     for f in fields for v in f['values'] if isinstance(v,IRNode) and v.kind=='ExpressionIR']
        row={'root':g['record_identity'],'source_identity':g['source_identity'],'source_shard_sha256':g['source_shard_sha256'],
            'source_version':n.authority.source_version,'source_task_id':n.stable_hash(),'pointer':n.node_id,
            'source_artifact':n.authority.source_artifact,'source_artifact_sha256':sha(ROOT/n.authority.source_artifact),
            'source_span':n.payload['span'],'concrete_type':n.op,'bitmap':raw['bitmap'],'task_masks':list(masks),
            'attack_masks':[f['mask'] for f in fields],'expression_operands':expressions,
            'property_reference_roles':'UNKNOWN; reference fixture property keys supplied separately',
            'flags':[f for f in raw['fields'] if any(v.get('kind')=='bool' for v in f['values'] if isinstance(v,dict))],
            'target_selector':encode(n.payload['fields']['unbound_bit_0']),
            'attack_data':encode(n.payload['fields']['unbound_bit_1']),
            'continuation':'serialized parent task-list order; native hit split unknown',
            'unknown_fields':encode(fields),'full_source_task':n.to_dict(),'skill_joined':g['skill_joined']}
        if row['source_artifact_sha256']!=n.authority.source_sha256: raise ValueError('source artifact drift')
        pins[row['source_artifact']]=row['source_artifact_sha256'];rows.append(row);samples.setdefault(masks,row)
    assert len(roots)==632 and sum(g['skill_joined'] for g,ir in roots)==160 and len(damage)==207
    write('damage_structural_audit.json',{'instances':rows,'distinct_task_shapes':len(shapes),
        'shape_counts':{','.join(map(str,k)):v for k,v in shapes.items()},'shape_samples':list(samples.values()),
        'structural_damage_gaps':[], 'reader_expansion_required':False,
        'evidence':'Pinned R14 4.6.51 dispatcher/reader schemas, bounded full-record consumption',
        'native_formula_operand_roles_proven':False})
    controls=[control('real_combat_corpus_v2'),control('action_scheduler_v1'),control('dependency_closure_v1'),
        ROOT/'data/control/generic_runtime_modifier_event_engine_v1_20261009_001.json',
        ROOT/'data/control/generic_runtime_modifier_lifecycle_census_v1_20261009_001.json',
        ROOT/'data/control/generic_runtime_support_census_v7_20261009_001.json',
        ROOT/'data/control/generic_runtime_semantic_gap_ledger_v5_20261009_001.json']
    pins.update({p.relative_to(ROOT).as_posix():sha(p) for p in controls})
    write('source_pins.json',pins)
    # One source task per selected graph, selected for content and graph diversity.
    chosen=[]
    for name in ['Avatar_AventurineW_00_Skill01_Phase02','Avatar_Serval_Skill02_Phase02',
                 'Avatar_Anaxa_00_Skill03_Phase02','Avatar_Argenti_00_Skill01_Phase02',
                 'Avatar_Acheron_00_Skill01_Phase02','Avatar_TheHerta_00_Skill01_Phase02']:
        options=[(g,n) for g,n in damage if g['record_identity']==name and source_expression(n,attack_fields(n,n.payload['fields']['unbound_bit_1']),4).op!='unknown_opcode']
        if options: chosen.append(options[0])
    # Require the fixture diversity to come from actual selected sources.
    if len(chosen)<6:
        existing={g['record_identity'] for g,n in chosen}
        for g,n in damage:
            if g['record_identity'] in existing: continue
            if source_expression(n,attack_fields(n,n.payload['fields']['unbound_bit_1']),4).op!='unknown_opcode':
                chosen.append((g,n));existing.add(g['record_identity'])
                if len(chosen)==6:break
    write('real_damage_fixtures.json',[{'root':g['record_identity'],'graph':g,'node':n.to_dict(),
        'binding':task_binding(n),'category':'EXPLICIT_DAMAGE_REFERENCE_FIXTURE'} for g,n in chosen])
    print('audit',len(damage),'real damage records;',len(shapes),'task shapes;',len(chosen),'explicit fixtures',flush=True)
    return chosen
def frozen(roots):
    fixture=read(R17/'frozen_reference_policy.json');state=BehaviorBattleState.from_snapshot(fixture['state'])
    catalog=load_catalog();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    # Reconstruct the original alias map from R13; retain the exact R17 state and policies.
    from r13_reference_fixtures import fixture as make_fixture
    nodes=[n for g,ir in roots for n in walk_nodes(ir)]
    _,aliases,_=make_fixture({n.payload.get('alias') for n in nodes if n.op=='RPG.GameCore.TargetAlias'},
                           {n.payload['key'] for n in nodes if n.op=='lookup'})
    old={tuple(r['source_identity']):r for r in read(R17/'after_probes.json')}
    rows=[];drift=[];replay=[];diagnostic_changes=[]
    for index,(g,ir) in enumerate(roots):
        row,r,result=run_probe(g,ir,state,aliases,fixture['policies'],abilities,templates)
        row.update(damage_operations_attempted=sum(h.get('status')=='TASK_REACHED' and 'DamageByAttackProperty' in h.get('node',{}).get('op','') for h in r.state.scheduler.action_execution['history'])+
                    int(bool(result.gap and 'DamageByAttackProperty' in result.gap.task_type)),
                   damage_operations_committed=len(r.state.damage_history),roots_reaching_hp_mutation=bool(r.state.damage_history))
        keys=['status','metrics','first_gap_family','primitive','required_capability']
        changes={k:{'before':old[tuple(g['source_identity'])][k],'after':row[k]} for k in keys if old[tuple(g['source_identity'])][k]!=row[k]}
        if changes.get('required_capability',{}).get('before')=='DAMAGE: formula/settlement not implemented' and row['required_capability']=='DAMAGE_REFERENCE_INPUT_MISSING: explicit damage policy and source task operands':
            diagnostic_changes.append({'root':g['record_identity'],'skill_joined':g['skill_joined'],
                'source_identity':g['source_identity'],'before':changes.pop('required_capability')['before'],'after':row['required_capability']})
        if changes:drift.append({'root':g['record_identity'],'changes':changes})
        rows.append(row)
        if index%100==0:
            clone=r.clone();restored=BehaviorRuntime.from_snapshot(r.snapshot())
            assert r.stable_hash()==clone.stable_hash()==restored.stable_hash()
            replay.append({'root':g['record_identity'],'hash':r.stable_hash(),'status':'PASS'})
        if (index+1)%50==0:print('frozen',index+1,flush=True)
    write('frozen_probes.json',rows);write('frozen_drift.json',drift);write('frozen_replay.json',replay)
    receipt={'category':'UNCHANGED_FROZEN_FIXTURE','combat':{'before':summary(list(old.values())),'after':summary(rows)},
        'joined':{'before':summary([r for r in old.values() if r['skill_joined']]),'after':summary([r for r in rows if r['skill_joined']])},
        'damage_operations_attempted':sum(r['damage_operations_attempted'] for r in rows),
        'damage_operations_committed':sum(r['damage_operations_committed'] for r in rows),'roots_reaching_hp_mutation':0,
        'drift':drift,'damage_diagnostic_changes':diagnostic_changes,'native_actor':False,'additional_damage_inputs':False}
    write('frozen_summary.json',receipt)
    if drift: raise ValueError('frozen regression drift')
def explicit(chosen,roots):
    rows=[];prefix=[]
    catalog=load_catalog();abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    byroot={g['record_identity']:(g,ir) for g,ir in roots}
    for i,(g,n) in enumerate(chosen):
        r=make_runtime([n],coefficient=(i+2)*SCALE,targets=('b','c') if i==3 else ('b',))
        before=r.snapshot();left,out1=r.replay(['probe']);right,out2=r.replay(['probe'])
        assert out1==out2 and left.stable_hash()==right.stable_hash()
        result=r.step('probe');assert result.status.value=='ACTION_REFERENCE_COMPLETE',str(result.gap)
        assert r.stable_hash()==left.stable_hash()
        rows.append({'root':g['record_identity'],'source_task_id':n.stable_hash(),'source_span':n.payload['span'],
            'status':result.status.value,'category':'ISOLATED_REAL_DAMAGE_PRIMITIVE','wrapper_finish':'EXPLICIT_SYNTHETIC_WRAPPER_ONLY',
            'initial_runtime':before,'settlements':r.state.damage_history,'state_hash':r.state.stable_hash(),
            'replay':'PASS','remaining_gap':None,'metrics':r.state.scheduler.action_execution['metrics']})
        _,ir=byroot[g['record_identity']]
        damage=[x for x in walk_nodes(ir.payload.get('tasks')) if x.op=='RPG.GameCore.DamageByAttackProperty']
        pr=make_runtime(damage or [n],root=ir,coefficient=(i+2)*SCALE)
        pr.abilities=abilities;pr.templates=templates
        # Alias/lookup inputs are explicitly recorded, using the same sandbox targets.
        for x in walk_nodes(ir):
            if x.op=='lookup':pr.state.dynamic_values['supplied'][str(x.payload['key'])]=(i+2)*SCALE
            if x.op=='RPG.GameCore.TargetAlias':
                from hsr_battle_agent.battle_ir.behavior import TargetSelectorIR
                pr.aliases[x.payload['alias']]=TargetSelectorIR('prefix_alias/'+x.payload['alias'],'explicit',x.authority,{'entities':['b']})
        start={'state':pr.state.snapshot(),'policies':copy.deepcopy(pr.policies),
            'aliases':{k:v.to_dict() for k,v in pr.aliases.items()},'source_root':ir.to_dict(),
            'catalog_source':'R16 pinned ContentCatalog, unchanged',
            'catalog_abilities':len(abilities),'catalog_templates':len(templates)}
        res=pr.step('probe')
        clone=pr.clone();restored=BehaviorRuntime.from_snapshot(pr.snapshot())
        assert clone.stable_hash()==restored.stable_hash()==pr.stable_hash()
        prefix.append({'root':g['record_identity'],'source_identity':g['source_identity'],'initial_runtime':start,
            'category':'REAL_GRAPH_PREFIX_HP_MUTATION','status':res.status.value,
            'hp_mutated':bool(pr.state.damage_history),'settlements':pr.state.damage_history,
            'gap':res.gap.required_capability if res.gap else None,'gap_node':res.gap.node if res.gap else None,
            'metrics':pr.state.scheduler.action_execution['metrics'],'state_hash':pr.state.stable_hash(),
            'fabricated_source_finish':False,'full_real_skill_reference_transition':res.status.value=='ACTION_REFERENCE_COMPLETE'})
    write('explicit_damage_results.json',rows);write('real_graph_prefix_results.json',prefix)
    write('explicit_summary.json',{'isolated':{'completed':len(rows),'denominator':len(chosen)},
        'prefix':{'hp_mutated':sum(r['hp_mutated'] for r in prefix),'denominator':len(prefix)},
        'full_real_skill':{'completed':sum(r['full_real_skill_reference_transition'] for r in prefix),'denominator':len(prefix)},
        'isolated_settlements':sum(len(r['settlements']) for r in rows),
        'prefix_gaps':dict(collections.Counter(r['gap'] for r in prefix if r['gap']))})
    print('explicit fixtures PASS',flush=True)
if __name__=='__main__':
    roots,damage=load()
    if '--frozen-only' in sys.argv:
        frozen(roots)
        sys.exit(0)
    chosen=audit(roots,damage)
    if '--audit-only' not in sys.argv:
        explicit(chosen,roots)
        if '--explicit-only' not in sys.argv:frozen(roots)
