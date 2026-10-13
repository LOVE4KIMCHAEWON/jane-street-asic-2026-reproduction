"""Export the actual GDS pixel logo and Morse annotation, using only stdlib.

Requires the bundled gdstk.py subset reader beside this script (or native gdstk).
Usage: python extract_easter_geometry.py --puzzle-dir /path/to/asic-puzzle --out /path/to/results
All coordinates in JSON evidence are integer nanometres from the source GDS.
"""
import argparse, collections, csv, hashlib, json, math, pathlib, struct, zlib
import gdstk

S=1000
MORSE=dict(zip(
    ['.-','-...','-.-.','-..','.','..-.','--.','....','..','.---','-.-','.-..','--','-.','---','.--.','--.-','.-.','...','-','..-','...-','.--','-..-','-.--','--..',
     '-----','.----','..---','...--','....-','.....','-....','--...','---..','----.'],
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))

def nm(v): return int(round(v*S))
def points(p): return [(nm(x),nm(y)) for x,y in p.points]
def box(pts):
    return [min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
def overlaps(a,b): return a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3]
def poly_items(cell):
    yield from cell.polygons
    for path in cell.paths: yield from path.to_polygons()
def transformed_box(p,ref):
    angle=ref.rotation or 0; co=round(math.cos(angle)); si=round(math.sin(angle))
    assert abs(math.cos(angle)-co)<1e-9 and abs(math.sin(angle)-si)<1e-9
    ox,oy=map(nm,ref.origin); out=[]
    for x,y in points(p):
        if ref.x_reflection: y=-y
        out.append((co*x-si*y+ox,si*x+co*y+oy))
    return box(out)
def write_json(path, data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def write_png(path, pixels, scale=8, margin=3):
    """Lossless RGB PNG with literal, nearest-neighbour source pixels."""
    h=len(pixels); w=len(pixels[0]); width=(w+margin*2)*scale; height=(h+margin*2)*scale
    raw=bytearray(); ink=b'\x10\x42\x6b'; paper=b'\xff\xff\xff'
    for yy in range(height):
        raw.append(0)
        r=yy//scale-margin
        for xx in range(width):
            c=xx//scale-margin
            raw.extend(ink if 0<=r<h and 0<=c<w and pixels[r][c] else paper)
    def chunk(tag,body):
        return struct.pack('>I',len(body))+tag+body+struct.pack('>I',zlib.crc32(tag+body)&0xffffffff)
    data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(raw),9))+chunk(b'IEND',b'')
    path.write_bytes(data)

