from pathlib import Path
import json,csv,hashlib,shutil
import fitz
TMP=Path(__file__).resolve().parent;NEW=TMP.parents[1].parent/'260817/elsevier_review_v2_refined_20260907';EV=NEW/'refinement_evidence';VAL=EV/'validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=json.loads((EV/'protected_previous.json').read_text('utf-8'))
assert all(Path(n).exists() and sha(Path(n))==h for n,h in protected.items())
SOURCE=NEW.parent/'elsevier_review_v2_figlayout_20260907'
assert {str(p.resolve()) for p in SOURCE.rglob('*') if p.is_file()}==set(protected)
changed=[p.name for p in (SOURCE/'submit_figure').glob('*.pdf') if sha(p)!=sha(NEW/'submit_figure'/p.name)]
assert set(changed)=={'fig12_horizontal_modes.pdf','fig16_modal_shares.pdf'}
assert all(sha(p)==sha(NEW/'supplementary_data'/p.name) for p in (SOURCE/'supplementary_data').iterdir() if p.is_file())
for name in ['figure6_layout.json','absolute_metric_numeric_checks.json','figure15_values.json','manuscript_compile.json','report_browser_checks.json']:assert json.loads((VAL/name).read_text('utf-8'))['status']=='PASS'
fig15=json.loads((VAL/'figure15_values.json').read_text('utf-8'));source=json.loads((EV/'data/explanation_calculations.json').read_text('utf-8'))
for c in fig15['left_curves']:assert c['shares']==next(m['shares'] for m in source['models'] if (m['division'],m['method'])==(c['division'],c['method']))
doc=fitz.open(TMP/'report_print.pdf');pages=[]
for i,p in enumerate(doc,1):
 words=p.get_text('words');assert len(p.get_text().strip())>50
 assert not [w for w in words if w[0]<-1 or w[1]<-1 or w[2]>p.rect.width+1 or w[3]>p.rect.height+1]
 p.get_pixmap(dpi=105).save(TMP/'report_print'/f'page_{i:02}.png');pages.append({'page':i,'text_length':len(p.get_text()),'outside_text':0})
assert len(doc)==5
for f in ['report_desktop.png','report_mobile.png','report_mobile_metric.png']:shutil.copy2(TMP/f,VAL/f)
logdir=VAL/'compilation_logs';logdir.mkdir(exist_ok=True)
for p in TMP.glob('compile_*.log'):shutil.copy2(p,logdir/p.name)
for suffix in ['.abs','.aux','.blg','.log','.out']:
 p=NEW/('main'+suffix);q=logdir/p.name
 if p.exists():
  assert p.resolve().parent==NEW.resolve() and q.resolve().is_relative_to(NEW.resolve());shutil.move(str(p),str(q))
readme='''# 图6图内频率与图15变化幅度修订

本包为2026-09-07按Doctor Bego确认选择生成的独立版本；上一版86个文件完整保留。

- `图6排版与图15变化幅度指标修改汇报.html`：主汇报，包含更新图6、图15、全部8个柱值、表5四值及16处完整原文/新文对照；可离线独立阅读。
- `main.tex`：可编辑主稿；`main.pdf`：38页编译稿。图6第24页，图13第31页，图15/表5第33页。
- `submit_figure`：15幅投稿矢量图；本轮只重绘图6、图15，另附600dpi PNG。图6频率注释8pt，位于各自子图内空白处。
- `supplementary_data`：原样保留的模型矩阵和响应时程。
- `refinement_evidence/data/modal_share_deviation.json`及`actuator_share_deviations.csv`：本版指标，以逐坐标绝对相对变化相加。表5依次为0.0455、0.0039、1.3859、0.0423。
- data目录的其余文件为上一版计算输入/来源；其中`explanation_calculations.json`与`new_actuator_share_contributions.csv`含上一版有向指标，用于追溯比较，不是本版表5的取值入口。
- `refinement_evidence/manuscript_changes.json`、`main_changes.diff`、`baseline`：16处修改及旧稿基准。改动继续标红；原42条负间距保持。
- `refinement_evidence/code`：准备、计算、出图、改稿与验收代码。两份plot脚本及revise_metric/build_report脚本可在本包内运行；准备及编译验收脚本记录本次在原工作区tmp的运行环境。

验证：8个柱值通过两条数值路径交叉核对，最大差1.3628e-14；图6的12条曲线和12项频率一致，4组8pt注释与曲线有2.5pt避让；主稿41项一致性/编译检查与报告13项浏览器检查通过。报告5页A4打印已渲染检查。

主稿就地编译：pdflatex main.tex → bibtex main → pdflatex main.tex两遍。全部模板、文献和图件均已包含。原负间距造成的部分公式紧贴/重叠按用户要求保留；结构模型和闭环稳定性研究范围未扩大。本轮修改已完成，待用户审阅。
'''
(NEW/'README.md').write_text(readme,encoding='utf-8');shutil.copy2(__file__,EV/'code/finalize.py')
result={'status':'PASS','protected_previous_files':len(protected),'changed_figure_pdfs':changed,'unchanged_left_modal_shares':90,'independent_bar_values_verified':8,'manuscript_checks':41,'browser_checks':13,'report_print_pages':pages,'visual_review':'Figures 6/15 and all 19 changed manuscript pages inspected; inherited spacing retained. Report desktop/mobile and print inspected.','main_tex_sha256':sha(NEW/'main.tex'),'main_pdf_sha256':sha(NEW/'main.pdf'),'report_sha256':sha(NEW/'图6排版与图15变化幅度指标修改汇报.html')}
(VAL/'final_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (NEW/'delivery_manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['relative_path','bytes','sha256'])
 for p in sorted(NEW.rglob('*')):
  if p.is_file() and p.name!='delivery_manifest.csv':w.writerow([p.relative_to(NEW).as_posix(),p.stat().st_size,sha(p)])
print(json.dumps(result,ensure_ascii=False,indent=2))
