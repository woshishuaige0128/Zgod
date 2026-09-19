from pathlib import Path
import json,zipfile,copy,sys
from lxml import etree as E
B=Path(__file__).resolve().parent
N={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def q(s):p,n=s.split(':');return '{'+N[p]+'}'+n
def sub(p,t,**kw):return E.SubElement(p,q(t),{k:str(v) for k,v in kw.items()})
with zipfile.ZipFile(B/'backup/current.pptx') as z:parts={n:z.read(n) for n in z.namelist()}
records=[]
for page in [18,19]:
 root=E.fromstring(parts[f'ppt/slides/slide{page}.xml'])
 shapes={s.find('p:nvSpPr/p:cNvPr',N).get('name'):s for s in root.findall('.//p:sp',N)}
 for name,number in list(shapes.items()):
  if not name.endswith('_number'):continue
  circle=shapes[name[:-7]+'_circle'];assert circle.find('p:spPr/a:prstGeom',N).get('prst')=='ellipse'
  text=''.join(number.findall('.//a:t',N)[0].itertext());assert text.isdigit()
  old=circle.find('p:txBody',N)
  if old is not None:circle.remove(old)
  body=copy.deepcopy(number.find('p:txBody',N));circle.append(body)
  bp=body.find('a:bodyPr',N)
  for k,v in {'wrap':'none','lIns':'0','rIns':'0','tIns':'0','bIns':'0','anchor':'ctr','anchorCtr':'1'}.items():bp.set(k,v)
  for p in body.findall('a:p',N):
   pp=p.find('a:pPr',N)
   if pp is None:pp=E.Element(q('a:pPr'));p.insert(0,pp)
   pp.set('algn','ctr');pp.set('marL','0');pp.set('marR','0');pp.set('indent','0')
   for tag in ['a:spcBef','a:spcAft']:
    old=pp.find(tag,N)
    if old is not None:pp.remove(old)
    sub(sub(pp,tag),'a:spcPts',val=0)
   # Use the same font metrics for visible digits and paragraph terminator.
   rp=p.find('a:r/a:rPr',N)
   for par,tag in [(pp,'a:defRPr'),(p,'a:endParaRPr')]:
    old=par.find(tag,N)
    if old is not None:par.remove(old)
    pr=copy.deepcopy(rp);pr.tag=q(tag);par.append(pr)
  circle.find('p:nvSpPr/p:cNvPr',N).set('name',name[:-7]+'_labeled_circle')
  number.getparent().remove(number)
  xf=circle.find('p:spPr/a:xfrm',N)
  records.append({'slide':page,'old_number_name':name,'old_circle_name':name[:-7]+'_circle','name':name[:-7]+'_labeled_circle','text':text,'xfrm':{E.QName(c).localname:dict(c.attrib) for c in xf}})
 parts[f'ppt/slides/slide{page}.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
assert len(records)==54,len(records)
with zipfile.ZipFile(B/'draft/centered.pptx','w',zipfile.ZIP_DEFLATED) as z:
 for n,b in parts.items():z.writestr(n,b)
(B/'patch_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('Centered native labeled circles',len(records))
