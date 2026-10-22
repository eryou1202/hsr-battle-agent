"""Reproducible per-root evidence census, with site/row/root denominators separate."""
from __future__ import annotations
import collections
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r23_reference_fixtures import content, owner_binding
from r23_discovery import write
from r23_checks import AUDIT
from r21_checks import read, sha
from r16_dependency_closure import AUDIT as R16, R14
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes, stable_hash

CLASSES=['CONTENT_NOT_FOUND','EXACT_CONTENT_PRESENT','CONTENT_READER_GAP',
    'REFERENCE_IDENTITY_AMBIGUOUS','INLINE_CONTENT_CONTEXT_MISSING','TEMPLATE_PARAMETER_CONTEXT_MISSING',
    'DYNAMIC_PROVIDER_INPUT_MISSING','ACTOR_STATE_INPUT_MISSING','RUNTIME_PRIMITIVE_UNSUPPORTED',
    'NATIVE_EFFECTIVE_RUNTIME_UNKNOWN','PRESENTATION_POLICY_REQUIRED']


def structural_class(edge):
    return {'REFERENCE_NOT_FOUND':'CONTENT_NOT_FOUND','EXACT_REFERENCE_READER_GAP':'CONTENT_READER_GAP',
        'EXACT_REFERENCE_GRAPH_UNDECODED':'CONTENT_READER_GAP','AMBIGUOUS_REFERENCE':'REFERENCE_IDENTITY_AMBIGUOUS',
        'EXACT_RESOLVED_COMPILED':'EXACT_CONTENT_PRESENT'}.get(edge['status'],
            'INLINE_CONTENT_CONTEXT_MISSING' if edge.get('candidate_inline_definitions') else 'DYNAMIC_PROVIDER_INPUT_MISSING')


def runtime_class(row):
    cap=row.get('required_capability') or '';op=(row.get('primitive') or '').rsplit('.',1)[-1]
    if not cap:return 'EXACT_CONTENT_PRESENT'
    if 'missing decoded child catalog' in cap:return 'CONTENT_NOT_FOUND' # refined against exact catalog by caller
    if 'TEMPLATE_PARAMETER' in cap:return 'TEMPLATE_PARAMETER_CONTEXT_MISSING'
    if 'PROGRESSION' in cap or op in ('ByRankActivated','BySkillPointActivated'):return 'ACTOR_STATE_INPUT_MISSING'
    if 'dynamic_provider' in cap or 'PROVIDER' in cap or op=='SetDynamicValue':return 'DYNAMIC_PROVIDER_INPUT_MISSING'
    if 'POSITION' in cap or 'presentation' in cap:return 'PRESENTATION_POLICY_REQUIRED'
    if 'REFERENCE_INSTANCE_INPUT' in cap or op in ('AddModifier','RemoveModifier'):return 'ACTOR_STATE_INPUT_MISSING'
    if 'lifecycle slot' in cap:return 'NATIVE_EFFECTIVE_RUNTIME_UNKNOWN'
    return 'RUNTIME_PRIMITIVE_UNSUPPORTED'


