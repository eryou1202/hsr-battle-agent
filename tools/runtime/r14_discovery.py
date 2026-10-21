"""Canonical existing Behavior IR compilation and combat-only capability census.

Taxonomy, scores and first-blocker estimates are authored planning measures.
Synthetic reference probes are labelled separately from legal skill transitions.
"""
from __future__ import annotations

import collections
import hashlib
from dataclasses import asdict
from r14_corpus import *
from r12_runtime_reentry import ARCHIVED_DECODER_ROLES, source_authority
from hsr_battle_agent.battle_ir.behavior import IRNode, UnsupportedSemanticIR, walk_nodes
from hsr_battle_agent.battle_ir.behavior_expansion_binding import ExpansionCompiler
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime, default_registry
from r13_reference_fixtures import fixture

COMBAT={'ABILITY_CORPUS','MODIFIER_CORPUS','PASSIVE_CORPUS'}
STRATA=('ALIAS_CORPUS','ABILITY_CORPUS','MODIFIER_CORPUS','SKILL_JOINED_CORPUS','PASSIVE_CORPUS','OTHER_RUNTIME_CONFIG')

# Explicit type taxonomy for planning only; no evaluator or field meanings added.
TAXONOMY={
    'PredicateTaskList':'CONTROL_FLOW','TriggerAbility':'CONTROL_FLOW','IncludeTaskListTemplate':'CONTROL_FLOW',
    'DamageByAttackProperty':'DAMAGE','DamageByAttackPropertyNew':'DAMAGE',
    'DamagePerformFinish':'DAMAGE','LoopExecuteTaskListWithInterval':'SCHEDULER',
    'HealHP':'HEAL','ModifyHealData':'HEAL','AddModifier':'MODIFIER','RemoveModifier':'MODIFIER',
    'DispelStatus':'MODIFIER','SetDynamicValue':'PROPERTY','SetDynamicValueByProperty':'PROPERTY',
    'SetDynamicValueByModifierValue':'MODIFIER','StackProperty':'PROPERTY',
    'ModifySPNew':'RESOURCE','SkillPerformFinish':'SCHEDULER','WaitSecond':'SCHEDULER',
    'WaitAnimState':'SCHEDULER','WaitTimelineFinish':'SCHEDULER',
    'Retarget':'TARGETING','SetSkillTargetFormationByPos':'TARGETING','SetTeamFormation':'TARGETING',
    'TriggerAnimState':'PRESENTATION','TriggerAnimStateWithMove':'PRESENTATION','TriggerEffect':'PRESENTATION',
    'RemoveEffect':'PRESENTATION','LookAt':'PRESENTATION','HeadLookAt':'PRESENTATION',
    'MoveToTargetPosition':'PRESENTATION','MoveToTargetList':'PRESENTATION','CharacterPlayVO':'PRESENTATION',
    'TargetTimeSlow':'PRESENTATION','GlobalMainIntensityEffect':'PRESENTATION','RadialBlurEffect':'PRESENTATION',
    'SyncCharLightAndCameraDir':'PRESENTATION','SetEnergyBarState':'PRESENTATION','SetEntityVisible':'PRESENTATION',
    'ShowBattleUI':'PRESENTATION','HideLevelStage':'PRESENTATION','VCameraConfigChange':'PRESENTATION',
    'ShowBonusUIEffect':'PRESENTATION','PlayTimeline':'PRESENTATION','ScaleCharacterModel':'PRESENTATION',
    'FireProjectile':'PRESENTATION','AlignTargetToTeamCenter':'PRESENTATION','DebugLog':'PRESENTATION',
}


def taxonomy(family,identity):
    if family=='target':return 'TARGETING'
    if family=='predicate':return 'PREDICATE'
    if family=='expression':return 'PROPERTY'
    return TAXONOMY.get(identity.rsplit('.',1)[-1],'UNKNOWN')


