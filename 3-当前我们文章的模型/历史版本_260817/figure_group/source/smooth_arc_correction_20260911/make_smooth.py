from pathlib import Path
import zipfile,json,math,sys
from lxml import etree as E
B=Path(__file__).resolve().parent
N={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
def q(s):
 p,n=s.split(':');return '{'+N[p]+'}'+n
def sub(p,t,**kw):return E.SubElement(p,q(t),{k:str(v) for k,v in kw.items()})
def ser(r):return E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
k=4*(math.sqrt(2)-1)/3
mode=sys.argv[1] if len(sys.argv)>1 else 'cubic'
with zipfile.ZipFile(B/'backup/current.pptx') as z:parts={n:z.read(n) for n in z.namelist()}
records=[]
for page in [18,19]:
 root=E.fromstring(parts[f'ppt/slides/slide{page}.xml'])
 for sp in root.findall('.//p:sp',N):
  geo=sp.find('p:spPr/a:custGeom/a:pathLst/a:path',N)
  tail=sp.find('p:spPr/a:ln/a:tailEnd',N)
  if geo is None or tail is None or tail.get('type')!='triangle' or len(geo.findall('a:cubicBezTo',N))!=2:continue
  w=int(geo.get('w'));h=int(geo.get('h'))
  for c in list(geo):geo.remove(c)
  mv=sub(geo,'a:moveTo');sub(mv,'a:pt',x=0,y=0)
  if mode=='arc':sub(geo,'a:arcTo',wR=round(w/2),hR=h,stAng=10800000,swAng=-10800000)
  else:
   for ps in [[(0,k*h),((1-k)*w/2,h),(w/2,h)],[((1+k)*w/2,h),(w,k*h),(w,0)]]:
    c=sub(geo,'a:cubicBezTo')
    for x,y in ps:sub(c,'a:pt',x=round(x),y=round(y))
  tail.set('len','sm');tail.set('w','sm')
  records.append({'slide':page,'name':sp.find('p:nvSpPr/p:cNvPr',N).get('name'),'path_w':w,'path_h':h})
 parts[f'ppt/slides/slide{page}.xml']=ser(root)
assert len(records)==42,len(records)
with zipfile.ZipFile(B/'draft'/f'{mode}.pptx','w',zipfile.ZIP_DEFLATED) as z:
 for n,b in parts.items():z.writestr(n,b)
if mode=='cubic':
 S='http://www.w3.org/2000/svg'
 for fig in [3,4]:
  root=E.fromstring((B/'backup'/f'fig{fig}_generated_editable.svg').read_bytes())
  obs={o['name']:o for o in json.loads((B.parent/'figure1_4_editable_20260911/build'/f'fig{fig}.json').read_text(encoding='utf-8'))['objects']}
  el={s.get('id'):s for s in root.xpath('//*[@id]')}
  for rec in [r for r in records if r['slide']==fig+15]:
   name=rec['name'];pts=obs[name]['points'];x0=min(p[0] for p in pts);x1=max(p[0] for p in pts);y0=min(p[1] for p in pts);h=max(p[1] for p in pts)-y0;rx=(x1-x0)/2;cx=(x0+x1)/2
   el[name].set('d',f'M{x0},{y0} C{x0},{y0+k*h} {cx-k*rx},{y0+h} {cx},{y0+h} C{cx+k*rx},{y0+h} {x1},{y0+k*h} {x1},{y0}')
   marker=el[name+'_end_marker'];marker.set('markerHeight','2');marker.set('viewBox','0 0 3 2');marker.set('refY','1')
   marker[0].set('d','M0,0 L3,1 L0,2 Z')
  (B/'draft'/f'fig{fig}_generated_editable.svg').write_bytes(ser(root))
 (B/'patch_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(mode,len(records))
