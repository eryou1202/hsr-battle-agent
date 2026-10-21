"""Evidence-preserving structural dependency joins for canonical Behavior IR.

Serialized directory names are keys, never evidence by themselves. Entries require
trusted source framing supplied by the structural reader boundary. This catalog
does not admit actors, install modifiers or assign native execution semantics.
"""
from __future__ import annotations
import copy
from collections import defaultdict
from .behavior import IRNode, stable_hash

REFERENCE_TYPES = ('ABILITY_REFERENCE', 'TEMPLATE_REFERENCE', 'MODIFIER_REFERENCE',
                   'PASSIVE_REFERENCE', 'CALLBACK_REFERENCE',
                   'PRESENTATION_ABILITY_REFERENCE', 'UNKNOWN_REFERENCE')
DIRECTORY_TYPES = {'ABILITY_REFERENCE': 1, 'PASSIVE_REFERENCE': 1,
                   'TEMPLATE_REFERENCE': 2, 'MODIFIER_REFERENCE': 0}

def walk(value, pointer=''):
    if isinstance(value, dict):
        yield pointer, value
        for key, child in value.items():
            yield from walk(child, pointer+'/'+str(key).replace('~','~0').replace('/','~1'))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, pointer+'/'+str(i))

def field(node, mask):
    return next((f for f in node.get('fields', []) if int(f.get('mask', 0)) == mask), None)

def literal(node):
    if not isinstance(node, dict): return None
    if node.get('kind') == 'string': return node.get('value')
    if node.get('type') == 'RPG.GameCore.DynamicString' and int(node.get('bitmap', 0)) == 4:
        f = field(node, 4)
        if f and len(f.get('values', [])) == 1: return literal(f['values'][0])
    if node.get('child'): return literal(node['child'])
    return None

def references(graph):
    """Known serialized slots only; retain dynamic/context operands as unresolved.

    TriggerAbility mask 16 is the R15 explicit reference-model role. Native field
    naming remains unclaimed. Modifier/callback/task-list reader shapes are the
    archived exact-build contracts; inline bodies retain their own source spans.
    """
    roles = {'RPG.GameCore.TriggerAbility': (16, 'ABILITY_REFERENCE'),
             'RPG.GameCore.IncludeTaskListTemplate': (2, 'TEMPLATE_REFERENCE'),
             'RPG.GameCore.AddModifier': (8, 'MODIFIER_REFERENCE'),
             'RPG.GameCore.RemoveModifier': (4, 'MODIFIER_REFERENCE'),
             'RPG.GameCore.ByIsContainModifier': (8, 'MODIFIER_REFERENCE'),
             'RPG.GameCore.SkillConfig': (1 << 38, 'ABILITY_REFERENCE')}
    for pointer, node in walk(graph):
        typ = node.get('type')
        if not isinstance(typ, str): continue
        if typ in roles:
            mask, kind = roles[typ]
            f = field(node, mask)
            if not f: continue
            values = f.get('values', [])
            identity = literal(values[0]) if len(values) == 1 else None
            yield {'reference_type': kind, 'pointer': pointer+'/fields/'+str(node['fields'].index(f)),
                   'node_pointer':pointer, 'span': [f.get('start'), f.get('end')],
                   'field_identity': {'reader': node.get('reader'), 'type': typ, 'mask': mask},
                   'serialized_value': copy.deepcopy(values), 'identity': identity,
                   'role_authority': 'ARCHIVED_STRUCTURAL_SLOT_WITH_EXPLICIT_REFERENCE_POLICY',
                   'template_bindings': {str(m):copy.deepcopy(field(node,m)) for m in (4,8,16,32) if field(node,m)}
                        if kind == 'TEMPLATE_REFERENCE' else None}
        if typ == 'RPG.GameCore.CharacterConfig':
            f = field(node, 1 << 26)
            for vp, v in walk(f or {}):
                if v.get('kind') == 'string':
                    yield {'reference_type':'PASSIVE_REFERENCE','pointer':pointer+'/fields/'+str(node['fields'].index(f))+vp,
                           'span':[v.get('start'),v.get('end')], 'field_identity':{'reader':node.get('reader'),
                           'type':typ,'mask':1<<26}, 'serialized_value':copy.deepcopy(v),'identity':v.get('value')}
        if typ in ('RPG.GameCore.TaskListTemplate','RPG.GameCore.TurnBasedModifierCallbackConfig'):
            # Inline graphs are content bodies, not active instances or registrations.
            yield {'reference_type':'TEMPLATE_REFERENCE' if typ.endswith('TaskListTemplate') else 'CALLBACK_REFERENCE',
                   'pointer':pointer,'span':[node.get('start'),node.get('end')],
                   'field_identity':{'reader':node.get('reader'),'type':typ,'storage':'INLINE_BODY'},
                   'serialized_value':copy.deepcopy(node), 'identity':literal((field(node,1) or {}).get('values',[{}])[0]),
                   'inline':True}
        if typ == 'RPG.GameCore.TurnBasedAbilityConfig':
            modifiers=field(node,256)
            for vi,value in enumerate((modifiers or {}).get('values',[])):
                items=value.get('children',[])
                for i in range(0,len(items)-1,2):
                    key,body=items[i:i+2]
                    identity=literal(key)
                    if isinstance(identity,str) and body.get('type')=='RPG.GameCore.TurnBasedModifierConfig':
                        yield {'reference_type':'MODIFIER_REFERENCE','pointer':pointer+'/fields/'+str(node['fields'].index(modifiers))+
                               '/values/'+str(vi)+'/children/'+str(i+1),
                               'span':[body.get('start'),body.get('end')], 'field_identity':{'reader':node.get('reader'),
                               'type':typ,'mask':256,'storage':'INLINE_NAMED_DICTIONARY'},
                               'serialized_key':copy.deepcopy(key),'serialized_value':copy.deepcopy(body),
                               'identity':identity,'inline':True,'definition':True}
            for mask in (4,8,16,1024):
                f = field(node,mask)
                if f and any(v.get('children') for v in f.get('values',[])):
                    yield {'reference_type':'CALLBACK_REFERENCE','pointer':pointer+'/fields/'+str(node['fields'].index(f)),
                           'span':[f.get('start'),f.get('end')], 'field_identity':{'reader':node.get('reader'),
                           'type':typ,'mask':mask,'storage':'LIFECYCLE_SLOT'}, 'serialized_value':copy.deepcopy(f),
                           'identity':None,'inline':True,'lifecycle':True,'entry':mask==16}