def stratum_metrics(graphs):
    exclusive=collections.Counter(g['stratum'] for g in graphs)
    return {**{s:exclusive[s] for s in STRATA if s!='SKILL_JOINED_CORPUS'},
            'SKILL_JOINED_CORPUS':sum(g.get('skill_joined',False) for g in graphs),
            'GLOBAL_CORPUS':len(graphs),'COMBAT_CORPUS':sum(exclusive[s] for s in COMBAT),
            'ABILITY_INCLUDING_PASSIVE':exclusive['ABILITY_CORPUS']+exclusive['PASSIVE_CORPUS'],
            'count_policy':'Exclusive root strata; SKILL_JOINED_CORPUS is a subset view and must not be summed'}


def metrics(nodes):
    result={}
    for family in ('task','target','predicate','expression'):
        rows=[n for n in nodes if n['family']==family]
        result[family]={'instances':len(rows),'types':len({n['type'] for n in rows}),
            'IR_REPRESENTABLE_instances':len(rows),
            'IR_REPRESENTABLE_types':len({n['type'] for n in rows}),
            'CONDITIONAL_REFERENCE_types':len({n['type'] for n in rows if n['support']=='CONDITIONAL_REFERENCE'}),
            'STRUCTURE_ONLY_types':len({n['type'] for n in rows if n['support']=='STRUCTURE_ONLY'}),
            'UNSUPPORTED_types':len({n['type'] for n in rows if n['support']=='UNSUPPORTED'}),
            'CONDITIONAL_REFERENCE_instances':sum(n['support']=='CONDITIONAL_REFERENCE' for n in rows),
            'STRUCTURE_ONLY_instances':sum(n['support']=='STRUCTURE_ONLY' for n in rows),
            'UNSUPPORTED_instances':sum(n['support']=='UNSUPPORTED' for n in rows),
            'REFERENCE_EXECUTABLE_instances':0,'ORACLE_PENDING_instances':len(rows)}
    return result


def canonical_compile(record,path,ledger):
    compiler=ExpansionCompiler(source_authority(path,hashlib.sha256((REPO/path).read_bytes()).hexdigest()),
                               ledger,ARCHIVED_DECODER_ROLES)
    ir=compiler.compile_record(record['graph'],'/record',record['identity'])
    restored=IRNode.from_dict(json.loads(ir.canonical_json()))
    if restored!=ir or restored.stable_hash()!=ir.stable_hash():
        raise RuntimeError('canonical Behavior IR instability')
    repeated=compiler.compile_record(record['graph'],'/record',record['identity'])
    if repeated.stable_hash()!=ir.stable_hash():
        raise RuntimeError('repeated compile changed')
    return compiler,ir


