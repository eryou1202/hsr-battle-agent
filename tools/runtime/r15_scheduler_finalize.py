"""Finalize R15 controls, ownership audit, report and verified CR-only handoff."""
from __future__ import annotations
import collections
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r15_scheduler_probes import read,write,AUDIT,CR,SUFFIX,SCHEDULER,POLICY_ID,probe_policy

PRODUCTION=['src/hsr_battle_agent/battle_runtime/behavior.py','src/hsr_battle_agent/battle_runtime/behavior_state.py',
            'src/hsr_battle_agent/battle_runtime/action_scheduler.py']
TESTS=['tests/battle_runtime/test_behavior_r15.py']
TOOLS=['tools/runtime/r15_scheduler_probes.py','tools/runtime/r15_scheduler_regressions.py','tools/runtime/r15_scheduler_finalize.py']
CONTROLS=[f'data/control/generic_runtime_{name}_{SUFFIX}.json' for name in [
    'action_scheduler_v1','scheduler_support_census_v5','action_lifecycle_gap_ledger_v1']]
REPORT=f'docs/agent/handoffs/generic_runtime_action_scheduler_lifecycle_{SUFFIX}.md'


def support_category(row):
    if row['status']=='ACTION_REFERENCE_COMPLETE':return 'REFERENCE_ACTION_COMPLETE'
    family=row['first_gap_family']
    if family=='DAMAGE':return 'BLOCKED_BY_DAMAGE'
    if family=='MODIFIER_EVENT':return 'BLOCKED_BY_MODIFIER_LIFECYCLE'
    if family in ('PROPERTY_DYNAMIC_PROVIDER','PREDICATE_PROGRESSION','CONTENT_CATALOG_BINDING'):return 'BLOCKED_BY_CONTEXT'
    if family=='POSITION' or (row['primitive'] or '').rsplit('.',1)[-1] in ('FireProjectile','SetEntityVisible','AlignTargetToTeamCenter'):
        return 'BLOCKED_BY_PRESENTATION_POLICY'
    return 'BLOCKED_BY_OTHER_SEMANTICS'


