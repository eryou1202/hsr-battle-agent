"""Package only R27-owned additions; validate CRC, names, sizes and hashes."""
import hashlib
import json
import zipfile
from pathlib import Path
from r27_checks import ROOT,AUDIT,CR,read,write,sha,preserve
from r27_finalize import REPORT,CONTROL_NAMES,SUFFIX

def main():
    preserve()
    assert read(AUDIT/'final_summary.json')['native_correctness']=='NOT_CLAIMED'
    files=[p for p in (ROOT/'tools/runtime').glob('r27_*') if p.is_file()]
    files+=[ROOT/'tests/battle_runtime/test_behavior_r27.py',ROOT/REPORT]
    files+=[ROOT/f'data/control/generic_runtime_{n}_{SUFFIX}.json' for n in CONTROL_NAMES]
    excluded={'handoff_manifest.json','handoff_verification.json','handoff_delivery_verification.json'}
    files += [p for p in AUDIT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'test_tmp' not in p.parts
              and p.suffix!='.zip' and p.name not in excluded]
    members={p.relative_to(ROOT).as_posix():dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(set(files))}
    assert all(n.startswith(('tools/runtime/r27_','tests/battle_runtime/test_behavior_r27.py',
        'data/control/generic_runtime_real_','data/control/generic_runtime_exact_source_acquisition_',
        'docs/agent/handoffs/generic_runtime_real_character_monster_closure_',
        'tmp/audit/r27_real_character_monster_20261022_001/')) for n in members)
    assert not any(Path(n).suffix.lower() in {'.dll','.bytes','.dat','.exe','.pyc'} for n in members)
    gate=read(AUDIT/'start_gate.json')
    assert all(n not in gate['file_hashes'] or n=='tools/runtime/r27_checks.py' for n in members if not n.startswith('tmp/'))
    manifest=dict(change_request=CR,starting_head=gate['head'],scope='ONLY_R27_OWNED_ADDITIONS',files=members,
        production_files=[],source_game_binaries_included=False,git_writes='NONE')
    write('handoff_manifest.json',manifest)
    manifest_name=(AUDIT/'handoff_manifest.json').relative_to(ROOT).as_posix()
    archive=AUDIT/(CR+'_changed_files.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n in [*members,manifest_name]:
            info=zipfile.ZipInfo(n,(2026,10,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,(ROOT/n).read_bytes())
    expected={**members,manifest_name:dict(size=(AUDIT/'handoff_manifest.json').stat().st_size,sha256=sha(AUDIT/'handoff_manifest.json'))}
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(expected) and set(z.namelist())==set(expected)
        for n,row in expected.items():
            data=z.read(n)
            assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
    result=dict(status='PASS',CRC='PASS',exact_file_set='PASS',member_sizes='PASS',member_SHA256='PASS',
        source_archive=str(archive),destination=str(Path('D:/HSR_Battle_Agent/agent_handoffs')/archive.name),
        ZIP_sha256=sha(archive),archive_size=archive.stat().st_size,members=expected)
    write('handoff_verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='members'}),flush=True)

if __name__=='__main__':main()
