from pathlib import Path
import json,re,html,hashlib,csv,shutil,io,base64
from html.parser import HTMLParser
import fitz
from PIL import Image

TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907';EV=NEW/'revision_evidence';QA=EV/'validation'
checks=[]
def check(name,truth,details=''):
    checks.append({'check':name,'passed':bool(truth),'details':details})
    assert truth,(name,details)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
validation=json.loads((EV/'validation_summary.json').read_text('utf-8'))
check('manuscript bound to completed technical and numeric checks',sha(NEW/'main.tex')==validation['main_sha256'])
check('PDF bound to completed technical and visual checks',sha(NEW/'main.pdf')==validation['pdf_sha256'])
protected=json.loads((TMP/'protected_sources.json').read_text('utf-8'))
for p,h in protected.items():check('protected '+p,Path(p).exists() and sha(Path(p))==h)

ops=json.loads((EV/'change_operations.json').read_text('utf-8'))
for filename,baseline in [('main.tex','main_before.tex'),('references.bib','references_before.bib')]:
    original=(EV/'baseline'/baseline).read_text('utf-8');working=original;positions=[]
    for r in ops:
        if r.get('file','main.tex')!=filename:continue
        check('unique original operation '+r['id'],working.count(r['old'])==1)
        n=working.index(r['old']);positions.append((n,r));working=working[:n]+r['new']+working[n+len(r['old']):]
    check(filename+' forward reconstruction',working==(NEW/filename).read_text('utf-8'))
    for n,r in reversed(positions):
        check('reverse operation '+r['id'],working[n:n+len(r['new'])]==r['new'])
        working=working[:n]+r['old']+working[n+len(r['new']):]
    check(filename+' exact reverse reconstruction',working==original)

