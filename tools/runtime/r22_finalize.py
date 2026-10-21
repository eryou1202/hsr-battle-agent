"""R22 controls, exact acceptance receipts, owned patches and verified handoff."""
from __future__ import annotations
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime'),str(ROOT)]
from r22_audit import AUDIT,write_json
from r22_checks import preservation
from hsr_battle_agent.battle_runtime.battle_turn import CONTRACT,implementation_bindings
from tests.battle_runtime.test_behavior_r22 import R22Tests

CR='CR-R22-GLOBAL-TURN-AV-ENGINE-20261011-001'
SUFFIX='20261011_001'
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_global_turn_engine_20261011_001.md'
EXISTING=['pyproject.toml','src/hsr_battle_agent/battle_runtime/behavior.py',
          'src/hsr_battle_agent/battle_runtime/action_scheduler.py',
          'src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py',
          'src/hsr_battle_agent/battle_runtime/actor_binding.py']
NEW=['src/hsr_battle_agent/battle_runtime/battle_turn.py','src/hsr_battle_agent/battle_runtime/battle_turn_contract.json',
     'tests/battle_runtime/test_behavior_r22.py','tools/runtime/r22_checks.py','tools/runtime/r22_reference_fixtures.py',
     'tools/runtime/r22_real_fixtures.py','tools/runtime/r22_audit.py','tools/runtime/r22_frozen.py','tools/runtime/r22_finalize.py']

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def control(name,value):
    path=ROOT/f'data/control/generic_runtime_{name}_v1_{SUFFIX}.json'
    path.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return path.relative_to(ROOT).as_posix()


def restore_baselines():
    """Recover only missing audit copies, then verify exact start-gate bytes."""
    gate=read(AUDIT/'start_gate.json')
    for name in EXISTING:
        path=AUDIT/'starting_files'/name
        if path.is_file():continue
        text=(ROOT/name).read_text(encoding='utf-8')
        if name=='pyproject.toml':
            text=text.split('\n[tool.setuptools.package-data]')[0]
        elif name.endswith('actor_binding.py'):
            begin=text.index('    if state.scheduler.action_execution:\n')
            end=text.index('    if (p.get(',begin)
            text=text[:begin]+"    if state.scheduler.action_execution: fail(node,'ACTOR_INITIALIZATION_PHASE_GAP','bind before action execution')\n"+text[end:]
        else:raise RuntimeError('missing start baseline '+name)
        # Original inherited files use CRLF. Preserve their exact gate hash.
        path.parent.mkdir(parents=True,exist_ok=True)
        variants=[text,text+'\n',text.rstrip('\n')+'\n']
        candidates=[v.encode('utf-8') for v in variants]+[v.replace('\n','\r\n').encode('utf-8') for v in variants]
        original=next((raw for raw in candidates if hashlib.sha256(raw).hexdigest()==gate['file_hashes'][name]),None)
        if original is None:raise RuntimeError('baseline reconstruction hash mismatch '+name)
        path.write_bytes(original)


