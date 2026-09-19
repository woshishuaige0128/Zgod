"""Expand SVG dash patterns on original polylines before GDI+ recording.

Input dash lengths are SVG user units. The original converter asked GDI+ to
expand custom dashes; this derivative cuts the CENTERLINE by arclength and
uses only ordinary solid GDI strokes for the resulting open subpaths.

This task's dashed paths are open polylines, with butt caps, round joins,
strictly positive even-length patterns, and zero offset. Reject other cases
rather than silently approximating them. Every original non-dashed draw and
every other attribute remains unchanged.
"""
from pathlib import Path
from lxml import etree as ET
import argparse, hashlib, json, math, re

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[2]/'figure_all_ppt_20260907'

def sha(data):return hashlib.sha256(data).hexdigest()

def parse_points(text):
    assert '|' not in text
    values=[]
    for row in text.split(';'):
        x,y,t=row.split(',');t=int(t)
        assert t in (0,1), ('Only open SVG polyline supported',t)
        values.append((float(x),float(y),t))
    assert values and values[0][2]==0
    assert sum(t==0 for _,_,t in values)==1
    return [(x,y) for x,y,_ in values]

def expected_on_length(total,pattern):
    cycle=sum(pattern)
    cycles=math.floor(total/cycle)
    length=cycles*sum(pattern[::2]);rem=total-cycles*cycle
    for i,n in enumerate(pattern):
        used=min(rem,n)
        if i%2==0:length+=used
        rem-=used
        if rem<=0:break
    return length

def split(points,pattern):
    assert len(pattern)%2==0 and all(v>0 for v in pattern)
    index=0;remaining=pattern[0];current=[];paths=[]
    full_length=0.;on_length=0.;gap_length=0.
    eps=1e-11
    def close_run():
        nonlocal current
        if len(current)>1:paths.append(current)
        current=[]
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy);full_length+=length
        if length<=eps:continue
        distance=0.
        while distance<length-eps:
            if remaining<=eps:
                if index%2==0:close_run()
                index=(index+1)%len(pattern);remaining=pattern[index]
            take=min(length-distance,remaining)
            start=(a[0]+dx*distance/length,a[1]+dy*distance/length)
            distance+=take
            end=(a[0]+dx*distance/length,a[1]+dy*distance/length)
            if index%2==0:
                if not current:current.append(start)
                elif math.dist(current[-1],start)>eps:current.append(start)
                current.append(end);on_length+=take
            else:gap_length+=take
            remaining-=take
    close_run()
    expected=expected_on_length(full_length,pattern)
    measured=sum(math.dist(a,b) for p in paths for a,b in zip(p,p[1:]))
    assert abs(on_length-expected)<1e-7,(on_length,expected)
    assert abs(on_length+gap_length-full_length)<1e-7
    assert abs(measured-on_length)<1e-7
    return paths,dict(total_centerline_arclength=full_length,
                      expected_on_arclength=expected,actual_on_arclength=measured,
                      on_arclength_error=abs(measured-expected),
                      gap_arclength=gap_length,subpaths=len(paths))

def encode(paths):
    return '|'.join(';'.join(f'{x:.12f},{y:.12f},{0 if i==0 else 1}'
                            for i,(x,y) in enumerate(p)) for p in paths)

def process(n):
    source=OLD/'vectors'/f'fig{n}_gdi.xml'
    data=source.read_bytes();root=ET.fromstring(data);modified=[]
    for i,e in enumerate(root):
        array=e.get('stroke-dasharray')
        if not array:continue
        assert e.get('fill','none')=='none'
        assert e.get('stroke-linecap')=='butt'
        assert e.get('stroke-linejoin')=='round'
        assert float(e.get('stroke-dashoffset','0'))==0
        path=e.find('path');old_path=path.text
        points=parse_points(old_path)
        pattern=[float(v) for v in re.split(r'[,\s]+',array)]
        paths,metrics=split(points,pattern)
        path.text=encode(paths)
        del e.attrib['stroke-dasharray']
        if 'stroke-dashoffset' in e.attrib:del e.attrib['stroke-dashoffset']
        modified.append(dict(draw_index=i,color=e.get('stroke'),width=e.get('stroke-width'),
                             dasharray=array,original_path_sha256=sha(old_path.encode()),
                             explicit_path_sha256=sha(path.text.encode()),
                             original_points=len(points),**metrics))
    target=HERE/'vectors'/f'fig{n}_explicit.xml';target.parent.mkdir(exist_ok=True)
    target.write_bytes(ET.tostring(root))
    original=ET.fromstring(data)
    for i,(a,b) in enumerate(zip(original,root)):
        if not a.get('stroke-dasharray'):assert ET.tostring(a)==ET.tostring(b)
    assert source.read_bytes()==data
    return dict(figure=n,source_xml=str(source),output_xml=str(target),
                source_sha256=sha(data),output_sha256=sha(target.read_bytes()),
                unchanged_non_dashed_draws=len(root)-len(modified),modified=modified)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--figures',nargs='+',type=int,default=[11]);args=parser.parse_args()
    code=(OLD/'VectorRecorder.cs').read_bytes()
    (HERE/'VectorRecorder.cs').write_bytes(code)
    result=[process(n) for n in args.figures]
    (HERE/'preparation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for r in result:print('figure',r['figure'],'dash paths',len(r['modified']),'explicit segments',sum(x['subpaths'] for x in r['modified']))
