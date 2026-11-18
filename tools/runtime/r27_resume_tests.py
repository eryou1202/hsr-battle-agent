"""Durable missing-test validation: one runtime suite also covers R12-R26.

No production/test code is changed. Successful cases and their input hash are
persisted individually so an interrupted invocation need not repeat them.
"""
from __future__ import annotations
import collections
import ctypes
import datetime
import hashlib
import json
import os
import re
import sys
import time
import unittest
from pathlib import Path
from r27_checks import ROOT,AUDIT,read,sha
sys.path.insert(0,str(ROOT))
RESUME=AUDIT/'resume'
MODULES=['tests.battle_runtime.test_behavior_r'+str(n) for n in [*range(12,21),22,23,24,25,26]]

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save(name,value):
    path=RESUME/name;path.parent.mkdir(parents=True,exist_ok=True)
    staging=path.with_name(path.name+'.tmp')
    staging.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    for attempt in range(20):
        try:
            staging.replace(path)
            break
        except PermissionError:
            if attempt==19:raise
            time.sleep(.1)

def flat(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from flat(test)
        else:yield test

def inputs():
    gate=read(AUDIT/'start_gate.json')
    hashes={name:sha(ROOT/name) for name in gate['file_hashes']}
    assert hashes==gate['file_hashes'],'starting files changed: validate before reusing receipts'
    for name in ['r27_reader.py','r27_character.py','r27_monster_execute.py','r27_resume_tests.py']:
        hashes['tools/runtime/'+name]=sha(ROOT/'tools/runtime'/name)
    hashes['tests/battle_runtime/test_behavior_r27.py']=sha(ROOT/'tests/battle_runtime/test_behavior_r27.py')
    # These are the generated artifacts actually consumed by the eight R27 cases.
    artifacts=['reader_schemas.json','reader_dispatch.json','character/catalog_additions.json',
        'monster/selected_actors.json','monster/exact_joins.json','monster/character_configs.json']
    artifacts += ['monster/'+name+'_table.json' for name in ('MonsterConfig','MonsterTemplateConfig','MonsterSkillConfig')]
    artifacts += [p.relative_to(AUDIT).as_posix() for p in sorted((AUDIT/'monster/execution').rglob('*.json'))]
    for name in artifacts:hashes[(AUDIT/name).relative_to(ROOT).as_posix()]=sha(AUDIT/name)
    return hashes

def acquire_lock():
    path=RESUME/'runner.lock'
    if path.exists():
        prior=read(path);pid=prior['pid']
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,pid)
        if handle:
            code=ctypes.c_ulong()
            try:
                if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code)) or code.value==259:
                    raise RuntimeError('A prior validation process may still be active; refusing duplicate PID '+str(pid))
            finally:kernel.CloseHandle(ctypes.c_void_p(handle))
        elif ctypes.get_last_error()!=87:
            raise RuntimeError('Cannot disprove live prior PID; refusing duplicate validation')
        path.unlink()
    with path.open('x',encoding='utf-8') as f:json.dump(dict(pid=os.getpid(),started=now()),f)
    return path

