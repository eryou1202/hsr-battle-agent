"""R20 controls, whole-battle handoff and exact-member archive verification."""
from __future__ import annotations
import ast
import collections
import difflib
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r20_checks import AUDIT,read,write,sha,OWNED_EXISTING
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes
from hsr_battle_agent.battle_runtime.actor_binding import AUTHORITIES
from hsr_battle_agent.battle_runtime.resource_engine import DOMAINS,OPERATIONS

CR='CR-R20-ACTOR-STATE-RESOURCE-PROGRESSION-20261010-001'
DEST=Path('D:/HSR_Battle_Agent/agent_handoffs')/(CR+'_changed_files.zip')
REPORT=ROOT/'docs/agent/handoffs/generic_runtime_actor_resource_progression_20261010_001.md'
CONTROL_NAMES=['actor_state_binding_v1','resource_engine_v1','progression_census_v1','support_census_v10','semantic_gap_ledger_v8']
PRODUCTION=OWNED_EXISTING+['src/hsr_battle_agent/battle_runtime/actor_binding.py','src/hsr_battle_agent/battle_runtime/resource_engine.py']

def control(name): return ROOT/'data/control'/('generic_runtime_'+name+'_20261010_001.json')
def put(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def verify():
    gate=read(AUDIT/'start_gate.json');changed=[]
    for name,h in gate['file_hashes'].items():
        if not (ROOT/name).is_file() or sha(ROOT/name)!=h:changed.append(name)
    unexpected=[n for n in changed if n not in OWNED_EXISTING and not n.startswith('tools/runtime/r20_')]
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()
    assert git('rev-parse','HEAD')==gate['head'] and git('branch','--show-current')==gate['branch']
    assert git('diff','--cached','--name-status')==gate['staged'] and not unexpected
    # The source authority must not silently change during the phase.
    for name,h in read(AUDIT/'source_pins.json').items():assert sha(ROOT/name)==h
    findings=[]
    for name in PRODUCTION:
        source=(ROOT/name).read_text(encoding='utf-8');tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,(ast.If,ast.IfExp,ast.Compare)):
                text=ast.get_source_segment(source,node.test if isinstance(node,(ast.If,ast.IfExp)) else node) or ''
                if any(x in text for x in ('Natasha','110502','AvatarID','Skill02','MAvatar_')):findings.append({'file':name,'line':node.lineno})
    assert not findings
    write('preservation.json',{'checked_files':len(gate['file_hashes']),'changed_starting_files':changed,
          'unexpected_changes':unexpected,'frozen_modules_modified':False,'git_writes':'NONE','staged_unchanged':True})
    write('architecture.json',{'status':'PASS','forbidden_character_dispatch':findings,'second_battle_state':False,
        'second_scenario_compiler':False,'properties':'R19 evaluator','events':'R17 dispatch/R15 owned event queues',
        'atomicity':'existing R18 checkpoint stack reused for RESOURCE transactions; no second transaction scheduler',
        'storage':'existing entities/properties/progression/actor_resources/team_resources; opt-in R20 mechanics',
        'frozen_M10_M15_modified':False,'git_writes':'NONE','native_correctness':False})
    write('state_api_inventory.json',{
        'state':'existing BehaviorBattleState, schema evidence_aware_behavior_state/1; unchanged file',
        'entity_identity':'entities keyed by caller entity ID; exact static content identity bound separately',
        'existing_stores':['entities','properties','actor_resources','team_resources','progression','modifiers',
            'modifier_definitions','dynamic_values','target_context','scheduler','pending_events','rng','mechanics'],
        'properties':'R19 BASE/EFFECTIVE/MODIFIER/SNAPSHOT/ABILITY_DYNAMIC/MODIFIER_LOCAL/CONTEXT source evaluator',
        'catalog':'R16 ContentCatalog exact directory/source/graph hashes; executable_abilities and modifier_definitions reused',
        'modifier_events':'R17 explicit instances/contributions/listeners; definition existence is not activation',
        'scheduler':'R15 ActionExecutionRoot, TaskFrame, owned event/callback/continuation queues',
        'transactions':'existing R18 damage_transactions checkpoint stack + within_transaction ancestry, now also RESOURCE tagged checkpoints',
        'APIs':['step','legal_actions (local reference only)','run_until_decision','start_action','run_ready',
            'run_until_action_complete','clone','snapshot','from_snapshot','stable_hash','replay','bind_actor'],
        'frozen_static_entry':'existing ScenarioCompiler and 4.4.54 ContentDatabase inspected and unchanged',
        'duplicate_subsystems_created':False})

