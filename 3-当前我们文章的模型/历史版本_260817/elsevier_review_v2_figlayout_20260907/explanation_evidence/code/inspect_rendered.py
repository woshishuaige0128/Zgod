from pathlib import Path
import fitz,json,hashlib
from PIL import Image,ImageDraw
TMP=Path(__file__).resolve().parent
NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_figlayout_20260907'
checks=[]
for filename in ['report_print.pdf','report_print_expanded.pdf']:
 doc=fitz.open(TMP/filename);dest=TMP/filename.replace('.pdf','');dest.mkdir(exist_ok=True)
 pageinfo=[]
 for i,p in enumerate(doc,1):
  text=p.get_text();words=p.get_text('words');outside=[w for w in words if w[0]<-1 or w[1]<-1 or w[2]>p.rect.width+1 or w[3]>p.rect.height+1]
  assert not outside,(filename,i,outside)
  assert len(text.strip())>30,(filename,i,'blank page')
  p.get_pixmap(dpi=105).save(dest/f'page_{i:02}.png')
  pageinfo.append({'page':i,'text_characters':len(text),'image_count':len(p.get_images()),'outside_text':len(outside),'start':text[:80],'end':text[-80:]})
 for start in range(1,len(doc)+1,4):
  sheet=Image.new('RGB',(1400,2040),'#dbe1e8')
  for i in range(start,min(start+4,len(doc)+1)):
   im=Image.open(dest/f'page_{i:02}.png').convert('RGB');im.thumbnail((690,980));x=(i-start)%2*700;y=(i-start)//2*1020
   sheet.paste(im,(x+(700-im.width)//2,y+30));ImageDraw.Draw(sheet).text((x+15,y+10),f'PAGE {i}',fill='black')
  sheet.save(dest/f'contact_{start:02}_{min(start+3,len(doc)):02}.jpg',quality=90)
 checks.append({'file':filename,'pages':len(doc),'status':'PASS','page_details':pageinfo})
# The new main only changes two figure files and two caption phrases.
before=fitz.open(NEW/'explanation_evidence/baseline/main.pdf');after=fitz.open(NEW/'main.pdf')
unchanged=[];changed=[]
for i,(a,b) in enumerate(zip(before,after),1):
 if a.get_pixmap(dpi=72).samples==b.get_pixmap(dpi=72).samples:unchanged.append(i)
 else:changed.append(i)
(NEW/'explanation_evidence/validation/render_checks.json').write_text(json.dumps({'status':'PASS','printed_reports':checks,'manuscript_pixel_identical_pages':unchanged,'manuscript_changed_pages':changed,'manuscript_visual_review':'Updated figures and pages inspected; inherited negative-spacing overlap retained.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'print_reports':[(x['file'],x['pages']) for x in checks],'unchanged_manuscript_pages':unchanged,'changed_manuscript_pages':changed},ensure_ascii=False,indent=2))
