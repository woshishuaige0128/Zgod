"""Self-contained, offline delay selection report with all candidate figures."""
from pathlib import Path
import json,csv,base64,io,html
from PIL import Image
from delay_model import CASE,DT

ROOT=CASE.parents[1];OUT=ROOT/'reports';OUT.mkdir(exist_ok=True)
ROWS=json.loads((CASE/'results/selected_delays.json').read_text('utf-8'))
METRICS=list(csv.DictReader((CASE/'results/response_metrics.csv').open(encoding='utf-8')))
CHECKS=json.loads((CASE/'results/response_checks.json').read_text('utf-8'))
def fmt(x):return f'{float(x):.6g}'
def ms(x):return f'{float(x):.7f}'.rstrip('0').rstrip('.')
def get(row,exc,name,floor=2):return next(x for x in METRICS if x['key']==row['key'] and x['input']==exc and x['model']==name and int(x['floor'])==floor)
def image(name,alt):
    im=Image.open(CASE/'figures'/f'{name}.png');im.thumbnail((2200,2200));buf=io.BytesIO();im.save(buf,format='PNG',optimize=True)
    return f'<img loading="eager" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}" alt="{html.escape(alt)}" onclick="zoomImage(this)">'

def main():
    index=[];cards=[];options=[]
    for r in ROWS:
        key=r['key'];tau=f"首层 {ms(r['tau1_ms'])} ms；顶层 {ms(r['tau2_ms'])} ms"
        unstable=any(v!='stable' for v in r['status'].values())
        kind='unstable' if unstable else 'equal' if r['n1']==r['n2'] else 'unequal'
        badnames=[{'Full15':'完整15','Uncondensed19':'同接口19','Guyan6':'Guyan','CB12':'CB'}[name] for name,v in r['status'].items() if v!='stable']
        state=('、'.join(badnames)+'失稳，其余模型稳定') if unstable else '四种模型均稳定'
        tag='失稳示例' if unstable else '零时滞基准' if r['n1']==r['n2']==0 else '稳定候选'
        cells=[]
        for exc in ['eq','chirp']:
            for name in ['Guyan6','CB12']:cells.append(fmt(get(r,exc,name)['nrmse_same_interface_percent']))
        index.append(f'<tr><td><a href="#{key}">{ms(r["tau1_ms"])}, {ms(r["tau2_ms"])}</a></td><td>{tag}</td>'+''.join(f'<td>{x}</td>' for x in cells)+'</tr>')
        options.append(f'<option value="{key}">{tau} · {tag}</option>')
        detail=[]
        for exc,title in [('eq','地震'),('chirp','扫频')]:
            for floor in [1,2,3]:
                for name,label in [('Guyan6','Guyan'),('CB12','CB')]:
                    m=get(r,exc,name,floor)
                    detail.append(f'<tr><td>{title}</td><td>{floor} 层</td><td>{label}</td><td>{fmt(m["nrmse_same_interface_percent"])}</td><td>{fmt(m["nrmse_full15_same_delay_percent"])}</td><td>{fmt(m["nrmse_ideal_full15_percent"])}</td><td>{fmt(m["peak_response_mm"])}</td></tr>')
        pole='；'.join(f'{label} {r["rho_"+name]:.8f}' for name,label in [('Full15','完整15'),('Uncondensed19','同接口19'),('Guyan6','Guyan'),('CB12','CB')])
        note=('此点存在失稳模型，纵轴使用绝对值的对数尺度。接近边界的增长可能在40秒内不明显，稳定性以极点为准。' if unstable else '响应图和误差图在所有稳定候选间采用相同坐标范围。右列误差以同接口未缩聚参考为基准。')
        cards.append(f'''<section class="case" id="{key}" data-kind="{kind}">
          <div class="case-head"><h2>{tau}</h2><label class="pick"><input type="checkbox" value="{html.escape(tau)}" onchange="updateSelection()"> 标记此候选</label></div>
          <p class="case-status {'bad' if unstable else ''}">{state}。地震中间层 NRMSE：Guyan {cells[0]}%，CB {cells[1]}%；扫频：Guyan {cells[2]}%，CB {cells[3]}%。</p>
          <p class="figure-note">{note}</p>
          <div class="chart"><h3>地震响应：El Centro × 0.40</h3>{image(key+'_eq',tau+'地震三楼层响应及误差')}</div>
          <div class="chart"><h3>扫频响应：0.1—10 Hz，40 秒</h3>{image(key+'_chirp',tau+'扫频三楼层响应及误差')}</div>
          <details class="detail"><summary>极点与各楼层完整指标</summary><p>最大极点模：{pole}。</p><div class="table-wrap"><table><thead><tr><th>输入</th><th>楼层</th><th>方法</th><th>对同接口19，%</th><th>对同时滞完整15，%</th><th>对零时滞完整15，%</th><th>峰值位移，mm</th></tr></thead><tbody>{''.join(detail)}</tbody></table></div></details>
        </section>''')
    css='''
    :root{--ink:#17354d;--muted:#587087;--line:#dbe5ed;--blue:#24679a}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f1f5f8;color:#172c3e;font-family:"Microsoft YaHei","Segoe UI",sans-serif;font-size:15px;line-height:1.65}main{max-width:1220px;margin:auto;padding:28px 28px 60px}h1{font-size:30px;line-height:1.3;margin:0 0 14px}h2{font-size:22px;line-height:1.4;margin:0 0 12px}h3{font-size:16px;margin:4px 0}p{margin:8px 0}a{color:#176191}section,.intro{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:22px}.lead{font-size:18px}.badge{display:inline-block;padding:2px 10px;border-radius:20px;background:#e6f1f8;color:#165c8b;font-size:13px;margin:0 8px 8px 0}.callout{background:#eef5fa;border-left:4px solid #4477aa;padding:14px 18px;margin:16px 0}.muted,.figure-note{color:var(--muted)}.toolbar{position:sticky;top:0;background:#fffef8;z-index:2;border:1px solid var(--line);padding:12px;display:flex;gap:12px;flex-wrap:wrap;border-radius:9px;margin:16px 0}.toolbar label{display:flex;gap:6px;align-items:center}select,button{font:inherit;max-width:100%;padding:5px 9px;border:1px solid #b9cbd9;border-radius:5px;background:white}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}thead{background:#edf3f7}img{width:100%;height:auto;display:block;background:white;cursor:zoom-in}.case-head{display:flex;gap:20px;justify-content:space-between;align-items:start}.case-head h2{font-size:21px}.pick{font-size:14px;white-space:nowrap}.case-status{font-size:14px;color:#276441}.bad{color:#9d352c}.figure-note{font-size:13px}.chart{padding:12px 0 2px}.chart h3{color:#345771;font-weight:500}.detail{border-top:1px solid var(--line);margin-top:12px;padding-top:10px}.detail summary{cursor:pointer;color:#176191}.selection{background:#f8fafc;border:1px solid var(--line);padding:12px;min-height:52px;white-space:pre-wrap}dialog{border:0;padding:12px;max-width:96vw;max-height:96vh;border-radius:8px}dialog::backdrop{background:#0b2238bd}dialog img{width:auto;max-width:90vw;max-height:86vh;object-fit:contain}dialog button{display:block;margin-left:auto}.hidden{display:none!important}.summary-figure{margin-top:18px}.summary-figure p{font-size:14px}.end{font-size:14px}.overview-title{margin-bottom:4px}
    @media(max-width:600px){main{padding:14px 10px}section,.intro{padding:15px 12px;border-radius:8px}h1{font-size:24px}.lead{font-size:16px}.case-head{display:block}.pick{display:block;margin:4px 0}.case-head h2{font-size:18px}.toolbar{position:static;display:block}.toolbar label{display:block;margin:6px 0}.toolbar select{width:100%}.chart{overflow:hidden}th,td{padding:7px}dialog{padding:5px}}
    @page{size:A4;margin:9mm} @media print{body{background:white;font-size:9pt;line-height:1.35}main{padding:0;max-width:none}.toolbar,.pick,.selection-section,dialog,.detail{display:none!important}section,.intro{border:0;border-radius:0;padding:0;margin:0 0 8mm}.intro{break-after:page}h1{font-size:18pt}h2{font-size:13pt}h3{font-size:9pt}.lead{font-size:11pt}.badge{font-size:8pt}.case{break-before:page;break-inside:avoid}.case.hidden{display:block!important}.case-head h2{font-size:12pt;margin:0 0 2mm}.case-status,.figure-note{font-size:8pt;margin:1mm 0}.chart{padding:1mm 0 0;break-inside:avoid}.chart img{width:100%;max-height:117mm;object-fit:contain}.chart h3{font-size:8pt;margin:1mm 0}.summary-figure{break-before:page}.summary-figure img{max-height:175mm;object-fit:contain}.end{break-before:page;font-size:9pt}.callout{padding:3mm;margin:3mm 0}table{font-size:8pt}td,th{padding:1.5mm}.case:last-of-type{break-after:auto}a{color:inherit;text-decoration:none}}
    '''
    css += '.case{scroll-margin-top:100px}@media(max-width:600px){.case{scroll-margin-top:0}}'
    page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>划分二多时滞案例选图汇报</title><style>{css}</style></head><body><main>
    <header class="intro"><span class="badge">18 组候选 · 两种输入 · 实际计算</span><span class="badge">供 Doctor Bego 选择</span><h1>划分二：多时滞案例选图汇报</h1>
    <p class="lead">已计算零时滞及 17 组非零时滞，覆盖等时滞、不等时滞、接近稳定边界和失稳示例。每组展示三楼层地震与扫频响应，右列直接显示缩聚误差。正式采用哪个时滞，由您看图后决定。</p>
    <div class="callout"><strong>建议先看两组稳定候选：</strong><br><a href="#n04_04">首层、顶层均为 3.90625 ms</a>：便于说明两个通道共同滞后的影响。<br><a href="#n05_01">首层 4.8828125 ms、顶层 0.9765625 ms</a>：更接近 Guyan 的稳定边界，可观察通道不均衡和误差增长。<br><a href="#n05_05">两个通道均为 4.8828125 ms</a> 已使子结构模型失稳，仅用于稳定性展示。</div>
    <p><strong>时滞位置：</strong>第一通道驱动首层 ψ₁，第二通道驱动顶层 ψ₁₁。时滞为整数步，每步 1/1024 秒 = 0.9765625 ms。所有方法在每张图中使用同一组实际时滞。</p>
    <p><strong>图例说明：</strong>绿色虚线为 15 自由度完整框架（其他界面坐标理想连接）；灰色虚线为两个子结构保留全部局部自由度、仅在两个作动坐标连接的 19 自由度参考；蓝色为标准 Guyan（6 自由度），红色为 CB（每子结构 3 个模态，装配后 12 自由度）。右列误差以灰色参考为基准，单独衡量相同接口条件下的缩聚影响。</p>
    <p class="muted">本轮是依现稿第 2—3 节重建的有时滞子结构闭环。上一轮无时滞图采用整个框架直接缩聚，两者的接口协调条件不同，不能把两轮全部变化归因于时滞。</p>
    <p class="muted">参考的选择会改变结论：例如零时滞中间层地震响应，相对完整15的NRMSE为Guyan 8.811%、CB 9.164%，而相对同接口19为0.427%、0.00883%。因此，本轮将接口协调偏差与缩聚截断偏差分开列示。</p><h2>候选列表：中间层恢复误差</h2><p>下表 NRMSE 使用相同时滞、同接口未缩聚参考的全记录峰峰值归一化；失稳行的有限时长数值不用于正常精度排序。</p>
    <div class="table-wrap"><table><thead><tr><th>首层, 顶层时滞（ms）</th><th>状态</th><th>地震 Guyan，%</th><th>地震 CB，%</th><th>扫频 Guyan，%</th><th>扫频 CB，%</th></tr></thead><tbody>{''.join(index)}</tbody></table></div></header>
    <section class="summary-figure"><h2>已检查的整数时滞与稳定状态</h2><p>颜色为最大极点模减 1：负值稳定、正值失稳。黑圈为本轮实际响应计算点。图中每格对应一个已求根的整数时滞组合，共 81 个组合；不是连续边界的解析解。</p>{image('delay_grid','四种模型的整数时滞稳定检查与候选点')}</section>
    <section class="summary-figure"><h2>等时滞下：误差与闭环极点</h2><p>左图只比较稳定等时滞候选的中间层误差，使用固定的零时滞完整框架峰峰值归一化，避免归一化尺度随时滞变化；右图包含 5 步时滞，显示穿过稳定界限的位置。</p>{image('equal_delay_progression','等时滞误差及谱半径变化')}</section>
    <section class="summary-figure"><h2>两组稳定候选的局部响应</h2><p>左列：首层/顶层均 3.90625 ms；右列：首层 4.8828125 ms、顶层 0.9765625 ms。上排地震 6—16 秒，下排扫频 30—40 秒；均为物理子结构中间层恢复响应。</p>{image('two_candidate_windows','两组稳定候选的中间层局部响应')}</section>
    <div class="toolbar"><label>筛选 <select id="filter" onchange="filterCases()"><option value="all">全部 18 组</option><option value="equal">稳定等时滞</option><option value="unequal">稳定不等时滞</option><option value="unstable">失稳示例</option></select></label><label>跳转 <select id="jump" onchange="jumpCase(this.value)"><option value="">选择实际时滞组合</option>{''.join(options)}</select></label><button onclick="document.getElementById('selection').scrollIntoView()">查看已标记候选</button></div>
    {''.join(cards)}
    <section class="selection-section" id="selection"><h2>您标记的候选</h2><p>勾选只用于本页整理。请将希望采用的首层、顶层时滞值发到对话中；这里不会自动修改论文。</p><div class="selection" id="selection-text">尚未标记候选。</div></section>
    <section class="end"><h2>计算设置与实际验收</h2>
    <p><strong>结构和装配：</strong>沿用冻结全框架的几何、等效质量与全框架 5% Rayleigh 阻尼。物理部分由外侧一跨的两列柱和三层梁装配；数值部分为其余构件。物理、数值 M/C/K 嵌回全框架后与冻结矩阵完全相等。历史局部脚本包含两处额外边界转角刚度及单独的 10% 阻尼，本轮依据现稿几何与统一阻尼重新装配，并保存该差异记录。</p>
    <p><strong>控制和时滞：</strong>从标准 Guyan 装配模型静力缩聚到首层、顶层两个作动坐标，按 Q=diag(10⁶,10⁶,10⁴,10⁴)、R=diag(10⁻²,10⁻²)设计连续 LQR。四个模型共用这组通道增益，且随时滞保持固定，用于识别结构与接口差异。原文分别为各模型设计控制器的情形属于另一比较设置。</p>
    <p><strong>递推：</strong>CR 系数由未分通道的结构 M/C/K 构成；仅物理弹性、阻尼反力的作动列及对应控制力经过独立时滞。惯性由数值部分推进。零初值和负时间零历史，40 秒、40961 个输出时刻。地震原始 0.02 秒记录线性插值；扫频保持 0.1—10 Hz。物理中间层由延迟作动坐标与当前内部模态恢复。</p>
    <p><strong>数值验证：</strong>170 项模型和极点检查通过；MATLAB 独立 LQR 增益相对差 3.18×10⁻¹³；144 份 MATLAB CR 响应已用 Python 增广状态重新计算，最大相对差 {CHECKS['max_relative_difference']:.3e}。验证包含实际反馈平衡和物理端时滞恢复。图件和离线报告的最终检查记录位于案例 results 目录。</p>
    <p><strong>19 自由度参考的含义：</strong>数值子结构 12 个、物理子结构 9 个局部自由度，共享 2 个作动坐标后为 19 个。CB 保留全部内部模态会恢复这一参考；恢复理想完整15还需补上其余界面的协调条件。两种参考的各楼层指标在每组图下的可展开表格及 response_metrics.csv 中同时保留。</p>
    <p><strong>结果状态：</strong>本轮为选图提供可复现计算与验证，尚未替您选定正式工况，也未将结果认定为新理论证明或外部审查通过。稳定性判定来自离散极点；失稳曲线仅表示当前线性模型的增长。</p>
    <p><strong>交付：</strong>cases/case2_v1_divisionII_delays_20260916 包含模型、输入、代码、完整指标与39幅矢量PDF/600dpi PNG；本单文件HTML可离线移动阅读，另有可打印PDF。</p>
    </section></main><dialog id="zoom"><button onclick="this.parentElement.close()">关闭</button><img id="zoom-image" alt="放大图"></dialog><script>
    function zoomImage(img){{document.getElementById('zoom-image').src=img.src;document.getElementById('zoom').showModal()}}
    function filterCases(){{let f=document.getElementById('filter').value;document.querySelectorAll('.case').forEach(x=>x.classList.toggle('hidden',f!=='all'&&x.dataset.kind!==f))}}
    function jumpCase(id){{if(!id)return;document.getElementById('filter').value='all';filterCases();document.getElementById(id).scrollIntoView()}}
    function updateSelection(){{let a=[...document.querySelectorAll('.pick input:checked')].map(x=>x.value);document.getElementById('selection-text').textContent=a.length?a.join(String.fromCharCode(10)):'尚未标记候选。'}}
    document.querySelectorAll('a[href^="#n"]').forEach(x=>x.addEventListener('click',e=>{{e.preventDefault();jumpCase(x.hash.slice(1))}}));
    </script></body></html>'''
    path=OUT/'划分二多时滞案例选图汇报.html';path.write_text(page,'utf-8')
    print('REPORT',path,'bytes',path.stat().st_size,flush=True)

if __name__=='__main__':main()