def finalize():
    verify();gate=read(AUDIT/'start_gate.json');tests=read(AUDIT/'final_tests.json')
    assert all(t['returncode']==0 for t in tests.values())
    import unittest
    sys.path.insert(0,str(ROOT))
    from tests.battle_runtime.test_behavior_r20 import R20Tests
    focused_count=unittest.defaultTestLoader.loadTestsFromTestCase(R20Tests).countTestCases()
    assert tests['R12_R20']['tests']==265+focused_count and tests['battle_runtime_FAST_UNIT']['tests']==459+focused_count
    cohort=read(AUDIT/'actor_cohort_summary.json');rows=read(AUDIT/'actor_cohort_results.json')
    r19=read(AUDIT/'r19_damage_regression.json');frozen=read(AUDIT/'frozen_regression.json')
    resources=read(AUDIT/'resource_instruction_census.json');progress=read(AUDIT/'progression_instruction_census.json')
    follow=read(AUDIT/'resource_followup_summary.json');native=read(AUDIT/'modify_sp_native_boundary.json')
    replay=read(AUDIT/'original_graph_replay.json');assert replay['status']=='PASS' and len(replay['roots'])==cohort['real_graph_resource_prefix_roots']
    current_hashes={tuple(r['source_identity']):r['final_battle_state_hash'] for r in rows}
    assert all(r['final_state_hash']==current_hashes[tuple(r['source_identity'])] for r in replay['roots'])
    assert cohort['initialized_actor_contexts']==83 and cohort['real_graph_resource_prefix_roots']>=7
    assert cohort['full_joined_skill_transitions']==0 and cohort['actions_reference_complete']==3
    assert resources['counts']['RPG.GameCore.ModifySPNew']==39
    assert frozen['after']['combat']['metrics']['tasks_reached']==1025 and frozen['after']['combat']['metrics']['tasks_completed']==494
    assert frozen['after']['joined']['metrics']['tasks_reached']==300 and frozen['after']['joined']['metrics']['tasks_completed']==121
    completed=[r['root'] for r in rows if r['status']=='ACTION_REFERENCE_COMPLETE']
    capabilities={
        'Actor state initialization':{'status':'REFERENCE_EXECUTABLE','oracle':'NATIVE_ORACLE_PENDING','evidence':'pinned identity + explicit scenario/provenance; native legality unknown'},
        'Damage/HP':{'status':'REFERENCE_EXECUTABLE','oracle':'NATIVE_ORACLE_PENDING','evidence':'R18/R19 retained; reference formula/settlement/lifecycle'},
        'Heal':{'status':'REFERENCE_PARTIAL','oracle':'NATIVE_ORACLE_PENDING','evidence':'existing FormulaType2; synthetic heal/resource pair passes; original real heal mapping/context still incomplete'},
        'Modifier/Event':{'status':'REFERENCE_EXECUTABLE','oracle':'NATIVE_ORACLE_PENDING','evidence':'R17 instances/listeners with R15 ownership; real resource callback primitives execute in explicit listeners'},
        'Resources/Energy/SP':{'status':'REFERENCE_EXECUTABLE','oracle':'NATIVE_ORACLE_PENDING','evidence':'explicit resource domains/settlement; native identity, formula, caps and event semantics unresolved'},
        'Progression':{'status':'REFERENCE_EXECUTABLE','oracle':'NATIVE_ORACLE_PENDING','evidence':'explicit activation booleans + existing R19 keyed rank threshold'},
        'Shield':{'status':'NOT_BOUND','evidence':'no full subsystem; explicit sandbox damage bypass retained'},
        'Toughness/Break':{'status':'NOT_BOUND','evidence':'no settlement/break engine'},
        'True Turn/AV':{'status':'NOT_BOUND','evidence':'R15 logical callbacks do not establish native initiative/turn ownership'},
        'Action legality':{'status':'REFERENCE_PARTIAL','oracle':'NATIVE_ORACLE_PENDING','evidence':'R15 local caller-bound actions + explicit source cost transaction; no native legal_actions or M15 admission change'},
        'Monster AI':{'status':'STRUCTURE_ONLY','evidence':'no independently bound real opponent decision engine'},
        'Stage/wave/mode':{'status':'NOT_BOUND','evidence':'no independent full battle stage progression'},
        'Planner integration':{'status':'REFERENCE_PARTIAL','evidence':'deterministic reset/step/clone/snapshot/hash/replay affordances; full battle policy/search integration not established'}}
    ranking=[
        {'rank':1,'phase':'R21 TRUE BATTLE TURN / AV: bounded evidence discovery before implementation',
         'impact':'very high; action ownership, initiative, scheduling and planner horizon are missing',
         'source_availability':'existing scheduler/static evidence only; exact effective rules not bound',
         'reuse':'high across every actor/action','blocker_frequency':'not measurable from current first-gap corpus; missing whole subsystem',
         'end_to_end_value':'very high','cost':'medium discovery, high implementation','native_uncertainty':'high',
         'stop_boundary':'no native-like AV formula/order inferred in R20'},
        {'rank':2,'phase':'CONTENT CATALOG / CHARACTER ROOT COMPLETION','impact':'high prefix/full reference closure',
         'source_availability':'known directory entries/reader gaps','reuse':'high','blocker_frequency':'145 combat/75 joined frozen; 30 R20 catalog-family first gaps',
         'end_to_end_value':'high reference graph closure','cost':'medium','native_uncertainty':'medium'},
        {'rank':3,'phase':'TOUGHNESS / BREAK / SHIELD','impact':'very high combat state reconstruction',
         'source_availability':'partial existing structural/native records','reuse':'high','blocker_frequency':'unvisited; not equivalent to zero gaps',
         'end_to_end_value':'high','cost':'high','native_uncertainty':'high'},
        {'rank':4,'phase':'MONSTER BEHAVIOR BINDING','impact':'high opponent simulation',
         'source_availability':'structural inventory; selected behavior corpus needed','reuse':'high','blocker_frequency':'unmeasured missing subsystem',
         'end_to_end_value':'high','cost':'high','native_uncertainty':'high'},
        {'rank':5,'phase':'ACTION LEGALITY / COST','impact':'high planning admissibility',
         'source_availability':'partial source costs/resource paths, effective gates unknown','reuse':'high','blocker_frequency':'unbound beyond local actions',
         'end_to_end_value':'high with turn engine','cost':'medium/high','native_uncertainty':'high'},
        {'rank':6,'phase':'TARGETED NATIVE ORACLE','impact':'exact native validation',
         'source_availability':'bounded existing joins only; new effective evidence needed','reuse':'targeted',
         'blocker_frequency':'overlaps every native semantic capability','end_to_end_value':'high accuracy, little new whole-battle structure',
         'cost':'externally blocked','native_uncertainty':'high'}]
    ranking[1]['blocker_frequency']=str(cohort['first_gap_family_distribution'].get('CONTENT_CATALOG_BINDING',0))+' R20; 145 combat/75 joined frozen'
    versions={'REAL_RUNTIME_RESEARCH_BASELINE':'4.6.51 pinned snapshot','PRODUCT_BASELINE':'4.4.54 frozen ContentDatabase',
        'binding_version':'4.6.51','shared_types':'generic state contracts only',
        'pinned_manifest':'b702762039368badf25c1e2c0a3a4eea79d7b8ada79c6ce98a448492a97378ec',
        'exact_values_bound':'Avatar identity and decoded record fields; scenario level/promotion/rank/HP/resources remain explicit inputs',
        'promotion_skill_tree_availability':'same-version existing selected decoded promotion/skill-tree rows are source evidence; native activation/initialization still unknown',
        'cross_version_static_merge':False,'missing_compatible_source':'VERSIONED_CONTENT_GAP',
        'relabelled_source_test':'manifest version and source shard pin reject relabelling',
        'native_initialized_actor_state':'EFFECTIVE_RUNTIME_UNKNOWN'}
    write('version_compatibility.json',versions);write('whole_battle_capability_matrix.json',capabilities)
    write('next_phase_priority.json',ranking)
    baseline={'combat_roots':632,'joined_decoded_roots':160,'joined_skill_rows':161,
        'combat_reached_completed':[1025,494],'joined_reached_completed':[300,121],
        'hp_commits':0,'complete_joined_skill_transitions':0,'state_hash_drift':0}
    common={'change_request':CR,'starting_head':gate['head'],'branch':gate['branch'],'source_version':'4.6.51',
        'semantic_authority':'REFERENCE_MODEL','native_correctness':False,'git_writes':'NONE','frozen_M10_M15_modified':False,
        'tests':tests,'verdict':'GENERIC_ACTOR_RESOURCE_REFERENCE_ENGINE_ESTABLISHED'}
    actor=common|{'schema':'generic_runtime_actor_state_binding/1','authority_domains':list(AUTHORITIES),
        'field_presence':'absent / explicit zero / explicit false / unknown are separate; known null rejects',
        'constructor_validity_is_native_legality':False,'contract':'ActorRuntimeBinding -> BehaviorRuntime.bind_actor -> existing BehaviorBattleState',
        'identity':'exact pinned JSON record identity pointer + version manifest source shard pin',
        'scenario_fields':'explicit per-field provenance and overrides; inherited fixture state remains separately labelled',
        'properties':'R19 BASE/EFFECTIVE/MODIFIER sources; distinct base/effective validated with existing evaluator',
        'modifiers':'explicit active instances only; existing R17 definition graph hash, owner, listener/provider/dynamic/snapshot state validated',
        'version_compatibility':versions,'actor_cohort':cohort,'source_owner_join_warning':'55 nonjoined contexts are explicit scenario ability owners, not proven native owner joins'}
    resource=common|{'schema':'generic_runtime_resource_engine/1','domains':list(DOMAINS),'operations':list(OPERATIONS),
        'native_resource_name_mapping':'UNKNOWN; SP is not sufficient resource identity evidence','numeric':'R12 mode0 signed raw int64/scale2^33/step2 toward-zero; overflow gap',
        'ownership':'exact entity/team/action-owned ability; no namespace aliases','bounds':'explicit min/max, clamp/reject and initial overcap; unknown gaps',
        'events':'explicit PRE_RESOURCE/RESOURCE_CHANGE/POST_RESOURCE order, R17 complete listener registrations, R15 owned/drained callbacks',
        'transaction':'reuse R18 checkpoint ancestry + R15; rollback resource/HP/modifiers/registrations/RNG/queues together on nested atomic gap; earlier tasks retained',
        'cost_boundary':'resource_cost_reference requires explicit scenario source, nonnegative subtract amount and sufficient balance above min; native action legality/turn/ultimate thresholds not implied',
        'ModifySPNew':native,'instruction_census':resources,'followups':follow,
        'isolated_gap':'Local_SPAdd resolves multiple targets under the unchanged alias; exact single owner agreement remains a typed gap',
        'source_field_mapping':'all fields classified explicitly; serialized operand-as-delta reference is not native AddRatio/SPBase/rate formula',
        'real_graph_commits':cohort['resource_mutations_committed'],'real_graph_callbacks':cohort['resource_callbacks']}
    progression=common|{'schema':'generic_runtime_progression_census/1','instruction_census':progress,
        'skill_tree_policy':'hash-bound actual serialized TriggerKey with explicit activated booleans; absent key gaps',
        'native_PointID_TriggerKey_join':'only source-backed selected rows available; cohort activation dictionaries are explicit reference keyed state, not native legality',
        'rank_policy':'existing R19 KEYED_THRESHOLD_GE_REFERENCE; TriggerKey not numeric rank; missing rank/threshold/policy gaps',
        'constructed_activation_entries':cohort['bound_activation_rows'],'skill_tree_predicates_completed':cohort['skill_tree_predicates_completed'],
        'rank_predicates_completed':cohort['rank_predicates_completed'],'natasha_regression':read(AUDIT/'natasha_regression.json')}
    support=common|{'schema':'generic_runtime_support_census/10','frozen_baseline':baseline,'frozen_regression':frozen,
        'R19_same_15_root_cohorts':r19,'R20_explicit_actor_cohort':cohort,
        'transition_levels':{
            'ACTOR_STATE_CONSTRUCTED':{'contexts':83,'real_avatar_identities':25},
            'PROGRESSION_PREDICATE_EXECUTABLE':{'skill_tree_completions':cohort['skill_tree_predicates_completed'],'rank_completions':cohort['rank_predicates_completed']},
            'RESOURCE_MUTATION_EXECUTABLE':{'original_source_isolated':38,'denominator':39,'reference_modifier_callback_commits':3},
            'REAL_GRAPH_RESOURCE_PREFIX':{'roots':cohort['real_graph_resource_prefix_roots'],'commits':cohort['resource_mutations_committed']},
            'FULL_REAL_SKILL_REFERENCE_TRANSITION':{'joined':0,'separate_original_nonjoined_ability_actions':completed,'separate_ability_actions_count':3},
            'NATIVE_VALIDATED_TRANSITION':0},
        'whole_battle_capabilities':capabilities,'next_phase_ranking':ranking,'determinism':'PASS','replay':replay}
    prior=read(control('semantic_gap_ledger_v7'))
    gap=common|{'schema':'generic_runtime_semantic_gap_ledger/8','inherited_v7_artifact':str(control('semantic_gap_ledger_v7').relative_to(ROOT)),
        'inherited_v7_sha256':sha(control('semantic_gap_ledger_v7')),'frozen_distributions':prior['frozen_first_gap_distributions'] if 'frozen_first_gap_distributions' in prior else frozen['before'],
        'R20_observed_first_gaps':cohort['first_gaps'],'R20_family_distribution':cohort['first_gap_family_distribution'],
        'native_oracle_tickets':prior['oracle_tickets']+[
            {'identity':'ACTOR_NATIVE_INITIALIZATION_REQUIRED','status':'NATIVE_ORACLE_PENDING','question':'effective native level/promotion/skill-tree/modifier/provider/resources initial state and legality'},
            {'identity':'MODIFY_SP_EFFECTIVE_RESOURCE_ORACLE_REQUIRED','status':'NATIVE_ORACLE_PENDING','question':'exact resource identity, AddRatio/SPBase/rates, caps/sign/event/order/IFix/Lua effective path'},
            {'identity':'TRUE_TURN_AV_EVIDENCE_REQUIRED','status':'NOT_BOUND','question':'exact AV clock, initiative, tie-breaks, turn ownership, advance/delay and interrupt rules'}],
        'true_subsystem_absence':capabilities,'real_heal_resource_boundary':'original source FormulaType2/target field mapping unavailable in this cohort; synthetic existing-core pairing is not a real graph claim'}
    for name,value in zip(CONTROL_NAMES,[actor,resource,progression,support,gap]):put(control(name),value)
    summary=common|{'frozen_baseline':baseline,'actor_cohort':cohort,'resource_followups':follow,
        'completed_original_ability_actions':completed,'whole_battle_capability_matrix':capabilities,
        'recommended_R21':ranking[0]['phase'],'handoff':str(DEST),'production_files':PRODUCTION,
        'determinism':'PASS','replay':'PASS','architecture':'PASS','version_compatibility':versions}
    write('final_summary.json',summary)
    report(summary,r19,capabilities,ranking)
    print('R20 controls/report established',tests,flush=True)

