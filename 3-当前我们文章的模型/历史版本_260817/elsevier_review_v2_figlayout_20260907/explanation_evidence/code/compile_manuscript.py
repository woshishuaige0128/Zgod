from pathlib import Path
import subprocess,json,re,hashlib,shutil,difflib
import fitz

TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_figlayout_20260907'
for n,args in enumerate([['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex','main'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex']],1):
    r=subprocess.run(args,cwd=NEW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(TMP/f'compile_{n}.log').write_bytes(r.stdout);assert r.returncode==0,r.stdout[-3000:]
log=(NEW/'main.log').read_text(errors='replace');assert not re.search(r'(?m)^!|(?:Reference|Citation).*undefined|There were undefined',log)
before=(NEW/'explanation_evidence/baseline/main.tex').read_text('utf-8');after=(NEW/'main.tex').read_text('utf-8')
assert len(re.findall(r'\\vspace\{-[^}]+\}',after))==42 and re.findall(r'\\vspace\{-[^}]+\}',after)==re.findall(r'\\vspace\{-[^}]+\}',before)
changes=json.loads((NEW/'explanation_evidence/caption_changes.json').read_text('utf-8'));replay=before
for c in changes:replay=replay.replace(c['old'],c['new'],1)
assert replay==after,'Unexpected main.tex changes'
(NEW/'explanation_evidence/main_changes.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='previous_main.tex',tofile='main.tex')),encoding='utf-8')
doc=fitz.open(NEW/'main.pdf');texts=[p.get_text() for p in doc];assert all('??'not in t for t in texts)
mapping=[]
for number in range(1,16):
    found=[i+1 for i,t in enumerate(texts) if f'Figure {number}:'in t];assert len(found)==1,(number,found);mapping.append({'number':number,'page':found[0]})
out=TMP/'pages';out.mkdir(exist_ok=True)
for i,p in enumerate(doc,1):p.get_pixmap(dpi=105).save(out/f'page_{i:02}.png')
from PIL import Image,ImageDraw
for start in range(1,len(doc)+1,4):
    sheet=Image.new('RGB',(1400,2040),'#dbe1e8')
    for i in range(start,min(start+4,len(doc)+1)):
        im=Image.open(out/f'page_{i:02}.png').convert('RGB');im.thumbnail((690,980));x=(i-start)%2*700;y=(i-start)//2*1020
        sheet.paste(im,(x+(700-im.width)//2,y+30));ImageDraw.Draw(sheet).text((x+15,y+10),f'PAGE {i}',fill='black')
    sheet.save(out/f'contact_{start:02}_{min(start+3,len(doc)):02}.jpg',quality=92)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'status':'PASS','pages':len(doc),'figure_mapping':mapping,'caption_phrase_changes_only':2,'negative_skips_preserved':42,'main_sha256':sha(NEW/'main.tex'),'pdf_sha256':sha(NEW/'main.pdf'),'warnings':[l for l in log.splitlines() if 'Overfull'in l or 'Underfull'in l],'inherited_layout_limit':'原42条负间距保留，原有公式紧贴/重叠未在本轮改变。'}
(NEW/'explanation_evidence/validation/manuscript_compile.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(__file__,NEW/'explanation_evidence/code/compile_manuscript.py')
print(json.dumps(result,ensure_ascii=False,indent=2))
