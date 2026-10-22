"""Independent final lanes with separate receipts, collected after all complete."""
import json
import os
import re
import subprocess
import sys
from r26_checks import AUDIT
from r21_checks import ROOT,read

LANES={'R12_R25':['-m','unittest',*['tests.battle_runtime.test_behavior_r'+str(n) for n in [*range(12,21),22,23,24,25]]],
       'R21':['-m','unittest','discover','-s','tools/runtime','-p','r21_specs.py']}
LANES.update({f+'_FAST_UNIT':['-m','unittest','discover','-s','tests/'+f,'-t','.', '-p','test_*.py']
              for f in ('battle_ir','battle_runtime','battle_sandbox')})

def run(name):
    args=[sys.executable,*LANES[name]]
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),TMP=str(AUDIT/'test_tmp'),TEMP=str(AUDIT/'test_tmp'))
    p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True)
    body=(p.stdout+p.stderr).decode('utf-8',errors='replace')
    (AUDIT/('verified_'+name+'.txt')).write_text(body,encoding='utf-8')
    match=re.search(r'Ran (\d+) tests?',body)
    receipt={'returncode':p.returncode,'tests':int(match[1]) if match else None,'command':args}
    (AUDIT/('verified_'+name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(name,receipt,flush=True)
    assert p.returncode==0,body[-8000:]

def collect():
    rows={name:read(AUDIT/('verified_'+name+'.json')) for name in LANES}
    assert all(r['returncode']==0 for r in rows.values())
    (AUDIT/'final_tests.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(rows),flush=True)

if __name__=='__main__':
    if sys.argv[1:] == ['collect']:collect()
    else:
        for name in sys.argv[1:] or LANES:run(name)
