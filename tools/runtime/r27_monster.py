"""Pinned Monster tables, exact numerical ownership and original root recovery."""
from __future__ import annotations
import subprocess
import sys
from r27_checks import ROOT, AUDIT, write, read, sha
from r27_reader import Reader, machinery
from r14_corpus import Assets, scalar, children, directory, digest
from r14_discovery import canonical_compile
from hsr_battle_agent.battle_ir.content_catalog import ContentCatalog, source_key

TABLES=[('MonsterConfig',0x1e7eeaa0,False),('MonsterTemplateConfig',0x1e7f6f70,True),('MonsterSkillConfig',0x1e7f49e0,False)]

def table(assets,name,rva,header):
    asset=assets.lookup('BakedConfig/ExcelOutputGameCore/'+name+'.bytes')
    data,pin=assets.source(asset)
    attempts=[]
    for retry in range(10):
        schemas,dispatch=machinery()
        p=Reader(data,asset['offset'],asset['offset']+asset['length'],schemas,dispatch)
        if header:assert p.u()==0
        count=p.z();rows=[];gap=None
        try:
            for _ in range(count): rows.append(p.read(rva))
            assert p.cursor==p.end,'full original table consumption required'
        except (ValueError,AssertionError) as exc:
            gap=dict(cursor=p.cursor,question=str(exc),reader_gap=getattr(exc,'reader_gap',None))
        attempts.append(dict(decoded=len(rows),gap=gap))
        if not gap:break
        reader=gap['reader_gap']
        if not reader or any(a['gap'] and a['gap']['reader_gap']==reader for a in attempts[:-1]):break
        result=subprocess.run(['node','tools/runtime/r27_sources.cjs',reader],cwd=ROOT,capture_output=True)
        (AUDIT/'monster'/f'{name}_reader_retry_{retry}.txt').write_bytes(result.stdout+result.stderr)
        if result.returncode:break
    doc=dict(asset=asset,pin=pin,count=count,decoded=len(rows),complete=not gap and p.cursor==p.end,rows=rows,gap=gap,attempts=attempts)
    write('monster/'+name+'_table.json',doc)
    print(name,'decoded',len(rows),'/',count,'complete',doc['complete'],'gap',gap,flush=True)
    return doc

def config(assets,path):
    asset=assets.lookup(path)
    if not asset:return dict(path=path,status='INDEX_ABSENT')
    data,pin=assets.source(asset);schemas,dispatch=machinery()
    p=Reader(data,asset['offset'],asset['offset']+asset['length'],schemas,dispatch)
    try:
        assert p.u()==0,'CharacterConfig original root discriminator'
        graph=p.read(0x1e4a0200)
        assert p.cursor==p.end,'CharacterConfig full consumption'
        return dict(path=path,status='ACCEPTED',asset=asset,pin=pin,graph=graph,source_shard=asset['source_shard'],source_shard_sha256=pin['sha256'])
    except (ValueError,AssertionError) as exc:
        return dict(path=path,status='READER_GAP',asset=asset,pin=pin,cursor=p.cursor,
                    question=str(exc),reader_gap=getattr(exc,'reader_gap',None))

