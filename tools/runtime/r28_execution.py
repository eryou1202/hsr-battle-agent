"""Reproducible original parents and bounded Monster AI reader recovery."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/runtime')]
from r27_checks import AUDIT as OLD, read
from r27_reader import machinery
from r28_reader import Reader
from r14_corpus import Assets
from hsr_battle_agent.battle_ir.behavior import IRNode, stable_hash
from hsr_battle_agent.battle_ir.catalog_overlay import load_overlay
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.original_bindings import bind_remove_reference
AUDIT = ROOT/'tmp/audit/r28_original_combat_semantics_20261022_001'


def write(name, value):
    p = AUDIT/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')


def ai():
    original = read(OLD/'monster/AI_source_attempt.json')
    schemas, dispatch = machinery()
    for s in read(AUDIT/'reader_schemas.json'): schemas[int(s['rva'],16)] = s
    for r, mapping in read(AUDIT/'reader_dispatch.json').items():
        dispatch[int(r,16)] = {int(k):int(v) for k,v in mapping.items()}
    data, pin = Assets().source(original['asset'])
    assert pin == original['pin']
    start = original['asset']['offset']; end = start + original['asset']['length']
    reader = Reader(data, start, end, schemas, dispatch)
    try:
        graph = reader.read(0x1e26c2e0)
        assert reader.cursor == end
        again = Reader(data, start, end, schemas, dispatch).read(0x1e26c2e0)
        assert graph == again == json.loads(json.dumps(graph))
        write('monster/AI_decoded.json', graph)
        result = dict(status='EXACT_BODY_DECODED', cursor=reader.cursor, expected_end=end,
                      graph_hash=stable_hash(graph), full_consumption=True, roundtrip=True)
    except ValueError as exc:
        result = dict(status='READER_GAP', cursor=reader.cursor, expected_end=end,
                      question=str(exc), reader_gap=getattr(exc,'reader_gap',None))
    write('monster/AI_result.json', dict(original=original, result=result,
          source_backed_rules_executed=0, native_policy_supported=False,
          limitation='Only original serialized branch 14 is added; remaining dispatch variants stay gaps'))
    print('AI', result, flush=True)


def characters():
    import r23_reference_fixtures as fixtures
    import r23_probes as probes
    original = fixtures.content()
    catalog = load_overlay(original[0], ROOT/'data/overlays/r28_4651_v1/manifest.json')
    view = (catalog, *original[1:])
    fixtures.content = lambda: view
    probes.content = lambda: view
    probes.write = lambda name, value: write('character/'+name,value)
    graphs = {g['record_identity']:g for g in original[-1]['graphs']}
    baseline_create = fixtures.joined_runtime
    rows = []
    for stage in read(OLD/'character/dependency_stages.json'):
        before = stage['whole_original_parent']
        folder = 'character/'+before['root']
        # First replay exact R27 inputs without modification.
        saved = read(OLD/'character/replay'/before['root']/'initial_runtime.json')
        r = BehaviorRuntime.from_snapshot(saved)
        name = before['canonical_binding']['binding_hash'][:16]+'_template'
        commands = read(OLD/'character/scenarios'/name/'commands.json')
        old_final,_ = r.replay_turn_commands(commands)
        assert old_final.stable_hash() == before['full_runtime_hash']
        bind = before['gap_node']['op'] == 'RPG.GameCore.RemoveModifier'
        def create(*args, **kwargs):
            runtime,binding,receipts = baseline_create(*args,**kwargs)
            if bind:
                node = IRNode.from_dict(before['gap_node'])
                receipt = bind_remove_reference(runtime,node,
                    pending_callbacks='CANCEL_NOT_STARTED_REFERENCE',identity_filter={})
                write(folder+'/binding.json', receipt)
            write(folder+'/initial_runtime.json', runtime.snapshot())
            return runtime,binding,receipts
        probes.joined_runtime = create
        after = probes.execute(graphs[before['root']],templates=True,replay=True)
        initial = BehaviorRuntime.from_snapshot(read(AUDIT/folder/'initial_runtime.json'))
        final,_ = initial.replay_turn_commands(read(AUDIT/'character/scenarios'/name/'commands.json'))
        assert final.stable_hash() == after['full_runtime_hash']
        assert final.clone().stable_hash() == BehaviorRuntime.from_snapshot(json.loads(json.dumps(final.snapshot()))).stable_hash()
        write(folder+'/final_runtime.json',final.snapshot())
        write(folder+'/before.json',before)
        write(folder+'/after.json',after)
        rows.append(dict(root=before['root'],before=before['metrics']['tasks_completed'],
            after=after['metrics']['tasks_completed'],before_blocker=before['required_capability'],
            after_blocker=after['required_capability'],actions_completed=after['actions_completed'],
            original_task_hash=IRNode.from_dict(before['gap_node']).stable_hash(),
            original_task=before['gap_node'],authority='REFERENCE_MODEL',replay='PASS'))
        print(before['root'],rows[-1]['before'],rows[-1]['after'],after['required_capability'],flush=True)
    write('character/results.json',rows)


def monsters():
    rows=[]
    for p in sorted((OLD/'monster/execution').glob('*/commands.json')):
        initial=BehaviorRuntime.from_snapshot(read(p.parent/'initial_runtime.json'))
        final,_=initial.replay_turn_commands(read(p))
        assert final.snapshot()==read(p.parent/'final_runtime.json')
        row=read(p.parent/'result.json')
        write('monster/execution/'+p.parent.name+'/result.json',row)
        rows.append(row)
    write('monster/results.json',rows)


def provider():
    identity=read(AUDIT/'JsonEnum_provider_identity.json')
    schemas,dispatch=machinery()
    for s in read(AUDIT/'reader_schemas.json'): schemas[int(s['rva'],16)]=s
    for r,m in read(AUDIT/'reader_dispatch.json').items():
        dispatch[int(r,16)]={int(k):int(v) for k,v in m.items()}
    asset=Assets().lookup('BakedConfig/Config/GlobalConfig/JsonEnumDefineConfig.bytes')
    data,pin=Assets().source(asset)
    p=Reader(data,asset['offset'],asset['offset']+asset['length'],schemas,dispatch)
    try:
        graph=p.read(0x1e6d7c30)
        assert p.cursor==p.end
        assert Reader(data,asset['offset'],p.end,schemas,dispatch).read(0x1e6d7c30)==graph
        from r28_reader import encode_provider
        assert encode_provider(graph)==data[asset['offset']:p.end]
        write('provider/decoded.json',graph)
        result=dict(status='EXACT_BODY_DECODED',graph_hash=stable_hash(graph),end=p.cursor,byte_roundtrip=True)
        from hsr_battle_agent.battle_ir.jsonenum_provider import JsonEnumProvider
        provider=JsonEnumProvider(graph,stable_hash(graph))
        sites=[]
        for ticket in read(OLD/'acquisition_tickets.json'):
            if ticket.get('native_reader')=='0x1E6D6BF0':
                sites.append(dict(ticket=ticket,resolution=provider.resolve(ticket['serialized_lookup_key'])))
        write('provider/resolved_sites.json',sites)
    except ValueError as exc:
        result=dict(status='READER_GAP',cursor=p.cursor,question=str(exc),reader_gap=getattr(exc,'reader_gap',None))
    write('provider/result.json',dict(identity=identity,asset=asset,pin=pin,result=result))
    print(result,flush=True)


if __name__=='__main__':
    {'ai':ai,'characters':characters,'monsters':monsters,'provider':provider}[sys.argv[1]]()
