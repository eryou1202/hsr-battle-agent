"""R33 evidence-only authority assessment. Never modifies runtime or source IR."""
from r30_closure import *
from dataclasses import asdict
import copy
AUDIT=ROOT/'tmp/audit/r33_modifier_instance_authority_20261109_001'
R32=ROOT/'tmp/audit/r32_jade_modifier_closure_20261108_001'
R27=ROOT/'tmp/audit/r27_real_character_monster_20261022_001'
CR='CR-R33-MODIFIER-INSTANCE-AUTHORITY-20261109-001'
NAMES=['modifier_instance','constructor_operands','jade_execution','skill_dependency_cutset','skill_completion_feasibility','source_gaps']
CONTROLS=[f'data/control/generic_runtime_r33_{n}_v1_20261109_001.json' for n in NAMES]
REPORT='docs/agent/handoffs/generic_runtime_modifier_instance_authority_20261109_001.md'

def write(n,v):
    p=AUDIT/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')

def emit(i,v):
    (ROOT/CONTROLS[i]).write_text(json.dumps(dict(change_request=CR,**v),indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')

def investigate():
    from hsr_battle_agent.battle_ir.behavior import IRNode,stable_hash
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
    inputs={p.relative_to(ROOT).as_posix():sha(p) for p in R32.rglob('*') if p.is_file() and p.suffix in ('.json','.txt') and not any(x in p.parts for x in ('test_tmp','regressions')) and p.name not in ('member_manifest.json','handoff_verification.json')}
    for p in (ROOT/'data/control').glob('generic_runtime_r32_*.json'):inputs[p.relative_to(ROOT).as_posix()]=sha(p);read(p)
    report=ROOT/'docs/agent/handoffs/generic_runtime_jade_modifier_closure_20261108_001.md'
    report.read_text(encoding='utf8');inputs[report.relative_to(ROOT).as_posix()]=sha(report)
    definitions=read(R32/'inline_definition_acquisition.json')
    summaries=[]
    for row in definitions:
        d=row['definition'];assert d['graph_hash']==stable_hash(d['decoded_graph'])
        assert sha(ROOT/d['source_artifact'])==d['source_artifact_sha256']
        callbacks=[f for f in d['compiled_decoded']['fields'] if f['mask']==33554432]
        summaries.append(dict(key=row['key'],definition_id=d['definition_id'],source_span=d['source_span'],graph_hash=d['graph_hash'],source_identity=d['source_identity'],definition_bytes_sha256=row['definition_bytes_sha256'],callbacks=callbacks,definition_masks=[f['mask'] for f in d['decoded_graph']['fields']],redecoded=False))
        write('definitions/'+row['key']+'.json',row)
    inherited=read(R32/'native/evidence.json')
    for m in inherited['reused_methods']:
        p=R32/'native'/m['artifact'];assert sha(p)==m['sha256']
        (AUDIT/'native'/m['artifact']).write_bytes(p.read_bytes())
    extra=read(AUDIT/'native/additional_methods.json')
    for m in extra['methods']:assert sha(AUDIT/'native'/m['artifact'])==m['sha256']
    methods={m['rva']:m for m in inherited['reused_methods']+extra['methods']}
    # Each tuple identifies a concrete native observation, not a guessed field meaning.
    raw=[
      ('0x160A9440','0x160A945D;0x160A94A5','allocator result -> task ctor; config operand','original Task config -> executor','factory known; native task context contents not supplied'),
      ('0xB7585A0','0xB758715','config+0x18 selector; r8 output list; r9d mask','target evaluation','serialized aliases known; mask/provider semantics unresolved'),
      ('0xB7585A0','0xB7587F7','config+0x28 DynamicString','definition identity','exact task name joins inline Phase02 dictionary'),
      ('0xB7585A0','0xB758B14','helper 0xB75A130 return -> +0x60/+0x10','effective source instance','native source selection requires config+0x80 and task+0x20 object'),
      ('0xB75A130','0xB75A14A..0xB75A165','[this+0x18]+0x80 compares 0,1,2','source selection branch','enum meanings/default absent from reached serialized fields; not inferred'),
      ('0xB75A130','0xB75A16F..0xB75A26B','this+0x20 virtual +0x120 or +0x110; argument rdx for branch 2; cast 0xB66F210 -> 0x16949180','source provider','R15 ability:26 is not authority for these native object values'),
      ('0xB7585A0','0xB7594CB..0xB7594ED','rdx=[rbp+0x1c0];r8=[rbp+0x1e0];r9=[rbp+0x1a8];stack r12,false','TryAddModifierInstance operands','native temporary semantic mapping not closed'),
      ('0xF1290A0','0xF1290B5..0xF1290C1','rcx->r12;rdx->rsi;r8->r15;r9->r14;stack5->rbx','operand conservation','register/stack identities proven, exact original values not proven'),
      ('0xF1290A0','0xF1290FA..0xF129129','if stack5 null allocate context; context+0x18 allocation; +0x64=-1.0','context creation','native conditional default observed; not a general license to supply null'),
      ('0xF1290A0','0xF129256;0xF129370','global/local instance lookup; r15+0x18 branch; rbx+0x58 filter','duplicate path','find/reuse/delete policy and definition enum mapping unresolved'),
      ('0xF1290A0','0xF129429..0xF12944E','allocate at 0xF129430; ctor(this=new,rdx=rsi,r8=r15,r9=r12,stack5=r14,stack6=rbx)','actual creation call site','creation provider located statically; executable input authority absent'),
      ('0xF17A830','0xF17A83F..0xF17A853','arg2->r14;arg3->r12;arg4->r13;arg5->rbx;arg6->r15','constructor entry','register preservation proves call wiring'),
      ('0xF17A830','0xF17A8DA..0xF17A8F5','Base(this, r14,r12,[r13+0x10],rbx,[r15+0x18])','Base initialization','config/context/source operands required; source values not established'),
      ('0xEEA2780','0xEEA27E9..0xEEA27ED','arg2 -> instance+0x40;arg3 -> +0x70','Base stores','stores proven; do not derive all field meanings from metadata declaration order'),
      ('0xEEA2780','0xEEA288B..0xEEA28F2','new TaskContext at instance+0x38; virtual +0x118(arg4), +0x128(arg5); context+0x28=this','TaskContext initialization','independent native context allocation and setters; not inherited R15 dictionary equality'),
      ('0xF17A830','0xF17A8FA..0xF17A9D1','instance+0x148=arg4; +0x190=arg3; +0x1b8=arg6+0x38; TaskContext+0x20=arg6+0x28','derived instance/context state','nonserialized pointers require source provider'),
      ('0xF17A830','0xF17AD93..0xF17ADF6','0x16948200 -> +0x294;0xF13ABD0 -> +0x288;0x169484B0 -> +0x28c; arg6+0x74 -> +0x278;0x16947FA0 -> +0x274','computed initialization','not constants; lifetime/stack semantic mapping unknown'),
      ('0xF1290A0','0xF129503..0xF129558','context+0x58 -> instance+0x78; +0x30 -> +0x58; +0x54 -> +0x80; +0x6c controls ID path','instance identity/initial state','identity counter at component+0x2c8 used conditionally; not unconditional new-ID policy'),
      ('0xF1290A0','0xF1297D5','call 0xEDDA2A0 with existing new instance','registration','does not allocate instance'),
      ('0xEDDA2A0','0xEDDA2BD..0xEDDA317;0xEDDA3A5;0xEDDA435','component+0x38 collection append supplied rdx; interface slot 13 then conditional slot 14','registration/activation dispatch','conditional flag controls second call; full interface semantics unclosed'),
      ('0xF17F4D0','0xF17F534..0xF17F53B;0xF17F690;0xF180030;0xF1804DD;0xF1805B2','+0x94/+0x7c writes; range callbacks and ExecuteEvent calls','activation/listener setup','serialized event IDs known; Jade timing/order/trigger/cleanup unproven'),
      ('0xB7585A0','0xB7594F2;0xB759FAE','returned pointer null test; status literal 0x9999 after cleanup','completion/continuation','not mapped to native success or R22 release')]
    edges=[dict(method=r,site=s,operand_identity=o,edge=e,semantic_role=k,source_version='4.6.51',method_sha256=methods[r]['sha256'],artifact='native/'+methods[r]['artifact']) for r,s,o,e,k in raw]
    write('native/dataflow.json',dict(edges=edges,methods=list(methods.values()),budget=dict(additional_bodies=2,limit=12,new_hops_per_blocker=1,max_hops=2,families=2),stop='Required original values and lifecycle authority remain missing; constructor workstream stopped. No arbitrary further acquisition.'))
    operands=[]
    for name,origin,status,ticket in [
      ('definition identity','serialized mask 8 DynamicString -> inline exact dictionary','BOUND',''),
      ('instance identity','native allocation 0xF129430 and conditional component+0x2c8 counter','STATIC_PROVIDER_IDENTIFIED_VALUES_UNBOUND','R33-CONTEXT'),
      ('caster/source','source helper config+0x80, task+0x20 virtual paths','UNKNOWN','R33-SOURCE'),
      ('target','mask 2 aliases AbilityTargetEntity / Caster; reference context a in both saved runs','REFERENCE_CONTEXT_ONLY','R33-SOURCE'),
      ('source Ability instance','R15 ability:26 -> parent ability:20; native ctor arg4 points to component','OWNERSHIP_PROVEN_NATIVE_MAPPING_UNBOUND','R33-SOURCE'),
      ('TaskContext / ModifierContext','native Base creates context+0x38; constructor arg6 consumed at +0x18/+0x28/+0x38/+0x74','UNKNOWN','R33-CONTEXT'),
      ('stack initialization','computed native helper outputs +0x288/+0x28c; definition enum bytes recovered','UNKNOWN','R33-LIFETIME'),
      ('duration/lifetime','constructor context +0x74 and computed +0x274; semantic role unproven','UNKNOWN','R33-LIFETIME'),
      ('dynamic initialization','original mask 512 DynamicFloat key -1022829777','ROLE_AND_VALUE_UNKNOWN','R33-DYNAMIC'),
      ('initial properties','arg3+0xb8 loop; property helpers 0xF17B210/0xF17B0E0','UNKNOWN','R33-CONTEXT'),
      ('listener bindings','two original callback graphs per definition; event IDs structurally decoded','TIMING_TRIGGER_ORDER_OWNER_UNKNOWN','R33-LISTENERS'),
      ('activation flags','native writes and conditional interface call; Self mask 131072 retained','ROLE_AND_VALUES_UNKNOWN','R33-LISTENERS'),
      ('duplicate/refresh policy','native enum dispatch/find/delete branches; no witnessed original instance','UNKNOWN','R33-TRANSACTION'),
      ('transaction/continuation','pointer test and status 0x9999; R15 refusal rollback observed','NATIVE_COMMIT_BARRIER_UNKNOWN','R33-TRANSACTION')]:
        operands.append(dict(operand=name,provenance=origin,status=status,provider_ticket=ticket,default_supplied=False))
    emit(1,dict(operands=operands,native_edges=edges,original_dynamic_operand=dict(mask=512,key=-1022829777,role='UNKNOWN',value='UNKNOWN'),self_additional_definition_mask=dict(mask=131072,role='UNKNOWN'),executable_contract=False))
    results=[]
    for branch,predicate in [('b',True),('false',False)]:
        old=read(R32/'jade'/branch/'receipt.json');initial=read(R32/'jade'/branch/'initial_runtime.json');commands=read(R32/'jade'/branch/'commands.json')
        r,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert r.snapshot()==read(R32/'jade'/branch/'final_runtime.json')
        again,_=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert again.stable_hash()==r.stable_hash()==r.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot()))).stable_hash()
        diag=r.clone().run_until_blocked();assert diag.gap.node==old['node']
        node=IRNode.from_dict(old['node']);assert node.stable_hash()==old['task_hash']
        a=r.state.scheduler.action_execution
        row=dict(branch=branch,predicate_result=predicate,original_task_hash=node.stable_hash(),node=old['node'],modifier=old['modifier'],task_count_before=8,task_count_after=a['metrics']['tasks_completed'],complete_original_TaskIR_gain=0,constructed_instance=None,applied_state=r.snapshot()['state']['modifiers'],registered_listeners=[],owned_callbacks=[],next_original_SemanticGap=asdict(diag.gap),underlying_authority_gap='MODIFIER_INSTANCE_CONSTRUCTION_AUTHORITY_MISSING',actual_next_node=None,static_after_unwind=old['static_next_after_branch_unwinds'],pending_tasks={k:v['status'] for k,v in a['tasks'].items() if v['status']!='TASK_COMPLETE'},ability_ownership={k:{f:v.get(f) for f in ['identity','status','parent_ability_id','parent_task_id','children','completion_requested','context']} for k,v in a['abilities'].items() if 'Jade' in v['identity']},parent_complete=False,R22_turn_released=False,source_evidenced_instances=0,reference_only_instances=0,original_AddModifier_complete=False,replay='PASS',final_hash=r.stable_hash(),cohort='ORIGINAL_TASK_IN_INHERITED_REFERENCE_SCENARIO',new_assumptions=False)
        results.append(row)
        for n,v in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',r.snapshot()),('receipt.json',row)]:write('jade/'+branch+'/'+n,v)
    emit(2,dict(scenarios=results,original_AddModifier_tasks_complete=0,original_parent_complete=False,R22_turn_released=False,manual_cursor_advance=False,synthetic_finish=False,camera_skips_added=False))
    stages={k:'UNPROVEN' for k in ['MODIFIER_DEFINITION_DECODED','MODIFIER_DEFINITION_BOUND_TO_ORIGINAL_TASK','MODIFIER_INSTANCE_PROVIDER_IDENTIFIED','MODIFIER_CONSTRUCTION_OPERANDS_BOUND','MODIFIER_INSTANCE_CREATED','MODIFIER_ACTIVATION_COMMITTED','MODIFIER_CALLBACKS_BOUND','ORIGINAL_ADDMODIFIER_TASK_COMPLETE','ORIGINAL_PARENT_COMPLETE']}
    stages.update(MODIFIER_DEFINITION_DECODED='PROVEN',MODIFIER_DEFINITION_BOUND_TO_ORIGINAL_TASK='PROVEN',MODIFIER_INSTANCE_PROVIDER_IDENTIFIED='STATIC_ALLOCATION_CALL_IDENTIFIED_EXECUTABLE_PROVIDER_UNBOUND')
    emit(0,dict(verdict='MODIFIER_INSTANCE_AUTHORITY_BLOCKED',stages=stages,definitions=summaries,concrete_provider=dict(allocation='0xF129430',constructor='0xF12944E -> 0xF17A830',registration='0xF1297D5 -> 0xEDDA2A0',executable=False),source_evidenced_construction=0,explicit_reference_construction=0,source_evidenced_activation=0,original_task_complete=0,original_parent_complete=0,native_effective_validated=0,full_joined_skills=0,original_monster_actions=0,runtime_changes=[],reference_diagnostic='Not installed: no explicit complete input cohort; no assumptions manufactured',cross_character='No generic executable contract recovered; Herta/Fugue no construction attempted',budget=extra))
    write('evidence_inputs.json',inputs)
    cutset(results,definitions)

