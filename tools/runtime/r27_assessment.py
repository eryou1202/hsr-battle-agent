"""Rank all existing joined roots; exact acquisition chains and parent recovery."""
import collections
from r27_checks import ROOT,AUDIT,write,read,sha
from r23_checks import AUDIT as R23
from r23_reference_fixtures import content
from r27_character import catalog_overlay
from hsr_battle_agent.battle_ir.content_catalog import source_key
from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes

def main():
    original=content();base,owners,characters,joins,corpus=original
    additions=read(AUDIT/'character/catalog_additions.json')
    catalog=catalog_overlay(base,additions)
    prior=read(R23/'joined_dependency.json')
    stable=read(ROOT/'tmp/audit/r24_defense_break_shield_20261021_001/r23/joined_execution_results.json')
    observed={tuple(r['source_identity']):r for r in stable}
    closure=catalog.closure([r['source_identity'] for r in prior['roots']])
    old_reader_sites=[e for e in prior['dependency_sites'] if e['content_class']=='CONTENT_READER_GAP']
    resolved_reader_sites=[catalog.resolve(e) for e in old_reader_sites if catalog.resolve(e)['status']=='EXACT_RESOLVED_COMPILED']
    assert len(old_reader_sites)==117
    write('character/original_reader_site_progress.json',dict(original_structural_reader_sites=117,
        now_exact_compiled_sites=len(resolved_reader_sites),remaining_original_reader_sites=117-len(resolved_reader_sites),
        resolved=resolved_reader_sites,scope='Original R23 117-site denominator only; new transitive sites excluded',
        executable_meaning_implied=False))
    indexed=collections.defaultdict(list)
    for i,e in enumerate(closure['edges']):
        e['site_id']='R27-SITE-'+str(i+1).zfill(5)
        indexed[tuple(e['parent_source_identity'])].append(e)
    stages=read(AUDIT/'character/dependency_stages.json')
    latest={tuple(s['whole_original_parent']['source_identity']):s['whole_original_parent'] for s in stages}
    ranks=[]
    for root in prior['roots']:
        execution=latest.get(tuple(root['source_identity']),observed[tuple(root['source_identity'])])
        queue=[(tuple(root['source_identity']),0)];seen=set();after=[];depths={};finish=0
        while queue:
            at,depth=queue.pop(0)
            if at in seen:continue
            seen.add(at)
            record=catalog.records.get(at,{})
            if record.get('ir'):
                finish+=sum(n.op=='RPG.GameCore.SkillPerformFinish' for n in {n.stable_hash():n for n in walk_nodes(IRNode.from_dict(record['ir']))}.values())
            for e in indexed[at]:
                if e.get('inline'):continue
                after.append(e);depths[e['site_id']]=depth
                if e.get('target_source_identity'):queue.append((tuple(e['target_source_identity']),depth+1))
        missing=[e for e in after if e['status']!='EXACT_RESOLVED_COMPILED']
        dynamic=[op for op in root['closure_types'] if any(t in op for t in ('Dynamic','Property','Modifier','Activated'))]
        rank=dict(root=root['root'],source_identity=root['source_identity'],canonical_binding=root['canonical_binding'],
            canonical_owner_rows=root['canonical_owner_rows'],canonical_IR_hash=root['canonical_IR_hash'],
            exact_available_dependencies=sum(e['status']=='EXACT_RESOLVED_COMPILED' for e in after),
            remaining_gap_sites=len(missing),remaining_gap_depth=max((depths[e['site_id']] for e in missing),default=0),
            original_finish_nodes=finish,
            current_executable_tasks=execution['metrics']['tasks_completed'],current_first_blocker=execution['required_capability'],
            dynamic_provider_types=dynamic,static_runtime_support_scope='Observed stable R23 whole-root prefixes; unvisited branches not assumed supported',
            estimated_work='SOURCE_ACQUISITION_REQUIRED' if any(e['status']=='REFERENCE_NOT_FOUND' for e in missing) else
                'READER_THEN_RUNTIME_CONTEXT' if missing else 'RUNTIME_CONTEXT_AND_EXECUTOR_EVIDENCE',
            unresolved_site_ids=[e['site_id'] for e in missing],
            score_authority='R27 authored prioritization, not native semantics')
        ranks.append(rank)
    ranks.sort(key=lambda r:(bool(r['remaining_gap_sites']),r['remaining_gap_sites'],r['remaining_gap_depth'],
        not bool(r['original_finish_nodes']),-r['current_executable_tasks'],len(r['dynamic_provider_types']),r['root']))
    for i,r in enumerate(ranks):r['rank']=i+1
    roles={}
    for role,key in [('basic_attack','Skill01'),('skill','Skill02'),('ultimate_related','Skill03')]:
        roles[role]=next((r for r in ranks if any(j['skill_trigger_key']==key for j in r['canonical_owner_rows'])),None)
    write('character/all_160_ranked.json',dict(roots=ranks,roles=roles,dependency_sites=closure['edges'],
        view='R27 explicit catalog overlay; frozen inputs unchanged',
        ranking_axes=['available exact sources','remaining gaps','depth','original finish','observed execution support','dynamic/provider requirements','authored work estimate']))
    # Recover parent relationships by source coordinates and serialized references.
    historical=read(ROOT/'tmp/audit/r22_global_turn_engine_20261011_001/execution_traces.json')['traces']
    byhash={g['canonical_IR_hash']:g for g in corpus['graphs']}
    edges=prior['dependency_sites'];parents=[]
    for row in historical:
        if not row.get('source_IR_hash'):continue
        g=byhash.get(row['source_IR_hash'])
        if not g:
            parents.append(dict(trace=row['id'],status='HISTORICAL_IR_NOT_IN_R14_GRAPH_VIEW',IR_hash=row['source_IR_hash']));continue
        key=g['source_identity']
        direct=[j for j in joins['rows'] if j.get('exact_root_identity') and
            [j['exact_root_identity'][k] for k in ('source_shard_sha256','record_start','record_end')]==key]
        callers=[e for e in edges if e.get('target_source_identity')==key]
        canonical_parents=[dict(root=r['root'],binding=r['canonical_binding'],reference_site=e)
            for e in callers for r in prior['roots'] if r['source_identity']==e['parent_source_identity']]
        parents.append(dict(trace=row['id'],root=g['record_identity'],source_identity=key,direct_canonical_owners=direct,
            exact_canonical_parent_calls=canonical_parents,other_serialized_callers=callers,
            previously_completed_actions=row['actions_completed'],full_canonical_skill_implied=False,
            status='EXACT_CHILD_PARENT_RECOVERED_PARENT_STILL_REQUIRED' if canonical_parents else 'NO_DIRECT_CANONICAL_PARENT_PROVEN'))
    write('character/completed_unjoined_parent_recovery.json',parents)
    # Do not repeat any Camera directory search. Carry forward exact evidence,
    # explain provider availability separately from names and directories.
    camera=read(R23/'camera_audit.json')
    tickets=[]
    for old in camera['sites']:
        prior_e=old['prior_evidence'];site=prior_e.get('reference_site_recovered_from_exact_parent',prior_e['reference_site'])
        matching={e['site_id'] for e in prior['dependency_sites'] if e.get('parent_source_identity')==site['parent_source_identity'] and e.get('identity')==prior_e['identity']}
        owner_roots=[dict(root=r['root'],source_identity=r['source_identity'],canonical_owner_rows=r['canonical_owner_rows'],
            canonical_binding=r['canonical_binding']) for r in prior['roots'] if matching.intersection(r['transitive_dependency_sites'])]
        tickets.append(dict(ticket_id='R27-'+old['ticket_id'],workstream='CHARACTER',kind='CAMERA_ORIGINAL_SOURCE_ACQUISITION',
            canonical_owner_roots=owner_roots,
            identity=prior_e['identity'],parent_source_identity=site['parent_source_identity'],parent_graph_hash=site.get('parent_graph_hash'),
            caller_path=old['parent_directory']['config']['path'],caller_directory=old['parent_directory'],
            serialized_lookup_key=site.get('serialized_value'),reference_site=site,
            expected_content_type='Original TurnBasedAbilityConfig body for type-1 reference policy; native effective lookup authority also required',
            expected_body_path='UNKNOWN: no exact path is proven; acquire owning provider/archive mapping rather than derive a filename',
            available_directory_evidence=old['same_name_directory_entries'],
            missing_provider='Exact build external/inline source provider with identity/scope mapping; snapshot lacks full-client Unity/ASB/Lua sources',
            required_runtime_semantics='Original task body, child ownership, barrier effects and completion; no presentation-only authorization',
            current_failure_site=site.get('pointer'),source_classification=old['source_classification'],
            why_unreadable='No trusted serialized body in prior exact directory and inline scope audit; original provider artifact/lookup scope not pinned',
            acquisition_required=dict(build='OSBETAWin4.6.51_20260924-0600_16677734',manifest_pin='b702762039368badf25c1e2c0a3a4eea79d7b8ada79c6ce98a448492a97378ec',
                artifact='Original owning provider/archive plus exact key-to-body record and reader',
                validation=['version/build identity','SHA256 and source spans','exact lookup key and scope','full bounded decode','effective task/executor binding if semantics claimed']),
            no_new_directory_search=True,presentation_noop_authorized=False,status='BLOCKED_ORIGINAL_ARTIFACT_REQUIRED'))
    for attempt in read(AUDIT/'character/phase_attempts.json'):
        if attempt['result']['status']=='ACCEPTED':continue
        entry=attempt['entry'];gap=attempt['result']
        tickets.append(dict(ticket_id='R27-PHASE-'+entry['name'],workstream='CHARACTER',kind='ORIGINAL_READER_REQUIRED',
            identity=entry['name'],source_path=entry['config']['path'],source_identity=list(source_key(entry)),
            expected_content_type='TurnBasedAbilityConfig',serialized_lookup_key=entry['name'],directory_evidence=entry,
            missing_reader=gap.get('reader_gap'),current_failure_site=gap['cursor'],why_unreadable=gap['question'],
            required_original_artifact='Pinned native factory branch/child reader or exact reader schema; source bytes already available',
            runtime_semantics='Original child tasks remain required; structural factory decoding grants no task meaning'))
    refs=[]
    for rec in additions:
        from hsr_battle_agent.battle_ir.content_catalog import walk
        for pointer,node in walk(rec['graph']):
            if node.get('kind')=='external_enum_reference':
                refs.append(dict(ticket_id='R27-JSONENUM-'+str(len(refs)+1),workstream='CHARACTER',kind='ORIGINAL_JSONENUM_PROVIDER_REQUIRED',
                    root=rec['identity'],source_path=rec['entry']['config']['path'],source_identity=list(source_key(rec)),
                    pointer=pointer,span=[node['start'],node['end']],serialized_lookup_key=node['serialized_lookup_keys'],
                    native_reader='0x1E6D6BF0',native_resolver='0x1E6D6E90',native_cache='+0xC580',resource_identity_anchor='Global RVA 0x9BF82B0 passed to 0x1E62C900',
                    source_provider='Original JsonEnum backing table loaded through 0x1E62C900/0x1E6D7C30; exact provider artifact identity unknown',
                    required_original_artifact='Exact 4.6.51 provider resource bytes and key/value identity mapping',
                    behavior='UNRESOLVED; decoded keys are never effective enum values',status='SOURCE_PROVIDER_UNRESOLVED'))
    tickets+=refs
    write('acquisition_tickets.json',tickets)
    write('character/ranking_summary.json',dict(roots=160,roles={k:None if v is None else v['root'] for k,v in roles.items()},
        original_camera_gaps=68,structural_Phase_reader_gaps=sum(a['result']['status']!='ACCEPTED' for a in read(AUDIT/'character/phase_attempts.json')),
        JsonEnum_provider_sites=len(refs),archived_nonempty_prefixes=73,stable_nonempty_prefixes=72))
    print('Ranked 160; exact Camera tickets',68,'JsonEnum provider sites',len(refs),flush=True)

if __name__=='__main__':main()
