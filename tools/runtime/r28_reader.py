"""Bounded same-build provider dictionaries on the existing R27 reader.

0x1E6D7C30 -> 0x17B6F900: JsonEnumCategory / JsonEnumConfig.
0x1E6D78C0 -> 0x17B70BC0: string / int32.
Delegate descriptors and loop instructions are retained in the R28 audit.
"""
from r27_reader import Reader as BaseReader
from r13_frozen_reader import StructuralGap


def encode_provider(graph):
    def u(v):
        data=bytearray()
        while v>=128:data.append((v&127)|128);v>>=7
        data.append(v)
        return bytes(data)
    def z(v):return u((v<<1) if v>=0 else ((-v<<1)-1))
    result=u(graph['bitmap'])
    if graph['bitmap']&1:
        children=graph['fields'][0]['values'][0]['children']
        result+=z(len(children)//2)
        for i in range(0,len(children),2):
            key,value=children[i],children[i+1]
            if graph['type']=='RPG.GameCore.JsonEnumDefineConfig':
                result+=z(key['value'])+encode_provider(value)
            else:
                raw=key['value'].encode('utf8')
                result+=u(len(raw))+raw+z(value['value'])
    return result


class Reader(BaseReader):
    def read(self, reader, depth=0):
        r=int(reader,16) if isinstance(reader,str) else reader
        if r not in (0x1e6d7c30,0x1e6d78c0):
            return super().read(reader,depth)
        if depth>64: raise StructuralGap('provider depth bound')
        start=self.cursor
        bitmap=self.u()
        if bitmap & ~1: raise StructuralGap('unknown provider bitmap')
        fields=[]
        if bitmap & 1:
            at=self.cursor
            count=self.z()
            if not 0<=count<=100000: raise StructuralGap('provider dictionary count')
            children=[];seen=set()
            for _ in range(count):
                kstart=self.cursor
                key=self.z() if r==0x1e6d7c30 else self.string()
                if key in seen: raise StructuralGap('duplicate provider dictionary key')
                seen.add(key)
                children.append(dict(kind='int' if r==0x1e6d7c30 else 'string',value=key,start=kstart,end=self.cursor))
                vstart=self.cursor
                value=self.read(0x1e6d78c0,depth+1) if r==0x1e6d7c30 else dict(kind='int',value=self.z(),start=vstart,end=self.cursor)
                children.append(value)
            fields.append(dict(mask=1,start=at,end=self.cursor,values=[dict(kind='dict',count=count,start=at,end=self.cursor,children=children)]))
        return dict(reader=hex(r),type='RPG.GameCore.JsonEnumDefineConfig' if r==0x1e6d7c30 else 'RPG.GameCore.JsonEnumConfig',
                    bitmap=bitmap,fields=fields,start=start,end=self.cursor)
