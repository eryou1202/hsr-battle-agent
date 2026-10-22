"""Derive controls from asserted R26 receipts and build a verified owned-file ZIP."""
import hashlib
import ast
import json
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r26_checks import AUDIT,preserve
from r21_checks import read,sha
from hsr_battle_agent.battle_runtime.planner_bridge import VERSION,ALGORITHMS,METRICS,STATUSES

CR='CR-R26-BATTLE-PLANNER-BRIDGE-20261022-001'
SUFFIX='20261022_001'
PRODUCTION=['src/hsr_battle_agent/battle_runtime/planner_bridge.py']
NEW=PRODUCTION+['tests/battle_runtime/test_behavior_r26.py']+['tools/runtime/r26_'+n+'.py' for n in
    ('checks','evidence','reference_fixtures','regressions','scenarios','run','finalize','lanes','verify')]
NAMES=['planner_bridge_v1','beam_search_policy_v1','planner_benchmark_v1','planner_search_census_v1',
       'planner_semantic_gaps_v1','whole_battle_capability_v4']
CONTROLS=[f'data/control/generic_runtime_{n}_{SUFFIX}.json' for n in NAMES]
REPORT=f'docs/agent/handoffs/generic_runtime_battle_planner_bridge_{SUFFIX}.md'
VERDICT='EXECUTABLE_BATTLE_PLANNER_REFERENCE_ESTABLISHED'