def source_key(entry):
    return (entry['source_shard_sha256'], entry.get('absolute', entry.get('record_start')),
            entry['record_end'])

class ContentCatalog:
    """Fail-closed catalog of trusted directory identities and compiled graphs."""
    def __init__(self, directories, records=()):
        self.directories = defaultdict(dict)
        self.records = {}
        self.definitions = defaultdict(dict)
        for entry in directories:
            key = source_key(entry)
            if (not isinstance(key[0], str) or len(key[0]) != 64 or
                not isinstance(key[1], int) or not isinstance(key[2], int) or key[2] <= key[1] or
                entry.get('parent_framing') != 'EXACT_LIST_DICTIONARY_GRAMMAR_0x1EB94850' or
                not entry.get('layout', {}).get('hash') or
                not isinstance(entry.get('directory_entry_start'), int) or
                not isinstance(entry.get('directory_entry_end'), int)):
                raise ValueError('trusted serialized directory framing required')
            bucket = self.directories[(entry['name'],entry['type'])]
            if key in bucket and bucket[key] != entry:
                raise ValueError('conflicting structural directory identity')
            bucket[key] = copy.deepcopy(entry)
        for record in records: self.add(record)

    def add(self, record):
        key = source_key(record)
        if not any(key in bucket for bucket in self.directories.values()):
            raise ValueError('record has no trusted directory identity')
        if record.get('entry') and source_key(record['entry']) != key:
            raise ValueError('record and directory source identities disagree')
        if record.get('graph') is not None:
            graph=record['graph']
            if (graph.get('start'),graph.get('end')) != key[1:]:
                raise ValueError('decoded body and trusted source framing disagree')
            if record.get('consumption_status') != 'BOUNDED_FULL_CONSUMPTION':
                raise ValueError('full bounded structural consumption required')
        if record.get('graph') is not None and stable_hash(record['graph']) != record['graph_hash']:
            raise ValueError('structural graph hash mismatch')
        if record.get('ir') is not None:
            ir = IRNode.from_dict(record['ir'])
            if ir.stable_hash() != record['canonical_IR_hash']:
                raise ValueError('canonical IR hash mismatch')
        if key in self.records and self.records[key] != record:
            raise ValueError('conflicting source graph identity')
        self.records[key] = copy.deepcopy(record)
        if record.get('graph') is not None:
            for site in references(record['graph']):
                if not site.get('inline') or not isinstance(site.get('identity'),str):continue
                kind=DIRECTORY_TYPES.get(site['reference_type'])
                if kind is None:continue
                start,end=site['span']
                if not isinstance(start,int) or not isinstance(end,int) or not key[1]<=start<end<=key[2]:
                    raise ValueError('inline definition outside exact parent framing')
                inline_key=(key[0],start,end)
                definition={'inline_source_identity':list(inline_key),'parent_source_identity':list(key),
                            'parent_directory_identity':record.get('entry'), 'field_identity':site['field_identity'],
                            'source_pointer':site['pointer'],'serialized_name':site['identity'],
                            'serialized_key':site.get('serialized_key'),'graph_hash':stable_hash(site['serialized_value']),
                            'canonical_parent_IR_hash':record.get('canonical_IR_hash'),
                            'CONTENT_GRAPH_PRESENT':True,'compiled_inside_parent_IR':bool(record.get('ir')),
                            'effective_scope_and_inheritance':'UNKNOWN'}
                bucket=self.definitions[(site['identity'],kind)]
                if inline_key in bucket and bucket[inline_key]!=definition:
                    raise ValueError('conflicting inline structural identity')
                bucket[inline_key]=definition

    def resolve(self, site):
        result = copy.deepcopy(site)
        if site.get('inline'):
            parent=self.records.get(tuple(site.get('parent_source_identity',[])),{})
            result.update(status='EXACT_RESOLVED_COMPILED' if parent.get('ir') else 'EXACT_REFERENCE_GRAPH_UNDECODED',
                          structural_status='CONTENT_GRAPH_PRESENT', registration='NOT_IMPLIED', execution='POLICY_REQUIRED',
                          resolved_inline_identity=[site.get('parent_source_identity',[None])[0],*site['span']],
                          resolved_graph_hash=stable_hash(site['serialized_value']),
                          canonical_IR_hash=parent.get('canonical_IR_hash'),
                          resolution_evidence={'relation':'inline body in exact parent record','span':site['span'],
                                               'parent_source_identity':site.get('parent_source_identity')})
            return result
        kind = DIRECTORY_TYPES.get(site['reference_type'])
        if not isinstance(site.get('identity'), str) or kind is None:
            result['status'] = 'CONTEXT_BINDING_UNRESOLVED'; return result
        candidates = self.directories.get((site['identity'],kind),{})
        if not candidates:
            definitions=self.definitions.get((site['identity'],kind),{})
            if definitions:
                result.update(status='CONTEXT_BINDING_UNRESOLVED' if len(definitions)==1 else 'AMBIGUOUS_REFERENCE',
                    structural_status='CONTENT_GRAPH_PRESENT',candidate_inline_definitions=list(definitions.values()),
                    resolution_evidence={'relation':'serialized reference matches inline serialized name/key within trusted parent record'},
                    required_context_policy='EXPLICIT_INLINE_DEFINITION_SCOPE_AND_PARAMETER_INHERITANCE',
                    modifier_instance_active='NOT_IMPLIED',callback_registered='NOT_IMPLIED',callback_executable='NOT_IMPLIED')
                return result
        if len(candidates) != 1:
            result['status'] = 'AMBIGUOUS_REFERENCE' if candidates else 'REFERENCE_NOT_FOUND'
            result['candidate_source_identities'] = [list(k) for k in sorted(candidates)]
            return result
        key, entry = next(iter(candidates.items()))
        record = self.records.get(key, {})
        result.update(target_source_identity=list(key), resolved_directory_identity=entry,
                      resolved_graph_hash=record.get('graph_hash'), canonical_IR_hash=record.get('canonical_IR_hash'),
                      resolution_evidence={'relation':'serialized reference value equals trusted serialized directory key',
                         'directory_span':[entry['directory_entry_start'],entry['directory_entry_end']],
                         'layout_hash':entry['layout']['hash'], 'source_identity':list(key)},
                      status=('EXACT_RESOLVED_COMPILED' if record.get('ir') else
                              'EXACT_REFERENCE_READER_GAP' if record.get('reader_gap') or record.get('status')=='STRUCTURAL_READER_GAP' else
                              'EXACT_REFERENCE_GRAPH_UNDECODED'), reader_gap=record.get('reader_gap'),
                      question=record.get('question'))
        return result

    def executable_abilities(self):
        # Canonical names bind only after globally unique exact source resolution.
        result = {}
        for name, typ in sorted(self.directories):
            if typ != 1: continue
            resolved = self.resolve({'reference_type':'ABILITY_REFERENCE','identity':name})
            if resolved['status']=='EXACT_RESOLVED_COMPILED':
                result[name] = IRNode.from_dict(self.records[tuple(resolved['target_source_identity'])]['ir'])
        return result

    def compiled_templates(self):
        """Content presence only. Entry/parameter mapping still needs caller policy."""
        result = {}
        for name, typ in sorted(self.directories):
            if typ != 2: continue
            resolved = self.resolve({'reference_type':'TEMPLATE_REFERENCE','identity':name})
            if resolved['status']=='EXACT_RESOLVED_COMPILED':
                result[name] = IRNode.from_dict(self.records[tuple(resolved['target_source_identity'])]['ir'])
        return result

    def modifier_definitions(self):
        """Exact source-backed definitions, including inline bodies; no activation.

        Numeric policies and unknown fields remain decoded data. The paired
        canonical IR body supplies callback tasks without handwritten content.
        """
        result = {}
        for key, record in sorted(self.records.items()):
            if not record.get('graph') or not record.get('ir'):
                continue
            parent = IRNode.from_dict(record['ir'])
            decoded = parent.to_dict()['payload'].get('decoded')
            named = {tuple(s['span']): s['identity'] for s in references(record['graph'])
                     if s.get('definition')}
            named_sites = {s['pointer']: s['identity'] for s in references(record['graph']) if s.get('definition')}
            for pointer, graph in walk(record['graph']):
                if graph.get('type') != 'RPG.GameCore.TurnBasedModifierConfig':
                    continue
                if graph.get('child', {}).get('type') == 'RPG.GameCore.TurnBasedModifierConfig':
                    continue  # Reader envelope, not a second decoded definition.
                start, end = graph.get('start'), graph.get('end')
                if type(start) is not int or type(end) is not int or not key[1] <= start < end <= key[2]:
                    raise ValueError('modifier definition outside pinned parent span')
                body = decoded
                for token in pointer.strip('/').split('/') if pointer else []:
                    token = token.replace('~1', '/').replace('~0', '~')
                    body = body[int(token)] if isinstance(body, list) else body[token]
                source = [key[0], start, end]
                graph_hash = stable_hash(graph)
                identity = stable_hash({'source_identity': source, 'graph_hash': graph_hash})
                definition = {'definition_id': identity,
                    'config_identity': (record['identity'] if not pointer or pointer == '/child' else
                        named.get((start,end), next((name for path,name in named_sites.items()
                            if pointer.startswith(path+'/child')), None))),
                    'source_identity': source, 'parent_source_identity': list(key),
                    'source_version': parent.authority.source_version,
                    'source_artifact': parent.authority.source_artifact,
                    'source_artifact_sha256': parent.authority.source_sha256,
                    'source_span': [start,end], 'source_pointer': pointer,
                    'graph_hash': graph_hash, 'canonical_parent_IR_hash': parent.stable_hash(),
                    'native_references': sorted({n['reader'] for _,n in walk(graph) if isinstance(n.get('reader'),str)}),
                    'decoded_graph': copy.deepcopy(graph), 'compiled_decoded': copy.deepcopy(body),
                    'decoded_fields': copy.deepcopy(graph.get('fields', [])),
                    'unknown_fields': copy.deepcopy(graph.get('fields', [])),
                    'evidence_boundary': 'DECODED_MODIFIER_DEFINITION',
                    'semantic_authority': 'REFERENCE_MODEL', 'native_activation': 'NATIVE_EFFECTIVE_STATE_UNKNOWN'}
                # Exact coordinates/hash define uniqueness, independently of CR counts.
                if identity in result:
                    previous = result[identity]
                    if previous['compiled_decoded'] != definition['compiled_decoded']:
                        # Node paths/parent authority may differ; serialized body must agree.
                        if previous['decoded_graph'] != definition['decoded_graph']:
                            raise ValueError('conflicting exact modifier source')
                    continue
                result[identity] = definition
        return result

    def snapshot(self):
        return {'schema':'generic_content_catalog/1',
                'directories':[copy.deepcopy(entry) for _,bucket in sorted(self.directories.items())
                               for _,entry in sorted(bucket.items())],
                'records':[copy.deepcopy(record) for _,record in sorted(self.records.items())]}

    @classmethod
    def from_snapshot(cls, snapshot):
        if set(snapshot) != {'schema','directories','records'} or snapshot['schema'] != 'generic_content_catalog/1':
            raise ValueError('versioned catalog snapshot required')
        return cls(snapshot['directories'],snapshot['records'])

    def clone(self):
        return type(self).from_snapshot(self.snapshot())

    def stable_hash(self):
        return stable_hash(self.snapshot())

    def closure(self, roots, decode=None, *, max_records=4096, max_edges=20000, max_depth=32):
        visited, active, edges, cycles, gaps = set(), set(), [], [], []
        def visit(key, depth):
            if key in active: cycles.append(list(key)); return
            if key in visited: return
            if depth>max_depth or len(visited)>=max_records:
                gaps.append({'source_identity':list(key),'status':'WORK_BOUND','depth':depth}); return
            active.add(key); visited.add(key)
            record = self.records.get(key)
            if (not record or not record.get('graph')) and decode:
                entry=next((bucket[key] for bucket in self.directories.values() if key in bucket),None)
                if entry:
                    decoded=decode(entry)
                    if decoded:
                        self.add(decoded); record=self.records[key]
            if record and record.get('graph'):
                for site in references(record['graph']):
                    if len(edges)>=max_edges:
                        gaps.append({'source_identity':list(key),'status':'EDGE_BOUND'}); break
                    site.update(parent_source_identity=list(key),parent_graph_hash=record['graph_hash'],
                                parent_graph_id=record.get('identity'))
                    edge=self.resolve(site)
                    edge.update(parent_source_identity=list(key),parent_graph_hash=record['graph_hash'],
                                parent_graph_id=record.get('identity'),depth=depth)
                    target=tuple(edge.get('target_source_identity',[]))
                    if target and decode and not self.records.get(target,{}).get('graph'):
                        decoded=decode(edge['resolved_directory_identity'])
                        if decoded:
                            self.add(decoded); edge.update(self.resolve(site))
                    edges.append(edge)
                    if target: visit(target,depth+1)
            active.remove(key)
        for root in sorted(set(tuple(r) for r in roots)): visit(root,0)
        return {'edges':edges,'visited_source_identities':[list(k) for k in sorted(visited)],
                'cycles':cycles,'bounds':{'records':max_records,'edges':max_edges,'depth':max_depth},'work_gaps':gaps}


