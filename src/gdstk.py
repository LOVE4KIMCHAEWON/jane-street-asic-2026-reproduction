"""Small, stdlib-only reader for the orthogonal GDS subset used by this puzzle.

It exposes only the gdstk API consumed by reference/tools/extract2.py.
No approximation is used for the two-point orthogonal paths in these layouts.
"""
import struct, math
from types import SimpleNamespace as Obj

def real8(raw):
    if not raw or raw == b'\0'*8: return 0.0
    return (-1 if raw[0] & 128 else 1) * (int.from_bytes(raw[1:], 'big') / 2**56) * 16**((raw[0]&127)-64)

class Path:
    def __init__(self, e):
        self.layers=[e['layer']]; self.datatypes=[e['datatype']]
        self.e=e
    def to_polygons(self):
        e=self.e; p=e['xy']; w=abs(e['width'])/2
        assert len(p)==2, 'Only two-point paths are present in the input GDS'
        (x0,y0),(x1,y1)=p
        assert x0==x1 or y0==y1, 'Expected orthogonal path'
        typ=e.get('pathtype',0)
        assert typ in (0,2,4), 'Unsupported path cap'
        a=b=0
        if typ==2: a=b=w
        elif typ==4: a=e.get('beginext',0); b=e.get('endext',0)
        if y0==y1:
            s=1 if x1>x0 else -1
            x0-=s*a; x1+=s*b
            xmin,xmax=min(x0,x1),max(x0,x1); ymin,ymax=y0-w,y0+w
        else:
            s=1 if y1>y0 else -1
            y0-=s*a; y1+=s*b
            xmin,xmax=x0-w,x0+w; ymin,ymax=min(y0,y1),max(y0,y1)
        return [Obj(layer=e['layer'], datatype=e['datatype'], points=[(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)])]

class Library:
    def __init__(self,cells): self.cells=cells
    def top_level(self):
        referenced={r.cell.name for c in self.cells for r in c.references}
        return [c for c in self.cells if c.name not in referenced]

def read_gds(filename):
    data=open(filename,'rb').read(); pos=0; names={}; cell=None; e=None; unit=.001
    starts={8:'polygon',9:'path',10:'ref',11:'arrayref',12:'text',21:'node',45:'box'}
    fields={13:'layer',14:'datatype',15:'width',16:'xy',18:'sname',19:'colrow',22:'texttype',23:'presentation',26:'strans',27:'mag',28:'angle',25:'string',33:'pathtype',48:'beginext',49:'endext'}
    pending=[]
    while pos<len(data):
        n,t,d=struct.unpack('>HBB',data[pos:pos+4]); raw=data[pos+4:pos+n]; pos+=n
        if d==6: v=raw.rstrip(b'\0').decode(errors='replace')
        elif d==2: v=struct.unpack('>'+str(len(raw)//2)+'h',raw)
        elif d==3: v=struct.unpack('>'+str(len(raw)//4)+'i',raw)
        elif d==1: v=struct.unpack('>'+str(len(raw)//2)+'H',raw)
        elif d==5: v=tuple(real8(raw[i:i+8]) for i in range(0,len(raw),8))
        else: v=raw
        if t==3:
            unit=v[0]
        elif t==6:
            cell=Obj(name=v, polygons=[], paths=[], labels=[], references=[]); names[v]=cell
        elif t==7: cell=None
        elif t in starts: e={'kind':starts[t]}
        elif t==17:
            kind=e['kind']
            if 'xy' in e: e['xy']=[(e['xy'][i]*unit,e['xy'][i+1]*unit) for i in range(0,len(e['xy']),2)]
            if kind=='polygon': cell.polygons.append(Obj(layer=e['layer'],datatype=e['datatype'],points=e['xy']))
            elif kind=='path':
                for f in ('width','beginext','endext'):
                    if f in e: e[f]*=unit
                cell.paths.append(Path(e))
            elif kind=='text': cell.labels.append(Obj(layer=e['layer'],texttype=e['texttype'],origin=e['xy'][0],text=e['string']))
            elif kind=='ref':
                r=Obj(origin=e['xy'][0], rotation=math.radians(e.get('angle',0)),x_reflection=bool(e.get('strans',0)&32768))
                cell.references.append(r); pending.append((r,e['sname']))
            elif kind=='arrayref': raise ValueError('Array references not supported')
            e=None
        elif e is not None and t in fields:
            key=fields[t]; e[key]=v[0] if isinstance(v,tuple) and len(v)==1 else v
    for r,n in pending: r.cell=names[n]
    return Library(list(names.values()))
