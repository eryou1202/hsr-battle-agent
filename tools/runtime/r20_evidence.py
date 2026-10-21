"""Bounded census of existing trusted R14 graphs and R11 resource evidence."""
from __future__ import annotations
import collections
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r20_checks import AUDIT, read, write, sha
from r18_probes import load
from hsr_battle_agent.battle_ir.behavior import walk_nodes

def main():
    roots,_=load(); unique={};progress={}
    for g,ir in roots:
        for n in [*walk_nodes(ir.payload.get('tasks')),*walk_nodes(ir)]:
            key=(g['source_shard_sha256'],str(n.payload.get('span')),n.op)
            if n.op.rsplit('.',1)[-1] in ('BySkillPointActivated','ByRankActivated'):
                progress.setdefault(key,(g,n))
            if any(s in n.op for s in ('ModifySP','BoostPoint','Energy','Resource')):
                unique.setdefault(key,(g,n))
    rows=[]
    for g,n in unique.values():
        is_sp=n.op=='RPG.GameCore.ModifySPNew'
        fields=n.payload.get('fields',{})
        rows.append({'root':g['record_identity'],'source_identity':g['source_identity'],
            'source':n.authority.to_dict(),'node':n.to_dict(),'task_hash':n.stable_hash(),
            'source_fields':n.to_dict()['payload'].get('fields',{}),
            'classification':'STRUCTURALLY_PRESENT_RESOURCE_MUTATION_CANDIDATE' if is_sp else 'PRESENTATION_OR_RESOURCE_STATE_UNKNOWN',
            'target_context':'exact decoded selector; runtime context required' if is_sp else 'no numeric mutation target established',
            'target_selector_candidates':{k:v.to_dict() for k,v in fields.items() if getattr(v,'kind',None)=='TargetSelectorIR'},
            'amount_expression_candidates':{k:v.to_dict() for k,v in fields.items() if getattr(v,'kind',None)=='ExpressionIR'},
            'resource_candidate':'actor properties 0xB/0xC/0x8A for related unpatched ModifySPNew path; effective mapping unknown' if is_sp else 'UNKNOWN; state/icon fields do not prove resource balance mutation',
            'scope_evidence':'R11 same-version selected native actor path, distinct team BP path' if is_sp else 'UNKNOWN_NATIVE_RESOURCE',
            'amount_operand':'serialized dynamic fields; ratio/base/rate join incomplete' if is_sp else 'dynamic fields present; numeric amount role unproved',
            'events':'native IDs/order/effective listeners unknown; explicit R17 reference listeners required',
            'missing_native_evidence':['effective task executor/IFix/Lua join','resource key identity','cost/gain formula','cap/overflow/event policy'],
            'native_oracle_status':'NATIVE_ORACLE_PENDING'})
    all_types=collections.Counter()
    for g,ir in roots:
        seen=set()
        for n in walk_nodes(ir):
            key=(n.op,str(n.payload.get('span')))
            if n.kind in ('TaskIR','UnsupportedSemanticIR') and key not in seen:
                all_types[n.op]+=1;seen.add(key)
    write('resource_instruction_census.json',{'instances':rows,'counts':dict(collections.Counter(n.op for g,n in unique.values())),
          'full_combat_task_type_inventory':dict(all_types),'resource_names_are_semantic_proof':False,
          'denominator':632,'joined_roots':160,'joined_rows':161,'dedup':'shard + exact source span + operation'})
    write('progression_instruction_census.json',{'instances':[{'root':g['record_identity'],'source_identity':g['source_identity'],
          'source':n.authority.to_dict(),'node':n.to_dict(),'predicate_hash':n.stable_hash(),
          'serialized_TriggerKey_candidates':{k:v for k,v in n.to_dict()['payload'].get('fields',{}).items() if type(v) is int},
          'native_comparison':'UNKNOWN; explicit activation/threshold policy only'} for g,n in progress.values()],
          'counts':dict(collections.Counter(n.op for g,n in progress.values()))})
    refs=['tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/sp_resource.json',
          'tmp/audit/r102_4651_structural_path_closure_20261004_001/avatar_decode.json',
          'tmp/audit/r11c_4651_effective_runtime_semantic_closure_20261006_001/avatarskilltree_decode.json',
          'tmp/audit/r11c_4651_effective_runtime_semantic_closure_20261006_001/avatarpromotion_decode.json']
    refs += ['data/control/generic_runtime_'+n+'_20261010_001.json' for n in
             ('damage_lifecycle_v1','dynamic_property_v1','damage_continuation_census_v1','support_census_v9','semantic_gap_ledger_v7')]
    refs += ['docs/agent/handoffs/generic_runtime_damage_continuation_property_20261010_001.md']
    native=read(ROOT/refs[0]);pins={r:sha(ROOT/r) for r in refs}
    for name in native['evidence']:
        path='tmp/audit/r11_4651_natasha_semantic_closure_20261005_001/'+name
        pins[path]=sha(ROOT/path)
    write('source_pins.json',pins)
    write('modify_sp_native_boundary.json',{'source_version':'4.6.51','existing_evidence':native,
        'exact_effective_mapping':'UNKNOWN','reference_binding_required':True,'no_name_inference':True,
        'bounded_work':'reuse existing structural graphs and selected native receipts only; no new disassembly/capture'})
    print('resource',dict(collections.Counter(n.op for g,n in unique.values())))
    print('progression',dict(collections.Counter(n.op for g,n in progress.values())))
    for typ in sorted({n.op for g,n in unique.values()}|{n.op for g,n in progress.values()}):
        g,n=next((g,n) for g,n in [*unique.values(),*progress.values()] if n.op==typ)
        print(g['record_identity'],n.to_dict())
    print('graph keys',list(roots[0][0]))

if __name__=='__main__': main()
