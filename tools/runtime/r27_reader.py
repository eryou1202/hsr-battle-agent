"""Opt-in pinned R27 reader overlay; no frozen schemas or IR are rewritten."""
from r14_corpus import Reader as BaseReader, StructuralGap
from r23_discovery import machinery as inherited_machinery
from r27_checks import AUDIT, read

class Reader(BaseReader):
    def read(self, reader, depth=0):
        reader=int(reader,16) if isinstance(reader,str) else reader
        if reader==0x1e6d6bf0:
            # JsonEnum.ParseFromBinary reads exactly two uint32 ULEBs, zigzags
            # them, then asks a lazily loaded source provider for the value.
            # Preserve the keys; never substitute an enum or pretend lookup ran.
            start=self.cursor;raw=[self.u(),self.u()]
            if any(v>0xffffffff for v in raw):raise StructuralGap('JsonEnum uint32 storage bound')
            return dict(type='RPG.GameCore.JsonEnum',reader='0x1E6D6BF0',kind='external_enum_reference',
                start=start,end=self.cursor,raw_keys=raw,serialized_lookup_keys=[(v>>1)^-(v&1) for v in raw],
                source_provider='native lazy cache +0xC580; ParseFromBinary -> 0x1E6D6E90',
                resolution='SOURCE_PROVIDER_UNRESOLVED',native_value=None)
        return super().read(reader,depth)

    def operation(self, operation, depth):
        if operation['kind']=='enum_list':
            start=self.cursor
            count=self.z()
            if not 0<=count<=100000:
                raise StructuralGap('bounded enum list count')
            children=[]
            for _ in range(count):
                at=self.cursor
                value=super().operation(operation['element'],depth)
                children.append({**value,'start':at,'end':self.cursor})
            return dict(kind='list',count=count,start=start,end=self.cursor,children=children,
                        provenance='R27 exact generic enum descriptor and 0x17B6B560 count/indirect element loop')
        return super().operation(operation,depth)

def machinery():
    schemas,dispatch=inherited_machinery()
    for schema in read(AUDIT/'reader_schemas.json'):
        schemas[int(schema['rva'],16)]=schema
    if (AUDIT/'reader_dispatch.json').exists():
        for r,mapping in read(AUDIT/'reader_dispatch.json').items():
            dispatch[int(r,16)]={int(k):int(v) for k,v in mapping.items()}
    return schemas,dispatch
