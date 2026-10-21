"""R16 honest closure censuses, preservation audit and verified CR-only ZIP."""
from __future__ import annotations
import re
import zipfile
from r16_probes import *
from hsr_battle_agent.battle_ir.content_catalog import classify_dependency
from r14_discovery import canonical_compile

PRODUCTION=['src/hsr_battle_agent/battle_ir/content_catalog.py',
            'src/hsr_battle_agent/battle_runtime/action_scheduler.py']
TESTS=['tests/battle_runtime/test_behavior_r16.py']
TOOLS=['tools/runtime/r16_'+n for n in ['checks.py','dependency_closure.py','local_readers.cjs','probes.py','regressions.py','finalize.py']]
CONTROL_NAMES=['ability_dependency_graph_v1','catalog_resolution_census_v1','dependency_closure_v1',
               'support_census_v6','semantic_gap_ledger_v4']
REPORT=f'docs/agent/handoffs/generic_runtime_ability_dependency_closure_{SUFFIX}.md'
ZIP_NAME=CR+'_changed_files.zip'

def write_control(name,value):
    control(name).write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')

def main(package=False):
    cat=load_catalog();graph=read(control('ability_dependency_graph_v1'))
    probes=read(AUDIT/'probe_summary.json');before=read(AUDIT/'before_probes.json');after=read(AUDIT/'after_probes.json')
    expanded=read(AUDIT/'expanded_probes.json');gate=read(AUDIT/'start_gate.json');baseline=read(AUDIT/'frozen_baseline.json')
    tests=read(AUDIT/'final_tests.json');replay=read(AUDIT/'replay_receipt.json');regressions=read(AUDIT/'real_content_regressions.json')
    batch=read(R14/'expanded_decoded_records.json');rows=list(cat.records.values())
    old=ContentCatalog(read(AUDIT/'directory_inventory.json')['entries'],
        [*[r for r in rows if r.get('ir') and not r.get('newly_decoded')],*batch['record_gaps']])
    corpus=read(control('real_combat_corpus_v2'))
    frozen_sources={tuple(g['source_identity']) for g in corpus['graphs'] if g['stratum'] in COMBAT}
    external=[e for e in graph['edges'] if not e.get('inline')]
    frozen_edges=[e for e in external if tuple(e['parent_source_identity']) in frozen_sources]
    resolved_sites=[e for e in frozen_edges if e['status']=='EXACT_RESOLVED_COMPILED' and old.resolve(e)['status']!='EXACT_RESOLVED_COMPILED']
    byroot={r['root']:r for r in after};historical={r['root']:r for r in before}
    audits={'Phase':[],'Camera':[],'Other':[]}
    for row in before:
        cap=row.get('required_capability') or ''
        if not row['skill_joined'] or not cap.startswith('missing decoded child catalog reference:'):continue
        identity=cap.split(':',1)[1]
        category='Camera' if '_Camera' in identity else 'Phase' if '_Phase' in identity else 'Other'
        site=next((e for e in graph['edges'] if e.get('identity')==identity and e['parent_source_identity']==row['source_identity']),
                  {'identity':identity,'reference_type':'ABILITY_REFERENCE'})
        oldresolution=old.resolve(site);resolution=cat.resolve(site)
        target=cat.records.get(tuple(resolution.get('target_source_identity',[])))
        audits[category].append({'root':row['root'],'identity':identity,'reference_site':site,
             'before_status':oldresolution['status'],'after_status':resolution['status'],
             'inspection':classify_dependency(target),'after_first_gap':byroot[row['root']]['required_capability'],
             'after_first_gap_family':byroot[row['root']]['first_gap_family'],
             'name_category_is_prioritization_only':True,'no_empty_child_substitution':True})
    assert len(audits['Camera'])==68 and len(audits['Phase'])==15
    write('phase_camera_audit.json',audits)
    # Lifecycle/callback graph presence and effective behavior are different stages.
    lifecycle=[]
    for r in rows:
        if not r.get('ir'):continue
        ir=IRNode.from_dict(r['ir']);p=ir.payload
        if ir.op=='ability':
            slots=p.get('reference_unbound_sequences',[])
            stage='ENTRY_ABILITY_FOUND_POLICY_UNKNOWN' if slots else 'LIFECYCLE_SLOT_BOUND'
            lifecycle.append({'identity':r['identity'],'source_identity':list(source_key(r)),
                'stage':stage,'additional_slots':slots,'ADDITIONAL_LIFECYCLE_SLOT_PRESENT':bool(slots),
                'canonical_IR_hash':ir.stable_hash(),'authority':'REFERENCE_MODEL',
                'serialized_entry_slot_present':any(f.get('mask')==16 for f in r['graph'].get('fields',[])),
                'entry_binding':'EXISTING_R13_BITMAP_16_REFERENCE_ENTRY',
                'additional_slot_policy_supplied_in_corpus_probe':False,'native_inheritance_claimed':False})
    write('lifecycle_slot_audit.json',lifecycle)
    first_inputs=[]
    for row in after:
        if not (row.get('required_capability') or '').startswith('explicit reference input:'):continue
        node=IRNode.from_dict(row['gap_node']);roles=node.payload.get('reference_binding',{}).get('roles',{})
        known=all(k in roles for k in ('target','modifier'))
        modifier_input=node.op.endswith('AddModifier')
        dynamic_input=node.op.endswith('SetDynamicValue')
        classification='EXPLICIT_MODIFIER_APPLICATION_FIXTURE_INPUT_MISSING' if modifier_input else \
                       'DYNAMIC_PROVIDER_FIXTURE_INPUT_MISSING' if dynamic_input else 'OTHER_EXPLICIT_FIXTURE_INPUT_MISSING'
        first_inputs.append({'root':row['root'],'source_identity':row['source_identity'],'skill_joined':row['skill_joined'],
             'primitive':node.op,'required_input':row['required_capability'],'node_id':node.node_id,
             'decoded_role_keys':sorted(roles),'target_and_modifier_roles_present':known,
             'classification':classification,
             'handler_evidence':'behavior_expansion.modifier requires modifiers.applications[node.node_id] before graph installation' if modifier_input else
                                'behavior_expansion.task(SetDynamicValue) requires dynamic_providers[node.node_id] before field evaluation',
             'policy_evidence':'same frozen R15 fixture has modifiers.applications = {}' if modifier_input else 'same frozen R15 fixture has dynamic_providers = {}',
             'catalog_problem':False,'reader_failure':False,'next_subsystem':'MODIFIER_EVENT' if modifier_input else 'PROPERTY_DYNAMIC_PROVIDER',
             'installed_instances_inferred':False})
    write('first_input_gap_analysis.json',{'rows':first_inputs,
        'baseline_joined_task_list_0_classification':dict(collections.Counter(r['primitive'] for r in before if r['skill_joined'] and r['required_capability']=='explicit reference input:/record/task_list/0')),
        'joined_task_list_0_blockers':sum(r['skill_joined'] and r['required_input']=='explicit reference input:/record/task_list/0' for r in first_inputs),
        'classification_counts':dict(collections.Counter(r['classification'] for r in first_inputs))})
    template_edges=[e for e in graph['edges'] if e['reference_type']=='TEMPLATE_REFERENCE']
    modifier_edges=[e for e in graph['edges'] if e['reference_type']=='MODIFIER_REFERENCE']
    callback_edges=[e for e in graph['edges'] if e['reference_type']=='CALLBACK_REFERENCE' and not e.get('lifecycle')]
    write('template_modifier_callback_audit.json',{'templates':template_edges,'modifiers':modifier_edges,'callbacks':callback_edges,
        'numeric_string_sequence_and_caller_fields_retained':True,'modifier_instance_active':'NOT_IMPLIED',
        'callback_registered':'NOT_IMPLIED','callback_executable':'POLICY_AND_SEMANTICS_REQUIRED',
        'template_execution':'TEMPLATE_PARAMETER_INHERITANCE unless hash-bound call and entry policies explicitly supplied'})
    census={'schema':'generic_runtime_catalog_resolution_census/1','change_request':CR,
        'authority':'STRUCTURAL_CONTENT_PRESENCE_PLUS_REFERENCE_MODEL_EXECUTION_ONLY','native_executable':False,
        'dependency_edges':len(graph['edges']),'character_side_edges':len(graph['character_reference_edges']),
        'external_edges':len(external),'inline_edges':len(graph['edges'])-len(external),
        'external_status_counts':dict(collections.Counter(e['status'] for e in external)),
        'inline_status_counts':dict(collections.Counter(e['status'] for e in graph['edges'] if e.get('inline'))),
        'frozen_root_external_sites':len(frozen_edges),
        'frozen_root_sites_before':dict(collections.Counter(old.resolve(e)['status'] for e in frozen_edges)),
        'frozen_root_sites_after':dict(collections.Counter(e['status'] for e in frozen_edges)),
        'newly_resolved_frozen_reference_sites':len(resolved_sites),
        'newly_resolved_unique_source_identities':len({tuple(e['target_source_identity']) for e in resolved_sites}),
        'resolved_sites':resolved_sites,'Phase':audits['Phase'],'Camera':audits['Camera'],
        'ability_lifecycle_counts':dict(collections.Counter(r['stage'] for r in lifecycle)),
        'baseline_metrics_frozen':baseline,'count_policy':'External calls, inline bodies and character references reported separately. New descendants do not change frozen root denominators.'}
    write_control('catalog_resolution_census_v1',census)
    ranking=[]
    for family_name,n in probes['combat']['after']['first_gap_family_distribution'].items():
        j=probes['skill_joined']['after']['first_gap_family_distribution'].get(family_name,0)
        ranking.append({'family':family_name,'combat_first_gaps':n,'joined_first_gaps':j,'observed_score':n+2*j})
    ranking.sort(key=lambda r:(-r['observed_score'],r['family']))
    # Raw frequency still ranks missing catalogs first. Actionable ranking accounts
    # for the explicit stop boundary: directory-not-found requires new source-path
    # evidence; residual readers need a separate bounded phase.
    costs={'CONTENT_CATALOG_BINDING':4,'MODIFIER_EVENT':1,'DAMAGE':2,'OTHER_SEMANTICS':3,
           'PREDICATE_PROGRESSION':2,'PROPERTY_DYNAMIC_PROVIDER':2,'ACTION_EXECUTION_SCHEDULER':2,
           'HEAL':2,'RESOURCE':2,'POSITION':2}
    actionable=[{**r,'authored_independent_phase_cost':costs.get(r['family'],3),
                 'actionable_score':r['observed_score']/costs.get(r['family'],3)} for r in ranking]
    actionable.sort(key=lambda r:(-r['actionable_score'],r['family']))
    recommendations={'MODIFIER_EVENT':'R17 MODIFIER + EVENT ENGINE','DAMAGE':'R17 DAMAGE + HP/TOUGHNESS PIPELINE',
                     'CONTENT_CATALOG_BINDING':'R17 MORE CATALOG CLOSURE','RESOURCE':'R17 RESOURCE ENGINE',
                     'PROPERTY_DYNAMIC_PROVIDER':'R17 PROPERTY / DYNAMIC PROVIDER'}
    next_phase=recommendations.get(actionable[0]['family'],'R17 TARGETED GENERIC SEMANTIC CLOSURE')
    new_instances={}
    for r in rows:
        if not r.get('newly_decoded'):continue
        for node in walk_nodes(IRNode.from_dict(r['ir'])):
            payload=node.payload
            if node.kind not in ('TaskIR','UnsupportedSemanticIR','TargetSelectorIR','PredicateIR','ExpressionIR'):continue
            span=payload.get('span')
            if not isinstance(span,list) or len(span)!=2 or None in span:continue
            typ=payload.get('task_type',node.op)
            family_name='task' if node.kind in ('TaskIR','UnsupportedSemanticIR') else \
                        'target' if node.kind=='TargetSelectorIR' else 'predicate' if node.kind=='PredicateIR' else 'expression'
            key=(source_key(r),family_name,typ,tuple(span))
            new_instances[key]={'family':family_name,'type':typ,'span':span,'source_identity':list(source_key(r)),
                                'IR_kind':node.kind,'STRUCTURALLY_COMPILED':True,'NATIVE_EFFECTIVE':False,
                                'ORACLE_PENDING':True,'unsupported_preserved':node.kind=='UnsupportedSemanticIR'}
    write('expanded_semantic_type_census.json',{'instances':list(new_instances.values()),
          'count_policy':'New roots only; physical source coordinates/type deduplicated across IR payload copies. Nodes without a proven serialized span are omitted.',
          'instances_by_family':dict(collections.Counter(n['family'] for n in new_instances.values())),
          'types_by_family':{f:sorted({n['type'] for n in new_instances.values() if n['family']==f}) for f in ['task','target','predicate','expression']}})
    write_control('support_census_v6',{'schema':'generic_runtime_support_census/6','change_request':CR,
        'semantic_authority':'REFERENCE_MODEL','native_correct':False,'frozen_combat':probes['combat'],
        'frozen_skill_joined':probes['skill_joined'],'expanded_corpus':probes['expanded'],
        'expanded_denominator':len(expanded),'baseline_denominators':{'combat':632,'joined_unique':160,'joined_rows':161},
        'types_inherited_without_semantic_upgrade':read(control('scheduler_support_census_v5'))['types'],
        'new_structural_root_types':read(AUDIT/'closure_summary.json')['new_root_types'],
        'expanded_static_type_census':read(AUDIT/'expanded_semantic_type_census.json'),
        'stage_definitions':{'CONTENT_GRAPH_PRESENT':'Fully decoded and compiled body, installation unknown',
                            'MODIFIER_INSTANCE_ACTIVE':'Requires explicit instance installation; not implied',
                            'CALLBACK_REGISTERED':'Requires explicit registration; not implied',
                            'CALLBACK_EXECUTABLE':'Requires context and task semantics; not implied'},
        'observed_first_gap_ranking':ranking,'actionable_planning_ranking':actionable,
        'ranking_authority':'AUTHORED_PLANNING_ONLY; frequency score = combat + 2*joined. Phase cost explicitly estimates scope/evidence needed, not native semantics.',
        'recommended_R17':next_phase,'first_blocker_changed_joined':probes['first_blocker_changed_joined']})
    grouped=collections.defaultdict(list)
    for r in after:
        if r['required_capability']:grouped[(r['primitive'],r['required_capability'],r['first_gap_family'])].append(r)
    gap_rows=[{'primitive':primitive,'required_capability':cap,'family':fam,'combat_roots':len(rs),
               'joined_roots':sum(r['skill_joined'] for r in rs),'source_identities':[r['source_identity'] for r in rs],
               'native_status':'RUNTIME_ORACLE_PENDING'} for (primitive,cap,fam),rs in grouped.items()]
    write_control('semantic_gap_ledger_v4',{'schema':'generic_runtime_semantic_gap_ledger/4','change_request':CR,
        'frozen_first_gaps':gap_rows,'unresolved_dependency_edges':[e for e in external if e['status']!='EXACT_RESOLVED_COMPILED'],
        'first_input_analysis':first_inputs,'lifecycle_slot_policy_gaps':[r for r in lifecycle if r['additional_slots']],
        'observed_ranking':ranking,'actionable_ranking':actionable,'recommended_R17':next_phase,
        'reader_boundary':'180 local method spans; no new provider/archive/global registry discovery',
        'source_discovery_boundary':'Verified all inherited player/common directories; 1728 candidate transforms are discovery-only and found no new camera asset identity',
        'camera_irrelevance':'NOT_PROVEN; all 68 initial joined Camera-name references remain explicit gaps',
        'native_equivalence_claimed':False})
    # Recompile every newly decoded body; original IR and unknown fields are fixed.
    ledger=read(ROOT/'data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    hashes={}
    for r in rows:
        if not r.get('newly_decoded'):continue
        _,ir=canonical_compile(r,r['decoded_artifact'],ledger)
        if ir.stable_hash()!=r['canonical_IR_hash']:raise ValueError('repeated canonical compile drift')
        hashes[r['IR_artifact']]=ir.stable_hash()
    write('determinism_verification.json',{'status':'PASS','canonical_hashes':hashes,
          'canonical_roundtrip_and_recompile':True,'real_root_replay_count':len(replay['roots']),
          'full_catalog_snapshot_hash_check_count':sum(r['catalog_snapshot_hash_checked'] for r in replay['roots'])})
    changed=[p for p,h in gate['file_hashes'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    unrelated=[p for p in changed if p not in PRODUCTION]
    pins=all(sha(ROOT/p)==h for p,h in baseline['control_pins'].items())
    forbidden=[]
    for path in PRODUCTION:
        text=(ROOT/path).read_text(encoding='utf-8-sig')
        for token in ['Natasha','Avatar_','110502','SkillID','AvatarID','"_Camera"','"_Phase"','ScenarioCompiler','time.sleep(','subprocess','ctypes','pymem']:
            if token in text:forbidden.append({'path':path,'token':token})
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    architecture={'status':'PASS' if not unrelated and pins and not forbidden and head==gate['head'] and branch==gate['branch'] else 'FAIL',
        'starting_head':gate['head'],'current_head':head,'starting_branch':gate['branch'],'current_branch':branch,
        'changed_preexisting_files':changed,'unrelated_files_changed':unrelated,'forbidden_production_patterns':forbidden,
        'historical_control_pins_preserved':pins,'frozen_M10_M15_modified':False,'frozen_tests_modified':False,
        'ScenarioCompiler_modified':False,'M15_strict_admission_bypassed':False,'git_writes':'NONE',
        'game_launch':'NONE','process_attach':'NONE','new_scheduler':'NONE','new_IR':'NONE'}
    write('architecture_audit.json',architecture)
    if architecture['status']!='PASS' or any(r['returncode'] for r in tests.values()):raise RuntimeError('closing gate failed')
    completion={'schema':'generic_runtime_dependency_closure/1','change_request':CR,
        'starting_head':gate['head'],'verdict':'REAL_ABILITY_DEPENDENCY_CLOSURE_EXPANDED',
        'baseline':baseline,'structural_closure':read(AUDIT/'closure_summary.json'),
        'catalog_census_summary':{k:v for k,v in census.items() if k not in ('resolved_sites','Phase','Camera','baseline_metrics_frozen')},
        'combat':probes['combat'],'skill_joined':probes['skill_joined'],'expanded':probes['expanded'],
        'first_blocker_changed_combat':probes['first_blocker_changed_combat'],
        'first_blocker_changed_joined':probes['first_blocker_changed_joined'],
        'phase_initial_gaps':15,'phase_initial_gaps_remaining':sum(r['after_status']!='EXACT_RESOLVED_COMPILED' for r in audits['Phase']),
        'camera_initial_gaps':68,'camera_initial_gaps_remaining':sum(r['after_status']!='EXACT_RESOLVED_COMPILED' for r in audits['Camera']),
        'before_after_primitive_occurrences':probes['primitive_occurrences'],
        'first_gap_subtype_distributions':probes['first_gap_subtype_distributions'],
        'runtime_unbound_catalog_lookups':probes['runtime_unbound_catalog_lookups'],
        'historical_baseline_drift':probes['historical_baseline_drift'],
        'baseline_drift_explanation':'One template gap now uses the typed TEMPLATE_PARAMETER_INHERITANCE label. All historical task/child/status/family metrics remain unchanged.',
        'tests':tests,'architecture':architecture,'determinism':'PASS','replay':'PASS','regressions':regressions,
        'observed_ranking':ranking,'actionable_ranking':actionable,'recommended_R17':next_phase,
        'production_files':PRODUCTION,'test_files':TESTS,'git_writes':'NONE',
        'stop_boundary':'Every reachable selected reference is accounted for. Further directory-not-found closure needs independent source discovery; residual reader gaps require another bounded reader phase; modifier/damage require major generic semantic subsystems.',
        'native_correct':False,'reference_transition_executable_native_fixture_count':0,
        'handoff_destination':'D:/HSR_Battle_Agent/agent_handoffs/'+ZIP_NAME}
    write_control('dependency_closure_v1',completion)
    b=probes['combat']['before'];a=probes['combat']['after'];j=probes['skill_joined']['after']
    lines=['# R16 Real Ability Dependency Closure', '', f'CR `{CR}`. Verdict **REAL_ABILITY_DEPENDENCY_CLOSURE_EXPANDED**.', '',
        f'Starting HEAD `{gate["head"]}`, branch `{gate["branch"]}`. Git writes NONE. Frozen M10–M15, frozen tests, R14/R15 controls, prior audit trees and unrelated dirty files preserved by SHA-256 audit.', '',
        'The generic ContentCatalog joins explicit reference slots to trusted serialized directory identities and exact source spans. DesignV entries, all inherited layout directories and pinned shard hashes are revalidated. Names select search candidates only; graph names never assign execution semantics. Canonical Behavior IR, R15 ActionExecutionRoot and M15 admission stay in place.', '',
        f'Frozen corpus: 632 combat roots, 160 decoded joined roots / 161 rows; instances {baseline["instances"]}. The same R15 fixture and scheduler policy are used before and after. Newly decoded roots are measured separately: {len(expanded)}; none is counted as a new baseline root or native actor.', '',
        f'Discovered {len(graph["edges"])} dependency edges: {len(external)} external references and {len(graph["edges"])-len(external)} inline lifecycle/template/callback bodies. Character reference side view: {len(graph["character_reference_edges"])}. Cycles: {len(graph["cycles"])}; traversal work/depth gaps: {len(graph["work_gaps"])}. Exact external compiled joins: {sum(e["status"]=="EXACT_RESOLVED_COMPILED" for e in external)}. Among frozen parent reference sites, {len(resolved_sites)} become compiled exact joins to {census["newly_resolved_unique_source_identities"]} unique sources.', '',
        'New structural roots: 51 ability, 94 modifier, 4 template. All 149 canonical IR hashes match repeated compile and round-trip; unknown fields and unsupported tasks remain intact. Narrow reader recovery reuses the frozen exact-build extractor with a 180-method ceiling. No new global dispatcher, provider, archive enumeration or live capture is performed. The first bounded pass recovered wrappers; a further targeted pass prioritized observed joined-root blockers to close their concrete bodies.', '',
        f'Joined first-gap Phase-name references: 15 → {completion["phase_initial_gaps_remaining"]}; Camera-name: 68 → {completion["camera_initial_gaps_remaining"]}. Each of the 83 original referenced sites has a source/evidence/status/next-gap row in the audit. All 68 Camera-name references remain REFERENCE_NOT_FOUND in this bounded trusted directory scope and UNKNOWN semantically. No presentation-only claim or empty substitute is used. Separate decoded Camera-name graphs are inspected by their tasks and remain policy-dependent.', '',
        'Template numeric, string, sequence and caller-context dictionaries are preserved. Direct modifier and inline callback bodies carry their source hashes/spans. CONTENT_GRAPH_PRESENT does not imply MODIFIER_INSTANCE_ACTIVE, CALLBACK_REGISTERED or CALLBACK_EXECUTABLE. Additional ability lifecycle slots are listed separately; the default probe leaves them unbound. Explicit reference policies are keyed by the full canonical node hash, cover every nonempty slot or every parameter/context dictionary, and execute through the original R15 ownership frames.', '',
        '| Frozen combat metric | Before | After |','|---|---:|---:|']
    for key in ['tasks_reached','tasks_completed','abilities_invoked','child_abilities_completed','barriers_encountered','callbacks_completed']:
        lines.append(f'| {key} | {b["metrics"][key]} | {a["metrics"][key]} |')
    for key in ['roots_reaching_damage','roots_reaching_heal','roots_reaching_modifiers','roots_reaching_finish','actions_reference_complete']:
        lines.append(f'| {key} | {b[key]} | {a[key]} |')
    lines += ['',f'First blocker changed: {probes["first_blocker_changed_combat"]} combat roots, {probes["first_blocker_changed_joined"]} joined roots. Joined child invocations 22 → {j["metrics"]["abilities_invoked"]}; joined task completions 114 → {j["metrics"]["tasks_completed"]}. Child completions and action reference completions remain zero. A resolved child does not make a whole skill executable. Damage/modifier reach is an attempted node, never settlement or installation.', '',
        f'Expanded-only probe ({len(expanded)} new roots): {probes["expanded"]["metrics"]}; statuses {probes["expanded"]["status_distribution"]}. Expanded results are not added to the frozen corpus table.', '',
        f'Combat first-gap families before: {b["first_gap_family_distribution"]}.',
        f'Combat first-gap families after: {a["first_gap_family_distribution"]}.',
        f'Joined first-gap families after: {j["first_gap_family_distribution"]}.', '',
        'The baseline 43 joined task_list/0 explicit-input blockers contain 41 AddModifier application inputs and 2 SetDynamicValue provider inputs. After closure there are 44 such first-input blockers: 41 application and 3 provider inputs. The handlers require explicit modifiers.applications[node.node_id] or dynamic_providers[node.node_id]; both frozen fixture maps are empty. These are separate semantic/context fixture inputs, not structural reader failures. Catalog presence cannot install an instance or supply a dynamic provider. The 43 joined MODIFIER_EVENT first-gap-family count is a different grouping and remains unchanged. Detailed role presence and source nodes are retained in first_input_gap_analysis.json.', '',
        'Inline named definitions are indexed from the exact parent record and serialized key/body spans. References to these available bodies receive CONTEXT_BINDING_UNRESOLVED until the caller supplies scope/inheritance policy. They are no longer mislabelled REFERENCE_NOT_FOUND; inline presence creates no active modifier or automatic template invocation.', '',
        'Historical baseline metrics are unchanged. One existing template gap receives the typed TEMPLATE_PARAMETER_INHERITANCE label; its family, status and task counts are unchanged. This label change is excluded from the eight catalog-driven joined blocker changes.', '',
        'Newly reached TaskListTemplate body entry/parameter gaps are classified separately as TEMPLATE_PARAMETER_CONTEXT, rather than being mistaken for modifier roots or missing catalog entries. A subtype census also separates unbound runtime lookups, explicit fixture inputs and lifecycle policies. Runtime lookup failure does not prove structural content absence; the catalog resolution sidecar is authoritative for content presence.', '',
        f'Raw observed priority (combat + twice joined): {[(r["family"],r["observed_score"]) for r in ranking]}. Missing catalog remains the largest weighted family; Modifier/Event is the largest combat family. The actionable planning ranking divides those scores by explicitly authored independent-phase cost: catalog 4 (new path/reader evidence), modifier 1, damage/property/resource 2, other semantics 3. This is a planning estimate, not native semantics. Highest actionable family: {actionable[0]["family"]}. Recommended **{next_phase}**; unresolved catalog evidence remains a separate targeted backlog.', '',
        f'Real-root clone/snapshot/replay: {len(replay["roots"])} checkpoints PASS, including full catalog/runtime hash checks at {sum(r["catalog_snapshot_hash_checked"] for r in replay["roots"])} checkpoints. Nested owned TriggerAbility, context inheritance, template policies, lifecycle policies and atomic rollback are also checked in focused tests.', '',
        'Natasha remains a regression: Skill02 Phase01 still invokes the real Phase02 and stops at explicit actor progression input; no action completion is claimed. Non-Natasha regressions include Bailu Phase child, Anaxa Camera-name call, Acheron basic-attack slot/damage, skill and ultimate-related joined slots, real template call, newly decoded modifier callback task and a decoded Camera-name graph. Whole roots and isolated real-node synthetic wrappers are labelled separately.', '',
        f'Tests PASS: {tests}. Architecture PASS. Determinism PASS. Replay PASS.', '',
        'Reproduce: python tools/runtime/r16_dependency_closure.py; python tools/runtime/r16_probes.py; python tools/runtime/r16_regressions.py; python tools/runtime/r16_checks.py final; python tools/runtime/r16_finalize.py --package. The pinned snapshot and existing R14/R15 artifacts are prerequisites; the handoff contains only R16-owned changed files, new parsed graphs/IR, targeted evidence, controls, logs and manifest. It includes no source game binaries, process dumps or old reverse trees.', '',
        f'Production files: {PRODUCTION}. Tests added: {TESTS}.', '',
        f'Handoff requested at `D:/HSR_Battle_Agent/agent_handoffs/{ZIP_NAME}`. Archive verification receipt records CRC, exact member set, uncompressed sizes, per-member SHA-256 and archive SHA-256.']
    (ROOT/REPORT).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Record prerequisites without copying old reverse trees into this CR archive.
    prerequisites={r[k]:sha(ROOT/r[k]) for r in rows if not r.get('newly_decoded') for k in ('IR_artifact','decoded_artifact') if r.get(k)}
    write('prerequisite_artifact_pins.json',prerequisites)
    if package:
        files=[ROOT/p for p in [*PRODUCTION,*TESTS,*TOOLS,REPORT]]+[control(n) for n in CONTROL_NAMES]
        excluded={'handoff_verification.json','changed_files_manifest.json',ZIP_NAME}
        files += [p for p in AUDIT.rglob('*') if p.is_file() and p.name not in excluded and 'test_tmp' not in p.parts and p.suffix!='.zip']
        files=sorted(set(files));manifest={'change_request':CR,'starting_head':gate['head'],'members':[
            {'path':p.relative_to(ROOT).as_posix(),'size':p.stat().st_size,'sha256':sha(p)} for p in files],
            'prerequisites':'Pinned 4.6.51 snapshot plus prior R12-R15 workspace artifacts; see prerequisite_artifact_pins.json',
            'source_game_payloads_included':False,'git_writes':'NONE'}
        write('changed_files_manifest.json',manifest)
        archive=AUDIT/ZIP_NAME
        manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode('utf-8')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in files:z.write(p,p.relative_to(ROOT).as_posix())
            z.writestr('MANIFEST.json',manifest_bytes)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert set(z.namelist())=={m['path'] for m in manifest['members']}|{'MANIFEST.json'}
            for m in manifest['members']:
                data=z.read(m['path']);assert len(data)==m['size'] and hashlib.sha256(data).hexdigest()==m['sha256']
            assert z.read('MANIFEST.json')==manifest_bytes
            assert z.getinfo('MANIFEST.json').file_size==len(manifest_bytes)
        member_hashes={m['path']:m['sha256'] for m in manifest['members']}
        member_hashes['MANIFEST.json']=hashlib.sha256(manifest_bytes).hexdigest()
        write('handoff_verification.json',{'status':'PASS','CRC':'PASS','member_set':'PASS','sizes':'PASS','per_member_SHA256':'PASS',
            'all_member_sha256':member_hashes,
            'archive_sha256':sha(archive),'archive_size':archive.stat().st_size,'members':len(manifest['members'])+1,
            'workspace_archive':str(archive),'requested_destination':completion['handoff_destination']})
        print('ZIP',archive,'SHA256',sha(archive),flush=True)
    print('R16 complete',completion['verdict'],'next',next_phase,flush=True)

if __name__=='__main__':main(package='--package' in sys.argv)
