"""Systematic bounded player corpus and exact owner/skill/root join expansion."""
from __future__ import annotations

import collections
from r14_corpus import *


def table(assets, schemas, registries, path, reader, header=False):
    asset=assets.lookup(path)
    if not asset:
        raise StructuralGap('required table absent:'+path)
    data,pin=assets.source(asset)
    p=Reader(data,asset['offset'],asset['offset']+asset['length'],schemas,registries)
    if header and p.take(1)!=b'\x00':
        raise StructuralGap('Avatar table header')
    count=p.z()
    if not 0<=count<=100000:
        raise StructuralGap('table count')
    rows=[]
    for i in range(count):
        graph=p.read(reader)
        rows.append({'ordinal':i,'graph':graph,'source_shard':asset['source_shard'],
                     'source_shard_sha256':pin['sha256'],'asset':asset})
    if p.cursor!=p.end:
        raise StructuralGap('table incomplete consumption:'+path)
    return rows


def join_skill(avatar, skill_rows, character, directories, decoded):
    """Only exact decoded relation values; never filename or actor-name joins."""
    aid=scalar(avatar['graph'],1)
    result=[]
    for child in children(avatar['graph'],65536):
        sid=child.get('value')
        row={'avatar_id':aid,'skill_id':sid,'status':'STRUCTURAL_READER_GAP',
             'evidence':[{'relation':'Avatar.SkillList','source_shard_sha256':avatar['source_shard_sha256'],
                          'record_start':avatar['graph']['start'],'field_mask':65536,
                          'value':sid}]}
        levels=skill_rows.get(sid,[])
        if not levels:
            row['question']='Skill record absent'
            result.append(row); continue
        keys={scalar(s['graph'],64) for s in levels}
        row['skill_levels_examined']=len(levels)
        row['skill_level_spans']=[[s['graph']['start'],s['graph']['end']] for s in levels]
        if len(keys)!=1 or None in keys:
            row['question']='SkillTriggerKey absent or level disagreement'
            result.append(row); continue
        key=next(iter(keys))
        row['skill_trigger_key']=key
        row['evidence'].append({'relation':'Skill.SkillTriggerKey','field_mask':64,'value':key,
            'source_shard_sha256':levels[0]['source_shard_sha256'],
            'record_start':levels[0]['graph']['start']})
        if character is None or character.get('status')!='ACCEPTED':
            row['status']='CHARACTER_CONFIG_JOIN_GAP'
            row['question']=character.get('question') if character else 'Character config not present'
            result.append(row); continue
        slots=[s for s in children(character['graph'],1<<25) if scalar(s,1)==key]
        if len(slots)!=1:
            row['status']='SKILL_CONFIG_FOUND_NO_ROOT' if not slots else 'OTHER_EXPLICIT_STATUS'
            row['question']='Exact skill slot absent or ambiguous'
            result.append(row); continue
        slot=slots[0]
        row['owner_config_join']='EXACT'
        root=scalar(slot,1<<38)
        row['evidence'].append({'relation':'CharacterConfig.SkillConfig.Name','field_mask':1,
            'source_shard_sha256':character['source_shard_sha256'],'record_start':slot['start'],'value':key})
        if not root:
            row['status']='NO_ENTRY_ABILITY'
            result.append(row); continue
        row['root_reference']=root
        row['evidence'].append({'relation':'SkillConfig.EntryAbility','field_mask':1<<38,
            'source_shard_sha256':character['source_shard_sha256'],'record_start':slot['start'],
            'field_start':field(slot,1<<38)['start'],'field_end':field(slot,1<<38)['end'],'value':root})
        candidates=[d for d in directories if d['name']==root and d['type']==1]
        # A global root identity is accepted only if unique source coordinates.
        unique={(d['source_shard_sha256'],d['absolute'],d['record_end']):d for d in candidates}
        if len(unique)!=1:
            row['status']='ROOT_REFERENCE_FOUND_GRAPH_UNDECODED'
            row['question']='Directory identity missing or ambiguous'
            result.append(row); continue
        candidate=next(iter(unique.values()))
        row['exact_root_identity']={'source_shard_sha256':candidate['source_shard_sha256'],
            'record_start':candidate['absolute'],'record_end':candidate['record_end']}
        found=decoded.get((candidate['source_shard_sha256'],candidate['absolute'],candidate['record_end']))
        row['status']='EXACT_ROOT_JOIN'
        row['root_structurally_decoded']=found is not None
        row['root_ir_compiled']=False
        row['reference_execution']='NOT_EVALUATED_NO_REQUIRED_REFERENCE_STATE'
        row['evidence'].append({'relation':'EntryAbility->serialized directory identity',
            'directory_hash':candidate['layout']['hash'],'ordinal':candidate['ordinal'],'value':root})
        if found is None:
            row['graph_status']='STRUCTURAL_READER_GAP_OR_FRAMING_GAP'
        result.append(row)
    return result


