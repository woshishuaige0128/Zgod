from pathlib import Path
import json, re, hashlib, difflib, html, base64, csv, io, shutil
from collections import Counter
import fitz
from catalog import META, SUBPOINTS

TMP=Path(__file__).resolve().parent
ROOT=TMP.parent.parent
REV=ROOT.parent/'260817/elsevier_review_20260906'
OLD=ROOT.parent/'260817/elsevier'
FROZEN=ROOT/'figure/表3至表5_按当前出图设置核查_20260906/evidence/main_source_readonly.tex'
OUT=REV/'revision_evidence/逐项修改报告'
OUT.mkdir(exist_ok=True)
REPORT=REV/'全文修改逐项对照与回退决策汇报.html'
H=json.loads((TMP/'hunks.json').read_text(encoding='utf-8'))
old=FROZEN.read_text(encoding='utf-8'); new=(REV/'main.tex').read_text(encoding='utf-8')
oldlines=old.splitlines(); newlines=new.splitlines()
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
e=lambda s: html.escape(str(s),quote=True)
beforehash=json.loads((REV/'revision_evidence/source_hashes.json').read_text())
deliveryhash=json.loads((REV/'revision_evidence/delivery_hashes.json').read_text())
assert sha(FROZEN)==beforehash['main.tex']
assert all(sha(REV/k)==v for k,v in deliveryhash.items())
assert len(H)==104
rebuild=oldlines[:]
for h in reversed(H):
 assert '\n'.join(oldlines[h['old_start']-1:h['old_end']])==h['old']
 assert '\n'.join(newlines[h['new_start']-1:h['new_end']])==h['new']
 rebuild[h['old_start']-1:h['old_end']]=h['new'].split('\n') if h['new_end']>=h['new_start'] else []
assert rebuild==newlines
reverse=newlines[:]
for h in reversed(H):reverse[h['new_start']-1:h['new_end']]=h['old'].split('\n') if h['old_end']>=h['old_start'] else []
assert reverse==oldlines

# Render figure regions from the delivered PDF, preserving every diagram label.
pdf=fitz.open(REV/'main.pdf')
for n,pg,rect in [(1,11,(112,50,430,214)),(2,15,(156,198,386,407)),(3,16,(149,125,392,304)),(4,18,(90,49,453,201))]:
 pdf[pg-1].get_pixmap(matrix=fitz.Matrix(2.5,2.5),clip=fitz.Rect(rect),alpha=False).save(TMP/f'new_figure_{n}.png')

rows=json.loads((REV/'revision_evidence/table345_verified_values.json').read_text(encoding='utf-8'))['rows']
changed=[r for r in rows if r['status']!='相符']
assert len(changed)==30
cell_hunk=lambda r:83 if r['table']==3 else 99 if r['table']==5 else 90 if 'El Centro' in r['item'] else 91
table_titles={3:'模态频率误差与振型相似性',4:'首层响应误差',5:'有符号模态份额指标'}
table_why={3:'以当前出图链的质量、刚度矩阵重新求解特征值和振型，按原表精度取整；MATLAB与Python独立计算互证。',4:'以当前图使用的时程计算误差平方的时域积分，统一使用全记录峰峰值归一化；扫频按表中固定频带边界积分，并在线性插值后的端点截取。MATLAB与Python互证。',5:'按论文现有公式，使用前5阶振型；约化振型恢复到15个原坐标并用完整质量矩阵归一化，在各类两作动坐标上求有符号相对变化之和。MATLAB与Python互证。'}
table_source={3:'表3_完整模态指标.csv；table345_verified_values.json',4:'逐单元格核查_44项.csv；table345_verified_values.json；表4_频段边界与积分方式敏感性.csv',5:'表5_15个物理坐标模态份额.csv；table345_verified_values.json'}
for hn in [83,90,91,99]:
 rs=[r for r in changed if cell_hunk(r)==hn]; t=rs[0]['table']
 META[hn]=(f'表{t}：'+('El Centro行' if hn==90 else '五个扫频频带' if hn==91 else '第二类两阶模态' if hn==83 else '两类四个指标')+f'，{len(rs)}格改值','数值',f'原表内{len(rs)}个显示值与当前出图口径复算不符，逐格列在下方。',f'将这{len(rs)}格改为当前复算值并标红，其他显示值保留。',table_why[t],table_source[t],'按当前出图口径建议保留','单格可以选择另改；如恢复旧值，必须提供相应模型与计算口径，并同步引用该值的摘要、正文和结论。','全文数值'+('|模态指标' if t==5 else ''))

items=[]; decision_meta=[]
eqnames={'full-order-eom':'完整结构运动方程','substructure-eom':'数值与物理子结构运动方程','physical-eom':'数值与物理子结构运动方程','partitioned-local-eom':'保留/缩聚坐标的分块方程','general-projection':'统一投影变换','assembled-reduced':'装配后约化运动方程','guyan-coordinate-relation':'Guyan静力恢复关系','guyan-transformation':'Guyan变换矩阵','fixed-interface-modes':'固定界面模态方程','cb-transformation':'Craig–Bampton变换矩阵','cb-internal-recovery':'Craig–Bampton内部坐标恢复','integer-delay':'整数步通道时滞','delay-recovery':'含时滞的两种坐标恢复关系','cb-delay-recovery':'含时滞的两种坐标恢复关系','delayed-eom':'含时滞的约化运动方程','z-derivatives':'离散积分的z域导数算子','lqr-law':'LQR反馈律','z-matrix':'闭环z域矩阵','characteristic-equation':'闭环特征方程','mac':'振型相似性MAC公式','nrmse':'响应误差NRMSE公式','dof-energy':'坐标模态份额定义','energy-change':'模态份额相对变化指标'}
def location(h):
 prior='\n'.join(oldlines[:h['old_start']-1])
 secs=re.findall(r'\\(?:sub)*section\{([^}]+)\}',prior)
 title=secs[-1] if secs else '导言区 / 摘要'
 labels=re.findall(r'\\label\{([^}]+)\}',prior)
 return title,labels[-1] if labels else ''
