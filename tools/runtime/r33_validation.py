"""Fresh test attempts, including failures, with final source/input hashes."""
from r33_authority import *

def runtime_retry():
    prior=read(AUDIT/'tests/results.json');write('tests/initial_attempt.json',prior)
    write('tests/final_input_hashes.json',{p.relative_to(ROOT).as_posix():sha(p) for d in ['src','tests','tools/runtime','data/control','data/overlays'] for p in (ROOT/d).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.gz','.cjs')})
    cmd=[sys.executable,'-X','faulthandler','-m','unittest','discover','-s','tests/battle_runtime','-t','.','-p','test_*.py','-v']
    log=AUDIT/'tests/battle_runtime_retry.log';start=now()
    with log.open('wb') as f:p=subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),TMP=str(AUDIT/'test_tmp'),TEMP=str(AUDIT/'test_tmp')),stdout=f,stderr=subprocess.STDOUT)
    m=re.search(r'Ran (\d+) tests?',log.read_text(encoding='utf8',errors='replace'))
    receipt=dict(command=cmd,actual_exit_code=p.returncode,case_count=int(m[1]) if m else None,started=start,finished=now(),input_hash_manifest_sha256=sha(AUDIT/'tests/final_input_hashes.json'),log_sha256=sha(log),reason='Retry initial Windows process exit 3221225477 with faulthandler and verbose identification; no runtime source changes')
    write('tests/runtime_retry.json',receipt);print(receipt,flush=True)
    return p.returncode

def preserve():
    g=read(AUDIT/'start_gate.json');changed=[n for n,h in g['file_hashes'].items() if not (ROOT/n).is_file() or sha(ROOT/n)!=h]
    pin=read(R27/'resume/input_hashes.json')['files'];old=read(R32/'preservation.json')['approved_pre_R32_differences_from_R27_pin']
    drift=[n for n,h in pin.items() if sha(ROOT/n)!=h and n not in old]
    row=dict(changed_inherited_files=changed,frozen_drift=drift,approved_pre_R32_differences_from_R27_pin=old,head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),staged_unchanged=git('diff','--cached','--name-status')==g['staged'],git_writes='NONE',frozen_modified=False,production_files_changed=[],frozen=[632,160,161],checked_files=len(g['file_hashes']))
    write('preservation.json',row);assert not changed and not drift and row['head']==g['head'] and row['branch']==g['branch'] and row['staged_unchanged']

def focused():
    args=[sys.executable,'-m','unittest','tests.battle_runtime.test_behavior_r33','-v'];start=now()
    p=subprocess.run(args,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True)
    log=AUDIT/'tests/R33.log';log.write_bytes(p.stdout+p.stderr)
    m=re.search(rb'Ran (\d+) tests?',p.stderr)
    write('tests/R33.json',dict(command=args,actual_exit_code=p.returncode,case_count=int(m[1]) if m else None,started=start,finished=now(),test_sha256=sha(ROOT/'tests/battle_runtime/test_behavior_r33.py'),control_hashes={n:sha(ROOT/n) for n in CONTROLS},source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').rglob('*.py')},log_sha256=sha(log)))
    print(p.stderr.decode());return p.returncode

def replay_regressions():
    import r30_closure as inherited
    inherited.AUDIT=AUDIT
    inherited.replays()

if __name__=='__main__':
    if sys.argv[1]=='runtime_retry':sys.exit(runtime_retry())
    elif sys.argv[1]=='focused':sys.exit(focused())
    elif sys.argv[1]=='replays':replay_regressions()
    elif sys.argv[1]=='preserve':preserve()
