from pathlib import Path
import json,zipfile,copy,math
from lxml import etree as E
B=Path(__file__).resolve().parents[1]
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def q(t):p,n=t.split(':');return '{'+NS[p]+'}'+n
def sub(parent,tag,**kw):return E.SubElement(parent,q(tag),{k:str(v) for k,v in kw.items()})
scenes=json.loads((B/'build/all_scenes.json').read_text(encoding='utf-8'))
z=zipfile.ZipFile(B/'draft/native_raw.pptx');parts={n:z.read(n) for n in z.namelist()}; z.close()
for idx,scene in enumerate(scenes,1):
    spec={o['name']:o for o in scene['objects']}; scale=scene['transform']['scale']
    root=E.fromstring(parts[f'ppt/slides/slide{idx}.xml'])
    for sp in root.findall('.//p:sp',NS):
        name=sp.find('p:nvSpPr/p:cNvPr',NS).get('name'); ob=spec[name]
        if ob['kind']!='text':continue
        body=sp.find('p:txBody',NS)
        if body is not None:sp.remove(body)
        body=sub(sp,'p:txBody'); bp=sub(body,'a:bodyPr',wrap='none',lIns=0,rIns=0,tIns=0,bIns=0,anchor='t',rtlCol=0)
        sub(bp,'a:noAutofit');sub(body,'a:lstStyle');p=sub(body,'a:p');pp=sub(p,'a:pPr',algn={'left':'l','center':'ctr','right':'r'}[ob['align']])
        ls=sub(pp,'a:lnSpc');sub(ls,'a:spcPct',val=100000)
        for r in ob['runs']:
            # Office/WPS applies its native 65% sub/superscript reduction.
            # Keep the parent run size for ordinary indices; avoid reducing twice.
            run_scale=r.get('scale',1)/.72 if r.get('baseline',0) else r.get('scale',1)
            run=sub(p,'a:r');rp=sub(run,'a:rPr',lang='en-US',sz=round(ob['size']*scale*run_scale*75),b=int(r.get('bold',ob['bold'])),i=int(r.get('italic',ob['italic'])),baseline=round(r.get('baseline',0)*1000),dirty=0)
            sf=sub(rp,'a:solidFill');sub(sf,'a:srgbClr',val=r.get('color',ob['color']).lstrip('#'))
            for f in ['a:latin','a:ea','a:cs']:sub(rp,f,typeface='Times New Roman')
            t=sub(run,'a:t');t.text=r['text'];t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        sub(p,'a:endParaRPr',lang='en-US',sz=round(ob['size']*scale*75))
    tree=root.find('p:cSld/p:spTree',NS)
    children=[o for o in tree if o.tag not in [q('p:nvGrpSpPr'),q('p:grpSpPr')]]
    grp=sub(tree,'p:grpSp');nv=sub(grp,'p:nvGrpSpPr');sub(nv,'p:cNvPr',id=10000+idx,name=f'Generated Figure {idx} - editable objects');sub(nv,'p:cNvGrpSpPr');sub(nv,'p:nvPr')
    gp=sub(grp,'p:grpSpPr');xf=sub(gp,'a:xfrm')
    sub(xf,'a:off',x=0,y=0);sub(xf,'a:ext',cx=9144000,cy=6858000);sub(xf,'a:chOff',x=0,y=0);sub(xf,'a:chExt',cx=9144000,cy=6858000)
    for child in children:tree.remove(child);grp.append(child)
    parts[f'ppt/slides/slide{idx}.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    # SVG: text remains live and all paths remain individually editable.
    S='http://www.w3.org/2000/svg';svg=E.Element('{'+S+'}svg',nsmap={None:S},width=str(scene['width']),height=str(scene['height']),viewBox=f"0 0 {scene['width']} {scene['height']}")
    E.SubElement(svg,'title').text=f'Editable generated Figure {idx}'
    E.SubElement(svg,'desc').text='Native vector reconstruction of the user-selected generated reference. Font: Times New Roman. Editable text and grouped vector geometry.'
    E.SubElement(svg,'rect',width='100%',height='100%',fill='white')
    group=E.SubElement(svg,'g',id=f'fig{idx}',**{'font-family':'Times New Roman'})
    for ob in scene['objects']:
        color=ob.get('color','#111111');lw=ob.get('lineWidth',0)
        common={'id':ob['name'],'fill':ob.get('fill','none'),'stroke':color if lw else 'none','stroke-width':str(lw),'stroke-linejoin':'round','stroke-linecap':'round'}
        if ob['kind']=='path':
            d=' '.join(('M' if i==0 else 'L')+f'{p[0]:.4f},{p[1]:.4f}' for i,p in enumerate(ob['points']))+(' Z' if ob['closed'] else '')
            E.SubElement(group,'path',d=d,**common)
        elif ob['kind']=='rect':
            E.SubElement(group,'rect',x=str(ob['x']),y=str(ob['y']),width=str(ob['w']),height=str(ob['h']),rx=str(ob.get('radius',0)),**common)
        elif ob['kind']=='ellipse':
            E.SubElement(group,'ellipse',cx=str(ob['x']+ob['w']/2),cy=str(ob['y']+ob['h']/2),rx=str(ob['w']/2),ry=str(ob['h']/2),**common)
        else:
            anchor={'left':'start','center':'middle','right':'end'}[ob['align']];x=ob['x']+({'left':0,'center':.5,'right':1}[ob['align']])*ob['w']
            text=E.SubElement(group,'text',id=ob['name'],x=str(x),y=str(ob['y']+ob['size']*.90),fill=color,**{'font-size':str(ob['size']),'text-anchor':anchor,'font-weight':'bold' if ob['bold'] else 'normal','font-style':'italic' if ob['italic'] else 'normal'})
            text.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
            for r in ob['runs']:
                svg_scale=r.get('scale',1)*.65/.72 if r.get('baseline',0) else r.get('scale',1)
                a={'font-size':str(ob['size']*svg_scale),'font-weight':'bold' if r.get('bold',ob['bold']) else 'normal','font-style':'italic' if r.get('italic',ob['italic']) else 'normal','baseline-shift':f"{r.get('baseline',0)}%",'fill':r.get('color',color)}
                E.SubElement(text,'tspan',**a).text=r['text']
    # XML indentation becomes visible spaces inside live SVG text.
    (B/'draft'/f'fig{idx}_generated_editable.svg').write_bytes(E.tostring(svg,xml_declaration=True,encoding='UTF-8',pretty_print=False))
with zipfile.ZipFile(B/'draft/native_four.pptx','w',zipfile.ZIP_DEFLATED) as out:
    for n,b in parts.items():out.writestr(n,b)
print('Native four-slide PPTX grouped; four editable SVG files written')
