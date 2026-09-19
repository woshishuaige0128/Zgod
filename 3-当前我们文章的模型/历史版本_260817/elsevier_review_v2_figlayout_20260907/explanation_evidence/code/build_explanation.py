from pathlib import Path
import json, base64, shutil, html, hashlib

TMP=Path(__file__).resolve().parent
ROOT=TMP.parents[1]
NEW=ROOT.parent/'260817/elsevier_review_v2_figlayout_20260907'
SOURCE=ROOT.parent/'260817/elsevier_review_v2_20260907'
if TMP.name=='code' and TMP.parent.name=='explanation_evidence':
    NEW=TMP.parents[1]; SOURCE=NEW.parent/'elsevier_review_v2_20260907'
D=json.loads((NEW/'explanation_evidence/data/explanation_calculations.json').read_text(encoding='utf-8'))
models={(m['division'],m['method']):m for m in D['models']}
def num(x,n=6): return f'{x:.{n}f}'
def signed(x,n=4): return f'{x:+.{n}f}'
def pct(x,n=4): return num(x*100,n)+'%'
def image(name,source=NEW):
    return 'data:image/png;base64,'+base64.b64encode((source/'submit_figure'/name).read_bytes()).decode()
if not (NEW/'submit_figure/fig16_modal_shares.png').exists():
    shutil.copy2(SOURCE/'submit_figure/fig16_modal_shares.png',NEW/'submit_figure/fig16_modal_shares.png')
full=models[2,'Full']; guyan=models[2,'Guyan']; cb=models[2,'CB']
first=next(x for x in D['actuator_contributions'] if x['division']==2 and x['method']=='Guyan')
gdrift=next(x for x in D['drifts'] if x['division']==2 and x['excitation']=='chirp' and x['method']=='Guyan' and x['storey']==3)
fdrift=next(x for x in D['drifts'] if x['division']==2 and x['excitation']=='chirp' and x['method']=='Full' and x['storey']==3)
cdrift=next(x for x in D['drifts'] if x['division']==2 and x['excitation']=='chirp' and x['method']=='CB' and x['storey']==3)

drift_rows=''
for div in [1,2]:
 for exc in ['eq','chirp']:
  for floor in [1,2,3]:
   values=[next(x['peak_drift_percent'] for x in D['drifts'] if (x['division'],x['excitation'],x['method'],x['storey'])==(div,exc,method,floor)) for method in ['Full','Guyan','CB']]
   drift_rows+=f'<tr><td>划分{"I"*div} · {"地震" if exc=="eq" else "扫频"}</td><td>第{floor}层</td>'+''.join(f'<td>{num(v,6)}</td>' for v in values)+'</tr>'
contrib_rows=''
for c in D['actuator_contributions']:
 for k,j in enumerate(c['actuated_dofs']):
  contrib_rows+=f'<tr><td>划分{"I"*c["division"]}</td><td>{"Craig–Bampton" if c["method"]=="CB" else c["method"]}</td><td>ψ<sub>{j}</sub></td><td>{num(c["full_shares"][k])}</td><td>{num(c["reduced_shares"][k])}</td><td>{signed(c["relative_changes"][k],6)}</td><td>{signed(c["relative_changes"][k]*100,4)}%</td></tr>'
delta_rows=''.join(f'<tr><td>划分{"I"*c["division"]}</td><td>{"Craig–Bampton" if c["method"]=="CB" else c["method"]}</td><td>{signed(c["relative_changes"][0],6)} {signed(c["relative_changes"][1],6)}</td><td>{signed(c["delta_E"],6)}</td></tr>' for c in D['actuator_contributions'])
share_tables=''
for div in [1,2]:
 rows=''
 for j in range(1,16):
  label={1:'首层水平平动',6:'中层水平平动',11:'顶层水平平动'}.get(j,'节点'+str(j-1 if j<6 else j-2 if j<11 else j-3)+'转动')
  # Node IDs of the twelve rotation coordinates are 5--16 in floor order.
  if j not in [1,6,11]:label='节点'+str(5+[x for x in range(1,16) if x not in [1,6,11]].index(j))+'转动'
  rows+=f'<tr><td>ψ<sub>{j}</sub> · {label}</td>'+''.join(f'<td>{num(models[div,m]["shares"][j-1],6)}</td>' for m in ['Full','Guyan','CB'])+'</tr>'
 share_tables+=f'<h3>划分{"I"*div}：图15左图的全部15个点</h3><div class="table-wrap"><table><thead><tr><th>物理坐标</th><th>完整模型</th><th>Guyan</th><th>Craig–Bampton</th></tr></thead><tbody>{rows}</tbody><tfoot><tr><td>15个坐标之和</td><td>1.000000</td><td>1.000000</td><td>1.000000</td></tr></tfoot></table></div>'

