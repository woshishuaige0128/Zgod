from pathlib import Path
import zipfile,json,math,hashlib,copy
from lxml import etree as E
B=Path(__file__).resolve().parent
N={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def q(s):p,n=s.split(':');return '{'+N[p]+'}'+n
def sub(p,t,**kw):return E.SubElement(p,q(t),{k:str(v) for k,v in kw.items()})
def serialize(r):return E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile(B/'backup/current.pptx') as z:parts={n:z.read(n) for n in z.namelist()}
records=[];k=4*(math.sqrt(2)-1)/3
for page in [18,19]:
    root=E.fromstring(parts[f'ppt/slides/slide{page}.xml']);shapes={s.find('p:nvSpPr/p:cNvPr',N).get('name'):s for s in root.findall('.//p:sp',N)}
    heads={n:s for n,s in shapes.items() if n.endswith('_head')}
    assert len(heads)==(17 if page==18 else 41)
    for n,head in heads.items():
        name=n[:-5];s=shapes[name];geo=s.find('p:spPr/a:custGeom/a:pathLst/a:path',N);assert geo is not None
        # Existing arrow shafts retain position, scale, color and width.
        curved=len(geo.findall('a:lnTo',N))>1
        if curved:
            w=int(geo.get('w'));h=int(geo.get('h'));assert w>0 and h>0
            for child in list(geo):geo.remove(child)
            move=sub(geo,'a:moveTo');sub(move,'a:pt',x=0,y=0)
            c=sub(geo,'a:cubicBezTo')
            for x,y in [(0,k*h),((1-k)*w/2,h),(w/2,h)]:sub(c,'a:pt',x=round(x),y=round(y))
            c=sub(geo,'a:cubicBezTo')
            for x,y in [((1+k)*w/2,h),(w,h),(w,h*.7)]:sub(c,'a:pt',x=round(x),y=round(y))
            end=sub(geo,'a:lnTo');sub(end,'a:pt',x=w,y=0)
        ln=s.find('p:spPr/a:ln',N);assert ln is not None
        for ch in list(ln):
            if ch.tag in [q('a:headEnd'),q('a:tailEnd')]:ln.remove(ch)
        sub(ln,'a:headEnd',type='none',w='med',len='med')
        sub(ln,'a:tailEnd',type='triangle',w='med',len='sm' if curved else 'lg')
        head.getparent().remove(head)
        records.append({'slide':page,'name':name,'curve':curved,'native_end_arrow':'triangle','one_shape':True})
    parts[f'ppt/slides/slide{page}.xml']=serialize(root)
with zipfile.ZipFile(B/'draft/arrows_fixed.pptx','w',zipfile.ZIP_DEFLATED) as out:
    for n,b in parts.items():out.writestr(n,b)
# Editable SVG uses a marker attached to the same path; no loose polygon remains.
S='http://www.w3.org/2000/svg';sn={'s':S}
for fig in [3,4]:
    root=E.fromstring((B/'backup'/f'fig{fig}_generated_editable.svg').read_bytes())
    defs=E.Element('{'+S+'}defs');root.insert(2,defs)
    elems={s.get('id'):s for s in root.xpath('//*[@id]')}
    scene=json.loads((B.parent/'figure1_4_editable_20260911/build'/f'fig{fig}.json').read_text(encoding='utf-8'))
    obs={o['name']:o for o in scene['objects']}
    for rec in [r for r in records if r['slide']==fig+15]:
        name=rec['name'];path=elems[name];head=elems[name+'_head'];ob=obs[name]
        if rec['curve']:
            pts=ob['points'];x0=min(p[0] for p in pts);x1=max(p[0] for p in pts);y0=min(p[1] for p in pts);h=max(p[1] for p in pts)-y0;rx=(x1-x0)/2;cx=(x0+x1)/2
            path.set('d',f'M{x0},{y0} C{x0},{y0+k*h} {cx-k*rx},{y0+h} {cx},{y0+h} C{cx+k*rx},{y0+h} {x1},{y0+h} {x1},{y0+.7*h} L{x1},{y0}')
        ml='3' if rec['curve'] else '6'
        marker=E.SubElement(defs,'{'+S+'}marker',id=name+'_end_marker',viewBox=f'0 0 {ml} 3',refX=ml,refY='1.5',markerWidth=ml,markerHeight='3',orient='auto',markerUnits='strokeWidth',overflow='visible')
        E.SubElement(marker,'{'+S+'}path',d=f'M0,0 L{ml},1.5 L0,3 Z',fill=ob['color'],stroke='none')
        path.set('marker-end',f'url(#{name}_end_marker)');head.getparent().remove(head)
    (B/'draft'/f'fig{fig}_generated_editable.svg').write_bytes(serialize(root))
report={'pass':True,'arrows':len(records),'rotational_arrows':sum(r['curve'] for r in records),'translational_and_axis_arrows':sum(not r['curve'] for r in records),'objects_after':{'18':102,'19':253},'records':records}
(B/'patch_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='records'}))
