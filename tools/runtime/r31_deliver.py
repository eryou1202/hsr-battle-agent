"""R31 controls, final-byte verification and exact-patch handoff."""
from r31_execution import *
import difflib
import base64
CR='CR-R31-REAL-TASK-EXECUTION-BREAKTHROUGH-20261108-001'
PRODUCTION=['src/hsr_battle_agent/battle_runtime/original_bindings.py','src/hsr_battle_agent/battle_runtime/behavior_expansion.py']
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_original_task_breakthrough_20261108_001.md'

def IR_hash(value):
    from hsr_battle_agent.battle_ir.behavior import IRNode
    return IRNode.from_dict(value).stable_hash()

def controls():
    # Read and hash all prior controls, saved root executions and selected bodies.
    inputs={}
    for folder in [OLD, ROOT/'tmp/audit/r30_dynamic_context_closure_20261108_001']:
        for p in folder.rglob('*'):
            if p.is_file() and p.suffix in ('.json','.txt') and 'test_tmp' not in p.parts:
                if p.suffix=='.json':read(p)
                else:p.read_text(encoding='utf8')
                inputs[p.relative_to(ROOT).as_posix()]=sha(p)
    for p in (ROOT/'data/control').glob('generic_runtime_r[23][90]_*.json'):
        read(p);inputs[p.relative_to(ROOT).as_posix()]=sha(p)
    write('inherited_evidence_read.json',inputs)
    roots=read(OLD/'character/results.json')
    jade=[read(AUDIT/'jade'/n/'receipt.json') for n in ['b','false']]
    ownership=[]
    for row in jade:
        state=read(AUDIT/'jade'/row['target']/'final_runtime.json')['state']
        scheduler=state['scheduler']['action_execution']
        root=scheduler['roots'][scheduler['current_root']]
        assert root['status']=='RUNNING' and not root['completion_requested']
        ownership.append(dict(scenario=row['target'],canonical_root=root,
            predicate_hash=row['original_predicate_hash'],result=row['decisions'],
            next_original_task_hash=IR_hash(row['next_gap']['node']),
            next_original_source_pointer=row['next_gap']['node']['authority']['source_pointer'],
            owned_pending_containers=[dict(frame_id=k,status=v['status'],node_id=v['node']['node_id'],op=v['node']['op'])
                for k,v in scheduler['tasks'].items() if v['status']=='WAITING'],
            completed_leaf_tasks=scheduler['metrics']['tasks_completed'],finish_fabricated=False))
    write('source_to_execution.json',ownership)
    native=read(AUDIT/'native_methods.json')
    reasons={
        '0x1E4113D0':(0,'Bind original masks 4/8 to config target operands; inherited IR listed reader RVA only'),
        '0x1E4113C0':(0,'Prove omitted AliveStateMask default 15; base flag initialization'),
        '0x160A6E00':(0,'Exact config-cast factory and executor allocation identity'),
        '0xE808840':(1,'Concrete Evaluate: left null false; scalar entity identity comparison'),
        '0xE808810':(1,'Executor constructor config/context offsets and initial status'),
        '0xEDE81C0':(2,'First entity of target collection or null; collection release before return')}
    for m in native['methods']:
        assert sha(AUDIT/m['artifact'])==m['sha256']
        m['dependency_hop'],m['reason_and_evidence_gain']=reasons[m['rva']]
    write('method_budget.json',dict(new_bodies=len(native['methods']),limit=20,max_dependency_hops=3,
        observed_max_new_hops=2,reused_third_hop='R29 TaskContext.EvaluateTarget 0xF0EBD00',
        families=['SetDynamicValueByProperty','ByCompareTarget'],methods=native['methods']))
    entry=dict(verdict='NO_GO',gap='DYNAMIC_CONCRETE_ENTRY_PROVIDER_MISSING',
        interface='FFKBNBIMMHE',type_index=10867,global_rva='0x9804FA0',
        status='EXACT_CLASS/INTERFACE_IDENTITY',
        census=read(AUDIT/'metadata.json')['census_status'],
        exact_implementers=None,name_discovery_candidates=[],
        limitation='No decoded interface-offset/implemented-interface table available in the reused metadata tooling. Empty name scan is NOT an empty implementer census.',
        required=['Pinned implemented-interface/interface-offset table decoder and concrete vtable slots 3/4/5/7',
            'Actual constructor and storage registration keyed MDF_Lynx_MaxHpValue',
            'Original invocation TaskContext instance graph and chosen scope-0 store'],
        runtime_entry_identified=False,new_native_bodies=0)
    lynx=next(r for r in roots if 'Lynx' in r['root'])
    context=dict(verdict='NO_GO',root=lynx['root'],before=1,after=1,
        original_task=lynx['current_task'],task_hash=lynx['task_hash'],
        concrete_entry=None,construction_registration=None,TaskContext_identity=None,
        property=dict(selector='Caster',native_mask=63,AbilityProperty=1,value_provider=None,
            empty_selection='SOURCE_OUT_OF_RANGE_EXCEPTION_NOT_ZERO'),
        getter_setter='Interface operation order only; no concrete implementation',
        callbacks='Store delegate call site observed; registration, reentrancy, rollback and continuation unknown',
        source_contract='data/control/generic_runtime_r30_keyed_setter_v1_20261108_001.json',
        gap='DYNAMIC_CONCRETE_ENTRY_PROVIDER_MISSING',adapter_installed=False)
    predicate=dict(verdict='ORIGINAL_PREDICATE_EXECUTABLE_WITH_REFERENCE_CONTEXT',
        original_node=original()[1].to_dict(),original_hash=original()[1].stable_hash(),
        factory='0x160A6E00',allocation_global='0x98B3860',executor='DACHDDJDBDK type 55645',
        evaluate='0xE808840',helper='0xEDE81C0',reader='0x1E4113D0',
        serialized_field_map={'mask4_config+0x20':'TargetType','mask8_config+0x28':'CompareType'},
        serialized_aliases=['AbilityTargetEntity','Caster'],mask_default=15,
        comparison='FIRST_NON_NULL_EQUAL',collection='First element only; empty left false and right not evaluated; empty right differs from nonnull left',
        source_operations='Unpatched same-build native bodies only; no native-effective validation',
        reference_policies=['MASK15_CALLER_RESOLVED_REFERENCE','BOOLEAN_TO_R15_BRANCH_REFERENCE','SERIALIZED_BRANCH_REFERENCE'],
        result_ownership='Existing R13 bool result -> existing R15 owned original branch container; no native 0x9999 claim',
        scenarios=jade,original_IR_edited=False)
    outcomes=[]
    for r in roots:
        name=r['root'];before=next(x for x in read(ROOT/'data/control/generic_runtime_r29_original_task_bindings_v1_20261108_001.json')['roots'] if x['root']==name)['after']
        outcomes.append(dict(root=name,before=before,after=8 if 'Jade' in name else before,
            original_IR_hash=r['original_IR_hash'],predicate_executed='Jade' in name,
            next_task='RPG.GameCore.AddModifier' if 'Jade' in name else r['current_task']['op']))
    execution=dict(verdict='FIRST_ORIGINAL_TASK_EXECUTOR_BREAKTHROUGH',
        qualification='New unchanged original PredicateIR family executes and canonical parent selects real next branch. No additional leaf TaskIR completion or complete parent is claimed.',
        newly_executable_original_task_families=['RPG.GameCore.ByCompareTarget'],
        original_predicate_evaluations_per_scenario=1,new_completed_leaf_tasks=0,
        parent_progression=outcomes,full_joined_canonical_skills=0,original_monster_actions=0,
        source_backed_monster_ai_rules=0,native_effective_validations=0,
        frozen=dict(combat_roots=632,joined_roots=160,joined_rows=161,historical_prefixes=73,stable_prefixes=72,camera_unresolved=68),
        statuses={'EXACT_SOURCE_BODY':True,'EXACT_CLASS/INTERFACE_IDENTITY':True,
            'EXACT_INSTANCE_PROVIDER':False,'ORIGINAL_OPERAND_BOUND':True,
            'REFERENCE_EXECUTABLE':True,'SOURCE_EVIDENCED_EXECUTABLE':'Comparison operation only; end-to-end context/status remain reference',
            'FULL_ORIGINAL_PARENT_COMPLETE':False,'NATIVE_EFFECTIVE_VALIDATED':False})
    gaps=dict(gaps=[entry['gap'],'JADE_ADDMODIFIER_INSTANCE_INPUT_MISSING',
        'NATIVE_MASK15_SELECTOR_AND_STATUS_AUTHORITY_MISSING','NATIVE_EFFECTIVE_VALIDATION_MISSING'],
        dynamic_negative_acceptance=dict(status='BLOCKED_NO_DYNAMIC_ADAPTER',cases=[
            'missing concrete implementer','missing keyed entry','wrong TaskContext owner','unknown property object',
            'missing setter','callback failure','invalid numeric domain']),
        predicate_negative_acceptance=dict(status='COVERED',cases=['unknown target selector','unknown entity',
            'unsupported result contract','extra serialized flags','missing binding','empty selection']),
        next='Recover exact Jade AddModifier construction/context for the actually reached self/other branch; preserve predicate reference boundary. No third excavation performed.')
    for name,value in [('entry_implementer',entry),('lynx_context',context),('jade_predicate',predicate),('original_task_execution',execution),('semantic_gaps',gaps)]:
        p=ROOT/'data/control'/f'generic_runtime_r31_{name}_v1_20261108_001.json'
        p.write_text(json.dumps(dict(change_request=CR,source_version='4.6.51',frozen_product_authority='4.4.54 separate',**value),indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')
    write('jade/results.json',jade)

def preserve():
    gate=read(AUDIT/'start_gate.json')
    changed=[n for n,h in gate['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    assert set(changed)==set(PRODUCTION),changed
    assert git('rev-parse','HEAD')==gate['head']
    assert git('branch','--show-current')==gate['branch']
    assert git('diff','--cached','--name-status')==gate['staged']
    inputs=read(AUDIT/'inherited_evidence_read.json')
    assert all(sha(ROOT/n)==h for n,h in inputs.items())
    tested=read(AUDIT/'fresh/tests/input_hashes.json')
    names=[n for n in tested if n.startswith(('src/','tests/'))]
    assert all(sha(ROOT/n)==tested[n] for n in names)
    write('preservation.json',dict(expected_production_changes=changed,other_starting_file_drift=[],
        inherited_evidence_files_verified=len(inputs),final_tested_source_and_test_files=len(names),
        head_unchanged=True,branch_unchanged=True,staged_unchanged=True,git_writes='NONE'))
    for n in PRODUCTION:
        final=(ROOT/n).read_text(encoding='utf8')
        if n.endswith('original_bindings.py'):
            start=final.index('\n\ndef bind_compare_target_reference')
            end=final.index('\n\ndef bind_remove_reference')
            before=final[:start]+final[end:]
            assert hashlib.sha256(before.replace('\n','\r\n').encode()).hexdigest()==gate['file_hashes'][n] or hashlib.sha256(before.encode()).hexdigest()==gate['file_hashes'][n]
        else:
            before=subprocess.check_output(['git','show','HEAD:'+n],cwd=ROOT).decode('utf8')
            assert hashlib.sha256(before.encode()).hexdigest()==gate['file_hashes'][n] or hashlib.sha256(before.replace('\n','\r\n').encode()).hexdigest()==gate['file_hashes'][n]
        patch=''.join(difflib.unified_diff(before.splitlines(True),final.splitlines(True),fromfile='a/'+n,tofile='b/'+n))
        p=AUDIT/'patches'/(Path(n).name+'.patch');p.parent.mkdir(exist_ok=True);p.write_text(patch,encoding='utf8')
        # Exact byte edits also preserve any starting newline representation.
        before_bytes=next(b for b in [before.encode(),before.replace('\n','\r\n').encode()]
            if hashlib.sha256(b).hexdigest()==gate['file_hashes'][n])
        final_bytes=(ROOT/n).read_bytes()
        edits=[dict(start=a,end=b,replacement_base64=base64.b64encode(final_bytes[c:d]).decode())
            for tag,a,b,c,d in difflib.SequenceMatcher(None,before_bytes,final_bytes,autojunk=False).get_opcodes()
            if tag!='equal']
        applied=before_bytes
        for edit in reversed(edits):
            applied=applied[:edit['start']]+base64.b64decode(edit['replacement_base64'])+applied[edit['end']:]
        assert applied==final_bytes
        write('patches/'+Path(n).name+'.bytes.json',dict(path=n,base_sha256=gate['file_hashes'][n],
            target_sha256=sha(ROOT/n),offset_unit='byte',application_order='reverse list order',edits=edits,
            independently_applied_to_starting_bytes='PASS'))
    write('production_patch_bases.json',{n:dict(starting_working_bytes_sha256=gate['file_hashes'][n],
        final_bytes_sha256=sha(ROOT/n),patch='patches/'+Path(n).name+'.patch') for n in PRODUCTION})

def report():
    tests=read(AUDIT/'fresh/tests/results.json');scenarios=read(AUDIT/'tests/scenarios.json')
    assert all(r['actual_exit_code']==0 for r in [*tests.values(),*scenarios.values()])
    assert len(tests)==4 and len(scenarios)==6
    jade=read(AUDIT/'jade/results.json')
    table='\n'.join(f"| {r['target']} | {r['decisions'][0]['predicate_result']} | 8 -> {r['after']} | {r['next_gap']['node']['payload']['reference_binding']['roles']['modifier']['payload']['value']} |" for r in jade)
    gate=read(AUDIT/'start_gate.json')
    REPORT.write_text(f'''# R31 REAL TASK EXECUTION BREAKTHROUGH COMPLETE

Starting HEAD: `{gate['head']}`. Branch: `{gate['branch']}`. CR `{CR}`.

Verdict: **FIRST_ORIGINAL_TASK_EXECUTOR_BREAKTHROUGH**, qualified as an unchanged original **PredicateIR** executor and observable R15 branch progression under explicit reference context/status. Newly executable original family: **ByCompareTarget**. Additional completed leaf TaskIR tasks: **0**. Full canonical skills: **0**. Native-effective validations: **0**. This is not a closed original skill or native parity claim.

Path A result: **NO-GO**, `DYNAMIC_CONCRETE_ENTRY_PROVIDER_MISSING`. Exact interface FFKBNBIMMHE / type 10867 is retained. Concrete keyed-entry implementer, constructor/registration/provider, Lynx TaskContext identity and property-value authority remain unavailable. The available metadata helper cannot decode implemented-interface/interface-offset tables; a name-discovery scan found no explicit interface-qualified method names and does **not** prove there are no implementers. The requested exact implementer census therefore remains incomplete. No A bodies or dynamic runtime adapter were added. Getter/setter operation order is inherited R30 evidence; listener subscriptions, reentrancy, rollback and continuation remain unknown. Lynx original task executable: no; parent **1 -> 1**. Klara remains **0 -> 0**. No arbitrary dictionaries or property values were installed. The investigation switched immediately to B.

Path B result: exact config type 23409 factory 0x160A6E00 allocates global 0x98B3860, type 55645 DACHDDJDBDK. Its Evaluate at 0xE808840 calls GetPredicateTarget at 0xEDE81C0 for each operand with config mask 15. The helper evaluates a collection and returns its first entity or null. Evaluate short-circuits false for a null left, otherwise compares entity identity with the first right. Reader 0x1E4113D0 maps bits 4/8 to config +0x20/+0x28; metadata names these TargetType/CompareType. Original aliases are AbilityTargetEntity and Caster, span [10644296,10644328). Constructor 0x1E4113C0 establishes omitted mask 15. No count, set intersection or ordered-list equality is inferred.

Implementation: a small opt-in binding in existing `original_bindings.py` supplies a per-original-hash contract inside the R13 policy. Existing `behavior_expansion.py` selects through R12/R13 and returns a boolean to the existing R15 branch mechanism. Original IR, canonical bindings and their hashes are unchanged. Additional serialized flags, unsupported result contracts, missing aliases and unknown entities fail closed. No new registry, predicate engine, character branch or scheduler finish was added.

The comparison operation has exact unpatched native body evidence. Mask interpretation, resolved aliases, native base-predicate flag/status lifecycle and branch handoff remain explicitly **reference** policies. `0x9999` is not asserted to be generic TRUE. IFix patched effective behavior is unvalidated. The default saved template inherits Caster as AbilityTargetEntity; the separate false case supplies resolved alias b explicitly. It does not claim native self/other legality.

| Scenario | Predicate result | Completed leaf tasks | Next original modifier |
| --- | --- | --- | --- |
{table}

Both canonical executions use original Phase01 -> Phase02/template ownership and reach the original AddModifier child. R15's branch container remains pending on its child, so the completed leaf count stays **8 -> 8**, although the predicate now executes and selects the next original node. Original finish ownership remains with the existing parent; no finish is fabricated. Herta 2, Fugue 12, Kafka 4, Sampo 1 remain unchanged. Original Monster actions **0**, executable source-backed Monster AI rules **0**.

Additional source bodies: **6/20**; at most **2 new dependency hops**, with existing R29 EvaluateTarget reused as the third hop. Two primary families only. Reasons, gains, hashes and exact ranges are in `method_budget.json`. No broad archive extraction, Camera recrawl, game launch, live attach, memory/process patching or third workstream occurred. Pinned 4.6.51 snapshot authority remains separate from frozen 4.4.54 product authority.

Determinism/replay: 17 inherited saved-stage replays plus both changed canonical scenarios; public commands, initial/final snapshots, clone and JSON round-trip hashes retained. Predicate and original ability hashes unchanged. Dynamic negative adapter cases remain explicitly BLOCKED, not reported as passing execution tests. R31 tests cover source hashes, unbound refusal, true/false, first-element behavior, empty-left short circuit, missing alias/entity, unsupported result/flags, snapshots and real canonical-parent replay.

Fresh final-source tests: {json.dumps({k:dict(cases=v['case_count'],exit=v['actual_exit_code']) for k,v in tests.items()})}. Full runtime includes R12-R31 available focused modules and R27/R28/R30 source/root tests. R21 specs are separate. Fresh scenario/root lanes: {json.dumps(scenarios)}. R22 covers A-K and L1-L3 (14 traces). Historical PASS records substitute for fresh tests: **no**. Earlier harness experiments are retained separately; authoritative final runs are under `fresh/tests`. Final tested source/test hashes are verified during packaging.

Frozen modified: **none** (M10-M15, ScenarioCompiler, strict admission unchanged). Corpus **632/160/161**, stable prefixes **72**, historical prefixes **73**, Camera unresolved **68** preserved. Frozen regressions compare observables and original IR hashes. Existing authorized staged/unstaged work is preserved; the only inherited file changes are the two requested runtime bridge changes.

Remaining exact blockers: Lynx concrete entry/store/provider and callback authority; Jade AddModifier original construction/application inputs in each selected branch; complete native selector-mask/status lifecycle; effective native validation. Recommended R32: close one actually reached Jade AddModifier instance/context contract using existing R17, then continue its original branch. Beam/MCTS remain deferred.

Production files: `original_bindings.py`, `behavior_expansion.py`. Tests: `test_behavior_r31.py` (11 cases). Git writes: **NONE**. Handoff: `{CR}_changed_files.zip`, with exact patches relative to the starting working bytes, additions, curated source/replay/test receipts and a member manifest. Archive/member SHA-256, sizes, CRC and exact member set are in `handoff_verification.json` beside the archive.
''',encoding='utf8')

def package():
    controls();preserve();report()
    write('final_summary.json',dict(verdict='FIRST_ORIGINAL_TASK_EXECUTOR_BREAKTHROUGH',
        qualification='Original PredicateIR operation and R15 branch progression; completed leaf task delta zero',
        source_methods=6,new_original_executable_families=1,new_leaf_tasks_completed=0,
        lynx_parent=[1,1],jade_parent=[8,8],full_canonical_skills=0,original_monster_actions=0,
        native_effective_validations=0,git_writes='NONE',
        fresh_tests=read(AUDIT/'fresh/tests/results.json'),fresh_scenarios=read(AUDIT/'tests/scenarios.json')))
    paths=[REPORT,ROOT/'tests/battle_runtime/test_behavior_r31.py',
        *list((ROOT/'tools/runtime').glob('r31_*.*')),
        *list((ROOT/'data/control').glob('generic_runtime_r31_*.json'))]
    paths += [p for p in AUDIT.rglob('*') if p.is_file() and p.suffix in ('.json','.txt','.log','.patch')
        and not any(x in p.parts for x in ['test_tmp','a']) and p.name not in ('handoff_manifest.json','handoff_verification.json')]
    # Exclude obsolete experimental root-suite receipts; authoritative final run retained.
    paths=[p for p in paths if p not in [AUDIT/'tests/results.json',AUDIT/'tests/input_hashes.json']]
    paths += [OLD/n for n in ['method_1dca0fd0.txt','method_edf6e30.txt','method_127100d0.txt','method_f0ebd00.txt']]
    paths=sorted(set(paths))
    members={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in paths}
    write('handoff_manifest.json',dict(change_request=CR,files=members,manifest_excludes_itself=True))
    paths.append(AUDIT/'handoff_manifest.json')
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={p.relative_to(ROOT).as_posix() for p in paths}
        for n,m in members.items():assert len(z.read(n))==m['size'] and hashlib.sha256(z.read(n)).hexdigest()==m['sha256']
    write('handoff_verification.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
        members=len(paths),CRC='PASS',exact_member_set='PASS',per_member_size_and_sha256='PASS',manifest_sha256=sha(AUDIT/'handoff_manifest.json')))
    print(json.dumps(read(AUDIT/'handoff_verification.json')),flush=True)
if __name__=='__main__':
    {'controls':controls,'package':package}[sys.argv[1]]()