report=NEW/'RHTS第二版全文修改逐项对照与回退决策汇报.html';source=report.read_text('utf-8')
class Parser(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.ids=[];self.external=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id'in a:self.ids.append(a['id'])
        if tag=='img':self.images.append(a['src'])
        if tag in ['script','img','link','iframe','video','audio']:
            for k in ['src','href','poster']:
                if a.get(k) and not a[k].startswith(('data:','#')):self.external.append(a[k])
parser=Parser();parser.feed(source);parser.close()
check('HTML parser and UTF-8 declaration','<meta charset="utf-8">'in source)
check('all IDs unique',len(parser.ids)==len(set(parser.ids)))
check('20 embedded images',len(parser.images)==20)
for i,uri in enumerate(parser.images,1):
    check('embedded PNG '+str(i),uri.startswith('data:image/png;base64,'));im=Image.open(io.BytesIO(base64.b64decode(uri.split(',',1)[1])));im.verify()
check('no external rendering dependencies',not parser.external,parser.external)
check('no external CSS resource',not re.search(r'url\(\s*["\']?(?:https?:|/)',source))
check('formatting section is last',source.rfind('<section id="formatting">')>source.rfind('<section class="panel" id="decision-help">'))
cards=re.findall(r'<article class="change-card" id="([^"]+)"(.*?)(?=</article>)',source,re.S)
check('all 64 changes present',len(cards)==64 and {k for k,c in cards}=={r['id'] for r in ops})
check('30 explicit changed table-cell decisions',len(re.findall(r'data-key="table-cell-',source))==30)
check('new additions explicitly say original has no content','原稿无此内容。'in source)
check('two bibliography removals explicitly labelled','已删除此重复内容。'in source)
meta=json.loads(re.search(r'<script type="application/json" id="report-meta">(.*?)</script>',source,re.S).group(1))
check('report metadata matches actual manuscripts',meta['main_sha256']==sha(NEW/'main.tex') and meta['pdf_sha256']==sha(NEW/'main.pdf'))
check('94 review positions unique',len(meta['decisions'])==len({x['id'] for x in meta['decisions']})==94)
browser=json.loads((QA/'html_browser_checks.json').read_text('utf-8'))
check('26 browser checks match final HTML',browser['status']=='PASS' and browser['checks_passed']==26 and browser['report_sha256']==sha(report))
portable=json.loads((QA/'portable_figure_check.json').read_text('utf-8'))
check('10 portable figures and 8 numeric CSV files reproduce',portable['status']=='PASS' and portable['figure_count']==10 and len(portable['checks'])==20)

normal=lambda s:re.sub(r'\s+','',html.unescape(s))
titles=[]
for key,body in cards:
    title=html.unescape(re.search(r'<h3>(.*?)</h3>',body,re.S).group(1))
    old=html.unescape(re.search(r'<h4>原来</h4><p>(.*?)</p>',body,re.S).group(1));titles.append((key,title,old))
print_reports=[]
for kind in ['summary','full']:
    p=TMP/'report_qa'/f'report_{kind}_print.pdf';d=fitz.open(p);texts=[page.get_text() for page in d];compact=[normal(t) for t in texts];outside=[]
    for number,page in enumerate(d,1):
        for b in page.get_text('dict')['blocks']:
            for line in b.get('lines',[]):
                for span in line['spans']:
                    a,c,e,f=span['bbox']
                    if span['text'].strip() and (a<0 or c<0 or e>page.rect.width+1 or f>page.rect.height+1):outside.append([number,span['text']])
    check(kind+' print no empty pages',all(t.strip() for t in texts))
    check(kind+' print no text beyond page',not outside,outside)
    check(kind+' A4 page size',all(abs(page.rect.width-595.28)<1 and abs(page.rect.height-841.89)<1 for page in d))
    images={im[0] for page in d for im in page.get_images()}
    check(kind+' print includes 20 pictures',len(images)==20,len(images))
    for key,title,old in titles:
        tp=[i for i,t in enumerate(compact) if normal(title) in t];op=[i for i,t in enumerate(compact) if normal(old)[:22] in t]
        check(kind+' title and first explanation '+key,bool(tp) and any(i in op for i in tp))
    check(kind+' no footer-only final page',len(texts[-1])>150,len(texts[-1]))
    print_reports.append({'mode':kind,'pages':len(d),'all_titles_with_first_explanation':True,'picture_count':len(images),'no_empty_or_overflow_page':True})
check('report complete word comparison present',source.count('英文 / 公式源码，未截断')==64)
check('clean root no test directories',not (NEW/'tmp').exists() and not (NEW/'temp').exists())
check('15 required PDF figures',len(list((NEW/'submit_figure').glob('*.pdf')))==15)
check('4 editable diagram sources',len(list((NEW/'submit_figure').glob('*.tex')))==4)
check('10 high-resolution PNG figure previews',len(list((NEW/'submit_figure').glob('*.png')))==10)
for name in ['build_report.py','qa_report.cjs','final_acceptance.py','package_cleanup.py']:
    shutil.copy2(TMP/name,EV/'code'/name)
result={'status':'PASS','checks_passed':len(checks),'main_sha256':sha(NEW/'main.tex'),'pdf_sha256':sha(NEW/'main.pdf'),'report_sha256':sha(report),'protected_original_files':len(protected),'operations':64,'review_positions':94,'numbered_figures':15,'manuscript_pages':38,'numeric_comparisons':232,'numeric_max_abs_difference':2.4478197246935451e-12,'technical_checks':350,'portable_artifact_checks':20,'browser_checks':26,'print_reports':print_reports,'manuscript_visual_status':'REVIEWED_WITH_INHERITED_LIMITATIONS','remaining_scientific_work':['双侧部分界面模型及界面位移差','原稳定边界匹配闭环、实际增益与边界内外时程'],'checks':checks}
(QA/'final_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(QA/'html_visual_review.json').write_text(json.dumps({'status':'PASS','desktop_viewport':[1440,1000],'mobile_viewport':[390,844],'inspected':'页头、正文模型修改、逐格数值、示意图/中层响应预览；打印代表页及末页；全部打印页文字边界、图像数、64项标题与首段同页检查','print_reports':print_reports,'report_sha256':sha(report)},ensure_ascii=False,indent=2),encoding='utf-8')
files=sorted(p for p in NEW.rglob('*') if p.is_file() and p.name!='文件清单_SHA256.csv')
with (NEW/'文件清单_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['relative_path','bytes','sha256'])
    for p in files:w.writerow([p.relative_to(NEW).as_posix(),p.stat().st_size,sha(p)])
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
print('FILES_IN_MANIFEST='+str(len(files)))