def report(summary,r19,capabilities,ranking):
    c=summary['actor_cohort'];f=summary['resource_followups'];tests=summary['tests']
    lines=[
        '# R20 Actor State + Resource / Progression', '',
        f"CR `{CR}`. Verdict **GENERIC_ACTOR_RESOURCE_REFERENCE_ENGINE_ESTABLISHED**. Starting HEAD `{summary['starting_head']}`, branch `terra/implementation`. Git writes NONE; frozen M10–M15, ScenarioCompiler and strict admission unchanged. All inherited/unrelated files are hash-checked against the start gate.", '',
        'R20 adds ActorRuntimeBinding and explicit resource transactions to the existing BehaviorRuntime/BehaviorBattleState. Actor/team stores and progression are reused; entity/ability-local reference stores and records live under opt-in mechanics. R15 schedules owned work, R17 dispatches modifiers/listeners, R19 evaluates properties/rank, and the existing R18 checkpoint stack protects atomic nested effects. There is no second BattleState, ScenarioCompiler, property evaluator, event bus or process-global cache.', '',
        '## Actor authority and versions', '',
        'REAL_CONTENT_STATIC, REAL_CONTENT_RECONSTRUCTED, REFERENCE_MODEL, EXPLICIT_SCENARIO_INPUT and EFFECTIVE_RUNTIME_UNKNOWN remain distinct. Absent fields, explicit zero, explicit false and unknown values remain distinct. Fields are never silently completed into native legality. Existing reference fixture values are preserved as inherited reference inputs rather than upgraded to native state.', '',
        'Actor identity comes from the exact pinned 4.6.51 AvatarConfig decoded row, source pointer/hash and version manifest/source-shard pin. Levels, promotions, ranks, activation booleans, HP/property/resources and overrides are caller fixture inputs. Definition existence does not imply an active modifier. Initial instances require explicit activation evidence, exact definitions/owners, listener/provider policy, dynamic/snapshot state and unique IDs. Base/effective differences are checked with the R19 contribution evaluator to prevent double counting.', '',
        'Research baseline is **4.6.51**; product ContentDatabase remains **4.4.54**. Shared types are version-independent abstractions. Static values are not merged across versions. Incompatible or relabelled source versions return VERSIONED_CONTENT_GAP. Exact native initialized actor legality and unprovided static/property/progression/resource values remain unknown. See version_compatibility.json.', '',
        '## Resources, progression and callbacks', '',
        'The trusted 632-root census has 39 ModifySPNew instances, 45 ByRankActivated predicates and 44 BySkillPointActivated predicates. The 31 SetEnergyBarState records remain structure-only candidate operations; they are not asserted to mutate a numeric resource.', '',
        'Existing same-version R11 evidence identifies a related unpatched actor property path at 0xB/0xC/0x8A, a distinct team BP path, and a partial AddRatio → SPBase/rate/cap chain. Effective resource identity/formula, IFix/Lua/task mapping, event dispatch and capacities remain unproved. The label SP establishes none of those. Execution uses a hash-bound, caller-authored field mapping, exact target/owner/resource domain and explicit serialized-operand-as-delta policy. This is not native AddRatio formula equivalence.', '',
        'ACTOR_RESOURCE, TEAM_RESOURCE, ENTITY_RESOURCE and ABILITY_LOCAL_RESOURCE are independent; UNKNOWN_NATIVE_RESOURCE rejects. READ, SET, ADD, SUBTRACT, CLAMP and COMPARE use the existing R12 fixed-point contract (signed int64 raw, scale 2^33, step2 toward-zero). Bounds, initial overcap, overflow, event order and complete active R17 listener registrations are explicit. Pre/change/post events drain owned R15 callbacks. Source costs require explicit source/authority, nonnegative subtraction and sufficient balance above the minimum; this does not establish native availability, turn ownership, ultimate thresholds or M15 admission.', '',
        'Skill-tree predicates bind the actual serialized TriggerKey and explicit boolean activation input. TriggerKey activation dictionaries in the cohort are reference state; they do not prove native PointID/activation legality. Rank reuses R19 KEYED_THRESHOLD_GE_REFERENCE with exact actor rank and keyed threshold. TriggerKey is not treated as rank. Missing rank, threshold, activation or comparison policy returns a gap.', '',
        'Unsupported atomic resource effects restore resource/HP values, listeners/modifiers, RNG, queues and transaction records, including nested damage. Earlier committed source tasks persist and retry resumes the original source. Actors, policies, progression, resources and pending transactions serialize through existing snapshot/clone/hash/replay. Runtime hashes include behavior-changing policies; committed resource records include exact policy hashes. Actor binding policies also live in state.', '',
        '## Measured boundaries', '',
        '| Scope | Result |', '|---|---|',
        '| Frozen combat roots / joined roots / joined rows | 632 / 160 / 161 |',
        '| Frozen combat tasks reached/completed | 1025 / 494 → 1025 / 494 |',
        '| Frozen joined tasks reached/completed | 300 / 121 → 300 / 121 |',
        '| Frozen HP commits / complete joined transitions | 0 / 0; state hash drift 0 |',
        '| Same 15 R19 roots, finish-only lifecycle closures | 10 / 15 → 10 / 15 |',
        '| Same 15 R19 roots, continuation-expression closures | 14 / 15 → 14 / 15 |',
        '| Same 15 R19 roots, separate explicit-rank closures | 15 / 15 → 15 / 15 |',
        '| Same 15 R19 roots reaching HP with expression/rank | 15 / 15 → 15 / 15 |',
        '| Complete joined skills, all R19 comparison cohorts | 0 / 15 → 0 / 15 |',
        f"| R20 explicit contexts / real Avatar identities / exact source owner joins | {c['initialized_actor_contexts']} / {c['unique_real_avatars']} / {c['exact_source_owner_join_contexts']} |",
        f"| Explicit activation entries / completed skill-tree / rank predicates | {c['bound_activation_rows']} / {c['skill_tree_predicates_completed']} / {c['rank_predicates_completed']} |",
        f"| R20 original graph tasks reached/completed | {c['metrics']['tasks_reached']} / {c['metrics']['tasks_completed']} |",
        f"| Original graph resource attempted/committed / prefix roots | {c['resource_mutations_attempted']} / {c['resource_mutations_committed']} / {c['real_graph_resource_prefix_roots']} |",
        f"| Original graph HP-mutating roots / settlements | {c['hp_mutated']} / {c['settlements']} |",
        '| Isolated original resource primitives | 38 commits / 39 probes, excluded from original graph/full-skill totals |',
        '| Explicit modifier listener invoking real resource task | 3 callbacks / 3 commits, separate reference probes |',
        '| Real graph resource callbacks | 0; separate listener probes do not inflate this count |',
        '| Complete joined skill transitions / native validated | 0 / 0 |', '',
        'Three original nonjoined ability-root reference actions complete under explicit scenario owner contexts: '+', '.join('`'+x+'`' for x in summary['completed_original_ability_actions'])+'. All use their original source completion nodes and drained work. They are not joined complete skills and do not prove native actor ownership/legality. The 55 unjoined contexts use explicitly supplied ability owners rather than inferred character identities.', '',
        'Seven original resource-prefix roots pass independent replay, clone and snapshot/resume comparisons, including all three completed ability actions. All 39 isolated source-resource probes pass checkpoint determinism; Local_SPAdd retains an exact-target-owner gap because the unchanged alias resolves multiple targets. No missing SkillPerformFinish is inserted. The paired damage/resource probe and existing reference Heal FormulaType2/resource probe mutate HP/resources; those pairings are explicitly synthetic. Original real heal FormulaType2/target mapping remains SOURCE_COMPATIBILITY_GAP in the paired probe and is not fabricated.', '',
        'Natasha Skill02 Phase01/Phase02 retain their original progression blocker under unchanged fixtures. With separately labelled explicit activation state, both progress to the next original DispelStatus task and stop there. No Natasha keys or AvatarID branches exist in production.', '',
        '## Whole battle capability matrix', '',
        '| Capability | Reference status | Native evidence |', '|---|---|---|']
    lines += ['| '+name+' | '+v['status']+' | '+v.get('oracle','NOT_BOUND')+' |' for name,v in capabilities.items()]
    lines += ['', 'Top remaining gaps include missing decoded catalogs/template parameters, effective modifier/provider inputs, DispelStatus and other unbound primitives, native actor/resource initialization and formula/events, true turn/AV, shield/break, Monster decisions and stage progression. First-gap frequency does not measure unvisited subsystem absence.', '',
        '**Recommended R21: TRUE BATTLE TURN / AV, starting with bounded evidence discovery.** Establish a source/effective-runtime contract for clock/initiative/tie-break/turn ownership/advance-delay/interrupt semantics before implementing native-like scheduling. R15 logical time is insufficient evidence. Catalog/character-root completion ranks second for concrete graph closure, followed by toughness/break/shield, Monster behavior, action legality/cost and targeted native oracle work. See next_phase_priority.json for impact, evidence availability, generic reuse, blockers, cost and uncertainty; another local property/resource phase is not the default.', '',
        '## Validation and handoff', '',
        'Determinism PASS; replay PASS; architecture PASS. R20 focused tests cover provenance/version relabelling, absent/zero/false/unknown, progression/rank gaps, all resource operations/domains, bounds/overcap/cost, event order/ownership, nested HP/resource/RNG/listener rollback, active initial modifiers/providers, base/effective contributions, checkpoint restoration and explicit replay.', '',
        'Final lanes: '+', '.join(name+' **'+str(row['tests'])+' PASS**' for name,row in tests.items())+'. Frozen historical tests unchanged.', '',
        'Production: '+', '.join('`'+p+'`' for p in PRODUCTION)+'. Tests: `tests/battle_runtime/test_behavior_r20.py` ('+str(tests['R12_R20']['tests']-265)+' focused tests). Five requested R20 controls and this report are generated by r20_finalize.py. Audit: `tmp/audit/r20_actor_resource_progression_20261010_001/`.', '',
        'Reproduce: `python tools/runtime/r20_evidence.py`; `python tools/runtime/r20_probes.py --frozen`; `python tools/runtime/r20_probes.py --r19`; `python tools/runtime/r20_probes.py`; `python tools/runtime/r20_followups.py`; `python tools/runtime/r20_replay.py`; `python tools/runtime/r20_checks.py final`; `python tools/runtime/r20_finalize.py`; `python tools/runtime/r20_finalize.py --package`. The start gate must never be regenerated after edits.', '',
        f'Handoff: `{DEST.as_posix()}`. Archive includes only R20-owned source/tests/tools/controls/report/audits, baseline-relative patches and manifest. Inherited starting-file copies, binaries, native payloads/process dumps/old reverse trees and unrelated dirty files are excluded. CRC, exact members, sizes, per-member SHA-256 and ZIP SHA-256 are verified; ZIP receipt stays external to avoid a self-reference.', '',
        '**Native correctness NOT CLAIMED. Git writes NONE.**', '']
    REPORT.write_text('\n'.join(lines),encoding='utf-8')