def extract_logo(top,out,common):
    shapes=[]
    for i,p in enumerate(top.polygons):
        if p.layer!=69 or p.datatype!=20: continue
        pts=points(p); b=box(pts)
        if b[2]-b[0]==300 and b[3]-b[1]==300:
            assert all(x in (b[0],b[2]) and y in (b[1],b[3]) for x,y in pts)
            shapes.append((i,b))
    assert shapes, 'No 300nm-square met2 pixel annotation found'
    b=[min(s[1][0] for s in shapes),min(s[1][1] for s in shapes),max(s[1][2] for s in shapes),max(s[1][3] for s in shapes)]
    pitch=300; cols=(b[2]-b[0])//pitch; rows=(b[3]-b[1])//pitch
    assert (b[2]-b[0])%pitch==0 and (b[3]-b[1])%pitch==0
    matrix=[[0]*cols for _ in range(rows)]; pixels=[]
    for i,pb in shapes:
        col=(pb[0]-b[0])//pitch; row=(b[3]-pb[3])//pitch
        assert pb[0]==b[0]+col*pitch and pb[3]==b[3]-row*pitch
        assert not matrix[row][col], 'Duplicate source pixel'
        matrix[row][col]=1
        pixels.append({'top_polygon_index':i,'row_from_top':row,'column_from_left':col,'bbox_nm':pb})
    # A conservative bounding-box test proves no top-level wire or flattened
    # cell conductor/via touches any logo pixel, including boundary contact.
    candidates=[]; chosen={i for i,_ in shapes}
    for i,p in enumerate(top.polygons):
        if i in chosen: continue
        if (p.layer,p.datatype) not in ((69,20),(68,44),(69,44)): continue
        pb=box(points(p))
        if overlaps(pb,b): candidates.append(('top_polygon',i,p.layer,p.datatype,pb))
    for i,path in enumerate(top.paths):
        for p in path.to_polygons():
            if (p.layer,p.datatype) not in ((69,20),(68,44),(69,44)): continue
            pb=box(points(p))
            if overlaps(pb,b): candidates.append(('top_path',i,p.layer,p.datatype,pb))
    for i,ref in enumerate(top.references):
        for p in poly_items(ref.cell):
            if (p.layer,p.datatype) not in ((69,20),(68,44),(69,44)): continue
            pb=transformed_box(p,ref)
            if overlaps(pb,b): candidates.append((ref.cell.name,i,p.layer,p.datatype,pb))
    contacts=[{'geometry':item[:4],'bbox_nm':item[4],'pixel_polygon_indices':[i for i,pb in shapes if overlaps(pb,item[4])]} for item in candidates]
    contacts=[c for c in contacts if c['pixel_polygon_indices']]
    data=dict(common,kind='met2_pixel_logo',layer=69,datatype=20,pixel_count=len(shapes),
        pixel_size_nm=[pitch,pitch],pitch_nm=pitch,bbox_nm=b,rows=rows,columns=cols,
        matrix_row_order='top to bottom; GDS y decreases',matrix_column_order='left to right; GDS x increases',
        matrix=matrix,pixels=sorted(pixels,key=lambda p:(p['row_from_top'],p['column_from_left'])),
        conservative_isolation_check={'compared_layer_datatypes':[[69,20],[68,44],[69,44]],
            'other_geometry_bboxes_intersecting_logo_bbox':len(candidates),'geometry_touching_any_source_pixel':len(contacts),
            'contacts':contacts,'electrically_isolated_from_routing':not contacts})
    write_json(out/'logo_pixelmap.json',data)
    with (out/'logo_pixelmap.csv').open('w',newline='',encoding='utf-8') as f: csv.writer(f).writerows(matrix)
    with (out/'logo_source_pixels.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f); wr.writerow(['top_polygon_index','row_from_top','column_from_left','x_min_nm','y_min_nm','x_max_nm','y_max_nm'])
        for p in data['pixels']: wr.writerow([p['top_polygon_index'],p['row_from_top'],p['column_from_left']]+p['bbox_nm'])
    # Preserve original integer geometry. SVG's y axis is flipped into the GDS
    # convention through one explicit transform, rather than changing the map.
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="456" height="456" viewBox="0 0 %d %d">'%((b[2]-b[0]),(b[3]-b[1])),
        '<title>Met2 logo extracted literally from puzzle.gds: %d source pixels</title>'%len(shapes),
        '<rect width="100%" height="100%" fill="white"/>',
        '<g fill="#10426b" shape-rendering="crispEdges" transform="translate(%d %d) scale(1 -1)">'%(-b[0],b[3])]
    for _,pb in shapes: lines.append('<rect x="%d" y="%d" width="300" height="300"/>'%(pb[0],pb[1]))
    lines.extend(['</g>','</svg>']); (out/'logo_original_geometry.svg').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_png(out/'logo_original_geometry.png',matrix)
    return {k:data[k] for k in ('pixel_count','pixel_size_nm','pitch_nm','bbox_nm','rows','columns','conservative_isolation_check')}