def root(assets,entry):
    from r27_character import decode
    result=decode(assets,entry)
    envelope=dict(identity=entry['name'],entry=entry,source_shard=entry['source_shard'],
        source_shard_sha256=entry['source_shard_sha256'],record_start=entry['absolute'],record_end=entry['record_end'],**result)
    if result['status']!='ACCEPTED':return envelope
    name='monster/decoded/'+entry['name']+'.json';write(name,envelope)
    path=(AUDIT/name).relative_to(ROOT).as_posix()
    ledger=read(ROOT/'data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    _,ir=canonical_compile(envelope,path,ledger)
    write('monster/ir/'+entry['name']+'.json',ir.to_dict())
    envelope.update(ir=ir.to_dict(),canonical_IR_hash=ir.stable_hash(),decoded_artifact=path,
        IR_artifact=(AUDIT/'monster/ir'/f'{entry["name"]}.json').relative_to(ROOT).as_posix())
    return envelope

def main():
    (AUDIT/'monster').mkdir(parents=True,exist_ok=True)
    assets=Assets();tables={n:table(assets,n,r,h) for n,r,h in TABLES}
    templates={scalar(g,4):g for g in tables['MonsterTemplateConfig']['rows']}
    skills={scalar(g,1):g for g in tables['MonsterSkillConfig']['rows']}
    assert len(skills)==tables['MonsterSkillConfig']['decoded']
    # Three independent simple content paths, chosen by original skill-list size.
    seen=set();selected=[];configs=[];directory_receipts=[];records=[];joins=[]
    rows=sorted(tables['MonsterConfig']['rows'],key=lambda g:(len(children(g,1<<31)),scalar(g,16)))
    for row in rows:
        template=templates.get(scalar(row,32))
        if not template:continue
        original_path=scalar(template,4096)
        if not original_path:continue
        path='BakedConfig/'+original_path.removesuffix('.json')+'.bytes'
        if path in seen:continue
        # Avoid the first complex boss family; the same rule applies to all rows.
        if not children(row,1<<31):continue
        seen.add(path)
        cfg=config(assets,path);configs.append(cfg)
        if cfg['status']!='ACCEPTED':
            print('CONFIG GAP',path,cfg.get('reader_gap'),flush=True)
            if len(configs)>=12:break
            continue
        selected.append(dict(monster_id=scalar(row,16),template_id=scalar(row,32),graph=row,
            source_shard=tables['MonsterConfig']['asset']['source_shard'],
            source_shard_sha256=tables['MonsterConfig']['pin']['sha256'],
            template=template,character_config=path))
        candidate=path.replace('/ConfigCharacter/','/ConfigAbility/').removesuffix('_Config.bytes')+'_Ability.bytes'
        asset=assets.lookup(candidate);layout=assets.lookup(candidate.removesuffix('.bytes')+'.layout.bytes')
        receipt=dict(candidate_path=candidate,discovery_only=True,config_found=bool(asset),layout_found=bool(layout))
        directory_receipts.append(receipt)
        if asset and layout:
            data,pin=assets.source(asset);schemas,dispatch=machinery()
            try:
                entries=[dict(**e,config=asset,layout=layout,source_shard=asset['source_shard'],source_shard_sha256=pin['sha256'])
                    for e in directory(data,layout,asset,schemas,dispatch)]
            except ValueError as exc:receipt['gap']=str(exc);entries=[]
            receipt['entries']=entries
            # Decode only the exact selected slot and its own serialized dependencies.
            from hsr_battle_agent.battle_ir.content_catalog import references
            slot_by_key={scalar(s,1):s for s in children(cfg['graph'],1<<25)}
            queue=[]
            for sid_node in children(row,1<<31):
                sid=sid_node['value'];skill=skills.get(sid)
                if not skill:continue
                trigger=scalar(skill,4);slot=slot_by_key.get(trigger)
                if not slot:continue
                entry_name=scalar(slot,1<<38)
                matches=[e for e in entries if e['type']==1 and e['name']==entry_name]
                join=dict(monster_id=scalar(row,16),skill_id=sid,trigger_key=trigger,entry_ability=entry_name,
                    monster_span=[row['start'],row['end']],template_id=scalar(row,32),template_span=[template['start'],template['end']],
                    skill_span=[skill['start'],skill['end']],character_path=path,skill_config_span=[slot['start'],slot['end']],
                    ownership_field_mask=1<<31,trigger_field_mask=4,entry_field_mask=1<<38,
                    source_shard_sha256=tables['MonsterConfig']['pin']['sha256'],
                    status='EXACT_MONSTER_SKILL_ROOT_JOIN' if len(matches)==1 else 'DIRECTORY_IDENTITY_GAP',
                    exact_root_identity=list(source_key(matches[0])) if len(matches)==1 else None,native_correctness='NOT_CLAIMED')
                joins.append(join)
                if len(matches)==1:queue.append(matches[0])
            visited=set()
            while queue and len(visited)<24:
                entry=queue.pop(0);key=source_key(entry)
                if key in visited:continue
                visited.add(key);rec=root(assets,entry);records.append(rec)
                if rec.get('graph'):
                    for site in references(rec['graph']):
                        matches=[e for e in entries if e['type']==1 and e['name']==site.get('identity')]
                        if len(matches)==1:queue.append(matches[0])
        if len(selected)>=3:break
    write('monster/selected_actors.json',dict(actors=selected))
    write('monster/character_configs.json',configs)
    write('monster/directories.json',directory_receipts)
    write('monster/root_records.json',records)
    write('monster/exact_joins.json',joins)
    write('monster/recovery_summary.json',dict(monster_records_decoded=tables['MonsterConfig']['decoded'],
        monster_table_complete=tables['MonsterConfig']['complete'],template_records_decoded=tables['MonsterTemplateConfig']['decoded'],
        skill_records_decoded=tables['MonsterSkillConfig']['decoded'],selected_actors=len(selected),
        monster_skill_root_joins=sum(j['status']=='EXACT_MONSTER_SKILL_ROOT_JOIN' for j in joins),
        original_ability_bodies_decoded=sum(bool(r.get('ir')) for r in records),
        AI_rules_decoded=0,AI_semantics_supported=0,original_actions_executed=0))
    print('Monster exact joins',len(joins),'decoded roots',sum(bool(r.get('ir')) for r in records),flush=True)

if __name__=='__main__':main()
