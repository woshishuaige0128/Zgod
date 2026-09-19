"""Build evidence-bound Chinese analysis and self-contained ELI5 HTML."""
import argparse,base64,hashlib,html,json,shutil
from pathlib import Path
import numpy as np
from scipy import linalg as la
from full15_model import ROOT,H

def main(work):
    results=ROOT/'results';figs=ROOT/'figures';results.mkdir(exist_ok=True);figs.mkdir(exist_ok=True)
    # Copy only completed outputs; MATLAB scratch exports remain in temp.
    for p in (work/'computed').iterdir():
        if p.suffix in ['.npz','.json']:shutil.copy2(p,results/p.name)
    for p in (work/'validation').glob('*.json'):
        if p.name in ['model_validation.json','theory_validation.json','matlab_validation.json']:shutil.copy2(p,results/p.name)
    shutil.copytree(work/'figures',figs,dirs_exist_ok=True)
    shutil.copy2(work/'latex/full15_error_theory.pdf',ROOT/'theory/full15_error_theory.pdf')
    d=json.loads((results/'dynamics.json').read_text('utf8'));r=json.loads((results/'responses.json').read_text('utf8'));c=json.loads((results/'critical_mechanism.json').read_text('utf8'))
    v=json.loads((results/'case_validation.json').read_text('utf8'));mat=json.loads((results/'matlab_case_validation.json').read_text('utf8'));assert v['status']==mat['status']=='PASS'
    v['matlab']='PASS';v['matlab_maximum_residual']=max(x['residual'] for x in mat['checks']);(results/'case_validation.json').write_text(json.dumps(v,indent=2),'utf8')
    r['status']='PASS';r['verification']='case_validation.json and matlab_case_validation.json; source model checks separate';(results/'responses.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf8')
    names={'Full15':'完整模型','Guyan':'Guyan','CB3':'CB（3个内部模态）'}
    def table(head,rows):return '| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n'
    modalrows=[];boundary=[];eqrows=[];drifts=[];tones=[];speeds=[];exceptions=[]
    for ds,D in d['divisions'].items():
        for m in [0,3]:
            mm=D['modal_convergence'][m];modalrows.append([ds,'Guyan' if m==0 else 'CB',mm['order'],*[f'{x:.6f}' for x in mm['frequency_error_pct'][:3]]])
        for name in names:
            b=D['step_refinement']['4'][name]['critical_interval_s'];boundary.append([ds,names[name],f'[{b[0]*1000:.6f}, {b[1]*1000:.6f}]'])
        for ns,entry in r['divisions'][ds]['earthquake'].items():
            for name in ['Guyan','CB3']:
                mr=entry['models'][name];eqrows.append([ds,f'{int(ns)*H*1000:.6f}',names[name],*[f'{x:.6f}' for x in mr['to_matched_full']['nrmse_range_pct']],f'{mr["to_original_passive_RK4"]["nrmse_range_pct"][1]:.6f}'])
                drifts.append([ds,f'{int(ns)*H*1000:.6f}',names[name],*[f'{x:.6f}' for x in mr['story_drift_to_matched_full']['nrmse_range_pct']]])
            for floor in range(3):
                g=entry['models']['Guyan']['to_matched_full']['nrmse_range_pct'][floor];cb=entry['models']['CB3']['to_matched_full']['nrmse_range_pct'][floor]
                if cb>g:exceptions.append(dict(division=int(ds),n=int(ns),floor=floor+1,Guyan=g,CB=cb))
        for entry in r['divisions'][ds]['tones']:
            for name,mr in entry['models'].items():
                f=mr['free_identification'];tones.append([ds,f'{entry["tau_s"]*1000:.6f}',f'{entry["frequency_hz"]:.6f}',names[name],f'{mr["measured_amplitude"][1]*1000:.6f}',f'{mr["measured_phase_deg"][1]:.5f}',f'{f["frequency_hz"]:.6f}',f'{f["decay"]:.6f}'])
        for e in r['divisions'][ds]['slow_chirp']['runs']:
            speeds.append([ds,f'{e["duration_s"]:.3f}',f'{e["sweep_rate_hz_s"]:.8f}',*[f'{e["models"][n]["quasisteady_complex_error_pct"]:.6f}' for n in names]])
    arr=np.load(results/'dynamics_arrays.npz');identity=[]
    for ds,D in d['divisions'].items():
        for n in D['selection']['representative_n']:
            for name in ['Guyan','CB3']:
                ref=arr[f'd{ds}_n{n}_Full15_frf'];err=arr[f'd{ds}_n{n}_{name}_frf']-ref;pred=arr[f'd{ds}_n{n}_{name}_frf_error_prediction']
                residual=float(la.norm(err-pred)/la.norm(ref));assert residual<=1e-10;identity.append(residual)
    summary=dict(earthquake_exceptions=exceptions,max_frf_identity_residual=max(identity),matlab_complete_record_max=v['matlab_maximum_residual'],
        theory_checks=1605,formal_response_checks=len(v['checks']),matlab_records=len(mat['checks']),
        max_refined_eq_nrmse=max(max(m['half_to_quarter']['nrmse_range_pct']) for D in v['step_refinement'].values() for m in D.values()))
    (results/'delivery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
    md='''# 原完整框架基准：两种划分的等时滞案例分析

## 结论与使用范围
本轮完成原15自由度完整框架、标准Guyan和保留3个内部模态的Craig–Bampton（CB）的统一虚拟反馈案例。两作动通道时滞相同。主比较保留物理刚度/阻尼延迟反馈，附加控制增益为零；原稿与封存旧案例保持。

划分二的CB收益明确：第二阶被动频率误差由7.549461%降到0.107785%；两个作动器均延迟2.9296875ms时，中间层地震缩聚NRMSE由0.984218%降到0.159095%。在完整模型选定的9.329600Hz定频加载后撤载案例中，中间层整段NRMSE由22.187473%降到2.133060%。三者使用同一激励、时滞、输出及算法。

论文主线建议为“内部运动近似 → 频响/极点偏移 → 响应和稳定边界偏差”。正常地震衡量实际给定输入；定频加载后撤载检验幅相、频率和衰减；等时滞稳定扫描检验失稳判断。敏感段慢扫频作为扫速收敛补充。

## 1. 比较的是哪一个结构
完整15坐标定义延迟反馈后，各缩聚基底一致投影。未作动的物理坐标由当前数值坐标提供，即明确的虚拟补充协调；质量在数值侧推进。本轮不声称两台硬件作动器已独立实现全部未作动接口的运动与力协调。

划分一保留ψ1/ψ6/ψ11/ψ4/ψ9/ψ14，Guyan为6阶，CB为9阶；两个通道ψ1/ψ6。划分二保留ψ1/ψ11/ψ4/ψ9/ψ14，Guyan为5阶，CB为8阶；两个通道ψ1/ψ11。保留全部内部模态后都恢复同一15坐标反馈系统。不同划分的延迟物理贡献不同，各自使用匹配的完整模型。

精度有两个参照：同一时滞、同一反馈的完整模型隔离缩聚误差；原无时滞无附加控制的完整框架RK4响应衡量最终总偏差。原被动完整框架本身没有作动器时滞失稳边界，边界精度针对明确加入虚拟反馈的匹配15坐标完整模型。

## 2. 为什么划分二更敏感
标准Guyan基底为T_G=[I;−K_cc⁻¹K_cr]（按保留/内部坐标重排），质量、阻尼、荷载均用合同投影。其静力恢复只包含约束运动。完整静力响应满足q_F−T_G q_G=[0;K_cc⁻¹ f_c]。划分一地震惯性荷载全部落在保留水平坐标，f_c=0，静力楼层响应精确；划分二删除中间层水平坐标，f_c≠0，遗漏了直接受载的内部变形。

划分二中层单位输入静力误差Guyan为−3.830976%，CB为−0.144589%。这一项解释低频恢复差异；动态误差还包含遗漏质量、阻尼和时滞耦合，不能仅用静力项替代。

CB增加固定界面内部模态。对称正定被动结构满足嵌套Ritz频率上界/收敛关系；它不保证每个有时滞输出指标都单调改善。以下是前三阶被动频率相对误差：

'''+table(['划分','方法','阶数','第一阶(%)','第二阶(%)','第三阶(%)'],modalrows)+'''
## 3. 时滞、稳定性与选点
基准步长h=1/1024s。先扫描完整模型，再应用预设选点规则，未按Guyan/CB最大差值选参数。原完整模型最后稳定整数点为划分一3.90625ms、划分二4.8828125ms，此处缩聚模型已出现失稳判断差异。因此正文响应采用三者共同稳定的2.9296875ms，不称它为完整模型临界附近。划分一另外保留正常1.953125ms；划分二正常点和共同稳定点重合，合并而不伪造第三个工况。

下面是h/4=1/4096s时首次网格失稳区间。端点为最后已确认稳定点和首次不稳定点，不是连续延迟的精确根或严格包含唯一越界的证明；h、h/2、h/4完整结果与再入可能性范围见dynamics.json。

'''+table(['划分','方法','首次网格失稳区间(ms)'],boundary)+'''
CB比Guyan更接近完整模型首次失稳位置，但CB3仍提前预测失稳。粗网格区间重合只表示该网格不能分辨，不表示恢复了精确边界；也不推论整个稳定域的包含关系或框架真实容许时滞被增加。指定步长下完整模型首次失稳网格点的极点频率约18.3/18.2Hz，超出原0.1–10Hz扫频，这不排除地震在该频段的成分。按该极点频率0.8–1.2倍窗口比较，输入输出留数非零，表明该根在所选通道可激励/可观测。

窗口FRF整体误差定义为100×sqrt(Σ频点Σ楼层|H_r−H_F|²/Σ频点Σ楼层|H_F|²)，使用等间距、等权的复频响采样，不只是幅值。共同稳定点下，划分一Guyan/CB为101.413%/3.980%，划分二为77.597%/22.915%。高频精度改善与边界预测改善一致；本轮未对临界根偏移与各遗漏耦合项做因果贡献分解。CB3在此高频区仍有明显截断误差，全部内部模态才严格恢复完整模型。

## 4. 地震响应：缩聚误差与最终总偏差
原40s地震输入不变。NRMSE=100×误差均方根/完整参照峰峰值。下表前三层参照同τ完整模型，最后一列参照原无时滞RK4完整框架；两种百分比不可相加。

'''+table(['划分','等时滞(ms)','方法','首层缩聚(%)','中层缩聚(%)','顶层缩聚(%)','中层总偏差(%)'],eqrows)+'''
划分二2.9296875ms时，完整延迟CR模型相对原被动RK4框架的中层总NRMSE为1.140147%，含时滞与CR/RK4积分差；同CR算法隔离的纯时滞偏差为1.139685%。Guyan总偏差1.700657%，CB总偏差1.290062%。这些数不是所有缩聚模型总偏差的理论下限，误差可部分抵消。

响应差值严格分解为缩聚差 + 完整模型时滞差 + CR/RK4积分差，直接核验闭合。若要比较平方误差贡献，还应包含交叉项；不能把三个NRMSE直接求和。本轮统一模型没有额外自由接口系统差异，所以未再把旧19坐标对15坐标的差当成缩聚误差。

各层层间位移角使用0.635m层高；下表参照同τ完整模型：

'''+table(['划分','等时滞(ms)','方法','第一层NRMSE(%)','第二层NRMSE(%)','第三层NRMSE(%)'],drifts)+'''
非单调结果：划分一2.9296875ms顶层Guyan/CB的NRMSE为0.022577%/0.022824%，CB略高0.000247个百分点。此处只报告固定步长的结果，不能据它宣称稳健的物理优劣；总体最大步长差也不能替代该项单独的误差预算。对应主导低阶衰减的CB改善不保证逐项成立。

## 5. 定频加载与撤载：理论与识别对照
频率取各延迟完整模型0.1–10Hz三楼层物理频响二范数的前两个峰。输入幅值1m/s²；三模型共同持续时间依据最慢衰减并通过相邻稳态窗口检查。撤载后保留完整延迟历史。表中幅相来自时程拟合，频率与衰减来自撤载后输出识别，不是将理论极点直接作为拟合输出。

'''+table(['划分','时滞(ms)','激励频率(Hz)','方法','中层幅值(mm)','中层相位(°)','自由频率(Hz)','衰减(s⁻¹)'],tones)+'''
所有幅相理论对照通过0.5%/0.5°，自由频率/衰减通过0.5%/2%；具体窗口、秩、拟合残差及预测值保存在responses.json。Guyan幅值低不能解释为阻尼过大：其相关衰减率更小而频率偏移明显，应由频率失谐、衰减变化和输入输出参与共同解释。输出识别使用零噪声确定性数值数据，精确吻合验证实现和理论，不等于试验识别精度。

## 6. 快扫频与慢扫频
保留原0.1–10Hz/40s快速扫频，避免只展示新激励。慢扫频覆盖完整模型第二峰的85%–115%，时长初值由完整模型带宽确定，扫速逐次减半。下表是各方法解调复幅值相对于自身准稳态FRF的整体误差，不是缩聚误差：

'''+table(['划分','扫频时长(s)','扫速(Hz/s)','Full误差(%)','Guyan误差(%)','CB误差(%)'],speeds)+'''
终止还要求相邻两次减速结果差≤1%，全部满足。划分二为满足Guyan窄峰的共同准稳态条件需约3858s；这是数值诊断时长，不作为硬件实时试验时长建议。正文优先定频撤载，慢扫频放补充材料。

## 7. 能否得到解析误差
零历史、给定离散积分下，状态表达为x_k=Σ A^(k−1−j)b u_j，输出y_k=O x_k。两种模型的有限卷积差给出任意采样地震或扫频记录的精确离散误差表达，非零历史另加O A^k x_0。谐波使用H_r(z)−H_F(z)乘输入，残余力形式为e=−Y_F Z_F⁻¹(f_F−Z_F T q_r)。理论与实际频响/时程差均核验。

“解析形式”指矩阵幂、传递算子与有限卷积表达，不代表任意实测地震存在简短初等函数公式。连续时滞特征方程一般为超越方程；本轮稳定边界采用已验证的离散全部极点网格扫描。连续根灵敏度公式已限定简单根等条件，算子导数已验证，根分支灵敏度未用于定量边界预测。

## 8. 核验与科学状态
'''+f'''- 模型与理论：1605项检查通过；六组同一地震动响应的MATLAB/Python最大相对差{summary['matlab_complete_record_max']:.4e}，阈值1e-9。
- 正式幅相、自由识别、扫速检查{summary['formal_response_checks']}项通过；频域残余力恒等最大归一化残差{summary['max_frf_identity_residual']:.4e}，阈值1e-10。
- 同一实际2.9296875ms、同一线性插值地震，h/2→h/4三层响应最大NRMSE为{summary['max_refined_eq_nrmse']:.6f}%；保留完整数值，未降低验收阈值来迁就结果。
'''+'''
- GPT Pro第三轮审读完整理论/代码正文并允许依条件推进；未执行新Python/MATLAB代码、未独立核查新附件哈希。第四轮已审读数值摘要并认可主线、定频撤载优先及网格边界用语；关于总偏差、同维度静力恢复、微小反例、FRF范数及高频因果范围的意见已落实。回复与实际读取范围另存pro_reviews；这不是独立复跑。
- 计算、科学图与旧新对照为本轮交付；原论文正文尚未替换。最终HTML采用内嵌图片，静态资源/导航检查与科学PDF实际渲染分开记录；本地HTML浏览器预览受既有安全限制，不声称浏览器视觉验收已完成。

## 9. 旧新图的对应与论文组织
按原TeX实际includegraphics顺序：旧6振型，7划分一地震，8/9划分二地震，10划分一快扫，11/12划分二快扫，13峰值层间角，14双延迟稳定域，15加权模态动能。HTML逐张并列新图与相关旧图，新增机理图明确无直接旧图。旧图与新图存在标准Guyan、接口/时滞实现、参照及部分输入差异，属于历史主题比较；当前三模型同工况比较才用于精度结论。旧15指标未直接沿用，当前用静力受载、内部模态收敛和关键频段误差解释机制。

正文建议依次：模型一致性与被动基线 → 内部模态/受载机制 → 等时滞稳定边界 → 定频加载撤载 → 既定地震工程误差。频响和独立误差图支撑前述各节，慢扫频/固定增益/网格细化作为补充。边界准确性与输入输出精度分别评价。
'''
    (ROOT/'CASE_ANALYSIS.md').write_text(md,'utf8')

    manifest=json.loads((figs/'figure_manifest.json').read_text('utf8'))
    oldroot=ROOT.parent/'case1_v1_standard_guyan_20260916/sources/original_figures'
    def embed(p):return 'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode('ascii')
    def img(name,alt):return f'<img loading="lazy" src="{embed(figs/"previews"/(name+".png"))}" alt="{html.escape(alt)}">'
    def figure(name,caption):return '<figure>'+img(name,caption)+'<figcaption>'+caption+'</figcaption></figure>'
    def htmltable(head,rows):return '<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    diagram='''<svg viewBox="0 0 960 245" role="img" aria-label="同一完整楼房，Guyan只保留约束变形，CB增加内部摆动"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#526575"/></marker></defs><rect x="10" y="10" width="940" height="225" rx="24" fill="#f1f5fa"/><g stroke="#228833" stroke-width="7" fill="none"><path d="M90 190V50H220V190M90 100H220M90 145H220M60 195H250"/></g><text x="155" y="220" text-anchor="middle">同一栋完整楼</text><path d="M270 120H355" stroke="#526575" stroke-width="3" marker-end="url(#arrow)"/><g stroke="#EE6677" stroke-width="6" fill="none"><path d="M405 190L420 145L435 100L450 50M530 190L545 145L560 100L575 50M420 145H545M435 100H560M450 50H575"/></g><text x="493" y="220" text-anchor="middle">Guyan：用静力形状带着动</text><path d="M612 120H675" stroke="#526575" stroke-width="3" marker-end="url(#arrow)"/><g stroke="#4477AA" stroke-width="6" fill="none"><path d="M710 190Q770 145 740 100Q705 65 760 50M835 190Q895 145 865 100Q830 65 885 50M735 145H860M740 100H865M760 50H885"/></g><text x="809" y="220" text-anchor="middle">CB：再补回内部摆动</text></svg>'''
    pairs=[];mapping=[]
    for f in manifest:
        old=f['old_figure'];old=[] if old is None else old if isinstance(old,list) else [old]
        oldimgs=''.join('<figure><h4>原稿图'+str(i)+'</h4><img loading="lazy" src="'+embed(oldroot/f'fig{i:02}.png')+'" alt="原稿图'+str(i)+'"><figcaption>历史原图；计算条件与右侧新案例不同。</figcaption></figure>' for i in old)
        if not oldimgs:oldimgs='<div class="new"><strong>新增的解释或验证图</strong><p>原稿没有直接对应图。</p></div>'
        pairs.append('<article class="pair"><h3>'+html.escape(f['name'])+'</h3><p>'+html.escape(f['caption'])+'</p><div class="twocol"><div>'+oldimgs+'</div><figure><h4>本轮统一模型</h4>'+img(f['name'],f['caption'])+'</figure></div></article>')
        mapping.append(dict(new=f['name'],old=old,caption=f['caption'],comparison='historical topic comparison; conditions differ'))
    (results/'historical_figure_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),'utf8')
    body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Doctor Bego · 完整框架等时滞案例</title><style>
    :root{--blue:#4477AA;--red:#EE6677;--green:#228833;--ink:#172b40}*{box-sizing:border-box}body{font-family:"Microsoft YaHei",sans-serif;color:var(--ink);background:#f5f7fa;margin:0;line-height:1.65}main{max-width:1180px;margin:auto;padding:28px}header{padding:42px 0 20px}h1{font-size:clamp(28px,4vw,48px);line-height:1.3}h2{font-size:30px;margin-top:12px}h3{overflow-wrap:anywhere}p{max-width:960px}nav{display:flex;gap:14px;flex-wrap:wrap}a{color:#285d8e}section{background:white;padding:32px;border-radius:20px;margin:26px 0;box-shadow:0 3px 16px #14283b09}.kicker{font-size:14px;letter-spacing:2px;color:#526575}.lead{font-size:22px}.cards,.twocol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.cards{grid-template-columns:repeat(3,minmax(0,1fr))}.card{padding:22px;border-radius:14px;background:#f1f5fa}.card b{display:block;font-size:32px}.blue{color:var(--blue)}.red{color:var(--red)}.green{color:var(--green)}figure{margin:18px 0;min-width:0}img{width:100%;height:auto;display:block;background:#fff}figcaption{font-size:14px;color:#506071;padding:10px 2px}.note{border-left:4px solid var(--blue);padding:12px 18px;background:#f1f6fb}.pair{border-top:1px solid #ddd;padding:18px 0}.new{padding:35px;background:#f5f7fa;border-radius:12px}.table{overflow:auto}table{border-collapse:collapse;font-size:14px;white-space:nowrap;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #dce3e9}summary{cursor:pointer;font-size:22px;font-weight:bold;padding:12px}svg{width:100%;height:auto}svg text{font-family:"Microsoft YaHei",sans-serif;font-size:19px}footer{font-size:13px;color:#526575;padding:20px}.status{display:inline-block;background:#e9f4ed;padding:5px 12px;border-radius:18px}.formula{font-family:serif;font-size:24px;overflow-wrap:anywhere;padding:16px;background:#f5f7fa}@media(max-width:760px){main{padding:12px}section{padding:18px}.cards,.twocol{grid-template-columns:1fr}h2{font-size:24px}.lead{font-size:19px}}@media print{section{break-inside:avoid;box-shadow:none}details{display:block}nav{display:none}}
    </style></head><body><main><header><div class="kicker">DOCTOR BEGO · 2026-09-16 · 科研案例说明</div><h1>CB 补回了什么？<br>同一栋楼、相同的时滞，直接比较。</h1><p class="lead">划分二的差异已经显现。现在能说明误差来自哪里，也能把公式预测与实际曲线对上。</p><span class="status">计算与本地核验完成</span><nav><a href="#mechanism">为什么</a><a href="#response">看曲线</a><a href="#boundary">看稳定性</a><a href="#earthquake">看工程误差</a><a href="#pairs">全部新旧图</a><a href="#evidence">核验说明</a></nav></header>
    <section id="mechanism"><h2>1　Guyan 省掉了独立的内部运动</h2>'''+diagram+'''<p class="lead">划分二把中间层水平运动放进了被消去的坐标。那里仍然受地震惯性力，所以只用静力形状恢复，会漏掉一部分变形和摆动。</p><div class="cards"><div class="card">第二阶频率误差<b><span class="red">7.55%</span> → <span class="blue">0.108%</span></b>Guyan → CB，划分二</div><div class="card">中层静力误差绝对值<b><span class="red">3.83%</span> → <span class="blue">0.145%</span></b>直接受载恢复</div><div class="card">CB 内部模态<b class="blue">保留 3 个</b>继续增加可恢复完整模型</div></div><p class="note">统一模型假定：未作动坐标由当前数值状态提供虚拟协调。两台作动器的硬件实现仍需单独论证。</p></section>
    <section id="response"><h2>2　让完整模型告诉我们该激励哪里</h2><p class="lead">完整模型第二共振附近，Guyan 摆错了频率；CB 的幅值、相位和撤载衰减更接近完整模型。</p><div class="cards"><div class="card">共同等时滞<b>2.930 ms</b>两个通道、三种模型相同</div><div class="card">完整模型选定频率<b>9.330 Hz</b>先看参考模型，再选工况</div><div class="card">中层整段响应误差<b><span class="red">22.19%</span> → <span class="blue">2.13%</span></b>加载＋撤载，峰峰值NRMSE</div></div>'''+figure('17_steady_free_detail','划分二中间层：左为稳态最后3周期，右为撤载后自由响应。绿：完整模型；红：Guyan；蓝：CB。两列上排同纵轴，下排直接画误差。')+'''<p>撤载后相关频率：完整 9.333 Hz，Guyan 10.034 Hz，CB 9.342 Hz。理论预测与响应识别已逐项核验。</p></section>
    <section id="boundary"><h2>3　还要看“什么时候判错失稳”</h2><p class="lead">CB 的失稳边界预测更接近完整模型。保留 3 个内部模态，仍没有完全消除边界偏差。</p>'''+figure('06_delay_boundary_refinement','左划分一、右划分二；横轴表示步长细化倍数。线段是首次网格失稳区间，不是精确连续临界值。')+htmltable(['划分','模型','h/4首次网格失稳区间(ms)'],boundary)+'''<p class="note">完整模型临界前的点上，部分缩聚模型已经判为失稳。共同稳定响应退到2.930 ms，因此不把它称为完整模型的近临界点。约18 Hz的失稳运动还超出了原快扫频范围。</p></section>
    <section id="earthquake"><h2>4　原来的地震记录，也要如实比较</h2><p class="lead">划分二中间层：缩聚误差降低约84%。时滞本身的影响仍然保留。</p><div class="cards"><div class="card">同时滞完整模型为参照<b><span class="red">0.984%</span> → <span class="blue">0.159%</span></b>隔离缩聚造成的误差</div><div class="card">原无时滞完整框架为参照<b><span class="red">1.701%</span> → <span class="blue">1.290%</span></b>包含时滞影响的总偏差</div><div class="card">划分一的例外<b>0.0226% → 0.0228%</b>顶层CB略高；不隐藏反例</div></div>'''+figure('07_earthquake_division2','划分二，三楼层真实地震响应与同τ缩聚误差。小误差放到独立坐标中，原曲线幅度保持。')+'''<p>两个百分比参照不同，不能相加。划分一的差异较小；论文应解释这种差别，不要求每个指标都由CB胜出。</p></section>
    <section id="formula"><h2>5　公式能预测误差，慢扫频只是验证手段</h2><div class="formula">输出误差 =（CB 或 Guyan 的传递函数 − 完整模型传递函数）× 输入</div><p class="lead">定频可直接预测幅值和相位；给定地震、扫频记录可用有限卷积计算每一步误差。</p><p>这里是精确离散矩阵表达，不是把任意地震写成一个简短初等函数。连续时滞的临界值仍需解特征方程。</p>'''+figure('13_prediction_identification','理论预测与撤载响应识别：点接近灰色一致线。左划分一、右划分二；上为频率，下为衰减率。')+'''<p class="note">慢扫频已做扫速减半检查。划分二需要约3858 s才满足三种模型共同的准稳态条件；正文采用约25 s的定频加载＋撤载更直接，慢扫频放补充。</p></section>
    <section id="pairs"><details><summary>6　逐张查看新图与历史原图（点击展开）</summary><p>对应关系按原稿TeX实际图注核对。旧新条件不同，下面是历史主题对照；当前同工况的三条曲线才用于判定缩聚精度。新增图明确标注。原稿图1–5为框架/模型/输入信息，未替换；旧图15的动能指标未直接沿用。</p>'''+''.join(pairs)+'''</details></section>
    <section id="evidence"><details><summary>7　数值表与核验范围（点击展开）</summary><h3>完整地震误差表</h3>'''+htmltable(['划分','时滞(ms)','方法','首层缩聚%','中层缩聚%','顶层缩聚%','中层总偏差%'],eqrows)+'''<h3>慢扫频收敛</h3>'''+htmltable(['划分','时长(s)','扫速(Hz/s)','Full误差%','Guyan误差%','CB误差%'],speeds)+f'''<p>模型/理论1605项，正式幅相/自由识别/扫速84项，两种划分×三种模型的六组MATLAB地震响应均通过。MATLAB与Python最大相对差 {summary['matlab_complete_record_max']:.3e}。步长减半至四分之一步长的最大地震NRMSE差 {summary['max_refined_eq_nrmse']:.6f}%。</p>'''+'''<p>GPT Pro审读过理论与代码正文并提出修改；没有执行本地计算。最终结果的文字复核另存审查记录。科学图PDF实际渲染查看；HTML做结构/内嵌资源/导航静态核验，浏览器本地HTML视觉验收受既有安全限制。</p><p>详细推导：theory/full15_error_theory.pdf；完整解释：CASE_ANALYSIS.md；原始结果与全部指标：results；可复现入口：README.md。原稿和旧案例保持。</p></details></section><footer>本报告为独立单文件；全部图片内嵌。新旧图只作有明确条件说明的历史比较。原论文尚未替换。</footer></main></body></html>'''
    report=ROOT/'完整框架等时滞案例_图解汇报.html';report.write_text(body,'utf8')
    print(json.dumps(dict(report=str(report),figures=len(manifest),bytes=report.stat().st_size,summary=summary),ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);main(p.parse_args().work)
