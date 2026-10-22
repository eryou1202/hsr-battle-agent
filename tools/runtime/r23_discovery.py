"""Bounded R23 source audit: two new path families, existing readers only."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r23_checks import AUDIT
from r21_checks import read, sha
from r14_corpus import Assets, directory, decode_entry, MANIFEST_SHA
from r16_dependency_closure import load_catalog, AUDIT as R16, R14
from hsr_battle_agent.battle_ir.content_catalog import source_key, walk, stable_hash, references


def write(name, value):
    import json
    path = AUDIT/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def machinery():
    schemas = {int(s['rva'], 16): s for s in read(R14/'reader_schemas.json') if s.get('rva')}
    for s in read(R16/'local_reader_schemas.json'):
        s = copy.deepcopy(s)
        for f in s.get('fields', []): f['mask'] = int(f['mask'])
        schemas[int(s['rva'], 16)] = s
    schemas[0x1eb95230] = {'kind':'wrapper','type':'RPG.GameCore.TurnBasedModifierConfig','child':0x1eb95390}
    dispatch = {int(r,16): {int(k):int(v,16) for k,v in t.items()}
                for r,t in read(R14/'reader_dispatch.json').items()}
    return schemas, dispatch


def main():
    prior = read(R16/'phase_camera_audit.json')
    assert len(prior['Camera']) == 68
    catalog = load_catalog()
    for old in prior['Camera']:
        if old['reference_site'].get('parent_source_identity'): continue
        matches = [(r,s) for r in catalog.records.values() if r.get('graph')
                   for s in references(r['graph']) if not s.get('inline') and s.get('identity')==old['identity']]
        assert len(matches)==1, len(matches)
        parent,site = matches[0]
        old['reference_site_recovered_from_exact_parent'] = {**site,
            'parent_source_identity':list(source_key(parent)), 'parent_graph_hash':parent['graph_hash']}
    assets = Assets()
    schemas, dispatch = machinery()
    chars = read(R14/'character_records.json')
    entries = [e for bucket in catalog.directories.values() for e in bucket.values()]
    new_entries, new_records, candidates = [], [], []
    # R16's ConfigCamera / suffix products are deliberately not repeated.
    # These two hypothesized split-runtime path families are discovery ONLY.
    parents = {tuple(r.get('reference_site_recovered_from_exact_parent',r['reference_site'])['parent_source_identity']) for r in prior['Camera']}
    parent_entries = [e for e in entries if source_key(e) in parents]
    for path in sorted({e['config']['path'] for e in parent_entries}):
        for family, candidate in [
            ('CLIENT_SPLIT', path.removesuffix('_Ability.bytes')+'_Ability_Client.bytes'),
            ('CAMERA_SUBDIRECTORY', path.replace('/Avatar/', '/Avatar/Camera/'))]:
            config = assets.lookup(candidate)
            evidence = {'family':family,'candidate_path':candidate,'index_found':bool(config),
                        'discovery_only':True,'accepted_identity':False}
            candidates.append(evidence)
            if not config: continue
            layout = assets.lookup(candidate.removesuffix('.bytes')+'.layout.bytes')
            evidence['layout_found'] = bool(layout)
            if not layout: continue
            data,pin = assets.source(config)
            try:
                found = directory(data,layout,config,schemas,dispatch)
            except ValueError as exc:
                evidence['reader_gap'] = str(exc); continue
            for d in found:
                new_entries.append({**d,'config':config,'layout':layout,
                    'source_shard':config['source_shard'],'source_shard_sha256':pin['sha256']})
    assert len({c['family'] for c in candidates}) <= 2
    rows = []
    for ordinal, old in enumerate(prior['Camera']):
        site = old.get('reference_site_recovered_from_exact_parent',old['reference_site'])
        parent = catalog.records[tuple(site['parent_source_identity'])]
        # Check actual serialized parent scope and every already proven directory,
        # including other record types; a CharacterConfig string is no body.
        exact_chars = [{'artifact':str(R14.relative_to(ROOT)/'character_records.json'),
            'path':c['path'],'source_sha256':c['source_shard_sha256'],'pointer':p,
            'span':[n.get('start'),n.get('end')],'record_type':c['graph'].get('type'),
            'value':n['value'],'body_identity_proven':False}
            for c in chars if c['status']=='ACCEPTED' for p,n in walk(c['graph'])
            if n.get('kind')=='string' and n.get('value')==old['identity']]
        same_keys = [e for e in entries+new_entries if e['name']==old['identity']]
        inline = [d for (name,_), bucket in catalog.definitions.items() if name==old['identity'] for d in bucket.values()]
        resolved = catalog.resolve(site)
        classification = ('EXACT_SOURCE_FOUND' if resolved['status']=='EXACT_RESOLVED_COMPILED' else
            'SOURCE_EXISTS_READER_UNSUPPORTED' if resolved['status']=='EXACT_REFERENCE_READER_GAP' else
            'INLINE_OR_PARENT_SCOPE_REQUIRED' if inline else
            'IDENTITY_AMBIGUOUS' if resolved['status']=='AMBIGUOUS_REFERENCE' else
            'SEMANTICALLY_UNRESOLVED' if same_keys else 'EXACT_SOURCE_NOT_FOUND')
        rows.append({'ticket_id':f'R23-CAMERA-{ordinal+1:03d}','prior_evidence':old,
            'prior_artifact_sha256':sha(R16/'phase_camera_audit.json'),
            'parent_directory':parent['entry'],'expected_record_type':1,
            'expected_record_type_authority':'R16 TriggerAbility reference policy, not spelling',
            'same_name_directory_entries':same_keys,'inline_candidates':inline,
            'character_declarations':exact_chars,'source_classification':classification,
            'behavior_classification':'UNKNOWN','blocker_class':'CONTENT_NOT_FOUND',
            'lookup_scope':'ALL_2672_TRUSTED_ENTRIES_PLUS_TWO_BOUNDED_FAMILIES',
            'next_evidence':'exact type-1 directory or serialized inline body + lookup scope; native effective lookup if absent',
            'presentation_noop_authorized':False,'resolved':resolved['status']=='EXACT_RESOLVED_COMPILED'})
    write('camera_audit.json', {'sites':rows,'candidate_paths':candidates,
        'new_source_path_families':2,'new_directories':new_entries,
        'source_manifest_sha256':MANIFEST_SHA,'index_pin':assets.index_pin,
        'prior_candidate_audit_sha256':sha(R16/'directory_inventory.json'),
        'stop':'No exact body recovered with approved source machinery; stop camera discovery. No provider/archive/IFix/Lua research.'})
    phase = []
    for old in prior['Phase']:
        if old['after_status']=='EXACT_RESOLVED_COMPILED': continue
        entry = old['reference_site']['resolved_directory_identity']
        data,pin = assets.source(entry['config'])
        assert pin['sha256']==entry['source_shard_sha256']
        result = decode_entry(data,entry,schemas,dispatch)
        phase.append({'root':old['root'],'identity':old['identity'],'prior':old,
            'source_identity':list(source_key(entry)),'source_pin':pin,'result':result,
            'blocker_class':'CONTENT_READER_GAP' if result['status']!='ACCEPTED' else 'EXACT_CONTENT_PRESENT',
            'reader_policy':'EXISTING_R14_R16_SCHEMAS_ONLY; no guessed inactive field'})
    assert len(phase)==7
    write('phase_retry.json', phase)
    print('Camera',len(rows),'exact recovered',sum(r['resolved'] for r in rows),
          'Phase retries',len(phase),'decoded',sum(r['result']['status']=='ACCEPTED' for r in phase),flush=True)


if __name__ == '__main__': main()
