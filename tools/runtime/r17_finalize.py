"""R17 controls, gap ranking, architecture/preservation audit and verified handoff."""
from __future__ import annotations
import ast
import collections
import difflib
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from r17_checks import ROOT,AUDIT,PRODUCTION,read,write,sha,preservation

CR='CR-R17-MODIFIER-EVENT-ENGINE-20261009-001'
SUFFIX='20261009_001'
TESTS=['tests/battle_runtime/test_behavior_r17.py']
TOOLS=['tools/runtime/r17_checks.py','tools/runtime/r17_reference_fixtures.py','tools/runtime/r17_probes.py',
       'tools/runtime/r17_regressions.py','tools/runtime/r17_finalize.py']
CONTROL_NAMES=['modifier_event_engine_v1','modifier_lifecycle_census_v1','support_census_v7','semantic_gap_ledger_v5']
CONTROLS=[f'data/control/generic_runtime_{name}_{SUFFIX}.json' for name in CONTROL_NAMES]
REPORT=f'docs/agent/handoffs/generic_runtime_modifier_event_engine_{SUFFIX}.md'
DEST=Path('D:/HSR_Battle_Agent/agent_handoffs')/(CR+'_changed_files.zip')

def emit(path,value):
    target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def counts(rows,key='metrics'):
    result=collections.Counter()
    for row in rows:result.update(row.get(key,{}))
    return dict(result)

def audit():
    preservation()
    starting=read(AUDIT/'start_gate.json')
    # Recover the two-line R17 edit's exact approved predecessor, checked by SHA.
    path='src/hsr_battle_agent/battle_runtime/behavior.py'
    previous=(ROOT/path).read_bytes().replace(b'    from .modifier_lifecycle import install as install_modifier_reference\r\n    install_modifier_reference(registry)\r\n',b'')
    if hashlib.sha256(previous).hexdigest()!=starting['file_hashes'][path]:
        previous=(ROOT/path).read_bytes().replace(b'    from .modifier_lifecycle import install as install_modifier_reference\n    install_modifier_reference(registry)\n',b'')
    if hashlib.sha256(previous).hexdigest()!=starting['file_hashes'][path]:raise ValueError('R17 behavior predecessor differs')
    target=AUDIT/'starting_files'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(previous)
    findings=[]
    for path in PRODUCTION:
        source=(ROOT/path).read_text(encoding='utf-8')
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,(ast.If,ast.IfExp,ast.Compare)):
                segment=ast.get_source_segment(source,node.test if isinstance(node,(ast.If,ast.IfExp)) else node) or ''
                if re.search(r'AvatarID|SkillID|Natasha|MAvatar_|110502|Skill02',segment):
                    findings.append({'file':path,'line':node.lineno,'branch':segment})
        before=AUDIT/'starting_files'/path
        old=before.read_text(encoding='utf-8').splitlines(keepends=True) if before.exists() else []
        diff=''.join(difflib.unified_diff(old,source.splitlines(keepends=True),fromfile='approved_before/'+path,tofile='R17/'+path))
        out=AUDIT/'diffs'/(Path(path).name+'.diff');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(diff,encoding='utf-8')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip()
    if head!=starting['head'] or branch!=starting['branch']:raise ValueError('Git identity changed')
    scheduler=(ROOT/'src/hsr_battle_agent/battle_runtime/action_scheduler.py').read_text()
    engine=(ROOT/'src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py').read_text()
    receipt={'status':'PASS' if not findings else 'FAIL','forbidden_dispatch_branches':findings,
        'event_processing':'R15 _owned_event / CallbackFrame / _sequence / ActionExecutionRoot',
        'separate_event_executor':False,'definition_instance_listener_store':'BehaviorBattleState',
        'per_character_handlers':False,'damage_formula_added':False,'native_numeric_policies_interpreted':False,
        'frozen_modules_and_tests':'SHA256_PRESERVED','strict_M15_and_ScenarioCompiler':'SHA256_PRESERVED',
        'git_writes':'NONE','starting_head':starting['head'],'ending_head':head,'branch':branch,
        'source_checks':{'shared_owned_event_function':'def _owned_event(' in scheduler,
                         'no_runtime_drive_in_modifier_module':'def drive(' not in engine}}
    write('architecture.json',receipt)
    if findings:raise ValueError('forbidden production dispatch')
    return receipt

