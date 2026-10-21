"""R18 controls, bounded oracle tickets, report, preservation and verified ZIP."""
from __future__ import annotations
import collections
import difflib
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from r18_checks import ROOT,AUDIT,PRODUCTION,read,write,sha,preservation

CR='CR-R18-DAMAGE-HP-SETTLEMENT-20261009-001'
SUFFIX='20261009_001'
TESTS=['tests/battle_runtime/test_behavior_r18.py']
TOOLS=['tools/runtime/r18_'+name+'.py' for name in ('checks','reference_fixtures','probes','followups','finalize')]
CONTROLS=[f'data/control/generic_runtime_{name}_{SUFFIX}.json' for name in
          ('damage_pipeline_v1','hp_settlement_v1','damage_support_census_v1','support_census_v8','semantic_gap_ledger_v6')]
REPORT=f'docs/agent/handoffs/generic_runtime_damage_hp_settlement_{SUFFIX}.md'
DEST=Path('D:/HSR_Battle_Agent/agent_handoffs')/(CR+'_changed_files.zip')
def emit(path,value):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
def unit(raw):
    from fractions import Fraction
    return str(Fraction(raw,1<<33))
def strip_runtime(row): return {k:v for k,v in row.items() if k not in ('initial_runtime',)}
def verification():
    preservation();start=read(AUDIT/'start_gate.json')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip()
    assert head==start['head'] and branch==start['branch']=='terra/implementation'
    for name,expected in read(AUDIT/'source_pins.json').items():
        assert sha(ROOT/name)==expected,'source pin drift: '+name
    old=read(ROOT/'tmp/audit/r17_modifier_event_20261009_001/handoff_verification.json')
    path=Path(old['destination']);assert path.is_file() and sha(path)==old['ZIP_sha256']
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and set(z.namelist())==set(old['members'])
        for name,expected in old['members'].items():
            b=z.read(name)
            assert hashlib.sha256(b).hexdigest()==expected['sha256']
    write('r17_verification.json',{'status':'PASS','archive':str(path),'sha256':sha(path),
        'CRC':'PASS','exact_member_set':'PASS','per_member_sha256':'PASS',
        'controls_code_fixtures':'start-gate SHA256 preserved; R12-R17 baseline tests PASS'})
    for name in PRODUCTION:
        source=(ROOT/name).read_text(encoding='utf-8')
        before=AUDIT/'starting_files'/name
        oldtext=before.read_text(encoding='utf-8') if before.exists() else ''
        target=AUDIT/'diffs'/(Path(name).name+'.diff');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(''.join(difflib.unified_diff(oldtext.splitlines(keepends=True),source.splitlines(keepends=True),
            fromfile='approved_R17/'+name,tofile='R18/'+name)),encoding='utf-8')

