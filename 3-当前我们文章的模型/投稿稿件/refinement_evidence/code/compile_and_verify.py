from pathlib import Path
import subprocess,json,re,hashlib,shutil,csv
import fitz
from PIL import Image,ImageDraw
TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_refined_20260907'
EV=NEW/'refinement_evidence';checks=[]
def check(name,passed,**info):checks.append({'name':name,'passed':bool(passed),**info});assert passed,(name,info)
for n,args in enumerate([['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex','main'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex']],1):
 r=subprocess.run(args,cwd=NEW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(TMP/f'compile_{n}.log').write_bytes(r.stdout);check(f'compile command {n}',r.returncode==0)
log=(NEW/'main.log').read_text(errors='replace');check('no undefined references or compilation errors',not re.search(r'(?m)^!|(?:Reference|Citation).*undefined|There were undefined',log))
before=(EV/'baseline/main.tex').read_text('utf-8');after=(NEW/'main.tex').read_text('utf-8');ops=json.loads((EV/'manuscript_changes.json').read_text('utf-8'));replay=before
for c in ops:replay=replay.replace(c['old'],c['new'],1)
check('16 documented changes exactly reconstruct manuscript',replay==after and len(ops)==16)
check('42 negative spacing commands unchanged',len(re.findall(r'\\vspace\{-[^}]+\}',after))==42 and re.findall(r'\\vspace\{-[^}]+\}',after)==re.findall(r'\\vspace\{-[^}]+\}',before))
check('absolute value applied inside coordinate sum',r'\left|\frac{E^{\mathrm{red}}(d_{k})-E^{\mathrm{full}}(d_{k})}{E^{\mathrm{full}}(d_{k})}\right|'in after)
metric=json.loads((EV/'data/modal_share_deviation.json').read_text('utf-8'))
table=after.split(r'\label{tab:energy}')[1].split(r'\end{table}')[0]
for div in [1,2]:
 vals=[next(m['absolute_relative_deviation_sum'] for m in metric['model_totals'] if m['division']==div and m['method']==method) for method in ['Guyan','CB']]
 expected=f'{"I"*div}'+r' & \rev{'+f'{vals[0]:.4f}'+r'} & \rev{'+f'{vals[1]:.4f}'+'}'
 check(f'table5 division{div} computed values',expected in re.sub(r'\s+',' ',table))
for word in ['0.8914','0.0365','-0.0414','Signed relative','retain their signs','modal redistribution ratio']:check('no stale manuscript value or wording: '+word,word not in after)
layout=json.loads((EV/'validation/figure6_layout.json').read_text('utf-8'));oldlayout=json.loads((EV/'data/layout_figure_manifest.json').read_text('utf-8'))[0]
check('figure6 12 curves and frequencies unchanged',layout['curves']==oldlayout['data_series'])
for a in layout['placement_checks']:check('8pt frequency placement panel'+str(a['panel']),a['frequency_font_pt']==8 and a['inside_axes'] and not a['curve_collisions_at_2p5pt_padding'] and not a['heading_overlap'])
f15=json.loads((EV/'validation/figure15_values.json').read_text('utf-8'))
for m in metric['model_totals']:
 b=next(x for x in f15['right_bars'] if x['division']==m['division'] and x['method']==m['method']);check(f'figure15 and table5 {m["division"]}/{m["method"]}',abs(b['sum']-m['absolute_relative_deviation_sum'])<1e-14 and min(b['heights'])>=0)
doc=fitz.open(NEW/'main.pdf');texts=[p.get_text() for p in doc];check('no question-mark references',all('??'not in t for t in texts));mapping=[]
for number in range(1,16):
 found=[i+1 for i,t in enumerate(texts) if f'Figure {number}:'in t];check('unique figure '+str(number),len(found)==1);mapping.append({'number':number,'page':found[0]})
out=TMP/'pages';out.mkdir(exist_ok=True)
for i,p in enumerate(doc,1):p.get_pixmap(dpi=105).save(out/f'page_{i:02}.png')
for start in range(1,len(doc)+1,4):
 sheet=Image.new('RGB',(1400,2040),'#dbe1e8')
 for i in range(start,min(start+4,len(doc)+1)):
  im=Image.open(out/f'page_{i:02}.png').convert('RGB');im.thumbnail((690,980));x=(i-start)%2*700;y=(i-start)//2*1020
  sheet.paste(im,(x+(700-im.width)//2,y+30));ImageDraw.Draw(sheet).text((x+15,y+10),f'PAGE {i}',fill='black')
 sheet.save(out/f'contact_{start:02}_{min(start+3,len(doc)):02}.jpg',quality=90)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'status':'PASS','checks_passed':len(checks),'checks':checks,'pages':len(doc),'figure_mapping':mapping,'main_sha256':sha(NEW/'main.tex'),'pdf_sha256':sha(NEW/'main.pdf'),'warnings':[l for l in log.splitlines() if 'Overfull'in l or 'Underfull'in l]}
(EV/'validation/manuscript_compile.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copy2(__file__,EV/'code/compile_and_verify.py')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
