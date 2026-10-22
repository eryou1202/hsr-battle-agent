"""Bounded rescan of existing pinned decoded graphs; no new native extraction."""
from __future__ import annotations
import collections
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r24_checks import AUDIT
from r21_checks import read, sha
from r16_dependency_closure import load_catalog, COMBAT, R14
from hsr_battle_agent.battle_ir.behavior import stable_hash


def write(name, document):
    path = AUDIT/name
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    path.write_text(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf-8')


def objects(value, pointer=''):
    if isinstance(value, dict):
        yield pointer, value
        for k, v in value.items():
            yield from objects(v, pointer+'/'+str(k).replace('~','~0').replace('/','~1'))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from objects(v, pointer+'/'+str(i))


def main():
    names = ['joined_skill_dependency_v1', 'catalog_closure_v2',
             'joined_skill_execution_census_v1', 'support_census_v11']
    controls = {n: ROOT/f'data/control/generic_runtime_{n}_20261012_001.json' for n in names}
    previous = {n: read(p) for n,p in controls.items()}
    report = ROOT/'docs/agent/handoffs/generic_runtime_real_skill_root_closure_20261012_001.md'
    report.read_text(encoding='utf-8')
    frozen = previous['support_census_v11']
    assert frozen['frozen_denominators'] == [632,160,161]
    explicit = frozen['R23_explicit']
    assert [explicit[k] for k in ('partial_real_skill_prefix_roots','hp_settled_roots',
            'original_finish_completed_roots','source_closed_unique_roots')] == [73,18,15,0]
    census = read(ROOT/'data/control/generic_runtime_real_combat_corpus_v2_20261008_001.json')
    assert sum(g['stratum'] in COMBAT for g in census['graphs']) == 632
    assert sum(bool(g['skill_joined']) for g in census['graphs']) == 160
    joins = read(ROOT/'data/control/generic_runtime_skill_root_join_census_v1_20261008_001.json')
    assert sum(bool(j.get('root_ir_compiled')) for j in joins['rows']) == 161
    joined = collections.defaultdict(list)
    for row in joins['rows']:
        identity = row.get('exact_root_identity')
        if identity:
            key = tuple(identity[k] for k in ('source_shard_sha256','record_start','record_end'))
            joined[key].append({k:row.get(k) for k in ('avatar_id','skill_id','level','root_ir_compiled')})
    catalog = load_catalog()
    from r13_frozen_reader import SNAPSHOT, MANIFEST_SHA
    assert sha(SNAPSHOT/'SNAPSHOT_MANIFEST.json') == MANIFEST_SHA
    types = collections.Counter(); matched = {}; damage = {}; pins = {}
    for key, record in catalog.records.items():
        graph = record.get('graph')
        if not graph: continue
        assert stable_hash(graph) == record['graph_hash']
        assert record['source_manifest_sha256'] == MANIFEST_SHA
        artifact = record['decoded_artifact']
        pins[artifact] = sha(ROOT/artifact)
        for pointer, obj in objects(graph):
            concrete = obj.get('type')
            if not isinstance(concrete, str) or not concrete.startswith('RPG.'):
                continue
            start,end = obj.get('start'),obj.get('end')
            if type(start) is not int or type(end) is not int: continue
            identity = (record['source_shard_sha256'],start,end,concrete)
            if identity in matched or identity in damage: continue
            types[concrete] += 1
            if not re.search('shield|stance|weakness|toughness|break', concrete, re.I) and \
                    concrete not in ('RPG.GameCore.DamageByAttackProperty','RPG.GameCore.DamageByAttackPropertyNew'):
                continue
            observation = {'concrete_type':concrete, 'source_version':'4.6.51',
                'source_shard_sha256':identity[0], 'body_sha256':stable_hash(obj),
                'source_span':[start,end], 'artifact':artifact, 'artifact_sha256':pins[artifact],
                'json_pointer':'/graph'+pointer, 'reader':obj.get('reader'),
                'record_identity':record['identity'], 'record_source_identity':list(key),
                'config':record.get('entry',{}).get('config',{}).get('path'),
                'canonical_skill_owner_joins':joined.get(tuple(key),[]),
                'unknown_fields':[{'mask':f.get('mask'),'source_span':[f.get('start'),f.get('end')],
                                   'value_body_sha256':stable_hash(f.get('values'))} for f in obj.get('fields',[])],
                'proven_defense_operand_roles':[], 'effective_runtime_semantics':'UNKNOWN',
                'executable_defense_operation':False,
                'uncertainty':'Concrete type and structural span only; no native defensive operand roles or effective executor join'}
            if 'DamageByAttackProperty' in concrete: damage[identity] = observation
            else: matched[identity] = observation
    context = []
    context_paths = [R14/'character_records.json', R14/'owner_tables.json',
        ROOT/'tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/global_alias_decode.json']
    context_pins = {}
    context_record_counts = {}
    for path in context_paths:
        document = read(path)
        relative = path.relative_to(ROOT).as_posix()
        context_pins[relative] = sha(path)
        if path.name == 'owner_tables.json':
            context_record_counts.update({key:len(rows) for key,rows in document.items() if isinstance(rows,list)})
        if path.name == 'character_records.json': context_record_counts['character_configs'] = len(document)
        for pointer,obj in objects(document):
            concrete = obj.get('type')
            if not isinstance(concrete,str) or not concrete.startswith('RPG.') or not re.search(
                    'shield|stance|weakness|toughness|break',concrete,re.I): continue
            if type(obj.get('start')) is not int or type(obj.get('end')) is not int: continue
            context.append({'artifact':relative,'artifact_sha256':context_pins[relative],
                'json_pointer':pointer,'concrete_type':concrete,'source_version':'4.6.51',
                'body_sha256':stable_hash(obj),'source_span':[obj['start'],obj['end']],
                'proven_defense_operand_roles':[], 'source_supported_event_identity':None,
                'uncertainty':'Structural context/selector only; no executable defense operation'})
    r11 = ROOT/'tmp/audit/r11_4651_natasha_semantic_closure_20261005_001'
    metadata = {}
    for name in ('type_field_references.json','runtime_named_methods.json','selected_enums.json',
                 'semantic_type_inventory.json','followup_type_inventory.json','runtime_core_inventory.json'):
        path = r11/name
        doc = read(path)
        metadata[name] = {'artifact_sha256':sha(path),'observations':[
            {'pointer':ptr,'body_sha256':stable_hash(obj), 'name':obj['name'],
             'source_version':'4.6.51','source_span':{'json_pointer':ptr},
             'details':{k:obj[k] for k in ('index','rva','type','offset') if k in obj},
             'authority':'METADATA_CANDIDATE_ONLY','effective_behavior':'UNKNOWN',
             'uncertainty':'Named metadata candidate does not prove active instance, operand role, effective executor or semantics'}
            for ptr,obj in objects(doc) if isinstance(obj.get('name'),str) and
            re.search('shield|stance|weakness|toughness|break',obj['name'],re.I)]}
    # One existing native path, one existing body, zero new selected bodies.
    body = r11/'method_f145660.txt'; lines = body.read_text(encoding='utf-8').splitlines()
    calls = read(r11/'calls_f145660.json')
    exit_calls = [{'pointer':ptr,'observation':obj} for ptr,obj in objects(calls)
                  if (obj.get('method') or {}).get('name') == 'ExitBreakState']
    assert exit_calls and any('18f1414e0' in line.lower() for line in lines)
    native = {'subsystem_paths_examined':1, 'existing_method_bodies_examined':1,
        'new_selected_method_bodies':0, 'dependency_hops':1,
        'observations':[{'source_version':'4.6.51','artifact':body.relative_to(ROOT).as_posix(),
            'body_sha256':sha(body),'source_span':{'lines':[1,len(lines)],'rva_start':'0xF145660'},
            'crossref_artifact':(r11/'calls_f145660.json').relative_to(ROOT).as_posix(),
            'crossref_sha256':sha(r11/'calls_f145660.json'), 'exit_break_call':exit_calls,
            'concrete_native_function_evidenced':True,'effective_runtime_behavior_known':False,
            'observation':'Saved unpatched body has a call to ExitBreakState plus IFix guards',
            'uncertainty':'Call is not recovery timing or current/maximum toughness semantics; active IFix/Lua authority remains unresolved'}],
        'stop_reason':'Bounded existing evidence cannot bind effective defense operands, ordering or values; preserve oracle gaps',
        'provider_or_archive_discovery_reopened':False,'new_registration_archaeology':False}
    background_paths = [ROOT/'data/semantics/4.4.54/full_reconstruction/astra_damage_survival_targeted_evidence_v1.json',
        ROOT/'data/raw/4.4.54/damage_task_prepare_507303_10.txt',
        ROOT/'data/raw/4.4.54/target_damage_hp_504579_10.txt',
        ROOT/'tmp/audit/r10_4651_selected_record_binding_20261003_001/task_dispatcher.json',
        ROOT/'tmp/audit/r11d_4651_live_runtime_semantic_closure_20261007_001/final_semantic_closure.json']
    background = []
    for path in background_paths:
        if not path.exists(): continue
        content = path.read_text(encoding='utf-8-sig')
        background.append({'artifact':path.relative_to(ROOT).as_posix(),'body_sha256':sha(path),
            'source_version':'4.4.54_BACKGROUND' if '/4.4.54/' in path.as_posix() else '4.6.51',
            'source_span':{'lines':[1,len(content.splitlines())]},
            'uncertainty':'Historical/source structural background only; no same-build effective native semantics transferred'})
    task_types = {name:count for name,count in types.items() if re.search('shield|stance|weakness|toughness|break', name,re.I)}
    write('defense_inventory.json', {'schema':'r24_defense_evidence/1','source_version':'4.6.51',
        'product_baseline':'frozen 4.4.54; no version promotion',
        'source_snapshot_manifest_sha256':MANIFEST_SHA,
        'authoritative_control_pins':{p.relative_to(ROOT).as_posix():sha(p) for p in [*controls.values(),report]},
        'baseline_verified':{'combat_roots':632,'joined_unique_roots':160,'joined_rows':161,
            'real_prefix_roots':73,'reference_hp_roots':18,'original_child_finish_roots':15,'source_closed_transitions':0},
        'scope':{'catalog_records':len(catalog.records),'decoded_records':sum(bool(r.get('graph')) for r in catalog.records.values()),
                 'scope_limit':'All existing R16 catalog decoded graphs; undecoded directory entries and undiscovered archives are not claimed'},
        'actual_defense_candidate_types':task_types,'decoded_defense_candidate_instances':len(matched),
        'decoded_defense_candidates':list(matched.values()), 'decoded_damage_candidate_instances':len(damage),
        'additional_context_pins':context_pins,'context_record_counts':context_record_counts,
        'additional_context_candidates':context,
        'monster_config_initialization':'NO_EXECUTABLE_DEFENSE_FIELD_BINDING; names and directory presence do not initialize native state',
        'damage_candidates':list(damage.values()),'metadata_candidates':metadata,
        'source_supported_native_event_identities_bound':[], 'source_backed_defense_operations':0,
        'C_SOURCE_BACKED_DEFENSE_CONTENT':0,
        'missing_families':{family:'NO_EXECUTABLE_OPERAND_BOUND_CONTENT_PROVEN' for family in
            ('SHIELD_APPLICATION','SHIELD_ABSORPTION','TOUGHNESS_REDUCTION','WEAKNESS_BREAK_TRIGGER','BREAK_EFFECT','BREAK_RECOVERY')},
        'conceptual_names_not_assumed':{name:types.get('RPG.GameCore.'+name,0) for name in
                                      ('ReduceToughness','BreakShield','ApplyBreak')},
        'definition_count_not_instance_count':len(catalog.modifier_definitions()),
        'native_investigation':native,'background':background,
        'evidence_levels_distinct':['SOURCE_FILE_EXISTS','STRUCTURAL_FIELD_DECODED','CONCRETE_NATIVE_FUNCTION_EVIDENCED',
                                    'EFFECTIVE_RUNTIME_BEHAVIOR_KNOWN','EXECUTABLE_REFERENCE_POLICY'],
        'decoded_graph_pins':pins, 'native_correctness':'NOT_CLAIMED'})
    print('R24 evidence',len(matched),'defense candidates;',len(damage),'damage candidates; source-backed operations=0',flush=True)


if __name__ == '__main__': main()
