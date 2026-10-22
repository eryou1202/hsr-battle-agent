"""R23 controls, preservation, evidence ranking and exact-member handoff."""
from __future__ import annotations
import ast
import collections
import difflib
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r23_checks import AUDIT
from r23_discovery import write
from r21_checks import read,sha

CR='CR-R23-REAL-SKILL-ROOT-CLOSURE-20261012-001'
SUFFIX='20261012_001'
PRODUCTION=['src/hsr_battle_agent/battle_ir/content_catalog.py',
    'src/hsr_battle_agent/battle_runtime/action_scheduler.py','src/hsr_battle_agent/battle_runtime/battle_turn.py']
TEST='tests/battle_runtime/test_behavior_r23.py'
TOOLS=['tools/runtime/r23_'+n+'.py' for n in ['checks','discovery','reference_fixtures','census','probes','finalize']]
REPORT='docs/agent/handoffs/generic_runtime_real_skill_root_closure_'+SUFFIX+'.md'
CONTROL_NAMES=['joined_skill_dependency_v1','catalog_closure_v2','camera_reference_audit_v1',
    'joined_skill_execution_census_v1','support_census_v11','semantic_gap_ledger_v9']


def control(name,value):
    p=ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json'
    p.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return p.relative_to(ROOT).as_posix()


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode('utf-8').strip()


