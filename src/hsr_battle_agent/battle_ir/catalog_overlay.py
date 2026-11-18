"""Pinned, opt-in original content overlays. No frozen catalog mutation."""
import gzip
import hashlib
import json
from pathlib import Path
from .behavior import IRNode, stable_hash
from .content_catalog import ContentCatalog, source_key


def load_overlay(base, manifest_path):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['schema'] != 'original_content_overlay/1' or manifest['build'] != '4.6.51':
        raise ValueError('unsupported overlay contract')
    payload = (path.parent / manifest['payload']).resolve()
    if payload.parent != path.parent.resolve():
        raise ValueError('overlay payload must be a sibling')
    data = payload.read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest['payload_sha256']:
        raise ValueError('overlay payload hash mismatch')
    records = json.loads(gzip.decompress(data))
    if len(records) != len(manifest['records']):
        raise ValueError('overlay record count mismatch')
    replacements = {}
    for record, pin in zip(records, manifest['records']):
        key = source_key(record)
        if (list(key) != pin['source_identity'] or key in replacements or
                record['identity'] != pin['identity'] or
                stable_hash(record['graph']) != record['graph_hash'] or
                IRNode.from_dict(record['ir']).stable_hash() != pin['IR_hash']):
            raise ValueError('overlay identity/graph/IR mismatch')
        if key not in base.records:
            raise ValueError('overlay must replace an exact existing directory record')
        replacements[key] = record
    entries = [entry for bucket in base.directories.values() for entry in bucket.values()]
    return ContentCatalog(entries, {**base.records, **replacements}.values())
