"""Pinned R14 corpus plumbing. Reuses exact archived readers, never scans payloads.

Path transforms only discover candidate assets. Owner/root edges require decoded
relation fields and an unambiguous serialized directory identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(Path(__file__).parent))
from r13_frozen_reader import (FrozenReader, StructuralGap, MANIFEST_SHA, R102,
                               R11, R11C, pinned_source, reuse_recorded_readers)
from r12_runtime_reentry import walk_dicts

AUDIT = REPO / 'tmp/audit/r14_real_combat_corpus_20261008_001'
SUFFIX = '20261008_001'
CR = 'CR-R14-REAL-COMBAT-CORPUS-CAPABILITY-DISCOVERY-20261008-001'
INDEX = 'StarRail_Data/Persistent/DesignData/Windows/DesignV_46462ce82b89158eb9139524ef7d89c6.bytes'


def read(path):
    return json.loads((REPO / path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                              allow_nan=False) + '\n', encoding='utf-8')


def path_hash(path):
    """Exact seed-zero XXH64, transcribed from proven R10.2 path_hash.cjs."""
    mask = (1 << 64) - 1
    p1, p2, p3, p4, p5 = (0x9e3779b185ebca87, 0xc2b2ae3d27d4eb4f,
                          0x165667b19e3779f9, 0x85ebca77c2b2ae63, 0x27d4eb2f165667c5)
    def rot(x, n):
        x &= mask
        return ((x << n) | (x >> (64-n))) & mask
    def rnd(x, y):
        return rot(x + y*p2, 31)*p1 & mask
    b, at = path.encode('utf-8'), 0
    if len(b) >= 32:
        v = [(p1+p2)&mask, p2, 0, (-p1)&mask]
        while at <= len(b)-32:
            for i in range(4):
                v[i] = rnd(v[i], int.from_bytes(b[at+8*i:at+8*i+8], 'little'))
            at += 32
        h = sum(rot(x, n) for x, n in zip(v, (1,7,12,18))) & mask
        for x in v:
            h = ((h ^ rnd(0,x))*p1+p4)&mask
    else:
        h = p5
    h = (h+len(b))&mask
    while at+8 <= len(b):
        h = (rot(h ^ rnd(0,int.from_bytes(b[at:at+8], 'little')),27)*p1+p4)&mask
        at += 8
    if at+4 <= len(b):
        h = (rot(h ^ (int.from_bytes(b[at:at+4], 'little')*p1&mask),23)*p2+p3)&mask
        at += 4
    while at < len(b):
        h = rot(h ^ (b[at]*p5&mask),11)*p1&mask
        at += 1
    h ^= h >> 33
    h = h*p2&mask
    h ^= h >> 29
    h = h*p3&mask
    return str(h ^ (h >> 32))


class Assets:
    def __init__(self):
        b, self.index_pin = pinned_source(INDEX)
        cursor = 0
        def take(fmt):
            nonlocal cursor
            size = struct.calcsize(fmt)
            if cursor+size > len(b):
                raise StructuralGap('index range')
            value = struct.unpack_from(fmt,b,cursor)
            cursor += size
            return value[0] if len(value)==1 else value
        magic, version, count, total = take('>4I')
        if (magic,version)!=(255,4):
            raise StructuralGap('pinned index version')
        self.entries, self.cache = {}, {}
        actual = 0
        for ordinal in range(count):
            bundle_hash = str(take('>Q'))
            words = take('>4I')
            shard = 'StarRail_Data/Persistent/DesignData/Windows/' + ''.join(f'{w:08x}' for w in words) + '.bytes'
            size, n = take('>Q'), take('>I')
            for j in range(n):
                position = cursor
                identity, length, offset = str(take('>Q')), take('>I'), take('>I')
                if offset+length > size or identity in self.entries:
                    raise StructuralGap('index duplicate identity/range')
                self.entries[identity] = {'hash':identity,'ordinal':j,'index_cursor':position,
                    'offset':offset,'length':length,'source_shard':shard,'bundle_ordinal':ordinal,
                    'bundle_hash':bundle_hash}
            length = take('>h')
            if length < 0 or cursor+length > len(b):
                raise StructuralGap('index bundle name range')
            cursor += length
            take('>B')
            actual += n
        if cursor != len(b) or actual != total:
            raise StructuralGap('index full consumption')

    def lookup(self, path):
        entry = self.entries.get(path_hash(path))
        return {**entry, 'path':path} if entry else None

    def source(self, entry):
        shard = entry['source_shard']
        if shard not in self.cache:
            self.cache[shard] = pinned_source(shard)
        return self.cache[shard]


class Reader(FrozenReader):
    """Additional leaf storage already proven in archived owner_decode.cjs."""
    def take(self,count):
        if self.cursor<0 or self.end>len(self.data):
            raise StructuralGap('bounded source range')
        return super().take(count)

    def read(self, reader, depth=0):
        reader = int(reader,16) if isinstance(reader,str) else reader
        start = self.cursor
        if reader == 0x1e1487c0:
            return {'reader':hex(reader),'kind':'uleb','value':self.u(),'start':start,'end':self.cursor}
        if reader == 0x1e152010:
            raw = self.u()
            return {'reader':hex(reader),'kind':'signed64_storage','raw':str(raw),
                    'value':str((raw>>1)^-(raw&1)),'start':start,'end':self.cursor}
        if reader == 0x1e151ae0:
            raw = self.take(4)
            return {'reader':hex(reader),'kind':'float32_storage','raw_hex':raw.hex(),
                    'bits':int.from_bytes(raw,'little'),'start':start,'end':self.cursor}
        if reader == 0x1e1524a0:
            components = [self.read(0x1e151ae0,depth+1) for _ in range(3)]
            return {'reader':hex(reader),'components':components,'start':start,'end':self.cursor}
        try:
            return super().read(reader,depth)
        except StructuralGap as exc:
            if not hasattr(exc,'reader_gap'):
                exc.reader_gap=hex(reader)
                exc.reader_gap_type=self.schemas.get(reader,{}).get('type')
            raise


def field(node, mask):
    return next((f for f in node.get('fields',[]) if int(f['mask']) == mask), None)


def scalar(node, mask):
    f = field(node,mask)
    return f['values'][0].get('value') if f and f['values'] else None


def children(node, mask):
    f = field(node,mask)
    return f['values'][0].get('children',[]) if f and f['values'] else []


def machinery(assets):
    schemas, inputs = {}, []
    for path in (R102+'reader_schemas_continuation.json', R11+'global_alias_reader_schemas.json',
                 R102+'owner_schema_1e365280.json',R102+'owner_schema_1e4a0200.json',
                 R102+'owner_schema_1ea206d0.json',R102+'skill_schema_final.json',
                 R11C+'progression_reader_schemas.json'):
        value = read(path)
        inputs.append({'path':path,'sha256':hashlib.sha256((REPO/path).read_bytes()).hexdigest()})
        for s in value if isinstance(value,list) else [value]:
            s = copy.deepcopy(s)
            if s.get('fields'):
                # JS serialized uint64 one-bit masks above 2**53 through Number.
                # Recover exact one-hot storage only when the IEEE-754 value is
                # identical; source reader test instructions prove one-bit masks.
                for f in s['fields']:
                    m=int(f['mask'])
                    if m and m & (m-1):
                        exact=1 << (m.bit_length()-1)
                        if float(exact)!=float(m):
                            exact <<= 1
                        if float(exact)!=float(m):
                            raise StructuralGap('non one-hot archived mask')
                        f['archived_rounded_mask']=f['mask']
                        f['mask']=exact
                s['fields'] = sorted({int(f['mask']):f for f in s['fields']}.values(),key=lambda f:int(f['mask']))
            schemas[int(s['rva'],16)] = s
    common = read(R11C+'mandatory_common_modifier_decode.json')['native_reader_schemas']
    for s in common.values() if isinstance(common,dict) else common:
        schemas[int(s['rva'],16)] = copy.deepcopy(s)
    # Exact patches from archived owner_decode.cjs, not inferred declaration order.
    for f in schemas[0x1e365280]['fields']:
        bit = int(f['mask']).bit_length()-1
        if bit in (1,2,6,7,28,38):
            f['operations']=[{'kind':'zigzag'},{'kind':'uleb'}]
        if bit in (15,16):
            f['operations']=[{'kind':'list','children':[0x1e1487c0]}]
        if bit==18:
            f['operations']=[{'kind':'list','children':[0xffff001]}]
        if bit>=39:
            f['operations']=[{'kind':'list','children':[0x1e151ae0]}]
    schemas[0x1eb95230]={'kind':'wrapper','type':'RPG.GameCore.TurnBasedModifierConfig','child':0x1eb95390}
    registries={int(t['rva'],16):{i:int(v['method']['rva'],16) for i,v in enumerate(t['mapping'])
        if v and v.get('method',{}).get('rva')} for t in read(R102+'selected_dispatch_bindings.json')}
    if (AUDIT/'local_reader_schemas.json').exists():
        for s in read(AUDIT.relative_to(REPO)/'local_reader_schemas.json'):
            s=copy.deepcopy(s)
            for f in s.get('fields',[]):
                m=int(f['mask'])
                if m and m&(m-1):
                    exact=1 << (m.bit_length()-1)
                    if float(exact)!=float(m):
                        exact <<= 1
                    if float(exact)!=float(m):
                        raise StructuralGap('local schema non one-hot mask')
                    f['mask']=exact
            schemas[int(s['rva'],16)]=s
        for t in read(AUDIT.relative_to(REPO)/'local_reader_dispatch.json'):
            registries[int(t['rva'],16)]={i:int(v['method']['rva'],16) for i,v in enumerate(t['mapping'])
                if v and v.get('method',{}).get('rva')}
    sources=read('data/control/generic_runtime_support_census_v3_20261007_001.json')['actual_corpus']
    sources += [{'path':R102+n} for n in ('avatar_decode.json','skill_decode.json','character_decode.json')]
    # Structural reader shapes are reusable only after re-reading their recorded byte spans.
    derived,nodes = reuse_recorded_readers(schemas,sources)
    # R10.2's string leaf omits its reader label. Its explicit kind and exact
    # spans still prove a nonempty homogeneous string list (same string reader).
    for _,_,n in nodes:
        r=int(n['reader'],16)
        if r not in derived or derived[r]['kind']!='bitmap':
            continue
        for f in n.get('fields',[]):
            if any(int(v['mask'])==int(f['mask']) for v in derived[r]['fields']):
                continue
            if len(f.get('values',[]))!=1:
                continue
            value=f['values'][0]
            items=value.get('children',[])
            if value.get('kind')=='list' and items and all(c.get('kind')=='string' for c in items):
                derived[r]['fields'].append({'mask':f['mask'],'operations':[{'kind':'list','children':[0x1e14a800]}]})
        derived[r]['fields'].sort(key=lambda f:int(f['mask']))
    for source in sources:
        for _,n in walk_dicts(read(source['path'])):
            if n.get('discriminator') is not None and n.get('child') and n.get('reader'):
                binding=n.get('binding',{}).get('method',{}).get('rva')
                if binding:
                    registries.setdefault(int(n['reader'],16),{})[n['discriminator']]=int(binding,16)
    validations=[]
    # Recorded owner spans live in the source indicated by their outer asset; all
    # combat archives in the inherited corpus use the selected shard.
    selected=assets.lookup('BakedConfig/Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.bytes')
    selected_data,_=assets.source(selected)
    seen=set()
    for source,pointer,n in nodes:
        r=int(n['reader'],16)
        if r not in derived or n.get('start') is None or n.get('end') is None:
            continue
        key=(source,r,n['start'],n['end'])
        if key in seen:
            continue
        seen.add(key)
        doc=read(source)
        data=selected_data
        if isinstance(doc,dict) and doc.get('path'):
            entry=assets.lookup(doc['path'])
            if entry:
                data,_=assets.source(entry)
        p=Reader(data,n['start'],n['end'],schemas,registries)
        try:
            value=p.read(r)
            if p.cursor!=n['end'] or value.get('type')!=n.get('type'):
                raise StructuralGap('archived span/type mismatch')
            status='PASS'
        except (StructuralGap,UnicodeError) as exc:
            status=str(exc)
        validations.append({'reader':hex(r),'source':source,'pointer':pointer,'status':status})
    # Missing dependencies remain gaps. A mismatched derived shape is never admitted.
    for r in {int(v['reader'],16) for v in validations if v['status']=='archived span/type mismatch'}:
        schemas.pop(r,None)
    write(AUDIT/'reader_validation.json',validations)
    write(AUDIT/'reader_schemas.json',list(schemas.values()))
    write(AUDIT/'reader_dispatch.json',{hex(k):{str(i):hex(v) for i,v in t.items()} for k,t in registries.items()})
    write(AUDIT/'reader_inputs.json',inputs)
    return schemas,registries


def directory(data, layout, config, schemas, registries):
    p=Reader(data,layout['offset'],layout['offset']+layout['length'],schemas,registries)
    if p.u()!=1:
        raise StructuralGap('directory root bitmap')
    count=p.z()
    if not 0<=count<=100000:
        raise StructuralGap('directory count')
    entries=[]
    for i in range(count):
        start=p.cursor
        flags=p.u()
        if flags & ~15:
            raise StructuralGap('directory unknown fields')
        name=p.string() if flags&1 else None
        kind=p.u() if flags&2 else 0
        relative=p.z() if flags&4 else 0
        deps=[]
        if flags&8:
            number=p.z()
            if not 0<=number<=100000:
                raise StructuralGap('directory dependency count')
            deps=[p.string() for _ in range(number)]
        entries.append({'ordinal':i,'directory_entry_start':start,'directory_entry_end':p.cursor,
            'name':name,'type':kind,'relative_offset':relative,'absolute':config['offset']+relative,
            'dependencies':deps})
    if p.cursor!=p.end:
        raise StructuralGap('directory incomplete framing')
    coordinates=[e['absolute'] for e in entries]
    if len(set(coordinates))!=len(coordinates) or any(not config['offset']<=s<config['offset']+config['length'] for s in coordinates):
        raise StructuralGap('directory duplicate/outside record start')
    ordered=sorted(coordinates)+[config['offset']+config['length']]
    ends=dict(zip(ordered,ordered[1:]))
    framed=[{**e,'record_end':ends[e['absolute']]} for e in entries]
    if (AUDIT/'parent_container_schema.json').exists():
        return frame_container(data,config,framed,schemas,registries)
    return framed


def encoded_u(value):
    result=bytearray()
    while value>=128:
        result.append((value&127)|128);value>>=7
    result.append(value)
    return bytes(result)


def frame_container(data,config,entries,schemas,registries):
    """Exact parent list/dictionary grammar, including keys and group counts.

    Body boundaries are computed BEFORE reading the body; no post-hoc acceptance
    of plausible leftovers. Every prefix is re-read and matched to the directory.
    """
    parent=Reader(data,config['offset'],config['offset']+config['length'],schemas,registries)
    bitmap=parent.u()
    if bitmap & ~63:
        raise StructuralGap('parent container unknown bitmap')
    groups=[(1,1,False),(2,0,True),(4,2,False),(8,3,True),(16,4,False),(32,6,True)]
    active=[]
    for bit,kind,dictionary in groups:
        values=sorted([e for e in entries if e['type']==kind],key=lambda e:e['absolute'])
        if values and not bitmap&bit:
            raise StructuralGap('directory type absent in parent bitmap')
        if bitmap&bit:
            active.append((bit,kind,dictionary,values))
    if sum(len(g[3]) for g in active)!=len(entries):
        raise StructuralGap('parent directory type partition')
    # A dictionary key is exactly length-prefixed UTF8 according to the recovered
    # string descriptor in native TurnBasedAbilityConfigList.FromBinary.
    for _,_,dictionary,values in active:
        for e in values:
            if dictionary:
                if not isinstance(e['name'],str):
                    raise StructuralGap('dictionary key identity absent')
                b=e['name'].encode('utf-8');prefix=encoded_u(len(b))+b
                e['prefix_start']=e['absolute']-len(prefix)
                if e['prefix_start']<config['offset'] or data[e['prefix_start']:e['absolute']]!=prefix:
                    raise StructuralGap('directory dictionary prefix identity mismatch')
                e['parent_key_span']=[e['prefix_start'],e['absolute']]
            else:
                e['prefix_start']=e['absolute']
    counts={}
    pending=[]
    for i,g in enumerate(active):
        bit,kind,dictionary,values=g
        if not values:
            pending.append(i);continue
        encoded=encoded_u(len(values)*2)
        count_start=values[0]['prefix_start']-len(encoded)
        if data[count_start:values[0]['prefix_start']]!=encoded:
            raise StructuralGap('parent group cardinality mismatch')
        counts[i]=count_start
        # Empty active groups immediately preceding this group consume one exact
        # zero-count byte each, as specified by the same list/dictionary framing.
        for j in reversed(pending):
            count_start-=1
            if data[count_start:count_start+1]!=b'\x00':
                raise StructuralGap('parent empty group cardinality mismatch')
            counts[j]=count_start
        pending=[]
    end=config['offset']+config['length']
    for j in reversed(pending):
        end-=1
        if data[end:end+1]!=b'\x00':
            raise StructuralGap('parent trailing empty group mismatch')
        counts[j]=end
    if active and counts[0]!=parent.cursor:
        raise StructuralGap('parent initial framing mismatch')
    for i,(_,_,_,values) in enumerate(active):
        following=counts.get(i+1,config['offset']+config['length'])
        for j,e in enumerate(values):
            e['record_end']=values[j+1]['prefix_start'] if j+1<len(values) else following
            if e['record_end']<=e['absolute']:
                raise StructuralGap('parent body range')
            e['parent_framing']='EXACT_LIST_DICTIONARY_GRAMMAR_0x1EB94850'
    return entries


def decode_entry(data, entry, schemas, registries):
    mapping={0:0x1eb95390,1:0x1eb94400}
    if (AUDIT/'root_type_dispatch.json').exists():
        mapping.update({r['kind']:int(r['reader']['rva'],16) for r in read(AUDIT.relative_to(REPO)/'root_type_dispatch.json') if r.get('reader')})
    reader=mapping.get(entry['type'])
    if reader is None:
        return {'status':'UNSUPPORTED_ROOT_TYPE','question':'unproven root type dispatch'}
    p=Reader(data,entry['absolute'],entry['record_end'],schemas,registries)
    try:
        graph=p.read(reader)
        if p.cursor!=p.end:
            return {'status':'FRAMING_GAP','cursor':p.cursor,'question':'incomplete root consumption'}
        return {'status':'ACCEPTED','reader':hex(reader),'consumption_status':'BOUNDED_FULL_CONSUMPTION',
                'graph':graph,'graph_hash':digest(graph)}
    except (StructuralGap,UnicodeError) as exc:
        text=str(exc)
        status='FRAMING_GAP' if 'range' in text or 'overflow' in text else 'STRUCTURAL_READER_GAP'
        return {'status':status,'cursor':p.cursor,'question':text,'reader':hex(reader),
                'reader_gap':getattr(exc,'reader_gap',None),'reader_gap_type':getattr(exc,'reader_gap_type',None)}


def source_identity(record):
    return (record['source_shard_sha256'],record['record_start'],record['record_end'])


def deduplicate(records):
    result={}
    for r in records:
        key=source_identity(r)
        if key in result and result[key]['graph_hash']!=r['graph_hash']:
            raise StructuralGap('conflicting graph for source coordinates')
        result.setdefault(key,r)
    return sorted(result.values(),key=source_identity)
