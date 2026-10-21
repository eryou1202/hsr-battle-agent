"""Bounded real dependency closure, exact readers and canonical existing IR."""
from __future__ import annotations
import collections
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from hsr_battle_agent.battle_ir.content_catalog import ContentCatalog, references, source_key
from hsr_battle_agent.battle_ir.behavior import IRNode, walk_nodes
from r14_corpus import Assets, Reader, directory, decode_entry, digest, MANIFEST_SHA
from r14_discovery import canonical_compile
from r16_checks import AUDIT, sha, write

SUFFIX='20261008_001'
CR='CR-R16-ABILITY-DEPENDENCY-CATALOG-CLOSURE-20261008-001'
R14=ROOT/'tmp/audit/r14_real_combat_corpus_20261008_001'
R15=ROOT/'tmp/audit/r15_action_scheduler_20261008_001'
COMBAT={'ABILITY_CORPUS','PASSIVE_CORPUS','MODIFIER_CORPUS'}

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def control(name): return ROOT/f'data/control/generic_runtime_{name}_{SUFFIX}.json'

def load_catalog():
    inventory=read(AUDIT/'catalog_records.json')
    for record in inventory:
        if record.get('decoded_artifact'):
            record['graph']=read(ROOT/record['decoded_artifact'])['graph']
        if record.get('IR_artifact'):
            record['ir']=read(ROOT/record['IR_artifact'])
    return ContentCatalog(read(AUDIT/'directory_inventory.json')['entries'],inventory)

