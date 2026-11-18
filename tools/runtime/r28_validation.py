"""Pinned inherited receipts and fresh regression lanes; no duplicate long suite."""
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from r28_execution import ROOT,AUDIT,OLD,read,write


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def inherited():
    pin=read(OLD/'resume/input_hashes.json')
    changed=[n for n,h in pin['files'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    assert not changed,changed
    tests=read(OLD/'release_tests.json')
    write('tests/inherited_exact_input_receipts.json',dict(
        mode='REVALIDATED_PRIOR_PASS_NOT_A_FRESH_RUN',verified_at=now(),
        tested_input_hashes=pin,original_receipts=tests,changed_tested_files=changed,
        new_modules='R28 opt-in modules tested separately; no inherited implementation modified'))
    gate=read(AUDIT/'start_gate.json')
    assert not [n for n,h in gate['file_hashes'].items() if sha(ROOT/n)!=h]
    # Preserve prior audit and frozen regression artifacts, not just source.
    manifest=read(OLD/'handoff_manifest.json')
    invalid=[n for n,pin in manifest['files'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=pin['sha256'] or (ROOT/n).stat().st_size!=pin['size']]
    assert not invalid,invalid
    write('tests/prior_manifest_contract.json',dict(manifest=manifest,manifest_sha256=sha(OLD/'handoff_manifest.json')))
    write('preservation.json',dict(starting_files_checked=len(gate['file_hashes']),changed_files=[],
        frozen_drift=0,git_writes='NONE',head=gate['head']))


def fresh():
    lanes={n:['-m','unittest','discover','-s','tests/'+n,'-t','.','-p','test_*.py'] for n in ('battle_ir','battle_sandbox')}
    lanes['R21']=['-m','unittest','discover','-s','tools/runtime','-p','r21_specs.py']
    lanes['R27']=['-m','unittest','tests.battle_runtime.test_behavior_r27']
    lanes['R28']=['-m','unittest','tests.battle_runtime.test_behavior_r28']
    if len(sys.argv)>2:lanes={k:v for k,v in lanes.items() if k in sys.argv[2:]}
    hashes={p.relative_to(ROOT).as_posix():sha(p) for base in ('src','tests','tools/runtime','data/overlays')
            for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    hash_name='inputs_'+fingerprint+'.json'
    write('tests/'+hash_name,hashes)
    def run(item):
        name,args=item;command=[sys.executable,*args];started=now()
        temp=AUDIT/'test_tmp'/name;temp.mkdir(parents=True,exist_ok=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),TMP=str(temp),TEMP=str(temp)))
        body=(result.stdout+result.stderr).decode('utf8',errors='replace')
        (AUDIT/'tests'/(name+'.log')).write_text(body,encoding='utf8')
        count=re.search(r'Ran (\d+) tests?',body)
        row=dict(command=command,exit_code=result.returncode,tests=int(count[1]) if count else None,
                 started=started,timestamp=now(),tested_input_hashes=hash_name)
        write('tests/'+name+'.json',row);print(name,row,flush=True)
        assert result.returncode==0
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,lanes.items()))


if __name__=='__main__':{'inherited':inherited,'fresh':fresh}[sys.argv[1]]()
