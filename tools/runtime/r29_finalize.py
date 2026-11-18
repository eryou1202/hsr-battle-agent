"""Curated R29 evidence controls and checksum-verified archive, no Git writes."""
import json
import zipfile
from pathlib import Path
from r29_assessment import ROOT,AUDIT,OLD,R27,read,write,sha,validate

CR='CR-R29-ORIGINAL-TASK-CONTEXT-CLOSURE-20261108-001'
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_original_executor_context_20261108_001.md'
CONTROLS=[]
def control(name,**v):
    p=ROOT/'data/control'/('generic_runtime_r29_'+name+'_v1_20261108_001.json')
    p.write_text(json.dumps(dict(change_request=CR,source_build='4.6.51',native_effective_validated=False,**v),indent=2,sort_keys=True)+'\n',encoding='utf8');CONTROLS.append(p)

def main():
    validate()
    gate=read(AUDIT/'start_gate.json'); native=read(AUDIT/'native_methods.json')
    assert len(native['methods'])==40
    for m in native['methods']:assert sha(AUDIT/m['artifact'])==m['sha256']
    rows=read(AUDIT/'character/results.json');refs=read(AUDIT/'reference/results.json');byref={r['root']:r for r in refs}
    den=read(ROOT/'data/control/generic_runtime_original_skill_semantics_v1_20261022_001.json')['denominators']
    # These are observations of unpatched native branches, not complete executors.
    facts=[
      dict(id='DYN_PROPERTY_FACTORY',method='0x160A9DD0',sites=['0x160A9DFA','0x160A9E35'],fact='Exact config cast and constructor call 0x1270FFF0 -> .DNOPKLPLACJ.'),
      dict(id='DYN_COUNT_FACTORY',method='0x160A9F40',sites=['0x160A9F6A','0x160A9FA5'],fact='Exact config cast and constructor call 0x163ECA00 -> .FFCLKNPNDCE.'),
      dict(id='DYN_PROPERTY_FLOW',method='0x127100D0',sites=['0x12710126','0x12710176','0x127101A5','0x127101EF','0x12710214'],fact='Context/scope/key lookup; target evaluation mask 0x3f; first result; TurnBasedAbilityComponent.GetProperty; dynamic lookup writer. Empty selection reaches ThrowArgumentOutOfRange_IndexException, not zero.'),
      dict(id='DYN_COUNT_FLOW',method='0x163ECB70',sites=['0x163ECC02','0x163ECC10','0x163ECC5C','0x163ECD08','0x163ECD35','0x163ECE10','0x163ECE6E','0x163ECEAB'],fact='AliveOnly selects evaluation masks 1 or 15. Per-candidate context assigned before predicate; 0x9999 result increments count; signed count encoded using shifts 33/26 and writer tail call. Mask bits and status lifecycle are not fully mapped.'),
      dict(id='DYN_SCOPE_PROVIDER',method='0xEDF6E30',sites=['0xEDF6E61','0xEDF6F75','0xEDF6F81','0xEDF6FA8','0xEDF7014'],fact='Scopes 0/9 have special lookup paths; scope 0 traverses owner/parent stores and further fallbacks. Scopes 1..8 dispatch through native table. A single supplied scope is insufficient.'),
      dict(id='DYN_PROPERTY_PROVIDER',method='0xF124690',sites=['0xF1246A8','0xF124711','0xF124771','0xF124797'],fact='Property indices 18/23 have computed branches, general path reads indexed property object +0x48. Native property object is not an R19 base-property assertion.'),
      dict(id='DYN_WRITER',method='0x1DCA0FD0',sites=['0x1DCA0FF7','0x1DCA1020','0x1DCA10B5'],fact='Writer locates keyed entry and invokes interface methods on stored object; not proved equivalent to dictionary assignment.'),
      dict(id='MODIFIER_FACTORY',method='0x160A9440',sites=['0x160A946A','0x160A94A5'],fact='Exact AddModifier cast -> .JAJPDPAHFOA constructor 0xB758240. OnTaskBegin 0xB7585A0 calls source/target evaluation and TryAddModifierInstance 0xF1290A0; full lifecycle not reconstructed.'),
      dict(id='DAMAGE_EXECUTOR',method='0xC9C5070',sites=[],fact='Direct calls include GetActualOwner, BeginAttack, StoreDamage, FireEvent, split-ratio helper and deferred modifier params. Exact serialized expression-to-stage mapping remains incomplete.'),
      dict(id='PROJECTILE_EXECUTOR',method='0x16E74CA0',sites=[],fact='Original FireProjectile config cast found by exact type load. Executor calls Retarget and HasBegunDyingProcess; callback builder 0x16E75370 constructs child task chain. No immediate completion/no-op equivalence.'),
      dict(id='FORMATION_EXECUTOR',method='0x161A94C0',sites=['0x161A94E2','0x161A94E6','0x161A954D'],fact='Config/context fields packed into application argument block for 0x16A8CC50. Helper evaluates targets; native formation state still absent. Shared RVA call names are candidates, not disambiguated identities.'),
      dict(id='DISTANCE_EXECUTOR',method='0xB628010',sites=['0xB6280BF','0xB628114','0xB628295','0xB6282B8','0xB6283D3'],fact='From/To predicate selectors; fallback GetMovementTargetPos; vector differences and sqrtss; float-to-native numeric conversion; radius sum adjustment. Unit, conversion constants, final comparator and scene authority not fully closed.'),
      dict(id='DISTANCE_RADIUS',method='0xB628510',sites=['0xB62854E','0xB62856A','0xB628570','0xB628585','0xB6285B1'],fact='Position from component +0x118/+0x120. IgnoreRadius flag +0x40 returns zero radius while retaining position. Otherwise component virtual radius getter; missing radius component also returns zero in this branch. This does not authorize zero position/distance.'),
      dict(id='AI_SEQUENCE_AXIS',method='0xCB44EE0',sites=['0xCB44F2F','0xCB44F91','0xCB44F94','0xCB44F9A','0xCB44FC7','0xCB4501B'],fact='GetAISkillSequence or fallback config; (context field +1) modulo sequence length, then two search segments using candidate helper. Field ownership/reset and complete eligibility semantics not proved.'),
      dict(id='AI_ACTION_DEPENDENCY',method='0xBAD72D0',sites=['0xBAD7340','0xBAD7388'],fact='Action reads sequence and invokes 0xED36EA0 plus skill conversion helper. 0xED36EA0 delegates through virtual operation and increments stored/global counter; do not label this sequence cursor advancement without resolving provider.'),
    ]
    for f in facts:
        f.update(authority='SAME_BUILD_UNPATCHED_METHOD_OBSERVATION',status='ORIGINAL_EXECUTOR_OPERATION_PARTIALLY_EVIDENCED',artifact='method_'+f['method'][2:].lower()+'.txt')
    gaps={
      'Lynx':dict(kind='DYNAMIC_CONTEXT_PROVIDER_MISSING',required=['TaskContext owner/parent/child/modifier data graph for scope 0','AbilityProperty 1 effective property authority','dynamic keyed entry object and listener/write callback contract','native numeric representation conversion to R19 contract'],methods=['0x127100D0','0xEDF6E30','0xF124690','0x1DCA0FD0']),
      'Klara':dict(kind='DYNAMIC_CONTEXT_PROVIDER_MISSING',required=['same dynamic scope/write ownership graph','selector state mask 1/15 bit meanings','candidate predicate context stack and status 0x9999 lifecycle','modifier containment against exact instance context','native count representation conversion'],methods=['0x163ECB70','0xEDF6E30','0x1DCA0FD0']),
      'Modifier':dict(kind='MODIFIER_CONSTRUCTION_INPUT_MISSING',required=['exact modifier definition and source shard join per application','caster/source/target application context','native instance initialization duration/stack/refresh contract','complete listener/provider/effect callbacks and event order'],methods=['0xB7585A0','0xF1290A0','0xB75A370']),
      'Kafka':dict(kind='DAMAGE_REFERENCE_INPUT_MISSING',required=['AttackData field-to-formula and stage mapping','effective property and dynamic lookup values','target order and hit split settlement authority','callbacks and modifier delay ownership'],methods=['0xC9C3BC0','0xC9C5070']),
      'Sampo':dict(kind='PROJECTILE_WORLD_PROVIDER_MISSING',required=['native launch/world/collision service','original source/target snapshot and update authority','impact callback child task context','completion barrier and tick/reset contract'],methods=['0x16E74CA0','0x16E75420','0x16E755D0','0x16E75370']),
      'Formation':dict(kind='FORMATION_PROVIDER_MISSING',required=['exact formation config object','team/caster/servant and center/member count','formation component storage and callbacks','targetability/position updates and completion'],methods=['0x161A9450','0x161A94C0','0x16A8CC50']),
      'Distance':dict(kind='SPATIAL_PROVIDER_MISSING',required=['authoritative scene positions and units','radius component virtual provider','float/native representation constants and comparator','movement-target fallback context'],methods=['0xB628010','0xB628510']),
      'AI':dict(kind='AI_SEQUENCE_CONTEXT_PROVIDER_MISSING',required=['sequence source/stepper state owner','skill trigger conversion and availability','candidate helper condition/result ownership','action provider virtual operation/counter and reset boundary'],methods=['0xCB44EE0','0xCB452F0','0xBAD72D0','0xED36EA0']),
      'Camera':dict(kind='ORIGINAL_OWNING_PROVIDER_ARTIFACT_REQUIRED',required=['new exact same-build owning provider and caller-to-body map'],methods=[])
    }
    matrix=[]
    for r in rows:
        ref=byref.get(r['root']); after=ref['after_completed'] if ref else r['after_completed']
        nextnode=ref['next_gap']['node'] if ref else r['current_task']
        matrix.append(dict(root=r['root'],before=r['before_completed'],after=after,next_task=nextnode['op'],next_gap=ref['next_gap'] if ref else r['next_SemanticGap'],unchanged_original_IR_hash=r['original_IR_hash'],before_runtime_hash=r['final_runtime_hash'],after_runtime_hash=ref['final_runtime_hash'] if ref else r['final_runtime_hash']))
    counters=dict(new_exact_source_provider_joins=0,new_method_bodies_acquired=40,new_fully_decoded_executor_semantics=0,new_original_task_families_supported=0,
        original_task_executions_with_new_reference_inputs=sum(len(r['bindings']) for r in refs),new_same_build_partial_observations=len(facts),
        new_source_complete_operand_bindings=0,new_source_native_parent_tasks_completed=0,new_reference_parent_tasks_completed=sum(r['after_completed']-r['before_completed'] for r in refs),
        full_joined_skill_transitions=0,exact_monster_actions_completed=0,executable_original_AI_rules=0,native_effective_validated_actions=0)
    control('executor_context',starting_head=gate['head'],denominators=den,observations=facts,native_methods=native,blockers=gaps,
        budget=dict(methods=40,limit=40,max_dependency_hops=3,paths=['dynamic scope/property','modifier construction','damage stage','projectile/formation/spatial scene','monster AI'],
            exceptions=['Targeted config-type cross-reference scan over pinned code section to locate obfuscated executor factories; no registry initializer decoded or asset recrawl.']),
        generic_contract_status='NOT_INSTALLED_INCOMPLETE_CONTEXT_AUTHORITY',counters=counters)
    control('original_task_bindings',roots=matrix,baseline_receipts='character/results.json',reference_receipts=refs,
        tiers=dict(ORIGINAL_BODY_DECODED='Inherited exact tasks unchanged',ORIGINAL_OPERAND_ROLE_EVIDENCED='Partial same-build observations',ORIGINAL_EXECUTOR_SEMANTICS_EVIDENCED=False,
            ORIGINAL_TASK_REFERENCE_EXECUTABLE='Existing RemoveModifier family only',ORIGINAL_PARENT_REFERENCE_COMPLETE=False,ORIGINAL_MONSTER_ACTION_COMPLETE=False,NATIVE_EFFECTIVE_VALIDATED=False),
        correction='R28 report prose incorrectly calls Fugue/Jade current blockers AddModifier. Exact R28 gap_node/hash identifies further RemoveModifier tasks. Original controls were not edited.')
    definitions=[]
    for r in rows:
        if any(n in r['root'] for n in ['Fugue','Jade','Herta']):
            ref=byref.get(r['root']);node=ref['next_gap']['node'] if ref else r['current_task']
            definitions.append(dict(root=r['root'],actual_next_task=node,exact_definition_join='NOT_ESTABLISHED',construction_inputs='NOT_SUPPLIED'))
    control('modifier_construction',cohort_A=dict(status='BLOCKED',executed=0,reason=gaps['Modifier']),cohort_B=dict(status='NOT_CONSTRUCTED',executed=0,reason='No caller-supplied instance/lifetime construction policy. Removal reference policy is not construction.'),applications=definitions,
        engine='Existing R17 only',second_engine=False)
    kafka=next(r for r in rows if 'Kafka' in r['root'])
    operands=[]
    def visit(v,path=''):
        if isinstance(v,dict):
            if 'start' in v and 'end' in v and any(k in v for k in ['mask','int32_operands','signed_payload','value']):
                operands.append(dict(pointer=path,source_span=[v['start'],v['end']],source_value=v,body_status='ORIGINAL_BODY_DECODED',executor_role_status='PARTIAL_OR_UNBOUND',numeric_authority='NOT_BOUND'))
            for k,x in v.items():visit(x,path+'/'+k)
        elif isinstance(v,list):
            for i,x in enumerate(v):visit(x,path+'/'+str(i))
    visit(kafka['current_task']['payload'])
    control('damage_context',root=kafka['root'],original_task=kafka['current_task'],operand_ledger=operands,blocker=gaps['Kafka'],pipeline='R18/R19 unchanged',new_reference_scenarios=0,enum_roles='Inherited DOT/DOT_Poison strings establish enum/provider roles only')
    control('monster_ai_semantics',original_body=read(OLD/'monster/AI_result.json'),observations=[f for f in facts if f['id'].startswith('AI_')],blocker=gaps['AI'],rules_newly_decoded=0,rules_executed=0,structure_only=True)
    control('monster_action_census',chains=[[1002013,100201301],[1002014,100201401],[1002040,100204001]],replays=read(AUDIT/'monster/results.json'),completed=0,formation=gaps['Formation'],distance=gaps['Distance'],authored_substitution=False)
    control('semantic_gap_ledger',denominators=den,counters=counters,roots=matrix,gaps=gaps,camera_unresolved=68,
        verdict='EXECUTOR_EVIDENCE_ADVANCED_REFERENCE_PREFIXES_ONLY',preferred_success_bar=False,
        recommended_R30='Bind scope-0 TaskContext ownership and keyed dynamic setter interface before R19 integration; close native numeric conversion and selector masks. Then exact AddModifier construction; keep Beam/MCTS deferred.')
    tests={n:read(AUDIT/'tests'/(n+'.json')) for n in ['battle_ir','battle_sandbox','R21','R27','R28']}
    assert all(t['exit_code']==0 for t in tests.values())
    write('final_tests.json',dict(fresh=tests,fresh_count=sum(t['tests'] for t in tests.values()),inherited=read(AUDIT/'tests/inherited.json'),
        runtime_code_changed=False,full_runtime_fresh=False,final_runtime_source_hashes={n:h for n,h in gate['file_hashes'].items() if n.startswith('src/hsr_battle_agent/battle_runtime/')},
        limitation='651 runtime cases and their R12-R26/R22/R24/R25/R26 subsets revalidated against tested input hashes, not freshly rerun. No production/runtime-admission code changed.'))
    table='\n'.join('| '+r['root'].split('_Skill02')[0]+' | '+str(r['before'])+' | '+str(r['after'])+' | '+r['next_task']+' |' for r in matrix)
    facttext='\n\n'.join('`'+f['id']+'` — `'+f['method']+'`: '+f['fact'] for f in facts)
    REPORT.write_text(f'''# R29 original executor context investigation

CR `{CR}`. Starting HEAD `{gate['head']}`; branch `{gate['branch']}`. Investigation and handoff complete; **preferred executor/context execution success is NOT established**. Verdict: **EXECUTOR_EVIDENCE_ADVANCED_REFERENCE_PREFIXES_ONLY**. No full joined character skill, original Monster action, source-backed executable AI rule or native-effective outcome is claimed.

Forty same-build method bodies were acquired and hashed under the pinned 4.6.51 snapshot. These establish partial operations and exact executor factory/class mappings; they do not establish forty complete executor semantics. Frozen 4.4.54 product authority remains separate. All inherited production and historical controls remain byte-identical. M10-M15, ScenarioCompiler and strict admission changed: **no**. Git writes: **none**.

| Parent | R28 completed | R29 reference completed | Actual next task |
| --- | ---: | ---: | --- |
{table}

The R28 report text incorrectly described Fugue/Jade's blockers as AddModifier. Their exact gap hashes and serialized bodies identify further RemoveModifier tasks. R29 preserves those historical artifacts, records the correction, and applies the already existing R17 bridge only to exact subsequent removals. Every new removal has an explicit CANCEL_NOT_STARTED_REFERENCE callback policy and empty identity filter. No instance is created. New reference completions: **{counters['new_reference_parent_tasks_completed']}**, new executable task families: **0**, new source-native parent task completions: **0**. These are reference inputs, not recovered native removal semantics.

The new method evidence is:

{facttext}

The deepest dynamic-value blocker is the actual scope-0 TaskContext owner/parent/child/modifier graph plus keyed entry write/listener behavior, not a missing property dictionary. The property executor takes the first selected result and throws on empty selection; it does not justify unknown-to-zero. Klara's AliveOnly masks and candidate context are partly observed, while complete mask meanings, predicate status ownership and native numeric conversion remain unbound. A contract has therefore not been installed. Native methods contain IFix branches; these observations cover their unpatched paths and never establish patched effective parity.

AddModifier cohort A (exact source construction): **0**, blocked on exact definition joins and full application/instance/listener/lifetime inputs. Cohort B (explicit reference construction): **0**, no caller-supplied construction contract. Removal policy does not authorize construction. The R17 engine remains the sole modifier lifecycle.

Kafka is rerun with the unchanged R28 inputs and remains at DAMAGE_REFERENCE_INPUT_MISSING after four tasks. Its exact serialized operand tree is retained in the per-operand damage ledger. Dynamic property values, formula/stage mapping, split and settlement semantics remain unbound. R28 JsonEnum values are reused only as provider-role evidence. No new damage binding is fabricated.

Sampo's executor retargets and checks dying state; its child callback builder and Tick are retained. Native projectile world/collision/impact ownership is missing, so no immediate no-op or child callback is synthesized. SetTeamFormation now has an exact config-held executor and application helper, but no authoritative formation component state. FORMATION_PROVIDER_MISSING remains. ByDistance reads scene positions and a virtual radius provider, uses float vector length and converts native numeric representation before comparison. IgnoreRadius zeroes radius only, not distance or position. Spatial units, providers and exact numeric conversion remain incomplete.

Monster AI retains the original 140-byte decoded body. New axis/action bodies reveal sequence access, modulo-based search, candidate checks, virtual provider calls and counters. The selected action helper at 0xED36EA0 cannot be called cursor advancement solely from its name/use. Stepper/skill conversion, availability, result ownership and reset are incomplete. AI rules executed: **0**. Monster chains 1002013→100201301, 1002014→100201401, 1002040→100204001 retain exact snapshots and blockers; completed actions **0**.

Camera unresolved **68**. No concrete new provider artifact appeared; no Camera search, no-op or invented finish was attempted. Source-provider asset joins gained: **0**. Frozen denominators are copied from R28 and independently kept separate (632 combat roots, 160 joined roots, 161 joined rows, stable 72 versus historical 73).

Seven unchanged baseline parents and three Monster actions were freshly replayed from their original states/commands with exact final hashes, JSON snapshots and clones. Changed reference scenarios regenerate public command receipts (old command prehashes are intentionally invalid after policy changes), then replay them exactly; each stage is saved. Original IR hashes remain unchanged. Gap ownership remains with the scheduler; no failure is converted into completion.

Fresh tests: battle_ir **586**, battle_sandbox **918**, R21 **21**, R27 **8**, R28 **7**, all exit **0** (total **1540**). The inherited **651** runtime cases, including R12-R26 focused cases and R22/R24/R25/R26 trace contracts, have identical tested input hashes and remain **revalidated prior PASS**, not fresh full runtime execution. No production runtime or admission behavior changed, so the conditional fresh full-runtime release gate was not triggered. This is an explicit limitation against the request to freshly run every regression lane. Commands, exit codes, counts, input manifests and source fingerprints are in final_tests.json. No unfinished test is reported PASS.

Investigation budget: 40/40 new method bodies, at most three dependency hops from selected factory/executor paths; five grouped subsystem paths. The one justified broad static operation was an exact selected config-type reference scan over the pinned code section to locate obfuscated factories. No archive recrawl, registry initializer research, game launch, attachment or process/memory modification occurred. Raw disassembly acquisition is distinguished from full semantic decoding. Failed tool experiments (invalid RVA, descriptor diagnostic formatting, stale replay prehash, gap serialization) were corrected; no failed attempt counts as execution success.

Recommended R30: recover scope-0 ownership and dynamic keyed setter callback contract, native numeric conversion and selector mask meanings, then implement the generic opt-in R19/R20 binding and rerun Lynx/Klara. Follow actual reached modifier blockers with exact instance construction inputs. Keep Beam/MCTS deferred.

Production files changed: **none**. New tools: r29_sources.cjs, r29_assessment.py, r29_finalize.py. New test modules: none; existing source/provider regressions rerun. Seven new controls, this report, and curated per-root/native/test receipts form the handoff. The archive manifest records exact members, sizes and per-member SHA-256; external verification records CRC and ZIP SHA-256 without a self-referential archive hash.
''',encoding='utf8')
    write('final_summary.json',dict(head=gate['head'],roots=matrix,counters=counters,verdict='EXECUTOR_EVIDENCE_ADVANCED_REFERENCE_PREFIXES_ONLY',production_files=[],git_writes='NONE',report=REPORT.relative_to(ROOT).as_posix()))
    paths=[*CONTROLS,REPORT,*[ROOT/'tools/runtime'/n for n in ['r29_sources.cjs','r29_assessment.py','r29_finalize.py']]]
    paths += [p for p in AUDIT.rglob('*') if p.is_file() and p.suffix in ['.json','.txt','.log'] and 'test_tmp' not in p.parts and p.name not in ['handoff_manifest.json','handoff_verification.json']]
    members={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(set(paths))}
    write('handoff_manifest.json',dict(change_request=CR,files=members,manifest_excludes_itself=True))
    paths.append(AUDIT/'handoff_manifest.json')
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(paths)):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={p.relative_to(ROOT).as_posix() for p in paths}
        import hashlib
        for n,m in members.items():assert len(z.read(n))==m['size'] and hashlib.sha256(z.read(n)).hexdigest()==m['sha256']
    write('handoff_verification.json',dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=len(paths),CRC='PASS',exact_member_set='PASS',member_sizes_sha256='PASS'))
    print(json.dumps(read(AUDIT/'handoff_verification.json')),flush=True)

if __name__=='__main__':main()