def main():
    RESUME.mkdir(parents=True,exist_ok=True)
    lock=acquire_lock()
    os.environ['TMP']=os.environ['TEMP']=str(RESUME/'test_tmp')
    (RESUME/'test_tmp').mkdir(exist_ok=True)
    try:
        fingerprint=inputs()
        code_hash=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
        loader=unittest.TestLoader()
        focused=list(flat(loader.loadTestsFromNames(MODULES)))
        full=list(flat(loader.discover(str(ROOT/'tests/battle_runtime'),pattern='test_*.py',top_level_dir=str(ROOT))))
        assert not loader.errors,loader.errors
        ids=[t.id() for t in full];focus_ids=[t.id() for t in focused]
        assert len(ids)==len(set(ids)) and set(focus_ids)<=set(ids)
        assert len(focus_ids)==449 and len(ids)==651
        state_path=RESUME/'case_results.json'
        if state_path.exists():
            state=read(state_path)
            if state['input_hash']!=code_hash:
                old=read(RESUME/'input_hashes.json')['files']
                changed={k for k in set(old)|set(fingerprint) if old.get(k)!=fingerprint.get(k)}
                assert changed=={'tools/runtime/r27_resume_tests.py'},'tested input drift: '+str(changed)
                save('runner_only_change_'+str(len(state['invocations']))+'.json',dict(
                    previous_input_hash=state['input_hash'],current_input_hash=code_hash,
                    changed_files=sorted(changed),reason='Durable receipt writer Windows sharing-violation retry; tested code and input bytes unchanged',
                    previous_hashes=old,current_hashes=fingerprint))
                state['input_hash']=code_hash
        else:state=dict(input_hash=code_hash,cases={},invocations=[])
        previous=read(AUDIT/'syntax_validation.json')['files']
        # Preserve the complete eight-case PASS from the prior phase. Their source
        # and consumed generated artifacts predate that completed log.
        old_log=AUDIT/'R27_focused.txt';body=old_log.read_text(encoding='utf-8')
        assert re.search(r'Ran 8 tests',body) and body.strip().endswith('OK')
        for name in ['tools/runtime/r27_reader.py','tools/runtime/r27_character.py','tools/runtime/r27_monster_execute.py','tests/battle_runtime/test_behavior_r27.py']:
            assert sha(ROOT/name)==previous[name],name
        generated=[ROOT/name for name in fingerprint if name.startswith('tmp/')]
        assert all(p.stat().st_mtime<=old_log.stat().st_mtime for p in generated),'R27 inputs changed after prior completed test log'
        reused=[]
        for identity in ids:
            if identity.startswith('tests.battle_runtime.test_behavior_r27.'):
                state['cases'].setdefault(identity,dict(status='PASS',authority='REUSED_COMPLETE_R27_FOCUSED_LOG',
                    receipt='../R27_focused.txt',receipt_sha256=sha(old_log),input_hash=code_hash))
                reused.append(identity)
        assert len(reused)==8
        pending=[t for t in full if t.id() not in state['cases']]
        invocation=dict(pid=os.getpid(),started=now(),command=sys.argv,python=sys.executable,
            input_hash=code_hash,tests_pending=len(pending),runtime_cases=len(ids),focused_subset_cases=len(focus_ids),
            reused_completed_R27_cases=len(reused))
        state['invocations'].append(invocation)
        save('input_hashes.json',dict(head=read(AUDIT/'start_gate.json')['head'],input_hash=code_hash,files=fingerprint))
        save('selection.json',dict(runtime_cases=ids,focused_subset_cases=focus_ids,reused_R27_cases=reused,
            method='Normal unittest runtime discovery order; identical R12-R26 case IDs are a separately reported subset, not a second execution'))
        save('case_results.json',state);save('process.json',invocation)
        def persist(active=None):
            save('case_results.json',state)
            save('progress.json',dict(input_hash=code_hash,pid=os.getpid(),updated=now(),active_test=active,
                completed=len(state['cases']),required=len(ids),
                status_counts=dict(collections.Counter(r['status'] for r in state['cases'].values()))))
        class Result(unittest.TextTestResult):
            started=time.monotonic()
            def startTest(self,test):
                self.started=time.monotonic();persist(test.id());super().startTest(test)
            def record(self,test,status,detail=None):
                state['cases'][test.id()]=dict(status=status,duration_seconds=round(time.monotonic()-self.started,6),
                    finished=now(),input_hash=code_hash,detail=detail)
                persist()
            def addSuccess(self,test):super().addSuccess(test);self.record(test,'PASS')
            def addFailure(self,test,err):super().addFailure(test,err);self.record(test,'FAIL',self._exc_info_to_string(err,test))
            def addError(self,test,err):super().addError(test,err);self.record(test,'ERROR',self._exc_info_to_string(err,test))
            def addSkip(self,test,reason):super().addSkip(test,reason);self.record(test,'SKIP',reason)
            def addExpectedFailure(self,test,err):super().addExpectedFailure(test,err);self.record(test,'EXPECTED_FAILURE')
            def addUnexpectedSuccess(self,test):super().addUnexpectedSuccess(test);self.record(test,'UNEXPECTED_SUCCESS')
            def addSubTest(self,test,subtest,err):
                super().addSubTest(test,subtest,err)
                if err is not None:self.record(test,'FAIL',self._exc_info_to_string(err,subtest))
        print(json.dumps(invocation),flush=True)
        with (RESUME/'unittest_stream.txt').open('a',encoding='utf-8',buffering=1) as stream:
            result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.TestSuite(pending))
        after=inputs();assert after==fingerprint,'input bytes changed during validation'
        invocation.update(finished=now(),returncode=0 if result.wasSuccessful() else 1,tests_run=result.testsRun)
        persist()
        receipts={}
        for name,selected in [('R12_R26',focus_ids),('battle_runtime_FAST_UNIT',ids)]:
            outcomes=[state['cases'].get(i,dict(status='NOT_COMPLETED')) for i in selected]
            ok=all(r['status'] in ('PASS','SKIP','EXPECTED_FAILURE') for r in outcomes)
            receipt=dict(returncode=0 if ok else 1,tests=len(selected),
                command=[sys.executable,'tools/runtime/r27_resume_tests.py'],
                receipt='resume/case_results.json',stream='resume/unittest_stream.txt',
                input_hash=code_hash,input_hashes='resume/input_hashes.json',code_unchanged_during_run=True,
                selected_case_ids=selected,status_counts=dict(collections.Counter(r['status'] for r in outcomes)),
                coverage_method='One runtime discovery execution, explicit focused subset; eight completed R27 cases reused',
                independent_duplicate_suite_launched=False)
            receipts[name]=receipt
            (AUDIT/('verified_'+name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        final={name:read(AUDIT/('verified_'+name+'.json')) for name in ['R12_R26','R21','battle_ir_FAST_UNIT','battle_runtime_FAST_UNIT','battle_sandbox_FAST_UNIT']}
        (AUDIT/'final_tests.json').write_text(json.dumps(final,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        save('completion.json',dict(finished=now(),returncode=0 if all(r['returncode']==0 for r in final.values()) else 1,
            receipts=receipts,invocation=invocation,input_hash=code_hash))
        print(json.dumps({k:dict(returncode=v['returncode'],tests=v['tests'],status_counts=v['status_counts']) for k,v in receipts.items()}),flush=True)
        return 0 if all(r['returncode']==0 for r in final.values()) else 1
    finally:
        lock.unlink(missing_ok=True)

if __name__=='__main__':raise SystemExit(main())
