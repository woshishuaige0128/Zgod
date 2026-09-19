from pathlib import Path
import json,hashlib,re,shutil
from html.parser import HTMLParser
import fitz
ROOT=Path(__file__).resolve().parents[2]
TMP=Path(__file__).resolve().parent
REV=ROOT.parent/'260817/elsevier_review_20260906'
OUT=REV/'revision_evidence/逐项修改报告'
REPORT=REV/'全文修改逐项对照与回退决策汇报.html'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((OUT/'全部修改清单.json').read_text(encoding='utf-8'))
start=json.loads((TMP/'turn_start_hashes.json').read_text(encoding='utf-8'))
assert all(Path(p).is_file() and sha(Path(p))==h for p,h in start.items())
class Audit(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.current=None;self.pre=False;self.articles={};self.links=[];self.resources=[];self.utf8=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='article':self.current=a['id'];self.articles[self.current]=[]
  if tag=='pre':self.pre=True;self.articles[self.current].append('')
  if tag=='a':self.links.append(a.get('href',''))
  if tag in ['img','script','link']:self.resources.append((tag,a.get('src',a.get('href',''))))
  if tag=='meta' and a.get('charset')=='utf-8':self.utf8=True
 def handle_endtag(self,tag):
  if tag=='pre':self.pre=False
  if tag=='article':self.current=None
 def handle_data(self,s):
  if self.pre:self.articles[self.current][-1]+=s
p=Audit();p.feed(REPORT.read_text(encoding='utf-8'))
assert p.utf8 and len(p.articles)==112
for it in data['items']:
 assert p.articles[it['id']][-2:]==[it['old'] or '（此处原来没有内容）',it['new'] or '（删除，无替代文本）'],it['id']
 assert all(it[k] for k in ['title','why','source','recommendation','rollback','groups'])
assert all(not r[1] or r[1].startswith('data:') for r in p.resources)
assert all(x.startswith('#') for x in p.links)
assert len({x['id'] for x in data['decisions']})==198
assert len({s['cell_record_id'] for x in data['items'] for s in x['subpoints'] if 'cell_record_id'in s})==30
browser=json.loads((OUT/'browser_qa.json').read_text(encoding='utf-8'))
assert len(browser['checks'])==34 and all(x['pass'] for x in browser['checks'])
result={'protected_existing_files':len(start),'protected_files_unchanged':len(start),'all_html_raw_pairs_equal_catalog':112,'unique_decision_ids':198,'table345_changed_cell_ids':30,'utf8':True,'external_resources':0,'external_navigation':0,'browser_checks_pass':34}
normalize=lambda s:re.sub(r'\s','',s)
prints=[]
for filename in ['report_print_A4.pdf','report_print_A4_with_source.pdf']:
 d=fitz.open(TMP/filename);overflow=[];blank=[];headed=[]
 texts=[normalize(pg.get_text()) for pg in d]
 for n,pg in enumerate(d):
  if len(pg.get_text())<100 and not pg.get_images():blank.append(n+1)
  for b in pg.get_text('dict')['blocks']:
   for l in b.get('lines',[]):
    for s in l['spans']:
     if s['bbox'][0]<15 or s['bbox'][2]>pg.rect.width-15:overflow.append([n+1,s['bbox'],s['text']])
 for it in data['items']:
  if it['category']=='公式间距':continue
  title=normalize(it['title']);intro=normalize(it['old_meaning'])[:16]
  found=[i+1 for i,t in enumerate(texts) if title in t and intro in t]
  headed.append({'id':it['id'],'same_page_title_and_old_meaning':bool(found),'pages':found})
 assert not overflow and not blank,(filename,overflow,blank)
 assert all(x['same_page_title_and_old_meaning'] for x in headed),(filename,[x for x in headed if not x['same_page_title_and_old_meaning']])
 prints.append({'filename':filename,'pages':len(d),'sha256':sha(TMP/filename),'off_page_text_spans':0,'blank_pages':0,'heading_with_first_comparison':headed})
result['print_checks']=prints
(OUT/'final_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(__file__,OUT/Path(__file__).name)
manifest={str(p.relative_to(REV)).replace('\\','/'):sha(p) for p in [REPORT,*sorted(OUT.iterdir())] if p.is_file() and p.name!='report_files_sha256.json'}
(OUT/'report_files_sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'static_and_protection':'PASS','browser':'34/34 PASS','headings_and_print_bounds':'PASS','print_pages':[x['pages'] for x in prints],'report_files':len(manifest)},ensure_ascii=False))