def package():
    verify();assert read(AUDIT/'final_summary.json')['verdict']=='GENERIC_ACTOR_RESOURCE_REFERENCE_ENGINE_ESTABLISHED'
    for name in OWNED_EXISTING:
        old=(AUDIT/'starting_files'/name).read_text(encoding='utf-8');new=(ROOT/name).read_text(encoding='utf-8')
        diff=''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='inherited/'+name,tofile='r20/'+name))
        path=AUDIT/'patches'/(name+'.patch');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(diff,encoding='utf-8')
    files=[ROOT/n for n in PRODUCTION]+[ROOT/'tests/battle_runtime/test_behavior_r20.py']
    files+=sorted((ROOT/'tools/runtime').glob('r20_*.py'))+[control(n) for n in CONTROL_NAMES]+[REPORT]
    files += [p for p in AUDIT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'test_tmp' not in p.parts
              and 'starting_files' not in p.parts and p.name not in ('manifest.json','handoff_verification.json') and p.suffix!='.zip']
    files=sorted(set(files));members={p.relative_to(ROOT).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for p in files}
    manifest={'change_request':CR,'starting_head':read(AUDIT/'start_gate.json')['head'],
        'scope':'R20-owned changes only; existing changed source includes inherited baseline and baseline-relative R20 patch',
        'members':members,'inherited_base_hashes':{n:sha(AUDIT/'starting_files'/n) for n in OWNED_EXISTING},
        'git_writes':'NONE','excluded':['starting copies','unrelated dirty files','source binaries','process dumps','previous reverse audit trees']}
    write('manifest.json',manifest);files.append(AUDIT/'manifest.json')
    local=AUDIT/DEST.name
    with zipfile.ZipFile(local,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
    expected={p.relative_to(ROOT).as_posix():{'size':p.stat().st_size,'sha256':sha(p)} for p in files}
    receipt=verify_zip(local,expected)
    receipt.update(destination=str(DEST),local_archive=str(local))
    write('handoff_verification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='members'},indent=2))

def verify_zip(path,expected):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(expected)
        for name,row in expected.items():
            data=z.read(name);assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
    return {'CRC':'PASS','exact_members':'PASS','sizes_per_member_SHA256':'PASS','member_count':len(expected),
        'ZIP_sha256':sha(path),'ZIP_size':Path(path).stat().st_size,'members':expected}

def destination_receipt():
    receipt=read(AUDIT/'handoff_verification.json');actual=verify_zip(DEST,receipt['members'])
    assert actual['ZIP_sha256']==receipt['ZIP_sha256']
    receipt['destination_verified']=True;write('handoff_verification.json',receipt)
    print('destination verified',DEST,actual['ZIP_sha256'])

if __name__=='__main__':
    if '--package' in sys.argv:package()
    elif '--verify-destination' in sys.argv:destination_receipt()
    else:finalize()