def references(graph):
    """Serialized structural roles already recovered by R13; no semantics inferred."""
    for pointer,node in walk_dicts(graph):
        if node.get('type')=='RPG.GameCore.AddModifier' and node.get('fields'):
            f=field(node,8)
            value=f['values'][0] if f else {}
            identity=scalar(value,4) if value.get('type')=='RPG.GameCore.DynamicString' and value.get('bitmap')==4 else None
            if isinstance(identity,str):
                yield {'kind':'modifier','identity':identity,'pointer':pointer,'node_start':node.get('start')}
        if node.get('type')=='RPG.GameCore.IncludeTaskListTemplate' and node.get('fields'):
            identity=scalar(node,2)
            if isinstance(identity,str):
                yield {'kind':'template','identity':identity,'pointer':pointer,'node_start':node.get('start'),
                    'serialized_parameter_binding':{str(mask):field(node,mask) for mask in (4,8,32) if field(node,mask)},
                    'serialized_caller_context':field(node,16),
                    'caller_context_source':'CALL_SITE_SERIALIZED_CONTEXT',
                    'inheritance_policy':'UNRESOLVED'}


def expand():
    assets=Assets()
    schemas,registries=machinery(assets)
    avatars=table(assets,schemas,registries,'BakedConfig/ExcelOutputGameCore/AvatarConfig.bytes',0x1e365280,True)
    skills=table(assets,schemas,registries,'BakedConfig/ExcelOutputGameCore/AvatarSkillConfig.bytes',0x1e36ca80)
    skills_by_id=collections.defaultdict(list)
    for row in skills:
        skills_by_id[scalar(row['graph'],1)].append(row)
    write(AUDIT/'owner_tables.json',{'avatars':avatars,'skills':[{'ordinal':s['ordinal'],
        'skill_id':scalar(s['graph'],1),'trigger_key':scalar(s['graph'],64),
        'level':scalar(s['graph'],16),'start':s['graph']['start'],'end':s['graph']['end'],
        'source_shard_sha256':s['source_shard_sha256']} for s in skills]})
    characters,paths={},set()
    for avatar in avatars:
        path=scalar(avatar['graph'],256)
        if not isinstance(path,str):
            continue
        baked='BakedConfig/'+path.removesuffix('.json')+'.bytes'
        e=assets.lookup(baked)
        result={'path':baked,'status':'STRUCTURAL_READER_GAP','question':'outer identity absent'}
        if e:
            data,pin=assets.source(e)
            p=Reader(data,e['offset'],e['offset']+e['length'],schemas,registries)
            result.update(asset=e,source_shard_sha256=pin['sha256'])
            try:
                if p.u()!=0:
                    raise StructuralGap('unproven CharacterConfig root dispatch')
                g=p.read(0x1e4a0200)
                if p.cursor!=p.end:
                    raise StructuralGap('CharacterConfig incomplete root consumption')
                result.update(status='ACCEPTED',graph=g,question=None)
            except (StructuralGap,UnicodeError) as exc:
                result.update(question=str(exc),cursor=p.cursor,
                    reader_gap=getattr(exc,'reader_gap',None),reader_gap_type=getattr(exc,'reader_gap_type',None))
        characters[scalar(avatar['graph'],1)]=result
        # Candidate discovery rule checked by exact outer hash membership. It is
        # deliberately not used by join_skill, which joins decoded relation fields.
        candidate=baked.replace('/ConfigCharacter/','/ConfigAbility/')
        if candidate.endswith('_Config.bytes'):
            paths.add(candidate.removesuffix('_Config.bytes')+'_Ability.bytes')
    common=read(R11C+'mandatory_common_modifier_decode.json')['source']['path']
    paths.add(common)
    write(AUDIT/'character_records.json',list(characters.values()))
    directories,dir_gaps,discovery=[],[],[]
    for path in sorted(paths):
        config=assets.lookup(path)
        layout=assets.lookup(path.removesuffix('.bytes')+'.layout.bytes')
        discovery.append({'path':path,'config_found':config is not None,'layout_found':layout is not None,
            'discovery_only':'avatar decoded JsonPath transform or R11 proven common path'})
        if not config or not layout:
            continue
        data,pin=assets.source(config)
        if config['source_shard']!=layout['source_shard']:
            dir_gaps.append({'path':path,'question':'cross-shard layout not supported'}); continue
        try:
            es=directory(data,layout,config,schemas,registries)
            directories.extend({**e,'config':config,'layout':layout,'source_shard':config['source_shard'],
                'source_shard_sha256':pin['sha256']} for e in es)
        except (StructuralGap,UnicodeError) as exc:
            dir_gaps.append({'path':path,'question':str(exc)})
    write(AUDIT/'directory_inventory.json',{'discovery':discovery,'entries':directories,'gaps':dir_gaps})
    accepted,gaps=[],[]
    attempted=set()
    def attempt(e,reason):
        key=(e['source_shard_sha256'],e['absolute'],e['record_end'])
        if key in attempted:
            return
        attempted.add(key)
        data,_=assets.source(e['config'])
        decoded=decode_entry(data,e,schemas,registries)
        envelope={'identity':e['name'],'entry':e,'source_shard':e['source_shard'],
            'source_shard_sha256':e['source_shard_sha256'],'record_start':e['absolute'],
            'record_end':e['record_end'],'reason':reason,'source_manifest_sha256':MANIFEST_SHA,
            **decoded}
        (accepted if decoded['status']=='ACCEPTED' else gaps).append(envelope)
    # Every reachable player/common ability entry is attempted, independent of names.
    for entry in directories:
        if entry['type']!=0:
            attempt(entry,'SYSTEMATIC_ABILITY_ENUMERATION')
    # Recursively decode only modifiers with exact serialized reference identities.
    links=[]
    seen_ref=set()
    cursor=0
    while cursor < len(accepted):
        record=accepted[cursor];cursor+=1
        for ref in references(record['graph']):
            ref_key=(source_identity(record),ref['pointer'],ref['identity'])
            if ref_key in seen_ref:
                continue
            seen_ref.add(ref_key)
            matches=[e for e in directories if e['name']==ref['identity'] and
                     (e['type']==0 if ref['kind']=='modifier' else e['type']==2)]
            unique={(e['source_shard_sha256'],e['absolute'],e['record_end']):e for e in matches}
            link={**ref,'caller_source_identity':list(source_identity(record)),
                'status':'EXACT_DIRECTORY_IDENTITY' if len(unique)==1 else 'REFERENCE_JOIN_GAP'}
            if len(unique)==1:
                entry=next(iter(unique.values()))
                link['target_source_identity']=[entry['source_shard_sha256'],entry['absolute'],entry['record_end']]
                attempt(entry,'DIRECT_SERIALIZED_MODIFIER_REFERENCE' if ref['kind']=='modifier' else 'TEMPLATE_REFERENCE')
            links.append(link)
    # Preserve the preexisting decoded modifier corpus, even unreferenced records.
    baseline=read('data/control/generic_runtime_real_content_corpus_v1_20261007_001.json')
    baseline_modifiers={g['record_identity'] for g in baseline['graphs'] if 'Modifier' in (g['root_type'] or '')}
    for e in directories:
        if e['type']==0 and e['name'] in baseline_modifiers:
            attempt(e,'R13_BASELINE_MODIFIER')
    accepted=deduplicate(accepted)
    by_source={source_identity(r):r for r in accepted}
    for link in links:
        link['target_graph_decoded']=tuple(link.get('target_source_identity',[])) in by_source
    joins=[j for avatar in avatars for j in join_skill(avatar,skills_by_id,
        characters.get(scalar(avatar['graph'],1)),directories,by_source)]
    passive_links=[]
    for aid,character in characters.items():
        if character['status']!='ACCEPTED':
            continue
        # CharacterConfig mask 2**26 installs serialized ability identifiers;
        # structural presence does not prove any real actor's active callbacks.
        for c in children(character['graph'],1<<26):
            identity=c.get('value')
            matching=[e for e in directories if e['name']==identity and e['type']==1]
            coords={(e['source_shard_sha256'],e['absolute'],e['record_end']) for e in matching}
            passive_links.append({'avatar_id':aid,'identity':identity,'field_mask':1<<26,
                'character_source_shard_sha256':character['source_shard_sha256'],
                'field_span':[field(character['graph'],1<<26)['start'],field(character['graph'],1<<26)['end']],
                'target_source_identity':list(next(iter(coords))) if len(coords)==1 else None,
                'status':'CONTENT_GRAPH_PRESENT' if len(coords)==1 and next(iter(coords)) in by_source else 'REFERENCE_JOIN_GAP',
                'activation':'ACTIVE_IN_ANY_REAL_ACTOR_UNKNOWN'})
    passive_sources={tuple(l['target_source_identity']) for l in passive_links if l['status']=='CONTENT_GRAPH_PRESENT'}
    for r in accepted:
        kind=r['entry']['type']
        r['stratum']='MODIFIER_CORPUS' if kind==0 else (
            'PASSIVE_CORPUS' if source_identity(r) in passive_sources else (
            'ABILITY_CORPUS' if kind==1 else ('ALIAS_CORPUS' if kind==3 else 'OTHER_RUNTIME_CONFIG')))
    result={'schema':'real_combat_batch/1','change_request':CR,'source_version':'4.6.51',
        'accepted':accepted,'record_gaps':gaps,'reference_links':links,'passive_links':passive_links,
        'joins':joins,'avatar_count':len(avatars),'skill_level_count':len(skills),
        'unique_skill_table_ids':len(skills_by_id),'directory_entries':len(directories),
        'counts':dict(collections.Counter(['ACCEPTED']*len(accepted)+[g['status'] for g in gaps])),
        'character_counts':dict(collections.Counter(c['status'] for c in characters.values())),
        'join_counts':dict(collections.Counter(j['status'] for j in joins)),
        'source_pins':[pin for _,pin in assets.cache.values()],
        'index_pin':assets.index_pin,'monster_boundary':'MONSTER_BEHAVIOR_CORPUS_NOT_YET_BOUND',
        'scope':'All exact layout assets discoverable from all 95 decoded Avatar.JsonPath rows, plus proven common asset; opaque outer hashes without decoded paths remain unenumerated'}
    write(AUDIT/'expanded_decoded_records.json',result)
    print(json.dumps({k:result[k] for k in ('counts','character_counts','join_counts','directory_entries','avatar_count','unique_skill_table_ids')},indent=2))
    return result


if __name__=='__main__':
    expand()