def classify_dependency(record):
    """Inspect decoded tasks; graph names are deliberately not an input."""
    if not record or not record.get('graph'):
        return {'classification':'UNKNOWN','task_types':[],'evidence':'No fully decoded referenced body'}
    types=sorted({n['type'] for _,n in walk(record['graph']) if isinstance(n.get('type'),str)
                  and n['type'].startswith('RPG.GameCore.')})
    short={t.rsplit('.',1)[-1] for t in types}
    flags=[]
    for category, primitives in [
        ('POSITION_RELEVANT',{'MoveToTargetPosition','MoveToTargetList','TriggerAnimStateWithMove','SetTeamFormation','SetSkillTargetFormationByPos'}),
        ('STATE_RELEVANT',{'DamageByAttackProperty','HealHP','AddModifier','RemoveModifier','ModifySPNew','StackProperty','SetDynamicValueByProperty'}),
        ('SCHEDULER_RELEVANT',{'TriggerAbility','WaitSecond','WaitAnimState','WaitTimelineFinish','SkillPerformFinish','TurnBasedModifierCallbackConfig'})]:
        if short & primitives: flags.append(category)
    return {'classification':flags[0] if flags else 'REFERENCE_POLICY_REQUIRED','evidence_categories':flags,
            'task_types':types,'graph_hash':record['graph_hash'],'source_identity':list(source_key(record)),
            'native_irrelevance_proven':False,'evidence':'Fully decoded concrete task identities; no name-based semantics',
            'rng_effects':'UNKNOWN_UNLESS_EXPLICITLY_BOUND','callbacks':'CONTENT_PRESENCE_DOES_NOT_REGISTER_CALLBACKS'}
