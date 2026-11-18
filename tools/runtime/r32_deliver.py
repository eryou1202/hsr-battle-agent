"""Emit R32 bounded stop controls and verified, R32-only archive."""
from r32_closure import *
CR='CR-R32-JADE-ORIGINAL-MODIFIER-CLOSURE-20261108-001'
REPORT='docs/agent/handoffs/generic_runtime_jade_modifier_closure_20261108_001.md'
CONTROL_NAMES=['jade_modifier_sources','modifier_construction','original_execution','source_gaps']
CONTROLS=[f'data/control/generic_runtime_r32_{n}_v1_20261108_001.json' for n in CONTROL_NAMES]

def emit(path,value):
    (ROOT/path).write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')

def build():
    rows=read(AUDIT/'jade/results.json');acquired=read(AUDIT/'inline_definition_acquisition.json')
    from r16_dependency_closure import load_catalog
    from hsr_battle_agent.battle_ir.behavior import IRNode
    from hsr_battle_agent.battle_ir.content_catalog import walk
    catalog=load_catalog()
    write('exact_catalog_lookup.json',dict(keys={key:[e for bucket in catalog.directories.values() for e in bucket.values() if e.get('name')==key] for key in KEYS},scope='Existing exact ContentCatalog directory keys; no filename heuristic'))
    phases=[]
    for phase in ['Phase01','Phase02']:
        path=ROOT/f'tmp/audit/r27_real_character_monster_20261022_001/decoded/Avatar_Jade_00_Skill02_{phase}.json'
        if path.exists():
            doc=read(path);graph=doc['graph']
            from hsr_battle_agent.battle_ir.content_catalog import references
            phases.append(dict(source=path.relative_to(ROOT).as_posix(),sha256=sha(path),inline_modifier_configs=[s for s in references(graph) if s.get('definition') and s['identity'] in KEYS]))
    write('original_phase_definition_lookup.json',phases)
    for row in rows:
        snapshot=read(AUDIT/'jade'/row['branch']/'final_runtime.json')
        a=snapshot['state']['scheduler']['action_execution']
        main=next(s for s in a['sequences'].values() if any(n['node_id']=='/record/task_list/7' for n in s['nodes']))
        static=main['nodes'][8]
        row['static_next_after_branch_unwinds']=dict(node=static,task_hash=IRNode.from_dict(static).stable_hash(),status='STATIC_ONLY_NOT_REACHED',owner=main['ability_instance_id'])
        row['listener_effect_state']['listeners']=[reg for inst in row['listener_effect_state']['modifiers'].values() for reg in inst['event_registrations']]
        row['root_statuses']={k:v['status'] for k,v in a['roots'].items()}
        row['ability_statuses']={k:v['status'] for k,v in a['abilities'].items()}
        row['R22_turn_state']=snapshot['state']['mechanics']['battle_turn_v1']
        write('jade/'+row['branch']+'/receipt.json',row)
    write('jade/results.json',rows)
    tickets=[dict(ticket_id='R32-INSTANCE-AUTHORITY-'+r['modifier'],status='OPEN',gap_type='MODIFIER_INSTANCE_CONSTRUCTION_AUTHORITY_MISSING',exact_reference=r['modifier'],original_task_hash=r['task_hash'],definition_id=d['definition']['definition_id'],definition_source=d['definition']['source_identity'],definition_graph_hash=d['definition']['graph_hash'],resolved_edges=['Original TaskIR serialized DynamicString -> exact inline named dictionary key','Named dictionary value -> fully decoded TurnBasedModifierConfig and compiled original callback bodies'],required_acquisition=['Exact source/native instance factory operand mapping and owner/caster/source-ability context','Mask 512 constructor role and dynamic provider value','Duration/stack initialization policy and instance identity/lifetime','Listener activation/event dispatch and duplicate/failure completion policy'],closure_test='Prove sufficient constructor/context semantics or obtain explicit caller reference values for every missing operand before original R15/R17 application',stop='Definitions recovered; instance authority missing. No caller values invented to manufacture a reference prefix') for r,d in zip(rows,acquired)]
    emit(CONTROLS[0],dict(change_request=CR,rows=rows,acquisition=acquired,directory_receipt='tmp/audit/r32_jade_modifier_closure_20261108_001/directory_receipt.json',definitions_recovered=2,source_versions=dict(native='4.6.51',frozen_product='4.4.54')))
    classification={k:'UNKNOWN' for k in ['definition','native_instance_factory_binding','native_owner_caster','duration_stack','initial_properties','listeners_events','instance_identity_lifetime']}
    classification.update(target_selector='Original aliases known, caller reference context only',source_ability='R15 ability:26 Phase02 under ability:20 Phase01; source supported ownership, reference instance identity',constructor_operand='Serialized DynamicFloat lookup key -1022829777 at unknown mask 512; no role/value inferred')
    classification['definition']='KNOWN: two exact named inline definitions recovered with graph and original compiled callbacks'
    classification['listeners_events']='Serialized callback event IDs/tasks known; native activation timing, meaning and order remain UNKNOWN'
    emit(CONTROLS[1],dict(change_request=CR,verdict='ORIGINAL_MODIFIER_CONSTRUCTION_BLOCKED',classification=classification,source_evidenced_applications=0,explicit_reference_applications=0,cohort_A='BLOCKED: definitions recovered; native instance operands/context insufficient',cohort_B='BLOCKED: concrete missing caller lifetime/stack/provider/listener assumptions unavailable; none invented',runtime_changes=[],existing_authority='R15 invokes existing R17 execute/apply before generic primitive dispatch; R17 requires per-task-hash application and exact definition',transaction_safety='R17 refusal tested without state change. Known-definition application still requires explicit constructor authority.',native_evidence='tmp/audit/r32_jade_modifier_closure_20261108_001/native/evidence.json',native_effective_validation=False))
    emit(CONTROLS[2],dict(change_request=CR,scenarios=rows,original_AddModifier_tasks_completed=0,original_predicates_completed_per_scenario=1,complete_canonical_skill_transitions=0,parent_finish=False,turn_released=False,public_command_replay='PASS',manual_cursor_advancement=False,synthetic_finish=False,cross_character_reuse='No generic construction capability established; no Herta/Fugue authority added',frozen=[632,160,161],stable_prefixes=72,historical_prefixes=73))
    matrix=[dict(case=n,status='BLOCKED_BY_MISSING_INSTANCE_AUTHORITY',execution_test_pass=False) for n in ['ambiguous definition reference','unknown caster/owner','missing target','unknown duration/stack','missing listener authority','Jade callback ordering','Jade duplicate/refresh behavior','Jade rollback after successful construction','Jade suspended callback resumption']]
    matrix += [dict(case=n,status='REFUSAL_OR_REPLAY_TEST_PASS',execution_test_pass=False) for n in ['true AddModifier remains blocked','false AddModifier remains blocked','unknown definition atomic refusal','original TaskIR hash preservation','original Jade parent command replay','clone/snapshot/hash equality']]
    emit(CONTROLS[3],dict(change_request=CR,tickets=tickets,acceptance_matrix=matrix,stop_rule_observed=True,additional_native_bodies=0,new_dependency_hops=0,definition_families=2,source_evidenced_coverage_gain=0,reference_prefix_gain=0,remaining_native_questions=['Instance allocation and ownership operands','Source ability mapping and target native mask/status','Duration/stack/parameter interpretation','Listener activation, callback order and native duplicate/failure policy','Task completion/continuation status mapping; 0x9999 not assumed semantic success'],native_observations=[dict(method='0xB7585A0',observed='At 0xB758715 calls EvaluateTarget with selector at config +0x18, output list r8 and computed mask r9d. Empty list branches away. At 0xB7587F7 evaluates dynamic string config +0x28. At 0xB758B14 calls helper 0xB75A130 then accesses returned +0x60/+0x10; exact provider mapping remains unclosed.'),dict(method='0xB7585A0',observed='At 0xB7594CB..0xB7594ED passes r12 on stack, literal false byte, rdx=[rbp+0x1c0], r8=[rbp+0x1e0], r9=[rbp+0x1a8] to TryAddModifierInstance. At +0xB7594F2 tests returned pointer and branches on null; semantic ownership of all temporaries not proven.'),dict(method='0xF1290A0',observed='At 0xF129256/0xF129370 calls separate global/local instance find paths. At 0xF1297D5 calls AddModifierInstance. At 0xF1298D4 conditionally calls postprocess; return pointer at 0xF1298D9. Existing-instance path branches via +0x7c into separate processing/delay methods. Method names do not establish duplicate/refresh policy.'),dict(method='0xB7585A0',observed='At 0xB759FAE writes status literal 0x9999 after cleanup. No native-effective continuation oracle or generic success mapping claimed.')]))
    write('acceptance_matrix.json',matrix)
    native=read(AUDIT/'native/evidence.json')
    for key in ['edda2a0','f17a830','f17f4d0']:
        base=ROOT/'tmp/audit/r11_4651_natasha_semantic_closure_20261005_001'
        artifact='method_'+key+'.txt';calls=read(base/('calls_'+key+'.json'))
        (AUDIT/'native'/artifact).write_bytes((base/artifact).read_bytes())
        if not any(m['rva']==calls['rva'] for m in native['reused_methods']):native['reused_methods'].append(dict(rva=calls['rva'],method=calls['method'],artifact=artifact,sha256=sha(base/artifact),calls=calls['calls'],source_artifact=(base/artifact).relative_to(ROOT).as_posix()))
    native['stop']='Exact inline definitions and existing constructor body recovered; sufficient instance operand/context and activation policy authority remains missing. No additional method bodies acquired.'
    native['constructor_observations']=[dict(site='0xF17A8DA..0xF17A8F5',observed='Ctor forwards [r13+0x10] in r9, r14/r12 in rdx/r8, stack rbx and [r15+0x18] to BaseModifierInstance ctor 0xEEA2780; stores r13 at instance+0x148 and r12 at +0x190. Native identity semantics of all operands and caller construction binding not closed.'),dict(site='0xEDDA2BD..0xEDDA317',observed='AddModifierInstance appends supplied instance pointer to collection at component+0x38 with count/version maintenance; append evidence does not prove factory operands or duplicate policy.'),dict(site='0xF17F534..0xF17F53B',observed='OnActivate writes +0x94=1 and +0x7c=1; later calls _SetupRangeCallbackList at 0xF17F690,0xF180030,0xF1804DD and ExecuteEvent at 0xF1805B2. Event semantics and Jade policy mapping remain unproven.')]
    write('native/evidence.json',native)
    # Cross-character exact operands are retained without assigning any Jade policy.
    inherited=read(ROOT/'data/control/generic_runtime_r29_modifier_construction_v1_20261108_001.json')
    write('cross_character.json',dict(new_capability=False,new_authority=False,exact_inherited_applications=inherited['applications'],status='NOT_EXECUTED: no new generic construction capability; no Jade-specific authorization transferred'))
    g=read(AUDIT/'start_gate.json')
    changed=[n for n,h in g['file_hashes'].items() if 'r32_' not in n and (not (ROOT/n).is_file() or sha(ROOT/n)!=h)]
    frozen=read(ROOT/'tmp/audit/r27_real_character_monster_20261022_001/resume/input_hashes.json')['files']
    historical_drift=[n for n,h in frozen.items() if sha(ROOT/n)!=h]
    drift=[n for n in historical_drift if n not in g['file_hashes'] or sha(ROOT/n)!=g['file_hashes'][n]]
    preservation=dict(changed_inherited_files=changed,frozen_drift=drift,approved_pre_R32_differences_from_R27_pin=historical_drift,head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),staged_unchanged=git('diff','--cached','--name-status')==g['staged'],git_writes='NONE')
    write('preservation.json',preservation)
    assert not changed and not drift and preservation['head']==g['head'] and preservation['staged_unchanged']
    if sys.argv[1]=='evidence':
        print('Evidence controls and preservation verified; final tests pending',flush=True)
        return
    tests=read(AUDIT/'tests/results.json');scenarios=read(AUDIT/'tests/scenarios.json')
    assert set(scenarios)=={'frozen','skills','defense','encounters','planner','turns'}
    extra=read(AUDIT/'tests/R32_sources.json');assert extra['actual_exit_code']==0
    tests['R32_sources']=extra
    assert all(v['actual_exit_code']==0 for v in [*tests.values(),*scenarios.values()])
    # Verify final tested runtime bytes, separately from subsequently emitted controls/tools.
    tested=read(AUDIT/'tests/input_hashes.json')
    final={n:sha(ROOT/n) for n in tested if n.startswith(('src/','tests/'))}
    assert all(final[n]==tested[n] for n in final)
    final['tests/battle_runtime/test_behavior_r32_sources.py']=sha(ROOT/'tests/battle_runtime/test_behavior_r32_sources.py')
    assert final['tests/battle_runtime/test_behavior_r32_sources.py']==extra['test_sha256']
    write('final_tested_hashes.json',final)
    text='''# R32 ORIGINAL JADE MODIFIER CLOSURE COMPLETE

Verdict: **ORIGINAL_MODIFIER_CONSTRUCTION_BLOCKED**. Starting HEAD `61e12bb4aa7fc515d1762ce9d6597e182252d9a4`, branch `terra/implementation`. No production changes or Git writes. Existing approved work, M10–M15, ScenarioCompiler and strict admission preserved.

Two exact original modifier definitions were recovered from the already acquired Phase02 Ability's inline named dictionary (mask 256). The top-level directory has 20 entries and neither requested key, and the inherited catalog lacks these inline bodies until the acquired Phase02 record is included. These earlier scoped negative observations do not imply missing content. The exact serialized task references bind independently to the dictionary keys `MAvatar_Jade_00_BPSkillSelf` and `MAvatar_Jade_00_BPSkillBuffListen`, then to their decoded definitions and original compiled callback bodies. No matching filename or guessed path was admitted. Self definition span [10646629,10647060), graph hash df0f4c0e547bb259fb88f120ae9b9a838c26155c35f4eb1f97b736dda68331db; BuffListen span [10645392,10645683), graph hash e26b16ce06a4d39d225c39ecfcfa75d2fbea9d23ebd5b80ed531e987eb2e74d5. Both selected definition spans were re-read with the existing 0x1EB95390 reader, consumed exactly to the end and compared equal to the acquired decoded graphs. Definition byte hashes, key spans, source SHA and parent IR hashes are in the acquisition receipts. Only these two exact definition families were retained.

Both tasks retain original bitmap 522 (masks 2/8/512). True task span [10644447,10644512), target alias AbilityTargetEntity; false span [10644514,10644572), target alias Caster. They refer to different modifier names. Mask 512 holds a DynamicFloat program using key -1022829777; neither its construction role nor a value is invented. Each definition has two original callbacks; Self additionally contains definition mask 131072, whose initialization meaning is not inferred. Their shared enum storage values do not prove shared native stack/lifetime semantics. Per-node hashes, source SHA, byte SHA, exact node IDs, serialized arguments, child ability and sequence ownership are in separate branch receipts. Phase01 -> Phase02 ownership remains intact. Caller reference context resolves true target a and false Caster a in these particular saved scenarios; that coincidence does not equate the serialized target selectors or modifier types.

Six already acquired native bodies were reused with recorded SHA: R29 factory 0x160A9440, OnTaskBegin 0xB7585A0, TryAddModifierInstance 0xF1290A0; R11 AddModifierInstance 0xEDDA2A0, TurnBasedModifierInstance ctor 0xF17A830 and OnActivate 0xF17F4D0. The ctor forwards explicit native operands to BaseModifierInstance, stores context pointers and initializes fields. Registration appends the supplied instance; activation writes state flags and calls range/event setup. Proven call sites, pointer/status tests and operands are recorded separately from unknown identity mapping, listener activation policy and lifetime semantics. Additional native bodies 0/16, new hops 0/3, modifier families 2/2. Sufficient instance operand/provider authority remains missing and triggers the source stop rule. Unpatched static observations provide no native-effective oracle validation.

R17 already integrates with R15 task ownership before primitive dispatch. Its application gate requires explicit per-original-task hash input, exact definition graph and every field/listener policy. Cohort A now has exact content but lacks sufficient instance construction operands/context. Cohort B lacks caller-supplied concrete missing construction/lifetime/listener values. No assumptions were invented to lengthen a reference prefix. Callback event IDs and task bodies are recovered, while activation meaning/timing/order, native owner/caster, lifetime/stack, properties and native instance identity remain UNKNOWN. No empty dictionary, zero stack, infinite lifetime, first-instance or no-listener defaults were supplied.

Both complete public command sequences were replayed from R31's exact initial snapshots and matched R31 final snapshots. Each predicate completed once; leaf tasks **8 -> 8** on both branches. Original AddModifier tasks completed **0**; actual constructed modifiers **0**; source applications **0**; reference applications **0**. No modifier/listener effect occurred. Exact next runtime gap remains `REFERENCE_INSTANCE_INPUT_MISSING` for each original AddModifier hash. The deeper acquisition gap is `MODIFIER_INSTANCE_CONSTRUCTION_AUTHORITY_MISSING`. No subsequent original node was reached; static continuation after branch unwind is original SetCameraRootFollow at /record/task_list/8. Pending original sequences and all ancestor ownership are retained. R15 rolls back the failed task frame before suspension. Parent finish false, R22 turn released false, full canonical transitions **0**. No cursor was advanced manually and no finish was synthesized.

Six R32 tests verify bounded top-level directory absence, original hashes and distinct selectors, full public command replay, R17 missing-definition atomic refusal, absent reference authority, and reused source hashes. Four additional source tests verify the exact inline dictionary key/value binding, distinct graphs and original callbacks, registration through R17 without construction, and atomic refusal of known definitions without constructor policies. These are structural/refusal tests, not successful AddModifier execution tests. Deeper Jade constructor/callback/duplicate/resumption acceptance cases remain BLOCKED. Existing R17 regressions separately exercise generic reference listener order, refresh, rollback, callback suspension and snapshots on acquired definitions; those are not evidence of Jade execution. No new generic construction capability was established, so no Herta/Fugue execution was authorized. Their exact inherited operands are retained in the cross-character receipt.

Frozen denominators remain **632 combat roots / 160 joined roots / 161 joined rows**. Historical 73 and stable 72 prefixes remain distinct. Frozen drift none. Clone, JSON snapshot and complete public command replay passed. Beam Search / MCTS remain deferred.

Recommended R33: use the recovered exact inline definitions and acquire the native instance factory/context operands and missing lifetime/stack/provider/listener authority; alternatively obtain concrete caller reference values explicitly. Bind through existing R17 and resume the pending original R15 tasks. Do not start a second modifier engine.

Fresh final-source tests and scenario receipts:
'''
    text += '\n```json\n'+json.dumps(dict(tests=tests,scenarios=scenarios),indent=2)+'\n```\n'
    text += '\nProduction files: none. Tests: `test_behavior_r32.py` (6), `test_behavior_r32_sources.py` (4). Tools: `r32_closure.py`, `r32_deliver.py`. Controls: four R32 JSON files. Curated audits include separate true/false commands, snapshots, ownership, raw source references, native receipts and test hashes. The approved pre-R32 behavior_expansion.py hash differs from the older R27 pin; its starting bytes are preserved. Git writes: NONE.\n'
    (ROOT/REPORT).write_text(text,encoding='utf8')

