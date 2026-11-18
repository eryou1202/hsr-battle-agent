"""Exact original JsonEnum lookup; unknown keys never become zero."""
from .behavior import stable_hash


class JsonEnumProvider:
    @classmethod
    def from_overlay(cls, manifest_path):
        import gzip
        import hashlib
        import json
        from pathlib import Path
        path=Path(manifest_path)
        manifest=json.loads(path.read_text(encoding='utf8'))
        if manifest['schema']!='original_content_overlay/1' or manifest['build']!='4.6.51':
            raise ValueError('unsupported provider contract')
        pin=manifest['JsonEnum_provider']
        payload=(path.parent/pin['payload']).resolve()
        if payload.parent!=path.parent.resolve():raise ValueError('provider payload must be a sibling')
        data=payload.read_bytes()
        if hashlib.sha256(data).hexdigest()!=pin['payload_sha256']:raise ValueError('provider payload hash mismatch')
        return cls(json.loads(gzip.decompress(data)),pin['graph_hash'])

    def __init__(self, graph, expected_hash):
        if stable_hash(graph) != expected_hash:
            raise ValueError('JsonEnum provider hash mismatch')
        self.graph_hash = expected_hash
        self.values = {}
        categories = graph['fields'][0]['values'][0]['children']
        for i in range(0,len(categories),2):
            category = categories[i]['value']
            children = categories[i+1]['fields'][0]['values'][0]['children']
            for j in range(0,len(children),2):
                key = (category,children[j+1]['value'])
                self.values.setdefault(key,[]).append(children[j]['value'])

    def resolve(self, serialized_keys):
        if (len(serialized_keys)!=2 or any(type(v) is not int for v in serialized_keys)):
            raise ValueError('two signed source indexes required')
        values = self.values.get(tuple(serialized_keys),[])
        if len(values)!=1:
            raise ValueError('JSONENUM_SOURCE_LOOKUP_MISSING_OR_AMBIGUOUS')
        return {'serialized_lookup_keys':list(serialized_keys),'source_value':values[0],
                'provider_graph_hash':self.graph_hash,
                'authority':'ORIGINAL_TASK_SEMANTICS_SAME_BUILD_EVIDENCED',
                'native_effective_validated':False}