def discover():
    batch=read(AUDIT.relative_to(REPO)/'expanded_decoded_records.json')
    ledger=read('data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    baseline=read('data/control/generic_runtime_real_content_corpus_v1_20261007_001.json')
    inherited_sources=read('data/control/generic_runtime_support_census_v3_20261007_001.json')['actual_corpus']
    for source in inherited_sources:
        if hashlib.sha256((REPO/source['path']).read_bytes()).hexdigest()!=source['sha256']:
            raise RuntimeError('R13 archive source drift')
    records=list(batch['accepted'])
    aliases=read(R11+'global_alias_decode.json')
    shard='StarRail_Data/Persistent/DesignData/Windows/890a6e7e7858a46fdeddf2a4acb00e6f.bytes'
    raw,pin=pinned_source(shard)
    # The frozen complete global alias asset is preserved with exact byte spans
    # and hash-checked R13 archive authority; it never drives combat ranking.
    for e in aliases['entries']:
        graph=e['value']
        records.append({'identity':e['key']['value'],'graph':graph,'graph_hash':digest(graph),
            'record_start':graph['start'],'record_end':graph['end'],'source_shard':shard,
            'source_shard_sha256':pin['sha256'],'stratum':'ALIAS_CORPUS','status':'ACCEPTED',
            'consumption_status':'R11_COMPLETE_GLOBAL_ALIAS_ASSET_ARCHIVED',
            'archive_authority':next(s for s in inherited_sources if s['path']==R11+'global_alias_decode.json'),
            'source_manifest_sha256':MANIFEST_SHA,'directory_identity':aliases['asset']})
    records=deduplicate(records)
    exact={tuple(j['exact_root_identity'][key] for key in ('source_shard_sha256','record_start','record_end'))
        for j in batch['joins'] if j.get('root_structurally_decoded')}
    baseline_starts={(g['source_shard_sha256'],g['start']) for g in baseline['graphs'] if g.get('start') is not None}
    root_rows,node_rows,compiled=[],[],[]
    semantic_seen=set()
    registry=default_registry()
    for record in records:
        key=source_identity(record)
        label=key[0][:16]+'_'+str(key[1])+'_'+str(key[2])
        path=(AUDIT/'graphs'/f'{label}.json').relative_to(REPO).as_posix()
        write(REPO/path,record)
        compiler,ir=canonical_compile(record,path,ledger)
        ir_path=(AUDIT/'ir'/f'{label}.json').relative_to(REPO).as_posix()
        write(REPO/ir_path,ir.to_dict())
        summaries=[]
        per_root=set()
        for pointer,node in walk_dicts(record['graph']):
            normalized=compiler.normalize_record(node)
            if normalized:
                family={'TaskConfig':'task','PredicateConfig':'predicate','TargetSelector':'target'}[normalized['kind']]
                identity=normalized['concrete_type']
                concrete=normalized.get('structure',{})
                coordinate=(family,identity,concrete.get('start',normalized.get('start')),concrete.get('end',normalized.get('end')))
            elif node.get('type')=='RPG.GameCore.DynamicFloat' and 'tag' in node:
                family,identity,concrete='expression',node['type'],node
                coordinate=(family,identity,node['start'],node['end'])
            else:continue
            if coordinate in per_root:continue
            per_root.add(coordinate)
            bound=compiler.convert(node,'/record'+pointer)
            supported=bound.op in registry.handlers[family]
            status='UNSUPPORTED' if isinstance(bound,UnsupportedSemanticIR) else (
                'CONDITIONAL_REFERENCE' if supported else 'STRUCTURE_ONLY')
            row={'family':family,'type':identity,'stratum':record['stratum'],'graph_identity':record['identity'],
                'source_identity':list(key),'span':list(coordinate[2:]),'pointer':pointer,'support':status,
                'IR_kind':bound.kind,'IR_REPRESENTABLE':True,'ORACLE_PENDING':True,
                'capability_family':taxonomy(family,identity),'native_method_refs':list(bound.authority.native_method_refs),
                'raw_structure':concrete,'node_id':bound.node_id}
            summaries.append({k:v for k,v in row.items() if k!='raw_structure'})
            global_key=(key[0],*coordinate)
            if global_key not in semantic_seen:
                semantic_seen.add(global_key);node_rows.append(row)
        root_rows.append({'source_identity':list(key),'record_identity':record['identity'],
            'source_shard':record['source_shard'],'source_shard_sha256':key[0],
            'record_start':key[1],'record_end':key[2],'root_type':record['graph'].get('type'),
            'stratum':record['stratum'],'skill_joined':key in exact,'graph_hash':record['graph_hash'],
            'canonical_IR_hash':ir.stable_hash(),'decoded_artifact':path,'IR_artifact':ir_path,
            'consumption_status':record['consumption_status'],'compile_status':'IR_REPRESENTABLE',
            'baseline_source_start':(key[0],key[1]) in baseline_starts,
            'semantic_instances':summaries,'native_correct_claimed':False})
        compiled.append((record,ir))
    combat=[n for n in node_rows if n['stratum'] in COMBAT]
    frequencies=collections.Counter((n['family'],n['type']) for n in combat)
    graph_types=collections.defaultdict(set)
    for g in root_rows:
        if g['stratum'] in COMBAT:
            for n in g['semantic_instances']:
                graph_types[(n['family'],n['type'])].add(tuple(g['source_identity']))
    type_rows=[]
    for family,identity in sorted({(n['family'],n['type']) for n in node_rows}):
        rows=[n for n in node_rows if (n['family'],n['type'])==(family,identity)]
        status=collections.Counter(n['support'] for n in rows)
        type_rows.append({'family':family,'type':identity,'global_instances':len(rows),
            'combat_instance_frequency':frequencies[(family,identity)],
            'combat_type_frequency':len(graph_types[(family,identity)]),
            'support_instance_counts':dict(status),'IR_REPRESENTABLE':True,
            'REFERENCE_EXECUTABLE':False,'CONDITIONAL_REFERENCE':status['CONDITIONAL_REFERENCE']>0,
            'STRUCTURE_ONLY':status['STRUCTURE_ONLY']>0,'UNSUPPORTED':status['UNSUPPORTED']>0,
            'ORACLE_PENDING':True,'STRUCTURAL_READER_GAP':False,'capability_family':taxonomy(family,identity)})
    # Actual R13 reference probes: synthetic context only. Missing native inputs
    # remain explicit SemanticGaps; completion is not a legal skill transition.
    aliases_needed={n.payload.get('alias') for _,ir in compiled for n in walk_nodes(ir)
                    if n.op=='RPG.GameCore.TargetAlias'}
    lookup_keys={n.payload['key'] for _,ir in compiled for n in walk_nodes(ir) if n.op=='lookup'}
    state,alias_catalog,policies=fixture(aliases_needed,lookup_keys)
    abilities=collections.defaultdict(list)
    for record,ir in compiled:
        if record['stratum'] in ('ABILITY_CORPUS','PASSIVE_CORPUS'):
            abilities[record['identity']].append(ir)
    catalog={name:values[0] for name,values in abilities.items() if len(values)==1}
    probes=[]
    for record,ir in compiled:
        if record['stratum'] not in COMBAT:continue
        if ir.op!='ability':
            probes.append({'source_identity':list(source_identity(record)),
                'status':'SEMANTIC_GAP','required_capability':'modifier/event root installation and callback lifecycle policy',
                'prefix_tasks_completed':0,'scope':'SYNTHETIC_R13_REFERENCE_CONTEXT'});continue
        runtime=BehaviorRuntime(state,abilities=catalog,aliases=alias_catalog,policies=policies)
        runtime.state.target_context['current_ability']=record['identity']
        runtime.actions['probe']=ir
        try:
            result=runtime.step('probe')
        except (AttributeError,TypeError,ValueError,KeyError) as exc:
            # A discovered shape can expose a reference adapter contract gap.
            # Preserve that observation; never classify a crashing probe as pass.
            probes.append({'source_identity':list(source_identity(record)),
                'status':'REFERENCE_ADAPTER_GAP','required_capability':'generic reference adapter: '+str(exc),
                'prefix_tasks_completed':0,'scope':'SYNTHETIC_R13_REFERENCE_CONTEXT',
                'legal_skill_transition_claimed':False})
            continue
        probes.append({'source_identity':list(source_identity(record)),'status':result.status.value,
            'required_capability':result.gap.required_capability if result.gap else None,
            'primitive':result.gap.task_type if result.gap else None,'gap_node':result.gap.node if result.gap else None,
            'prefix_tasks_completed':len(result.trace),'scope':'SYNTHETIC_R13_REFERENCE_CONTEXT',
            'legal_skill_transition_claimed':False})
    write(AUDIT/'reference_prefix_probes.json',probes)
    first_gaps=collections.Counter(p['required_capability'] for p in probes if p.get('required_capability'))
    # Static serialized suffix is an upper-bound estimate, not scheduler reachability.
    blocked=collections.Counter()
    root_blockers={}
    for g in root_rows:
        if g['stratum'] not in COMBAT:continue
        tasks=sorted([n for n in g['semantic_instances'] if n['family']=='task'],key=lambda n:n['span'][0])
        for i,n in enumerate(tasks):
            if n['support']!='CONDITIONAL_REFERENCE':
                blocked[n['type']]+=len(tasks)-i-1
                root_blockers[tuple(g['source_identity'])]=n['type'];break
    joined_graphs={tuple(j['exact_root_identity'][k] for k in ('source_shard_sha256','record_start','record_end'))
        for j in batch['joins'] if j.get('root_structurally_decoded')}
    # Explicit transparent authored scoring. Presentation tasks retain frequency
    # but are not candidates for the next battle-mechanics subsystem.
    centrality={'DAMAGE':3,'MODIFIER':3,'SCHEDULER':3,'CONTROL_FLOW':3,'RESOURCE':2,
        'PROPERTY':2,'TARGETING':2,'PREDICATE':2,'HEAL':2,'UNKNOWN':1,'PRESENTATION':0}
    confidence={'DAMAGE':0.8,'MODIFIER':0.8,'SCHEDULER':0.7,'CONTROL_FLOW':0.8,'RESOURCE':0.6,
        'PROPERTY':0.7,'TARGETING':0.7,'PREDICATE':0.7,'HEAL':0.8,'UNKNOWN':0.3,'PRESENTATION':0.9}
    cost={'DAMAGE':3,'MODIFIER':3,'SCHEDULER':3,'CONTROL_FLOW':2,'RESOURCE':2,'PROPERTY':2,
        'TARGETING':2,'PREDICATE':2,'HEAL':2,'UNKNOWN':3,'PRESENTATION':1}
    rankings=[]
    for family in sorted({r['capability_family'] for r in type_rows if r['combat_instance_frequency']}):
        types=[r for r in type_rows if r['capability_family']==family and r['combat_instance_frequency']]
        instances=sum(t['combat_instance_frequency'] for t in types)
        roots=set().union(*(graph_types[(t['family'],t['type'])] for t in types))
        blocked_skills=sum(root_blockers.get(k) in {t['type'] for t in types} for k in joined_graphs)
        suffix=sum(blocked[t['type']] for t in types)
        pending=sum(n['capability_family']==family and n['support'] in ('UNSUPPORTED','STRUCTURE_ONLY') for n in combat)
        pending_roots={tuple(n['source_identity']) for n in combat if n['capability_family']==family and n['support'] in ('UNSUPPORTED','STRUCTURE_ONLY')}
        score=round((pending+2*len(pending_roots)+suffix+5*blocked_skills)*centrality[family]*confidence[family]/cost[family],3)
        rankings.append({'family':family,'combat_instances':instances,'affected_graphs':len(roots),
            'unimplemented_or_structure_only_instances':pending,'downstream_blocked_node_upper_bound':suffix,
            'graphs_with_missing_reference_support':len(pending_roots),
            'decoded_skill_roots_with_first_static_blocker':blocked_skills,
            'architectural_centrality':centrality[family],'planning_confidence':confidence[family],
            'native_evidence_cost':cost[family],'score':score})
    rankings.sort(key=lambda x:-x['score'])
    # Registered reference support is still conditional. Rank only subsystems
    # with material absent implementations; do not choose a supported expression
    # family merely for its many serialized literals.
    candidates=[r for r in rankings if r['family']!='PRESENTATION' and r['unimplemented_or_structure_only_instances']>0]
    next_family=candidates[0]['family'] if candidates else 'MORE_CORPUS'
    next_phase={'DAMAGE':'R15 DAMAGE + TOUGHNESS/BREAK DISCOVERY AND PIPELINE',
        'MODIFIER':'R15 MODIFIER + EVENT ENGINE','SCHEDULER':'R15 TURN / AV / ACTION SCHEDULER',
        'CONTROL_FLOW':'R15 TEMPLATE / CONTEXT SEMANTICS','RESOURCE':'R15 RESOURCE + ACTION COST ENGINE'}.get(next_family,'R15 MORE CORPUS EXPANSION')
    baseline_tasks=set(read('data/control/generic_runtime_support_census_v3_20261007_001.json')['known_task_types'])
    new_tasks=sorted({n['type'] for n in combat if n['family']=='task'}-baseline_tasks)
    checkpoint={}
    for title,types in {'damage':{'RPG.GameCore.DamageByAttackProperty','RPG.GameCore.DamageByAttackPropertyNew'},
        'toughness_break':set(),'shield':set(),'action_order_AV':set(),'resource':{'RPG.GameCore.ModifySPNew'}}.items():
        counts={t:frequencies[('task',t)] for t in types if frequencies[('task',t)]}
        checkpoint[title]={'status':'YES' if counts else 'NO / NOT YET DECODED','task_type_counts':counts,
            'semantic_scope':'Serialized structure only; no damage/break/shield/action-order evaluator added'}
    joins=batch['joins']
    for j in joins:
        j['root_ir_compiled']=bool(j.get('root_structurally_decoded'))
        if j.get('root_structurally_decoded'):
            key=tuple(j['exact_root_identity'][k] for k in ('source_shard_sha256','record_start','record_end'))
            p=next(p for p in probes if tuple(p['source_identity'])==key)
            j['synthetic_reference_prefix_probe']={k:v for k,v in p.items() if k not in ('gap_node','source_identity')}
    join_counts={'canonical_avatar_skill_ownership_rows':len(joins),'rows_examined':len(joins),
        'canonical_definition':'Every serialized Avatar.SkillList ownership edge in the pinned canonical AvatarConfig table; no guessed 620-row denominator',
        'unique_skill_ids_in_ownership':len({j['skill_id'] for j in joins}),
        'skill_level_table_rows':batch['skill_level_count'],'unique_skill_ids_in_level_table':batch['unique_skill_table_ids'],
        'exact_owner_config_joins':sum(j.get('owner_config_join')=='EXACT' for j in joins),
        'exact_root_joins':sum(j['status']=='EXACT_ROOT_JOIN' for j in joins),
        'rows_with_structurally_decoded_roots':sum(j.get('root_structurally_decoded',False) for j in joins),
        'unique_structurally_decoded_skill_roots':len(joined_graphs),'IR_compiled_skill_roots':len(joined_graphs),
        'rows_with_IR_compiled_roots':sum(j.get('root_ir_compiled',False) for j in joins),
        'roots_reaching_synthetic_executable_prefix':sum(p['prefix_tasks_completed']>0 for p in probes if tuple(p['source_identity']) in joined_graphs),
        'synthetic_completed_root_probes':sum(p['status']=='COMPLETED' for p in probes if tuple(p['source_identity']) in joined_graphs),
        'REFERENCE_TRANSITION_EXECUTABLE':0,'full_reference_transitions':0,
        'qualification':'Required real actor state and policies unavailable; synthetic prefix/completion probes are not executable skills'}
    oracle=[]
    for rank in candidates[:6]:
        fam=rank['family']
        affected=[t for t in type_rows if t['capability_family']==fam and t['combat_instance_frequency']]
        primitive=max(affected,key=lambda t:t['combat_instance_frequency'])['type']
        question={'DAMAGE':'Which AttackData fields and hooks define damage category, property materialization, mitigation, critical sampling, HP settlement and break settlement, and in what order?',
            'MODIFIER':'When does a decoded modifier install each callback, which owner/caster context does it carry, and which callbacks fire on refresh/removal?',
            'CONTROL_FLOW':'For each serialized float/string/sequence dictionary mask, which caller scopes are inherited, replaced or isolated by IncludeTaskListTemplate?',
            'SCHEDULER':'Which exact barrier releases WaitAnimState/WaitSecond, owns the continuation and authorizes SkillPerformFinish?',
            'RESOURCE':'Which actor/resource store does ModifySPNew mutate and at which settlement boundary?',
            'TARGETING':'What do the retained anonymous target masks mean and which effective context supplies candidate order?'}.get(fam,'Which preserved anonymous fields select the exact comparison/state policy?')
        refs=sorted({ref for n in combat if n['type']==primitive for ref in n['native_method_refs']})
        oracle.append({'generic_primitive':primitive,'planning_family':fam,'exact_semantic_question':question,
            'decoded_frequency':frequencies[('task',primitive)] or frequencies[('target',primitive)] or frequencies[('predicate',primitive)],
            'affected_graphs':sorted([list(k) for k in graph_types[next((t['family'],t['type']) for t in affected if t['type']==primitive)]]),
            'existing_native_evidence':{'reader_refs':refs,'archive':'real_runtime_generic_primitive_ledger_20261007_001.json','scope':'selected archived native cores; serialization does not close effective behavior'},
            'minimum_additional_evidence_needed':'One bounded native method/dispatch chain plus paired state-before/state-after oracle vectors for precisely these fields and hooks; no whole-character reverse request'})
    anonymous=[]
    for n in combat:
        if n['family'] not in ('target','predicate') and n['type']!='RPG.GameCore.AddModifier':continue
        g=n['raw_structure']
        anonymous.append({'type':n['type'],'bitmap':g.get('bitmap'),'field_spans':[{'mask':f.get('mask'),
            'start':f.get('start'),'end':f.get('end'),'value_representation':f.get('values')} for f in g.get('fields',[])],
            'source_identity':n['source_identity'],'surrounding_graph':n['graph_identity'],
            'field_names_assigned':False,'purpose':'Targeted evidence questions; co-occurrence is not semantic proof'})
    write(AUDIT/'anonymous_field_corpus.json',anonymous)
    templates=[l for l in batch['reference_links'] if l['kind']=='template']
    write(AUDIT/'template_structural_joins.json',{'calls':templates,'schema_policy':'Serialized dictionary masks/types retained; inheritance unresolved; existing Behavior TaskIR remains the only task IR',
        'definitions':[{'source_identity':g['source_identity'],'identity':g['record_identity'],'IR_artifact':g['IR_artifact']} for g in root_rows if g['root_type']=='RPG.GameCore.TaskListTemplate'],
        'parameter_layouts':dict(collections.Counter(str(sorted(c.get('serialized_parameter_binding',{}))) for c in templates)),
        'nested_calls':[c for c in templates if any(g['root_type']=='RPG.GameCore.TaskListTemplate' and g['source_identity']==c['caller_source_identity'] for g in root_rows)]})
    write(AUDIT/'modifier_structural_references.json',[l for l in batch['reference_links'] if l['kind']=='modifier'])
    write(AUDIT/'semantic_node_census.json',node_rows)
    corpus={'schema':'generic_runtime_real_combat_corpus/2','change_request':CR,'baseline':{
        'total_roots':baseline['decoded_behavior_graphs'],'ability_roots':baseline['ability_config_records'],
        'modifier_roots':baseline['modifier_graphs'],'alias_roots':baseline['alias_graphs'],
        'skill_exact_joins':baseline['skills_with_proven_owner_root_join']},
        'expanded_counts':stratum_metrics(root_rows),'batch_counts':batch['counts'],'graphs':root_rows,
        'accepted_graphs_IR_compiled':len(root_rows),'canonical_IR_stability':'PASS',
        'deduplication':'source shard SHA256 + exact body start/end; never display name',
        'source_pins':batch['source_pins'],'index_pin':batch['index_pin'],'manifest_sha256':MANIFEST_SHA,
        'passive_links':batch['passive_links'],'monster_boundary':batch['monster_boundary'],
        'record_acceptance':'Exact parent container keys/counts + trusted directory + known dispatch + bounded full body consumption; original full global alias archive retained',
        'scope':batch['scope'],'native_correct_claimed':False,'executable_skill_count_claimed':False}
    census={'schema':'generic_runtime_support_census/4','change_request':CR,'types':type_rows,
        'GLOBAL_CORPUS':metrics(node_rows),'COMBAT_CORPUS':metrics(combat),
        'support_categories':['IR_REPRESENTABLE','REFERENCE_EXECUTABLE','CONDITIONAL_REFERENCE','STRUCTURE_ONLY','ORACLE_PENDING','UNSUPPORTED','STRUCTURAL_READER_GAP'],
        'coverage_definition':'IR representability and registered reference handlers reported separately. REFERENCE_EXECUTABLE requires complete transitions with supplied required state; none qualified.',
        'combat_type_frequency':{f'{f}:{t}':len(graph_types[(f,t)]) for f,t in sorted(frequencies)},
        'combat_instance_frequency':{f'{f}:{t}':n for (f,t),n in sorted(frequencies.items())},
        'first_gap_distribution':dict(first_gaps.most_common()),'first_gap_scope':'Actual runtime probes in synthetic explicit R13 context; not legal skill activation',
        'downstream_blocked_node_estimate':dict(blocked),'estimate_policy':'Static serialized suffix after first task without registered reference handler; upper bound, not execution reachability',
        'structural_reader_gaps':batch['record_gaps'],'native_validated_task_types':[]}
    capability={'schema':'generic_runtime_capability_discovery/1','change_request':CR,
        'new_task_types':new_tasks,'planning_taxonomy':TAXONOMY,'taxonomy_semantic_authority':'PLANNING_ONLY',
        'families_with_new_task_types':sorted({taxonomy('task',t) for t in new_tasks}),
        'new_capability_families':sorted({taxonomy('task',t) for t in new_tasks}
            -{taxonomy('task',t) for t in baseline_tasks}-{'UNKNOWN','PRESENTATION'}),
        'mechanic_checkpoint':checkpoint,'rankings':rankings,'next_subsystem':next_family,'recommended_R15':next_phase,
        'score_formula':'(instances with missing reference support + 2*graphs with missing support + static_suffix_nodes + 5*decoded_skill_roots_blocked) * centrality * confidence / native_evidence_cost; scores are authored planning estimates',
        'ranking_policy':'Combat strata only; exclude presentation from next combat subsystem; require material absent implementations',
        'scheduler_checkpoint':{t:frequencies[('task','RPG.GameCore.'+t)] for t in ('TriggerAbility','WaitAnimState','WaitSecond','WaitTimelineFinish','SkillPerformFinish')},
        'scheduler_semantics':'Invocation/delay/completion nodes present; native barrier release, callback ownership, inserted actions and AV policies unresolved',
        'oracle_questions':oracle,'runtime_primitives_added':[],'reason_no_runtime_addition':'Expanded unsupported damage/task families need native settlement/context evidence; R13 policies retained exactly',
        'monster_boundary':batch['monster_boundary'],'native_correct_claimed':False}
    gaps={'schema':'generic_runtime_semantic_gap_ledger/3','change_request':CR,
        'combat_first_gap_distribution':dict(first_gaps.most_common()),'planning_rankings':rankings,
        'targeted_oracle_questions':oracle,'structural_reader_family_frequency':dict(collections.Counter(
            (g.get('reader_gap_type') or g.get('reader_gap') or g['question']) for g in batch['record_gaps']).most_common()),
        'unknown_fields_preserved':True,'native_correct_claimed':False}
    join_doc={'schema':'generic_runtime_skill_root_join_census/1','change_request':CR,'counts':join_counts,
        'status_counts':batch['join_counts'],'rows':joins,'character_config_counts':batch['character_counts']}
    for name,value in [('generic_runtime_real_combat_corpus_v2',corpus),('generic_runtime_support_census_v4',census),
        ('generic_runtime_capability_discovery_v1',capability),('generic_runtime_semantic_gap_ledger_v3',gaps),
        ('generic_runtime_skill_root_join_census_v1',join_doc)]:
        write(REPO/f'data/control/{name}_{SUFFIX}.json',value)
    write(AUDIT/'summary.json',{'corpus':corpus['expanded_counts'],'skill_joins':join_counts,
        'combat':census['COMBAT_CORPUS'],'new_tasks':new_tasks,'mechanic_checkpoint':checkpoint,
        'rankings':rankings,'next_subsystem':next_family,'recommended_R15':next_phase,
        'first_gap_distribution':census['first_gap_distribution'],
        'template_calls':len(templates),'templates_joined_decoded':sum(l['target_graph_decoded'] for l in templates),
        'modifier_references':sum(l['kind']=='modifier' for l in batch['reference_links']),
        'modifier_references_joined_decoded':sum(l['target_graph_decoded'] for l in batch['reference_links'] if l['kind']=='modifier')})
    print(json.dumps({'corpus':corpus['expanded_counts'],'combat':census['COMBAT_CORPUS'],'next':next_phase},indent=2))


if __name__=='__main__':
    discover()
