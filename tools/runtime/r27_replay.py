"""Reconstruct every selected original character from commands and source pins."""
from r27_checks import ROOT,AUDIT,read,write
import r23_reference_fixtures as fixtures
from r27_character import catalog_overlay

def main():
    original=fixtures.content();catalog=catalog_overlay(original[0],read(AUDIT/'character/catalog_additions.json'))
    view=(catalog,*original[1:]);fixtures.content=lambda:view
    graphs={g['record_identity']:g for g in original[-1]['graphs']}
    rows=[]
    stages=read(AUDIT/'character/dependency_stages.json')
    for stage in stages:
        expected=stage['whole_original_parent']
        runtime,binding,_=fixtures.joined_runtime(graphs[expected['root']],templates_enabled=True)
        initial=runtime.snapshot()
        name=binding['binding_hash'][:16]+'_template'
        commands=read(AUDIT/'character/scenarios'/name/'commands.json')
        final,_=runtime.replay_turn_commands(commands)
        assert final.stable_hash()==expected['full_runtime_hash']
        assert runtime.snapshot()==initial
        folder='character/replay/'+expected['root']
        write(folder+'/initial_runtime.json',initial)
        write(folder+'/final_runtime.json',final.snapshot())
        rows.append(dict(root=expected['root'],initial_hash=runtime.stable_hash(),final_hash=final.stable_hash(),
            command_count=len(commands),status='PASS',initial_parent_unchanged=True))
        print('reconstructed',expected['root'],'PASS',flush=True)
    write('character/independent_replay.json',dict(status='PASS',roots=rows))

if __name__=='__main__':main()
