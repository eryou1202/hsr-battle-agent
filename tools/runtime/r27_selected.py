"""Reproduce basic/ultimate diversity probes with the explicit R27 catalog."""
from r27_checks import ROOT,AUDIT,write,read
import r23_reference_fixtures as fixtures
import r23_probes as probes
from r27_character import catalog_overlay

def main():
    original=fixtures.content();catalog=catalog_overlay(original[0],read(AUDIT/'character/catalog_additions.json'))
    view=(catalog,*original[1:]);fixtures.content=lambda:view;probes.content=lambda:view
    probes.write=lambda n,d:write('character/diversity/'+n,d)
    ranked=read(AUDIT/'character/all_160_ranked.json')
    graphs={g['record_identity']:g for g in original[-1]['graphs']}
    rows=[]
    for role in ('basic_attack','ultimate_related'):
        root=ranked['roles'][role]
        captured={}
        def create(*args,**kwargs):
            r,b,receipts=fixtures.joined_runtime(*args,**kwargs)
            captured['runtime']=r;captured['initial']=r.snapshot()
            return r,b,receipts
        probes.joined_runtime=create
        row=probes.execute(graphs[root['root']],templates=True,replay=True)
        row['selected_role']=role
        write('character/diversity/'+role+'/initial_runtime.json',captured['initial'])
        write('character/diversity/'+role+'/final_runtime.json',captured['runtime'].snapshot())
        rows.append(row)
        print(role,row['root'],'NEXT',row['required_capability'],flush=True)
    write('character/diversity/results.json',rows)

if __name__=='__main__':main()
