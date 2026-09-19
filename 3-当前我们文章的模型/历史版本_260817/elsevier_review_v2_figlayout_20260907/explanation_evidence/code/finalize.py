from pathlib import Path
import json,csv,hashlib,shutil,re
from html.parser import HTMLParser
import numpy as np
from scipy.io import loadmat

TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
NEW=ROOT.parent/'260817/elsevier_review_v2_figlayout_20260907'
SOURCE=ROOT.parent/'260817/elsevier_review_v2_20260907'
EV=NEW/'explanation_evidence';VAL=EV/'validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name,passed,**info):
 checks.append({'name':name,'passed':bool(passed),**info});assert passed,(name,info)
protected=json.loads((EV/'protected_v2.json').read_text('utf-8'))
for name,digest in protected.items():check('previous version unchanged: '+Path(name).name,Path(name).is_file() and sha(Path(name))==digest,path=name)
check('previous version file set unchanged',set(protected)=={str(p.resolve()) for p in SOURCE.rglob('*') if p.is_file()})
changed_figs=[]
for p in (SOURCE/'submit_figure').glob('*.pdf'):
 target=NEW/'submit_figure'/p.name
 if sha(target)!=sha(p):changed_figs.append(p.name)
check('only figure6 and figure13 PDFs changed',set(changed_figs)=={'fig12_horizontal_modes.pdf','fig15_peak_drift.pdf'})
for p in (SOURCE/'supplementary_data').iterdir():
 if p.is_file():check('supplementary source identical: '+p.name,sha(p)==sha(NEW/'supplementary_data'/p.name))
layout=json.loads((EV/'data/layout_figure_manifest.json').read_text('utf-8'))
check('two 1 by 4 figures',len(layout)==2 and all(x['layout']==[1,4] for x in layout))
check('24 original data series retained',sum(len(x['data_series']) for x in layout)==24)
check('12 frequencies retained',sum('frequency_hz'in s for x in layout for s in x['data_series'])==12)
for item in layout:
 for ext in ['pdf','png']:check('figure manifest hash: '+item['file']+'.'+ext,sha(NEW/'submit_figure'/(item['file']+'.'+ext))==item[ext+'_sha256'])
for name in ['independent_numeric_checks.json','manuscript_compile.json','browser_report_checks.json','render_checks.json']:
 d=json.loads((VAL/name).read_text('utf-8'));check('completed validation: '+name,d['status']=='PASS')
data=json.loads((EV/'data/explanation_calculations.json').read_text('utf-8'))
for div in [1,2]:
 mat=loadmat(NEW/'supplementary_data'/f'division_{"I"*div}_matrices.mat');M=mat['M_full']
 check(f'full mass diagonal {div}',np.max(abs(M-np.diag(np.diag(M))))==0)
 for m in [m for m in data['models'] if m['division']==div]:
  V=np.array(m['expanded_modes']);norm=np.sum(V*(M@V),axis=0)
  check(f'full mass normalization {div}/{m["method"]}',max(abs(norm-1))<1e-12,max_error=float(max(abs(norm-1))))
htmlfile=NEW/'图13与图15读图及计算讲解汇报.html';htmltext=htmlfile.read_text('utf-8')
class AuditHTML(HTMLParser):
 def __init__(self):super().__init__();self.img=[];self.external=[];self.ids=[];self.json='';self.in_json=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id'in a:self.ids.append(a['id'])
  if tag=='img':self.img.append(a.get('src',''))
  if tag=='script' and a.get('id')=='report-data':self.in_json=True
  for key in ['src','href']:
   if a.get(key,'').startswith(('http:','https:')):self.external.append(a[key])
 def handle_endtag(self,tag):
  if tag=='script':self.in_json=False
 def handle_data(self,s):
  if self.in_json:self.json+=s
audit=AuditHTML();audit.feed(htmltext);audit.close()
check('HTML three inline PNGs',len(audit.img)==3 and all(s.startswith('data:image/png;base64,') for s in audit.img))
check('HTML no external rendering dependencies',not audit.external)
check('HTML unique element IDs',len(audit.ids)==len(set(audit.ids)))
check('HTML embedded exact numeric calculation data',json.loads(audit.json)==data)
check('HTML key calculations present',all(x in htmltext for x in ['113.8673%','2.259470%','0.891420','66.3485%','64.0788%','−3.4208%']))
check('figure15 source image unchanged',sha(NEW/'submit_figure/fig16_modal_shares.png')==sha(SOURCE/'submit_figure/fig16_modal_shares.png'))
compile_result=json.loads((VAL/'manuscript_compile.json').read_text('utf-8'))
check('final manuscript tex/pdf match compiled files',sha(NEW/'main.tex')==compile_result['main_sha256'] and sha(NEW/'main.pdf')==compile_result['pdf_sha256'])
for filename in ['report_desktop.png','report_figure15.png','report_modal_calculation.png','report_mobile.png','report_mobile_bars.png']:
 shutil.copy2(TMP/filename,VAL/filename)