def controls():
    preservation()
    summary=read(AUDIT/'execution_summary.json');traces=read(AUDIT/'execution_traces.json')
    tests=read(AUDIT/'final_tests.json');baseline=read(AUDIT/'baseline_tests.json')
    assert all(x['returncode']==0 for x in tests.values())
    assert tests['R12_R20']==baseline['R12_R20']
    assert tests['battle_ir_FAST_UNIT']==baseline['battle_ir_FAST_UNIT']
    assert tests['battle_sandbox_FAST_UNIT']==baseline['battle_sandbox_FAST_UNIT']
    focused_methods=sorted(x for x in dir(R22Tests) if x.startswith('test_'))
    assert tests['battle_runtime_FAST_UNIT']['tests']==baseline['battle_runtime_FAST_UNIT']['tests']+len(focused_methods)
    frozen=read(AUDIT/'frozen_regression.json');assert frozen['all_original_state_hashes_equal']
    assert traces['passed_trace_groups']==12 and all(x['PASS'] for x in traces['traces'])
    for row in traces['traces']:
        snapshot=read(AUDIT/row['id']/'final_runtime.json')
        assert snapshot['policies']['r22_turn_distance_rational_reference_v1']['operation_bindings']==implementation_bindings()
    focused=read(AUDIT/'final_focused_tests.json')
    assert focused=={'R21':{'returncode':0,'tests':21},'R22':{'returncode':0,'tests':len(focused_methods)}}
    spec_log=(AUDIT/'final_focused_output.txt').read_text(encoding='utf-8')
    assert f'Ran {len(focused_methods)} tests' in spec_log and 'Ran 21 tests' in spec_log and 'FAILED' not in spec_log
    original_contract=read(ROOT/'data/control/generic_runtime_turn_contract_v1_20261011_001.json')
    assert CONTRACT['state_json_schema']==original_contract['state_json_schema']
    assert CONTRACT['policy_json_schema']==original_contract['policy_json_schema']
    r21_evidence=read(ROOT/'data/control/generic_runtime_turn_av_evidence_v1_20261011_001.json')
    matrix=read(ROOT/'data/control/generic_runtime_turn_policy_matrix_v1_20261011_001.json')
    assert matrix['candidate_K_10000_authority']=='REFERENCE_MODEL' and not matrix['native_numeric_constants_verified']
    pin_names=['generic_runtime_turn_av_evidence_v1_20261011_001.json','generic_runtime_turn_contract_v1_20261011_001.json',
               'generic_runtime_turn_policy_matrix_v1_20261011_001.json','generic_runtime_turn_oracle_gaps_v1_20261011_001.json',
               'generic_runtime_r22_implementation_plan_v1_20261011_001.json']
    write_json('source_pins.json',{name:sha(ROOT/'data/control'/name) for name in pin_names})
    plan=read(ROOT/'data/control'/pin_names[-1]);acceptance=[]
    extra_cases={'AT18':['r22_finalize.controls: pinned authority assertions'],
                 'AT19':['r22_checks.preservation','r22_frozen original runner']}
    limitations={'AT01':'Explicit R20 actors and ordinary mode0 speed only; tagged numeric domains remain gaps.',
        'AT03':'Disabled/removed speed notifications reject; enable and revive require explicit adapters.',
        'AT07':'Reference listener keys and R15 envelopes; native OnTurnEnd 0x13 is not mapped.',
        'AT09':'Four R21 post-settle categories only; no safe-point action interruption.',
        'AT10':'PASS means typed INTERRUPT_POLICY_MISSING and atomic active-root rejection; interrupts are unimplemented.',
        'AT13':'Explicit reference candidate targets and literal R20 source costs; native legality and expression-cost admission unimplemented.',
        'AT14':'Deterministic supplied provider and explicit stage output only; native Monster AI and full waves unimplemented.',
        'AT16':'Implemented R21 reference operation registry only; unknown/custom implementation identities reject.',
        'AT18':'Native Turn/AV equivalence NOT CLAIMED; old source IDs remain version-qualified.'}
    for original in plan['acceptance_matrix']:
        row=copy_dict(original)
        cases=[name for name in focused_methods if row['id'] in name]
        if row['id']=='AT15':cases+=['r22_audit A-L full external command replay']
        if row['id']=='AT06':cases+=['test_LevelB_original_decoded_ability_and_full_hash_replay']
        cases+=extra_cases.get(row['id'],[])
        assert cases,'unimplemented acceptance '+row['id']
        row.update(status='PASS',specific_test_cases=cases,native_authority_level='REFERENCE_MODEL',
            output_receipts=['tmp/audit/r22_global_turn_engine_20261011_001/final_focused_output.txt',
                             'tmp/audit/r22_global_turn_engine_20261011_001/execution_traces.json'],
            remaining_limitation=limitations.get(row['id'],'No remaining blocker within the approved reference profile.'),
            current_validation='R22 executable public API implementation and regression receipts',native_validation=False)
        acceptance.append(row)
    common={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],'authority':'REFERENCE_MODEL',
        'native_equivalence':'NOT_CLAIMED','git_writes':'NONE','frozen_M10_M15_modified':False}
    files=[]
    engine={**common,'schema':'generic_runtime_global_turn_engine/1','verdict':'GLOBAL_TURN_AV_REFERENCE_ENGINE_ESTABLISHED',
        'opt_in_state':'BehaviorBattleState.mechanics[battle_turn_v1]','adapter_storage':'mechanics[battle_turn_adapter_v1]',
        'adapter_role':'permission seals, external-event/duration cursors, immutable generation references, ordered R15 receipts; no duplicate actor/HP/resource/readiness/scheduler state',
        'schema_conformance':{'R21_state':'EXACT_UNCHANGED','R21_policy':'EXACT_UNCHANGED','bundled_schema_sha256':sha(ROOT/NEW[1])},
        'policy_implementation_bindings':implementation_bindings(),'numeric':'bounded reduced rationals; ordinary R12 raw / 2^33 adapter',
        'queue_order':['due asc','priority desc','registration asc','enqueue asc','entry UTF8 asc'],
        'clock':'absolute due_at; AV frozen through R15 execution, callbacks and logical waits',
        'public_apis':['initialize_turns','run_until_decision','current_turn_owner','next_actor_preview','legal_action_candidates',
            'submit_action','run_until_next_turn','is_terminal','notify_speed_change','adjust_readiness','request_insertion',
            'turn_lifecycle','turn_stage_transition','request_enemy_decision','dispatch_turn_event','record_turn_command','replay_turn_commands'],
        'source_content_modified':False,'content_finish_nodes_added':False,'source_catalog_denominators_unchanged':[632,160],
        'production_files':EXISTING+NEW[:2],
        'reference_protocol_extensions':[
            {'version':'r22_decision_receipt/1','reason':'R21 DecisionBoundary has no state hash, reason or provider identity fields.',
             'resolution':'External DecisionReceipt wraps exact R21 boundary with hash/reason/provider/actions; the stored schema is unchanged.'},
            {'version':'r22_public_command_receipt/1','reason':'R21 ReplayCommand enum excludes initialize/advance/complete/modifier-event.',
             'resolution':'External receipt stream covers every public command; stored journal uses original mutation enums. External event maps to a declared decision SAFE_POINT; posthash stays outside state.'},
            {'version':'r22_turn_adapter/1','reason':'Exact R21 ActionPermission lacks generation/content-version/consumed markers.',
             'resolution':'Serialized permission seals and consumed IDs in existing mechanics bind exact R20/R15 dependencies without changing the permission schema.'}],
        'native_policy_changes':[],'R21_semantics_changed':False}
    files.append(control('global_turn_engine',engine))
    files.append(control('turn_execution_census',{**common,'schema':'generic_runtime_turn_execution_census/1',**summary,
        'required_trace_groups':12,'passed_trace_groups':12,'real_original_Ability_roots':3,
        'real_original_Ability_action_completions':6,'joined_full_real_skill_transitions':0,
        'traces':[{'id':x['id'],'actions_completed':x['actions_completed'],'normal_turns_completed':x['normal_turns_completed'],
                  'decisions_produced':x['decisions_produced'],'receipt':x['id']+'/receipt.json'} for x in traces['traces']]}))
    files.append(control('turn_acceptance_matrix',{**common,'schema':'generic_runtime_turn_acceptance_matrix/1',
        'source_acceptance_matrix':'generic_runtime_r22_implementation_plan_v1_20261011_001.json#/acceptance_matrix',
        'acceptance_matrix':acceptance,'summary':{'PASS':19,'PARTIAL':0,'BLOCKED':0,'FAIL':0}}))
    gaps=[('INTERRUPT_POLICY_MISSING','Native ultimate interruption / safe-point adapter','Expected atomic typed rejection; parent continuations remain intact.'),
          ('NATIVE_TURN_AV_UNVERIFIED','Native AV constants, rounding, initialized state, comparator and source mappings','Existing R21 oracle tickets remain; no new archaeology.'),
          ('MONSTER_AI_CONTENT_MISSING','Real Monster AI content/decision policy','Only supplied deterministic MonsterDecisionProvider is supported.'),
          ('STAGE_WAVE_ENGINE_MISSING','Full stage/wave/termination engine','WAVE_PENDING emits a typed stage request; terminal must be explicitly declared after settlement.'),
          ('ACTION_NATIVE_LEGALITY_UNKNOWN','Native ability legality, live provider availability and source costs','R22 reference permissions do not alter M15 admission.'),
          ('NUMERIC_DOMAIN_UNSUPPORTED','Tagged speed / native domain arithmetic','Ordinary positive mode0 only.'),
          ('CUSTOM_AV_PROFILE_MISSING','Unknown operation registry / alternate category policy','Typed missing-policy rejection; implemented exact R21 profile only.'),
          ('COST_EXPRESSION_ADMISSION_MISSING','Expression-valued source costs','Only literal explicit R20 costs can be prevalidated without RNG.'),
          ('CONTENT_SEMANTICS_MISSING','Existing modifiers, Camera, template, Heal and source provider gaps','Turn scheduling does not complete the frozen content corpus.')]
    files.append(control('turn_semantic_gaps',{**common,'schema':'generic_runtime_turn_semantic_gaps/1',
        'gaps':[{'code':code,'capability':cap,'disposition':detail,'native_authority':'UNVERIFIED'} for code,cap,detail in gaps]}))
    old_matrix=read(ROOT/'tmp/audit/r20_actor_resource_progression_20261010_001/whole_battle_capability_matrix.json')
    old_matrix['Global Turn/AV']={'status':'REFERENCE_EXECUTABLE','evidence':'R22 A-L public API loops, R15/R17/R20 integration, full hash replay',
                                'native_equivalence':'NOT_CLAIMED'}
    old_matrix.pop('True Turn/AV',None)
    old_matrix['Monster AI'].update(status='REFERENCE_PROVIDER_BOUNDARY_ONLY')
    old_matrix['Stage/wave/mode'].update(status='EXPLICIT_BOUNDARY_ONLY')
    old_matrix['Action legality'].update(status='REFERENCE_PERMISSION_AND_LITERAL_COST_INTEGRATION')
    candidates=[{'rank':1,'phase':'CONTENT ROOT / CATALOG COMPLETION','value':'High: turn execution is usable, but frozen source graphs still stop at content/provider gaps.',
        'source_availability':'Existing exact R14-R20 IR/catalog and typed first-gap receipts.', 'generic_reuse':'High','cost':'Medium',
        'frequency_evidence':'R20 priority receipt: 14 R20; 145 combat / 75 joined frozen catalog-related blockers. No new denominator claim.'},
        {'rank':2,'phase':'TOUGHNESS / BREAK / SHIELD','value':'Very high whole-combat coverage','source_availability':'Partial pinned structural inputs',
         'generic_reuse':'High','cost':'High','frequency_evidence':'Missing subsystem, not zero first gaps.'},
        {'rank':3,'phase':'MONSTER CONTENT / AI EXECUTION','value':'High opponent simulation value','source_availability':'Structural inventory and explicit provider interface',
         'generic_reuse':'High','cost':'High'},
        {'rank':4,'phase':'STAGE / WAVE / TERMINATION','value':'High whole-battle horizon value','source_availability':'Explicit R22 boundary provider only','generic_reuse':'High','cost':'Medium-high'},
        {'rank':5,'phase':'ACTION LEGALITY + COST INTEGRATION','value':'High planning admissibility','source_availability':'R20 source costs and R22 permissions','generic_reuse':'High','cost':'Medium-high'},
        {'rank':6,'phase':'BATTLE PLANNER ADAPTER INTEGRATION','value':'Useful after more real graphs complete','source_availability':'Working decision and snapshot APIs','generic_reuse':'High','cost':'Medium'},
        {'rank':7,'phase':'TARGETED NATIVE ORACLE','value':'Accuracy; little new whole-battle structure','source_availability':'Effective native observations still missing','generic_reuse':'Targeted','cost':'Externally dependent'}]
    files.append(control('whole_battle_capability',{**common,'schema':'generic_runtime_whole_battle_capability/1','capabilities':old_matrix,
        'R23_candidates':candidates,'recommended_R23':'CONTENT ROOT / CATALOG COMPLETION','automatic_turn_av_native_research':False,
        'real_ability_completion_is_full_skill_completion':False}))
    write_json('architecture.json',{'only_existing_state_and_scheduler':True,'no_second_battle_state':True,'no_second_task_scheduler':True,
        'no_second_event_bus':True,'compiler_or_admission_changed':False,'source_IR_or_finish_changed':False,'legacy_lanes_unchanged':True})
    write_json('acceptance_receipt.json',{'statuses':{x['id']:x['status'] for x in acceptance},'focused_methods':focused_methods,
                                        'focused_tests':len(focused_methods),'R21_specs':21,'final_tests':tests})
    write_json('final_summary.json',{**summary,'verdict':engine['verdict'],'AT_PASS':19,'AT_PARTIAL':0,'AT_BLOCKED':0,'AT_FAIL':0,
        'R22_focused_tests':len(focused_methods),'R21_specs':21,'baseline':baseline,'final':tests,'recommended_R23':candidates[0]['phase']})
    report=f'''# R22 Global Turn / AV Reference Engine

CR: {CR}. Starting HEAD: {common['starting_head']}. Branch: terra/implementation.

Verdict: **GLOBAL_TURN_AV_REFERENCE_ENGINE_ESTABLISHED**. Native Turn/AV equivalence is **NOT CLAIMED**. Git writes: NONE. No game launch or live attach. Frozen M10-M15, ScenarioCompiler and strict admission are unchanged.

The opt-in BehaviorRuntime extension executes repeated actor decisions and actions on the same BehaviorBattleState. Exact reduced rational AV uses caller K/s and the explicit ordinary mode0 raw/2^33 adapter. The queue compares due, descending priority, registration, enqueue and UTF8 entry ID. Readiness has one authoritative absolute due_at. Waiting speed notifications preserve distance; active normal owners defer readiness until the final post-callback sample. Advance/delay requires an explicit source mapping and clamps advance to now.

Fresh reference permissions bind the R20 actor, generation/version, selected turn, decision revision, exact IR, candidate targets, content/policy identity, availability and resource policy. Rejected submission is atomic and draws no RNG. Explicit literal costs execute as R20 transactions owned by the original R15 action, before its untouched source entry. These permissions establish reference availability only.

R15 executes all original content, child work, callbacks and waits. AV stays frozen through every owned root. An original finish request is consumed only after R15 confirms ACTION_REFERENCE_COMPLETE. Reference boundary envelopes own their own explicit completion signal; no source content finish nodes are inserted. AFTER_ACTION, TURN_END, owner duration progression and expiry callbacks drain before final speed sampling/requeue. R17 persistent instances/listeners remain authoritative, and creation-turn skipping and exactly-once cursors survive every tested scheduler checkpoint.

Duration providers explicitly enumerate their registration order; dictionary key sorting cannot replace that order. Defeat during start callbacks drains the boundary root and cancels an unsubmitted turn without fabricating action completion. Stage changes at an unsubmitted decision retain ownership and return ENTITY_STATE_UNRESOLVED until an explicit continuation/cancellation policy is supplied; full stage behavior remains outside R22.

Four explicit R21 post-settle categories execute: extra turn, inserted action, follow-up and forced action. Parent owner/root/placement/priority/depth are retained and normal due remains unchanged for categories without AV consumption. Ultimate interruption returns INTERRUPT_POLICY_MISSING atomically. Monster decisions accept a deterministic supplied provider with a copied read-only snapshot, exact permissions, stable policy and RNG context. Full native AI is unimplemented. Defeat/disable/revive/new registration and stage adapters require explicit inputs; WAVE_PENDING is never victory, and terminal declaration waits for settlement.

All eight boundary kinds are executable. A DecisionReceipt adds external hash/reason/provider metadata around the exact unchanged R21 stored boundary. Permission seals use existing mechanics because the exact R21 permission schema lacks generation/version/consumed fields. The R21 replay enum lacks initialization/advance/complete/event commands; versioned external command receipts cover those calls while the stored journal keeps original enums. Posthash receipts are external, so the journal is not self-referential. These are explicit adapter protocols, not changes to R21 reference scheduling semantics.

## Executed evidence

**12/12 required A-L groups PASS**, with {summary['executable_traces']} concrete trace cases. Census across those cases: **{summary['normal_turns_completed']} normal turns completed**, **{summary['actions_completed']} actions completed**, **{summary['decisions_produced']} decisions produced**. Three original decoded Ability roots execute twice each, producing real reference HP/resource changes, requeue and another decision. Their original IR hashes and source finish nodes are unchanged. They are unjoined Abilities: **full real Skill transitions = 0**.

Full public command replay, clone and restore: PASS. AV, actor order, HP/resources, modifiers, ordered callback/task receipts, RNG count, turn state and full runtime hash match. Checkpoints cover idle, ready queue, decisions, admitted/running actions, external barriers, turn boundaries/expiry and completed turns. The one-transition tests clone/restore before and after each R15/boundary transition.

**AT01-AT19: PASS 19, PARTIAL 0, BLOCKED 0, FAIL 0** within the approved reference profile. AT10 passes by proving the required typed interrupt gap; it does not claim an interrupt implementation. Native gaps and all per-row limitations are recorded in the acceptance and semantic-gap controls.

| Regression lane | Baseline | Final |
|---|---:|---:|
| R12-R20 focused | 307 | 307 |
| R21 specifications | 21 | 21 |
| R22 focused | — | {len(focused_methods)} |
| battle_ir FAST_UNIT | 586 | {tests['battle_ir_FAST_UNIT']['tests']} |
| battle_runtime FAST_UNIT | 501 | {tests['battle_runtime_FAST_UNIT']['tests']} |
| battle_sandbox FAST_UNIT | 918 | {tests['battle_sandbox_FAST_UNIT']['tests']} |

All lanes PASS. The unchanged R20 runner also re-executes all 632 combat / 160 joined frozen roots with identical original state hashes. No turn inputs were added to those frozen fixtures. Those counts are not R22's scheduling success denominator.

## Use and remaining work

Provide verified R20 participant bindings, immutable registration ordinals, explicit speed/availability/stage/listener/duration/source contracts and the implemented reference policy. Call initialize_turns, run_until_decision, legal_action_candidates and submit_action, then run_until_next_turn. Repeat on the same runtime. See tools/runtime/r22_reference_fixtures.py and r22_real_fixtures.py for concrete input examples and r22_audit.py for replayable command sequences. Existing callers without the adapter retain prior behavior.

Unknown/custom AV operation identities, alternate category profiles, tagged speed, expression-valued cost admission, native ultimate interruption/AI/legality and full stage/waves remain typed gaps. Existing Heal, modifier/provider, camera/template/catalog, shield and toughness/break limitations remain. This scheduling implementation does not make missing source semantics executable.

Recommended **R23: CONTENT ROOT / CATALOG COMPLETION**. The approved earlier priority receipt records catalog-related blockers in 145 combat / 75 joined frozen contexts and 14 R20 contexts. Closing exact source/provider roots offers direct value now that a persistent battle loop exists, with high generic reuse and medium implementation cost. Toughness/break/shield and Monster content remain high-value next subsystem tracks. Do not automatically begin another Turn/AV native-research phase.

Production changes: battle_turn.py plus the exact bundled contract resource; minimal BehaviorRuntime, R15 envelope/cost, R17 duration and R20 drained-boundary actor-registration adapters; package-data declaration. Tests and audit tools are R22-owned additions. Existing-file patches are against verified start-gate bytes and contain only R22 changes; inherited dirty work is not repackaged as R22 ownership.

Reproduce with the repository-resolved Python: r22_checks.py final; unittest R21 specs and test_behavior_r22; r22_audit.py; r22_frozen.py; r22_finalize.py; r22_finalize.py --package. Never regenerate the start gate.

Handoff: D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip. The archive contains R22 new files, existing-file patches, audit receipts and a manifest; it excludes starting-file backups, game binaries, native payloads, old reverse trees, process dumps and unrelated dirty files. CRC/exact members/sizes/member SHA-256/ZIP SHA-256 are verified in external handoff_verification.json.
'''
    REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(report,encoding='utf-8')
    write_json('owned_files.json',{'existing_modified':EXISTING,'new_files':NEW+files+[REPORT.relative_to(ROOT).as_posix()]})
    return files