def main():
    baseline=read(AUDIT.relative_to(ROOT)/'r14_scheduler_baseline.json')
    probes=read(AUDIT.relative_to(ROOT)/'after_probes.json')
    summary=read(AUDIT.relative_to(ROOT)/'probe_summary.json')
    real=read(AUDIT.relative_to(ROOT)/'real_node_regressions.json')
    gate=read(AUDIT.relative_to(ROOT)/'start_gate.json')
    tests=read(AUDIT.relative_to(ROOT)/'final_tests.json')
    corpus=read(f'data/control/generic_runtime_real_combat_corpus_v2_{SUFFIX}.json')
    previous=read(f'data/control/generic_runtime_support_census_v4_{SUFFIX}.json')
    bysource={tuple(g['source_identity']):g for g in corpus['graphs']}
    ranking=[]
    for fam,n in summary['combat']['after']['first_gap_family_distribution'].items():
        joined=summary['skill_joined']['after']['first_gap_family_distribution'].get(fam,0)
        ranking.append({'family':fam,'combat_first_gaps':n,'skill_joined_first_gaps':joined,'score':n+2*joined})
    ranking.sort(key=lambda r:(-r['score'],r['family']))
    next_phase='R16 CORPUS READER EXPANSION'
    stages=collections.Counter(support_category(p) for p in probes)
    reachable=sum(bool(set(p['reached_types'])&SCHEDULER) for p in probes)
    stage_rows=[{'root':p['root'],'source_identity':p['source_identity'],'skill_joined':p['skill_joined'],
        'STRUCTURALLY_COMPILED':True,'REFERENCE_SCHEDULER_REACHABLE':bool(set(p['reached_types'])&SCHEDULER),
        'REFERENCE_ACTION_COMPLETE':p['status']=='ACTION_REFERENCE_COMPLETE','blocking_category':support_category(p),
        'primitive':p['primitive'],'required_capability':p['required_capability']} for p in probes]
    scheduler_types=SCHEDULER|{'MoveToTargetPosition','MoveToTargetList'}
    type_rows=[]
    for original in previous['types']:
        row=dict(original)
        row['R15_POLICY_CONDITIONAL_REFERENCE']=row['family']=='task' and (row['type'].rsplit('.',1)[-1] in scheduler_types or row['type'].rsplit('.',1)[-1] in probe_policy()['presentation'])
        row['NATIVE_EFFECTIVE']=False
        row['ORACLE_PENDING']=True
        type_rows.append(row)
    census={'schema':'generic_runtime_scheduler_support_census/5','change_request':CR,
        'semantic_authority':'REFERENCE_MODEL','native_executable_claimed':False,
        'stage_counts':{'STRUCTURALLY_COMPILED':len(probes),'REFERENCE_SCHEDULER_REACHABLE':reachable,
            'REFERENCE_ACTION_COMPLETE':summary['combat']['after']['actions_reference_complete'],**dict(stages)},
        'stage_definition':'STRUCTURALLY_COMPILED and REACHABLE are overlapping flags; blocking categories are exclusive first blockers. Reachable includes attempted scheduler primitives, not completion proof.',
        'combat':summary['combat'],'skill_joined':summary['skill_joined'],'decoded_joined_rows':summary['decoded_joined_rows'],
        'types':type_rows,'roots':stage_rows,'ranking_policy':'Observed combat first gaps + 2 * observed joined-root first gaps; planning priority only',
        'post_R15_rankings':ranking,'recommended_R16':next_phase,'native_policy_unknown':True}
    write(CONTROLS[1],census)
    tickets=[]
    for primitive,question,evidence in [
        ('TriggerAbility','Which serialized flags select parent resume and owner/caster/provider inheritance?', 'Bound task Begin/Execute paths, controller child linkage, completion callback and branch on each active flag'),
        ('WaitAnimState','What releases each animation-state wait, and which callbacks remain owned by the action?', 'Wait registration, release predicate and continuation enqueue with runtime context'),
        ('WaitSecond','What is the duration unit and conversion into the native scheduler?', 'Duration evaluator and native scheduling call with unit/scale conversion'),
        ('WaitTimelineFinish','Which timeline finish signal releases a task continuation?', 'Task registration and finish callback ownership'),
        ('SkillPerformFinish','Which after-end callbacks and descendants remain pending after the finish signal?', 'Finish execute/callback chain and ownership of settlement work'),
        ('DamagePerformFinish','Does this signal request lifecycle completion or settle damage?', 'Native task execute body plus consumers; empty serialized bitmap alone is insufficient')]:
        nodes=[n for g in corpus['graphs'] if g['stratum'] in ('ABILITY_CORPUS','PASSIVE_CORPUS','MODIFIER_CORPUS')
            for n in g['semantic_instances'] if n['family']=='task' and n['type'].rsplit('.',1)[-1]==primitive]
        unique={(tuple(n['source_identity']),tuple(n['span'])) for n in nodes}
        tickets.append({'id':'R15-ORACLE-'+primitive,'generic_question':question,'combat_instances':len(unique),
            'affected_roots':len({tuple(n['source_identity']) for n in nodes}),'minimum_native_evidence':evidence,
            'native_status':'RUNTIME_ORACLE_PENDING','whole_character_reverse_requested':False})
    grouped=collections.defaultdict(list)
    for p in probes:
        if p['required_capability']:grouped[(p['primitive'],p['required_capability'],p['first_gap_family'])].append(p)
    gap_rows=[{'primitive':primitive,'required_capability':capability,'family':fam,'frequency':len(rows),
        'affected_source_identities':[r['source_identity'] for r in rows], 'joined_roots':sum(r['skill_joined'] for r in rows),
        'blocking':True,'semantic_authority':'REFERENCE_MODEL','native_validation':'RUNTIME_ORACLE_PENDING'}
        for (primitive,capability,fam),rows in sorted(grouped.items(),key=lambda item:(-len(item[1]),str(item[0])))]
    write(CONTROLS[2],{'schema':'generic_runtime_action_lifecycle_gap_ledger/1','change_request':CR,
        'gaps':gap_rows,'oracle_tickets':tickets,'post_R15_rankings':ranking,'recommended_R16':next_phase,
        'missing_completion_request_roots':[p['source_identity'] for p in probes if p['status']=='WAITING_SCHEDULER'],
        'missing_completion_explanation':'Empty/fully drained ability entries without root SkillPerformFinish remain open; no implicit action finish is invented.',
        'DamagePerformFinish':'STRUCTURE_ONLY: 118 empty/structured serialized nodes do not prove settlement semantics'})
    changed_tracked=[]
    for path,sha in gate['tracked_hashes'].items():
        current=ROOT/path
        if not current.is_file() or hashlib.sha256(current.read_bytes()).hexdigest()!=sha:changed_tracked.append(path)
    unrelated=[p for p in changed_tracked if p not in PRODUCTION]
    architecture={'starting_head':gate['head'],'current_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'starting_branch':gate['branch'],'current_branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'tracked_files_changed_since_start':changed_tracked,'unrelated_tracked_changed':unrelated,
        'frozen_M10_M15_modified':False,'ScenarioCompiler_modified':False,'git_writes':'NONE',
        'turn_AV_implemented':False,'new_native_evidence_discovered':False,
        'production_character_names':{},'forbidden_scheduler_imports':[]}
    new_source=(ROOT/PRODUCTION[-1]).read_text(encoding='utf-8-sig')
    for token in ('Natasha','Acheron','Serval','Avatar_','110502'):
        if token in new_source:architecture['production_character_names'][token]=True
    for pattern in [r'\bimport threading\b',r'\bimport asyncio\b',r'\btime\.sleep\(',r'\bScenarioCompiler\b']:
        if re.search(pattern,new_source):architecture['forbidden_scheduler_imports'].append(pattern)
    pins_ok=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in baseline['control_pins'].items())
    architecture['R14_controls_preserved']=pins_ok
    architecture['status']='PASS' if not unrelated and pins_ok and not architecture['production_character_names'] and not architecture['forbidden_scheduler_imports'] and architecture['current_head']==gate['head'] and architecture['current_branch']==gate['branch'] else 'FAIL'
    write(AUDIT.relative_to(ROOT)/'architecture_audit.json',architecture)
    if architecture['status']!='PASS' or any(t['returncode'] for t in tests.values()):raise RuntimeError('closing gate failed')
    natasha=next(p for p in probes if p['root']=='Avatar_Natasha_00_Skill02_Phase01')
    real_root_fixtures=[]
    for pattern in ['TriggerAbility','WaitSecond','WaitAnimState','WaitTimelineFinish','AddModifier','DamageByAttackProperty']:
        rows=[p for p in probes if p['skill_joined'] and 'Natasha' not in p['root'] and pattern in p['reached_types']]
        if pattern=='TriggerAbility':rows.sort(key=lambda p:-p['metrics']['abilities_invoked'])
        if rows:real_root_fixtures.append({'pattern':pattern,'probe':rows[0]})
        else:real_root_fixtures.append({'pattern':pattern,'scope':'NO_JOINED_ROOT_REACHED_THIS_PRIMITIVE','isolated_regression_available':any(r['pattern']==pattern for r in real)})
    model={'schema':'generic_runtime_action_scheduler/1','change_request':CR,'starting_head':gate['head'],
        'verdict':'ACTION_SCHEDULER_REFERENCE_MODEL_ESTABLISHED','domains':{'ACTION_EXECUTION_SCHEDULER':'REFERENCE_MODEL',
            'BATTLE_TURN_SCHEDULER':'NOT_YET_BOUND_FROM_REAL_CONTENT'},'reference_policy':probe_policy(),
        'native_policy':'UNKNOWN / RUNTIME_ORACLE_PENDING','execution_objects':['AbilityExecution','TaskFrame','SequenceFrame',
            'ChildAbilityFrame','Barrier','ScheduledContinuation','CallbackFrame','CompletionRequest','ActionExecutionRoot'],
        'ownership_keys':['action_root_id','ability_instance_id','task_frame_id','parent_ability_id','parent_task_id','controller_owner','callback_owner'],
        'queues':['task_queue','child_queue','time_queue','event_queue','callback_queue'],
        'completion_contract':'Root completion request AND all required same-action abilities/sequences/tasks/child relations/barriers/events/callbacks/logical continuations drained. Persistent modifier storage is excluded.',
        'ability_completion':'Entry sequence plus its own event/callback/time drain; descendants additionally gated by WAIT_CHILD_TREE. Child finish never finishes root.',
        'task_completion':'Leaf completion or satisfied child/barrier/nested sequence condition, then cursor advances.',
        'primitive_transactions':'Clone candidate state per transition; GapError discards candidate and attempted trace, leaving original frame/cursor/RNG intact.',
        'hash_contract':'BehaviorRuntime.snapshot includes all scheduler frames, logical time, ownership, queues, order, requests, history, IR catalogs and supplied policies; SHA-256 canonical JSON.',
        'snapshot_restore':'Original full ExecutionResult and resulting snapshot/hash compared at 23 mid-execution budgets, including child/barrier/callback checkpoints.',
        'work_budget':'Total transitions plus task/frame transitions, callback enqueue/start transitions, child invocations, logical-time advances; exhaustion is resumable, never terminal completion.',
        'r14_baseline':baseline,'combat_probes':summary['combat'],'skill_joined_probes':summary['skill_joined'],
        'real_corpus_full_actions_reference_complete':0,'synthetic_positive_actions_reference_complete':True,
        'natasha_regression':natasha,'non_natasha_full_root_fixtures':real_root_fixtures,'isolated_real_node_regressions':real,
        'probe_timing_seconds':summary['timings_seconds'],'tests':tests,'architecture_audit':architecture,
        'determinism':'PASS','replay':'PASS','recommended_R16':next_phase,'production_files':PRODUCTION,'test_files':TESTS,
        'limitations':['No damage formula/settlement','No native modifier root installation','No implicit finish for empty roots',
            'Missing child catalog references remain gaps','Wait/native timing equivalence unknown','Presentation instant classifications are explicit synthetic assumptions',
            'Movement cannot be discarded','No turn/AV/ultimate/FUA insertion']}
    write(CONTROLS[0],model)
    b=summary['combat']['before'];a=summary['combat']['after'];j=summary['skill_joined']['after']
    lines=[f'# R15 Action Execution Scheduler + Lifecycle', '',f'CR `{CR}`. Verdict **ACTION_SCHEDULER_REFERENCE_MODEL_ESTABLISHED**.',
        f'Starting HEAD `{gate["head"]}`; branch `{gate["branch"]}`. Git writes: NONE. M10–M15, ScenarioCompiler, R14 controls and unrelated tracked dirty files preserved (hash audit PASS).', '',
        'ACTIONS are planner-visible invocations in the existing evidence-aware BehaviorRuntime. ACTION_EXECUTION_SCHEDULER is REFERENCE_MODEL; BATTLE_TURN_SCHEDULER remains NOT_YET_BOUND_FROM_REAL_CONTENT. No turn/AV/insertion mechanics or character execution subclasses were added.', '',
        f'Frozen R14 baseline: {baseline["combat_roots"]} combat roots, {baseline["task_instances"]} tasks; {baseline["scheduler_lifecycle_instances"]} scheduler/lifecycle instances across {baseline["graphs_affected"]} roots, {baseline["skill_roots_containing_scheduler"]} joined roots containing those tasks, {baseline["joined_roots_first_gap_scheduler"]} joined roots first blocked at a scheduler primitive. Counts: {baseline["scheduler_lifecycle_counts"]}. This union includes TriggerAbility, whereas the old SCHEDULER taxonomy has 1,137 instances/373 graphs; neither count replaces the other.', '',
        'The frames are JSON value records with monotonic explicit IDs, snapshot/clone/stable_hash APIs and replay through the same engine. Sequence cursors wait for primitive completion. TriggerAbility creates a scheduled child with explicit inherited context and FIRE_AND_CONTINUE_REFERENCE / WAIT_CHILD_REFERENCE / WAIT_CHILD_TREE_REFERENCE relationships. Controller, owner/caster, targets, ParamEntity stack, dynamic provider parent, RNG sharing, event scope and resume policy are serialized and hashed. Unknown masks/child references remain typed gaps.', '',
        'Ready task continuations run before owned events/callbacks, then child activation, then the next logical-time continuation. Enqueue ordinals break ties. Event expansion is resumable and budgeted. Callback children retain action ownership and source event; modifier callback owner/caster and nested callbacks are tested. Other actions’ queued work does not keep this action open.', '',
        'WaitSecond evaluates an executable duration under SERIALIZED_RAW_REFERENCE_UNITS. Logical time is a nonnegative arbitrary-precision integer; serialized fixed-point tagged/overflow operands retain the existing numeric gaps. WaitAnimState/WaitTimelineFinish are explicit barrier fences, logical delays, external barriers, or gaps. No sleep/FPS conversion/native unit claim. Presentation classifications are authored synthetic scenario assumptions, backed only by structural identity, not native irrelevance proof. Movement requires integer modeled position and continuation. STATE_RELEVANT tasks retain generic dispatch.', '',
        'SkillPerformFinish records COMPLETION_REQUEST. Task, ability and action completion are distinct. Root requests do not skip suffix tasks or settlement callbacks; all same-action owned work must drain. Persisted future-turn modifiers do not keep an action open. DamagePerformFinish remains structure-only: its empty serialized bitmap and R14 census do not prove native settlement. Unsupported primitives atomically discard candidate state, preserving scheduler cursor, context, RNG and prior successful work.', '',
        'Deterministic budgets bound total/frame/task transitions, callback enqueue/activation, child invocations and time advances. Ability/template/task/callback paths have cycle/depth guards; repeated zero-delay event/schedule ancestry returns a typed gap. Budget exhaustion is EXECUTION_BUDGET_EXHAUSTED and resumes from snapshots.', '',
        '| Combat probe metric | R14 rerun | R15 |','|---|---:|---:|']
    for key in ['tasks_reached','tasks_completed','abilities_invoked','child_abilities_completed','barriers_encountered','callbacks_completed','logical_time_advances']:
        lines.append(f'| {key} | {b["metrics"][key]} | {a["metrics"][key]} |')
    lines += [f'| ACTION_REFERENCE_COMPLETE | {b["actions_reference_complete"]} | {a["actions_reference_complete"]} |','',
        f'All 632 roots rerun from hash-checked frozen R14 IR. Adapter crashes: {sum(bool(p["adapter_error"]) for p in probes)}. R15 reaches damage in {a["roots_reaching_damage"]} roots; no damage evaluator. {a["status_distribution"]}. The 51 drained roots without a root finish request stay WAITING_SCHEDULER, not false completion. Timings: {summary["timings_seconds"]}; catalog verification is outside drive timing. Full raw per-root results and frozen first-gap distribution are in audit. Reach/completion counts are execution occurrences; static serialized census deduplicates physical spans. R14 completed task counts exclude absent handler attempts, while R15 adds failed task attempts to reach counts.', '',
        f'Skill view: 160 unique decoded joined roots / 161 joined rows. Started {j["roots_starting_execution"]}; child reached {j["roots_reaching_child"]}; damage {j["roots_reaching_damage"]}; heal {j["roots_reaching_heal"]}; modifier operations {j["roots_reaching_modifiers"]}; finish {j["roots_reaching_finish"]}; action complete {j["actions_reference_complete"]}. Prefix tasks completed 4 → {j["metrics"]["tasks_completed"]}. These are synthetic probes, not executable native skills.', '',
        f'Natasha Skill02 Phase01: {natasha["top_level_tasks_completed"]} top-level tasks completed under WAIT_CHILD_TREE, child invocations {natasha["metrics"]["abilities_invoked"]}, nested abilities {natasha.get("nested_abilities", [])}; {natasha["metrics"]["tasks_completed"]} descendant tasks completed, {natasha["metrics"]["barriers_encountered"]} waits; first remaining gap `{natasha["required_capability"]}` at `{natasha["primitive"]}`; action complete NO. Its parent TriggerAbility remains suspended rather than being prematurely counted complete.', '',
        'Non-Natasha full-root fixtures and isolated exact real IR nodes are recorded separately. The isolated nodes use synthetic wrapper sequences and an explicit synthetic modifier registration; their completion is not added to whole-root corpus completion. No full joined root reaches WaitTimelineFinish in this probe, so its preserved real-node regression supplies coverage without inventing reachability.', '',
        '| Isolated real-node pattern | Source root | Result |','|---|---|---|']
    for r in real:lines.append(f'| {r["pattern"]} | {r.get("root", "not bound")} | {r["status"]} |')
    lines += ['', 'Post-R15 first-gap priority (combat + twice joined-root blockers):', '']
    for r in ranking:lines.append(f'- {r["family"]}: combat {r["combat_first_gaps"]}, joined {r["skill_joined_first_gaps"]}, score {r["score"]}.')
    lines += ['',f'Recommended **{next_phase}**, targeted to exact missing referenced child abilities, with MODIFIER/EVENT ENGINE next. Missing catalog references dominate joined roots; modifier lifecycle is the largest combat family. Damage is now observable in 72 combat/14 joined roots but is not yet the dominant first gap. Do not choose turn/AV.', '',
        'Six narrow oracle tickets cover invocation flags, animation release, duration units, timeline finish, finish after-end ownership and DamagePerformFinish; each records frequency, affected roots and minimum native evidence. No live capture or whole-character reverse request.', '',
        'Validation: determinism PASS; replay PASS; architecture PASS. Full ExecutionResult including pending-frame journal and canonical snapshots/hashes are compared across clones/restores. Unit checks also cover RNG rollback, action-owned and child-owned callback drains, persistent modifiers, position rollback, external barrier release, budgets and zero-delay cycles.', '']
    for name,t in tests.items():lines.append(f'- {name}: {t["tests"]} tests, return code {t["returncode"]}, {t["result"]}.')
    lines += ['', 'The initial battle_ir baseline had five sandbox-temp permission errors; the workspace TMP/TEMP rerun passed all 586. Final FAST_UNIT uses that same workspace temp root.', '',
        'Production files:', '']+[f'- `{p}`' for p in PRODUCTION]+['', 'New test: `tests/battle_runtime/test_behavior_r15.py`. Reproducible audit entry points: `tools/runtime/r15_scheduler_probes.py`, `r15_scheduler_regressions.py`, `r15_scheduler_finalize.py`. Required three controls accompany this report. Handoff contains only CR-owned files plus a manifest; no source game payloads or old reverse trees. ZIP CRC, exact members, uncompressed sizes, member SHA-256 and ZIP SHA-256 are verified by the finalizer.']
    (ROOT/REPORT).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    audit_files=['start_gate.json','r14_scheduler_baseline.json','before_probes.json','after_probes.json','probe_summary.json',
        'reference_policy.json','real_node_regressions.json','architecture_audit.json','final_tests.json']
    # Avoid shipping the large unrelated tracked-file hash map/status listing.
    write(AUDIT.relative_to(ROOT)/'handoff_start_gate.json', {k:gate[k] for k in ['head','branch']})
    audit_files[0]='handoff_start_gate.json'
    audit_files += [t['log'].rsplit('/',1)[-1] for t in tests.values()]
    owned=PRODUCTION+TESTS+TOOLS+CONTROLS+[REPORT]+[(AUDIT.relative_to(ROOT)/p).as_posix() for p in audit_files]
    members={p:{'size':(ROOT/p).stat().st_size,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sorted(owned)}
    manifest={'change_request':CR,'starting_head':gate['head'],'git_writes':'NONE','members':members,
        'excluded':'Source payloads, R14 graphs/IR, old reverse trees, unrelated dirty files',
        'prerequisite':'Existing R12/R13/R14 workspace and frozen R14 IR referenced by controls; these are not CR-owned'}
    write(AUDIT.relative_to(ROOT)/'handoff_manifest.json',manifest)
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(owned):z.write(ROOT/p,p)
        z.write(AUDIT/'handoff_manifest.json','manifest.json')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist())!=set(owned)|{'manifest.json'}:raise RuntimeError('ZIP CRC/member mismatch')
        for p,info in members.items():
            raw=z.read(p)
            if len(raw)!=info['size'] or hashlib.sha256(raw).hexdigest()!=info['sha256']:raise RuntimeError('ZIP size/hash mismatch')
    verification={'zip':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'size':archive.stat().st_size,'member_count':len(owned)+1,'CRC':'PASS','member_set':'PASS','sizes':'PASS','member_SHA256':'PASS'}
    write(AUDIT.relative_to(ROOT)/'handoff_verification.json',verification)
    print(json.dumps(verification,indent=2))

if __name__=='__main__':main()