for filename in ['inspect_rendered.py','finalize.py']:
 shutil.copy2(TMP/filename,EV/'code'/filename)
logdir=EV/'validation/compilation_logs';logdir.mkdir(exist_ok=True)
for p in TMP.glob('compile_*.log'):shutil.copy2(p,logdir/p.name)
# Only move the explicitly named, generated compilation intermediates inside this new package.
for suffix in ['.abs','.aux','.blg','.log','.out']:
 p=NEW/('main'+suffix);dest=logdir/p.name
 if p.exists():
  assert p.resolve().parent==NEW.resolve() and dest.resolve().is_relative_to(NEW.resolve())
  shutil.move(str(p),str(dest))
readme='''# 图6、图13布局更新与图13、图15读图讲解

本包建立于2026-09-07，以前一版 `elsevier_review_v2_20260907` 为基准；此前版的115个文件完整保留。

## 阅读入口
- `图13与图15读图及计算讲解汇报.html`：本次主汇报。包含原图、三层框架坐标图、真实峰值演算、五阶模态逐项计算、柱高与表5的联系；可单独复制后离线阅读。
- `main.pdf`：38页更新稿。图6在第24页，图13在第31页，图15在第34页。
- `main.tex`：可编辑主稿；与前版相比仅改两处图注短语。
- `submit_figure`：15份矢量投稿图；图6、图13另附600dpi PNG，图15附原PNG以便报告独立使用。
- `supplementary_data`：原样复制的模型矩阵和响应时程。
- `explanation_evidence`：前版基准、差异、完整派生数据、代码与验收证据。

## 本次改变
图6和图13改为1行4列、每个子图竖长。图6保持12项频率，图13保持36个峰值及原子图顺序。图15等其余13幅投稿图不变；全部原负间距、正文红色标注及其余论述保留。

## 验证与已知边界
- 模态与响应的144项独立数值检查通过，最大绝对差3.3862e-15；份额/峰值的预设门限为1e-10。
- 142项浏览器检查通过，包括全部36个峰值选择、90个坐标份额选择、桌面/390px窄屏和移动后离线使用。
- 报告默认打印11页，全部数据表展开时14页；无空白页或越界文字，公式、表格和代表页实际渲染检查。
- 论文实际执行pdfLaTeX、BibTeX、pdfLaTeX两遍；38页、15图，无Error、未定义引用/文献或??。
- 保留原42条负间距，原第6、7、8、12、13、21、22页部分公式与文字紧贴/重叠保持；本轮未改变这些排版设置。
- 图15是当前相同15物理坐标和前5阶模态上的质量加权份额诊断。ΔE是两项带符号相对变化之和，不能解释为总能量变化或稳定性阈值。

## 本包内重建
主稿在本目录就地运行 `pdflatex -interaction=nonstopmode main.tex`、`bibtex main`、`pdflatex -interaction=nonstopmode main.tex` 两遍。TeX所需图件、模板和文献已在本包。

`explanation_evidence/code/plot_layout.py` 可从本包内的CSV重绘图6与图13；需要Python、numpy、matplotlib及TeX Live。`build_explanation.py` 可从本包内的JSON和PNG重建单文件HTML。

其余代码是此次在原工作区 `tmp/figure6_13_explanation_20260907` 执行的准备、复算与验收记录；`prepare.py` 会拒绝覆盖已有目标目录。临时截图、打印PDF和全稿逐页渲染保留在该tmp目录，不混入论文根目录。
'''
(NEW/'README.md').write_text(readme,encoding='utf-8')
result={'status':'PASS','checks_passed':len(checks),'checks':checks,'previous_version_files_protected':len(protected),'main_pdf_pages':38,'numeric_checks_passed':144,'browser_checks_passed':142,'report_print_pages':11,'expanded_report_print_pages':14,'report_sha256':sha(htmlfile),'main_tex_sha256':sha(NEW/'main.tex'),'main_pdf_sha256':sha(NEW/'main.pdf'),'visual_review':{'updated_figures':'PASS','manuscript_changed_pages':'24 and 31--38 inspected; 29 other pages pixel-identical to prior PDF','report_desktop_mobile':'PASS','report_print':'PASS after removing a trailing paragraph-only page and footer-only page','inherited_limit':'Original 42 negative skips and corresponding tight/overlapping formula layout retained.'}}
(VAL/'final_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (NEW/'delivery_manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['relative_path','bytes','sha256'])
 for p in sorted(NEW.rglob('*')):
  if p.is_file() and p.name!='delivery_manifest.csv':w.writerow([p.relative_to(NEW).as_posix(),p.stat().st_size,sha(p)])
print(json.dumps({k:v for k,v in result.items() if k not in ['checks','visual_review']},ensure_ascii=False,indent=2))