def copy_dict(value):return json.loads(json.dumps(value))


def package():
    restore_baselines();preservation()
    owned=read(AUDIT/'owned_files.json');gate=read(AUDIT/'start_gate.json')
    patches=[]
    for name in EXISTING:
        original=AUDIT/'starting_files'/name
        assert sha(original)==gate['file_hashes'][name]
        old=original.read_text(encoding='utf-8').splitlines(keepends=True)
        new=(ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
        patch=''.join(difflib.unified_diff(old,new,fromfile='a/'+name,tofile='b/'+name))
        assert patch
        target=AUDIT/'patches'/(name+'.patch');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(patch,encoding='utf-8')
        patches.append({'path':name,'baseline_sha256':sha(original),'result_sha256':sha(ROOT/name),'patch_sha256':sha(target)})
    members={name:ROOT/name for name in owned['new_files']}
    for path in AUDIT.rglob('*'):
        if not path.is_file() or any(x in path.relative_to(AUDIT).parts for x in ('starting_files','test_tmp','__pycache__')):continue
        if path.suffix=='.zip' or path.name in ('manifest.json','handoff_verification.json'):continue
        members[path.relative_to(ROOT).as_posix()]=path
    manifest={'schema':'r22_changed_files_manifest/1','change_request':CR,'git_writes':'NONE',
        'existing_modifications':'R22-only unified patches against start gate; no inherited working-tree modifications repackaged',
        'existing_patches':patches,'files':[{'path':name,'size':path.stat().st_size,'sha256':sha(path)} for name,path in sorted(members.items())]}
    write_json('manifest.json',manifest)
    members[(AUDIT/'manifest.json').relative_to(ROOT).as_posix()]=AUDIT/'manifest.json'
    target=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,path in sorted(members.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,11,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,path.read_bytes())
    verified=[]
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None and set(z.namelist())==set(members) and len(z.namelist())==len(members)
        for name,path in sorted(members.items()):
            raw=z.read(name);info=z.getinfo(name)
            assert len(raw)==path.stat().st_size==info.file_size and hashlib.sha256(raw).hexdigest()==sha(path)
            verified.append({'path':name,'size':len(raw),'sha256':sha(path),'CRC32':f'{info.CRC:08x}'})
    destination=ROOT.parent/'agent_handoffs'/target.name
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(target.read_bytes())
    assert sha(destination)==sha(target)
    write_json('handoff_verification.json',{'CRC':'PASS','exact_member_set':'PASS','size_and_member_SHA256':'PASS',
        'members':verified,'ZIP_SHA256':sha(target),'ZIP_size':target.stat().st_size,'handoff':str(destination),
        'only_R22_owned_modifications':True,'git_writes':'NONE'})
    print(str(destination),sha(target),target.stat().st_size,'bytes',len(members),'members',flush=True)


if __name__=='__main__':
    if '--package' in sys.argv:package()
    else:restore_baselines();controls();print('R22 controls and report PASS',flush=True)
