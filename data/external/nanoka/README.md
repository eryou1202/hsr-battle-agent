# Nanoka external snapshots

This directory is the local, version-locked raw cache for the public Nanoka
HSR oracle.  It is intentionally ignored by Git because a complete detail
snapshot is generated data.  Recreate it with:

```powershell
python scripts/fetch_nanoka_snapshot.py 4.4.54 --locale zh
```

Raw payloads must not be edited.  `provenance/index.json` records URL,
version, locale, HTTP metadata, fetch time, and SHA-256 for every payload.