for h in H:
 n=h['n']; sec,label=location(h)
 if n not in META:
  assert h['old']==r'\vspace{-3.5em}'
  is_before=oldlines[h['old_start']].startswith(r'\begin')
  if is_before:label=re.findall(r'\\label\{([^}]+)\}','\n'.join(oldlines[h['old_start']:h['old_start']+100]))[0]
  side='前' if is_before else '后';name=eqnames[label.removeprefix('eq:')]
  META[n]=(f'取消{name}之{side}的负间距','公式间距',f'在公式{side}插入负间距，使后续内容向上挤压3.5个字体高度。','改成说明性注释，由模板决定公式间距。','原稿大量负间距会让公式与正文贴得过近；本轮统一去掉后逐页检查。公式数学内容未改。','两版TeX该位置，标签'+label+'；上轮29页PDF视觉复核','可按排版偏好回退','可单处恢复或改为更小间距；需重新编译检查相邻文字和公式是否碰撞。','公式与分页')
 title,cat,om,nm,why,source,rec,risk,groups=META[n]
 it={**h,'id':f'修改{n:03d}','title':title,'category':cat,'old_meaning':om,'new_meaning':nm,'why':why,'source':source,'recommendation':rec,'rollback':risk,'groups':groups.split('|'),'section':sec,'near_label':label,'subpoints':[]}
 for k,sp in enumerate(SUBPOINTS.get(n,[]),1):
  it['subpoints'].append({'id':f'修改{n:03d}.{k}','title':sp[0],'old_meaning':sp[1],'new_meaning':sp[2],'why':sp[3]})
 if n==53:
  for k,mat in enumerate(['柱：A992 Gr.50','梁：A36'],1):it['subpoints'].append({'id':f'修改053.{k}','title':mat+'的弹性模量','old_meaning':'200 GPa','new_meaning':'206 GPa','why':'对齐当前E=206e9 Pa输入；回到200 GPa需要重算下游结果。'})
 for k,r in enumerate([r for r in changed if cell_hunk(r)==n],1):
  scope=('第一类：外侧跨下部两层，作动ψ1/ψ6' if r['division']==1 else '第二类：外侧跨三层，作动ψ1/ψ11')
  it['subpoints'].append({'id':f'修改{n:03d}.格{k:02d}','title':f"表{r['table']} · {scope} · {r['item']} · {r['method']} · {r['metric']}",'old_meaning':r['manuscript_value'],'new_meaning':r['rounded_value'],'why':table_why[r['table']]+' 未取整复算值：'+format(r['recomputed'],'.12g')+'。','cell_record_id':r['id']})
 items.append(it)

def bib_entries(txt):
 starts=list(re.finditer(r'(?m)^@\w+\{([^,]+),',txt))
 return {m[1]:txt[m.start():starts[i+1].start() if i+1<len(starts) else len(txt)].strip() for i,m in enumerate(starts)}
oldbib=(OLD/'references.bib').read_text(encoding='utf-8');newbib=(REV/'references.bib').read_text(encoding='utf-8')
be=bib_entries(oldbib);bn=bib_entries(newbib)
assert set(be)-set(bn)=={'CraigBampton1968','ChenRicles2008b'}
for j,(key,kept,hn) in enumerate([('CraigBampton1968','Craig1968',23),('ChenRicles2008b','ChenCR2008',39)],1):
 items.append(dict(id=f'文献{j:02d}',title=f'删除重复BibTeX条目 {key}',category='文献',old=be[key],new='（该重复条目删除；保留条目如下）\n'+bn[kept],old_meaning=f'同一文献同时有{key}和{kept}两个引用键。',new_meaning=f'保留{kept}；正文引用键同步修改。',why='作者、题名与DOI对应同一文献，避免参考文献重复编号。',source='两版references.bib，正文修改'+str(hn),recommendation='建议保留',rollback='若恢复旧键，须同时恢复其BibTeX条目，并重新运行BibTeX及两轮LaTeX。',groups=['参考文献'],section='参考文献库',subpoints=[]))