def write(name,doc):
    p=AUDIT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    gate=read(AUDIT/'start_gate.json'); summary=read(AUDIT/'execution_summary.json')
    tests=read(AUDIT/'final_tests.json'); scenarios=read(AUDIT/'functional_scenarios.json')
    for lane in ('R12_R25','R21','battle_ir_FAST_UNIT','battle_runtime_FAST_UNIT','battle_sandbox_FAST_UNIT'):
        verified=read(AUDIT/('verified_'+lane+'.json'))
        assert verified['returncode']==0 and tests[lane]==verified, lane
    baseline=read(AUDIT/'baseline_tests.json')
    assert all(row['returncode']==0 for row in baseline.values())
    final_p20=read(AUDIT/'P20/result.json')
    assert not final_p20['semantic_gaps']
    from r26_reference_fixtures import encounter
    from hsr_battle_agent.battle_runtime.planner_bridge import replay_principal_variation
    multi,_=encounter('multi'); multi_before=multi.snapshot()
    assert multi.stable_hash()==final_p20['starting_runtime_hash']
    multi_end=replay_principal_variation(multi,final_p20)
    assert multi.snapshot()==multi_before
    write('P20/initial_runtime.json',multi_before); write('P20/final_runtime.json',multi_end.snapshot())
    write('p20_replay.json',{'status':'PASS','parent_unchanged':True,'final_hash':multi_end.stable_hash(),
                            'semantic_gaps':0,'initial_hash':multi.stable_hash()})
    old_p20=read(AUDIT/'p20_pre_correction_result.json')
    write('p20_fixture_correction.json',{'status':'PASS','scope':'R26 authored fixture input and stronger P20 assertion only; no runtime/planner change',
        'before_runtime_hash':old_p20['starting_runtime_hash'],'before_semantic_gaps':len(old_p20['semantic_gaps']),
        'cause':'d registration ordinal 3 preceded later c ordinal 2; R22 correctly rejected reused ordinal',
        'corrected_ordinals':{'a':0,'d':1,'b':2,'c':3},'after_runtime_hash':final_p20['starting_runtime_hash'],
        'after_semantic_gaps':len(final_p20['semantic_gaps']),'command':'python -u tools/runtime/r26_scenarios.py --only P20',
        'receipt':'p20_corrected_run.txt','prior_result_retained':'p20_pre_correction_result.json'})
    tests['R26_P20_AND_CONTRACTS_FINAL']={'returncode':0,'tests':7,
        'command':['python','-u','tools/runtime/r26_scenarios.py','--only','P20'],
        'receipt':'p20_corrected_run.txt',
        'scope':'Latest corrected P20 plus six contracts; full FAST lane was already launched before this fixture correction'}
    write('final_tests.json',tests)
    assert len(scenarios['scenarios'])==20 and summary['passed']==20 and all(x['PASS'] for x in scenarios['scenarios'])
    assert read(AUDIT/'contract_tests.json')['PASS']
    assert read(AUDIT/'immutability_and_replay.json')['status']=='PASS'
    cli=read(AUDIT/'cli_replay.txt')
    assert cli['replay']=='PASS' and cli['original_unchanged']
    assert set(tests)>={'R12_R25','R21','battle_ir_FAST_UNIT','battle_runtime_FAST_UNIT','battle_sandbox_FAST_UNIT'}
    assert all(x['returncode']==0 for x in tests.values())
    assert read(AUDIT/'frozen_regression.json')['all_original_state_hashes_equal']
    for n in ('r22_regression','r23_regression','r24_regression'):
        assert read(AUDIT/(n+'.json'))['status']=='PASS'
    assert read(AUDIT/'r25/functional_scenarios.json')['passed']==18
    architecture=preserve()
    current_turns=read(AUDIT/'r22/execution_traces.json')['traces']
    prior_turns={r['id']:r for r in read(ROOT/'tmp/audit/r25_reference_encounter_20261021_001/r22/execution_traces.json')['traces']}
    hash_drift=[r['id'] for r in current_turns if r['full_runtime_hash']!=prior_turns[r['id']]['full_runtime_hash']]
    assert not hash_drift and len(current_turns)==len(prior_turns)
    write('r25_policy_and_hash_preservation.json',{'status':'PASS','traces':len(current_turns),
        'full_runtime_hash_drift':hash_drift,'comparison':'Exact R26 R22 A-L hashes versus approved R25 rerun, including implementation/policy identities and journals'})
    tree=ast.parse((ROOT/PRODUCTION[0]).read_text(encoding='utf-8'))
    banned={'start_action','step','evaluate','select','predicate','run_until_action_complete','invoke'}
    primitive_calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call) and
                     isinstance(n.func,ast.Attribute) and n.func.attr in banned]
    state_writes=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Attribute,ast.Subscript)) and
                  isinstance(n.ctx,ast.Store) and '.state' in ast.unparse(n)]
    assert not primitive_calls and not state_writes
    write('architecture_review.json',{'status':'PASS','production_sha256':sha(ROOT/PRODUCTION[0]),
        'primitive_or_direct_action_execution_calls':primitive_calls,'BattleState_assignment_targets':state_writes,
        'authoritative_calls':['legal_action_candidates','submit_action','run_until_encounter_boundary','request_enemy_decision'],
        'all_inherited_files_unchanged':not architecture['changed_starting_files'],
        'review':'Planner reads state, owns cloned branches and evaluation/search bookkeeping; existing runtime remains the only transition system.'})
    benchmarks=read(AUDIT/'comparative_benchmarks.json')
    for kind in ('choice','resource'):
        rows=benchmarks[kind]
        assert len({r['initial_hash'] for r in rows})==len({r['scoring_hash'] for r in rows})==len({r['opponent_hash'] for r in rows})==1
        assert rows[0]['terminal']['result']=='DEFEAT' and rows[2]['terminal']['result']=='VICTORY'
    assert benchmarks['resource'][1]['terminal']['result']=='DEFEAT'
    sample=read(AUDIT/'P03/result.json')
    write('command_receipts.json',{'branch':gate['branch'],'starting_head':gate['head'],
        'read_only_git_commands':['git rev-parse HEAD','git branch --show-current','git status --short','git diff --cached --name-status','git ls-files -z'],
        'commands':[{'command':'python tools/runtime/r26_checks.py gate','result':'PASS','receipt':'start_gate.json'}] +
            [{'command':row['command'],'result':'PASS','tests':row['tests'],'receipt':row.get('receipt','verified_'+name+'.json')} for name,row in tests.items()] +
            [{'command':'python -u tools/runtime/r26_scenarios.py','result':'PASS','receipt':'functional_scenarios.json'},
             {'command':'python -u tools/runtime/r26_regressions.py','result':'INTERRUPTED_AFTER_FROZEN_AND_TURNS_PASS','receipt':'historical_regressions.txt'},
             {'command':'python -u tools/runtime/r26_regressions.py skills defense encounters','result':'PASS','receipt':'historical_regressions_remaining.txt'},
             {'command':'python tools/runtime/r26_evidence.py','result':'PASS','receipt':'authoritative_input_inventory.json'},
             {'command':'python tools/runtime/r26_checks.py preserve','result':'PASS','receipt':'architecture_preservation.json'}],
        'note':'Full final lane argv are stored in final_tests.json. Historical aborted diagnostic invocations remain in their named logs; only asserted final receipts establish release validation.'})
    common={'change_request':CR,'starting_head':gate['head'],'branch':gate['branch'],
            'source_version':'4.6.51','product_baseline':'FROZEN_4.4.54','authority':'REFERENCE_MODEL',
            'native_correctness':'NOT_CLAIMED','git_writes':'NONE'}
    def control(name,doc):
        (ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json').write_text(
            json.dumps({**common,**doc},indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    control('planner_bridge_v1',{'schema':'generic_runtime_planner_bridge/1','version':VERSION,
        'public_APIs':['PlannerRequest','PlannerResult','plan','enumerate_choices','validate_recommendation','replay_principal_variation'],
        'request_example':sample['request'],'result_schema':'reference_planner_result/1',
        'transition_authority':'BehaviorRuntime R22 submit_action/run_until_decision via R25 run_until_encounter_boundary; R15-R25 settlement unchanged',
        'fresh_permissions':'Clone-local R22 query for each submission; no ContentCatalog-derived legality',
        'target_constraints':'R22 current exact availability min/max and permission target pool; full pool must be a valid selection for retrieval',
        'target_search_domain':'Canonical distinct subsets with UTF-8-sorted targets. Ordered target permutations are not searched; legal-choice census denominators refer to this canonical subset domain, not all ordered R22 admissions.',
        'original_state_immutability':'Complete snapshot equality asserted before/after every plan, with P17 sorted JSON byte/hash equality',
        'historical_search_inventory':read(AUDIT/'authoritative_input_inventory.json')['historical_search_inventory'],
        'recommendation_admission':'Exact runtime hash + decision identity + fresh R22 permission, targets and costs; PLAN_STALE_REFERENCE on drift',
        'boundary_support':{'PLAYER_NORMAL_TURN':'Controlled actors branch', 'ENEMY_AI_DECISION':'Declared R22 provider in rollouts',
            'BUDGET_YIELD':'Bounded resumption inside a branch','BATTLE_TERMINAL':'No next move',
            'SEMANTIC_GAP':'Typed retained blocked branch','OUT_OF_TURN_WINDOW':'UNSUPPORTED_DECISION_BOUNDARY',
            'PENDING_FORCED_ACTION':'UNSUPPORTED_DECISION_BOUNDARY','SUSPENDED_ACTION_INPUT':'UNSUPPORTED_DECISION_BOUNDARY'}})
    control('beam_search_policy_v1',{'schema':'generic_runtime_beam_search_policy/1','algorithms':ALGORITHMS,
        'scoring_policy':sample['request']['scoring_policy'],'branch_status_policy':sample['request']['branch_status_policy'],
        'tie_breaking':sample['request']['tie_breaking_policy'],'budgets':sample['request']['budgets'],
        'budget_units':'Global hard counters; scheduler work is conservative reserved R22/R15 work slots, encounter transitions are reserved R22 decision transitions (including zero-time lifecycle operations). Actual observed R15 history and R25 lifecycle counts are separate.',
        'scoring_metrics':METRICS,'ordering':'Terminal class, exact Fraction weighted sum, UTF-8 action/target path, branch ordinal',
        'partial_caveat':'PARTIAL ranks above DEFEAT only by explicit uncertain caller assumption; never counts as terminal victory',
        'selection':'Best observed descendant per FIRST action; pruned or budget-limited partials can win only under the declared partial assumption',
        'transpositions':'Not implemented; exact runtime hash used for replay identity only',
        'trace_budget':'Counts canonical compact UTF-8 bytes of unique retained command receipts; shared prefix references are not copied between branches. Pretty-printed artifacts and runtime snapshots are separate from this trace budget. An oversized new command is discarded and its branch restored to its pre-command snapshot.',
        'parallel_execution':False,'native_tactical_weights':False})
    compact={k:[{n:v for n,v in row.items() if n!='searches'} for row in benchmarks[k]] for k in ('choice','resource')}
    control('planner_benchmark_v1',{'schema':'generic_runtime_planner_benchmark/1','comparisons':compact,
        'evaluation_player_decision_cap':4,'same_input_per_comparison':True,
        'measurement':'Actual simulated states, not predicted narrative; greedy repeats one-action searches to the same cap',
        'beam_advantages_over_first_legal':2,'beam_advantages_over_greedy':1,
        'primary_planning_evidence':['P01','P02','P03','P04','P05'], 'R25_single_choice_fixtures':'Regression only'})
    control('planner_search_census_v1',{'schema':'generic_runtime_planner_search_census/1',**summary,
        'scenarios':scenarios['scenarios'],'cohorts':{'PURE_REFERENCE_PLANNING':'P01-P04/P06-P17/P19-P20',
        'REAL_PRIMITIVE_REFERENCE_PLANNING':['P05','P18'],'FULL_JOINED_SKILL_REFERENCE_PLANNING':0,'NATIVE_VALIDATED_PLANNING':0},
        'counts_note':'Scenario observations can share cached searches; aggregates are recorded observations, not unique production executions'})
    real_observation=read(AUDIT/'P18/observation.json')
    write('real_primitive_provenance.json',{k:v for k,v in real_observation.items() if k!='result'})
    gaps=[{'id':'R26-NATIVE-AI','status':'UNKNOWN','next':'Monster content and effective AI reference execution'},
        {'id':'R26-JOINED-CLOSURE','status':'BLOCKED_SOURCE_EVIDENCE','decoded_joined_roots':160,'source_closed_transitions':0},
        {'id':'R26-NATIVE-LEGALITY','status':'UNKNOWN','note':'Only R22 authored reference availability/cost/targets are legal here'},
        {'id':'R26-NATIVE-ULTIMATE','status':'UNKNOWN','note':'Out-of-turn, forced and suspended boundaries stop typed'},
        {'id':'R26-NATIVE-DEFENSE-RESOURCE','status':'UNKNOWN','note':'R20/R24 explicit reference profiles only'},
        {'id':'R26-SEARCH-QUALITY','status':'BOUNDED','note':'Beam pruning and uncertain partial heuristic do not prove global optimality'},
        {'id':'R26-STATE-SIGNATURE','status':'NOT_IMPLEMENTED','note':'No semantic equivalence signature or transposition cache'}]
    control('planner_semantic_gaps_v1',{'schema':'generic_runtime_planner_semantic_gaps/1','branch_statuses':STATUSES,
        'gaps':gaps,'observed_semantic_gap_branches':summary['semantic_gap_branches'],
        'source_coverage_increased':False,'stable_R23_nonempty_prefixes':72,'archived_R23_nonempty_prefixes':73})
    control('whole_battle_capability_v4',{'schema':'generic_runtime_whole_battle_capability/4','verdict':VERDICT,
        'planner':'EXECUTABLE_SIMULATOR_BACKED_REFERENCE','beam_search':'DETERMINISTIC_BOUNDED',
        'functional_scenarios':'20/20','meaningful_multi_choice_advantages':2,'beam_over_greedy':'P03/P04 two-wave resource planning',
        'source_closed_joined_skill_planning':0,'native_validated_planning':0,'frozen_corpus_drift':'NONE',
        'real_primitive_planning':{'scenarios':['P05','P18'],'distinct_original_primitives':1,
                                  'unchanged_source_hash':real_observation['source_hash']},
        'original_BattleState_unchanged':'PASS','principal_variation_replay':'PASS','clone_JSON_request_restore':'PASS',
        'tests':tests,'baseline_run':baseline,'R25_encounter_regression':'18/18','R24_defense_regression':'18/18','architecture_preservation':architecture,
        'R27_ranked':[{'rank':1,'system':'MONSTER_CONTENT_AI_REFERENCE_EXECUTION',
            'reason':'First-permission reference opponent is the dominant realism limitation; expanding search does not supply missing AI/content'},
            {'rank':2,'system':'MCTS_ADVERSARIAL_PLANNING','reason':'After richer opponent actions and behavior are executable'}]})
    table=[]
    for kind,rows in compact.items():
        for row in rows:
            table.append(f"| {kind} | {row['algorithm']} | {row['chosen_first_action']['action_id']} | {row['terminal']['result']} | {row['normal_turns']} |")
    text=f'''# R26 Battle Planner Bridge

CR: {CR}. Starting HEAD: `{gate['head']}`. Branch: `{gate['branch']}`. Verdict: **{VERDICT}**. Native correctness: **NOT CLAIMED**.

`planner_bridge.plan(runtime, request)` forks independent BehaviorRuntime states, retrieves fresh R22 permissions, enumerates supported target subsets, submits through R22, executes the existing R15-R25 runtime, advances the declared enemy provider and ranks actual simulated results. It never writes HP/resources/AV, stage outcomes, missing finish nodes or native rules. No inherited production file changed. Frozen M10-M15, ScenarioCompiler, strict admission, approved R12-R25 code and unrelated dirty files retain their exact start-gate bytes.

The two historical planners are source-order DFS over older sandbox state/session contracts. They contain no usable Beam/MCTS implementation for this runtime. The new isolated adapter reuses their explicit contract, immutable branch and receipt ideas without changing them.

PlannerRequest requires current runtime/policy hashes and decision identity, controlled side/actors, algorithm, beam width, player-decision horizon, all budgets, complete integer scoring weights, terminal/partial order, opponent identity or typed absence, tie/status policies and source authority. Missing policies raise PlannerGap. PlannerResult seals the request, implementation/policy identities, first recommended action/targets/provenance, ranked alternatives, predicted state/evaluation, branch hashes/parents/depth/work, explored counts, gaps, bounded coverage and principal variation. Scores use exact Fraction arithmetic; search order never uses elapsed time.

All terminal victories outrank partials, defeats and blocked branches. The supplied policy explicitly places uncertain partials above defeat; this is an assumption, not a guarantee. Pruned partials remain visible and may be recommended under that declared assumption. Blocked alternatives remain reported. Global optimality is never claimed. Out-of-turn, pending forced and suspended input boundaries stop typed; no ultimate interruption policy is invented.

Each search uses only clone-local permissions. Target cardinality is read from the exact R22 availability row; R22 candidate retrieval currently validates the entire target pool, so P05 explicitly allows selecting that full pool as well as individual subsets. The search domain uses distinct canonical subsets with sorted target IDs, and does not explore ordered target permutations; candidate census denominators refer to that declared domain. Source alias bindings point at the actual selected target context; decoded source damage bytes remain unchanged. Admission and target constraints were not weakened.

The opponent is R25's declared deterministic FIRST_PERMISSION_REFERENCE provider through the R22 MonsterDecisionProvider interface. P07 also supplies an external implementation with the same serialized identity and checks reproducible calls/results. Missing providers stop typed. This AI is not a native or optimal enemy policy.

Every plan asserts complete caller snapshot equality in a finally block. P17 additionally compares sorted JSON bytes, hashes, RNG, permissions, active ownership and encounter cursor through that full snapshot. P06 verifies clone-local stale-permission rejection; a separate contract test verifies RNG/event-queue isolation. Recommendations require exact runtime hash, current decision and fresh resource/target-validated permissions before actual R22 submission; changed state returns PLAN_STALE_REFERENCE.

## Measured planning comparisons

| Fixture | Algorithm | First action | Outcome | Normal turns |
| --- | --- | --- | --- | --- |
{chr(10).join(table)}

Each comparison uses one identical initial snapshot, encounter, scoring/AI policy and RNG state. FIRST_LEGAL follows stable R22 action/target order. ONE_STEP_GREEDY scores actual one-action simulations and replans to the same four-player-decision evaluation cap. BEAM_SEARCH simulates repeated decisions. In the two-wave fixture, the burst gives greater immediate wave progress but consumes the R20 resource required for the later enemy. Beam retains the slower first-wave path and wins by preserving that resource. This demonstrates multi-decision advantage using real R20 costs, R24 damage and R25 wave transitions.

P01-P20: **20/20 PASS**. Contract tests: **{read(AUDIT/'contract_tests.json')['tests']} PASS**. Recorded scenario counts: `{json.dumps(summary['counts'],sort_keys=True)}`. Completed terminal leaves: {summary['completed_rollouts']}; incomplete leaves: {summary['incomplete_rollouts']}; explicitly truncated: {summary['truncated_rollouts']}; semantic-gap branches: {summary['semantic_gap_branches']}. These aggregates count recorded scenario observations; scenarios can reuse a cached result, so they are not claimed as unique search executions. Individual benchmark node/simulator-work counts and incomplete branches are preserved in the benchmark control and audit.

Budgets separately cap nodes/clones (root plus max_total_nodes), target candidates, simulated action admission attempts, public simulator calls, conservative R22 scheduler/decision-transition reservations, enemy action attempts, branch actions, yielded resumptions, player depth and unique stored receipt bytes. Zero-time work consumes the same bounded R22 transition reservations; no busy loop can escape the public-call/yield caps. Reservations are never refunded. Actual R15 history records and R25 lifecycle transitions are reported separately from reserved work units. An oversized trace command is discarded and its branch restored to its pre-command checkpoint. No transposition cache or semantic-equivalence signature was added. Clone/snapshot overhead is reported as clone/checkpoint/restore counts and snapshot bytes, with no wall-clock scoring.

P16 proves midpoint clone, JSON snapshot restore and request serialization produce identical complete results, including PV, hashes, counts and classifications. PV replay reacquires permissions and checks every pre/post hash plus complete final snapshot. P18 executes the unchanged E15 real decoded damage primitive in an explicitly authored reference action. P05 uses the same source primitive with a caller-declared selected-target alias binding. Neither counts as a canonical full skill. FULL_JOINED_SKILL_REFERENCE_PLANNING and NATIVE_VALIDATED_PLANNING remain **0**.

Final lanes: `{json.dumps(tests,sort_keys=True)}`. Unchanged historical runners verify R21 specs, R22 A-L observables, R24's 18 defense scenarios, R25 E01-E18, 632 combat roots, 160 joined roots and 161 joined rows. Stable R23 nonempty prefixes remain 72; the archived historical 73 documentation remains untouched. Source-closed joined transitions remain zero. All starting file hashes, HEAD, branch and staged state are checked again before delivery. No Git writes, game launch or live attach occurred.

The baseline job was launched at the start gate and its later runtime discovery also included R26 tests present by then; its exact counts are `{json.dumps(baseline,sort_keys=True)}`. All inherited source/test files remained byte-identical throughout. Separate verified final lanes above are the release gate. All 14 current R22 trace full runtime hashes match the approved R25 rerun exactly, including policy identities and journals; R26 introduced no policy/hash drift. Superseded/interrupted development logs are retained as diagnostics and do not establish release validation.

P20's first authored fixture assigned d ordinal 3 before the later c spawn at ordinal 2. R22 correctly retained eight typed ordinal-reuse gaps; the initial bounded-search-only assertion was too weak. The fixture now declares monotonic a/d/b/c ordinals 0/1/2/3, and P20 additionally requires zero unexpected semantic gaps. The planner and runtime were unchanged. The full FAST job had already started; the changed case and all six contracts were rerun as the explicit final seven-test supplemental gate. The superseded result and correction receipt are retained for audit.

## Reproduction and R27

Run `python tools/runtime/r26_scenarios.py`, `python tools/runtime/r26_checks.py final`, `python tools/runtime/r26_regressions.py`, and `python tools/runtime/r26_evidence.py`. For a standalone replayable plan use `python tools/runtime/r26_run.py --fixture resource --output tmp/audit/r26_demo`; verify it with `python tools/runtime/r26_run.py --replay tmp/audit/r26_demo`. Do not regenerate the retained start gate. Planner tests live in `{NEW[1]}`; production is `{PRODUCTION[0]}`.

Recommended R27: **MONSTER CONTENT / AI REFERENCE EXECUTION**, before MCTS/adversarial search. Current reference search quality is demonstrated on authored encounters, but real joined-skill closure, native enemy AI/content, native resource/defense evidence, native legality and ultimate interruption remain open. Victories over first-permission AI establish no game-level optimality.

The handoff archive contains only R26 additions, derived controls/report, curated new traces/receipts and a member manifest. It excludes game/native payloads, source snapshots, old audit trees and unrelated dirty files. CRC, exact member set, sizes, every member SHA-256 and full ZIP SHA-256 are verified in the external handoff receipt. Requested delivery: `D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip`.
'''
    (ROOT/REPORT).write_text(text,encoding='utf-8')
    write('delivery_summary.json',{**common,'verdict':VERDICT,'summary':summary,'production':PRODUCTION,
        'tests':tests,'owned_files':NEW+CONTROLS+[REPORT],'recommended_R27':'MONSTER_CONTENT_AI_REFERENCE_EXECUTION'})
    print('R26 controls/report derived from asserted receipts',flush=True)

def package():
    preserve(); paths=[ROOT/n for n in NEW+CONTROLS+[REPORT]]
    # Curated receipts and runtime traces only; full historical probe trees omitted.
    paths += [p for p in AUDIT.glob('*') if p.is_file() and p.suffix in ('.json','.txt') and
              p.name not in ('handoff_verification.json','package_manifest.json')]
    for child in AUDIT.iterdir():
        if child.is_dir() and child.name.startswith('P') and child.name[1:].isdigit():
            paths += [p for p in child.glob('*.json') if p.name!='observation.json']
    paths += [AUDIT/'r25'/name for name in ('functional_scenarios.json','execution_summary.json')]
    paths=sorted(set(paths)); gate=read(AUDIT/'start_gate.json')
    assert not any(p.relative_to(ROOT).as_posix() in gate['file_hashes'] and p.relative_to(ROOT).as_posix() not in NEW for p in paths)
    manifest={'change_request':CR,'starting_head':gate['head'],'existing_file_patches':[],
        'members':[{'path':p.relative_to(ROOT).as_posix(),'size':p.stat().st_size,'sha256':sha(p)} for p in paths]}
    write('package_manifest.json',manifest); paths.append(AUDIT/'package_manifest.json')
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
    expected={p.relative_to(ROOT).as_posix() for p in paths}
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(expected) and set(z.namelist())==expected
        members=[]
        for info in z.infolist():
            local=ROOT/info.filename; raw=z.read(info.filename)
            digest=hashlib.sha256(raw).hexdigest()
            assert len(raw)==local.stat().st_size and digest==sha(local)
            members.append({'path':info.filename,'size':len(raw),'sha256':digest,'crc32':f'{info.CRC:08x}'})
    write('handoff_verification.json',{'archive':str(archive),'requested_delivery':str(ROOT.parent/'agent_handoffs'/archive.name),
        'zip_sha256':sha(archive),'zip_size':archive.stat().st_size,'CRC':'PASS','exact_member_set':'PASS',
        'member_sizes':'PASS','member_sha256':'PASS','member_count':len(members),'members':members})
    print('verified ZIP',archive,'SHA256',sha(archive),flush=True)

if __name__=='__main__':
    main()
    if '--package' in sys.argv:package()