def main():
    arch=audit();start=read(AUDIT/'start_gate.json');summary=read(AUDIT/'probe_summary.json')
    frozen=read(AUDIT/'after_probes.json');index=read(AUDIT/'modifier_definition_index.json')
    explicit=read(AUDIT/'explicit_joined_application_probes.json');inputs=read(AUDIT/'joined_addmodifier_first_gap_analysis.json')
    diversity=read(AUDIT/'real_modifier_regressions.json');regression=read(AUDIT/'regression_summary.json')
    events=[e for row in inputs for e in row.get('listener_event_probes',[])]
    providers=[r for r in frozen if r['skill_joined'] and r['primitive']=='RPG.GameCore.SetDynamicValue' and r['gap_node']['node_id']=='/record/task_list/0']
    write('joined_dynamic_provider_gaps.json',[{'root':r['root'],'source_identity':r['source_identity'],
        'classification':'DYNAMIC_PROVIDER_MISSING','reader_missing_implied':False,
        'required_capability':r['required_capability'],'native_effective_provider':'UNKNOWN'} for r in providers])
    assert len(providers)==3
    tests=read(AUDIT/'final_tests.json')
    if any(v['returncode'] for v in tests.values()):raise ValueError('tests failed')
    groups={'UNCHANGED_FROZEN_FIXTURE':{'combat_roots':632,'joined_roots':160,'joined_rows':161,
        'before':summary['combat']['before'],'after':summary['combat']['after'],
        'joined_before':summary['joined']['before'],'joined_after':summary['joined']['after']},
        'EXPLICIT_MODIFIER_REFERENCE_FIXTURE':{
            'joined_isolated_applications':{'denominator':len(explicit),'metrics':counts(explicit),
                'status_distribution':dict(collections.Counter(r['status'] for r in explicit))},
            'joined_listener_events':{'denominator':len(events),'metrics':counts(events),
                'status_distribution':dict(collections.Counter(r['status'] for r in events)),
                'first_gap_distribution':dict(collections.Counter(r['gap'] for r in events if r['gap']))},
            'diverse_real_modifiers':regression,
            'full_joined_roots_with_only_first_application_bound':{'denominator':len(explicit),
                'status_distribution':dict(collections.Counter(r.get('explicit_full_root_status') for r in inputs if r.get('explicit_full_root_status'))),
                'whole_skill_reference_completions':0,
                'waiting_explanation':'38 ability bodies complete without an explicit completion request; no SkillPerformFinish is fabricated'}},
        'NEW_EXPANDED_CORPUS':{'denominator':summary['expanded']['roots'],'origin':'R16 expanded-only recheck; R17 newly decoded=0',
                              'summary':summary['expanded']}}
    family=summary['combat']['after']['first_gap_family_distribution'];joined=summary['joined']['after']['first_gap_family_distribution']
    ranking=[]
    for name in ['CONTENT_CATALOG_BINDING','DAMAGE','RESOURCE','PROPERTY_DYNAMIC_PROVIDER','PREDICATE_PROGRESSION','MODIFIER_EVENT','SCHEDULER','OTHER']:
        old={'SCHEDULER':'ACTION_EXECUTION_SCHEDULER'}.get(name,name)
        a=family.get(old,0);b=joined.get(old,0)
        if name=='OTHER':
            a=sum(v for k,v in family.items() if k not in ['CONTENT_CATALOG_BINDING','DAMAGE','RESOURCE','PROPERTY_DYNAMIC_PROVIDER','PREDICATE_PROGRESSION','MODIFIER_EVENT','ACTION_EXECUTION_SCHEDULER'])
            b=sum(v for k,v in joined.items() if k not in ['CONTENT_CATALOG_BINDING','DAMAGE','RESOURCE','PROPERTY_DYNAMIC_PROVIDER','PREDICATE_PROGRESSION','MODIFIER_EVENT','ACTION_EXECUTION_SCHEDULER'])
        ranking.append({'family':name,'combat':a,'joined':b,'combat_plus_twice_joined':a+2*b,
            'dominant_blocker_dimension':('MISSING_CONTENT_OR_RUNTIME_CATALOG_CONTEXT' if name=='CONTENT_CATALOG_BINDING' else
                'MISSING_REFERENCE_POLICY_OR_INSTANCE_INPUT' if name=='MODIFIER_EVENT' else 'MISSING_RUNTIME_PRIMITIVE_OR_EFFECTIVE_INPUT')})
    ranking.sort(key=lambda r:-r['combat_plus_twice_joined'])
    recommended={'family':'DAMAGE / HP SETTLEMENT','reason':'Largest remaining unimplemented combat primitive family (74 combat, 15 joined); Modifier/Event now has an explicit reusable reference engine. Catalog remains the largest raw blocker and needs a separate targeted source/reader backlog.',
        'native_oracle_track':'INDEPENDENT','turn_AV_engine':'OUT_OF_SCOPE','planning_authority':'AUTHORED_REFERENCE_PHASE_SELECTION'}
    common={'schema':'generic_runtime_r17_control/1','change_request':CR,'starting_head':start['head'],
        'branch':start['branch'],'semantic_authority':'REFERENCE_MODEL','native_correct':False,'git_writes':'NONE'}
    lifecycle={**common,'definitions':{'exact_unique_decoded':len(index),'bound_definition_pipeline':len(index),
        'directory':summary['directory_definitions'],'inline':summary['inline_definitions'],
        'reader_envelopes_excluded':143,'R16_new_directory_graphs_inherited':94,
        'deduplication':'exact source SHA256 + source span + graph hash','R17_new_decoded_graphs':0,
        'index':'tmp/audit/r17_modifier_event_20261009_001/modifier_definition_index.json'},
        'groups':groups,'joined_AddModifier_analysis':summary['joined_first_input'],
        'joined_SetDynamicValue_first_inputs':len(providers),'baseline_drift':[],
        'source_pins':'tmp/audit/r17_modifier_event_20261009_001/source_pins.json',
        'metrics_semantics':{'modifier_applications':'per resolved target, committed transitions; failed primitive attempts remain gap records',
            'frozen_modifier_task_attempts':sum(r['primitive_occurrences'].get('AddModifier',0) for r in frozen),
            'frozen_instances_created_refreshed_removed':0,'frozen_listeners_registered':0,
            'explicit_actions':'isolated wrappers and independently invoked opaque event probes, never complete native skills'}}
    engine={**common,'verdict':'GENERIC_MODIFIER_EVENT_REFERENCE_ENGINE_ESTABLISHED',
        'application_policies':['INSERT_NEW_REFERENCE','REFRESH_EXISTING_REFERENCE','REPLACE_EXISTING_REFERENCE','INCREMENT_STACK_REFERENCE','REJECT_DUPLICATE_REFERENCE'],
        'native_numeric_application_policy':'NATIVE_POLICY_UNKNOWN',
        'pipeline':['exact definition binding','explicit target/owner/caster/source/provider operands','explicit identity matching and application policy',
            'construct/refresh/replace/stack','explicit activation','deterministic listener registration','R15 action-owned callback enqueue/drain'],
        'evidence_boundaries':['DECODED_MODIFIER_DEFINITION','REFERENCE_INSTANCE_CONSTRUCTED','REFERENCE_INSTANCE_ACTIVE',
            'REFERENCE_LISTENERS_REGISTERED','REFERENCE_CALLBACK_EXECUTED'],
        'event_authority':['EVENT_ID_STRUCTURALLY_DECODED','LISTENER_REFERENCE_CONFIGURED','REFERENCE_CALLBACK_EXECUTABLE',
            'NATIVE_EVENT_MEANING_UNKNOWN','NATIVE_EFFECTIVE_LISTENER_UNKNOWN'],
        'state_fields':['definition_id','instance_id','config_identity','owner','caster','original_caster','source_ability','target','stack','count',
            'duration','created_at','activated_at','activation_state','dynamic_values','snapshot_data','event_registrations','provider_binding',
            'property_contributions','reference_policy','pending_lifecycle_callbacks','refresh_count','replacement_of','removal_reason','removed_at'],
        'event_processing':arch['event_processing'],'callback_context':'owner/caster/original caster/event source/target/ParamEntity/ability context/provider parent/event payload/shared RNG/action root',
        'listener_order':'priority, instance identity, registration identity; serialized reference policy',
        'lifetime':'explicit reference advance/event/manual; no native AV or turn step',
        'removal':'instance/config-target/target-filter; deregistration + reversible contributions + tombstone + explicit pending callback policy',
        'retained_callbacks':'live reads while active; explicit dispatch snapshot after removal',
        'property_aggregation':'explicit ADDITIVE_REVERSIBLE_REFERENCE; native aggregation unknown',
        'transactions':'R15 state candidate per transition; unsupported primitive rolls back, earlier committed work and suspended continuation retained',
        'recursion':'R15 task/callback/ability depths, repeated callback-path hash and WorkBudget',
        'persistence':'installed modifiers do not keep source action open; currently triggered callbacks do until drained',
        'heal_extensions':'explicit pre_heal/effective_amount/settlement/hp_mutation/post_heal order + owned callback drain',
        'damage_extensions':'explicit before_damage/amount_modification/property_mutation/after_damage points; complete formula absent',
        'serialization':'all definition/instance/listener/policy/provider/lifetime/contribution/callback identities in state/runtime snapshots and hashes',
        'determinism':'PASS','replay':'PASS','tests':tests,'architecture':arch,'recommended_R18':recommended,
        'production_files':PRODUCTION,'test_files':TESTS,'stop_boundary':'next work requires missing predicates/providers/resources/damage primitives, exact missing sources/readers, initialized actors or independent native oracle; no turn/AV invention'}
    support={**common,'baseline_denominators':{'combat_roots':632,'joined_roots':160,'joined_rows':161},'groups':groups,
        'observed_ranking':ranking,'reference_vs_native':'reference engine established; no frozen fixture inputs fabricated and no native actor admitted',
        'recommended_R18':recommended,'full_native_skill_completions':0}
    ledger={**common,'blocker_taxonomy':['CONTENT_GRAPH_MISSING','REFERENCE_INSTANCE_INPUT_MISSING','MODIFIER_TARGET_BINDING_MISSING',
        'MODIFIER_LIFECYCLE_POLICY_MISSING','EVENT_REGISTRATION_UNKNOWN','CALLBACK_CONTEXT_MISSING','DYNAMIC_PROVIDER_MISSING','NATIVE_EFFECTIVE_STATE_UNKNOWN'],
        'first_input_analysis':inputs,'native_effective_unknown_roots':41,'genuinely_unblocked_frozen_roots':0,
        'missing_config_root':'Avatar_Aventurine_00_PassiveSkill01','dynamic_provider_inputs':providers,
        'ranking':ranking,'dimensions':['MISSING_CONTENT','MISSING_REFERENCE_POLICY','MISSING_RUNTIME_PRIMITIVE','MISSING_NATIVE_ORACLE'],
        'listener_probe_gaps':groups['EXPLICIT_MODIFIER_REFERENCE_FIXTURE']['joined_listener_events']['first_gap_distribution'],
        'recommended_R18':recommended,'native_oracle_policy':'independent validation; decoding, activation and deterministic replay never prove native effect'}
    for path,value in zip(CONTROLS,[engine,lifecycle,support,ledger]):emit(path,value)
    application_metrics=counts(explicit);event_metrics=counts(events)
    callback_total=event_metrics.get('modifier_callbacks_completed',0)+regression['metrics'].get('modifier_callbacks_completed',0)
    explicit_action_total=sum(r['status']=='ACTION_REFERENCE_COMPLETE' for r in explicit)+sum(e['status']=='ACTION_REFERENCE_COMPLETE' for e in events)+regression['action_reference_completions']
    write('final_summary.json',{'definitions':len(index),'bound':len(index),'joined_first_input':summary['joined_first_input'],
        'application_metrics':application_metrics,'event_metrics':event_metrics,'regression_metrics':regression['metrics'],
        'explicit_action_completions':explicit_action_total,'explicit_modifier_callbacks_completed':callback_total,
        'tests':tests,'verdict':engine['verdict'],'recommended_R18':recommended,'top_remaining_raw_blocker':ranking[0]})
    natasha=read(AUDIT/'natasha_regression.json')
    test_text=', '.join(f"{k}: {v['tests']} PASS" for k,v in tests.items())
    report=f'''# R17 Generic Modifier + Event Reference Engine

CR `{CR}`. Verdict **GENERIC_MODIFIER_EVENT_REFERENCE_ENGINE_ESTABLISHED**.
Starting HEAD `{start['head']}`, branch `{start['branch']}`. Git writes NONE. Frozen M10–M15, ScenarioCompiler, strict M15 admission, previous R12–R16 artifacts/tests and unrelated dirty files are SHA-256 preserved. The five R17 production edits extend the same BehaviorRuntime/state and R15 scheduler.

The exact unique modifier definition census is **296**, with **153 directory definitions and 143 inline bodies**. A preliminary 439 typed graph-node count included 143 reader envelopes; those are excluded from the final definition count. The 94 R16 newly decoded directory graphs are inherited, never added to the corpus count a second time. R17 decodes zero new structural roots. Definitions retain source version, pinned artifact/hash, exact span, graph hash, config identity, native reader references, compiled callback tasks, decoded fields and unknown fields. All 296 are exercised by state binding/clone tests. Binding creates no active instance.

The reference AddModifier pipeline resolves an exact source-backed definition and explicit operands, then applies insert, refresh, replace, increment-stack or reject-duplicate policy. Numeric native policies remain raw data. Match identities explicitly preserve owner, caster, original caster, source ability and target; cross-source updates require a preservation policy. Activation and refresh callbacks need explicit policies. Dynamic initialization uses the caller-selected source provider; callbacks use explicit modifier-local/snapshot/source precedence. Refresh provider preservation/rebinding is explicit. Selected property snapshots and reversible additive reference contributions persist in instance state. This aggregation model claims no native equivalence.

Listener IDs, priority, owner/caster/source context, predicates, callback targets and exact compiled callback IR are serialized in each instance. Numeric callback flags remain opaque explicit reference data and are never mistaken for predicates. Dispatch constructs context-rich wrappers and uses the existing R15 event queue, CallbackFrame, task sequences, budgets and ActionExecutionRoot. Nested callbacks retain current action ownership. Logical expiry and opaque event expiry are explicit reference policies; real battle turn/AV mechanics are absent. Removal updates the active store, listeners, reversible contributions and tombstones; pending callbacks explicitly retain dispatch snapshots or cancel work that has not started. Running continuations remain resumable.

Every R15 transition executes on a cloned candidate state. A SemanticGap discards that primitive's state/RNG/listener/stack changes and keeps the earlier committed continuation. Retrying a suspended unsupported callback neither loses it nor repeats committed tasks or RNG draws. Callback-depth, task-depth, repeated-path cycle and WorkBudget guards remain in R15. Installed future-lifetime modifiers do not hold their originating action open; callbacks currently owned by that action do until drained. Definitions, instances, dynamic/snapshot stores, listeners, contribution records, pending callback IDs and reference policy identities all participate in clone/snapshot/restore/hash/replay.

Explicit heal stages can dispatch and drain callbacks in caller-declared pre-heal, effective amount, settlement, HP mutation and post-heal order. Damage has generic explicitly configured event points only. Native event IDs/order and complete damage formulas remain unresolved.

| Unchanged frozen fixture | R16 | R17 |
|---|---:|---:|
| Combat roots | 632 | 632 |
| Joined decoded skill roots / rows | 160 / 161 | 160 / 161 |
| Combat Modifier/Event first gaps | 181 | 181 |
| Joined Modifier/Event first gaps | 43 | 43 |
| Combat tasks reached | 1025 | 1025 |
| Combat tasks completed | 494 | 494 |
| Child abilities invoked / completed | 44 / 0 | 44 / 0 |
| Whole action reference completions | 0 | 0 |
| Joined task_list/0 AddModifier inputs | 41 | 41 |
| Joined task_list/0 dynamic provider inputs | 3 | 3 |

No modifier application input is fabricated in the frozen fixture. Exact first-gap and metric drift is empty. Frozen clone/restore checkpoints pass. The inherited R16 expanded-only 149 roots are rechecked separately under `NEW_EXPANDED_CORPUS`; they are never counted in the 632/160 denominators.

Each of the 41 joined AddModifier input roots has a detailed source/target/owner/caster/provider/policy/listener row. **40** have an exact definition and complete application/activation/registration in an independently labelled explicit sandbox fixture. **1** (`Avatar_Aventurine_00_PassiveSkill01`) lacks the exact config in current decoded files. **0** frozen roots are genuinely unblocked and all **41** remain native-effective unknown. Giving only the first application policy to their original full roots produces **38 WAITING_SCHEDULER** outcomes (ability bodies complete without a serialized finish request), **2 SemanticGaps**, and no whole-skill completion. No finish node is inserted in those full roots.

Separate explicit categories and denominators:

- 40 isolated real AddModifier wrappers: {dict(collections.Counter(r['status'] for r in explicit))}; committed target applications {application_metrics.get('modifier_applications_completed',0)}, instances created {application_metrics.get('modifier_instances_created',0)}, listeners {application_metrics.get('listeners_registered',0)}.
- 52 independently triggered listener event probes: {dict(collections.Counter(e['status'] for e in events))}; modifier callbacks completed {event_metrics.get('modifier_callbacks_completed',0)}. The leading callback gaps are wave/maze predicates (29 probes), other predicate/progression/context operands, further AddModifier inputs, resource operations and retargeting. These are runtime/input gaps, not automatically missing readers.
- Four diverse real source-backed configuration/application fixtures: three initial complete lifecycles and one explicit scheduler/context gap. Their subsequent reference refresh/stack/replace/event/remove actions produce {regression['action_reference_completions']} reference action completions and {regression['metrics'].get('modifier_callbacks_completed',0)} completed modifier callbacks. Bailu property buff, Acheron property contribution and Seele multi-event callback behavior pass. Silwolf dynamic write executes under exact caller-authored operand/provider policy, then stops at an anonymous TriggerAbility mask rather than silently skipping it. Argenti, Robin and Yukong definitions were also inspected but have no observed AddModifier site in the selected frozen graphs; no site is invented for them.

The sum of these distinctly labelled sandbox subcategories is **{explicit_action_total} reference wrapper/event actions and {callback_total} completed modifier callbacks**. This total is not a whole-real-skill coverage percentage or a frozen-corpus improvement.

Natasha remains a regression only: original source graphs and Skill02 child invocation are preserved; actor progression remains blocked without initialized real actor rows. Native actor supplied: false; progression blocker preserved: {natasha['actor_progression_preserved']}.

The largest remaining raw family is CONTENT_CATALOG_BINDING (145 combat / 75 joined; weighted score 295). Modifier/Event (181 / 43) is now principally instance/reference-policy/native-effective context for these frozen fixtures. Recommend **R18 DAMAGE / HP SETTLEMENT** as the largest remaining unimplemented combat primitive (74 combat / 15 joined; weighted score 104), with targeted missing catalog/source/reader work kept as a separate backlog. This is authored phase planning, not native semantics. Wave/maze predicates and provider/resource gaps exposed by explicit event probes are retained in ledger v5; R17 stops before those major subsystems and before any real Turn/AV engine.

Tests: {test_text}. Architecture, determinism and replay PASS. Focused tests cover exact binding, policies, identities, refresh/replace/stack, explicit providers/snapshots, activation/listeners, priority/predicates, nested owned callbacks, removal/cancellation, persistence/current-action drain, atomic registration and RNG rollback, callback retries/cycles/depth bounds, mid-callback restore/hash/replay, real configurations, Natasha preservation, heal stages and damage extension boundaries. Frozen tests are unchanged.

Production files: {json.dumps(PRODUCTION)}.
Tests: `{TESTS[0]}`.
Controls: {json.dumps(CONTROLS)}.
Audit: `tmp/audit/r17_modifier_event_20261009_001/`.

Reproduce: `python tools/runtime/r17_checks.py gate` before new edits; `python tools/runtime/r17_checks.py baseline`; `python tools/runtime/r17_probes.py`; `python tools/runtime/r17_regressions.py`; `python tools/runtime/r17_checks.py final`; `python tools/runtime/r17_finalize.py --package`. `--reuse-frozen` reuses the already verified unchanged frozen result while regenerating only explicitly labelled probes. The pinned R14/R16 source artifacts and catalog remain prerequisites.

Handoff destination: `{DEST.as_posix()}`. ZIP member set, CRC, sizes, per-member SHA-256 and archive SHA-256 are recorded in `handoff_verification.json`. Only R17-owned changes, parsed explicit fixture evidence, controls, logs, receipts and manifest are packaged; native binaries, whole source payloads, old audit trees and dumps are excluded.
'''
    (ROOT/REPORT).write_text(report,encoding='utf-8')
    print('controls/report finalized',flush=True)
    if '--package' in sys.argv:package(DEST)

