"""Verify R18 controls/archive and exact bounded R19 source/native evidence."""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(Path(__file__).parent)]
from r19_checks import AUDIT,read,write,sha
from r13_frozen_reader import pinned_source,MANIFEST_SHA
from hsr_battle_agent.battle_ir.behavior import IRNode
from hsr_battle_agent.battle_runtime.dynamic_property import compile_program
R18=ROOT/'tmp/audit/r18_damage_hp_settlement_20261009_001'

def main():
    controls=[ROOT/'data/control'/('generic_runtime_'+n+'_20261009_001.json') for n in
              ('damage_pipeline_v1','hp_settlement_v1','damage_support_census_v1','support_census_v8','semantic_gap_ledger_v6')]
    for p in controls:read(p)
    previous=read(R18/'final_summary.json');census=read(controls[2]);joined=read(R18/'joined_explicit_summary.json')
    finish=read(R18/'damage_perform_finish_evidence.json');damage=read(R18/'damage_structural_audit.json')
    assert census['trusted_records_structurally_decoded']==207 and len(census['shape_counts'])==9
    assert len(finish['instances'])==118
    assert joined['denominator']==15 and joined['hp_mutated']==11 and joined['committed_settlements']==22
    assert joined['full_real_skill_reference_transitions']==0
    frozen=read(R18/'frozen_summary.json')
    assert frozen['combat']['after']['roots']==632 and frozen['joined']['after']['roots']==160
    assert frozen['damage_operations_attempted']==74 and frozen['damage_operations_committed']==0
    zipreceipt=read(R18/'handoff_verification.json');archive=Path(zipreceipt['destination'])
    assert sha(archive)==zipreceipt['ZIP_sha256']
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(zipreceipt['members'])
        for name,expected in zipreceipt['members'].items():
            b=z.read(name);assert hashlib.sha256(b).hexdigest()==expected['sha256']
            assert len(b)==expected['size']
    pins={str(p.relative_to(ROOT).as_posix()):sha(p) for p in controls}
    for name,expected in read(R18/'source_pins.json').items():
        assert sha(ROOT/name)==expected; pins[name]=expected
    write('r18_verification.json',{'status':'PASS','controls':{str(p.relative_to(ROOT)):sha(p) for p in controls},
        'archive':str(archive),'archive_sha256':sha(archive),'CRC':'PASS','members_sizes_SHA256':'PASS',
        'baseline':{'damage_instances':207,'damage_shapes':9,'finish_instances':118,'isolated':{'completed':6,'denominator':6},
            'joined_hp_mutated':11,'joined_denominator':15,'joined_settlements':22,'joined_full_transitions':0,
            'combat_roots':632,'decoded_joined_roots':160,'joined_rows':161,'frozen_damage_attempts':74,'frozen_damage_commits':0}})
    inventory=read(AUDIT/'native_inventory.json');table=read(AUDIT/'opcode_table.json')
    assert next(r for r in table if r['opcode']==4)['branch']=='0x1E196678'
    evaluator=(AUDIT/'native_1e196300.txt').read_text()
    assert '19e1966b3:' in evaluator and '0x19ec1bcf0' in evaluator
    rows=read(R18/'joined_explicit_prefix_results.json');programs=[]
    for row in rows:
        if row['primitive'] not in ('unknown_opcode','RPG.GameCore.ByRankActivated'):continue
        node=IRNode.from_dict(row['gap_node']);artifact=ROOT/node.authority.source_artifact
        assert sha(artifact)==node.authority.source_sha256;pins[node.authority.source_artifact]=sha(artifact)
        graph=read(artifact)
        # Existing graph source metadata holds the exact pinned shard identity.
        raw=node.payload.get('decoded')
        result={'root':row['root'],'source':node.authority.to_dict(),'node':node.to_dict(),
                'runtime_input_in_R18':read(R18/'joined_explicit_inputs.json')['state']['dynamic_values'].get('supplied',{}).get('-1126825319')}
        if raw:
            assert raw['token_ids']==[1,0,0,0,4,17]
            result.update(raw_program=raw,ast=compile_program(node).to_dict(),generic_family='LOOKUP_LITERAL_MULTIPLY',
                operand_encoding='operand index byte; signed int32 provider key / signed int64 FixPoint raw',
                stack_effect='1: push bound lookup; 0: push literal; 4: pop right/pop left/push product; 17: one result terminate',
                native_evaluator='0x1E196300; opcode table 0x1E197720; opcode4 branch 0x1E196678; multiply call 0x1E1966B3 -> 0x1EC1BCF0',
                native_provider='TaskContext.Evaluate@0xF0EA100 -> TaskContext.IDynamicValueProvider.Evaluate@0xF0EC420 -> AbilityStatic.GetDynamicValueByKey@0xEDF8530 -> GetDynamicValueLookupByKey@0xEDF6E30',
                effective_provider='UNKNOWN; R19 explicitly binds unchanged R18 supplied store; no actor/global fallback')
            programs.append(result)
        else:
            result.update(decoded_key=node.payload['fields']['unbound_bit_0'],reader_mask=8,
                metadata_fields=inventory['result'][1]['fields'],native_field='TriggerKey (StringHash); not an ordinal rank',
                missing_fixture_input='actor rank and keyed activation/threshold relation',
                native_predicate_comparison='UNKNOWN: config conversion methods are not the effective predicate executor',
                explicit_policy='KEYED_THRESHOLD_GE_REFERENCE; comparison/threshold authored, not native proven',
                state_fields='existing progression[actor].rank and rank_requirements[key]',avatar_specific_branch=False)
            write('rank_evidence.json',result)
    write('dynamic_program_evidence.json',programs)
    lua='tmp/audit/r11c_4651_effective_runtime_semantic_closure_20261006_001/'
    refs=[lua+'lua_task_registration_key_join.json',lua+'lua_selected_package_evidence.json',lua+'native_semantic_continuation.json',
          'data/control/real_runtime_4651_live_runtime_authority_20261007_001.json']
    for ref in refs:pins[ref]=sha(ROOT/ref)
    native={p.name:sha(p) for p in AUDIT.glob('native*') if p.is_file()}
    write('damage_finish_native_evidence.json',{
        'source_version':'4.6.51','manifest_pin':MANIFEST_SHA,'trusted_mapping':'R09 exact metadata method-index table, reused R10.2 exact.cjs',
        'config_type':inventory['result'][0],
        'structural_fields':'SkipDeathSettlement and IsFakeAvatarAttack; all 118 selected decoded bitmap=0; defaults not inferred',
        'related_finish_method':'TurnBasedAbilityComponent.CharmDamagePerformFinish@0xF1418A0 method index 523296',
        'related_event_signal':'unpatched related method fills event fields, tail calls 0xE26CD70 -> EventManager.FireEvent@0xEF632B0',
        'related_consumer':'CharacterHudComponent._OnAbilityDamagePerformFinish@0xEEC5F80; presentation consumer does not prove settlement/ownership semantics',
        'exact_task_to_related_method_join':'UNPROVEN; config reader is not a runtime task executor',
        'effective_runtime_uncertainty':{'task_executor':'config->runtime executor binding not recovered in the bounded existing mapping',
            'IFix':'CharmDamagePerformFinish patch guard RVA 0x978E100, patch id 0x7FC20; provider patch id 0x7F939; active flags/maps unknown',
            'Lua':'existing R11C runtime Type.Name registration; effective backend/initialized hook maps unbound; no no-override certificate'},
        'answers':{q:'UNKNOWN for effective DamagePerformFinish task; no equivalence asserted' for q in
            ('request_finalization','waits_for_settlement','additional_callbacks','controller_completion','scheduler_barrier_release','damage_bookkeeping','further_events')},
        'signals_distinct':['TASK_COMPLETION','DAMAGE_REQUEST_COMPLETION','DAMAGE_SETTLEMENT_COMPLETION','ABILITY_COMPLETION','ACTION_COMPLETION'],
        'reference_policy':'R18 ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE + R19 current ability/descendant callbacks/events/continuations assertion',
        'reference_effects':'only successful local task boundary and metric; no fabricated callbacks/barriers/SkillPerformFinish',
        'native_semantics_blocker':'DAMAGE_FINISH_EFFECTIVE_RUNTIME_ORACLE_REQUIRED',
        'evidence_files':native,'previous_version_4454_semantics_reused':False,'previous_4651_refs':refs,
        'new_provider_archive_registration_discovery':False,'live_capture':False,'game_launch':False})
    write('source_pins.json',pins)
    print('R18 controls/archive and bounded R19 native/program evidence PASS',flush=True)

if __name__=='__main__':main()