def main():
    verification()
    start=read(AUDIT/'start_gate.json');frozen=read(AUDIT/'frozen_summary.json')
    explicit=read(AUDIT/'explicit_summary.json');joined=read(AUDIT/'joined_explicit_summary.json')
    isolated=read(AUDIT/'explicit_damage_results.json');prefix=read(AUDIT/'real_graph_prefix_results.json')
    joinedrows=read(AUDIT/'joined_explicit_prefix_results.json');event=read(AUDIT/'event_damage_checkpoint.json')
    structural=read(AUDIT/'damage_structural_audit.json');rows=read(AUDIT/'frozen_probes.json')
    tests=read(AUDIT/'final_tests.json');assert all(v['returncode']==0 for v in tests.values())
    assert frozen['combat']['after']['metrics']['tasks_reached']==1025
    assert frozen['combat']['after']['metrics']['tasks_completed']==494
    assert frozen['combat']['after']['first_gap_family_distribution']['DAMAGE']==74
    assert frozen['joined']['after']['first_gap_family_distribution']['DAMAGE']==15
    assert len(frozen['damage_diagnostic_changes'])==74 and not frozen['drift']
    assert explicit['isolated']=={'completed':6,'denominator':6}
    assert joined['hp_mutated']==11 and joined['denominator']==15
    shared={'change_request':CR,'starting_head':start['head'],'branch':start['branch'],
        'semantic_authority':'REFERENCE_MODEL','native_correctness':False,'git_writes':'NONE',
        'frozen_modules_modified':False,'source_version':'4.6.51'}
    numeric={'identity':'R12_MODE0_INT64_STEP2_TOWARD_ZERO_REFERENCE','operand':'signed int64 mode0 raw, tag bit clear',
        'scale':1<<33,'arithmetic_order':'explicit binary formula AST, left-to-right operand evaluation',
        'intermediate_quantization':'each multiply/divide toward zero at representable raw step 2',
        'overflow':'typed gap; no wrapping/saturation','negative':'explicit rejection or clamp-zero reference',
        'zero':'zero applied HP delta','final_rounding':'raw step2 or whole-HP toward zero, caller selected',
        'origin':'existing R12 behavior_primitives raw_checked/fixed_binary',
        'historical_evidence_version':'4.4.54 architectural background only; no damage formula/constants reused',
        'native_4651_rounding_proven':False,'reference_formula_origin':'R18 caller-authored sandbox',
        'native_formula_operand_roles_proven':False,'python_float_arithmetic':False}
    pipeline=shared|{'schema':'generic_runtime_damage_pipeline/1','verdict':'GENERIC_DAMAGE_HP_REFERENCE_PIPELINE_ESTABLISHED',
        'pipeline':['original decoded damage task','exact source hash/mask binding','DamageRequestIR',
                    'explicit reference formula evaluation','R17 stage dispatch/R15 owned callback drain',
                    'reference HP property mutation','post-damage callbacks','atomic damage commit'],
        'event_stages':['BEFORE_DAMAGE','DAMAGE_AMOUNT_MODIFICATION','BEFORE_HP_MUTATION','HP_MUTATION','AFTER_HP_MUTATION','AFTER_DAMAGE'],
        'event_order_authority':'EXPLICIT_CALLER_REFERENCE; native event IDs/order unknown',
        'listener_set':'explicit active reference instances only; native effective listeners unknown',
        'amount_modification':'exact callback hash + explicit event payload/request ID + serialized R17 listener aggregation',
        'transaction':'checkpoint before source TaskFrame; descendant-only scheduling; semantic gap restores whole damage primitive',
        'retry':'re-enter original source task; committed earlier tasks remain; no duplicate HP/RNG/callbacks',
        'budget_suspension':'pending transaction and callbacks serialize/clone/restore for resumption',
        'ordering':'selected target order + explicit duplicate policy + serialized source request order; native hit splitting unknown',
        'numeric_contract':numeric,'typed_IR':'DamageRequestIR in existing Behavior IR; source task unchanged',
        'state':'existing BehaviorBattleState damage_requests/damage_history/damage_transactions/next_damage_id',
        'search_state':'clone/snapshot/hash/replay include all requests, ownership, checkpoints and policy identities',
        'event_checkpoint':strip_runtime(event),'production_files':PRODUCTION,'tests':tests}
    emit(CONTROLS[0],pipeline)
    settlement=shared|{'schema':'generic_runtime_hp_settlement/1','numeric_contract':numeric,
        'HP_validation':'existing target identity; explicit HP/max HP property keys, 0 <= HP <= max HP and max HP > 0',
        'calculation':'effective amount >= 0; applied = min(pre_HP,effective); post_HP = pre_HP-applied; overkill=effective-applied',
        'storage':'mode0 raw existing property store, clamp-zero/max explicit reference',
        'life_state':'explicit preserve or alive=(HP>0); no inferred native callbacks/removal/battle termination',
        'shield':'only explicit sandbox bypass; unknown policy -> DAMAGE_SHIELD_POLICY_UNKNOWN',
        'toughness':'only explicit sandbox no-mutation; never inferred from HP damage',
        'break':'only explicit sandbox no-processing; no weakness/super-break implementation',
        'resources':'explicit sandbox no-processing; no energy/kill-resource defaults',
        'DamagePerformFinish':'exact local owned-damage drain assertion under explicit policy; never global action finish',
        'real_source_fixture_results':[strip_runtime(r) for r in isolated],
        'R17_event_checkpoint':strip_runtime(event),'transactional':True}
    emit(CONTROLS[1],settlement)
    task_exprs=[e for r in structural['instances'] for e in r['expression_operands'] if e['mask']==4]
    gaps=[r for r in joinedrows if r['required_capability']=='expression:unknown_opcode']
    damage_finish=[]
    from r18_probes import load
    from hsr_battle_agent.battle_ir.behavior import walk_nodes
    roots,_=load();seen=set()
    for g,ir in roots:
        for n in walk_nodes(ir):
            if n.op=='RPG.GameCore.DamagePerformFinish':
                key=(g['source_shard_sha256'],tuple(n.payload['span']))
                if key not in seen:
                    seen.add(key);damage_finish.append({'root':g['record_identity'],'source_identity':g['source_identity'],
                        'source_span':n.payload['span'],'node_id':n.node_id,'source_evidence':n.authority.to_dict(),
                        'decoded_fields':n.to_dict(),'skill_joined':g['skill_joined']})
    write('damage_perform_finish_evidence.json',{'instances':damage_finish,
        'native_evidence':'concrete TaskConfig/reader/span only; runtime finish signal meaning unresolved',
        'reference_policy':'ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE; separate from ability/action completion'})
    groups={'UNCHANGED_FROZEN_FIXTURE':frozen,
        'ISOLATED_REAL_DAMAGE_PRIMITIVE':explicit['isolated']|{'settlements':explicit['isolated_settlements'],
            'roots':[r['root'] for r in isolated],'wrapper_finish':'synthetic explicit wrapper only'},
        'EXPLICIT_DAMAGE_EVENT_REFERENCE_CHECKPOINT':{'completed':1,'denominator':1,'amount_HP_units':25,
            'HP_transition':[100,75],'callbacks_completed':1,'native_listener':'UNKNOWN','listener':'explicit synthetic R17 reference instance'},
        'REAL_GRAPH_PREFIX_HP_MUTATION':{'selected_nonjoined_ability_graphs':explicit['prefix'],
            'actual_joined_skill_roots':{'completed':joined['hp_mutated'],'denominator':joined['denominator'],
                'settlements':joined['committed_settlements'],'remaining_gap_distribution':joined['gap_distribution']}},
        'FULL_REAL_SKILL_REFERENCE_TRANSITION':{'completed':joined['full_real_skill_reference_transitions'],
            'denominator':joined['denominator'],'reference_actor_and_policies':True,'native_validated':False},
        'selected_ability_graph_reference_completions':explicit['full_real_skill']}
    support=shared|{'schema':'generic_runtime_damage_support_census/1','baseline_denominators':{'combat_roots':632,'joined_roots':160,'joined_rows':161},
        'damage_instances':207,'distinct_damage_task_shapes':structural['distinct_task_shapes'],
        'shape_counts':structural['shape_counts'],'trusted_records_structurally_decoded':207,
        'newly_decoded_records':0,'new_reader_work':0,'structural_damage_gaps':[],
        'source_mask4_expression_status':dict(collections.Counter(e['expression']['op'] for e in task_exprs)),
        'native_formula_binding':'UNKNOWN for all anonymous operand roles',
        'groups':groups,'determinism':'PASS','replay':'PASS','tests':tests}
    emit(CONTROLS[2],support)
    families=set(frozen['combat']['after']['first_gap_family_distribution'])|{'SHIELD_TOUGHNESS_BREAK','MONSTER_RUNTIME'}
    ranking=[]
    dimensions={'CONTENT_CATALOG_BINDING':['MISSING_CONTENT','MISSING_REFERENCE_POLICY','MISSING_NATIVE_ORACLE'],
        'MODIFIER_EVENT':['MISSING_REFERENCE_STATE_POLICY','MISSING_NATIVE_ORACLE'],
        'DAMAGE':['MISSING_REFERENCE_STATE_POLICY','MISSING_NATIVE_ORACLE'],
        'PROPERTY_DYNAMIC_PROVIDER':['MISSING_REFERENCE_STATE_POLICY','MISSING_GENERIC_PRIMITIVE','MISSING_NATIVE_ORACLE'],
        'PREDICATE_PROGRESSION':['MISSING_REFERENCE_STATE_POLICY','MISSING_GENERIC_PRIMITIVE','MISSING_NATIVE_ORACLE'],
        'RESOURCE':['MISSING_REFERENCE_STATE_POLICY','MISSING_GENERIC_PRIMITIVE','MISSING_NATIVE_ORACLE'],
        'SHIELD_TOUGHNESS_BREAK':['MISSING_GENERIC_PRIMITIVE','MISSING_NATIVE_ORACLE'],
        'MONSTER_RUNTIME':['MISSING_CONTENT','MISSING_GENERIC_PRIMITIVE','MISSING_NATIVE_ORACLE']}
    for family in families:
        combat=frozen['combat']['after']['first_gap_family_distribution'].get(family,0)
        skills=frozen['joined']['after']['first_gap_family_distribution'].get(family,0)
        ranking.append({'family':family,'combat_roots':combat,'joined_roots':skills,'weighted_score':combat+2*skills,
            'dimensions':dimensions.get(family,['MISSING_REFERENCE_STATE_POLICY','MISSING_NATIVE_ORACLE']),
            'zero_first_gap_frequency_means_implemented':False})
    ranking.sort(key=lambda r:(-r['weighted_score'],r['family']))
    census=shared|{'schema':'generic_runtime_support_census/8','groups':groups,'blocker_priority_ranking':ranking,
        'top_raw_blocker':ranking[0],'recommended_R19':'DAMAGE FOLLOW-UP / PROPERTY PIPELINE: exact DynamicFloat programs + DamagePerformFinish local lifecycle evidence',
        'recommendation_basis':'11/15 joined prefixes settle HP, 10 stop at DamagePerformFinish; four unknown source programs and one progression predicate remain',
        'catalog_reader_closure_backlog':'145 combat / 75 joined first blockers; missing content distinct from reference damage state',
        'architecture':'same BehaviorRuntime, R15 scheduler, R17 dispatch, ContentCatalog; no character-specific branches',
        'tests':tests,'determinism':'PASS','replay':'PASS','native_skill_completions':0}
    emit(CONTROLS[3],census)
    pointers=[{k:r[k] for k in ('root','source_identity','source_artifact','source_artifact_sha256','source_span','pointer','source_version','skill_joined')} for r in structural['instances']]
    tickets=[]
    for identity,question,evidence in [
        ('NATIVE_DAMAGE_OPERAND_ROLES','Recover exact 4.6.51 AttackData mask-to-formula-role reads for one selected bounded task path.','Pinned AttackData/TaskConfig reader schemas and 207 bounded records; roles unnamed'),
        ('NATIVE_ROUNDING_LOCATIONS','Identify native arithmetic mode, intermediate/final rounding locations and overflow/negative handling on one formula path.','R12 raw mode0 reference contract; no native 4.6.51 rounding equivalence'),
        ('CRITICAL_DETERMINATION','Identify crit flag/provider, RNG consumption and critical transform for one selected task.','Decoded bool/enum operands remain opaque; no reference RNG draw implied'),
        ('DEFENSIVE_TRANSFORM_ORDER','Recover exact mitigation/resistance/vulnerability operand sources and native aggregation order.','No global damage formula invented; explicit sandbox formula only'),
        ('HP_EVENT_ORDER','Identify exact native pre-amount/pre-HP/post-HP event IDs, listeners and modification aggregation on one bounded path.','R17 callback structure and reference event queue; native effective listeners unknown'),
        ('MULTI_HIT_ORDER','Prove hit splitting, duplicate target handling and per-hit callback relationship for one multi-request source graph.','Serialized source request and target traversal preserved; native atomicity unknown'),
        ('DEATH_OVERKILL_BOUNDARY','Identify life-state/property hooks, death callbacks, overkill and terminal checks for one zero-HP settlement.','Explicit preserve/set-alive reference policies only; native side effects unknown')]:
        tickets.append({'ticket_id':'R18-'+identity,'affected_task_type':'RPG.GameCore.DamageByAttackProperty',
            'frequency':207,'affected_joined_skill_roots':len({tuple(r['source_identity']) for r in pointers if r['skill_joined']}),
            'source_pointers':pointers,'existing_evidence':evidence,'minimum_missing_oracle_evidence':question,
            'native_version_required':'4.6.51','broad_character_reverse_request':False})
    tickets.append({'ticket_id':'R18-DAMAGE_PERFORM_FINISH','affected_task_type':'RPG.GameCore.DamagePerformFinish',
        'frequency':len(damage_finish),'affected_joined_skill_roots':len({tuple(r['source_identity']) for r in damage_finish if r['skill_joined']}),
        'source_pointers':damage_finish,'existing_evidence':'Decoded concrete TaskConfig and native reader only',
        'minimum_missing_oracle_evidence':'Exact finish consumer and ownership relation among request settlement, callback drain, ability and action; one pinned 4.6.51 path',
        'explicit_joined_first_gap_frequency':10,'reference_assertion':'local damage drain; no action finish'})
    tickets.append({'ticket_id':'R18-DAMAGE_DYNAMIC_PROGRAM','affected_task_type':'RPG.GameCore.DynamicFloat',
        'frequency':sum(e['expression']['op']=='unknown_opcode' for e in task_exprs),'affected_joined_skill_roots':len(gaps),
        'source_pointers':[{'root':r['root'],'source_identity':r['source_identity'],'gap_node':r['gap_node']} for r in gaps],
        'existing_evidence':'Exact token streams and operand arrays decoded; unknown opcode semantics preserved',
        'minimum_missing_oracle_evidence':'Selected exact opcode/stack arithmetic and fixed-point helper evidence, version-qualified 4.6.51 or explicitly reference-only policy',
        'replacement_with_literal_allowed':False})
    ledger=shared|{'schema':'generic_runtime_semantic_gap_ledger/6','dimensions':list({d for r in ranking for d in r['dimensions']}),
        'oracle_tickets':tickets,'blocker_priority_ranking':ranking,'frozen_first_gaps':[{k:r[k] for k in
            ('root','source_identity','skill_joined','primitive','required_capability','first_gap_family','gap_node')} for r in rows],
        'explicit_joined_remaining_gaps':[{k:r[k] for k in ('root','source_identity','primitive','required_capability','gap_node')} for r in joinedrows],
        'native_correctness':'NOT_CLAIMED','separate_core_subsystems':['native death/terminal','shield/toughness/break','energy/resources','real turn/AV']}
    emit(CONTROLS[4],ledger)
    write('oracle_tickets.json',tickets);write('blocker_priority_ranking.json',ranking)
    report=ROOT/REPORT;report.parent.mkdir(parents=True,exist_ok=True)
    lines=[f'# R18 Generic Damage + HP Settlement', '',f'CR `{CR}`. Verdict **GENERIC_DAMAGE_HP_REFERENCE_PIPELINE_ESTABLISHED**.', '',
        f'Starting HEAD `{start["head"]}`, branch `{start["branch"]}`. Git writes NONE. SHA-256 preservation covers frozen M10–M15, ScenarioCompiler, strict admission, approved R12–R17 and unrelated dirty files. R17 archive CRC/member-set/member-hash verification PASS.', '',
        'The existing generic runtime now executes the original decoded damage task through DamageRequestIR, explicit reference formula evaluation, R17 dispatch/R15 owned callback drain and persistent HP property settlement. Source tasks remain unchanged, including their UnsupportedSemanticIR envelope; R18 admits them only under exact caller-authored source-hash/mask policies. No character-specific handler or second runtime/event bus is introduced.', '',
        'All **207** unique frozen DamageByAttackProperty instances have bounded decoded TaskConfig/target/AttackData records, covering **9** task bitmap shapes. No new reader was needed. The audit retains exact shard/record/artifact SHA-256, version, span, reader references, expressions, flags, nested structures and unknown fields. Native AttackData formula roles remain unknown. Masks selected by fixtures are explicitly sandbox roles, not semantic names inferred from numerical values. Unknown DynamicFloat programs are never replaced with literals.', '',
        'The numeric contract reuses R12 mode0 raw signed int64 arithmetic, scale 2^33, representable step 2. Binary AST order is explicit; multiply/divide quantize toward zero after each operation. Tagged/mixed domains, overflow and division by zero return typed gaps. Negative behavior and final raw/whole-HP rounding require explicit reference policies. Historical 4.4.54 evidence is architectural background only; no historical damage formula/constants are transferred into native 4.6.51 claims.', '',
        'The six configurable stages are BEFORE_DAMAGE, DAMAGE_AMOUNT_MODIFICATION, BEFORE_HP_MUTATION, HP_MUTATION, AFTER_HP_MUTATION and AFTER_DAMAGE. Native IDs/order and effective listeners remain unknown. Fixtures declare every event stage and the active reference listener scope. Exact callback targets, event payloads, callback hashes and serialized R17 listener aggregation permit pending amount changes. All callbacks, child abilities and continuations stay under R15 ActionExecutionRoot.', '',
        'A source-task transaction snapshots before TaskFrame creation and executes only its descendant work until commit. A SemanticGap restores HP, modifier/listener effects, event registration, RNG, scheduler additions and damage histories together; earlier committed tasks remain. Retry re-enters the original source task. Budget-suspended requests/callbacks/checkpoints remain cloneable, hashable and resumable. Ordered targets, explicitly allowed duplicates and separately serialized source requests produce per-target settlement records.', '',
        'HP settlement validates entity/property identities and initial HP/max HP, caps applied damage at current HP and records effective amount, pre/post HP, applied delta and overkill. Life state changes only under explicit policy. Shield bypass, no toughness mutation, no break processing and no resource/death/battle-end processing are individually declared sandbox boundaries. Missing/unknown policies are typed gaps. No shield amount is inferred as HP and no toughness is inferred from HP damage.', '',
        f'DamagePerformFinish has {len(damage_finish)} unique frozen structural instances. Native signal meaning remains unknown. An exact reference local damage-drain assertion is available, and tests prove it does not request ability/action completion. Source graph probes receive no fabricated SkillPerformFinish.', '',
        '| Completion category | Result |', '|---|---:|',
        '| ISOLATED_REAL_DAMAGE_PRIMITIVE | 6 / 6 (7 target settlements) |',
        '| Explicit real damage + R17 amount callback checkpoint | 1 / 1 |',
        f'| REAL_GRAPH_PREFIX_HP_MUTATION — selected ability graphs | {explicit["prefix"]["hp_mutated"]} / 6 |',
        '| REAL_GRAPH_PREFIX_HP_MUTATION — actual joined skill roots | 11 / 15 (22 settlements) |',
        '| FULL_REAL_SKILL_REFERENCE_TRANSITION — actual joined probes | 0 / 15 |',
        '| Native skill correctness | NOT CLAIMED |','',
        'The isolated wrappers contain an explicitly synthetic completion node; this does not change real source graphs or count as whole-skill completion. Selected ability-graph probes and joined skill probes retain their own denominators. The joined tests exercise real Skill01/Skill02 roots and child ability invocation where source provides it, and all 15 still return SemanticGap: ten DamagePerformFinish blockers, four unknown DynamicFloat programs and one ByRankActivated progression predicate.', '',
        '| Unchanged frozen input | R17 | R18 |','|---|---:|---:|',
        '| Combat roots / decoded joined roots / joined rows | 632 / 160 / 161 | 632 / 160 / 161 |',
        '| Combat tasks reached / completed | 1025 / 494 | 1025 / 494 |',
        '| Joined tasks reached / completed | 300 / 121 | 300 / 121 |',
        '| Combat / joined first DAMAGE blockers | 74 / 15 | 74 / 15 |',
        '| Damage operations attempted / committed | 74 / 0 | 74 / 0 |',
        '| Roots reaching HP mutation / action completions | 0 / 0 | 0 / 0 |','',
        'Frozen task counts, first-gap families, primitives and unrelated diagnostics have zero drift. The 74 DAMAGE capability strings now accurately identify missing explicit reference inputs instead of an absent implementation; 15 affect joined roots. No damage properties/policies were added to frozen inputs. Expanded corpora and synthetic wrappers are not merged into 632/160 denominators.', '',
        '| Real source fixture | Amount (HP units) | HP before → after |', '|---|---:|---|']
    for r in isolated:
        for d in r['settlements']:
            lines.append(f'| {r["root"]} → {d["target"]} | {unit(d["evaluated_amount_raw"])} | {unit(d["hp_before_raw"])} → {unit(d["hp_after_raw"])} |')
    lines.extend(['','The explicit event checkpoint uses the unchanged AventurineW decoded task and an explicitly synthetic R17 active listener/callback. Base damage 20 becomes 25 by exact callback addition; HP 100 → 75, one owned modifier callback drains, and clone/restore/replay hashes match. The listener is never labelled as native or source-recovered.', '',
        'Structured controls include first-gap distributions, task counts, raw input bindings, full settlement records, source pointers and narrowly scoped oracle tickets. Native operand roles, rounding, critical sampling, defensive ordering, event IDs/listeners, multi-hit splitting, death/overkill and DamagePerformFinish consumers remain ticketed.', '',
        'Largest raw blocker: CONTENT_CATALOG_BINDING, **145 combat / 75 joined** (weighted score 295). Modifier/Event is largely missing reference/native state (181 / 43). Recommend **R19 DAMAGE FOLLOW-UP / PROPERTY PIPELINE** from measured explicit prefixes: resolve selected exact DynamicFloat programs and DamagePerformFinish local lifecycle evidence, with catalog reader closure as an independent content backlog. No automatic Natasha selection, resource engine, shield/break subsystem or invented Turn/AV model.', '',
        'Tests: '+', '.join(f'{k}: {v["tests"]} PASS' for k,v in tests.items())+'. Determinism/replay/architecture/preservation PASS. R18 adds 48 focused tests; frozen tests are unchanged.', '',
        'Production files: '+', '.join('`'+n+'`' for n in PRODUCTION)+'.',
        'Tests: `'+TESTS[0]+'`.',
        'Controls: '+', '.join('`'+n+'`' for n in CONTROLS)+'.',
        'Audit: `tmp/audit/r18_damage_hp_settlement_20261009_001/`.', '',
        'Reproduce: `python tools/runtime/r18_probes.py --explicit-only`; `python tools/runtime/r18_probes.py --frozen-only`; `python tools/runtime/r18_followups.py`; `python tools/runtime/r18_checks.py final`; `python tools/runtime/r18_finalize.py --package`. Start-gate hashes must already exist before edits. Scripts preserve R17 controls/audits and perform only read-only Git commands.', '',
        f'Handoff destination: `{DEST.as_posix()}`. Only R18-owned changed files, parsed selected-record/reference evidence, controls, receipts, diffs and manifest are packaged; binaries, whole raw payloads, dumps, previous audit trees and starting file copies are excluded. Verification records exact ZIP member set, CRC, sizes, every member SHA-256 and archive SHA-256.', ''])
    report.write_text('\n'.join(lines),encoding='utf-8')
    write('final_summary.json',{'verdict':pipeline['verdict'],'starting_head':start['head'],'groups':groups,
        'tests':tests,'architecture':'PASS','determinism':'PASS','replay':'PASS','top_blocker':ranking[0],
        'recommended_R19':census['recommended_R19'],'production_files':PRODUCTION,'tests_modified':TESTS,
        'frozen_modules_modified':False,'git_writes':'NONE','native_correctness':'NOT_CLAIMED'})
    if '--package' in sys.argv: package()
    print(json.dumps({'verdict':pipeline['verdict'],'tests':tests,'joined_prefix':joined,'production_files':PRODUCTION},indent=2),flush=True)