def main():
    catalog,owners,_,joins,corpus=content()
    controls=sorted((ROOT/'data/control').glob('generic_runtime_*.json'))
    pins={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in controls if '20261012_001' not in p.name}
    # Reading the controls is deliberate: each authoritative artifact is pinned,
    # interpreted in its own historical census view, and never rewritten.
    authoritative={p.name:read(p) for p in controls if '20261012_001' not in p.name}
    expected=joins['counts']
    assert expected['canonical_avatar_skill_ownership_rows']==660
    assert expected['exact_owner_config_joins']==309 and expected['exact_root_joins']==306
    graphs=[g for g in corpus['graphs'] if g['skill_joined']]
    assert len(graphs)==160 and sum(bool(j.get('root_ir_compiled')) for j in joins['rows'])==161
    frozen=read(R16/'after_probes.json');frozen={tuple(r['source_identity']):r for r in frozen}
    graph=catalog.closure([tuple(g['source_identity']) for g in graphs])
    indexed=collections.defaultdict(list)
    for i,e in enumerate(graph['edges']):
        e['site_id']='R23-SITE-'+str(i+1).zfill(5)
        e['content_class']=structural_class(e)
        e['execution_implied']=False
        indexed[tuple(e['parent_source_identity'])].append(e)
    rows=[]
    for g in graphs:
        key=tuple(g['source_identity']);queue=[(key,0)];seen=set();edges=[];depths={}
        while queue:
            at,depth=queue.pop(0)
            if at in seen:continue
            seen.add(at)
            for e in indexed[at]:
                edges.append(e);depths[e['site_id']]=depth
                if not e.get('inline') and e.get('target_source_identity'):
                    queue.append((tuple(e['target_source_identity']),depth+1))
        ext=[e for e in edges if not e.get('inline')]
        blocked=[e for e in ext if e['status']!='EXACT_RESOLVED_COMPILED']
        ir=IRNode.from_dict(read(ROOT/g['IR_artifact']))
        assert ir.stable_hash()==g['canonical_IR_hash']
        own=[j for j in joins['rows'] if j.get('exact_root_identity') and
             tuple(j['exact_root_identity'][k] for k in ('source_shard_sha256','record_start','record_end'))==key]
        nodes={n.stable_hash():n for n in walk_nodes(ir)}
        task_ops=sorted({n.op for n in nodes.values() if n.kind in ('TaskIR','UnsupportedSemanticIR')})
        child_records=[catalog.records[k] for k in seen if k in catalog.records and catalog.records[k].get('ir')]
        closure_ops=sorted({n.op for r in child_records for n in walk_nodes(IRNode.from_dict(r['ir']))})
        finish=sum(1 for r in child_records for n in
                   {n.stable_hash():n for n in walk_nodes(IRNode.from_dict(r['ir']))}.values()
                   if n.op=='RPG.GameCore.SkillPerformFinish')
        before=frozen[key]
        klass=runtime_class(before)
        if 'missing decoded child catalog reference:' in (before.get('required_capability') or ''):
            identity=before['required_capability'].split(':',1)[1]
            resolved=catalog.resolve({'reference_type':'ABILITY_REFERENCE','identity':identity})
            klass=structural_class(resolved)
        rank={'exact_external_sites':sum(e['status']=='EXACT_RESOLVED_COMPILED' for e in ext),
            'missing_dependencies':len(blocked),'missing_reference_depth':max((depths[e['site_id']] for e in blocked),default=0),
            'original_finish_nodes_in_decoded_closure':finish,
            'estimated_downstream_work':'HIGH' if len(blocked)>3 or klass=='CONTENT_NOT_FOUND' else 'MEDIUM',
            'generic_runtime_first_blocker_class':klass,
            'actor_state_requirements':'R20 exact Avatar + explicit level/promotion/rank/activation/property/resource inputs',
            'whole_action_opportunity':'BLOCKED_BY_SOURCE_EVIDENCE' if any(e['content_class']=='CONTENT_NOT_FOUND' for e in blocked) else
                'REFERENCE_CONTEXT_THEN_SEMANTICS_REQUIRED' if finish else 'ORIGINAL_COMPLETION_NOT_PROVEN'}
        rows.append({'root':g['record_identity'],'source_identity':list(key),'source_version':'4.6.51',
            'directory_identity':catalog.records[key]['entry'],'source_graph_hash':catalog.records[key]['graph_hash'],
            'source_artifact':g['decoded_artifact'],'source_artifact_sha256':sha(ROOT/g['decoded_artifact']),
            'IR_artifact':g['IR_artifact'],'canonical_IR_hash':ir.stable_hash(),'IR_roundtrip_hash':IRNode.from_dict(ir.to_dict()).stable_hash(),
            'canonical_owner_rows':own,'canonical_binding':owner_binding(g,catalog),
            'skill_level_configs':[s for s in owners['skills'] if s['skill_id'] in {j['skill_id'] for j in own}],
            'direct_dependency_sites':[e['site_id'] for e in indexed[key]],
            'transitive_dependency_sites':[e['site_id'] for e in edges],
            'dependency_depths':depths,'structural_gap_sites':[e['site_id'] for e in blocked],
            'dependency_content_classes':dict(collections.Counter(e['content_class'] for e in ext)),
            'runtime_frozen_first_gap':{k:before.get(k) for k in ('primitive','required_capability','gap_node','metrics','state_hash','status')},
            'runtime_first_gap_class':klass,'task_types':task_ops,'closure_types':closure_ops,'ranking':rank,
            'next_blocker_after_each_resolved_dependency':'See R23 execution stages; unexecuted branches remain structural only',
            'original_content_modified':False})
    rows.sort(key=lambda r:(not bool(r['ranking']['original_finish_nodes_in_decoded_closure']),
        r['ranking']['missing_dependencies'],r['ranking']['missing_reference_depth'],r['root']))
    for i,r in enumerate(rows):r['priority_ordinal']=i+1
    cohort={}
    tests={'basic_attack':lambda r:any(j['skill_trigger_key']=='Skill01' for j in r['canonical_owner_rows']),
           'skill':lambda r:any(j['skill_trigger_key']=='Skill02' for j in r['canonical_owner_rows']),
           'ultimate_related':lambda r:any(j['skill_trigger_key']=='Skill03' for j in r['canonical_owner_rows']),
           'damage':lambda r:'RPG.GameCore.DamageByAttackProperty' in r['task_types'],
           'heal':lambda r:'RPG.GameCore.HealHP' in r['closure_types'],
           'modifier':lambda r:'RPG.GameCore.AddModifier' in r['task_types'],
           'resource':lambda r:'RPG.GameCore.ModifySPNew' in r['closure_types'],
           'passive_interaction':lambda r:any(j['skill_trigger_key']=='SkillP01' for j in r['canonical_owner_rows'])}
    for role,select in tests.items():
        chosen=next((r for r in rows if select(r)),None)
        cohort[role]={'source_identity':chosen['source_identity'],'root':chosen['root'],
            'selection_is_fixture_only':True,'whole_completion_proven':False} if chosen else None
    result={'schema':'generic_runtime_joined_skill_dependency/1','source_version':'4.6.51',
        'denominators':{'canonical_owner_rows':660,'exact_owner_config_rows':309,'exact_root_rows':306,
            'decoded_joined_unique_roots':160,'decoded_joined_rows':161,'combat_roots':632},
        'blocker_classes':CLASSES,'roots':rows,'dependency_sites':graph['edges'],
        'cycles':graph['cycles'],'work_gaps':graph['work_gaps'],'diversity_cohort':cohort,
        'go_no_go':'GO_EXPLICIT_REFERENCE_CONTEXT_AND_TEMPLATE_BINDING; NO_GO_BROAD_CAMERA_DISCOVERY',
        'root_class_distribution':dict(collections.Counter(r['runtime_first_gap_class'] for r in rows)),
        'structural_site_class_distribution':dict(collections.Counter(e['content_class'] for e in graph['edges'] if not e.get('inline'))),
        'before':{'catalog_first_gaps_combat':145,'catalog_first_gaps_joined':75,'camera_first_gap_sites':68,
            'phase_first_gap_sites':7,'full_joined_transitions':0},
        'authority':'EXACT_SOURCE_CONTENT; EXPLICIT_REFERENCE_EXECUTION_ONLY','native_correctness':False}
    write('joined_dependency.json',result)
    write('authoritative_pins.json',{'files':pins,'owner_tables_sha256':sha(R14/'owner_tables.json'),
        'character_records_sha256':sha(R14/'character_records.json'),
        'frozen_probe_sha256':sha(R16/'after_probes.json'),'controls_read':len(authoritative)})
    print('joined census',len(rows),'sites',len(graph['edges']),'classes',result['root_class_distribution'],flush=True)


if __name__=='__main__':main()