def package():
    owned=[ROOT/p for p in [*CONTROLS,REPORT,'tests/battle_runtime/test_behavior_r32.py','tests/battle_runtime/test_behavior_r32_sources.py','tools/runtime/r32_closure.py','tools/runtime/r32_deliver.py']]
    owned += [p for p in AUDIT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['test_tmp','__pycache__']) and p.suffix in ['.json','.txt','.log'] and p.name not in ['member_manifest.json','handoff_verification.json']]
    members={p.relative_to(ROOT).as_posix():p.read_bytes() for p in owned}
    manifest={n:dict(size=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in sorted(members.items())}
    write('member_manifest.json',dict(change_request=CR,members=manifest,scope='Only R32-owned files; excludes inherited source files and all scratch temp directories'))
    members[(AUDIT/'member_manifest.json').relative_to(ROOT).as_posix()]=(AUDIT/'member_manifest.json').read_bytes()
    dest=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(members.items()):z.writestr(n,b)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None and set(z.namelist())==set(members)
        result={n:dict(size=z.getinfo(n).file_size,crc32=f'{z.getinfo(n).CRC:08x}',sha256=hashlib.sha256(z.read(n)).hexdigest()) for n in z.namelist()}
        assert all(z.read(n)==b for n,b in members.items())
    write('handoff_verification.json',dict(archive=dest.name,archive_sha256=sha(dest),archive_size=dest.stat().st_size,CRC='PASS',exact_member_set='PASS',member_sizes_and_SHA256='PASS',member_count=len(members),members=result))
    print(str(dest));print(sha(dest),flush=True)

if __name__=='__main__':
    if sys.argv[1] in ['build','evidence']:build()
    elif sys.argv[1]=='package':package()
    elif sys.argv[1]=='extra_tests':
        args=[sys.executable,'-m','unittest','tests.battle_runtime.test_behavior_r32_sources']
        p=subprocess.run(args,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True)
        (AUDIT/'tests/R32_sources.log').write_bytes(p.stdout+p.stderr)
        write('tests/R32_sources.json',dict(command=args,actual_exit_code=p.returncode,case_count=4,test_sha256=sha(ROOT/'tests/battle_runtime/test_behavior_r32_sources.py'),log_sha256=sha(AUDIT/'tests/R32_sources.log')))
        assert p.returncode==0