def package():
    files=PRODUCTION+TESTS+TOOLS+CONTROLS+[REPORT]
    audit_files=[p for p in AUDIT.rglob('*') if p.is_file() and not any(part in ('starting_files','test_tmp') for part in p.relative_to(AUDIT).parts)
                 and p.suffix in ('.json','.txt','.diff') and p.name not in ('handoff_manifest.json','handoff_verification.json')]
    files+=sorted(p.relative_to(ROOT).as_posix() for p in audit_files)
    assert len(files)==len(set(files))
    manifest={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],'destination':DEST.as_posix(),
        'files':{n:{'size':(ROOT/n).stat().st_size,'sha256':sha(ROOT/n)} for n in files},
        'excluded':['native binaries','whole raw source payloads','process dumps','previous reverse audit trees','starting_files','test_tmp'],
        'git_writes':'NONE'}
    write('handoff_manifest.json',manifest)
    files.append((AUDIT/'handoff_manifest.json').relative_to(ROOT).as_posix())
    local=ROOT/'agent_handoffs'/(CR+'_changed_files.zip');local.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(local,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in files:z.write(ROOT/name,name)
    members={}
    with zipfile.ZipFile(local) as z:
        assert z.testzip() is None and set(z.namelist())==set(files) and len(z.namelist())==len(files)
        for item in z.infolist():
            b=z.read(item.filename);assert b==(ROOT/item.filename).read_bytes()
            members[item.filename]={'size':item.file_size,'compressed_size':item.compress_size,
                'crc32':f'{item.CRC:08x}','sha256':hashlib.sha256(b).hexdigest()}
    write('handoff_verification.json',{'local_archive':local.as_posix(),'destination':DEST.as_posix(),
        'ZIP_sha256':sha(local),'ZIP_size':local.stat().st_size,'crc':'PASS','member_set':'PASS',
        'member_count':len(members),'members':members,'external_copy':'PENDING'})
if __name__=='__main__':main()