figs={33:(1,['fig01_rths_loop_optionD.png'],'fig01_force_feedback.tex'),52:(2,['fig03_benchmark_geometry_optionC.png'],'fig02_geometry.tex'),54:(3,['fig04b_dof_idealized_optionD.png'],'fig03_dofs.tex'),61:(4,['fig05a_divisionI_concept_optionD.png','fig05b_divisionII_concept_optionD.png'],'fig04_divisions.tex')}
inventory=[]
allfiles=sorted(set(beforehash)|set(deliveryhash))
for rel in allfiles:
 status='原样复制' if rel in beforehash and rel in deliveryhash and beforehash[rel]==deliveryhash[rel] else '替换/重新生成' if rel in beforehash and rel in deliveryhash else '仅保留在原目录' if rel in beforehash else '新增'
 why='原文件字节未变，直接复制到修订目录。';kind='未变文件'
 if rel=='main.tex':why='104个差异块，详见逐项主清单。';kind='论文内容'
 elif rel=='references.bib':why='删除2条重复文献，详见文献清单。';kind='论文内容'
 elif status=='仅保留在原目录':
  if rel.endswith('.png'):
   why=('原稿没有引用此图，修订目录未复制；原文件仍在。' if Path(rel).name in ['fig02_pole_mapping_optionB.png','fig04a_dof_assumptions_optionD.png'] else '原稿引用的PNG由新TikZ图替代，修订目录未复制；原文件仍在。')
   kind='图件文件'
  else:why='SyncTeX编辑器定位辅助文件未复制；不属于论文内容。';kind='编译产物'
 elif status=='替换/重新生成' and rel.startswith('main.'):
  why='由修改后的稿件重新编译生成，随源码/文献/图件变化；回退时应重新编译，不能只替换其中一个缓存文件。';kind='编译产物'
 elif status=='新增':
  if rel.startswith('submit_figure'):why='新示意图的可编辑矢量源码；旧图—新图及完整新源码见相应主清单。';kind='图件文件'
  elif rel.startswith('supplementary_data'):why='新增可复现附件，提供当前精度模型矩阵/坐标规则；文件内容摘要见补充材料清单。';kind='补充数据'
  else:why='本轮改稿过程、指标复算、差异、验证或说明文件；服务审阅追溯，不属于论文正文。';kind='修订证据'
 inventory.append({'path':rel.replace('\\','/'),'status':status,'kind':kind,'why':why,'old_sha256':beforehash.get(rel),'new_sha256':deliveryhash.get(rel)})

extra=[]
from scipy.io import loadmat
import numpy as np
for j,p in enumerate(sorted((REV/'supplementary_data').iterdir()),1):
 if p.suffix=='.csv':
  a=np.loadtxt(p,delimiter=',');desc=f'{a.shape[0]}×{a.shape[1]}完整模型矩阵，纯数值CSV；用于重建当前精度基准。';content='\n'.join(p.read_text().splitlines()[:3])+'\n（此处展示前3行；完整数值在原附件内）'
 elif p.suffix=='.mat':
  a=loadmat(p);desc='MATLAB矩阵包；包含'+', '.join(f'{k}{v.shape}' for k,v in a.items() if not k.startswith('__'))+'。';content=desc
 else:content=p.read_text(encoding='utf-8');desc='坐标顺序、矩阵用途及模型解释说明。'
 extra.append(dict(id=f'附件{j:02d}',title='新增 '+p.name,category='新增附件',old='（原稿没有该附件）',new=content,old_meaning='原交付目录没有这个文件。',new_meaning=desc,why='响应模型可复现性意见，公开当前生成图表所用的矩阵与规则。该附件不能替代历史稳定边界生成矩阵。',source=str(p),recommendation='如采用当前精度模型，建议保留',rollback='可选择删去或改用别的补充格式；同时处理正文修改055中的补充材料指引。',groups=['基准参数','模型路线'],section='补充材料',subpoints=[]))
items+=extra

def decision(id,title,groups):
 decision_meta.append({'id':id,'title':title,'groups':groups})
 return f'<div class="decision" data-id="{e(id)}"><label>对此项的决定 <select aria-label="{e(id)} 决定"><option>待决定</option><option>保留</option><option>回退</option><option>另改</option></select></label><input type="text" aria-label="{e(id)} 备注" placeholder="可写：只恢复句式；保留数值……"></div>'
def pair(om,nm,cls=''):
 return f'<div class="pair {cls}"><div class="before"><b>修改前</b><p>{e(om)}</p></div><div class="after"><b>修改后</b><p>{e(nm)}</p></div></div>'
def rawpair(a,b):return '<div class="pair exact"><div class="before"><b>完整原文 / 原源码</b><pre>'+e(a or '（此处原来没有内容）')+'</pre></div><div class="after"><b>完整新文 / 新源码</b><pre>'+e(b or '（删除，无替代文本）')+'</pre></div></div>'
def img(p):return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" alt="{e(p.name)}">'