def extract_morse(top,out,common):
    annotation={}
    for ref in top.references:
        ps=[p for p in ref.cell.polygons if (p.layer,p.datatype)==(200,0)]
        if len(ps)==1 and len(ref.cell.polygons)==1 and not ref.cell.paths and not ref.cell.references:
            annotation[ref.cell.name]=ps[0]
    assert len(annotation)==2, 'Expected the dot and dash annotation cells'
    marks=[]
    for i,ref in enumerate(top.references):
        if ref.cell.name not in annotation: continue
        pb=transformed_box(annotation[ref.cell.name],ref)
        marks.append({'top_reference_index':i,'cell':ref.cell.name,'origin_nm':[nm(v) for v in ref.origin],'bbox_nm':pb,'width_nm':pb[2]-pb[0]})
    marks.sort(key=lambda m:m['bbox_nm'][0]); unit=min(m['width_nm'] for m in marks)
    assert all(m['width_nm'] in (unit,3*unit) for m in marks)
    ys={m['bbox_nm'][1] for m in marks}; heights={m['bbox_nm'][3]-m['bbox_nm'][1] for m in marks}
    assert len(ys)==1 and len(heights)==1
    code=''; groups=[]; current=''; current_marks=[]; last=None
    for m in marks:
        if last is not None:
            gap=m['bbox_nm'][0]-last; assert gap%unit==0
            m['gap_before_nm']=gap; m['gap_before_units']=gap//unit
            assert gap//unit in (1,3,7)
            if gap//unit>=3:
                groups.append({'morse':current,'letter':MORSE[current],'mark_reference_indices':current_marks}); current=''; current_marks=[]
                code+=' / ' if gap//unit==7 else ' '
                if gap//unit==7: groups.append({'word_break':True})
        symbol='.' if m['width_nm']==unit else '-'; m['symbol']=symbol
        code+=symbol; current+=symbol; current_marks.append(m['top_reference_index']); last=m['bbox_nm'][2]
    groups.append({'morse':current,'letter':MORSE[current],'mark_reference_indices':current_marks})
    decoded=''.join(' ' if g.get('word_break') else g['letter'] for g in groups)
    b=[marks[0]['bbox_nm'][0],min(m['bbox_nm'][1] for m in marks),marks[-1]['bbox_nm'][2],max(m['bbox_nm'][3] for m in marks)]
    data=dict(common,kind='outside_die_morse',layer=200,datatype=0,bbox_nm=b,unit_nm=unit,
        dot_width_nm=unit,dash_width_nm=3*unit,mark_height_nm=next(iter(heights)),
        gaps_units={'intra_letter':1,'inter_letter':3,'inter_word':7},mark_count=len(marks),
        morse=code,decoded=decoded,letter_groups=groups,source_marks=marks)
    write_json(out/'morse_geometry.json',data)
    with (out/'morse_source_marks.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f); wr.writerow(['top_reference_index','cell','symbol','x_min_nm','y_min_nm','x_max_nm','y_max_nm','width_nm','gap_before_units'])
        for m in marks: wr.writerow([m['top_reference_index'],m['cell'],m['symbol']]+m['bbox_nm']+[m['width_nm'],m.get('gap_before_units','')])
    (out/'morse_decode.txt').write_text(code+'\n'+decoded+'\n',encoding='utf-8')
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="23" viewBox="%d %d %d %d">'%(b[0],b[1],b[2]-b[0],b[3]-b[1]),
        '<title>Literal GDS layer 200/0 Morse annotation: %s</title>'%decoded,
        '<rect x="%d" y="%d" width="%d" height="%d" fill="white"/>'%(b[0],b[1],b[2]-b[0],b[3]-b[1]),'<g fill="#10426b">']
    for m in marks:
        pb=m['bbox_nm']; lines.append('<rect x="%d" y="%d" width="%d" height="%d"/>'%(pb[0],pb[1],pb[2]-pb[0],pb[3]-pb[1]))
    lines.extend(['</g>','</svg>']); (out/'morse_original_geometry.svg').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Display companion retains the physical mark widths/gaps, adds the decoded
    # text separately beneath, and does not introduce or change GDS marks.
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="125" viewBox="0 0 1600 125">',
        '<title>GDS Morse evidence</title>','<rect width="1600" height="125" fill="white"/>',
        '<text x="10" y="24" font-family="sans-serif" font-size="19" fill="#10426b">Original annotation on GDS layer 200/0</text>',
        '<g fill="#10426b" transform="translate(10 39) scale(%f)">'%(1580/(b[2]-b[0]))]
    for m in marks:
        pb=m['bbox_nm']; lines.append('<rect x="%d" y="0" width="%d" height="%d"/>'%(pb[0]-b[0],pb[2]-pb[0],pb[3]-pb[1]))
    lines.extend(['</g>','<text x="10" y="94" font-family="monospace" font-size="21" fill="#10426b">%s</text>'%decoded,
        '<text x="10" y="117" font-family="sans-serif" font-size="14" fill="#555">Dot: %d nm; dash: %d nm; gaps: 1, 3, or 7 dot units; %d original marks.</text>'%(unit,3*unit,len(marks)),'</svg>'])
    (out/'morse_evidence.svg').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {k:data[k] for k in ('mark_count','bbox_nm','unit_nm','dot_width_nm','dash_width_nm','mark_height_nm','morse','decoded')}

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--puzzle-dir',type=pathlib.Path,required=True); ap.add_argument('--out',type=pathlib.Path,required=True); args=ap.parse_args()
    source=args.puzzle_dir/'puzzle.gds'; args.out.mkdir(parents=True,exist_ok=True)
    lib=gdstk.read_gds(str(source)); top=next(c for c in lib.cells if c.name=='puzzle')
    common={'source_file':'puzzle.gds','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'gds_top_cell':top.name,'coordinate_units':'nanometres'}
    summary=dict(common,logo=extract_logo(top,args.out,common),morse=extract_morse(top,args.out,common))
    write_json(args.out/'geometry_summary.json',summary); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
