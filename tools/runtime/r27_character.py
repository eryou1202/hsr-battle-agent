"""Recover exact Phase bodies; rerun original canonical parents after each add."""
from __future__ import annotations
import copy
import sys
from r27_checks import ROOT, AUDIT, read, write, sha
from r27_reader import Reader, machinery
from r14_corpus import Assets, digest
from r14_discovery import canonical_compile
from r23_checks import AUDIT as R23
from hsr_battle_agent.battle_ir.content_catalog import ContentCatalog, source_key
import r23_reference_fixtures as fixtures
import r23_probes as probes

def catalog_overlay(base, additions):
    entries=[e for bucket in base.directories.values() for e in bucket.values()]
    replacements={source_key(r):r for r in additions}
    records={**base.records,**replacements}
    return ContentCatalog(entries,records.values())

def decode(assets, entry):
    schemas,dispatch=machinery()
    data,pin=assets.source(entry['config'])
    assert pin['sha256']==entry['source_shard_sha256']
    p=Reader(data,entry['absolute'],entry['record_end'],schemas,dispatch)
    try:
        graph=p.read(0x1eb94400)
        if p.cursor!=p.end:
            return dict(status='FRAMING_GAP',cursor=p.cursor,end=p.end,question='incomplete root consumption')
        return dict(status='ACCEPTED',graph=graph,graph_hash=digest(graph),consumption_status='BOUNDED_FULL_CONSUMPTION')
    except ValueError as exc:
        return dict(status='STRUCTURAL_READER_GAP',cursor=p.cursor,end=p.end,question=str(exc),
                    reader_gap=getattr(exc,'reader_gap',None),reader_gap_type=getattr(exc,'reader_gap_type',None))

def main():
    original=fixtures.content()
    base,_,_,_,corpus=original
    graphs={g['record_identity']:g for g in corpus['graphs'] if g['skill_joined']}
    only=sys.argv[2] if sys.argv[1:2]==['--only'] else None
    additions=read(AUDIT/'character/catalog_additions.json') if only else []
    attempts=read(AUDIT/'character/phase_attempts.json') if only else []
    stages=read(AUDIT/'character/dependency_stages.json') if only else []
    if only:
        additions=[r for r in additions if r['identity']!=only]
        attempts=[r for r in attempts if r['identity']!=only]
        stages=[r for r in stages if r['resolved_dependency']!=only]
    ledger=read(ROOT/'data/control/real_runtime_generic_primitive_ledger_20261007_001.json')
    assets=Assets()
    probes.write=lambda n,d:write('character/'+n,d)
    # Complete original parents, never isolated tasks or fabricated finishes.
    for old in read(R23/'phase_retry.json'):
        if only and old['identity']!=only:continue
        entry=old['prior']['reference_site']['resolved_directory_identity']
        result=decode(assets,entry)
        attempts.append(dict(identity=entry['name'],entry=entry,result={k:v for k,v in result.items() if k!='graph'}))
        if result['status']!='ACCEPTED': continue
        key=source_key(entry);name=entry['name']
        record=dict(identity=name,source_shard_sha256=key[0],record_start=key[1],record_end=key[2],
                    source_shard=entry['source_shard'],entry=entry,**result)
        rel='decoded/'+name+'.json'
        write(rel,record)
        path=(AUDIT/rel).relative_to(ROOT).as_posix()
        _,ir=canonical_compile(record,path,ledger)
        write('ir/'+name+'.json',ir.to_dict())
        record.update(ir=ir.to_dict(),canonical_IR_hash=ir.stable_hash(),decoded_artifact=path,
            IR_artifact=(AUDIT/'ir'/f'{name}.json').relative_to(ROOT).as_posix(),newly_decoded=True)
        # Same body repeated from original bytes, not from generated JSON.
        assert decode(assets,entry)==result
        additions.append(record)
        overlay=catalog_overlay(base,additions)
        view=(overlay,*original[1:])
        fixtures.content=lambda:view
        probes.content=lambda:view
        caller=old['prior']['reference_site']['parent_graph_id']
        graph=graphs[caller]
        row=probes.execute(graph,templates=True,replay=True)
        stages.append(dict(resolved_dependency=name,exact_source_identity=list(key),
            original_IR_unchanged=row['source_IR_unchanged'],whole_original_parent=row,
            next_actual_blocker=row['required_capability']))
        write('character/dependency_stages.json',stages)
        print('RECOVERED',name,'PARENT',caller,'NEXT',row['required_capability'],flush=True)
    write('character/phase_attempts.json',attempts)
    write('character/catalog_additions.json',additions)
    write('character/recovery_summary.json',dict(new_exact_compiled_child_sources=len(additions),
        complete_joined_transitions=sum(s['whole_original_parent']['actions_completed'] for s in stages),
        phase_remaining=sum(a['result']['status']!='ACCEPTED' for a in attempts),
        unchanged_frozen_inputs=True,native_correctness='NOT_CLAIMED'))

if __name__=='__main__':main()