cards=[]
for it in items:
 id=it['id'];n=it.get('n');groups=' · '.join(it['groups'])
 source_lines=f"冻结原稿 {it['old_start']}—{it['old_end']} 行 → 修订稿 {it['new_start']}—{it['new_end']} 行" if n else it['section']
 if n and it['old_end']<it['old_start']:source_lines=f"冻结原稿第 {it['old_start']} 行前插入 → 修订稿 {it['new_start']}—{it['new_end']} 行"
 c=f'<article class="change" id="{e(id)}" data-category="{e(it["category"])}"><div class="entry-head"><div class="eyebrow">{e(id)} · {e(it["category"])} · {e(it["section"])}</div><h3>{e(it["title"])}</h3><p class="location">{e(source_lines)}</p>'
 c+=pair(it['old_meaning'],it['new_meaning'])+'</div>'
 c+=f'<p><b>为什么改：</b>{e(it["why"])}</p><p><b>依据：</b>{e(it["source"])}</p><div class="rollback"><b>回退判断：</b>{e(it["recommendation"])}。<br><b>回退影响：</b>{e(it["rollback"])}<br><b>关联内容：</b>{e(groups)}</div>'
 primary_control=decision(id,it['title'],it['groups'])
 c+=primary_control
 if it['subpoints']:
  c+='<div class="subpoints"><h4>可以拆开决定的具体改动</h4><p class="muted">下列子项可单独选择；若与整段决定不同，以您给出的子项意见为准。导出仅记录意见。</p>'
  for s in it['subpoints']:
   c+=f'<section class="subpoint" id="{e(s["id"])}"><h5>{e(s["id"])}　{e(s["title"])}</h5>'+pair(s['old_meaning'],s['new_meaning'])+f'<p><b>理由 / 回退提示：</b>{e(s["why"])}</p>'+decision(s['id'],s['title'],it['groups'])+'</section>'
  c+='</div>'
 if n in figs:
  fnum,olds,nf=figs[n]
  c+='<div class="figure-comparison"><h4>实际图件对照</h4><p>左侧为原稿引用的原PNG，右侧为已交付PDF中的新图。新图的红色来自修订标红。</p><div class="pair"><div class="before"><b>修改前</b>'+''.join(img(OLD/'submit_figure'/f) for f in olds)+'</div><div class="after"><b>修改后</b>'+img(TMP/f'new_figure_{fnum}.png')+'</div></div></div>'
  c+='<details class="source"><summary>查看新增矢量图完整源码 '+e(nf)+'</summary><pre>'+e((REV/'submit_figure'/nf).read_text(encoding='utf-8'))+'</pre></details>'
 c+='<details class="source"><summary>查看这一项的完整原文与新文'+('（LaTeX原样，未截断）' if n else '')+'</summary>'+rawpair(it['old'],it['new'])+'</details></article>'
 if it['category']=='公式间距':
  c=f'<article class="change spacing" id="{e(id)}" data-category="公式间距"><div class="eyebrow">{e(id)} · 公式间距 · {e(it["near_label"])}</div><h3>{e(it["title"])}</h3><p class="location">{e(source_lines)}</p><p><b>修改前：</b><code>{e(it["old"])}</code><br><b>修改后：</b><code>{e(it["new"])}</code></p><p><b>理由：</b>{e(it["why"])} <b>回退：</b>{e(it["rollback"])} <b>依据：</b>两版该行差异及上轮PDF视觉检查；关联“公式与分页”。</p>'+primary_control+'<details class="source"><summary>查看该行完整源码对照</summary>'+rawpair(it['old'],it['new'])+'</details></article>'
 cards.append(c)