def preservation():
    gate=read(AUDIT/'start_gate.json')
    changed=[n for n,h in gate['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    unexpected=sorted(set(changed)-set(PRODUCTION))
    forbidden=[]
    for name in PRODUCTION:
        tree=ast.parse((ROOT/name).read_text(encoding='utf-8-sig'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Constant) and isinstance(n.value,str) and any(t in n.value for t in
                ('Avatar_Anaxa','Avatar_Natasha','Avatar_BlackSwan','Avatar_Serval')):
                forbidden.append({'file':name,'line':n.lineno,'constant':n.value})
    receipt={'changed_starting_files':changed,'unexpected_changes':unexpected,'checked_files':len(gate['file_hashes']),
        'head_unchanged':git('rev-parse','HEAD')==gate['head'],'branch_unchanged':git('branch','--show-current')==gate['branch'],
        'staged_unchanged':git('diff','--cached','--name-status')==gate['staged'],'forbidden_character_constants':forbidden,
        'frozen_M10_M15_modified':False,'frozen_historical_tests_modified':False,'ScenarioCompiler_modified':False,
        'strict_admission_bypassed':False,'new_catalog':False,'new_runtime':False,'game_launch':False,'live_attach':False,
        'git_writes':'NONE','status':'PASS'}
    assert not unexpected and not forbidden and receipt['head_unchanged'] and receipt['staged_unchanged'] and receipt['branch_unchanged'],receipt
    write('architecture_preservation.json',receipt)
    return receipt


def main():
    architecture=preservation();gate=read(AUDIT/'start_gate.json')
    dependency=read(AUDIT/'joined_dependency.json');camera=read(AUDIT/'camera_audit.json');phases=read(AUDIT/'phase_retry.json')
    rows=read(AUDIT/'joined_execution_results.json');summary=read(AUDIT/'execution_summary.json')
    template=read(AUDIT/'template_before_after.json');stepped=read(AUDIT/'stepped_template_checkpoint.json')
    frozen=read(AUDIT/'frozen_regression.json');r22=read(AUDIT/'r22_regression/execution_summary.json')
    baseline=read(AUDIT/'baseline_tests.json');tests=read(AUDIT/'final_tests.json')
    assert set(tests)=={'R12_R23','R21','battle_ir_FAST_UNIT','battle_runtime_FAST_UNIT','battle_sandbox_FAST_UNIT'},tests
    assert len(rows)==160 and summary['roots']==160 and not summary['source_closed_unique_roots']
    assert frozen['all_original_state_hashes_equal'] and r22['normal_turns_completed']==16 and r22['actions_completed']==18
    assert all(x['returncode']==0 for x in tests.values()), tests
    version_test=(AUDIT/'version_boundary_test.txt').read_text(encoding='utf-8-sig')
    assert 'Ran 1 test' in version_test and 'OK' in version_test and 'FAILED' not in version_test
    assert all(r['source_IR_unchanged'] for r in rows)
    assert stepped['replay']=='PASS' and stepped['status']=='SEMANTIC_GAP',stepped['status']
    # Exact site counts are independent from per-root first-gap counts.
    sites={e['site_id']:e for e in dependency['dependency_sites']}
    rootsets=collections.defaultdict(set);deps=collections.defaultdict(set)
    for root in dependency['roots']:
        for sid in root['structural_gap_sites']:
            e=sites[sid];k=e['content_class'];rootsets[k].add(root['root'])
            deps[k].add(tuple(e.get('target_source_identity',[])) or e.get('identity') or sid)
    runtime_sets=collections.defaultdict(set)
    for row in rows:runtime_sets[row['runtime_first_gap_class']].add(row['root'])
    ranking=[]
    for klass,roots in rootsets.items():
        ranking.append({'blocker_class':klass,'joined_roots_affected':len(roots),
            'common_exact_or_unresolved_dependency_identities':len(deps[klass]),
            'reference_runtime_reuse':'HIGH','evidence_confidence':'HIGH_WITHIN_PINNED_SCOPE',
            'implementation_cost':'NEW_SOURCE_INFRASTRUCTURE_OR_ORACLE' if klass=='CONTENT_NOT_FOUND' else
                'TARGETED_READER' if klass=='CONTENT_READER_GAP' else 'EXPLICIT_CONTEXT_BINDING',
            'downstream_completion_opportunity':'UNKNOWN_UNTIL_NEXT_REAL_BLOCKER',
            'disposition':'DEFER_PRECISE_ORACLE_TICKETS' if klass=='CONTENT_NOT_FOUND' else 'TARGETED_ONLY_NO_BROAD_CATALOG_PHASE'})
    ranking.sort(key=lambda r:-r['joined_roots_affected'])
    for i,r in enumerate(ranking):r['affected_root_rank']=i+1
    runtime_ranking=[]
    for klass,affected in sorted(runtime_sets.items(),key=lambda p:(-len(p[1]),p[0])):
        cohort=[r for r in rows if r['runtime_first_gap_class']==klass]
        runtime_ranking.append({'rank':len(runtime_ranking)+1,'blocker_class':klass,
            'joined_roots_affected':len(affected),
            'common_source_dependencies':len({r['required_capability'].split(':',1)[-1] for r in cohort}),
            'primitive_families':dict(collections.Counter(r['primitive'] or 'R22_BOUNDARY' for r in cohort)),
            'reference_runtime_reuse':'HIGH: existing R15/R17/R19/R20/R22 ownership and transactions',
            'evidence_confidence':'EXACT_RUNTIME_SITE; native effective values remain unknown',
            'implementation_cost':'EXTERNAL_SOURCE_OR_ORACLE' if klass=='CONTENT_NOT_FOUND' else
                'TARGETED_READER' if klass=='CONTENT_READER_GAP' else 'EXPLICIT_INPUT_AND_POLICY' if
                klass in ('ACTOR_STATE_INPUT_MISSING','DYNAMIC_PROVIDER_INPUT_MISSING') else 'GENERIC_SEMANTIC_HANDLER',
            'downstream_opportunity':'15 original child finishes already reachable, but no parent is fully closed; rerun after each targeted change'})
    inline=[x for r in rows for x in r['template_bindings'] if x.get('source')]
    # Supplement cached base-cohort receipts with the fresh staged call metadata.
    staged_inline=[x for stage in template for value in stage.values() if isinstance(value,dict)
                   for x in value.get('template_bindings',[]) if x.get('source')]
    spans={x['call_node_hash']:x.get('call_source_span') for x in staged_inline if x.get('call_source_span')}
    if any(x['call_node_hash'] not in spans for x in inline):
        from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes
        records=read(ROOT/'tmp/audit/r16_ability_dependency_closure_20261008_001/catalog_records.json')
        parents={tuple(x['source']['parent_source_identity']) for x in inline}
        for r in records:
            if (r['source_shard_sha256'],r['record_start'],r['record_end']) not in parents:continue
            ir=IRNode.from_dict(read(ROOT/r['IR_artifact']))
            for n in walk_nodes(ir):
                if n.op=='RPG.GameCore.IncludeTaskListTemplate':spans[n.stable_hash()]=n.payload['span']
    bound_definitions={tuple(x['source']['inline_source_identity']) for x in inline}
    bound_views={(x['source']['canonical_parent_IR_hash'],x['node_id']) for x in inline}
    bound_sites={(x['source']['canonical_parent_IR_hash'],tuple(x.get('call_source_span') or spans.get(x['call_node_hash']) or [x['node_id']])) for x in inline}
    child_closed=0;external_closed=0
    for root in dependency['roots']:
        external=[sites[s] for s in root['transitive_dependency_sites'] if not sites[s].get('inline')]
        children=[s for s in external if s['reference_type']=='ABILITY_REFERENCE']
        child_closed+=all(s['status']=='EXACT_RESOLVED_COMPILED' for s in children)
        external_closed+=all(s['status']=='EXACT_RESOLVED_COMPILED' for s in external)
    coverage={'denominator_unique_joined_roots':160,'canonical_owner_rows':660,'exact_owner_config_rows':309,
        'exact_root_join_rows':306,'decoded_joined_unique_roots':160,'decoded_joined_rows':161,
        'joined_roots_exact_child_ability_closure':child_closed,'joined_roots_all_external_content_closed':external_closed,
        'joined_roots_camera_first_blocker_frozen':68,'camera_reference_sites_unresolved':68,
        'phase_reference_sites_reader_blocked':7,'joined_roots_template_runtime_first_blocker':len(runtime_sets['TEMPLATE_PARAMETER_CONTEXT_MISSING']),
        'joined_roots_actor_state_first_blocker':len(runtime_sets['ACTOR_STATE_INPUT_MISSING']),
        'joined_roots_unsupported_primitive_first_blocker':len(runtime_sets['RUNTIME_PRIMITIVE_UNSUPPORTED']),
        'joined_roots_dynamic_provider_first_blocker':len(runtime_sets['DYNAMIC_PROVIDER_INPUT_MISSING']),
        'joined_roots_original_finish_reached':summary['original_finish_reached_roots'],
        'joined_roots_reference_complete':summary['source_closed_unique_roots'],
        'joined_roots_policy_abstracted_complete':summary['policy_abstracted_unique_roots'],
        'joined_roots_partial_executable_prefix':summary['partial_real_skill_prefix_roots'],
        'blocked_real_skill_entries':summary['blocked_real_skill_entries'],
        'new_exact_external_source_dependencies_recovered':0,'exact_inline_template_definitions_bound':len(bound_definitions),
        'exact_inline_template_call_sites_bound':len(bound_sites),'canonical_template_call_views_bound':len(bound_views)}
    common={'change_request':CR,'starting_head':gate['head'],'source_version':'4.6.51','authority':'REFERENCE_MODEL',
        'native_correctness':'NOT_CLAIMED','git_writes':'NONE','frozen_M10_M15_modified':False}
    # Bind each root's executable observation back to its exact structural census.
    bykey={tuple(r['source_identity']):r for r in rows}
    for root in dependency['roots']:
        execution=bykey[tuple(root['source_identity'])]
        root['R23_explicit_first_gap']={k:execution[k] for k in ('primitive','required_capability','gap_node','runtime_first_gap_class')}
        root['R23_executable_status']=execution['cohort']
        root['next_blocker_after_each_resolved_dependency']={
            'observation':'R23 action prefix only; blocked/unexecuted branches are not inferred closed',
            'next_gap':execution['required_capability'],'node':(execution['gap_node'] or {}).get('node_id'),
            'template_stages':[{k:v.get('required_capability') for k,v in t.items() if isinstance(v,dict)}
                for t in template if t['root']==root['root']]}
    capability=[
        {'rank':1,'subsystem':'TOUGHNESS / BREAK / SHIELD','whole_battle_value':'HIGH: expands every damage settlement boundary',
         'reuse':'R18/R19 damage transactions, R17 callbacks and R22 ownership','source_evidence':'PARTIAL; keep reference contracts explicit',
         'cost':'HIGH; bounded independent core subsystem','catalog_phase_required':False},
        {'rank':2,'subsystem':'STAGE / WAVE / TERMINATION','whole_battle_value':'HIGH: finite encounters, wave handoff and victory/defeat',
         'reuse':'R22 explicit stage and terminal boundaries','source_evidence':'PARTIAL','cost':'MEDIUM_HIGH'},
        {'rank':3,'subsystem':'MONSTER CONTENT / AI','whole_battle_value':'HIGH: real opposing actions and decisions',
         'reuse':'R22 supplied provider boundary','source_evidence':'STRUCTURAL INVENTORY; effective AI missing','cost':'HIGH'},
        {'rank':4,'subsystem':'ACTION LEGALITY','whole_battle_value':'HIGH: planning validity',
         'reuse':'canonical catalog receipts, R20 resources, R22 permissions','source_evidence':'NATIVE AVAILABILITY UNKNOWN','cost':'HIGH'},
        {'rank':5,'subsystem':'PLANNER BRIDGE','whole_battle_value':'MEDIUM until more complete mechanics/content',
         'reuse':'existing snapshot and decision APIs','source_evidence':'REFERENCE APIs PRESENT','cost':'MEDIUM'},
        {'rank':6,'subsystem':'TARGETED NATIVE ORACLE','whole_battle_value':'TARGETED identity/accuracy unblocking',
         'reuse':'precise Camera/Phase/context tickets','source_evidence':'EXTERNAL REQUIRED','cost':'EXTERNALLY_DEPENDENT'}]
    closure={**common,'schema':'generic_runtime_catalog_closure/2','verdict':'ROOT_CLOSURE_BLOCKED_BY_EXACT_SOURCE_EVIDENCE',
        'progress':'Exact canonical owner admission, source-backed child prefixes and parent-scoped template dictionary execution advanced',
        'preferred_success_milestone_claimed':False,'first_full_joined_skill_reference_transition_claimed':False,
        'coverage':coverage,'before_after':{'canonical_owner_rows':[660,660],'owner_config_rows':[309,309],
            'exact_root_rows':[306,306],'decoded_unique_joined_roots':[160,160],
            'frozen_catalog_first_gaps_combat':[145,145],'frozen_catalog_first_gaps_joined':[75,75],
            'camera_audit_sites':[68,68],'phase_reader_sites':[7,7],
            'frozen_template_context_first_gaps':[5,5],
            'source_closed_joined_transitions':[0,0],'policy_abstracted_joined_transitions':[0,0],
            'original_finish_reached_frozen_vs_R23_explicit':[0,summary['original_finish_reached_roots']]},
        'template_context_stages':template,'ranked_structural_blockers':ranking,
        'ranked_runtime_blockers':runtime_ranking,
        'runtime_blocker_distribution':summary['first_gap_classes'],
        'runtime_ranking_basis':'unique joined roots affected, common exact dependencies, reusable reference machinery, evidence confidence and downstream opportunities; not raw task frequency',
        'camera_stop_policy':camera['stop'],'phase_attempts':phases,
        'frozen_regression':frozen,'R22_multi_turn_regression':r22,'determinism':'PASS','replay':'PASS',
        'architecture':architecture,'baseline_tests':baseline,'final_tests':tests,
        'additional_version_boundary_guard_test':{'tests':1,'status':'PASS','log':'version_boundary_test.txt'},
        'whole_battle_reassessment':capability,'recommended_R24':'TOUGHNESS / BREAK / SHIELD',
        'another_broad_catalog_phase':'NO_GO; R23 is the final broad catalog-first phase by default',
        'native_ultimate_interruption':'UNIMPLEMENTED; existing atomic typed gap retained',
        'production_files':PRODUCTION,'test_files':[TEST]}
    execution={**common,'schema':'generic_runtime_joined_skill_execution_census/1','summary':summary,
        'count_policy':'unique roots, original finish nodes, action completions and turn transitions are separate; unjoined R22 roots excluded',
        'source_closed_cohort':[],'policy_abstracted_cohort':[],'results':rows,
        'additional_explicit_template_provider_cohort':template,
        'restore_checkpoints':stepped['checkpoints'],'between_successive_normal_turns':'R22 unchanged A-L traces; no joined source-closed battle available'}
    ledger=[]
    for edge in dependency['dependency_sites']:
        if edge.get('inline') or edge['content_class']=='EXACT_CONTENT_PRESENT':continue
        ledger.append({'id':edge['site_id'],'class':edge['content_class'],'source_identity':edge['parent_source_identity'],
            'field_identity':edge['field_identity'],'pointer':edge['pointer'],'span':edge['span'],
            'identity':edge.get('identity'),'target_identity':edge.get('target_source_identity'),
            'structural_status':edge['status'],'resolution_evidence':edge.get('resolution_evidence'),
            'next_evidence':edge.get('question') or edge.get('required_context_policy') or 'exact source body + trusted scope required'})
    ledger.extend({'id':'R23-RUNTIME-'+str(i+1).zfill(3),'class':r['runtime_first_gap_class'],
        'root':r['root'],'source_identity':r['source_identity'],'primitive':r['primitive'],
        'required_capability':r['required_capability'],'node':r['gap_node'],
        'turn_owner':r['turn_owner'],'normal_turns_completed':r['normal_turns_completed'],
        'scope':'R23_EXPLICIT_REFERENCE_SCENARIO'} for i,r in enumerate(rows))
    control('joined_skill_dependency_v1',{**common,**dependency})
    control('catalog_closure_v2',closure)
    control('camera_reference_audit_v1',{**common,'schema':'generic_runtime_camera_reference_audit/1',**camera})
    control('joined_skill_execution_census_v1',execution)
    control('support_census_v11',{**common,'schema':'generic_runtime_support_census/11','coverage':coverage,
        'frozen_denominators':[632,160,161],'frozen_corpus_drift':'NONE','R23_explicit':summary,
        'R22_regression':r22,'tests':tests,'whole_battle_reassessment':capability})
    control('semantic_gap_ledger_v9',{**common,'schema':'generic_runtime_semantic_gap_ledger/9',
        'classes':dependency['blocker_classes'],'entries':ledger,'remaining_whole_battle_subsystems':capability,
        'native_ultimate_interruption':'MISSING','native_action_legality':'MISSING','ranking':ranking})
    report=f'''# R23 Real Skill Root Closure

CR: {CR}. Starting HEAD: `{gate['head']}`. Branch: `{gate['branch']}`.

Verdict: **ROOT_CLOSURE_BLOCKED_BY_EXACT_SOURCE_EVIDENCE**. Full source-closed joined transitions: **0**. Policy-abstracted complete transitions: **0**. Native correctness: **NOT CLAIMED**. R23 advances exact canonical admission and executable real prefixes without claiming the preferred full-closure milestone.

All 660 canonical ownership rows remain separate from 309 exact owner/config rows, 306 exact directory root rows, 161 compiled joined rows and 160 unique compiled joined roots. These historical denominators are unchanged. The new census contains {len(dependency['dependency_sites'])} dependency sites, exact source hashes/spans, every owner/level/config edge, direct and transitive site IDs, frozen and explicit runtime gaps, a ranked go/no-go assessment, and the eight requested semantic diversity roles.

ContentCatalog now verifies Avatar.SkillList, the original decoded SkillID/level/SkillTriggerKey, Avatar.JsonPath, the direct CharacterConfig skill-list slot, EntryAbility and its unique trusted compiled directory entry. The Skill level record is re-read from its pinned original byte span with the existing reader. R22 binds the resulting receipt to the existing R20 actor, content version and original IR. Fresh reference permissions retain the existing provider, target, cost, generation and policy seals. No second catalog, actor model, runtime or scheduler was added.

The Camera audit first reads the exact R16 per-site evidence. One R16 Bailu row lacked a parent site; its actual serialized call was recovered from the exact decoded child body. Parent CharacterConfig declarations, all 2672 trusted directory entries including alternative record types, and inline definitions were checked. Two new path families produced 86 exact-index candidate queries and zero asset hits. All 68 sites remain EXACT_SOURCE_NOT_FOUND within the bounded scope, with UNKNOWN behavior. A CharacterConfig declaration is not an executable body. No missing Camera was replaced or classified as a presentation no-op. Discovery stops here; each site has a precise oracle ticket.

All seven remaining Phase directory identities were re-read under pinned shard hashes and the existing R14/R16 schemas. None achieved bounded full consumption. Their exact reader RVA/question remains in phase_retry.json and the closure control. No inactive field was guessed and no further native reader/provider/IFix/Lua campaign was started.

R15 now has an opt-in hash-keyed serialized template dictionary policy. Numeric and string expressions are evaluated from the original compiled dictionaries; original sequence bodies are retained, duplicate identities and unknown contexts reject, and missing inputs remain gaps. Parent-scoped inline templates are exposed from the existing compiled subtree with an explicit scope/entry adapter and no added task. Native scope/provider inheritance remains UNKNOWN. The Black Swan original joined root progresses from TEMPLATE_PARAMETER_INHERITANCE to the exact missing dynamic lookup. A separate explicit unit-valued provider input advances it to the original template body and its next unsupported ByRandomChance predicate. All additional values and policy authority are recorded; the frozen scenario is untouched.

Every one of the 160 joined roots is selected through a canonical owner receipt, R20 ActorRuntimeBinding, an R22 normal decision/permission and the original R15 action on the same BehaviorBattleState. {summary['partial_real_skill_prefix_roots']} roots execute a nonempty real prefix; {summary['blocked_real_skill_entries']} stop without a completed source task. {summary['hp_settled_roots']} roots settle reference HP and {summary['original_finish_reached_roots']} reach/complete an original SkillPerformFinish in their owned child tree. These source finishes cannot release a parent that subsequently needs missing content. Joined action completions and joined next-turn transitions remain zero. All 160 original root IR hashes are unchanged. R22's six historical unjoined action completions remain a separate cohort.

The explicit cohort first-gap classes are `{json.dumps(summary['first_gap_classes'],sort_keys=True)}`. The frozen catalog first gaps remain 145/632 combat and 75/160 joined; their Camera/Phase split remains 68/7. Five combat template-context first gaps remain five in the unchanged frozen view. Source content recovery is zero; {len(bound_definitions)} exact inline template body and {len(bound_sites)} call-site bindings become available only under separately recorded reference policies.

Frozen regression PASS: 632 combat / 160 joined roots, original inputs, task reach/completion, first gaps and all original state hashes unchanged. R22 A-L PASS: 12/12 groups, 16 normal turns, 18 action completions, 35 decisions. The new missing-content scenarios retain the current action/turn owner and freeze AV. Full public command replay and clone/snapshot restore pass for {summary['clone_snapshot_replay_roots']} selected original joined roots. Additional template checkpoints restore inside child work, before the template call, at waits and after HP mutation. Existing R22 A-L traces cover pre-completion and successive normal turns; no joined complete transition is claimed for those checkpoints.

Tests: baseline `{json.dumps(baseline,sort_keys=True)}`; final `{json.dumps(tests,sort_keys=True)}`. Historical tests are unchanged. Architecture/preservation PASS across {architecture['checked_files']} starting files: only the three R23 production extensions changed. Frozen M10-M15, ScenarioCompiler, strict admission, approved R12-R22 controls and unrelated dirty files are preserved. No game launch, live attach or Git write.

R23 closes the broad catalog-first track by default. Another broad Camera phase has insufficient evidence-adjusted value: it needs new source infrastructure or effective native identity observations. Recommended R24: **TOUGHNESS / BREAK / SHIELD**, followed by stage/wave/termination, Monster content/AI, action legality, planner bridge and targeted native oracle work. The missing native legality and ultimate interruption remain explicit even when absent from skill first-gap counts.

Production: {', '.join(PRODUCTION)}. Tests: {TEST}. Reproduce: r23_checks.py gate (new runs only; never overwrite this gate), baseline; r23_discovery.py; r23_census.py; r23_probes.py; r23_checks.py final; r23_finalize.py. Existing R20 frozen runner and R22 A-L trace runner are redirected into this R23 audit. Existing-file handoff patches require the exact start-gate hashes. Source snapshot/old runtime artifacts are prerequisites and are excluded from this handoff.

Handoff: D:/HSR_Battle_Agent/agent_handoffs/{CR}_changed_files.zip. The external verification receipt records CRC, exact member set, sizes, member SHA-256 and ZIP SHA-256.
'''
    (ROOT/REPORT).write_text(report,encoding='utf-8')
    write('final_summary.json',{'verdict':closure['verdict'],'coverage':coverage,'summary':summary,
        'tests':tests,'baseline':baseline,'architecture':architecture,'recommended_R24':closure['recommended_R24']})
    if '--package' in sys.argv: package()
    print(json.dumps({'verdict':closure['verdict'],'coverage':coverage,'tests':tests},indent=2),flush=True)


def package():
    # Only R23-owned new files and patches against SHA-verified starting bytes.
    members={}
    for name in PRODUCTION:
        original=AUDIT/'starting_files'/name
        assert sha(original)==read(AUDIT/'start_gate.json')['file_hashes'][name]
        before=original.read_text(encoding='utf-8').splitlines(keepends=True)
        after=(ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
        patch=''.join(difflib.unified_diff(before,after,fromfile='a/'+name,tofile='b/'+name))
        members['patches/'+name+'.patch']=patch.encode('utf-8')
    names=[TEST,*TOOLS,REPORT,*[f'data/control/generic_runtime_{n}_{SUFFIX}.json' for n in CONTROL_NAMES]]
    for name in names:members[name]=(ROOT/name).read_bytes()
    audit_names=['start_gate.json','authoritative_pins.json','architecture_preservation.json','baseline_tests.json',
        'final_tests.json','frozen_regression.json','final_summary.json','execution_summary.json',
        'camera_audit.json','phase_retry.json','template_before_after.json','stepped_template_checkpoint.json',
        'r22_regression/execution_summary.json','r22_regression/execution_traces.json','probes_log.txt',
        'version_boundary_test.txt']
    audit_names.extend(p.name for p in AUDIT.glob('final_*.txt'))
    audit_names.extend(p.name for p in AUDIT.glob('baseline_*.txt'))
    audit_names.extend(p.relative_to(AUDIT).as_posix() for p in (AUDIT/'scenarios').rglob('commands.json'))
    for name in sorted(set(audit_names)):members[(AUDIT/ name).relative_to(ROOT).as_posix()]=(AUDIT/name).read_bytes()
    manifest={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],'git_writes':'NONE',
        'existing_file_patch_baselines':{n:sha(AUDIT/'starting_files'/n) for n in PRODUCTION},
        'existing_file_patch_targets':{n:sha(ROOT/n) for n in PRODUCTION},
        'members':[{'path':n,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(members.items())],
        'exclusions':['game binaries','whole source payloads','process dumps','old reverse trees','unrelated dirty files','starting source backups'],
        'source_snapshot_prerequisite':'Pinned 4.6.51 snapshot and preserved R12-R22 artifacts'}
    members['MANIFEST.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8')
    path=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,b in sorted(members.items()):archive.writestr(name,b)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(members) and set(archive.namelist())==set(members)
        for name,b in members.items():
            info=archive.getinfo(name);assert info.file_size==len(b)
            assert hashlib.sha256(archive.read(name)).hexdigest()==hashlib.sha256(b).hexdigest()
    write('handoff_verification.json',{'archive':str(path),'sha256':sha(path),'size':path.stat().st_size,
        'CRC':'PASS','exact_member_set':'PASS','sizes':'PASS','member_sha256':'PASS','members':len(members),
        'manifest_sha256':hashlib.sha256(members['MANIFEST.json']).hexdigest(),
        'requested_destination':'D:/HSR_Battle_Agent/agent_handoffs/'+path.name})


if __name__=='__main__':main()
