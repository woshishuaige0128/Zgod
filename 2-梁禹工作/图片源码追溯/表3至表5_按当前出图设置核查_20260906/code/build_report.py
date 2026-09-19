from pathlib import Path
import csv,hashlib,html,json,shutil
import numpy as np

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]
PAPER=ROOT.parent/'260817'
TEMP=ROOT/'tmp/table345_audit_20260906/temp'
esc=lambda v:html.escape(str(v))

def main():
    result=json.loads((OUT/'results/python_results.json').read_text(encoding='utf-8'))
    rows=result['rows']
    independent=np.loadtxt(OUT/'results/MATLAB独立复算_44项.csv',delimiter=',')
    assert np.array_equal(independent[:,0],np.arange(1,45))
    error=np.abs(np.array([r['recomputed'] for r in rows])-independent[:,1])
    assert max(error)<1e-8
    cross=[dict(id=r['id'],table=r['table'],python=r['recomputed'],matlab=independent[i,1],absolute_difference=error[i],status='PASS') for i,r in enumerate(rows)]
    with (OUT/'results/MATLAB_Python_44项独立核对.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cross[0]));w.writeheader();w.writerows(cross)
    manifest=json.loads((OUT/'evidence/source_manifest.json').read_text(encoding='utf-8'))
    hash_matches=[hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in manifest]
    assert all(hash_matches)
    for name in ['matlab_all_four.log','matlab_metrics.log']:
        shutil.copy2(TEMP/name,OUT/'evidence'/name)
    log=(TEMP/'matlab_all_four.log').read_text(encoding='utf-8',errors='replace')
    assert log.count('AUDIT_FRESH_SIMULATION=PASS')==4 and 'ALL_FOUR_FRESH_SIMULATIONS=PASS' in log
    warning_count=log.count('警告:')
    max_response=max(r['maximum_absolute_difference_mm'] for r in result['source_comparisons'])
    pdf_match=[]
    for name in ['fig06_eq_div1.pdf','fig07_eq_div2.pdf','fig08_chirp_div1.pdf','fig09_chirp_div2.pdf']:
        a=PAPER/'elsevier/submit_figure'/name;b=PAPER/'figure/results_v2/PDF'/name
        same=hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(b.read_bytes()).digest();assert same
        pdf_match.append({'figure':name,'same_bytes':same,'sha256':hashlib.sha256(a.read_bytes()).hexdigest()})
    validation={'fresh_simulations_passed':4,'time_points_per_case':40961,'max_response_difference_mm':max_response,
                'cross_language_metrics':44,'max_cross_language_difference':float(max(error)),
                'source_hash_matches':sum(hash_matches),'source_hash_total':len(manifest),'submission_pdf_matches':pdf_match,
                'simulation_log_warning_occurrences':warning_count,'table_agreement':result['summary'],
                'computation_validation':'PASS','manuscript_three_tables_all_agree':False}
    (OUT/'evidence/numerical_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')

    def cell(r):
        klass='same' if r['status']=='相符' else 'changed'
        return f'<td class="{klass}"><span class="old">{esc(r["manuscript_value"])}</span><span class="arrow"> → </span><strong>{esc(r["rounded_value"])}</strong></td>'
    def table(header,body):
        return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in header)+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    t3=''
    for d in [1,2]:
        for mode in [1,2]:
            rr=[r for r in rows if r['table']==3 and r['division']==d and r['item']==f'第{mode}阶']
            t3+=f'<tr><td>第{d}类</td><td>{mode}</td>'+''.join(cell(r) for r in rr)+'</tr>'
    t4=''
    rr4=[r for r in rows if r['table']==4]
    for i in range(0,24,4):
        rr=rr4[i:i+4];t4+='<tr><td>'+esc(rr[0]['item'])+'</td>'+''.join(cell(r) for r in rr)+'</tr>'
    t5=''
    for d in [1,2]:
        rr=[r for r in rows if r['table']==5 and r['division']==d]
        t5+=f'<tr><td>第{d}类</td>'+''.join(cell(r) for r in rr)+'</tr>'
    full=''
    for r in rows:
        full+=f'<tr><td>表{r["table"]}</td><td>第{r["division"]}类 · {esc(r["item"])}</td><td>{esc(r["method"])}</td><td>{esc(r["metric"])}</td><td>{esc(r["manuscript_value"])}</td><td>{r["recomputed"]:.12g}</td><td>{r["status"]}</td></tr>'
    table3=table(['划分','阶次','Guyan频率误差(%)','Craig–Bampton频率误差(%)','Guyan MAC','Craig–Bampton MAC'],t3)
    table4=table(['激励 / 扫频频段','第1类 Guyan','第1类 Craig–Bampton','第2类 Guyan','第2类 Craig–Bampton'],t4)
    table5=table(['划分','Guyan','Craig–Bampton'],t5)
    appendix=table(['原表','对象','方法','指标','稿件值','本轮复算值','显示精度判定'],full)
    modelrows=''.join(f'<tr><td>第{m["division"]}类</td><td>15 / {m["guyan"]} / {m["craig_bampton"]}</td><td>{m["master_dofs"]}</td><td>{m["actuated_dofs"]}</td></tr>' for m in result['models'])
    modeltable=table(['当前出图模型','完整 / Guyan / Craig–Bampton自由度数','整体缩聚保留的物理坐标编号','表5求和的作动坐标编号'],modelrows)
    source_hash=next(x['sha256'] for x in manifest if x['path'].endswith('elsevier\\main.tex') or x['path'].endswith('elsevier/main.tex'))
    doc=f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>表3至表5数值准确性核查汇报</title>