index='<div class="index">'+''.join(f'<a href="#{it["id"]}">{it["id"]} · {e(it["title"])}</a>' for it in items)+'</div>'
filetable='<div class="table-wrap"><table><thead><tr><th>文件</th><th>变化</th><th>对象</th><th>为什么这样处理 / 回退影响</th></tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{e(r[k])}</td>' for k in ['path','status','kind','why'])+'</tr>' for r in inventory)+'</tbody></table></div>'
scope_path=lambda p:'<code>'+e(str(p))+'</code>'
style=r'''
:root{--ink:#162b3c;--muted:#536676;--line:#dbe4eb;--blue:#1c617e;--cream:#f7f5ef}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f1f4f6;color:var(--ink);font:16px/1.7 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}main{max-width:1220px;margin:auto;padding:36px 30px 80px}header{background:#113c50;color:#fff;padding:40px;border-radius:18px}h1{font-size:34px;line-height:1.35;margin:10px 0 20px}h2{font-size:26px;margin:0 0 18px}h3{font-size:21px;line-height:1.5;margin:4px 0 10px}h4{font-size:17px;margin:18px 0 8px}h5{font-size:16px;margin:0 0 10px}p{margin:10px 0}b{font-weight:700}a{color:#126181;text-decoration:underline;text-underline-offset:3px}header a{color:#d4f6ff}code{font-family:Consolas,monospace;font-size:.9em;overflow-wrap:anywhere}section.panel{background:white;padding:30px;border:1px solid var(--line);border-radius:14px;margin-top:24px}nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}nav a{padding:5px 14px;background:#e7f2f6;border-radius:20px;text-decoration:none}.lead{font-size:18px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:24px}.stat{background:#f2f7f8;padding:18px;border-radius:12px}.stat strong{display:block;font-size:29px;color:#165370}.stat span{font-size:14px}.notice{background:#fff5df;border-left:4px solid #c99634;padding:16px 20px;margin:18px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}.pair>div{min-width:0;padding:16px;border-radius:8px}.before{background:#fff3eb}.after{background:#eaf5f3}.pair b{font-size:14px;letter-spacing:.02em}.exact pre{background:transparent;padding:8px 0;margin:0}.change{background:white;border:1px solid var(--line);border-radius:12px;padding:28px;margin:22px 0;scroll-margin-top:18px;overflow-wrap:anywhere}.eyebrow{font-size:13px;color:#476a7f}.location,.muted{font-size:14px;color:var(--muted)}.rollback{background:#f6f4eb;padding:15px 18px;border-left:3px solid #b69748;margin:16px 0}.decision{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:12px;background:#f1f5f8;border-radius:8px;margin:10px 0}.decision label{display:flex;gap:10px;align-items:center;font-size:14px}.decision input{flex:1;min-width:190px}.decision select{width:100px}.decision select,.decision input,.controls select,.controls input,button{font:inherit;border:1px solid #afc3d0;border-radius:7px;padding:8px 10px;color:var(--ink);background:white}.subpoints{border-top:1px dashed #bfcdd6;margin-top:22px}.subpoint{border:1px solid #dce6ec;padding:20px;margin:16px 0;border-radius:10px;scroll-margin-top:16px}.subpoint .pair{margin:8px 0}.subpoint .pair>div{padding:10px 14px}.subpoint .pair p{margin:4px 0}.subpoint p{font-size:14px}.source{margin:16px 0 0;border-top:1px solid var(--line);padding-top:12px}summary{cursor:pointer;font-weight:700;color:#246681}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;font:13px/1.75 Consolas,"Microsoft YaHei",monospace;background:#f6f8fa;padding:14px;max-width:100%}.figure-comparison img{width:100%;height:auto;display:block;background:white;margin-top:14px}.figure-comparison .pair{align-items:start}.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0}.controls input[type=search]{flex:1;min-width:200px}.controls button{cursor:pointer;background:#14536d;color:white}.controls label{font-size:14px}.index{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px}.index a{font-size:14px;padding:4px 0;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:11px 12px;border:1px solid #dce5eb;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf3f7}td:first-child{min-width:200px;max-width:300px}.table-wrap{overflow:auto}#decision-status{font-size:14px;color:#2c637c}.hidden{display:none!important}.footer{color:var(--muted);font-size:14px}.priority li{margin:14px 0}.pill{font-size:12px;padding:3px 8px;background:#ecf3f6;border-radius:10px}.section-summary{color:#46616f;font-size:15px;border-top:1px solid var(--line);padding-top:14px}ul,ol{padding-left:25px}.print-note{display:none}
.spacing h3{font-size:18px}.spacing p{font-size:14px}.spacing{padding:20px 26px}@media(max-width:700px){main{padding:16px 12px 50px}header{padding:25px 22px}h1{font-size:27px}h2{font-size:23px}section.panel,.change{padding:21px 18px}.pair{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.stat{padding:12px}.index{grid-template-columns:1fr}.decision{gap:8px}.decision input{min-width:0;flex-basis:100%;width:100%}.subpoint{padding:14px}.controls>*{max-width:100%}}
@media print{.entry-head{break-inside:avoid}.pair:not(.exact){break-inside:avoid}.spacing{padding:3mm 0;margin:3mm 0;break-inside:avoid}.spacing h3{font-size:11pt}.spacing p{font-size:9pt;margin:1.5mm 0}.spacing .location{font-size:8pt}}@page{size:A4;margin:16mm 14mm 17mm}@media print{html{scroll-behavior:auto}body{background:white;font-size:10pt;line-height:1.55;color:#142d3a}main{max-width:none;padding:0}header{padding:7mm;border-radius:0;background:#eaf2f5;color:#142d3a}h1{font-size:23pt}h2{font-size:17pt}h3{font-size:14pt}h4,h5{font-size:11pt}h1,h2,h3,h4,h5,summary{break-after:avoid}p{orphans:3;widows:3}section.panel{padding:6mm 0;border:0;margin-top:6mm}.change{padding:5mm 0;margin:4mm 0;border:0;border-top:1px solid #cad8e0;border-radius:0}.pair{gap:3mm;grid-template-columns:1fr 1fr}.pair>div{padding:3mm}.eyebrow,.location,.muted,.footer,.subpoint p{font-size:9pt}.subpoint{padding:3mm;margin:3mm 0;break-inside:avoid}.source{display:none!important}.print-source .source{display:block!important}.source pre{font-size:8pt;line-height:1.5}.exact{display:block}.exact>div{margin-top:3mm}.decision{display:none!important}nav,.controls,#decision-status,#index-panel,#filter-result,.screen-only{display:none!important}.hidden{display:block!important}.stats{gap:3mm}.stat{padding:3mm}.stat strong{font-size:20pt}.stat span{font-size:9pt}.rollback{padding:3mm;margin:3mm 0;break-inside:avoid}.figure-comparison .pair{display:block}.figure-comparison .pair>div{break-inside:avoid;max-width:155mm;margin:3mm auto}.figure-comparison img{max-height:155mm;width:auto;max-width:100%;margin-left:auto;margin-right:auto}table{font-size:8pt;table-layout:fixed}td:first-child{min-width:0;max-width:none}tr{break-inside:avoid}th,td{padding:2mm}.table-wrap{overflow:visible}.print-note{display:block}.notice{break-inside:avoid}.priority li{margin:3mm 0}a{color:inherit;text-decoration:none}}
'''
body=f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RTHS论文全文修改逐项对照与回退决策汇报</title><style>{style}</style></head><body><main>
<header><div class="eyebrow" style="color:inherit">Doctor Bego · RTHS（实时混合试验）论文 · 2026年9月6日</div><h1>全文修改逐项对照<br>与回退决策汇报</h1><p class="lead">这份报告把上轮改稿逐项摊开：原来写什么、现在写什么、为什么改，以及回退时要同步处理什么。包含全部104个主稿源码差异块、30个表3—表5改值单元格、表1的2个改值单元格、4张图件替换、2条重复文献删除及新增附件。您可以逐项标记“保留 / 回退 / 另改”，再导出意见。本轮只整理报告，没有改稿或执行回退。</p><p>最需要优先判断的是建模路线和贡献表达：部分修改是经过复算的纠错，部分是我上轮选择的建模解释、内容删减与画法，并非必须整体接受。</p></header>
<nav><a href="#priority">先看关键选择</a><a href="#scope">比较对象与依据</a><a href="#concepts">必要概念</a><a href="#index-panel">全部修改目录</a><a href="#changes">逐项对照</a><a href="#files">文件增删清单</a><a href="#next">回退流程与验收</a></nav>
<section class="panel" id="priority"><h2>先决定这些，能避免反复改稿</h2><div class="stats"><div class="stat"><strong>104</strong><span>主稿差异块，全部列出</span></div><div class="stat"><strong>30 + 2</strong><span>三表30格 + 材料表2格改值</span></div><div class="stat"><strong>4</strong><span>示意图替换，原图新图可对照</span></div><div class="stat"><strong>42</strong><span>公式间距修改，逐处可决定</span></div></div>
<ol class="priority"><li><b>论文要采用哪一条模型路线？</b>旧稿写的是两子结构分别缩聚后装配，当前响应图实际使用一次整体缩聚。修订稿选择了把实际实现写清楚，还披露Guyan质量/阻尼采用保留方程的单侧处理。这个选择会改变论文的论证范围；另一条路是修正计算实现并重算图表。重点看 <a href="#修改060">单一整体恢复</a>、<a href="#修改062">表2整体替换</a>、<a href="#修改063">6/9与5/8及Guyan实现说明</a>。</li>
<li><b>新增的界面边界条件是否符合您的研究对象？</b>“释放而未作动的界面相互作用力为零”是我为补全原文作出的具体建模选择，当前整体响应计算没有验证这条边界条件。见 <a href="#修改018">新增界面力条件</a>。</li>
<li><b>反馈系统按力反馈解释是否正确？</b>我选择让文字与已有特征式一致，写成数值状态产生LQR力并经过通道时滞。若真实对象是位移跟踪或实测反馈，应联动修改图、信号说明和方程。见 <a href="#修改032">信号来源</a>、<a href="#修改033">框图</a>、<a href="#修改045">施加力公式</a>。</li>
<li><b>摘要、贡献段和结论收缩得是否过多？</b>旧数值和未经支持的排序确实需要纠正；删去大量机制解释、压缩贡献定位、删除末句范围条件，是可重新选择的编辑动作。可恢复原来的组织与有依据的解释。见 <a href="#修改005">摘要</a>、<a href="#修改006">引言贡献</a>、<a href="#修改101">结果讨论删段</a>、<a href="#修改104">结论末段</a>。</li>
<li><b>是否保留简化重画的图？</b>统一英文并不要求删除截面详图或原坐标说明。新几何图还把柱脚画成全固定以匹配当前精度矩阵。可以恢复信息量和画风；支座与模型选择需要一致。见 <a href="#修改052">几何与截面</a>、<a href="#修改054">自由度图</a>、<a href="#修改061">两类划分图</a>。</li></ol><p class="section-summary">数值纠错、建模选择和文字压缩可以拆开处理；不必为了保留正确数值而接受整段新写法。</p></section>
<section class="panel" id="scope"><h2>比较对象、证据与完成边界</h2><p><b>修改前：</b>{scope_path(FROZEN)}。这是上轮改稿前冻结的完整原文，SHA-256为 <code>{sha(FROZEN)}</code>，与上轮来源清单一致。</p><p><b>修改后：</b>{scope_path(REV/'main.tex')}，SHA-256为 <code>{sha(REV/'main.tex')}</code>。本报告使用上轮交付的29页PDF及配套文件。</p><div class="notice"><b>为什么不直接用原路径做“修改前”：</b>本次开始时，{scope_path(OLD/'main.tex')} 的摘要已与冻结原稿不同。若直接比较会漏掉摘要修改。报告采用冻结快照；原路径当前状态另有本轮开始时的哈希记录。这里仅记录可核查的差异，不判断修改者。</div>
<p><b>数值依据：</b>当前出图设置核查中，四套时程与图用数据的最大差为4.973799150320701×10⁻¹⁴ mm；44个表格指标的MATLAB/Python独立复算最大差为2.490452288839151×10⁻¹²。原表3有5/16格不符、表4有21/24格不符、表5有4/4格不符，共30格改值。表3—表5公式的数学主体没有在本轮被替换；补充了计算约定并改变了指标解释。</p>
<p><b>完成情况：</b>上轮完成改稿、编译及29页视觉检查；本轮完成差异清点、原新对照和回退意见入口。<b>尚未完成：</b>当前精度模型与历史稳定域的生成模型唯一匹配、部分界面分开装配的计算验证，以及您对新增建模选择的接受。已有验证不等于这些科学问题已经闭合。</p>
<details><summary>主要证据文件，供追溯</summary><ul><li>{scope_path(REV/'revision_evidence/main.diff')}：上轮完整主稿差异。</li><li>{scope_path(REV/'revision_evidence/table345_verified_values.json')}：44格核查值与原表值。</li><li>{scope_path(REV/'revision_evidence/additional_metrics.json')}：中层误差、峰值时间及末段幅值比。</li><li>{scope_path(REV/'revision_evidence/validation.json')}：上轮逐项验证记录。</li><li>{scope_path(REV/'revision_evidence/source_hashes.json')} 与 {scope_path(REV/'revision_evidence/delivery_hashes.json')}：两版文件清单。</li><li>{scope_path(ROOT/'figure/表3至表5_按当前出图设置核查_20260906')}：此前表格复算与独立核查证据。</li></ul></details><p class="section-summary">本报告回答“上轮到底改了什么”，并把已经证实的纠错与仍需您决定的研究选择分开呈现。</p></section>
<section class="panel" id="concepts"><h2>读清单前需要的几个概念</h2><ul><li><b>整体缩聚：</b>直接把完整15自由度模型减少成较小模型。<b>子结构分别缩聚再装配：</b>先把物理侧、数值侧各自缩小，再连接两侧共同保留的接口；两者不是同一个计算过程。</li><li><b>第一类划分（Division I）：</b>物理区域为外侧跨下部两层，两个作动点为首层ψ1和中层ψ6；当前精度模型Guyan有6个坐标，Craig–Bampton有9个。<b>第二类划分（Division II）：</b>物理区域为外侧跨三层，作动点为首层ψ1和顶层ψ11；当前两种精度模型分别有5个和8个坐标。</li><li><b>Guyan：</b>用静力关系恢复被消去的坐标。<b>Craig–Bampton：</b>在静力关系之外保留内部振动模态；当前每个全局模型额外保留3个模态坐标。</li><li><b>MAC（Modal Assurance Criterion，模态置信准则）：</b>比较振型方向是否接近；这里使用共同保留坐标的欧氏形式，数值受平移与转角的尺度约定影响。<b>NRMSE（Normalized Root Mean Square Error，归一化均方根误差）：</b>比较整段响应误差，以全记录峰峰值作归一化尺度；本稿以百分数报告。</li><li><b>LQR（Linear Quadratic Regulator，线性二次调节器）：</b>根据状态计算反馈力。<b>CR积分：</b>Chen–Ricles时间积分算法，用于所述离散稳定性公式；当前精度响应实际使用RK4（四阶Runge–Kutta积分）。</li><li><b>有符号模态份额指标：</b>比较作动坐标在前5阶模态中的质量加权份额变化，可以为负；它不是直接的能量转移量，也没有在当前材料中建立通用的稳定域预测关系。</li><li><b>差异块与子项：</b>一个源码差异块可能是一整段替换。下方把需要独立决定的子项另外列出；“修改005”等编号只用于定位，后面总带具体对象。</li></ul></section>
<section class="panel" id="index-panel"><h2>全部修改目录</h2><p>按原稿出现顺序排列；42处公式间距也逐条列出。可通过下方检索直接查某个词、数值或章节。</p><details><summary>展开全部 {len(items)} 个主条目（含文献与附件）</summary>{index}</details></section>
<section class="panel" id="changes"><h2>逐项原文—新文—理由—回退影响</h2><p>每项默认显示中文原意与新意，点击“完整原文与新文”可查看未截断的英文/LaTeX。两栏中的原文保留源文件写法，包括标红命令；没有把未改的上下文藏进一句概括。</p><p class="screen-only">决定保存在当前浏览器本地。<b>请用“导出回退意见”保存文件</b>，换目录或浏览器后本地记录可能不可用。导出文件只记录您的选择；论文不会自动变化。</p><div class="controls"><input id="search" type="search" placeholder="检索全文：摘要、界面力、0.138、修改018……" aria-label="检索全部修改"><select id="category" aria-label="类别筛选"><option value="">全部类别</option>{''.join('<option>'+e(x)+'</option>' for x in sorted(set(i['category'] for i in items)))}</select><select id="chosen" aria-label="决定筛选"><option value="">全部决定</option><option>待决定</option><option>保留</option><option>回退</option><option>另改</option></select><button id="expand">展开全部原文</button><button id="collapse">收起全部原文</button><button id="export">导出回退意见</button></div><div class="controls"><label><input type="checkbox" id="include-source"> 打印时包含完整英文/LaTeX源码（篇幅较长）</label><button id="print">打印 / 保存PDF</button></div><p id="filter-result" aria-live="polite"></p><p id="decision-status" aria-live="polite"></p><p class="print-note">本打印版默认保留所有中文逐项对照和图件；完整英文/LaTeX原文可在同名HTML中展开查看，或勾选“打印时包含完整源码”后重新打印。</p></section>
<div id="change-list">{''.join(cards)}</div>
<section class="panel" id="files"><h2>文件层面的全部增删与替换</h2><p>以下按上轮31项来源文件与44项交付清单比对，共{len(inventory)}条路径。只在原目录的文件没有被物理删除。此表包含未变文件以便核对遗漏；本次新增报告文件另列于本轮验收清单，不混入上轮改稿范围。</p>{filetable}<p>五份响应/稳定域PDF图件原样复制，文件名仍含fig06—fig10；论文实际排版编号为图5—图9。题目、作者信息、关键词与其余未列入差异的正文未改。新增图件使用四个TikZ文件，旧目录的七张PNG仍保留，其中两张原本未被主稿引用。</p><p class="section-summary">回退正文与图件后应重新编译生成PDF和辅助文件；重新编译产生的文件变化不应被误当成新的科学改动。</p></section>
<section class="panel" id="next"><h2>您选好之后，如何做局部回退</h2><ol><li><b>先给出意见：</b>在每项或其子项选择保留、回退或另改，备注您希望恢复的具体句式/图形信息。导出文件会保留条目标题、关联内容和比较基准。</li><li><b>形成可审阅的改稿范围：</b>根据您的选择，列出需要联动的摘要、表格、模型说明、图注和结论。存在整段与子项冲突时，以您明确的细项意见为依据，不能机械整段还原。</li><li><b>在新副本中实施：</b>确定版本名称后复制修订稿；按选择回退，保留当前两版和冻结原文。模型路线变化时，先对齐计算设置并重算相关图表。</li><li><b>验收后交付：</b>英文CAS稿实际运行pdfLaTeX → BibTeX → pdfLaTeX两次；检查引用、公式、图表编号和页面。数值修改逐项对照对应证据；与旧版本做新差异清单，确保只改了您选定及必要联动的内容。</li></ol><p><b>当前不需要您补材料。</b>您现在只需审阅这份报告并指出希望回退或另改的项。本报告没有把任何建议当作您的批准，也没有启动新的计算或外部评审。</p></section>
<p class="footer">报告生成与核验：全部104个差异块前向重建修订稿、反向重建冻结原稿均逐行一致；原文/新文原样内嵌。浏览器、打印和本轮文件保护的实际验收结果保存在 revision_evidence/逐项修改报告/ 中。</p>
</main>'''
data={'scope':'上轮全部稿件修改的逐项对照；本轮只生成报告，不实施回退','before_path':str(FROZEN),'before_sha256':sha(FROZEN),'after_path':str(REV/'main.tex'),'after_sha256':sha(REV/'main.tex'),'main_diff_blocks':104,'changed_table345_cells':30,'items':items,'file_inventory':inventory,'decisions':decision_meta}
js=r'''
const catalog=__CATALOG__;
const key='rhts-revision-decisions-'+catalog.after_sha256;
let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
const nodes=[...document.querySelectorAll('.decision')], cards=[...document.querySelectorAll('.change')];
for(const node of nodes){const value=saved[node.dataset.id]||{};node.querySelector('select').value=value.choice||'待决定';node.querySelector('input').value=value.note||'';for(const field of node.querySelectorAll('input,select'))field.addEventListener('input',()=>{save();filter()})}
function read(){return Object.fromEntries(nodes.map(n=>[n.dataset.id,{choice:n.querySelector('select').value,note:n.querySelector('input').value}]))}
function status(){const vals=Object.values(read()),n=vals.filter(v=>v.choice!=='待决定'||v.note).length;document.getElementById('decision-status').textContent='共 '+nodes.length+' 个决定入口（含整段与子项）；已填写 '+n+' 个。整段与子项均会导出，不自动执行回退。'}
function save(){try{localStorage.setItem(key,JSON.stringify(read()))}catch(e){document.getElementById('decision-status').textContent='浏览器未提供本地保存，请及时导出。';return}status()}
const search=document.getElementById('search'),category=document.getElementById('category'),chosen=document.getElementById('chosen');
function filter(){const q=search.value.trim().toLowerCase(),cat=category.value,ch=chosen.value;let shown=0;for(const c of cards){const choices=[...c.querySelectorAll('.decision select')].map(s=>s.value);const yes=(!q||c.textContent.toLowerCase().includes(q))&&(!cat||c.dataset.category===cat)&&(!ch||choices.includes(ch));c.classList.toggle('hidden',!yes);shown+=yes}document.getElementById('filter-result').textContent='当前显示 '+shown+' / '+cards.length+' 个主条目。'}
for(const el of [search,category,chosen])el.addEventListener('input',filter);
document.getElementById('expand').onclick=()=>document.querySelectorAll('.change:not(.hidden) details.source').forEach(d=>d.open=true);
document.getElementById('collapse').onclick=()=>document.querySelectorAll('.source').forEach(d=>d.open=false);
document.getElementById('export').onclick=()=>{const values=read();const payload={report:'全文修改逐项对照与回退决策汇报',created_at:new Date().toISOString(),before_path:catalog.before_path,before_sha256:catalog.before_sha256,after_path:catalog.after_path,after_sha256:catalog.after_sha256,execution:'仅导出意见，未执行任何稿件修改',decisions:catalog.decisions.map(d=>({...d,...values[d.id]}))};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='RTHS论文_逐项回退意见.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
document.getElementById('include-source').onchange=e=>document.body.classList.toggle('print-source',e.target.checked);
document.getElementById('print').onclick=()=>window.print();
window.addEventListener('beforeprint',()=>document.querySelectorAll('.source').forEach(d=>{d.dataset.wasOpen=String(d.open);d.open=true}));
window.addEventListener('afterprint',()=>document.querySelectorAll('.source').forEach(d=>{d.open=d.dataset.wasOpen==='true'}));
document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(!a)return;const t=document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));if(!t)return;const card=t.closest('.change');if(card&&card.classList.contains('hidden')){search.value='';category.value='';chosen.value='';filter()}});
status();filter();
'''.replace('__CATALOG__',json.dumps({k:data[k] for k in ['before_path','before_sha256','after_path','after_sha256','decisions']},ensure_ascii=False).replace('</',r'<\/'))
REPORT.write_text(body+'<script>'+js+'</script></body></html>',encoding='utf-8')
(OUT/'全部修改清单.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'全部修改清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['编号','对象','类别','修改前','修改后','为什么改','依据','回退建议','回退影响','关联内容'])
 for it in items:
  w.writerow([it['id'],it['title'],it['category'],it['old'],it['new'],it['why'],it['source'],it['recommendation'],it['rollback'],' / '.join(it['groups'])])
  for s in it['subpoints']:w.writerow([s['id'],s['title'],it['category'],s['old_meaning'],s['new_meaning'],s['why'],it['source'],it['recommendation'],it['rollback'],' / '.join(it['groups'])])
(OUT/'main_全部104项.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='冻结原稿/main.tex',tofile='上轮修订稿/main.tex')),encoding='utf-8')
(OUT/'references_两处删除.diff').write_text(''.join(difflib.unified_diff(oldbib.splitlines(True),newbib.splitlines(True),fromfile='原稿/references.bib',tofile='修订稿/references.bib')),encoding='utf-8')
checks={'main_hunks':len(H),'main_hunks_covered':len([x for x in items if 'n'in x]),'forward_rebuild':'PASS','reverse_rebuild':'PASS','roundtrip_scope':'完整文本逐行含空白，行尾编码差异不计入语义diff；两版原始字节另以SHA256冻结','table345_changed_cells':len(changed),'table345_cell_records':sum('cell_record_id'in s for it in items for s in it['subpoints']),'spacing_items':sum(i['category']=='公式间距' for i in items),'primary_items':len(items),'decision_entries':len(decision_meta),'file_inventory':len(inventory),'inventory_counts':dict(Counter(r['status'] for r in inventory)),'inline_images':body.count('data:image/png;base64,'),'before_sha256':sha(FROZEN),'after_sha256':sha(REV/'main.tex')}
(OUT/'coverage_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
for fname in ['build_report.py','catalog.py','hunks.json','turn_start_hashes.json']:shutil.copy2(TMP/fname,OUT/fname)
print(json.dumps({'report':str(REPORT),'bytes':REPORT.stat().st_size,'checks':checks},ensure_ascii=False,indent=2))
