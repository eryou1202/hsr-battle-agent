"""Run a reference planner or verify a previously serialized recommendation."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tools/runtime')]
from r26_reference_fixtures import encounter,request
from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime
from hsr_battle_agent.battle_runtime.planner_bridge import plan,replay_principal_variation,ALGORITHMS

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fixture',choices=['choice','turns','resource','targets','defense','real','multi'],default='resource')
    p.add_argument('--algorithm',choices=ALGORITHMS,default=ALGORITHMS[-1])
    p.add_argument('--output',type=Path)
    p.add_argument('--replay',type=Path,help='Directory containing initial_runtime.json and result.json')
    args=p.parse_args()
    if args.replay:
        initial=json.loads((args.replay/'initial_runtime.json').read_text(encoding='utf-8'))
        result=json.loads((args.replay/'result.json').read_text(encoding='utf-8'))
        r=BehaviorRuntime.from_snapshot(initial)
    else:
        r,_=encounter(args.fixture)
        initial=r.snapshot(); result=plan(r,request(r,algorithm=args.algorithm,horizon=4,width=4)).to_dict()
    end=replay_principal_variation(r,result)
    if args.output:
        args.output.mkdir(parents=True,exist_ok=True)
        for name,doc in [('initial_runtime',initial),('result',result),('final_runtime',end.snapshot())]:
            (args.output/(name+'.json')).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'chosen_action':result['chosen_action'],'status':result['status'],'counts':result['counts'],
        'replay_hash':end.stable_hash(),'replay':'PASS','original_unchanged':r.snapshot()==initial},indent=2),flush=True)

if __name__=='__main__':main()