<style>
:root{{--ink:#152b3b;--muted:#536777;--blue:#12566b;--line:#dce5ea;--bg:#f4f7f9;--bad:#963c24;--good:#226343}}header code{{color:#123e53!important;background:#e7f0f4!important}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.8 "Microsoft YaHei","Segoe UI",sans-serif}}
main{{max-width:1140px;margin:auto;padding:40px 30px 70px}}header{{padding:32px;background:#143f52;color:white;border-radius:15px}}h1{{font-size:30px;line-height:1.4;margin:0 0 16px}}h2{{font-size:23px;line-height:1.5;margin:0 0 14px}}h3{{font-size:18px}}p{{margin:10px 0 16px}}header p{{color:#e3edf2}}.eyebrow{{font-size:13px;letter-spacing:1px;color:#c8dde6;margin-bottom:12px}}
nav{{display:flex;flex-wrap:wrap;gap:9px;margin:24px 0}}nav a{{text-decoration:none;padding:5px 13px;border:1px solid var(--line);border-radius:20px;background:white;color:var(--blue)}}a{{color:var(--blue)}}section{{margin:24px 0;padding:28px;background:white;border:1px solid var(--line);border-radius:12px;scroll-margin-top:16px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:24px}}.card{{background:white;padding:22px;border:1px solid var(--line);border-radius:12px}}.big{{font-size:35px;font-weight:750;line-height:1.3}}.small{{font-size:14px;color:var(--muted)}}.callout{{background:#fff4ed;border-left:4px solid #d87949;padding:15px 18px;margin:18px 0}}.confirmed{{background:#edf6f2;border-left-color:#3c8b68}}
.table-scroll{{overflow-x:auto;max-width:100%;margin:18px 0}}table{{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}}th,td{{padding:11px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#eef3f6;color:#204459;font-weight:650}}td{{font-variant-numeric:tabular-nums}}.same{{background:#f1f8f4}}.changed{{background:#fff4ee;color:#812e1e}}.old{{color:#61686c;font-size:13px}}.arrow{{color:#839199}}strong{{font-weight:700}}code{{font-family:Consolas,monospace;overflow-wrap:anywhere;font-size:13px;background:#f0f4f6;padding:2px 4px}}.formula{{padding:14px 16px;background:#eff5f7;border-radius:7px;font-family:"Cambria Math","Microsoft YaHei",sans-serif;overflow-wrap:anywhere}}li{{margin:8px 0}}details{{border:1px solid var(--line);border-radius:8px;padding:14px;margin:15px 0}}summary{{cursor:pointer;font-weight:650}}.path{{overflow-wrap:anywhere}}footer{{font-size:13px;color:var(--muted)}}
@media(max-width:650px){{main{{padding:16px 12px 36px}}header,section{{padding:20px 16px}}h1{{font-size:25px}}h2{{font-size:21px}}.cards{{grid-template-columns:1fr}}.card{{padding:15px 20px;display:flex;gap:20px;align-items:center}}.big{{font-size:30px}}table{{min-width:720px}}#table5 table{{min-width:420px}}}}
@page{{size:A4;margin:14mm}}@media print{{body{{background:white;font-size:10pt;line-height:1.5}}main{{padding:0;max-width:none}}header{{background:white;color:#143f52;padding:0 0 12px;border-bottom:2px solid #143f52}}header p,.eyebrow{{color:#374f5c}}h1{{font-size:23pt}}h2{{font-size:16pt;break-after:avoid}}h3,summary{{break-after:avoid}}nav{{display:none}}section{{padding:15px 0;margin:14px 0;border:0;border-top:1px solid var(--line);border-radius:0}}.cards{{gap:8px}}.card{{padding:12px;break-inside:avoid}}.big{{font-size:25pt}}table{{font-size:8pt;min-width:0!important}}th,td{{padding:6px 5px}}tr,.callout,.formula{{break-inside:avoid}}thead{{display:table-header-group}}.table-scroll{{overflow:visible}}details{{border:0;padding:0}}a{{text-decoration:none}}.screen-only{{display:none}}}}
</style></head><body><main>
<header><div class="eyebrow">Doctor Bego · 2026-09-06 · 当前出图设置核查</div><h1>表 3、4、5 不能作为一组准确数值沿用</h1>
<p>核查已完成。以您指定的 <code>260817/elsevier/main.tex</code> 为对象，按当前响应图使用的模型重新运行四套仿真，并独立复算三个表共44个单元：14格与原表显示精度相符，30格不符。表3第一类划分的8格全部相符；表4大部分数值和表5四个数值均与当前出图口径不符。</p>
<p>本次交付原值与复算值逐项对照、复算代码和验证证据。原稿及原出图资产保持不变。后续修改应同时统一正文、模型和表格；本次核查不需要您先执行任何操作。</p></header>
<div class="cards"><div class="card"><div class="big">11 / 16</div><div>表3：模态精度<br><span class="small">相符11格，不符5格</span></div></div><div class="card"><div class="big">3 / 24</div><div>表4：首层时程误差<br><span class="small">相符3格，不符21格</span></div></div><div class="card"><div class="big">0 / 4</div><div>表5：模态重分配比<br><span class="small">当前可复算模型下四格均不符</span></div></div></div>
<nav aria-label="报告目录"><a href="#scope">范围与设置</a><a href="#table3">表3</a><a href="#table4">表4</a><a href="#table5">表5</a><a href="#impact">影响与修改建议</a><a href="#verification">验证证据</a><a href="#appendix">44项明细</a></nav>
<section id="scope"><h2>本次到底按哪一套设置检查</h2><p>表3是频率相对误差与振型相关性；表4是第一层水平位移的归一化均方根误差；表5是前五阶模态在作动坐标上的份额变化。表号由当前 <code>main.aux</code> 确认。稿件图6—9的四份PDF与 <code>figure/results_v2/PDF</code> 逐字节相同，因此可以沿该绘图目录的CSV追踪实际数据。</p>
<p>重新计算采用 <code>code/导师现场MATLAB全链演示_Fig06至Fig09</code> 的计算设置：15个物理自由度；El Centro地震输入乘0.40；扫频输入在40秒内由0.1 Hz线性增加至10 Hz；四阶Runge–Kutta固定步长积分，步长1/1024秒；每套输出40961个时刻。Craig–Bampton在整体消元模型中保留3个固定界面模态。</p>{modeltable}
<div class="callout"><strong>已发现正文与出图模型不同：</strong>正文第525行写两类模型均为Guyan 6个、Craig–Bampton 12个自由度；实际出图模型分别为6/9和5/8。出图入口对整体15自由度系统缩聚，Guyan质量和阻尼使用历史单侧处理；正文描述的是两子结构分别缩聚、双侧投影和缩聚后装配。因此，这次复算值准确回答“当前图对应哪些数值”，不能直接充当正文另一套模型的验证。</div>
<p class="small">本次没有换用正文声称的6/12自由度模型，也没有为匹配原表调整参数。图10的历史边界来源另见表5说明。</p></section>
<section id="table3"><h2>表3：第一类划分全部相符，第二类有5格不符</h2><p>频率误差表示降阶后的固有频率偏离完整模型多少；模态置信准则（MAC）表示同一组保留坐标上的振型有多相似，越接近1越相似。按当前稿件定义，Craig–Bampton只取保留物理坐标部分计算MAC。</p>
<div class="formula">频率误差 = |完整模型频率 − 降阶模型频率| / 完整模型频率 × 100%；<br>MAC = (两振型向量内积)² / (两向量平方范数的乘积)。</div>
<p>下表每格均为“原稿 → 当前模型复算值”。绿色表示按原表位数相符，浅橙色表示不符。</p>{table3}
<p>完整模型前两阶实算频率为 <strong>2.707425741915 Hz、9.328408686763 Hz</strong>。第二类Guyan对应3.222919493541 Hz、12.180519372231 Hz，故误差应为19.040%、30.574%。第二类Craig–Bampton的两阶误差为0.024%、0.108%，第二阶MAC应显示1.0000。</p>
<p><strong>含义：</strong>当前出图模型仍显示Craig–Bampton的频率误差较小，但原表对第二类模型的五个数字没有给出这套模型的实际结果。</p></section>
<section id="table4"><h2>表4：按首层响应与整段峰峰值归一化，21格不符</h2><p>归一化均方根误差（NRMSE）先把两条首层位移曲线的差平方、在指定时段取平均、再开平方，最后除以完整模型在全部40秒内的最大值与最小值之差。所有值均为百分数；扫频某一小段的分母仍用完整40秒的响应范围。</p>
<div class="formula">NRMSE = √[指定时段内误差平方的积分 / 该时段长度] / 完整模型全40秒响应峰峰值 × 100%。<br>扫频瞬时频率 f(t) = 0.1 + 0.2475t；由此把表中频率边界换为时间边界。</div>
<p>主核查采用表4明确写出的0.1、1.9、3.5、5.4、8.1、10 Hz边界；非采样时刻的边界值用线性插值后按梯形积分计算。这与稿件的积分定义一致。</p>{table4}
<p>相符的3格全部属于第一类Craig–Bampton扫频响应：0.1–1.9 Hz的“&lt;0.001”、1.9–3.5 Hz的0.008，以及3.5–5.4 Hz的0.003。其余21格不符。</p>
<details><summary>频率边界取整或积分方式能否解释这些差异</summary><p>已额外核对三种边界：表4字面边界、按正文2.7 Hz乘0.7/1.3/2/3、按当前实算基频2.707425741915 Hz乘相同比例；同时核对样本均方根代替时域积分的离散方式。三种频段解释均保持只有3/24格相符，无法解释原表的大部分差异。</p><p>例如第二类Guyan共振附近频段的积分NRMSE分别约为26.858%、26.703%、26.759%，均不是19.059%。频带定义会影响具体更正数值，后续改稿应明确采用哪一组边界。完整72条边界/方法记录见 <code>表4_频段边界与积分方式敏感性.csv</code>。</p></details>
<p><strong>含义：</strong>当前响应数据不支持“Craig–Bampton所有频段NRMSE均低于0.06%”。按表4边界，第一类最高频段约0.138%，第二类共振附近频段约0.074%。</p></section>
<section id="table5"><h2>表5：按现稿公式与当前响应模型，四个值全部不符</h2><p>这里的“模态份额”是稿件定义的一个模态分布指标：使用前5阶模态、地震影响向量在物理坐标1/6/11处为1，对振型作质量归一化，再按参与权重计算各物理坐标的份额。降阶振型先经各自变换矩阵恢复到完整15个坐标，并使用同一完整质量矩阵计算份额。</p>
<div class="formula">模态重分配比 ΔE = 两个作动坐标上 [(降阶后份额 − 完整模型份额) / 完整模型份额] 的总和。<br>第一类作动坐标为1和6；第二类为1和11。该公式没有绝对值，结果可以为负。</div>{table5}
<p>第一类Guyan的−0.0414表示按该公式求和后为负，并非把负号漏掉。它与正的0.3065在符号和大小上均不符。第一类两个方法的排序也与原表不同，因此不能继续沿用原文基于四个历史数值作出的排序论证。</p>
<div class="callout"><strong>与图10的证据边界：</strong>当前稿件图10旁的源码注释明确将它标为历史稳定域边界的绘图级复现。边界CSV/PDF不包含生成表5所需的完整质量矩阵、振型、恢复矩阵和模态归一化结果。本次四个复算值来自图6—9可执行模型，证明原表5与这套模型不符；尚不能证明它们就是生成图10历史边界那套模型的指标。</div>
<p><strong>含义：</strong>表5应先恢复与采用模型一致的计算来源，再用于解释稳定域；本次给出的是明确口径下的可核查结果。</p></section>
<section id="impact"><h2>这些发现对修改稿件有什么影响</h2><ol>
<li><strong>如果保留当前响应图：</strong>以上复算表可作为对应数值依据，同时把模型维数、整体缩聚/分别缩聚方式、Guyan投影处理和实际基频等正文描述改为与计算一致。原文基频约2.7 Hz尚可作为近似，第二频率9.1 Hz应与实算9.3284 Hz核对。</li>
<li><strong>如果保留正文的6/12自由度方案：</strong>应按该模型重新计算图和表，不能只把本报告数值抄入原表后认为图文已经一致。本次未建立这套不同模型。</li>
<li><strong>摘要、结果段和结论同步待复核：</strong>0.834%的最大频率误差应按当前模型核对为0.284%；第二类Guyan最大两阶频率误差30.574%；表4最大NRMSE约26.858%；Craig–Bampton最高频段0.138%使“所有情况小于0.06%”不成立。表5的0.3阈值和跨方法排序论述也需复核。</li>
<li><strong>表5与图10另行统一来源：</strong>恢复生成稳定域所用的模型和控制设置后，再计算模态指标并判断排序关系。不能从稳定边界外观反推表5数值。</li></ol>
<p>上述是本次核查支持的修改建议。本轮没有修改论文、重画图片、变更理论或继续图10参数搜索。</p></section>
<section id="verification"><h2>怎样证明本次检查可信</h2><div class="callout confirmed"><strong>本轮实际通过：</strong>四套MATLAB/Simulink仿真完成；四套时程与当前绘图CSV最大绝对差均不超过 {max_response:.3e} mm（验收门为1e-12 mm）；44项指标的MATLAB/Python最大差为 {max(error):.3e}（验收门为1e-8）；{len(manifest)}/{len(manifest)}项受保护输入的SHA-256不变。</div>
<p>本次仿真从复制的参数脚本重新生成质量、阻尼、刚度矩阵，运行源入口第1—7节计算。省去出图和读取参考CSV的末端验收节；实际出图CSV只在新计算结束后由独立核查器读取。频率用广义特征值问题重新求解；MAC和模态份额分别在MATLAB与Python实现，未直接使用历史表格结果。按显示位数逐格比较：频率误差和NRMSE保留3位小数，MAC和模态重分配比保留4位小数；“&lt;0.001”按不等式判断。</p>
<p>仿真日志保留原模型未连接Step/Chirp备用块等警告。实际激励通过计算入口接入的工作区输入驱动，四套仿真均成功结束，当前绘图数据比较通过；没有把“无警告”列作已通过项。</p>
<p><strong>数值验证通过与论文表格正确是两件事：</strong>前者说明这次复算可重复且实现相互吻合；后者由逐格比较决定，本次三表均未整表通过。</p>
<details><summary>文件与追溯入口</summary><ul>
<li>待核查稿件：<span class="path">{esc(PAPER/'elsevier/main.tex')}</span><br>本轮冻结SHA-256：<code>{source_hash}</code></li>
<li>主明细：<a href="results/逐单元格核查_44项.csv">逐单元格核查_44项.csv</a></li>
<li>独立实现：<a href="code/compute_metrics.py">Python指标计算代码</a>、<a href="code/compute_metrics_matlab.m">MATLAB指标计算代码</a></li>
<li>44项跨语言比较：<a href="results/MATLAB_Python_44项独立核对.csv">MATLAB_Python_44项独立核对.csv</a></li>
<li>频带解释：<a href="results/表4_频段边界与积分方式敏感性.csv">表4_频段边界与积分方式敏感性.csv</a></li>
<li>表5中间结果：<a href="results/表5_15个物理坐标模态份额.csv">表5_15个物理坐标模态份额.csv</a></li>
<li>源保护及数值验证：<a href="evidence/source_manifest.json">source_manifest.json</a>、<a href="evidence/numerical_validation.json">numerical_validation.json</a></li>
<li>新计算时程和模型位于：<span class="path">{esc(TEMP)}</span>；四套精确位置见 <code>results/本轮仿真与当前绘图数据比较.csv</code>。</li>
</ul><p>正文、表格和样式已全部内嵌；移动这个HTML或离线打开仍可完整阅读。上述证据链接是可选追溯入口，移动单个HTML后可能不再适用。</p></details></section>
<section id="appendix"><h2>44个单元逐项复算明细</h2><p>以下保留更多有效位，便于复查。相符判定始终按原表显示精度；这里的长小数不是要求论文增加位数。</p>{appendix}</section>
<footer>核查对象：当前 elsevier/main.tex 表3/4/5。执行日期：2026-09-06。交付状态：数值核查完成；原稿与原始出图数据未修改。原表不符项不登记为论文科学结论通过。</footer>
</main></body></html>'''
    path=OUT/'表3至表5数值准确性核查汇报.html';path.write_text(doc,encoding='utf-8')
    # Compact, editable companion for quick reading without a browser.
    md=['# 表3至表5当前出图设置数值核查','',
        '对象：260817/elsevier/main.tex。四套仿真重新运行通过，表3有11/16格相符，表4有3/24格相符，表5有0/4格相符。原稿未修改。','',
        '|表|划分|项目|方法|指标|原值|复算值|判定|','|---|---|---|---|---|---:|---:|---|']
    md += [f'|{r["table"]}|{r["division"]}|{r["item"]}|{r["method"]}|{r["metric"]}|{r["manuscript_value"]}|{r["rounded_value"]}|{r["status"]}|' for r in rows]
    md += ['',f'本轮仿真与当前绘图CSV最大绝对差：{max_response:.17g} mm；44项MATLAB/Python最大差：{max(error):.17g}；源保护{len(manifest)}/{len(manifest)}通过。',
           '', '表4主口径为表中明确标出的频率边界，按稿件积分公式和完整40秒响应峰峰值归一化。',
           '表5复算基于图6—9可执行模型及当前稿件公式；缺少与图10历史边界同模型的完整证据，不直接认定复算值可用于解释图10。',
           '正文写6/12自由度而当前出图为6/9和5/8；整体缩聚、Guyan单侧处理与正文另有差异。修改表格时必须同时核对模型和相关文字。',
           '', '完整解释及追溯见同目录HTML。']
    (OUT/'表3至表5数值核查简表.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(path),'numeric_validation':validation},ensure_ascii=False))

if __name__=='__main__':main()
