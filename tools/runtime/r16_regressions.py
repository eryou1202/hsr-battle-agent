"""Varied real graphs/nodes, explicit synthetic inputs and owned replay."""
from r16_probes import *
from hsr_battle_agent.battle_ir.content_catalog import classify_dependency
from hsr_battle_agent.battle_ir.behavior import Authority, AbilityIR, TaskSequenceIR, TaskIR
from hsr_battle_agent.battle_runtime.behavior_state import ModifierInstance

def main():
    catalog=load_catalog()
    corpus=read(control('real_combat_corpus_v2'))
    original=[IRNode.from_dict(read(ROOT/g['IR_artifact'])) for g in corpus['graphs']]
    allnodes=[n for ir in original for n in walk_nodes(ir)]
    state,aliases,policies=fixture({n.payload.get('alias') for n in allnodes if n.op=='RPG.GameCore.TargetAlias'},
                                  {n.payload['key'] for n in allnodes if n.op=='lookup'})
    policies[POLICY_ID]=probe_policy()
    abilities=catalog.executable_abilities();templates=catalog.compiled_templates()
    after=read(AUDIT/'after_probes.json');expanded=read(AUDIT/'expanded_probes.json')
    byname={r['root']:r for r in [*after,*expanded]}
    examples=[]
    selections={'NATASHA_SKILL':'Avatar_Natasha_00_Skill02_Phase01',
                'PHASE_CHILD':'Avatar_Bailu_00_Skill02_Phase01',
                'CAMERA_NAMED_CALL':'Avatar_Anaxa_00_Skill01_Phase01',
                'BASIC_ATTACK_SLOT':'Avatar_Acheron_00_Skill01_Phase02'}
    selections['SKILL_SLOT']=next(r['root'] for r in after if r['skill_joined'] and '_Skill02_Phase01' in r['root'] and 'Natasha' not in r['root'])
    selections['ULTIMATE_RELATED_SLOT']=next(r['root'] for r in after if r['skill_joined'] and '_Skill03_Phase01' in r['root'] and 'Natasha' not in r['root'])
    for pattern,name in selections.items():
        examples.append({'pattern':pattern,'scope':'WHOLE_REAL_ROOT_SYNTHETIC_PROBE',
                         'skill_slot_names_are_fixture_selection_only':True,'probe':byname[name]})
    entries=[(r,IRNode.from_dict(r['ir'])) for r in catalog.records.values() if r.get('ir')]
    authority=Authority('REFERENCE_MODEL','r16','SYNTHETIC_REAL_NODE_WRAPPER','',semantic_status='REFERENCE_MODEL')
    finish=next(n for ir in original for n in walk_nodes(ir) if n.op=='RPG.GameCore.SkillPerformFinish')
    for pattern,op in [('TEMPLATE_INVOCATION','IncludeTaskListTemplate'),('DAMAGE_PRODUCING_ABILITY','DamageByAttackProperty'),
                       ('MODIFIER_CALLBACK_REFERENCE',None)]:
        candidates=[(r,ir,n) for r,ir in entries if 'Natasha' not in r['identity']
                    and (op is not None or r['graph']['type']=='RPG.GameCore.TurnBasedModifierConfig')
                    for n in walk_nodes(ir.payload.get('tasks',ir.payload.get('decoded')))
                    if (n.op.rsplit('.',1)[-1]==op if op else n.kind in ('TaskIR','UnsupportedSemanticIR'))]
        if pattern=='MODIFIER_CALLBACK_REFERENCE':
            candidates.sort(key=lambda v:not v[0].get('newly_decoded',False))
        if pattern=='TEMPLATE_INVOCATION':
            candidates.sort(key=lambda v:'parameters' not in v[2].payload.get('reference_binding',{}).get('roles',{}))
        source,ir,node=candidates[0]
        local=state.clone();localpolicies=copy.deepcopy(policies);nodes=[node,finish]
        if pattern=='MODIFIER_CALLBACK_REFERENCE':
            dispatch=TaskIR('synthetic/event','modifier_event_dispatch',authority,{'event_id':901})
            nodes=[dispatch,finish]
            local.modifiers['fixture']=ModifierInstance('fixture','EXPLICIT_CALLBACK_REFERENCE','a','a','a',1,1,{},
                event_registrations=[{'event_id':901,'order':0,'callback':node.to_dict(),'mutation_result':'NORMAL_GENERIC_TASK_EXECUTION'}])
            localpolicies['r13_reference_v1']['event_callbacks']='ORDERED_OWNER_CONTEXT_REFERENCE_V1'
        wrapped=AbilityIR('synthetic/'+pattern,'ability',authority,
            {'tasks':TaskSequenceIR('synthetic/'+pattern+'/seq','immediate_sequence',authority,{'tasks':nodes})})
        r=BehaviorRuntime(local,actions={'probe':wrapped},abilities=abilities,templates=templates,aliases=aliases,policies=localpolicies)
        r.start_action('probe');r.run_ready(7)
        restored=BehaviorRuntime.from_snapshot(r.snapshot())
        results=[x.run_until_blocked() for x in (r,restored)]
        if results[0]!=results[1] or r.stable_hash()!=restored.stable_hash():raise ValueError('isolated real node replay mismatch')
        examples.append({'pattern':pattern,'root':source['identity'],'source_identity':list(source_key(source)),
                         'node_id':node.node_id,'node_hash':node.stable_hash(),'original_node_preserved':True,
                         'scope':'ISOLATED_REAL_IR_NODE_EXPLICIT_SYNTHETIC_WRAPPER',
                         'callback_registration':'EXPLICIT_SYNTHETIC_ONLY' if op is None else 'NONE',
                         'native_fixture':False,'whole_root_completion_claimed':False,
                         'status':results[0].status.value,'first_gap':results[0].gap.required_capability if results[0].gap else None,
                         'metrics':r.state.scheduler.action_execution['metrics'],'replay':'PASS'})
    cameras=[r for r,_ in entries if '_Camera' in r['identity'] and r['entry']['type']==1]
    examples.append({'pattern':'DECODED_CAMERA_NAMED_GRAPH','source':cameras[0]['identity'],
                     'inspection':classify_dependency(cameras[0]),'native_irrelevance_proven':False})
    write('real_content_regressions.json',{'status':'PASS','examples':examples,
           'native_executable_claimed':False,'whole_root_and_isolated_node_results_kept_separate':True})
    print('real regressions',len(examples),'PASS',flush=True)

if __name__=='__main__': main()