template=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>图13与图15读图及计算讲解汇报</title>
<style>
:root{--ink:#172c3c;--muted:#526675;--blue:#4477aa;--red:#c74359;--line:#d9e1e6;--paper:#fff;--soft:#f1f5f7;--gold:#916207}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eaf0f3;color:var(--ink);font:17px/1.8 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}main{max-width:1150px;margin:auto;background:var(--paper);padding:48px 58px 80px}header{padding-bottom:25px;border-bottom:3px solid var(--ink)}.eyebrow{font-size:13px;letter-spacing:2px;color:var(--muted)}h1{font-size:36px;line-height:1.35;margin:14px 0 20px}h2{font-size:27px;line-height:1.5;margin:0 0 20px}h3{font-size:20px;line-height:1.5;margin:24px 0 12px}p{margin:10px 0 17px}strong{font-weight:700}a{color:#245d87;text-underline-offset:4px}nav{display:flex;gap:8px 22px;flex-wrap:wrap;padding:22px 0}nav a{font-size:15px}section{padding-top:40px;margin-top:10px;border-top:1px solid var(--line);scroll-margin-top:16px}.lead{font-size:20px;line-height:1.75}.muted,figcaption{color:var(--muted);font-size:14px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}.card{padding:20px 24px;background:var(--soft);border-radius:12px}.card p:last-child{margin-bottom:0}.card h3{margin-top:0}.big{display:block;font-size:28px;font-weight:700;line-height:1.3;margin:6px 0}.callout{border-left:4px solid var(--blue);background:#eef4fa;padding:17px 23px;margin:22px 0}.callout.gold{border-color:var(--gold);background:#faf4e7}.callout p:last-child{margin-bottom:0}.equation{font-family:"Cambria Math",Cambria,"Microsoft YaHei",serif;font-size:22px;text-align:center;padding:18px 12px;margin:16px 0;background:#f7f8fa;border:1px solid var(--line);border-radius:8px;overflow-x:auto;line-height:2.1}.frac{display:inline-flex;flex-direction:column;vertical-align:middle;line-height:1.6;text-align:center;margin:0 5px}.frac>span:first-child{border-bottom:1px solid}.frac>span{padding:0 7px}.eq-note{font-size:15px;color:var(--muted)}figure{margin:22px 0;padding:0;break-inside:avoid}figure img{display:block;width:100%;height:auto}figure svg{width:100%;height:auto;display:block}figcaption{margin-top:12px;line-height:1.6}.table-wrap{overflow-x:auto;margin:16px 0 20px}table{width:100%;border-collapse:collapse;font-size:14px;white-space:nowrap;font-variant-numeric:tabular-nums}th,td{padding:9px 11px;text-align:right;border-bottom:1px solid var(--line)}th:first-child,td:first-child{text-align:left}thead th{color:var(--muted);border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);font-weight:600}tfoot td{border-bottom:2px solid var(--ink);font-weight:700}tbody tr:nth-child(even){background:#f8fafb}.selector{display:flex;flex-wrap:wrap;gap:14px;margin:16px 0}label{display:flex;flex-direction:column;gap:5px;font-size:14px;color:var(--muted)}select{font:inherit;font-size:16px;color:var(--ink);padding:9px 30px 9px 12px;border:1px solid #9bacb8;border-radius:7px;background:white;max-width:100%}button{font:inherit;font-size:14px;color:var(--ink);padding:8px 15px;border:1px solid #9bacb8;border-radius:7px;background:white;cursor:pointer}.demo{padding:20px 24px;border:1px solid #aabfcd;border-radius:12px;margin:24px 0}.output{background:#f3f7fa;padding:17px 20px;margin-top:18px;border-radius:8px}.output p:last-child{margin-bottom:0}.value-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.value-grid>div{padding:14px;background:white;border:1px solid var(--line);border-radius:8px}.value-grid small{display:block;font-size:13px;color:var(--muted)}.value-grid b{font-size:23px;font-variant-numeric:tabular-nums}details{border-top:1px solid var(--line);margin-top:16px;padding-top:12px}summary{cursor:pointer;color:#245d87;font-weight:700}code{font-size:13px;overflow-wrap:anywhere;white-space:normal}ol{padding-left:25px}li{margin:10px 0}.method-full{color:#555}.method-guyan{color:var(--blue)}.method-cb{color:var(--red)}.endnote{padding-top:26px;margin-top:40px;border-top:2px solid var(--ink);font-size:14px;color:var(--muted)}.formula-line{display:block}.print-only{display:none}
@media(max-width:700px){body{font-size:16px}main{padding:25px 20px 45px}h1{font-size:29px}h2{font-size:23px}.lead{font-size:18px}.cards,.value-grid{grid-template-columns:1fr}.card,.demo{padding:17px}.equation{font-size:18px}.wide-diagram{overflow-x:auto}.wide-diagram svg{min-width:630px}.selector label{max-width:100%}section{padding-top:28px}.big{font-size:25px}table{font-size:13px}th,td{padding:8px}nav{gap:8px 17px}}
@media print{@page{size:A4;margin:15mm 14mm}body{background:white;font-size:10pt;line-height:1.65}main{max-width:none;padding:0}header{padding-bottom:12px}h1{font-size:23pt}h2{font-size:17pt}h3{font-size:12pt}.lead{font-size:12pt}nav,.no-print{display:none}section{break-before:page;margin:0;padding-top:0;border:0}h2,h3,summary{break-after:avoid}p,li{orphans:3;widows:3}.card,.callout,.equation,.demo,.output,.value-grid,figure{break-inside:avoid}.cards{gap:10px;margin:12px 0}.card{padding:12px 15px}.big{font-size:19pt}.equation{font-size:14pt;margin:10px 0;padding:10px}.callout{padding:12px 17px;margin:13px 0}.demo{padding:13px 16px;margin:14px 0}.table-wrap{overflow:visible;margin:12px 0}table{font-size:8.4pt}th,td{padding:5px 6px}tr{break-inside:avoid}figure{margin:15px 0}figcaption,.muted,.eq-note{font-size:8.5pt}.selector{display:none}.output{padding:12px}.value-grid b{font-size:16pt}.print-only{display:block}.endnote{margin-top:20px;padding-top:15px;font-size:8pt}details:not([open])>summary{display:none}details{border:0}.wide-diagram svg{min-width:0}a{color:inherit;text-decoration:none}}
@media print{.endnote{display:none}.table-wrap{break-inside:avoid}#drift-example figure{margin:10px 0}#drift-example p{margin:8px 0;line-height:1.55}#drift-example .demo{margin:10px 0;padding:10px 12px}#drift-example .demo h3{margin:0 0 8px}#drift-example .output{margin-top:8px;padding:9px 12px}#drift-example .value-grid>div{padding:8px}}
</style></head><body><main>
<header><div class="eyebrow">RHTS · 读图与真实数值演算 · 2026-09-07</div><h1>图13看相邻楼层的变形<br>图15看模态份额如何改变</h1>
<p class="lead">Doctor Bego，图6与图13已改成<strong>一行四张竖长子图</strong>。本报告把图13的每一个峰值、图15的每一个点和每一根柱子，连接到具体坐标、公式和真实输入数据。</p>
<div class="cards"><div class="card"><h3>图13回答</h3><span class="big">层与层之间，最大错开多少？</span><p>用相邻楼层在<strong>同一时刻</strong>的位移差除以层高，检查缩聚模型是否保留层间变形。</p></div><div class="card"><h3>图15回答</h3><span class="big">低阶模态的份额，分布在哪里？</span><p>左图给15个坐标的份额；右图给两个作动坐标相对完整模型的变化率。</p></div></div>
<p class="muted">状态：两图重排、144项独立数值核对和38页论文编译已通过。本报告供读图与审阅；您无需提供新数据。本轮解释沿用已核验的完整框架响应模型。</p></header>
<nav aria-label="报告目录"><a href="#figure13">图13怎么读</a><a href="#drift-example">层间角怎么算</a><a href="#figure15">图15四个面板</a><a href="#coordinates">15个坐标是什么</a><a href="#modal-calculation">左图数字怎么算</a><a href="#bar-calculation">右图与表5怎么算</a><a href="#meaning">两图能说明什么</a><a href="#layout">布局与验收依据</a></nav>

<section id="figure13"><h2>图13：横坐标是最大层间位移角，纵坐标是楼层</h2>
<figure><img src="@@FIG13@@" alt="更新后的图13，一行四个子图：划分I地震、划分II地震、划分I扫频、划分II扫频。三条曲线比较完整模型、Guyan及Craig–Bampton的三层峰值层间位移角。"><figcaption>图13，论文第31页。Full order（灰色圆点）是完整模型参照；Guyan（蓝色三角）是静力缩聚；Craig–Bampton（红色方点）在缩聚中保留内部模态动力学。红灰接近表示该指标接近完整模型。</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>子图</th><th>结构划分</th><th>输入激励</th><th>读图顺序</th></tr></thead><tbody><tr><td>(a)</td><td>划分I</td><td>El Centro地震记录</td><td>看三层的三种方法是否重合</td></tr><tr><td>(b)</td><td>划分II</td><td>El Centro地震记录</td><td>与(a)比较划分变化的影响</td></tr><tr><td>(c)</td><td>划分I</td><td>Chirp，频率随时间增加的扫频</td><td>看扫频下的层间变形</td></tr><tr><td>(d)</td><td>划分II</td><td>Chirp扫频</td><td>蓝线在第3层明显偏向右侧</td></tr></tbody></table></div>
<p>纵轴的“第3层”指<strong>顶层与中层之间</strong>，第2层指中层与首层之间，第1层指首层与固定基础之间。横坐标越大，表示这一层的最大相对变形越大；它不等于该层楼板相对基础的位移。</p>
<p>每条线只连接3个峰值点，便于看层间分布。<strong>三个峰值可以发生在不同时间</strong>，连线并不代表某一瞬间的真实变形形状。(a,b)共用地震横轴尺度，(c,d)共用扫频横轴尺度；跨激励应读数值，不能只比线的横向位置。</p>
<div class="callout"><strong>先看最清楚的差别：</strong>在(d)的第3层，完整模型是@@FULLDRIFT@@%，Guyan是@@GUYANDRIFT@@%，Craig–Bampton是@@CBDRIFT@@%。Guyan相对完整模型高@@GERROR@@%，Craig–Bampton高@@CERROR@@%。这是峰值层间角的相对误差。</div>
</section>

<section id="drift-example"><h2>图13：从两层位移，算到图上的一个点</h2>
<p>层间位移角衡量一层楼在水平方向“错开”的程度。先在每个时刻计算上下两层的位移差，再除以层高，最后在完整时程中找绝对值最大的时刻。</p>
<div class="equation">θ<sub>k,peak</sub> = max<sub>t</sub> <span class="frac"><span>|x<sub>k</sub>(t) − x<sub>k−1</sub>(t)|</span><span>h<sub>k</sub></span></span> × 100%</div>
<p class="eq-note">其中，k是楼层序号；x<sub>k</sub>(t)是该层楼板位移，单位mm；x<sub>0</sub>=0为固定基础；h<sub>k</sub>=635 mm为层高。本图采用0—40 s时程，共40,961个采样时刻。</p>
<figure class="wide-diagram"><svg viewBox="0 0 940 305" role="img" aria-labelledby="drift-title"><title id="drift-title">划分II Guyan扫频第3层峰值的同一时刻位移示意</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#4477aa"/></marker></defs><rect width="940" height="305" rx="12" fill="#f3f7fa"/><g font-family="Microsoft YaHei,sans-serif" fill="#172c3c"><text x="24" y="32" font-size="17" font-weight="bold">真实取值：13.696289 s，划分II · Guyan · 扫频</text><path d="M155 80V240 M345 80V240" stroke="#bdcbd5" stroke-width="3" stroke-dasharray="6 5"/><path d="M192 229H380 M214 102H402 M192 229L214 102 M380 229L402 102" stroke="#4477aa" stroke-width="5" fill="none"/><text x="27" y="107" font-size="16">顶层楼板</text><text x="27" y="234" font-size="16">中层楼板</text><path d="M155 66H214 M155 261H192" stroke="#4477aa" stroke-width="2" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="236" y="70" font-size="16">x₃ = 38.476075 mm</text><text x="218" y="270" font-size="16">x₂ = 24.128439 mm</text><path d="M455 104V227" stroke="#4477aa" stroke-width="2" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="473" y="173" font-size="17">层高 635 mm</text><text x="650" y="113" font-size="16">两层相对位移</text><text x="650" y="149" font-size="26" font-weight="bold">14.347636 mm</text><text x="650" y="191" font-size="17">÷ 635 × 100%</text><text x="650" y="232" font-size="32" fill="#245d87" font-weight="bold">= 2.259470%</text></g></svg><figcaption>示意图中的水平变形被放大，数值来自同一真实采样时刻。灰色虚线表示未变形位置，蓝色表示该时刻的楼板位置。</figcaption></figure>
<p>这里先算38.476075 − 24.128439 = 14.347636 mm，再算14.347636 ÷ 635 × 100% = <strong>2.259470%</strong>，就是图13(d)蓝线在第3层的横坐标。若分别取顶层与中层各自的最大位移再相减，会把不同时间拼在一起，得不到这个层间角峰值。</p>
<div class="demo" id="drift-demo"><h3>逐点查看：图13的36个真实峰值</h3><div class="selector"><label>划分与激励<select id="drift-case"><option value="1-eq">划分I · 地震</option><option value="2-eq">划分II · 地震</option><option value="1-chirp">划分I · 扫频</option><option value="2-chirp" selected>划分II · 扫频</option></select></label><label>模型<select id="drift-method"><option value="Full">完整模型</option><option selected>Guyan</option><option value="CB">Craig–Bampton</option></select></label><label>层间位置<select id="drift-floor"><option value="1">第1层：首层—基础</option><option value="2">第2层：中层—首层</option><option value="3" selected>第3层：顶层—中层</option></select></label></div><div id="drift-output" class="output" aria-live="polite"></div></div>
<details><summary>展开图13全部36个峰值（单位：%）</summary><div class="table-wrap"><table><thead><tr><th>划分与激励</th><th>层间位置</th><th>完整模型</th><th>Guyan</th><th>Craig–Bampton</th></tr></thead><tbody>@@DRIFTROWS@@</tbody></table></div></details>
<p>因此，图13检查的是缩聚后<strong>相邻楼层的相对运动是否保留</strong>。即使某层楼板的位移峰值接近，层与层之间的相位或相对运动不同，层间角仍会出现误差。</p>
</section>

<section id="figure15"><h2>图15：先把左图的“份额”和右图的“变化率”分开</h2>
<figure><img src="@@FIG15@@" alt="图15原图：左侧两图比较15个物理坐标的模态份额；右侧两图比较两个作动坐标的带符号相对份额变化。上排为划分I，下排为划分II。"><figcaption>图15，论文第34页。本轮保持图15原图与数据不变。左侧是份额E，右侧是相对变化率；两边纵坐标的定义不同。</figcaption></figure>
<div class="cards"><div class="card"><h3>左侧(a,c)：每个坐标分到多少</h3><p>横轴j=1…15是<strong>物理坐标编号</strong>。纵轴E<sub>j</sub>是按前5阶模态计算的质量加权份额，每个模型的15个份额相加等于1。</p><p>例如完整模型在j=11处约0.5615，表示<strong>56.15%</strong>的该模态份额落在顶层水平坐标。</p></div><div class="card"><h3>右侧(b,d)：相对完整模型变了多少</h3><p>横轴只保留两个<strong>由作动器施加运动的坐标</strong>。纵轴是“缩聚份额−完整份额”再除以“完整份额”。</p><p>零表示相同，正值表示份额增大，负值表示份额减小。<strong>1.1387表示增加113.87%</strong>，不表示该坐标占113.87%。</p></div></div>
<p>上排是划分I：作动坐标为首层ψ<sub>1</sub>和中层ψ<sub>6</sub>。下排是划分II：作动坐标为首层ψ<sub>1</sub>和顶层ψ<sub>11</sub>。因此右下图没有ψ<sub>6</sub>；中层坐标仍可在完整物理坐标中恢复，所以左下图仍有j=6的点。</p>
<div class="callout gold"><strong>比较柱高前先看刻度：</strong>右上图纵轴约为−0.045到0.015，右下图约为−0.3到1.4，两图尺度不同。右上图的蓝色负柱是约−4.34%，右下图的蓝色正柱是约+113.87%。视觉高度相近不代表变化量相近。</div>
<p>图15没有分地震、扫频两种输入，因为它从质量矩阵、刚度矩阵和模态计算而来，没有使用这两条响应时程。它描述的是<strong>模型的低阶模态分布</strong>，不是某次激励实际产生的能量随时间变化。</p>
</section>

<section id="coordinates"><h2>图15的15个横坐标：3个平动，加12个转动</h2>
<p>这里的“物理坐标”是描述框架怎么动的一项变量。每层使用1个共用水平平动坐标和4个节点转动坐标，三层合计15项。因此图15的横轴并不是15层建筑。</p>
<figure class="wide-diagram"><svg viewBox="0 0 940 370" role="img" aria-labelledby="coord-title"><title id="coord-title">三层框架的15个物理坐标对应关系</title><rect width="940" height="370" rx="12" fill="#f3f7fa"/><g stroke="#a6b8c5" stroke-width="6" fill="none"><path d="M165 55V313 M325 55V313 M485 55V313 M645 55V313 M165 80H645 M165 170H645 M165 260H645"/></g><g fill="#172c3c" font-family="Microsoft YaHei,sans-serif" font-size="17"><text x="22" y="86">顶层</text><text x="22" y="176">中层</text><text x="22" y="266">首层</text><text x="717" y="65" fill="#245d87" font-weight="bold">ψ₁₁：水平平动</text><text x="717" y="97">ψ₁₂—ψ₁₅：转动</text><text x="717" y="155" fill="#245d87" font-weight="bold">ψ₆：水平平动</text><text x="717" y="187">ψ₇—ψ₁₀：转动</text><text x="717" y="245" fill="#245d87" font-weight="bold">ψ₁：水平平动</text><text x="717" y="277">ψ₂—ψ₅：转动</text><text x="159" y="58">13</text><text x="319" y="58">14</text><text x="479" y="58">15</text><text x="639" y="58">16</text><text x="162" y="148">9</text><text x="319" y="148">10</text><text x="479" y="148">11</text><text x="639" y="148">12</text><text x="162" y="238">5</text><text x="322" y="238">6</text><text x="482" y="238">7</text><text x="642" y="238">8</text><text x="30" y="344" font-size="15">节点旁的数字是节点号；ψ的下标是坐标号。图15横轴使用后者。</text></g><g fill="#4477aa"><circle cx="165" cy="80" r="7"/><circle cx="325" cy="80" r="7"/><circle cx="485" cy="80" r="7"/><circle cx="645" cy="80" r="7"/><circle cx="165" cy="170" r="7"/><circle cx="325" cy="170" r="7"/><circle cx="485" cy="170" r="7"/><circle cx="645" cy="170" r="7"/><circle cx="165" cy="260" r="7"/><circle cx="325" cy="260" r="7"/><circle cx="485" cy="260" r="7"/><circle cx="645" cy="260" r="7"/></g></svg><figcaption>坐标示意依据当前框架坐标定义。只展示三层节点与坐标关系，杆件长度未按比例绘制。</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>楼层</th><th>水平坐标</th><th>转动坐标</th><th>对应节点</th></tr></thead><tbody><tr><td>首层</td><td>ψ₁</td><td>ψ₂，ψ₃，ψ₄，ψ₅</td><td>5，6，7，8</td></tr><tr><td>中层</td><td>ψ₆</td><td>ψ₇，ψ₈，ψ₉，ψ₁₀</td><td>9，10，11，12</td></tr><tr><td>顶层</td><td>ψ₁₁</td><td>ψ₁₂，ψ₁₃，ψ₁₄，ψ₁₅</td><td>13，14，15，16</td></tr></tbody></table></div>
<p>图15左侧三个明显的峰恰好位于j=1、6、11，因为本算例的低阶水平模态在这三个平动坐标上分配了大部分份额。完整模型对应约<strong>10.20%、28.98%、56.15%</strong>，其余12个转动坐标合计约<strong>4.67%</strong>。</p>
<p>转动坐标接近零表示它们在这个指标中的权重较小，不表示转动被删除或完全不动。左图点与点的连线只方便比较；相邻编号可能从平动跳到转动，因此连线不是空间振型。</p>
</section>

<section id="modal-calculation"><h2>图15左图：先算每阶模态的份额，再作加权平均</h2>
<p>“模态”是一种结构自由振动的变形方式。图15取频率从低到高的前5种方式，先分别计算15个坐标各占多少，再根据各阶对统一水平输入的参与程度作加权平均。</p>
<h3>① 从模型求出5种振动方式</h3>
<div class="equation">K v<sub>i</sub> = ω<sub>i</sub><sup>2</sup> M v<sub>i</sub></div>
<p class="eq-note">其中，K是模型刚度矩阵，M是模型质量矩阵；v<sub>i</sub>是第i阶振型，ω<sub>i</sub>是角频率，频率f<sub>i</sub>=ω<sub>i</sub>/(2π)，单位Hz。对缩聚模型先在它自己的坐标中求解，再通过变换矩阵T恢复到相同的15个物理坐标，记为φ<sub>i</sub>。</p>
<p>恢复之后，使用<strong>完整模型的质量矩阵</strong>把每阶振型归一化，使φ<sub>i</sub><sup>T</sup>Mφ<sub>i</sub>=1。振型本来可以整体放大或缩小；这一步给各模型统一的大小基准。图6为了看形状，用的是“最大水平分量为1”的显示归一化，不能直接把图6上的读数代入本公式。</p>
<h3>② 对某一阶，算每个坐标分到多少</h3>
<div class="equation">a<sub>ji</sub> = <span class="frac"><span>m<sub>j</sub> φ<sub>ji</sub><sup>2</sup></span><span>Σ<sub>ℓ=1…15</sub> m<sub>ℓ</sub> φ<sub>ℓi</sub><sup>2</sup></span></span>，　Σ<sub>j=1…15</sub>a<sub>ji</sub> = 1</div>
<p class="eq-note">其中，a<sub>ji</sub>表示第i阶模态中，第j个坐标的质量加权份额；φ<sub>ji</sub>是该振型在该坐标上的分量；m<sub>j</sub>是完整质量矩阵的第j个对角元素，平动处为质量、转动处为转动惯量。平方让正负方向都产生非负份额。</p>
<p>本模型M为对角矩阵，归一化后该分母为1。以“划分II、Guyan、首层水平坐标、第1阶”为例：m<sub>1</sub>=@@MASS@@，φ<sub>1,1</sub>=@@PHI@@，所以这一阶首层的份额为<strong>@@A1@@</strong>，即@@A1PCT@@。振型整体反号不会改变平方后的份额。</p>
<h3>③ 确定5阶之间的权重</h3>
<p>用统一的水平地面运动方向衡量每阶模态的参与程度：三个平动坐标取1，转动坐标取0。每阶参与因子的平方再除以前5阶的平方和，得到这一阶的权重。</p>
<div class="equation">γ<sub>i</sub> = <span class="frac"><span>φ<sub>i</sub><sup>T</sup>MΓ</span><span>φ<sub>i</sub><sup>T</sup>Mφ<sub>i</sub></span></span>，　p<sub>i</sub> = <span class="frac"><span>γ<sub>i</sub><sup>2</sup></span><span>Σ<sub>q=1…5</sub>γ<sub>q</sub><sup>2</sup></span></span></div>
<p class="eq-note">其中，Γ是在j=1、6、11处为1、其余为0的输入方向向量；γ<sub>i</sub>为模态参与因子；p<sub>i</sub>为第i阶权重，五阶之和为1。各模型分别计算自己的振型与权重。</p>
<p>完整模型的5阶权重依次约为<strong>81.9911%、13.0648%、4.9427%、0%、0.0014%</strong>。所以这一份额指标主要反映前三阶在水平输入方向上的分布；第4阶虽然入选，但参与极小。这些权重是在所选5阶内部归一化，并不等于完整结构所有模态的全量分配。</p>
<h3>④ 五阶贡献相加，得到左图的一点</h3>
<div class="equation">E<sub>j</sub> = Σ<sub>i=1…5</sub> p<sub>i</sub>a<sub>ji</sub>，　Σ<sub>j=1…15</sub>E<sub>j</sub> = 1</div>
<p class="eq-note">其中，E<sub>j</sub>就是图15左图的纵坐标。它是5阶模态中该坐标份额的加权平均，没有单位，也没有使用某一时刻的位移或速度。</p>
<div class="demo" id="modal-demo"><h3>逐阶演算：选中一个坐标，看5项如何加成一个点</h3><div class="selector"><label>结构划分<select id="modal-div"><option value="1">划分I</option><option value="2" selected>划分II</option></select></label><label>模型<select id="modal-method"><option value="Full">完整模型</option><option selected>Guyan</option><option value="CB">Craig–Bampton</option></select></label><label>坐标<select id="modal-j">@@COORDOPTIONS@@</select></label><button type="button" id="reset-example">恢复首层示例</button></div><p id="modal-title" class="muted"></p><div class="table-wrap"><table id="modal-table"><thead><tr><th>阶次</th><th>频率 Hz</th><th>该阶份额 a<sub>ji</sub></th><th>该阶权重 p<sub>i</sub></th><th>乘积 p<sub>i</sub>a<sub>ji</sub></th></tr></thead><tbody></tbody><tfoot></tfoot></table></div><div id="modal-output" class="output" aria-live="polite"></div><details><summary>查看当前选择的质量、振型与参与因子</summary><p id="mass-note"></p><div class="table-wrap"><table id="raw-table"><thead><tr><th>阶次</th><th>恢复/归一化的φ<sub>ji</sub></th><th>参与因子γ<sub>i</sub></th><th>m<sub>j</sub>φ<sub>ji</sub>²</th></tr></thead><tbody></tbody></table></div></details></div>
<p>以默认选择为例，Guyan的五项相加得到<strong>E<sub>1</sub>=@@GSHARE@@</strong>，是图15(c)第一个蓝点。完整模型按相同流程得到<strong>@@FSHARE@@</strong>。两者都是在15个相同坐标上、按同一质量约定计算，比较才有意义。</p>
<details><summary>展开图15左侧两图全部90个数值</summary>@@SHARETABLES@@</details>
</section>

<section id="bar-calculation"><h2>图15右图：用左图的两个数，算出一根柱子</h2>
<p>右侧只显示两个作动坐标。对每个坐标，先算缩聚份额与完整模型的差，再除以完整模型的份额，就得到带正负号的相对变化率。</p>
<div class="equation">r<sub>j</sub> = <span class="frac"><span>E<sub>j</sub><sup>red</sup> − E<sub>j</sub><sup>full</sup></span><span>E<sub>j</sub><sup>full</sup></span></span></div>
<p class="eq-note">其中，red表示缩聚模型，full表示完整模型；r<sub>j</sub>是本报告为解释柱高使用的符号，即论文式(4.4)求和中的单项。图上的柱高没有乘100，换成百分数时再乘100%。完整模型与自身比较为0，所以右图不另画完整模型的柱子。</p>
<h3>例子：划分II，Guyan的首层正柱与顶层负柱</h3>
<div class="cards"><div class="card"><h3>首层 ψ₁</h3><p>左图份额：0.101991 → 0.218126<br>即10.1991% → 21.8126%</p><span class="big method-guyan">r₁ = +1.138673</span><p>相对原份额增加<strong>113.8673%</strong>；份额本身增加<strong>11.6135个百分点</strong>。所以右图的柱子向上，且超过1。</p></div><div class="card"><h3>顶层 ψ₁₁</h3><p>左图份额：0.561494 → 0.422663<br>即56.1494% → 42.2663%</p><span class="big method-guyan">r₁₁ = −0.247253</span><p>相对原份额减少<strong>24.7253%</strong>；份额本身减少<strong>13.8831个百分点</strong>。所以右图的柱子向下。</p></div></div>
<div class="equation">r₁ = <span class="frac"><span>0.218126 − 0.101991</span><span>0.101991</span></span> ≈ 1.138673<br>r₁₁ = <span class="frac"><span>0.422663 − 0.561494</span><span>0.561494</span></span> ≈ −0.247253</div>
<p class="eq-note">示例显示6位小数；精确计算使用未舍入数据，因此手动代入显示值会有末位差异。</p>
<div class="table-wrap"><table><thead><tr><th>划分</th><th>方法</th><th>坐标</th><th>完整份额</th><th>缩聚份额</th><th>图中柱高</th><th>相对变化</th></tr></thead><tbody>@@CONTRIBROWS@@</tbody></table></div>
<h3>两根带符号柱子相加，就是表5</h3>
<div class="equation">ΔE = r<sub>d₁</sub> + r<sub>d₂</sub><br>划分II · Guyan：1.138673 − 0.247253 = <strong>0.891420</strong></div>
<p class="eq-note">其中，d₁、d₂是两个作动坐标：划分I取1和6，划分II取1和11。ΔE是两项带符号相对变化的和，即论文称为“modal redistribution ratio”的模态重分配指标。</p>
<div class="table-wrap"><table><thead><tr><th>划分</th><th>方法</th><th>两根柱子的相加</th><th>ΔE</th></tr></thead><tbody>@@DELTAROWS@@</tbody></table></div>
<div class="callout gold"><strong>0.8914不表示两个作动坐标的总份额增加了89.14%。</strong><p>这两根柱子分别除以0.101991与0.561494，基准大小不同。实际把两个作动坐标的份额直接相加，是0.663485 → 0.640788，即<strong>66.3485% → 64.0788%</strong>，反而减少2.2696个百分点。若计算合计份额的相对变化，得到<strong>−3.4208%</strong>。这与两根相对变化柱之和+0.8914是两个不同指标。</p></div>
<p>因此，应先看两根柱子各自变化在哪、变化多大，再看它们的和。正负项可能相互抵消；ΔE接近零，单凭这一点也不能保证两个坐标或全部15个坐标都准确。</p>
</section>

<section id="meaning"><h2>两张图合起来：响应偏差在哪里，模态分布又变在哪里</h2>
<div class="table-wrap"><table><thead><tr><th>对象</th><th>这张图直接提供的证据</th><th>当前算例的结论</th></tr></thead><tbody><tr><td>图13：层间角</td><td>真实响应时程中的相邻楼层相对变形峰值</td><td>划分II下Guyan顶层层间角偏大</td></tr><tr><td>图15左侧：份额</td><td>前5阶、质量加权后的15坐标分布</td><td>划分II下Guyan首层份额明显增大，顶层减小</td></tr><tr><td>图15右侧：变化率</td><td>两个作动坐标各自偏离完整模型多少</td><td>首层+113.87%、顶层−24.73%，暴露表5合并的细节</td></tr></tbody></table></div>
<p><strong>第一，Craig–Bampton在本算例中更好地保留了参考模型。</strong>在图13中，它的层间角曲线接近完整模型；在图15中，它的坐标份额曲线也接近完整模型，两个作动坐标的变化率较小。两张图从响应和模态分布两个方面支持这一判断。</p>
<p><strong>第二，划分II的Guyan误差集中出现于一个有明确结构含义的变化之后：</strong>中层水平坐标从当前完整框架准确性模型的保留集合中被消去，恢复需要依赖其他保留坐标。图13显示相对变形的偏差，图15定位低阶模态份额的变化。两者互相补充，但单凭这些图不能把某一份额变化定量换算成某一响应误差。</p>
<p><strong>第三，图15适合作为诊断图。</strong>它能告诉我们缩聚改变了哪些坐标的低阶模态分布，让表5的单个数值变得可解释。仅凭ΔE的正负或大小，不能求出作动器可允许多少毫秒延迟；延迟稳定性要由包含控制器和延迟通道的闭环模型判断。</p>
<div class="callout"><strong>对当前论文的使用判断：</strong>图13提供层间变形这一独立工程指标；图15把表5拆开，解释“0.8914从哪里来、改变发生在哪里”。正文应把图15用于模态分布诊断，不把它写成总能量增加或稳定域缩小的定量证据。</div>
<p>这里的份额采用当前对角质量矩阵、相同15物理坐标、前5阶模态和统一水平输入方向。改变模态截断阶数、质量表示或输入方向，会改变这个指标。图13采用线性响应，峰值大小本身不构成屈服或倒塌判断。</p>
<p>本轮已完成布局更新和数值解释，下一步停在您阅读、判断两图是否表达清楚。论文中双侧界面装配及原稳定边界闭环匹配等既有研究缺口，仍按原记录保留为未完成。</p>
</section>

<section id="layout"><h2>图6、图13的布局更新与本报告的依据</h2>
<p>图6与图13均保持(a)到(d)的原顺序，改为1行4列。图6的12项频率移到各子图下方，图13按激励统一横轴范围。论文只更新这两张图及两处与新排列有关的图注短语，其余正文和原有42条负间距命令保持。</p>
<figure><img src="@@FIG6@@" alt="更新后的图6，一行四个竖长子图，显示两种划分的前两阶恢复水平振型，每个子图下方列出三种模型的对应频率。"><figcaption>图6，论文第24页。依次为划分I第1阶、划分I第2阶、划分II第1阶、划分II第2阶。图中振型按最大水平分量归一化，用于看形状。</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>对象</th><th>主要依据</th><th>已执行的验证</th></tr></thead><tbody><tr><td>图6</td><td>new_horizontal_modes.csv；new_modes_frequencies.csv</td><td>12条振型曲线、12项频率保持</td></tr><tr><td>图13</td><td>4份response_division_*时程；层高635 mm</td><td>36个峰值独立复算，误差≤1e−10</td></tr><tr><td>图15</td><td>2份division_*_matrices.mat；正文式(4.3)、(4.4)</td><td>90个坐标份额独立复算，误差≤1e−10</td></tr><tr><td>数值归一化</td><td>完整质量矩阵、坐标恢复、前5阶参与因子</td><td>连同前述数据共144项检查通过</td></tr><tr><td>论文</td><td>main.tex；15份投稿矢量图</td><td>38页实际编译，无错误或未定义引用</td></tr></tbody></table></div>
<p>本轮使用独立的eig(M<sup>−1</sup>K)数值求解路径复算模态，和前版广义特征值路径的输出交叉核对。响应峰值从原始采样时程重新计算；不是只核对图与导出的汇总表。</p>
<p>原第二版保存在<code>elsevier_review_v2_20260907</code>，本次交付在<code>elsevier_review_v2_figlayout_20260907</code>。该包的<code>explanation_evidence/data/explanation_calculations.json</code>包含逐阶份额、权重、乘积、峰值时刻及原始位移；<code>explanation_evidence/code</code>保存复算与出图代码；<code>explanation_evidence/validation</code>保存实际验收结果。</p>
<p class="muted">排版范围说明：按您此前的要求保留原负间距，第6、7、8、12、13、21、22页部分公式与文字仍紧贴或重叠。本次两张更新图已经查看，图例、坐标、频率和图注均无裁切。</p>
<button type="button" class="no-print" id="print-report">打印当前讲解</button><p class="muted">报告的文字、图片和数值均内嵌，可单独复制后离线阅读。打印会保留当前选择的数值；需要打印完整原始表时，先展开对应条目。</p>
</section>
<footer class="endnote">图13与图15读图及计算讲解汇报 · 本轮数值解释与布局更新已完成。完成计算核对不代表用户已确认论文结论，也不代替未完成的闭环稳定性计算。</footer>
</main><script id="report-data" type="application/json">@@DATA@@</script><script>
const DATA=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id), methods={Full:'完整模型',Guyan:'Guyan',CB:'Craig–Bampton'};
const fmt=(x,n=6)=>Math.abs(x)<1e-10&&x!==0?x.toExponential(2):x.toFixed(n), pct=x=>(100*x).toFixed(4)+'%', sign=x=>(x>=0?'+':'')+fmt(x);
const coord=j=>({1:'首层水平平动',6:'中层水平平动',11:'顶层水平平动'}[j]||'节点转动');
function driftUpdate(){const [ds,exc]=$('drift-case').value.split('-'),d=+ds,method=$('drift-method').value,k=+$('drift-floor').value;
 const r=DATA.drifts.find(x=>x.division===d&&x.excitation===exc&&x.method===method&&x.storey===k);
 const f=DATA.drifts.find(x=>x.division===d&&x.excitation===exc&&x.method==='Full'&&x.storey===k);
 $('drift-output').innerHTML=`<p><strong>划分${'I'.repeat(d)} · ${exc==='eq'?'地震':'扫频'} · ${methods[method]} · 第${k}层</strong>，峰值发生在 ${fmt(r.peak_time_s)} s。</p><div class="value-grid"><div><small>上层位移 x${k} / mm</small><b>${fmt(r.upper_displacement_mm)}</b></div><div><small>下层位移 x${k-1} / mm</small><b>${fmt(r.lower_displacement_mm)}</b></div><div><small>峰值层间角 / %</small><b>${fmt(r.peak_drift_percent)}</b></div></div><p>|${fmt(r.upper_displacement_mm)} − (${fmt(r.lower_displacement_mm)})| ÷ 635 × 100% = <strong>${fmt(r.peak_drift_percent)}%</strong>。相对完整模型同一层的峰值 ${fmt(f.peak_drift_percent)}%，变化为 ${sign((r.peak_drift_percent/f.peak_drift_percent-1)*100)}%。</p><p class="muted">这里比较各模型自身的层间角峰值；完整模型的峰值时刻可能不同。</p>`;
 $('drift-output').dataset.peak=r.peak_drift_percent;
}
function modalUpdate(){const d=+$('modal-div').value,method=$('modal-method').value,j=+$('modal-j').value-1,m=DATA.models.find(x=>x.division===d&&x.method===method),f=DATA.models.find(x=>x.division===d&&x.method==='Full');
 $('modal-title').textContent=`当前：划分${'I'.repeat(d)} · ${methods[method]} · ψ${j+1}（${coord(j+1)}）。数值均为无量纲份额，频率除外。`;
 $('modal-table').querySelector('tbody').innerHTML=m.weights.map((p,i)=>`<tr><td>第${i+1}阶</td><td>${fmt(m.frequencies_hz[i],4)}</td><td>${fmt(m.coordinate_fraction_per_mode[j][i])}</td><td>${fmt(p)}</td><td>${fmt(m.weighted_contribution_per_mode[j][i])}</td></tr>`).join('');
 $('modal-table').querySelector('tfoot').innerHTML=`<tr><td colspan="3">五阶相加</td><td>1.000000</td><td>${fmt(m.shares[j])}</td></tr>`;
 const r=(m.shares[j]-f.shares[j])/f.shares[j],acts=d===1?[1,6]:[1,11];
 $('modal-output').innerHTML=`<div class="value-grid"><div><small>左图：当前模型 E${j+1}</small><b>${fmt(m.shares[j])}</b><small>即 ${pct(m.shares[j])}</small></div><div><small>左图：完整模型 E${j+1}</small><b>${fmt(f.shares[j])}</b><small>即 ${pct(f.shares[j])}</small></div><div><small>相对完整模型的变化率</small><b>${sign(r)}</b><small>即 ${sign(r*100)}%</small></div></div><p>${acts.includes(j+1)?(method==='Full'?'完整模型是右图的零基准。':`该坐标是本划分的作动坐标，因此 ${sign(r)} 就是右图对应的${method==='Guyan'?'蓝色':'红色'}柱高。`):'该坐标不是本划分的作动坐标，因此左图有这个点，右图不画它的柱子。'}</p>`;
 $('modal-output').dataset.share=m.shares[j];$('modal-output').dataset.relative=r;
 $('mass-note').textContent=`完整质量矩阵第${j+1}个对角元素 m${j+1} = ${fmt(m.mass_diagonal[j])} ${[1,6,11].includes(j+1)?'kg':'kg·m²'}；逐阶份额的分母均为1（完整质量归一化）。平动坐标使用m、转动坐标使用rad的原始约定。`;
 $('raw-table').querySelector('tbody').innerHTML=m.weights.map((p,i)=>`<tr><td>第${i+1}阶</td><td>${fmt(m.expanded_modes[j][i],9)}</td><td>${fmt(m.gamma[i],9)}</td><td>${fmt(m.mass_diagonal[j]*m.expanded_modes[j][i]**2,9)}</td></tr>`).join('');
}
['drift-case','drift-method','drift-floor'].forEach(id=>$(id).addEventListener('change',driftUpdate));
['modal-div','modal-method','modal-j'].forEach(id=>$(id).addEventListener('change',modalUpdate));
$('reset-example').addEventListener('click',()=>{$('modal-div').value='2';$('modal-method').value='Guyan';$('modal-j').value='1';modalUpdate()});
$('print-report').addEventListener('click',()=>window.print());driftUpdate();modalUpdate();
</script></body></html>'''

values={'FIG13':image('fig15_peak_drift.png'),'FIG15':image('fig16_modal_shares.png'),'FIG6':image('fig12_horizontal_modes.png'),
'FULLDRIFT':num(fdrift['peak_drift_percent'],6),'GUYANDRIFT':num(gdrift['peak_drift_percent'],6),'CBDRIFT':num(cdrift['peak_drift_percent'],6),
'GERROR':num((gdrift['peak_drift_percent']/fdrift['peak_drift_percent']-1)*100,3),'CERROR':num((cdrift['peak_drift_percent']/fdrift['peak_drift_percent']-1)*100,3),
'DRIFTROWS':drift_rows,'CONTRIBROWS':contrib_rows,'DELTAROWS':delta_rows,'SHARETABLES':share_tables,
'MASS':num(guyan['mass_diagonal'][0]),'PHI':num(guyan['expanded_modes'][0][0],9),'A1':num(guyan['coordinate_fraction_per_mode'][0][0]),'A1PCT':pct(guyan['coordinate_fraction_per_mode'][0][0]),
'GSHARE':num(guyan['shares'][0]),'FSHARE':num(full['shares'][0]),
'COORDOPTIONS':''.join(f'<option value="{j}">ψ{j} · '+({1:'首层平动',6:'中层平动',11:'顶层平动'}.get(j,'节点转动'))+'</option>' for j in range(1,16)),
'DATA':json.dumps(D,ensure_ascii=False,separators=(',',':')).replace('</',r'<\/')}
for key,value in values.items():template=template.replace('@@'+key+'@@',value)
assert '@@' not in template
OUT=NEW/'图13与图15读图及计算讲解汇报.html'
OUT.write_text(template,encoding='utf-8')
if Path(__file__).resolve()!= (NEW/'explanation_evidence/code/build_explanation.py').resolve():shutil.copy2(__file__,NEW/'explanation_evidence/code/build_explanation.py')
print(json.dumps({'html':str(OUT),'bytes':OUT.stat().st_size,'inline_pngs':3,'inline_svgs':2,'guyan_top_drift_error_percent':(gdrift['peak_drift_percent']/fdrift['peak_drift_percent']-1)*100,'default_first_modal_share':guyan['coordinate_fraction_per_mode'][0][0]},ensure_ascii=False,indent=2))