def refresh_graph():
    catalog=load_catalog()
    previous=read(control('ability_dependency_graph_v1'))
    corpus=read(control('real_combat_corpus_v2'))
    roots=[g['source_identity'] for g in corpus['graphs'] if g['stratum'] in COMBAT]
    roots += [e['target_source_identity'] for e in previous['character_reference_edges'] if e.get('target_source_identity')]
    previous.update(catalog.closure(roots))
    previous['character_reference_edges']=[catalog.resolve(e) for e in previous['character_reference_edges']]
    control('ability_dependency_graph_v1').write_text(json.dumps(previous,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    summary=read(AUDIT/'closure_summary.json')
    summary.update(edges=len(previous['edges']),edge_statuses=dict(collections.Counter(e['status'] for e in previous['edges'])))
    write('closure_summary.json',summary)

def main():
    AUDIT.mkdir(parents=True,exist_ok=True)
    corpus=read(control('real_combat_corpus_v2'))
    baseline=read(R15/'after_probes.json')
    priorities=collections.Counter()
    for row in baseline:
        cap=row.get('required_capability') or ''
        if cap.startswith('missing decoded child catalog reference:'):
            priorities[cap.split(':',1)[1]]+=5 if row['skill_joined'] else 1
    controls=[control(n) for n in ['real_combat_corpus_v2','skill_root_join_census_v1','support_census_v4',
              'capability_discovery_v1','action_scheduler_v1','scheduler_support_census_v5','action_lifecycle_gap_ledger_v1']]
    unique={family:{(tuple(g['source_identity']),n['type'],tuple(n['span'])) for g in corpus['graphs'] if g['stratum'] in COMBAT
             for n in g['semantic_instances'] if n['family']==family} for family in ['task','target','predicate']}
    write('frozen_baseline.json',{'control_pins':{p.relative_to(ROOT).as_posix():sha(p) for p in controls},
        'combat_roots':sum(g['stratum'] in COMBAT for g in corpus['graphs']),
        'skill_joined_roots':sum(g['skill_joined'] for g in corpus['graphs']),
        'joined_rows':sum(r.get('root_ir_compiled',False) for r in read(control('skill_root_join_census_v1'))['rows']),
        'instances':{k:len(v) for k,v in unique.items()},
        'combat_first_gap_families':dict(collections.Counter(r['first_gap_family'] for r in baseline if r['first_gap_family'])),
        'joined_first_gap_families':dict(collections.Counter(r['first_gap_family'] for r in baseline if r['skill_joined'] and r['first_gap_family'])),
        'baseline_probe_sha256':sha(R15/'after_probes.json'),'native_claim':False})
    batch=read(R14/'expanded_decoded_records.json')
    entries=read(R14/'directory_inventory.json')['entries']
    assets=Assets()
    schemas={int(s['rva'],16):s for s in read(R14/'reader_schemas.json') if s.get('rva')}
    schemas[0x1eb95230]={'kind':'wrapper','type':'RPG.GameCore.TurnBasedModifierConfig','child':0x1eb95390}
    registries={int(r,16):{int(k):int(v,16) for k,v in t.items()} for r,t in read(R14/'reader_dispatch.json').items()}
    # Re-read exact index, pinned shard and layout framing before trusting inventory.
    verified=[]
    byconfig={e['config']['path']:e for e in entries}
    for path,e in sorted(byconfig.items()):
        config,layout=assets.lookup(path),assets.lookup(e['layout']['path'])
        if config!=e['config'] or layout!=e['layout']: raise ValueError('DesignV identity drift')
        data,pin=assets.source(config)
        decoded=directory(data,layout,config,schemas,registries)
        verified.extend({**d,'config':config,'layout':layout,'source_shard':config['source_shard'],
                         'source_shard_sha256':pin['sha256']} for d in decoded)
    if sorted(verified,key=source_key)!=sorted(entries,key=source_key): raise ValueError('serialized directory drift')
    # Candidate transforms are ONLY hash-membership discovery, never accepted joins.
    candidates=[]; discoveries=[]
    for path in sorted(byconfig):
        stem=path.removesuffix('_Ability.bytes')
        for folder in ['ConfigAbility','ConfigCamera','ConfigAbilityCamera']:
            for suffix in ['_Camera','_Camera_Ability','_Ability_Camera','_CameraAbility','_AbilityCamera','_SkillCamera']:
                candidate=stem.replace('/ConfigAbility/','/'+folder+'/')+suffix+'.bytes'
                found=assets.lookup(candidate)
                candidates.append({'path':candidate,'index_found':bool(found),'discovery_only':True})
                if found: discoveries.append(found)
    # Do not invent a directory identity for a missing path or missing layout.
    for config in discoveries:
        layout=assets.lookup(config['path'].removesuffix('.bytes')+'.layout.bytes')
        if not layout: continue
        data,pin=assets.source(config)
        for d in directory(data,layout,config,schemas,registries):
            entries.append({**d,'config':config,'layout':layout,'source_shard':config['source_shard'],'source_shard_sha256':pin['sha256']})
    write('directory_inventory.json',{'entries':entries,'discovery_candidates':candidates,
          'index_pin':assets.index_pin,'all_R14_directories_revalidated':True})
    records={}
    corpus_by_source={tuple(g['source_identity']):g for g in corpus['graphs']}
    for record in batch['accepted']:
        g=corpus_by_source[source_key(record)]
        ir=read(ROOT/g['IR_artifact'])
        if IRNode.from_dict(ir).stable_hash()!=g['canonical_IR_hash']: raise ValueError('frozen IR drift')
        records[source_key(record)]={**record,'ir':ir,'canonical_IR_hash':g['canonical_IR_hash'],
             'IR_artifact':g['IR_artifact'],'decoded_artifact':g['decoded_artifact'],'newly_decoded':False}
    gaps={source_key(r):r for r in batch['record_gaps']}
    roots=[tuple(g['source_identity']) for g in corpus['graphs'] if g['stratum'] in COMBAT]
    # Also retain character/passive/entry reference evidence as an explicit side view.
    characters=[c for c in read(R14/'character_records.json') if c['status']=='ACCEPTED']
    character_edges=[]
    basecatalog=ContentCatalog(entries,records.values())
    for c in characters:
        for ref in references(c['graph']):
            edge=basecatalog.resolve(ref)
            edge.update(parent_source_identity=[c['source_shard_sha256'],c['graph']['start'],c['graph']['end']],
                parent_graph_hash=digest(c['graph']),parent_graph_id=c['path'],scope='CHARACTER_REFERENCE_SIDE_VIEW')
            character_edges.append(edge)
    # Every discovered reachable reference is processed, with a hard local method
    # budget. Blocked readers do not prevent independent dependencies progressing.
    attempts=[]; reached=set(); newly=set(); requests=[]
    ledger=read(ROOT/'data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    for round_no in range(24):
        localpath=AUDIT/'local_reader_schemas.json'
        if localpath.exists():
            for s in read(localpath):
                s=copy.deepcopy(s)
                for f in s.get('fields',[]): f['mask']=int(f['mask'])
                schemas[int(s['rva'],16)]=s
        processed={int(a['rva'],16) for a in read(AUDIT/'local_reader_receipt.json')['attempts']
                   if 'R16_METHOD_BUDGET' not in a.get('question','')} if (AUDIT/'local_reader_receipt.json').exists() else set()
        current_gaps={}; queue=list(roots)+[tuple(e['target_source_identity']) for e in character_edges if e.get('target_source_identity')]
        visited=set()
        catalog=ContentCatalog(entries,records.values())
        while queue:
            key=queue.pop(0)
            if key in visited: continue
            if len(visited)>=4096: raise ValueError('record bound exceeded')
            visited.add(key); reached.add(key)
            if key not in records:
                entry=next((e for e in entries if source_key(e)==key),None)
                if not entry: continue
                data,pin=assets.source(entry['config'])
                result=decode_entry(data,entry,schemas,registries)
                envelope={'identity':entry['name'],'entry':entry,'source_shard':entry['source_shard'],
                          'source_shard_sha256':pin['sha256'],'record_start':key[1],'record_end':key[2],
                          'source_manifest_sha256':MANIFEST_SHA,'stratum':'MODIFIER_CORPUS' if entry['type']==0 else
                              'ABILITY_CORPUS' if entry['type']==1 else 'OTHER_RUNTIME_CONFIG',**result}
                attempts.append({'round':round_no,'source_identity':list(key),'identity':entry['name'],
                                 **{k:v for k,v in result.items() if k not in ('graph','graph_hash')}})
                if result['status']=='ACCEPTED':
                    label=key[0][:16]+'_'+str(key[1])+'_'+str(key[2])
                    path=AUDIT/'graphs'/f'{label}.json';path.parent.mkdir(exist_ok=True)
                    path.write_text(json.dumps(envelope,sort_keys=True,indent=2)+'\n',encoding='utf-8')
                    _,ir=canonical_compile(envelope,path.relative_to(ROOT).as_posix(),ledger)
                    ipath=AUDIT/'ir'/f'{label}.json';ipath.parent.mkdir(exist_ok=True)
                    ipath.write_text(ir.canonical_json()+'\n',encoding='utf-8')
                    envelope.update(ir=ir.to_dict(),canonical_IR_hash=ir.stable_hash(),
                        IR_artifact=ipath.relative_to(ROOT).as_posix(),decoded_artifact=path.relative_to(ROOT).as_posix(),newly_decoded=True)
                    records[key]=envelope;catalog.add(envelope);newly.add(key)
                else:
                    gaps[key]=envelope
                    if result.get('reader_gap') and int(result['reader_gap'],16) not in processed:
                        current_gaps.setdefault(result['reader_gap'],[]).append({'identity':entry['name'],'source_identity':list(key)})
                    continue
            for ref in references(records[key]['graph']):
                edge=catalog.resolve(ref)
                if edge.get('target_source_identity'): queue.append(tuple(edge['target_source_identity']))
        if not current_gaps: break
        receipt=read(AUDIT/'local_reader_receipt.json') if (AUDIT/'local_reader_receipt.json').exists() else {'native':[]}
        if len(receipt['native'])>=180: break
        requests=[{'rva':r,'reachable_records':gs,'round':round_no,
                   'execution_priority':sum(priorities[g['identity']] for g in gs)}
                  for r,gs in sorted(current_gaps.items(),key=lambda item:(-sum(priorities[g['identity']] for g in item[1]),-len(item[1]),item[0]))[:16]]
        write('selected_reader_requests.json',requests)
        p=subprocess.run(['node',str(ROOT/'tools/runtime/r16_local_readers.cjs')],cwd=ROOT,capture_output=True)
        with (AUDIT/'local_reader_output.txt').open('ab') as f: f.write(p.stdout+p.stderr)
        if p.returncode: raise RuntimeError('narrow reader extraction failed; see local_reader_output.txt')
        print('round',round_no,'reachable',len(visited),'new graphs',len(newly),'reader requests',len(requests),flush=True)
    catalog=ContentCatalog(entries,[*records.values(),*(r for k,r in gaps.items() if k not in records)])
    closure=catalog.closure(roots+[tuple(e['target_source_identity']) for e in character_edges if e.get('target_source_identity')])
    character_edges=[{**e,**catalog.resolve(e)} for e in character_edges]
    closure.update(schema='generic_runtime_ability_dependency_graph/1',change_request=CR,
          frozen_root_denominators={'combat':632,'decoded_joined_skill':160},character_reference_edges=character_edges,
          scope='FROZEN_COMBAT_ROOTS_PLUS_EXACT_CHARACTER_REFERENCE_SIDE_VIEW',
          native_execution_claimed=False,reference_types=list(__import__('hsr_battle_agent.battle_ir.content_catalog',fromlist=['REFERENCE_TYPES']).REFERENCE_TYPES))
    write('catalog_records.json',[{k:v for k,v in record.items() if k not in ('graph','ir')}
                                 for record in catalog.records.values()])
    write('decode_attempts.json',attempts)
    write('new_graph_index.json',[{k:v for k,v in records[key].items() if k not in ('graph','ir','entry')} for key in sorted(newly)])
    write('closure_summary.json',{'reachable_records':len(reached),'new_graphs':len(newly),
        'new_root_types':dict(collections.Counter(records[k]['graph']['type'] for k in newly)),
        'edges':len(closure['edges']),'edge_statuses':dict(collections.Counter(e['status'] for e in closure['edges'])),
        'stop':'All reachable exact selected dependencies processed; unknown readers remain explicit under local work budget.',
        'reader_requests_remaining':requests if len(receipt['native'])>=180 else []})
    control('ability_dependency_graph_v1').write_text(json.dumps(closure,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in read(AUDIT/'closure_summary.json').items() if k!='reader_requests_remaining'},indent=2),flush=True)

if __name__=='__main__':
    if '--refresh-graph' in sys.argv: refresh_graph()
    else: main()
