from pathlib import Path
import json,re,hashlib,difflib,subprocess,shutil,csv
import fitz
ROOT=Path(__file__).resolve().parents[2];TMP=Path(__file__).resolve().parent
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907'
QA=NEW/'revision_evidence/validation';QA.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name,truth,details=''):
    checks.append({'check':name,'passed':bool(truth),'details':details})
    if not truth:raise AssertionError((name,details))
def compile_pdf(path,prefix):
    commands=[['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex','main'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex']]
    for i,args in enumerate(commands,1):
        r=subprocess.run(args,cwd=path,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (TMP/f'{prefix}_{i}.txt').write_bytes(r.stdout)
        check(f'{prefix}: {i} {args[0]}',r.returncode==0,r.stdout[-500:].decode('utf-8',errors='replace') if r.returncode else 'exit 0')

before=(NEW/'revision_evidence/baseline/main_before.tex').read_text(encoding='utf-8')
after=(NEW/'main.tex').read_text(encoding='utf-8')
ops=json.loads((NEW/'revision_evidence/change_operations.json').read_text(encoding='utf-8'))
mainops=[r for r in ops if r.get('file','main.tex')=='main.tex']
replayed=before
for op in mainops:
    check('forward operation '+op['id'],replayed.count(op['old'])==1,op['title'])
    replayed=replayed.replace(op['old'],op['new'],1)
check('all operations reconstruct final manuscript',replayed==after)
for op in reversed(mainops):
    check('reverse operation '+op['id'],replayed.count(op['new'])==1,op['title'])
    replayed=replayed.replace(op['new'],op['old'],1)
check('all operations recover original manuscript',replayed==before)
a=before.splitlines(True);b=after.splitlines(True);hunks=[]
for tag,i,j,x,y in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
    if tag!='equal':hunks.append(dict(id=len(hunks)+1,old_start=i+1,old_end=j,new_start=x+1,new_end=y,old=''.join(a[i:j]),new=''.join(b[x:y])))
(NEW/'revision_evidence/raw_hunks.json').write_text(json.dumps(hunks,ensure_ascii=False,indent=2),encoding='utf-8')
check('negative skip commands unchanged and active',re.findall(r'(?m)^\s*(\\vspace\{-[^}]+\})',before)==re.findall(r'(?m)^\s*(\\vspace\{-[^}]+\})',after) and after.count(r'\vspace{-3.5em}')==42,'42/42; content and order unchanged')
intro=lambda s:s[s.index(r'\section{Introduction}'):s.index(r'\section{Structural modeling')]
check('original Introduction preserved verbatim',intro(before)==intro(after))
check('no unexpected control characters',all(ord(c)>=32 or c in '\n\t' for c in after))
check('fifteen numbered figures',after.count(r'\begin{figure}')==15)
check('six additional figures',after.count(r'\begin{figure}')-before.count(r'\begin{figure}')==6)

data=json.loads((NEW/'revision_evidence/data/table345_verified_values.json').read_text(encoding='utf-8'))
blocks=re.findall(r'\\begin\{table\}.*?\\end\{table\}',after,re.S)
check('five tables retained',len(blocks)==5)
actual=[]
for index,block in enumerate(blocks[2:],3):
    cleaned=re.sub(r'\\rev\{([^{}]*)\}',r'\1',block)
    for line in cleaned.splitlines():
        if index==3 and re.match(r'\s*(?:I|II)\s*&\s*[12]\s*&',line):values=line.split('&')[2:]
        elif index==4 and re.match(r'\s*(?:El Centro|Chirp,)',line):values=line.split('&')[1:]
        elif index==5 and re.match(r'\s*(?:I|II)\s*&',line):values=line.split('&')[1:]
        else:continue
        actual.extend(v.strip().rstrip('\\').strip().replace('$','') for v in values)
check('44 displayed table values',len(actual)==44)
for value,row in zip(actual,data['rows']):check('table cell '+str(row['id']),value==row['rounded_value'],value)
check('30 corrected table cells explicitly red',sum(block.count(r'\rev{') for block in blocks[2:])==30)
check('two modulus cells explicitly red',blocks[0].count(r'\rev{206}')==2)
check('obsolete maximum values absent from prose',all(v not in after for v in ['0.834','0.06\\%','24.575','19.059','0.3065','0.1879','0.3927','0.2021']))
check('six new figure metrics crosschecked in MATLAB',json.loads((NEW/'revision_evidence/data/new_metrics_matlab_validation.json').read_text())['status']=='PASS')

figures=[];oldfigs=[]
for s,target in [(before,oldfigs),(after,figures)]:
    for n,m in enumerate(re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',s,re.S),1):
        block=m.group();label=re.search(r'\\label\{([^}]+)\}',block).group(1)
        filenames=re.findall(r'\\includegraphics(?:\[[^\]]+\])?\{([^}]+)\}',block)
        target.append({'number':n,'label':label,'files':filenames,'source_line':s[:m.start()].count('\n')+1,'block':block})
oldlookup={f['label']:f for f in oldfigs}
for f in figures:
    f['old_number']=oldlookup.get(f['label'],{}).get('number');f['old_files']=oldlookup.get(f['label'],{}).get('files',[])
    for name in f['files']:
        p=NEW/'submit_figure'/name;check('figure file exists '+name,p.exists())
        d=fitz.open(p);check('vector figure '+name,all(not page.get_images() for page in d))
        check('no Type 3 font '+name,all(font[2]!='Type3' for page in d for font in page.get_fonts()))
(NEW/'revision_evidence/figure_mapping.json').write_text(json.dumps(figures,ensure_ascii=False,indent=2),encoding='utf-8')

compile_pdf(NEW,'final_production')
log=(NEW/'main.log').read_text(errors='replace')
check('no TeX errors or undefined references/citations',not re.search(r'(?m)^!|(?:Reference|Citation).*undefined|There were undefined',log))
fresh=TMP/'independent_manuscript_copy'
check('independent build folder initially absent',not fresh.exists())
fresh.mkdir();(fresh/'submit_figure').mkdir()
for p in NEW.iterdir():
    if p.is_file() and p.suffix in ['.tex','.bib','.bst','.cls','.sty','.jpeg']:shutil.copy2(p,fresh/p.name)
for f in figures:
    for name in f['files']:shutil.copy2(NEW/'submit_figure'/name,fresh/'submit_figure'/name)
compile_pdf(fresh,'independent_copy')
paper=fitz.open(NEW/'main.pdf');independent=fitz.open(fresh/'main.pdf')
papertext=[p.get_text() for p in paper]
check('independent manuscript page content identical',papertext==[p.get_text() for p in independent])
check('no unresolved question marks in PDF',all('??' not in t for t in papertext))
check('correct total page count in every footer',all(f'of {len(paper)}' in t[-150:] for t in papertext))
check('no malformed caption reference',all('ef{tab' not in t for t in papertext))
outside=[]
for i,p in enumerate(paper,1):
    for block in p.get_text('dict')['blocks']:
        if 'lines' not in block:continue
        for line in block['lines']:
            for span in line['spans']:
                box=span['bbox']
                if span['text'].strip() and (box[0]<-1 or box[1]<-1 or box[2]>p.rect.width+1 or box[3]>p.rect.height+1):outside.append([i,span['text'],list(box)])
check('no text outside page media boxes',not outside,outside)
for f in figures:
    matches=[i+1 for i,t in enumerate(papertext) if f'Figure {f["number"]}:' in t]
    check('one caption for figure '+str(f['number']),len(matches)==1,matches);f['page']=matches[0]
(NEW/'revision_evidence/figure_mapping.json').write_text(json.dumps(figures,ensure_ascii=False,indent=2),encoding='utf-8')
protected=json.loads((TMP/'protected_sources.json').read_text(encoding='utf-8'))
for name,value in protected.items():check('protected source '+Path(name).name,Path(name).exists() and sha(Path(name))==value,name)
words=lambda s:len(re.findall(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)*\b",re.sub(r'(?m)%.*$','',s)))
summary={'technical_checks':'PASS','checks_passed':len(checks),'manuscript_pages':len(paper),'numbered_figures':15,'added_figures':6,'main_source_diff_hunks':len(hunks),'documented_operations':len(ops),'changed_table345_cells':30,'changed_modulus_cells':2,'protected_files':len(protected),'original_word_tokens':words(before),'new_word_tokens':words(after),'original_negative_skips_preserved':42,'independent_compile':'PASS','known_visual_limitations':['原有负行距导致部分公式下方文字贴近或相叠，原稿PDF中也存在；按用户明确要求保留42处负行距，不宣称已消除该排版问题。'],'inherited_compile_warnings':[line for line in log.splitlines() if 'Overfull' in line or 'Underfull' in line],'scientific_items_still_open':['双侧部分界面装配的真实计算闭合及两侧中层位移差','历史稳定域对应的完整闭环矩阵、实际LQR增益及边界内外时程验证'],'main_sha256':sha(NEW/'main.tex'),'pdf_sha256':sha(NEW/'main.pdf')}
(QA/'technical_checks.json').write_text(json.dumps({'summary':summary,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
(NEW/'revision_evidence/validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['main.log','main.aux','main.blg']:
    shutil.copy2(NEW/name,QA/name)
print(json.dumps(summary,ensure_ascii=False,indent=2))