def cutset(results,definitions):
    from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes
    ranked=read(R27/'character/all_160_ranked.json');jade=next(r for r in ranked['roots'] if r['root']=='Avatar_Jade_00_Skill02_Phase01')
    snapshot=read(AUDIT/'jade/b/final_runtime.json');action=snapshot['state']['scheduler']['action_execution']
    actions={branch:read(AUDIT/'jade'/branch/'final_runtime.json')['state']['scheduler']['action_execution'] for branch in ['b','false']}
    rows=[]
    for a in action['abilities'].values():
        if 'Jade' not in a['identity']:continue
        seq=a['node']['payload']['tasks']['payload']['tasks']
        for index,n in enumerate(seq):
            children={v.stable_hash():v for v in walk_nodes(IRNode.from_dict(n)) if v.node_id.startswith('/record/task_list/')}
            for h,v in children.items():
                if v.kind not in ('TaskIR','UnsupportedSemanticIR','PredicateIR'):continue
                conditional='/structure/' in v.node_id
                classification='PATH_CONDITIONAL_BLOCKER' if conditional else 'NOT_YET_REACHED'
                if v.op=='RPG.GameCore.SetCameraRootFollow':classification='PROVEN_REQUIRED_BLOCKER'
                observed={}
                for branch in ['b','false']:
                    saved=actions[branch]
                    observed[branch]=[t['status'] for t in saved['tasks'].values() if t['ability_instance_id']==a['ability_instance_id'] and IRNode.from_dict(t['node']).stable_hash()==h]
                if any(result['original_task_hash']==h for result in results):classification='PROVEN_REQUIRED_BLOCKER_ON_SELECTED_BRANCH'
                elif any('TASK_COMPLETE' in statuses for statuses in observed.values()):classification='EXECUTED_IN_REFERENCE_SCENARIO'
                rows.append(dict(ability=a['identity'],owner=a['ability_instance_id'],parent_ability=a['parent_ability_id'],sequence_index=index,node_id=v.node_id,hash=h,op=v.op,kind=v.kind,classification=classification,observed_frame_statuses=observed,source_body='AVAILABLE_STRUCTURAL_IR',executor='UNSUPPORTED' if v.kind=='UnsupportedSemanticIR' else 'GENERIC_SUPPORT_REQUIRES_OPERANDS',path_condition='nested original branch; not all branches executed' if conditional else 'unconditional sequence position',node=v.to_dict()))
    # Restrict inventory traversal to the exact joined root's known transitive edges.
    queue=[jade['source_identity']];seen=set();edges=[]
    while queue:
        key=tuple(queue.pop(0))
        if key in seen:continue
        seen.add(key)
        for e in ranked['dependency_sites']:
            if tuple(e['parent_source_identity'])!=key:continue
            x=copy.deepcopy(e);x['r33_definition_join']='EXACT_R32_DEFINITION' if e.get('identity') in {d['key'] for d in definitions} else 'NOT_INVESTIGATED_OUTSIDE_TWO_FAMILIES'
            x['classification']='SOURCE_AVAILABILITY_UNKNOWN' if e['status']=='REFERENCE_NOT_FOUND' else 'PATH_CONDITIONAL_BLOCKER'
            if (e.get('identity') or '').endswith(('Skill02_Camera','Skill02_Camera_Self')):
                x.update(classification='PROVEN_REQUIRED_BLOCKER',source_body='MISSING_FROM_ACQUIRED_EXACT_CATALOG',downstream='UNSEEN',execution_obligation='Literal TriggerAbility in unconditional Phase01 sequence /2 or /8 after owned Phase02; not yet reached; native call flag semantics remain unbound')
            edges.append(x)
            if e.get('target_source_identity'):queue.append(e['target_source_identity'])
    camera=next(r for r in rows if r['op']=='RPG.GameCore.SetCameraRootFollow')
    presentation=snapshot['policies']['r15_action_scheduler_reference_v1']['presentation']
    callback_dependencies=[]
    for definition in definitions:
        d=definition['definition']
        field=next(f for f in d['compiled_decoded']['fields'] if f['mask']==33554432)
        for ordinal,callback in enumerate(field['values'][0]['children']):
            callback_dependencies.append(dict(definition=d['config_identity'],ordinal=ordinal,source_body='AVAILABLE_ORIGINAL_COMPILED_GRAPH',classification='PATH_CONDITIONAL_BLOCKER',trigger_and_mandatory_completion_barrier='UNKNOWN_EVENT_AUTHORITY',original_callback=callback))
    write('callback_dependency_cutset.json',callback_dependencies)
    emit(3,dict(root=jade['root'],canonical_IR_hash=jade['canonical_IR_hash'],canonical_binding=jade['canonical_binding'],scope='ALL_KNOWN_ACQUIRED_ROOT_AND_PHASE02_TASKS_AND_R27_EXACT_TRANSITIVE_SITES; NOT_A_COMPLETE_DOWNSTREAM_GRAPH',complete_dependency_graph=False,ordered_tasks=rows,known_dependency_sites=edges,required_child='Phase01 -> owned Phase02 ability:26; parent ability:20 waits for child tree',current_cut=['original selected AddModifier instance authority','Phase02 /record/task_list/8 SetCameraRootFollow executor/semantics'],camera_continuation=dict(classification='PROVEN_REQUIRED_BLOCKER',mandatory_on_both_saved_paths=True,reason='Unconditional next sequence position after /record/task_list/7 branch unwind; before /9 ModifySPNew and /10 SkillPerformFinish',node=camera,source_body='STRUCTURALLY_AVAILABLE',native_execution_authority='MISSING',not_ignorable=True),external_camera_bodies='Exact literal Camera and Camera_Self child references are in unconditional parent sequence positions /2 and /8; bodies unavailable, not yet reached; native invocation flag semantics remain unbound; no name/path search performed',inherited_reference_presentation_assumptions=presentation,source_closed_prefix_claim=False,finish_obligations=['Phase02 /10 original SkillPerformFinish must execute','Phase01 original remaining tasks and child tree must drain','R15 root completion and R22 ownership release must both occur'],unseen_downstream=['unavailable Camera/Camera_Self child bodies','unclosed modifier callback execution paths and event providers','other conditional modifier families outside R33 two-family bound']))
    candidates=[]
    for r in ranked['roots']:
        candidates.append({k:r[k] for k in ['root','rank','canonical_IR_hash','source_identity','remaining_gap_sites','remaining_gap_depth','original_finish_nodes','current_executable_tasks','current_first_blocker','dynamic_provider_types','exact_available_dependencies','unresolved_site_ids']})
        candidates[-1].update(observation_version='R27 historical source/reference inventory, not new native execution',unknown_external_provider_count='UNKNOWN_NOT_ZERO',finish_reachable_now=False,completion_ready=False)
    combat=[r for r in candidates if r['original_finish_nodes']]
    combat.sort(key=lambda r:(r['remaining_gap_sites'],r['remaining_gap_depth'],-r['current_executable_tasks'],len(r['dynamic_provider_types']),r['root']))
    emit(4,dict(roots=candidates,root_count=len(candidates),combat_priority=combat,best_alternative=combat[0],best_alternative_scope='NEXT_SOURCE_RECOVERY_CANDIDATE_ONLY; no proven completion-ready root',ranking_axes=['mandatory source availability','observed unresolved site count/depth','original finish presence, not reachability','reference execution support','unknown provider counts retained as unknown','repeatable inherited R15 replay'],maze_exclusions=[r for r in candidates if r['remaining_gap_sites']==0 and not r['original_finish_nodes']],assessment='No already joined combat root with original finish has zero inventoried gaps. Huohuo Skill01 has one exact missing Camera dependency and the longest observed prefix among the one-gap cohort (53); Sampo 40 and Xueyi Skill02 39 are comparable. Jade has additional instance/context and mandatory SetCameraRootFollow cutsets. None is proven nearly complete.',finish_presence_does_not_prove_reachability=True,full_joined_skills=0,inventory_sources=[str((R27/'character/all_160_ranked.json').relative_to(ROOT)), 'tmp/audit/r23_real_skill_root_closure_20261012_001/joined_dependency.json'],inventory_hashes={str(p.relative_to(ROOT)):sha(p) for p in [R27/'character/all_160_ranked.json',ROOT/'tmp/audit/r23_real_skill_root_closure_20261012_001/joined_dependency.json']}))
    tickets=[dict(id='R33-'+k,status='OPEN',gap='MODIFIER_INSTANCE_CONSTRUCTION_AUTHORITY_MISSING',required=x,max_new_hops=2) for k,x in [('SOURCE','Prove task+0x20/config+0x80 effective source mapping and native target/caster identity to R15/R20 context'),('CONTEXT','Prove original TryAdd stack5 -> ctor arg6 values and Base TaskContext setters, including instance identity and initial properties'),('LIFETIME','Prove stack/count/duration computations, source definition enums and context values without defaulting'),('DYNAMIC','Bind original mask512 key -1022829777 role and actual value; retain Self mask131072 unknown'),('LISTENERS','Prove event identity/trigger/timing/order/owner, repeated application, expiration/removal/cleanup'),('TRANSACTION','Prove duplicate/failure path and native activation/task continuation barrier')]]
    tickets += [dict(id='R33-CAMERA-CONTINUATION',status='OPEN',classification='PROVEN_REQUIRED_BLOCKER',required='Source-supported SetCameraRootFollow executor and operand mapping for exact /record/task_list/8; do not skip'),dict(id='R33-CAMERA-BODIES',status='OPEN',classification='PROVEN_REQUIRED_BLOCKER',required='Exact literal child source providers in parent sequence /2 and /8; downstream unknown; invocation flags unbound; no path guessing')]
    emit(5,dict(verdict='MODIFIER_INSTANCE_AUTHORITY_BLOCKED',tickets=tickets,additional_native_bodies=2,maximum=12,max_hops_used=1,constructor_workstream_stopped=True,source_evidenced_gain=0,reference_gain=0,unsupported_acceptance_cases={k:'BLOCKED_NO_ORIGINAL_CONSTRUCTION; NOT_EXECUTION_PASS' for k in ['native owner/caster/target binding','unknown lifetime/stack execution','activation/listener ownership','duplicate application','callback order','successful-construction rollback','successful suspended callback resumption']},frozen=[632,160,161],historical_prefixes=73,stable_prefixes=72))

def scenarios():
    receipts={}
    for mode,count in [('frozen',632),('skills',160),('defense',18),('encounters',18),('planner',20),('turns',14)]:
        args=[sys.executable,__file__,'regressions',mode];start=now();p=subprocess.run(args,cwd=ROOT,capture_output=True)
        log=AUDIT/'tests'/('scenario_'+mode+'.log');log.parent.mkdir(exist_ok=True);log.write_bytes(p.stdout+p.stderr)
        receipts[mode]=dict(command=args,actual_exit_code=p.returncode,case_count=count,started=start,finished=now(),log_sha256=sha(log),input_hash_manifest_sha256=sha(AUDIT/'tests/input_hashes.json'))
        write('tests/scenarios.json',receipts);print(mode,p.returncode,flush=True)
    assert all(r['actual_exit_code']==0 for r in receipts.values())

if __name__=='__main__':
    if sys.argv[1]=='investigate':investigate()
    elif sys.argv[1]=='regressions':
        import r30_closure as c
        c.AUDIT=AUDIT;c.regressions(sys.argv[2])
    elif sys.argv[1]=='scenarios':scenarios()
