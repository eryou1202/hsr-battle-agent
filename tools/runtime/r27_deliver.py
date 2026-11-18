"""Deliver the already validated R27 archive and verify destination bytes."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from r27_checks import AUDIT,read,sha,write,preserve

def main():
    receipt=read(AUDIT/'handoff_verification.json')
    assert receipt['status']=='PASS'
    source=Path(receipt['source_archive']);destination=Path(receipt['destination'])
    assert sha(source)==receipt['ZIP_sha256']
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        assert sha(destination)==receipt['ZIP_sha256'],'Refuse to overwrite a different existing handoff'
    else:shutil.copyfile(source,destination)
    assert sha(destination)==receipt['ZIP_sha256']
    expected=receipt['members']
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(expected) and set(archive.namelist())==set(expected)
        for name,row in expected.items():
            data=archive.read(name)
            assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
    preservation=preserve()
    result=dict(status='PASS',destination=str(destination),ZIP_sha256=sha(destination),
        archive_size=destination.stat().st_size,member_count=len(expected),CRC='PASS',
        exact_file_set='PASS',member_sizes='PASS',member_SHA256='PASS',
        source_equals_destination=True,inherited_file_drift=len(preservation['changed_starting_files']),git_writes='NONE')
    write('handoff_delivery_verification.json',result)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
