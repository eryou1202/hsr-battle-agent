"""Curated R33 report and archive; immutable inherited files, no Git writes."""
from r33_authority import *
from r33_validation import preserve

def report():
    preserve()
    evidence=read(AUDIT/'evidence_inputs.json')
    drift=[n for n,h in evidence.items() if sha(ROOT/n)!=h]
    write('inherited_evidence_preservation.json',dict(checked_files=len(evidence),changed=drift))
    assert not drift
    r23=ROOT/'tmp/audit/r23_real_skill_root_closure_20261012_001/joined_dependency.json'
    old=read(r23);ranked=read(R27/'character/all_160_ranked.json')
    assert {tuple(r['source_identity']) for r in old['roots']}=={tuple(r['source_identity']) for r in ranked['roots']}
    write('inventory_join_verification.json',dict(R23_sha256=sha(r23),R27_sha256=sha(R27/'character/all_160_ranked.json'),exact_160_root_source_identity_set='PASS',finish_counts='R27 transitive known source nodes only, not completion reachability',unknown_external_providers='UNKNOWN_NOT_ZERO'))
    lifecycle={k:dict(status='UNKNOWN',effect='BLOCKS_SOURCE_EVIDENCED_ACTIVATION',ticket='R33-LISTENERS') for k in ['event registration identity meaning','event trigger','activation time','callback ordering','callback execution owner','duration/stack updates','repeated application','removal/expiration','listener cleanup','action completion barrier']}
    write('lifecycle_authority.json',dict(callback_bodies='Two exact original callbacks per recovered definition; structurally available, unchanged',semantics=lifecycle,dispatcher='Existing R17 only',scheduler='Existing R15 only'))
    provider_rows=[]
    for branch in ['b','false']:
        snap=read(AUDIT/'jade'/branch/'final_runtime.json')
        provider_rows.append(dict(branch=branch,key=-1022829777,reference_scope='supplied',reference_raw_value=snap['state']['dynamic_values']['supplied']['-1022829777'],authority='INHERITED_REFERENCE_MODEL_VALUE_ONLY',original_source_value='UNKNOWN',constructor_role='UNKNOWN',native_context_binding=False))
    write('provider_recovery.json',dict(rows=provider_rows,priority_checks=['R15 child and owner context retained, not native pointers','Exact AddModifier task mask/selector/name preserved','Two definition initialization graphs retained','R17 definitions alone do not create instances','Native context allocation/setters lack original input values'],conclusion='Existing reference numeric value cannot establish the original operand role, source value or native context'))
    tests=read(AUDIT/'tests/results.json');retry=read(AUDIT/'tests/runtime_retry.json');extra=read(AUDIT/'tests/R33.json');scenarios=read(AUDIT/'tests/scenarios.json');replay_checks=read(AUDIT/'tests/R29_R30_replays.json')
    preservation=read(AUDIT/'preservation.json');execution=read(ROOT/CONTROLS[2]);feasibility=read(ROOT/CONTROLS[4])
    final_inputs={p.relative_to(ROOT).as_posix():sha(p) for d in ['src','tests','tools/runtime','data/control','data/overlays'] for p in (ROOT/d).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.gz','.cjs')}
    write('final_source_hashes.json',final_inputs)
    tested=read(AUDIT/'tests/input_hashes.json');changed_runtime=[n for n,h in tested.items() if n.startswith('src/') and final_inputs.get(n)!=h]
    assert not changed_runtime
    write('final_tested_hash_check.json',dict(runtime_source_changed_since_tests=changed_runtime,runtime_changes=False,R33_test_sha256=sha(ROOT/'tests/battle_runtime/test_behavior_r33.py'),R33_test_hash_matches_receipt=sha(ROOT/'tests/battle_runtime/test_behavior_r33.py')==extra['test_sha256'],controls_match_receipt=all(sha(ROOT/n)==h for n,h in extra['control_hashes'].items()),broad_suite_includes_R12_R32=True,R33_separate_fresh_tests=True))
    text=f'''# R33 MODIFIER INSTANCE AUTHORITY COMPLETE

Verdict: **MODIFIER_INSTANCE_AUTHORITY_BLOCKED**. Starting HEAD `{preservation['head']}`, branch `{preservation['branch']}`. Frozen modified: NO. Production changes: none. Git writes: NONE. All starting files and staged state preserved, including unrelated dirty work. Beam/MCTS remain deferred.

The two exact R32 original Jade definitions remain decoded and bound to the original AddModifier hashes. Self span [10646629,10647060), BuffListen [10645392,10645683); both have two original callback bodies. R33 reused their original graphs, callback source records, task byte hashes and snapshots without reacquiring or re-decoding definitions. Original bitmap 522 and DynamicFloat mask512 key -1022829777 are retained. Its role/value and Self definition mask131072 role remain UNKNOWN.

The inherited reference `supplied` provider contains raw value 17179869184 for key -1022829777 on both saved paths. This is recorded in provider_recovery.json as a reference value only: its constructor role and original source value remain UNKNOWN. It is not silently treated as an original lifetime or stack value.

The real static creation call is now explicitly separated from registration. TryAddModifierInstance allocates at 0xF129430 and calls TurnBasedModifierInstance at 0xF12944E, with `(new, rsi, r15, r12, r14, rbx)`. Entry operand conservation is recorded. Base ctor at 0xEEA2780 receives `(this,arg2,arg3,[arg4+0x10],arg5,[arg6+0x18])`, stores two operands at +0x40/+0x70, allocates its own TaskContext at +0x38, and invokes context setters. The derived constructor stores arg4 at +0x148 and arg3 at +0x190, consumes arg6+0x28/+0x38/+0x74 and computed helper outputs. This proves a static provider call, **not executable original operand authority**.

One bounded source-selection helper read (0xB75A130) shows config+0x80 selecting task+0x20 virtual paths (+0x120/+0x110) or the passed object, followed by casting/helper dispatch. No mapping from those native objects to the saved reference scenario values is established. The R15 child `ability:26` under `ability:20` and caster `a` are preserved, but are not fabricated native TaskContext/ModifierContext inputs. Constructor identity, initial properties, duration/stack, activation, duplicate/refresh behavior, callback event triggers/order/owner, expiration/removal/cleanup and completion barrier remain typed provider gaps. No zero/null/empty/infinite/first-instance defaults were supplied.

Six same-build anchors were reused and hash verified; two additional exact bodies were read (source-selection helper and Base ctor), within 12 bodies and one new hop per blocker, within two allowed. Two modifier families only. The constructor workstream stopped when required source/context values remained unavailable. Registration at 0xF1297D5 -> 0xEDDA2A0 appends an existing pointer; it is not construction. OnActivate writes +0x94/+0x7c and invokes range/event setup; those observations do not establish Jade event meaning or lifecycle policy. No native adapter was installed and no reference construction assumptions were manufactured. No cross-character construction test was authorized by sufficient evidence; Herta/Fugue retain inherited exact source tasks without Jade assumptions.

Both original Jade public command sequences were replayed, independently repeated and compared with R32 snapshots. True predicate selects BPSkillSelf; false selects BPSkillBuffListen. Each task metric remains **8 -> 8**. True AddModifier executed: NO. False AddModifier executed: NO. Source-evidenced instances: 0. Reference-only instances: 0. Applied modifier state: empty; registered listeners/owned callbacks: none. Exact runtime gap remains REFERENCE_INSTANCE_INPUT_MISSING at the original task hash; deeper authority gap remains MODIFIER_INSTANCE_CONSTRUCTION_AUTHORITY_MISSING. Parent/child tasks remain pending, original parent finished: NO, R22 turn released: NO. No cursor was advanced or finish fabricated. R15 refusal atomicity, original IR hash preservation, clone/snapshot/hash and public replay passed.

The dependency cutset covers all known acquired Phase01 and Phase02 task positions and their nested ownership plus the exact transitive R27 reference inventory. It is **not a complete downstream dependency graph**. Original Phase02 /record/task_list/8 SetCameraRootFollow is the unconditional continuation after /7 branch unwind on both saved paths, before /9 ModifySPNew and /10 SkillPerformFinish. Its structural task exists but executable semantic authority is missing: **PROVEN_REQUIRED_BLOCKER**. It is not classified as ignorable presentation. Phase01 also references exact Camera and Camera_Self children; their bodies are unavailable in the acquired catalog. Literal TriggerAbility tasks at unconditional parent sequence /2 and /8 establish static obligations after Phase02; neither was reached, and native invocation flags remain unbound. Their unseen bodies/downstream graphs are not guessed. Other conditional modifier families remain outside the two-family investigation. The inherited synthetic presentation assumptions are listed explicitly and do not confer source-closed prefix authority. A successful AddModifier alone would not establish a complete Jade skill.

All 160 joined roots were compared using exact R23/R27 inventories. Roots with no original finish are excluded from first canonical combat-skill completion priority. Every inventoried root with an original finish still has unresolved dependency sites. Best alternative recovery candidate: **{feasibility['best_alternative']['root']}**, one missing Camera dependency, 53 observed reference tasks, two finish nodes present. Sampo Skill01 (40 tasks) and Xueyi Skill02 (39) are comparable one-gap candidates. Finish presence is not reachability; provider counts remain UNKNOWN, not zero, and no candidate is claimed completion ready. Jade has 23 historical unresolved sites plus the separately demonstrated instance and continuation cutsets; two exact R32 definition joins resolve content identity, not instance/lifecycle authority. Historical rankings are labeled R27 and are not new native validation.

Full joined skills: 0. Original Monster action completions: 0. Native-effective validations: 0. Source-evidenced construction/activation/task completion: 0. Reference construction: 0. Frozen drift: none; denominators 632 / 160 / 161. Historical 73 and stable 72 prefixes remain separate.

The 12 fresh R33 tests exercise exact joins, native argument provenance hashes, known-definition/missing-provider refusal, owner-context separation, unknown operands, original branch gaps, pending ownership, rollback on refused application, source/reference count separation, complete-known-cutset classification and deterministic replay. These are structural/refusal tests, not successful original AddModifier executions. Successful construction rollback, actual listener ownership/order, duplicate application and successful callback resumption remain BLOCKED and are not passed acceptance cases. The full battle_runtime suite covers R12-R32 focused modules; R21 specifications and R22 A-L traces run separately via scenario regressions.

Initial battle_runtime attempt exited 3221225477 without a unittest summary. The failure is retained in initial_attempt.json and its original log; the verbose faulthandler retry result is reported below without concealing that attempt. No runtime source bytes changed during validation. R33 was added after broad discovery and also has a separate fresh final test receipt.

```json
{json.dumps(dict(initial_lanes=tests,runtime_retry=retry,R33={k:v for k,v in extra.items() if k not in ('source_hashes','control_hashes')},R29_R30_replays=replay_checks,scenarios=scenarios),indent=2,ensure_ascii=False)}
```

Recommended R34: prioritize an exact original context provider for the located allocation/ctor call, with the explicit R33 source/lifetime/dynamic/listener/transaction tickets as acceptance gates. Treat Jade SetCameraRootFollow and exact missing Camera child providers as independent hard cutsets. If first skill completion is the priority, pursue Huohuo's exact Camera source provider and verify its remaining finish path before widening modifier archaeology. Do not bypass Camera, invent a constructor policy, or optimize Beam/MCTS.

Production files: none. Tests: tests/battle_runtime/test_behavior_r33.py. Tools: r33_sources.cjs, r33_authority.py, r33_validation.py, r33_deliver.py. Six R33 controls and curated audits accompany this report. Native static evidence is build 4.6.51, frozen product corpus remains 4.4.54. No live attach, game launch or memory/process patching occurred.
'''
    (ROOT/REPORT).write_text(text,encoding='utf8')

def package():
    owned=[ROOT/p for p in [*CONTROLS,REPORT,'tests/battle_runtime/test_behavior_r33.py',*[f'tools/runtime/r33_{n}' for n in ['sources.cjs','authority.py','validation.py','deliver.py']]]]
    # Keep exact branch snapshots/native receipts, compact regression summaries; exclude historical trees.
    owned += [p for p in AUDIT.rglob('*') if p.is_file() and p.suffix in ('.json','.txt','.log') and not any(x in p.parts for x in ('test_tmp','regressions','replays','__pycache__')) and p.name not in ('member_manifest.json','handoff_verification.json')]
    owned += [p for p in (AUDIT/'regressions').glob('*.json')]
    owned += [p for p in (AUDIT/'regressions/r22').glob('execution_summary.json')]
    members={p.relative_to(ROOT).as_posix():p.read_bytes() for p in owned}
    write('member_manifest.json',dict(change_request=CR,members={n:dict(size=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in sorted(members.items())}))
    members[(AUDIT/'member_manifest.json').relative_to(ROOT).as_posix()]=(AUDIT/'member_manifest.json').read_bytes()
    dest=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(members.items()):z.writestr(n,b)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None and set(z.namelist())==set(members)
        assert all(z.read(n)==b and z.getinfo(n).file_size==len(b) for n,b in members.items())
        receipts={n:dict(size=z.getinfo(n).file_size,crc32=f'{z.getinfo(n).CRC:08x}',sha256=hashlib.sha256(z.read(n)).hexdigest()) for n in z.namelist()}
    write('handoff_verification.json',dict(archive=str(dest),sha256=sha(dest),size=dest.stat().st_size,CRC='PASS',member_set='PASS',sizes_SHA256='PASS',member_count=len(members),members=receipts))
    print(dest);print(sha(dest))

if __name__=='__main__':globals()[sys.argv[1]]()