def package(destination):
    payload=set(PRODUCTION+TESTS+TOOLS+CONTROLS+[REPORT])
    payload.update(p.relative_to(ROOT).as_posix() for p in AUDIT.rglob('*') if p.is_file() and
        not any(part in ('starting_files','test_tmp','__pycache__') for part in p.relative_to(AUDIT).parts) and
        p.name not in ('handoff_manifest.json','handoff_verification.json'))
    manifest={'change_request':CR,'scope':'R17-owned changes and audit only','git_writes':'NONE',
        'predecessor_hashes':{p:read(AUDIT/'start_gate.json')['file_hashes'].get(p) for p in PRODUCTION},
        'members':{p:{'size':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in sorted(payload)}}
    write('handoff_manifest.json',manifest);payload.add((AUDIT/'handoff_manifest.json').relative_to(ROOT).as_posix())
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for member in sorted(payload):archive.write(ROOT/member,member)
    details={}
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP CRC failure')
        if set(archive.namelist())!=payload or len(archive.namelist())!=len(payload):raise ValueError('ZIP member set mismatch')
        for info in archive.infolist():
            content=archive.read(info.filename);digest=hashlib.sha256(content).hexdigest()
            if digest!=sha(ROOT/info.filename) or len(content)!=(ROOT/info.filename).stat().st_size:raise ValueError('ZIP member mismatch')
            details[info.filename]={'size':len(content),'compressed_size':info.compress_size,'crc32':f'{info.CRC:08x}','sha256':digest}
    write('handoff_verification.json',{'destination':destination.as_posix(),'crc':'PASS','member_set':'PASS','sizes':'PASS',
        'per_member_sha256':'PASS','members':details,'member_count':len(payload),'ZIP_size':destination.stat().st_size,
        'ZIP_sha256':sha(destination),'excluded':['native binaries','whole raw source payloads','old audit trees','process dumps','baseline source copies']})
    print('HANDOFF',destination,'SHA256',sha(destination),flush=True)

if __name__=='__main__':
    if '--package-only' in sys.argv:
        override=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--destination=')),None)
        package(Path(override) if override else DEST)
    else:main()
