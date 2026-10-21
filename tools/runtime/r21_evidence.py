"""Inventory bounded static evidence; no runtime authority is inferred."""
from __future__ import annotations
import json
import re
from r21_checks import ROOT, AUDIT, read, write, sha

def main():
    inventory=read(AUDIT/'native_anchor_inventory.json')
    methods=read(AUDIT/'native_methods.json')
    snapshot=read(ROOT/'data/control/real_runtime_4651_source_snapshot_20261002_001.json')
    identity=snapshot['snapshot_identity']
    manifest_path=identity['manifest_path']
    assert sha(manifest_path)==identity['manifest_sha256']==inventory['manifest_sha256']
    manifest=read(manifest_path)
    source_pins={}
    for f in inventory['source_files']:
        p=__import__('pathlib').Path(identity['snapshot_path'])/f['relative_path']
        assert p.stat().st_size==f['size'] and sha(p)==f['sha256']
        source_pins[f['relative_path']]=f
    assert len(methods)==48 and len({x['method']['index'] for x in methods})==48
    controller=next(x for x in inventory['types'] if x['type']['name']=='TurnBasedGameMode')
    controller_ids={x['index'] for x in controller['methods']}
    edges={x['method']['index']:{m['index'] for c in x['calls'] for m in c['identities']} for x in methods}
    # Same-type methods are bounded subsystem anchors; dependencies require exact edges.
    paths={x: [x] for x in controller_ids}
    for _ in range(2):
        for parent,children in edges.items():
            if parent in paths:
                for child in children:
                    p=paths[parent]+[child]
                    if child not in paths or len(p)<len(paths[child]): paths[child]=p
    component_ids={x['index'] for t in read(AUDIT/'native_reachable_types.json')
                   if t['type']['name']=='TurnBasedAbilityComponent' for x in t['methods']}
    for m in component_ids:
        paths.setdefault(m,[516470,523121,m] if m!=523121 else [516470,523121])
    # One exact high-value join allowed by the CR: the directly called modifier
    # OnTurnEnd body closes the existence of a duration/event boundary candidate.
    paths[522868]=[516470,523121,523327,522868]
    examined=[]
    for x in methods:
        p=AUDIT/x['body_file'];assert sha(p)==x['body_sha256']
        instructions=re.findall(r'^\s*([0-9a-f]+):\s+(.+)$',p.read_text(),re.M)
        assert instructions
        index=x['method']['index']; route=paths.get(index)
        assert route and (len(route)<=3 or index==522868 and len(route)==4), (index,route)
        examined.append({**x,'source_version':'4.6.51','source_sha256':source_pins['GameAssembly.dll']['sha256'],
            'subsystem':'INITIATIVE_CONTROLLER' if index in controller_ids and index not in {516270,516417,516426,516500,516501} else
                        'INSERTION_BOUNDARIES' if index in {516270,516417,516426,516500,516501,533796,523327,522868} else 'ACTOR_DELAY_SPEED',
            'dependency_path':route,'dependency_hops':len(route)-1,
            'structural_same_type_join':index in component_ids and index!=523121,
            'high_value_hop_exception':index==522868,
            'review':'bounded instruction/call inventory inspected; exact behavior claimed only by the conclusion excerpts',
            'instruction_count':len(instructions),
            'patch_guard_present':'GetPatch' in str(x['calls']),
            'effective_runtime_status':'EFFECTIVE_RUNTIME_ORACLE_REQUIRED'})
    lookup={x['method']['index']:x for x in examined}
    def conclusion(cid,indices,statement,abstraction,ranges,uncertainty,status='SAME_BUILD_NATIVE_CORE_PROVEN'):
        excerpts=[]
        for i,lo,hi in ranges:
            x=lookup[i];lines=(AUDIT/x['body_file']).read_text().splitlines()
            selected=[s for s in lines if (m:=re.match(r'\s*([0-9a-f]+):',s)) and lo<=int(m[1],16)-0x180000000<=hi]
            assert selected
            excerpts.append({'method_index':i,'start_rva':hex(lo),'end_rva_inclusive':hex(hi),'instructions':selected})
        return {'id':cid,'source_version':'4.6.51','source_sha256':source_pins['GameAssembly.dll']['sha256'],
            'methods':[lookup[i]['method'] for i in indices], 'status':status,'actual_evidence':statement,
            'excerpts':excerpts,'native_runtime_uncertainty':uncertainty,'reusable_runtime_abstraction':abstraction}
    facts=[
      conclusion('E01',[516441,516442],
        'Base selection walks the controller list, calls HasActionTurn and IsAnyLockActionDelay. _PickTurnActiveEntity calls selection, SetCurrentTurnActionEntity, writes controller+0x260, notifies owner change, reads property 0x26, then advances list delay.',
        'Participant eligibility, selected action actor, separate ActiveTurn owner, elapsed readiness advancement',
        [(516442,0xF165023,0xF1650AF)],'Effective patch selection, actor initialization, lock semantics and decision legality unclosed'),
      conclusion('E02',[516431,516432,533850],
        'PackActionDelayCompareData reads property 0x26 when requested and packs a qword plus flags and signed integer keys. Comparator orders unequal tagless qwords signed ascending; after equality +08 boolean true first; equal zero delay additionally +09 true first and +0c signed descending; remaining +10 and +14 signed ascending. Tagged paths use separate comparisons.',
        'Queue readiness plus explicit tie policy; no unordered iteration',
        [(516432,0xF16DEC0,0xF16DECD),(533850,0xC49541C,0xC495451),(533850,0xC4954E3,0xC495574)],
        'Auxiliary key runtime producers, tagged representational reachability, stable final tie and effective comparator dispatch unclosed'),
      conclusion('E03',[523121,523436],
        'SetupActionDelayByUnitDistance reads property 0x20; multiplies config object field+0x190 by the argument, stores the result at component+0x2a0, divides by positive speed, then calls ModifyProperty for 0x26 with operation literal 1. get_UnitActionDelay returns config field+0x190 divided by positive property 0x20; nonpositive speed returns a static qword.',
        'Injectable distance/speed interval policy with explicit positive speed validation',
        [(523121,0xF12453D,0xF1245A4),(523121,0xF124629,0xF124649),(523436,0xF14CCF1,0xF14CD3E)],
        'The effective config field value, input scale, static fallback, exact division rounding, tagged range and initialization are not established; 10000 is not native-proven'),
      conclusion('E04',[523276,523245,523246],
        'RefreshSpeed has a modifier-behavior-dependent branch and writes property 0x20; another branch uses ToSpeedOverrideLinearProperty plus fixed-point addition/multiplication/subtraction and writes 0xd4. ApplyDelayModifyWhenActionPhaseEnd drains stored entries through ModifyProperty 0x26 operation literal 2.',
        'Speed provider revisions and delayed readiness mutations must be separate from a fixed scheduling formula',
        [(523276,0xF13D741,0xF13D78C),(523276,0xF13D7D9,0xF13D865),(523246,0xF139EE0,0xF139F17)],
        'No exact join from speed property-change notification to remaining delay rebase; field operands and modifier behavior numeric meaning unclosed'),
      conclusion('E05',[516473],
        'The base path clamps the supplied elapsed amount, calls ModifyEntitiesActionDelay on the controller list with a captured delegate, then adds elapsed amount into controller+0x348 through FixPoint.op_Addition. The delegate body and all filtering paths are not closed.',
        'BattleClock distinct from R15 logical time; remaining readiness is updated under explicit policy',
        [(516473,0xF16EAE8,0xF16EB9A)],'Per-actor callback subtraction and lock/redirect effects require additional joins; effective dispatch unknown'),
      conclusion('E06',[516284,516400,516443],
        'SetCurrentTurnActionEntity stores current action entity at controller+0x298. _PickTurnActiveEntity separately writes +0x260. Named current-turn-owner accessors and independent metadata fields corroborate distinct storage; ProcessTurnOwnerSwitch calls owner-change processing.',
        'Battle owner, turn owner, action owner and callback/modifier owner must remain distinct',
        [(516284,0xF15B2FA,0xF15B35A)],'Native controller ownership meaning during all insertion phases and effective owner change hooks unclosed'),
      conclusion('E07',[516270,516500,516501,533796,516417,516426],
        'TryInsertAbility invokes a separate sort. _CompareByInsertAbilityInstance calls ENGBNDIPDJL.KGAFHLGGNHJ, which first compares signed +0xa8 ascending, then entity-related data. _TickInsertAbility changes current action entity and invokes UseAbility; _FinishInsertAbility calls ExecuteAllModifierEvent and a LevelInsertAbilityFinish initializer.',
        'Separate ActionInsertion requests with explicit placement, parent ownership and boundary rules',
        [(533796,0x1625C882,0x1625C89D)],
        'Exact priority enum/field offset join, ultimate/FUA categories, native turn/AV consumption and interrupts not proven'),
      conclusion('E08',[516191,516373,523327,522868],
        'Action-finish controller paths check skill and limbo completion before OnAfterSkillPerform/RefreshCurrentSkillPerform. ProcessOnLevelTurnEnd iterates modifiers and calls OnTurnEnd; OnTurnEnd conditionally calls a helper for config literal 5, then calls event execution with literal 0x13.',
        'Drain owned work before boundaries; explicit turn events and modifier duration progression',
        [(522868,0xF182405,0xF182439)],
        'Literal 0x13 is observed only on this modifier base path, not a fabricated global event ID contract; event enum join, duration operation and global order/effective dispatch incomplete'),
      conclusion('E09',[516469,516470],
        'Distinct death and revive handlers exist. Revive reads/modifies properties and calls SetupActionDelayByUnitDistance. This establishes queue-affecting lifecycle candidates, not a complete native participation rule.',
        'Explicit participation generations and death/revival/summon policies',
        [(516470,0xF170FFA,0xF170FFA)],'Revive fraction inputs, removed actors, summons and wave initialization are unresolved','STRUCTURALLY_EVIDENCED')]
    old=ROOT/'data/semantics/4.4.54/full_reconstruction/astra_scheduler_targeted_evidence_v1.json'
    old_data=read(old)
    old_by_name={x['method_name']:x for x in old_data['native_body_excerpts']}
    compatibility=[{'old_version':'4.4.54','new_version':'4.6.51','name':x['method']['name'],
        'old_method_index':old_by_name[x['method']['name']]['method_index'],'new_method_index':x['method']['index'],
        'old_rva':old_by_name[x['method']['name']]['native_rva'],'new_rva':x['method']['rva'],
        'compatibility':'IDENTITY_CANDIDATE_ONLY; new body independently inspected; no transferred constants/offsets'}
        for x in methods if x['method']['name'] in old_by_name]
    refs=['data/control/real_runtime_4651_source_snapshot_20261002_001.json',
          'tmp/audit/r102_4651_structural_path_closure_20261004_001/exact.cjs',old.relative_to(ROOT).as_posix()]
    refs += ['data/control/generic_runtime_'+n+'_20261010_001.json' for n in
             ['actor_state_binding_v1','resource_engine_v1','support_census_v10','dynamic_property_v1','damage_lifecycle_v1']]
    refs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/agent/handoffs').glob('generic_runtime_*.md')]
    write('source_pins.json',{'snapshot_manifest':{'path':manifest_path,'sha256':sha(manifest_path)},
        'native_source_files':source_pins,'reused_artifacts':{p:sha(ROOT/p) for p in refs}})
    write('bounded_evidence.json',{'research_version':'4.6.51','product_baseline':'4.4.54',
        'budget':{'subsystem_paths_max':3,'subsystem_paths_used':3,'method_bodies_max':120,
          'method_bodies_examined':len(methods),'normal_dependency_hops_max':2,'max_dependency_hops':3,
          'hop_exception_used':True,'hop_exception':'M523327 directly calls M522868 OnTurnEnd; inspect this one exact join for modifier lifetime/event boundary, then stop',
          'stop_reason':'Bounded selected anchors answered structural questions; residual effective/config/provider joins are specific tickets. Budget need not be exhausted.'},
        'examined_methods':examined,'conclusions':facts,'version_compatibility':compatibility,
        'failed_or_unclosed_joins':[
          'Named BattleCharacterComponent identity not found; directly reached TurnBasedAbilityComponent replaces this candidate, without identity inference.',
          'Config object field +0x190 -> pinned initialized numeric distance value: NOT_CLOSED',
          'RefreshSpeed -> property after-change -> native remaining delay reschedule: NOT_CLOSED',
          'Captured ModifyEntitiesActionDelay delegate -> full per-actor subtraction/lock/redirect: NOT_CLOSED',
          'Packed comparator auxiliary fields -> effective runtime priority and full equal-key stability: NOT_CLOSED',
          'IFix guards -> effective patch payload/selection: prohibited live oracle and no rediscovery',
          'Insertion request -> ultimate/FUA/extra native turn accounting: NOT_CLOSED',
          'Modifier literal 0x13/config literal 5 -> effective enum, duration and global ordering: NOT_CLOSED',
          'Lifecycle handlers -> full summon/wave/terminal/decision boundary: NOT_CLOSED'],
        'negative_evidence_rule':'No absent TaskConfig in a 632-root corpus proves absence of native controller AV mechanics',
        'effective_native_turn_av':'NOT_CLOSED','native_equivalence_claimed':False})
    print('evidence PASS: 3 paths, 48 bodies, 2 hops plus one justified OnTurnEnd join; source pin verified')

if __name__=='__main__': main()
