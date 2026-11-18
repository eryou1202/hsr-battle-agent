"""Produce R30 authority-stop controls and a verified changed-files handoff."""
from r30_closure import *

CONTROL_NAMES=['dynamic_context','keyed_setter','original_task_execution','native_numeric','semantic_gaps']
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_dynamic_context_closure_20261108_001.md'
def control(name,**v):
    p=ROOT/'data/control'/('generic_runtime_r30_'+name+'_v1_20261108_001.json')
    p.write_text(json.dumps(dict(change_request=CR,authority='SAME_BUILD_UNPATCHED_OBSERVATIONS_ONLY',native_effective_validated=False,**v),indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
    return p
def main():
    gate_doc=read(AUDIT/'start_gate.json');meta=read(AUDIT/'selected_metadata.json')
    old=read(OLD/'native_methods.json');new=read(AUDIT/'native_methods.json')
    baseline=read(OLD/'character/results.json');bindings=read(ROOT/'data/control/generic_runtime_r29_original_task_bindings_v1_20261108_001.json')
    evidence=[]
    for m in old['methods']:
        if m['rva'] in ['0xEDF6E30','0x127100D0','0x163ECB70','0xF124690','0x1DCA0FD0','0x160A9DD0','0x160A9F40','0x1270FFF0','0x163ECA00']:
            assert sha(OLD/m['artifact'])==m['sha256'];evidence.append(dict(rva=m['rva'],path=(OLD/m['artifact']).relative_to(ROOT).as_posix(),sha256=m['sha256'],reacquired=False))
    for m in new['methods']:assert sha(AUDIT/m['artifact'])==m['sha256']
    tickets=[
        dict(id='DYNAMIC_ENTRY_SETTER_AUTHORITY_MISSING',object='FFKBNBIMMHE concrete entry stored at entry-array + 0x30 + 24*index',required=['Exact instantiated implementation and construction caller for Lynx/Klara keys','Concrete vtable map for slots 3/4/5/7','Setter provider coupling, nested listeners, reentrancy, exceptions and continuation'],sites=['0x1DCA1020','0x1DCA1279','0x1DCA134D'],stop='Interface metadata recovered; concrete runtime entry identity is not supplied by selected source roots. No dictionary fallback.'),
        dict(id='SCOPE0_OBJECT_GRAPH_AUTHORITY_MISSING',object='RPG.GameCore.TaskContext and provider fallback graph',required=['Exact owner/source/current ability and modifier objects for original invocation','Prove field-name-to-offset joins, parent stack installation and inherited context lifetime','Resolve scope fallback virtual slots and store constructors, global fallback authority'],sites=['0xEDF6E84','0xEDF6FA8','0xEDF7014','0xEDF7148','0xEDF7268','0xEDF732A','0xEDF73F8','0xEDF750F'],stop='Observable offset graph available, complete identities and propagation absent. Scope 9 and scopes 1..8 stay separate.'),
        dict(id='EFFECTIVE_PROPERTY_OBJECT_AUTHORITY_MISSING',object='AbilityProperty 1 on first selected Caster',required=['Effective property object array installation and +0x48 raw value authority','Meaning of absent property fallback global 0x97D51F0','Exact original selector context and mask 0x3F semantics'],sites=['0x12710176','0x127101EF','0xF12478D','0xF124797','0xF1247F3'],stop='Empty selection is out-of-range, not numeric zero; missing property sentinel value unresolved.'),
        dict(id='CANDIDATE_STATUS_CONTEXT_AUTHORITY_MISSING',object='Klara predicate task and candidate TaskContext stack',required=['Concrete predicate owner and virtual Begin/Update implementation','Candidate context push/pop exception safety and lifecycle','Mask 1/15 bit meanings; source modifier containment instance'],sites=['0x163ECC10','0x163ECCC3','0x163ECD08','0x163ECD30','0x163ECD61','0xB904CD8','0xB904E7C'],stop='0x9999 comparison is against returned task status; not an established generic boolean contract.'),
        dict(id='NATIVE_NUMERIC_EXTENDED_DOMAIN_UNSUPPORTED',object='RPG.GameCore.FixPoint tagged representation',required=['Mode-tag scale and mixed comparison/rounding contract beyond selected Clamp body','Native overflow and property-object initialization constants','Conversion authority before R12/R19 adoption'],sites=['0x163ECE6E','0x163ECE90','0x1EC22590'],stop='Count bit packing isolated offline. No tagged value admitted into R19.'),
    ]
    scope=[
      dict(order=0,path='context+0x18 -> +0xE0 -> +0x10 collection -> top item -> +0xA0 nonzero -> +0x38 store',sites=['0xEDF6E84','0xEDF6E91','0xEDF6EE3','0xEDF6EFD','0xEDF6F06'],condition='scope 0 or 9; key membership required; unavailable continues'),
      dict(order=1,path='context+0x48 chain; each node+0x20 store; parent link node+0x18',sites=['0xEDF6FA8','0xEDF6FC2','0xEDF6FD3','0xEDF6FEC'],condition='scope 0; first found key wins'),
      dict(order=2,path='context+0x50 TaskTemplate interface slot 0 -> store',sites=['0xEDF7014','0xEDF70AF','0xEDF70C6'],condition='non-null returned store with key; interface invoked again on success'),
      dict(order=3,path='context+0x28 -> +0x10 store',sites=['0xEDF7148','0xEDF717B'],condition='scope-0 second dispatch table target proven by saved table bytes'),
      dict(order=4,path='context virtual slot at class+0x120 -> object+0x68 store',sites=['0xEDF7268','0xEDF72CC','0xEDF72E9'],condition='scope 0 falls onward when unavailable'),
      dict(order=5,path='GetOwnerCustomData(context)+0x18 store',sites=['0xEDF732A','0xEDF733E','0xEDF735B'],condition='owner custom data includes +0x90 and +0x88 provider branches; exact types/instances unresolved'),
      dict(order=6,path='context virtual owners -> cast component -> custom-data +0x18 store',sites=['0xEDF7375','0xEDF73F8','0xEDF7468','0xEDF74EF'],condition='multiple type checks and identity comparison; no flattened ownership assertion'),
      dict(order=7,path='context+0x18 non-null gate -> global table+0x9CE8 -> +0x410 store',sites=['0xEDF750F','0xEDF7530','0xEDF7540','0xEDF7560'],condition='scope 0 only; missing key returns null at 0xEDF7ABD'),
    ]
    files=[]
    files.append(control('dynamic_context',verdict='DYNAMIC_CONTEXT_AUTHORITY_BLOCKED',adapter_installed=False,metadata='tmp/audit/r30_dynamic_context_closure_20261108_001/selected_metadata.json',reused_evidence=evidence,new_methods=new,scope_0_observable_search_order=scope,scope_9='Shares initial override; failure takes diagnostic path at 0xEDF6F3A, bypasses scope-0 chain.',other_scopes='Different table; do not generalize scope 0.',field_identity_status='Offsets observed; TaskContext field names recovered separately; full field-name offset authority and propagation NOT established',tickets=tickets[:2]))
    files.append(control('keyed_setter',status='DYNAMIC_ENTRY_SETTER_AUTHORITY_MISSING',entry_interface='FFKBNBIMMHE type 10867 via global 0x9804FA0',entry_identity='Exact lookup result object; concrete implementing type/instance unresolved',lookup=dict(store='receiver+0x20',helper='0x1BC90A50',missing='negative index returns at 0x1DCA134F, no insertion or callback',entry='dictionary+0x18 array; result object at array+0x30+24*index',null='null storage/array/entry and bounds use exception paths'),ordered_operations=[dict(slot=3,name='get_Val',role='capture old raw value'),dict(slot=5,name='get_MinValue'),dict(slot=7,name='get_MaxValue'),dict(call='0x1EC22590',name='FixPoint.Clamp',inputs=['incoming raw','min raw','max raw']),dict(slot=4,name='set_Val',role='mutate same keyed entry'),dict(owner='store receiver+0x10 delegate',role='if non-null: read new Val and invoke once on straight-line normal path, passing key, old-present payload, new value')],callback_receipt='Static call site only: 0x1DCA134D after setter 0x1DCA1279. No native invocation; exactly-once under reentrancy/exceptions NOT established.',r19_compatibility='Existing dynamic state can retain bounded raw values but lacks this entry/provider identity. R17 can represent explicit events only after listener order is evidenced.',rollback='R15 leaf atomicity exists; native setter/callback rollback and continuation unknown',contract=tickets[0]))
    roots=[]
    for b in bindings['roots']:
        r=next(x for x in baseline if x['root']==b['root'])
        roots.append(dict(root=b['root'],before=b['after'],after=b['after'],next_task=b['next_task'],next_blocker=b['next_gap'],original_IR_hash=b['unchanged_original_IR_hash'],baseline_task_hash=r['task_hash'],new_original_execution=False))
    selected=[r for r in baseline if 'Lynx' in r['root'] or 'Klara' in r['root']]
    traces=[]
    for r in selected:
        node=r['current_task'];traces.append(dict(parent=r['root'],source_child=node['authority']['source_artifact'],source_child_sha256=node['authority']['source_sha256'],source_pointer=node['authority']['source_pointer'],task_hash=r['task_hash'],unchanged_task=node,executor='0x127100D0' if 'Lynx' in r['root'] else '0x163ECB70',scope_provider='0xEDF6E30',writer='0x1DCA0FD0',runtime_route='R15 owned child under R20 actor binding; executor provider missing -> semantic gap, no new adapter',cohort='STRUCTURAL_ONLY'))
    for trace in traces:
        trace['canonical_owner']=next(r['canonical_owner'] for r in selected if r['root']==trace['parent'])
        trace['native_task_fields']=dict(config='+0x18',TaskContext='+0x20',status='+0x10',key_hash='+0x28' if 'Lynx' in trace['parent'] else '+0x30',predicate=None if 'Lynx' in trace['parent'] else '+0x28')
        trace['key_hash_provenance']=dict(constructor='0x1270FFF0' if 'Lynx' in trace['parent'] else '0x163ECA00',config_string='+0x18',algorithm='Two uint32 accumulators seeded 0x1505; alternating nonzero UTF-16 units update hash=(hash*33)^unit; result=(even + odd*0x5D588B65) modulo 2^32. Stops on zero unit.',runtime_key_instance='UNRESOLVED',native_invocation=False)
        if 'Klara' in trace['parent']:
            trace['candidate_context_edges']=[
                dict(site='0x163ECBA5..0x163ECBBF',edge='task+0x20 TaskContext -> +0x18 owner -> +0xE0 stack wrapper (r14)'),
                dict(site='0x163ECC9D..0x163ECCA4',edge='ReferencePool<LPNPMKNMMOK type 57289>.Acquire -> pooled frame; generic global 0x990D498; NOT a newly constructed TaskContext'),
                dict(site='0x163ECCA9..0x163ECCC3',edge='push frame into wrapper+0x10 stack'),
                dict(site='0x163ECD08',edge='frame+0x20 = selected candidate entity'),
                dict(site='0x163ECD0C..0x163ECD35',edge='task+0x28 predicate -> dispatcher -> captured task status compared to 0x9999; absent predicate increments count'),
                dict(site='0x163ECD4D..0x163ECD70',edge='normal-path pop wrapper+0x10; release pooled frame'),
                dict(site='0xEDF6E84..0xEDF6F06',edge='same TaskContext+0x18 owner -> +0xE0 top frame can supply dynamic override only under +0xA0 flag and key-membership gates'),
            ]
            trace['candidate_isolation_authority']='Normal-path stack edges observed; pooled reset, exception unwind, predicate lifetime/owner remain unresolved.'
    herta=next(r for r in baseline if 'Herta' in r['root'])
    modifier=dict(parent=herta['root'],task_hash=herta['task_hash'],task=herta['current_task'],definition='MAvatar_Herta_Skill02_CheckHp',selected_target='Caster',exact_definition_join='MISSING',application_instance_context_listeners='MISSING',executed=0,stop='After dynamic source stop; reuses R29 AddModifier method evidence. String identity alone does not construct R17 instance. No new method acquisition.')
    files.append(control('original_task_execution',cohorts={'SOURCE_EVIDENCED_EXECUTION':dict(new_tasks=0),'EXPLICIT_REFERENCE_EXECUTION':dict(new_tasks=0,new_inputs=0),'STRUCTURAL_ONLY':dict(selected_dynamic_tasks=2)},parents=roots,source_to_execution=traces,saved_command_replays='tmp/audit/r30_dynamic_context_closure_20261108_001/replays.json',original_addmodifier=modifier,source_native_parent_advancement=0,full_canonical_skills=0,original_monster_actions=0,monster_AI_rules=0,new_executable_task_families=0,monster_chains=[[1002013,100201301],[1002014,100201401],[1002040,100204001]],monster_shared_binding_promoted=False))
    files.append(control('native_numeric',storage='64-bit raw RPG.GameCore.FixPoint; property provider returns raw +0x48 without integer conversion at property task call site',count_packing=dict(input='sign-extended wrapping int32 accumulator r12d',branch='abs(count) < 0x40000000',small='signed64(count << 33)',large='signed64((count << 26) | 1)',sites=['0x163ECE6E','0x163ECE90'],rounding='integer shifts only in count packing; no fractional rounding',overflow='inc r12d wraps 32 bits; accepted encoder input restricted to signed int32; representable list loop cannot authorize arbitrary overflow policy'),clamp='Selected native Clamp compares bit-0 mode tags; mixed paths use arithmetic shift by 7 and low-seven-bit checks. Full numeric oracle NOT established.',r12_r19=dict(scale=1<<33,small_count_raw_compatible=True,tagged_mode_supported=False,compatibility_is_not_execution_authority=True),offline_transliteration='tools/runtime/r30_numeric.py',raw_examples={str(n):__import__('r30_numeric').pack_observed_count(n) for n in [0,1,-1,(1<<30)-1,1<<30,-(1<<31)]},native_conversion_installed=False))
    acceptance={k:'BLOCKED_NO_ADAPTER_AUTHORITY' for k in ['exact TaskContext ownership','scope-0 lookup order execution','missing owner/parent execution','keyed entry runtime identity','unknown setter interface rejection by new adapter','callback exactly once','empty target-selection execution','unknown source property execution','candidate context isolation','R15 new adapter owned work and rollback']}
    acceptance.update({'count raw packing':'OFFLINE_TRANSLITERATION_TESTED','source IR unchanged':'TESTED_ORIGINAL_RECEIPTS','clone/snapshot/hash/replay':'FRESH_SAVED_PUBLIC_COMMAND_REPLAYS','original Lynx task/parent':'FRESH_FAIL_CLOSED_PARENT_REPLAY; TASK NOT EXECUTED','original Klara task/parent':'FRESH_FAIL_CLOSED_PARENT_REPLAY; TASK NOT EXECUTED'})
    files.append(control('semantic_gaps',verdict='DYNAMIC_CONTEXT_AUTHORITY_BLOCKED',tickets=tickets,budget=dict(new_method_bodies=3,limit=12,dependency_hops=1,max_allowed_hops=2,paths=new['paths'],exceptions=[],stop='Concrete entry/provider identity and status contracts require source evidence not present in bounded selected graph. Stop dynamic branch; no reference default authored.'),acceptance=acceptance,inherited_gaps=read(ROOT/'data/control/generic_runtime_r29_semantic_gap_ledger_v1_20261108_001.json')['gaps'],camera_remaining=68,frozen=[632,160,161],stable_prefixes=72,historical_prefixes=73,full_native_skills=0,recommended_R31='Obtain exact entry construction/provider artifact for MDF_Lynx_MaxHpValue plus concrete FFKBNBIMMHE implementation/vtable and original invocation TaskContext. Resolve those before further task decoding or Monster synthesis.'))
    write('static_setter_receipts.json',read(files[1]));write('source_to_execution.json',traces);write('acceptance_status.json',acceptance);write('modifier_stop.json',modifier)
    table='\n'.join('| '+r['root']+' | '+str(r['before'])+' | '+str(r['after'])+' | '+r['next_task']+' |' for r in roots)
    tests_doc=read(AUDIT/'tests/results.json') if (AUDIT/'tests/results.json').exists() else {}
    scenarios=read(AUDIT/'tests/scenarios.json') if (AUDIT/'tests/scenarios.json').exists() else {}
    replay=read(AUDIT/'replays.json') if (AUDIT/'replays.json').exists() else {}
    if replay:
        from hsr_battle_agent.battle_ir.behavior import IRNode
        for row in replay['original_parents']:
            b=next(b for b in bindings['roots'] if b['root']==row['root'])
            if isinstance(b['next_gap'],dict) and 'node' in b['next_gap']:
                row['baseline_task_hash']=next(r['task_hash'] for r in baseline if r['root']==row['root'])
                row['task']=b['next_gap']['node'];row['task_hash']=IRNode.from_dict(row['task']).stable_hash()
                row['task_identity_authority']='Exact unchanged R29 saved post-reference gap node; baseline identity retained separately'
                assert row['task']['op']==b['next_task']
        write('replays.json',replay)
    REPORT.write_text(f'''# R30 dynamic context closure

CR `{CR}`. Starting HEAD `{gate_doc['head']}`, branch `{gate_doc['branch']}`. Verdict **DYNAMIC_CONTEXT_AUTHORITY_BLOCKED**. The bounded investigation is complete; dynamic task execution is not established. No native-effective equivalence is claimed.

R29 controls, exact selected method hashes/disassembly, seven original baselines, operand/context ledgers, replay receipts, R28 pinned overlay and R27 Phase evidence were reused. Their hashes are retained in evidence_inputs.json and inherited_controls.json. Starting staged, unstaged and untracked work is preserved. Production/admission code changes: none. M10-M15, ScenarioCompiler and strict admission remain frozen. Git writes: NONE.

The writer's interface identity is now exact: FFKBNBIMMHE (type 10867), global 0x9804FA0. Slots 3, 4, 5, 7 are get_Val, set_Val, get_MinValue, get_MaxValue. The exact keyed entry object is read from array +0x30+24*lookup-index, with no replacement/insertion. Negative lookup returns without mutation/callback. Null and bounds failures have exception paths. The normal path gets old value, min, max, calls FixPoint.Clamp, invokes set_Val, then optionally reads new Val and calls the store's delegate at 0x1DCA134D. This is one direct normal-path call site, not proof of exactly-once transitive listener effects. Concrete entry implementation, listener subscriptions, callback reentrancy, exception rollback and continuation remain unknown: **DYNAMIC_ENTRY_SETTER_AUTHORITY_MISSING**.

Scope 0 has an observable ordered graph: initial owner override stack, context+0x48 linked stack chain, context+0x50 TaskTemplate interface, context+0x28 store, current virtual ability owner store, GetOwnerCustomData, further typed entity/component owner fallbacks, then a gated global fallback store. Every relevant lookup checks key membership. The saved jump table proves scope 0 enters 0xEDF7148 after shared fallbacks. Scope 9 shares the initial path then takes its own diagnostic fallback; scopes 1..8 have a separate table. Full field-name/offset joins, instance reference identity and child/parent propagation are not closed. Offsets and exact sites are in dynamic_context control, not substituted with a flat dictionary.

Only three additional method bodies were acquired, one dependency hop each: GetOwnerCustomData (0xF0EA840), FixPoint.Clamp (0x1EC22590), and predicate/task status dispatcher (0xB904BF0). Each has an exact blocker and evidence hypothesis in native_methods.json. The first exposes context+0x90 and +0x88 provider branches. The dispatcher captures task status at +0x10 after virtual slot +0xF0 and before the later +0xF8 call, returning the captured status; 0x9999 cannot be generalized as TRUE. Further concrete providers remain absent. Budget 3/12 bodies, 1/2 hops, two related paths; no exceptions, no broad asset discovery or recrawl. This is the documented source-evidence stop condition.

Lynx's original unchanged task selects Caster with mask 0x3F, takes the first result and accesses AbilityProperty 1. Empty selection reaches an out-of-range path (0x127102B2), not zero. The property object returns raw +0x48; absent-property global value is unresolved. No source property value or keyed entry was invented. Klara's AliveOnly true selects mask 1, false selects 15. A pooled LPNPMKNMMOK frame is pushed through TaskContext+0x18 owner -> +0xE0 wrapper -> +0x10 stack, with candidate installed at frame +0x20, predicate dispatched, status compared with 0x9999, count conditionally incremented and stack popped on the normal path. Exception isolation and predicate owner contracts remain gaps. Both tasks remain STRUCTURAL_ONLY.

Count packing is precisely recorded: signed int32 count is extended; abs(count) below 2^30 uses count<<33, otherwise (count<<26)|1. The standalone offline transliteration tests raw boundaries and rejects unsupported inputs. R12/R19 scale 2^33 matches bounded small integer raw packing; tagged extended values are rejected by existing R12. Neither this match nor native Clamp metadata authorizes full property/mixed numeric semantics. No conversion was installed in runtime.

| Original parent | Before | After | Actual next blocker task |
| --- | ---: | ---: | --- |
{table}

These counts include inherited explicit reference inputs and are not native-evidenced completions. R30 new source-evidenced tasks: 0; new explicit-reference tasks/inputs: 0; new executable families: 0. Full canonical skills: 0. Original Monster actions: 0. Source-backed Monster AI rules: 0. Native-effective validations: 0. The source-to-execution trace preserves exact caller/child ownership, task hashes and serialized operands, with the current R15/R20 gap boundary.

After the dynamic stop, one Herta AddModifier blocker was inspected: MAvatar_Herta_Skill02_CheckHp targeting Caster, exact task hash {herta['task_hash']}. The source definition join and application instance/listener authority are absent. No R17 instance was created; no reference removal count was repurposed. Kafka/Sampo and Monster chains 1002013→100201301, 1002014→100201401, 1002040→100204001 retain their exact gaps. No new shared context capability is eligible for promotion. Camera bodies remaining: 68.

Fresh saved-stage replays: {len(replay.get('saved_scenarios',[]))}; unchanged snapshots, clones and public command replay hashes checked. Fresh unit/spec receipts: {json.dumps({k:dict(cases=v['case_count'],exit=v['actual_exit_code']) for k,v in tests_doc.items()})}. Fresh scenario/root receipts: {json.dumps({k:dict(cases=v['case_count'],exit=v['actual_exit_code']) for k,v in scenarios.items()})}. R22 A–L receipt is separate. Runtime suite includes R12–R28 focused tests and R30 negative original-parent tests. Counts of roots/scenarios and unittest cases are not summed together. Tests/results.json, scenarios.json and input_hashes.json retain commands, real exit codes, timestamps, completion and source/input hashes. Historical test results do not substitute for these runs.

Acceptance limitation: no authority-backed adapter exists, so runtime tests for scope lookup, missing owners, concrete entry identity, callback exactly once, empty native selection and candidate context isolation remain BLOCKED, explicitly listed in acceptance_status.json. Seven focused R30 tests cover preserved evidence, raw packing and original parent refusal/replay. They are not represented as successful adapter/native execution. Existing runtime tests cover prior transaction/rollback behavior only.

Architecture: no production files, second dynamic registry, event bus or character dispatcher added. Frozen corpus 632/160/161 and original hashes preserved; stable 72 and historical 73 remain distinct. Recommended R31: obtain the concrete keyed entry construction/provider artifact and original invocation TaskContext for MDF_Lynx_MaxHpValue, prove FFKBNBIMMHE implementation/vtable/listeners, then bind R19 and replay Lynx before widening scope. Beam/MCTS remain deferred.
''',encoding='utf8')
    print('controls/report written',flush=True)
def package():
    preserve()
    assert len(read(AUDIT/'tests/results.json'))==4
    assert all(v['actual_exit_code']==0 for v in read(AUDIT/'tests/results.json').values())
    assert len(read(AUDIT/'tests/scenarios.json'))==5
    assert all(v['actual_exit_code']==0 for v in read(AUDIT/'tests/scenarios.json').values())
    assert read(AUDIT/'tests/turns.json')['actual_exit_code']==0
    assert len(read(AUDIT/'replays.json')['saved_scenarios'])==17
    tested=read(AUDIT/'tests/input_hashes.json')
    final_tested={n:sha(ROOT/n) for n in tested if n.startswith(('src/','tests/'))}
    assert all(tested[n]==h for n,h in final_tested.items())
    write('tests/final_source_verification.json',dict(timestamp=now(),production_and_test_files_checked=len(final_tested),all_match_tested_bytes=True,hashes=final_tested,authoring_harness_changes_after_launch={n:dict(tested=h,final=sha(ROOT/n)) for n,h in tested.items() if n.startswith('tools/runtime/r30_') and sha(ROOT/n)!=h},supplemental_evidence='tests/r30_evidence_input_hashes.json'))
    write('final_summary.json',dict(verdict='DYNAMIC_CONTEXT_AUTHORITY_BLOCKED',starting_head=read(AUDIT/'start_gate.json')['head'],new_methods=3,new_original_executable_task_families=0,original_lynx_task_executable=False,lynx_parent=[1,1],original_klara_task_executable=False,klara_parent=[0,0],new_addmodifier=0,full_canonical_skills=0,original_monster_actions=0,native_effective_validations=0,frozen=[632,160,161],production_files=[],tests=['tests/battle_runtime/test_behavior_r30.py'],fresh_tests=read(AUDIT/'tests/results.json'),fresh_scenarios=read(AUDIT/'tests/scenarios.json'),fresh_R22=read(AUDIT/'tests/turns.json'),historical_tests_used_instead_of_fresh=False,git_writes='NONE'))
    paths=[ROOT/'data/control'/('generic_runtime_r30_'+n+'_v1_20261108_001.json') for n in CONTROL_NAMES]
    paths += [REPORT,ROOT/'tests/battle_runtime/test_behavior_r30.py',*[ROOT/'tools/runtime'/n for n in ['r30_closure.py','r30_deliver.py','r30_sources.cjs','r30_numeric.py']]]
    paths += [p for p in AUDIT.rglob('*') if p.is_file() and p.suffix in ['.json','.txt','.log'] and 'test_tmp' not in p.parts and p.name not in ['handoff_manifest.json','handoff_verification.json']]
    # Reused native text only, never game binaries or source archives.
    paths += [ROOT/r['path'] for r in read(ROOT/'data/control/generic_runtime_r30_dynamic_context_v1_20261108_001.json')['reused_evidence']]
    paths=sorted(set(paths));members={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in paths}
    write('handoff_manifest.json',dict(change_request=CR,files=members,manifest_excludes_itself=True));paths.append(AUDIT/'handoff_manifest.json')
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None;assert set(z.namelist())=={p.relative_to(ROOT).as_posix() for p in paths}
        for n,m in members.items():assert len(z.read(n))==m['size'] and hashlib.sha256(z.read(n)).hexdigest()==m['sha256']
    write('handoff_verification.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(paths),CRC='PASS',exact_member_set='PASS',member_sizes_sha256='PASS'))
    print(json.dumps(read(AUDIT/'handoff_verification.json')),flush=True)
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='package':package()
    else:main()
