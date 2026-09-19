from pathlib import Path
import csv,html,json,shutil
import numpy as np
from scipy.io import loadmat

OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1];RES=OUT/'results';TMP=ROOT/'temp/full_order_consistency_20260916'
find=json.loads((RES/'findings.json').read_text('utf-8'));checks=json.loads((RES/'algebra_checks.json').read_text('utf-8'))
matfile=loadmat(TMP/'matlab_algebra.mat',simplify_cells=True);mat=matfile['rows'];mr=[]
for row in mat:
    v={k:(value.tolist() if isinstance(value,np.ndarray) else value) for k,value in row.items()};mr.append(v)
assert len(mr)==2 and all(max(r[k+'_join_residual'] for k in ['M','C','K'])<1e-10 for r in mr)
delayrows=list(matfile['delayRows'])
for py,ma in zip(find['delay_operator_audit'],delayrows):
    for key in ['C_delay_projection_difference','K_delay_projection_difference']:assert abs(py[key]-ma[key])<1e-10
(RES/'matlab_source_checks.json').write_text(json.dumps(dict(status='PASS',divisions=mr,delay_operator_crosscheck=delayrows,new_time_integrations=0),ensure_ascii=False,indent=2),'utf-8')
shutil.copy2(TMP/'matlab_algebra.mat',RES/'matlab_algebra.mat')
decomp=list(csv.DictReader((RES/'error_decomposition.csv').open(encoding='utf-8-sig')))
baseline=list(csv.DictReader((ROOT/'cases/case1_v1_standard_guyan_20260916/results/standard/metric_errors.csv').open(encoding='utf-8')))
def esc(s):return html.escape(str(s))
def table(head,rows):return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>'
def coords(a):return ', '.join('ψ'+str(x) for x in a)
def section(id,title,body):return f'<section id="{id}"><h2>{title}</h2>{body}</section>'
def num(x):return f'{float(x):.6g}'

sources=[
('现稿原完整框架、几何、Rayleigh阻尼','sources/manuscript.tex',459,470),
('两种划分的局部坐标、缺失协调与模型阶数','sources/manuscript.tex',475,519),
('精度案例无控制、RK4与输入设置','sources/manuscript.tex',524,535),
('缩聚后共享坐标装配','sources/manuscript.tex',170,182),
('物理恢复先延迟保留坐标、模态当前更新','sources/manuscript.tex',308,326),
('按缩聚物理矩阵列分配时滞、惯性数值推进','sources/manuscript.tex',331,366),
('LQR及CR离散特征矩阵','sources/manuscript.tex',368,413),
('完整框架标准与旧Guyan矩阵及CB构造','sources/full_frame/rths_reduce.m',1,68),
('原Simulink负载投影与三楼层恢复','sources/full_frame/rths_simulate.m',1,46),
('当前划分二局部矩阵、装配及共同反馈','sources/delayed/delay_model.py',12,125),
('当前时滞矩阵、CR推进与物理端恢复','sources/delayed/delay_model.py',127,199),
('历史划分一局部质量、刚度及独立10%阻尼','sources/historical/PDmonicanshu2.m',91,155),
('历史划分一数值侧坐标长度与矩阵尺寸不一致','sources/historical/New_Ns2.m',1,32),
]
(OUT/'evidence_map.json').write_text(json.dumps([dict(claim=a,file=b,start=c,end=d) for a,b,c,d in sources],ensure_ascii=False,indent=2),'utf-8')

intro='''<p class="lead">本轮已完成两种划分的模型一致性核查。结论是：<strong>标准 Guyan 的修正成立，但此前无时滞与有时滞结果还不能组成“只改变时滞”的公平对照。</strong>两者同时改变了接口协调、时滞恢复路径、控制器和积分方法。</p>
<div class="callout"><strong>现在可以确认：</strong>完整框架直接缩聚时，CB零内部模态等于标准Guyan，保留全部内部模态可恢复原15自由度框架。<br><strong>现在需要解决：</strong>现稿局部装配只协调两个作动坐标；划分一和二分别还缺3、4个协调约束。有时滞下，恢复与时滞算子的顺序还会改变闭环。<br><strong>建议下一步：</strong>先选定并推导统一的完整框架等时滞反馈路径，再做缩聚对照；本轮仅提交修订建议，未修改理论或运行新响应。</div>
<p>本轮实际完成134项Python代数与既有时程检查、MATLAB独立源矩阵检查和72条等时滞误差分解。29个来源及旧两个案例的450个交付文件在交付复核中保持原哈希。报告已通过离线移动、桌面、窄屏和10页打印检查。正式案例、临界时滞精细定位和新的五组图均未启动。</p>'''

scope=section('scope','1．本轮范围与判断标准','''<p>用户已确定：原15自由度完整框架是最终精度目标；只讨论两个作动器等时滞；两种划分都比较，重点解释划分二。本轮执行模型核查、极限检查、既有结果分解与修正建议。</p><p><strong>代数检查通过</strong>表示等式、坐标映射与已有数值一致；<strong>模型一致性尚未闭合</strong>表示两条现有路线尚未成为同一个完整框架闭环的不同阶近似。报告不以“CB必然更好”为验收条件。</p><p>保持来源的几何、等效质量参数1491500 kg/m³、完整框架前两阶5% Rayleigh标定不变。这里是沿用既有模型参数，不是重新认定材料密度。所有新检查在独立审计目录和temp中执行，没有时间积分循环。</p>''')

contract=section('contract','2．两套计算实际比较的是什么',table(['项目','无时滞全框架精度路线','现有有时滞子结构路线'],[
['结构起点','已装配且协调的15自由度框架','物理与数值子结构分别缩聚，再共享两作动坐标'],
['划分一阶数','完整15；标准Guyan6；CB9','现稿规定Guyan6、CB12；全部局部坐标为18'],
['划分二阶数','完整15；标准Guyan5；CB8','实际已有Guyan6、CB12、全内部模态19、参考Full15'],
['CB模态数','整个框架保留3个内部模态','每个子结构保留3个，共增加6个'],
['接口与恢复','每个原坐标只有一个恢复值，原连接关系保留','只共享两作动坐标，其余共同坐标两侧分别恢复'],
['控制','零调节器力','现有划分二四模型共用一组两通道LQR增益'],
['时间推进','固定步长RK4（ode4）','CR递推，物理弹性/阻尼反力选列延迟，惯性数值推进'],
['时间步长与初值','1/1024 s；零初值；40 s','同样步长、零初值及负时间零历史；40 s'],
['输入','El Centro×0.40，原0.02 s记录线性插值；0.1—10 Hz扫频','同一输入离散记录；本轮只复核已有等时滞点'],
['地震荷载','完整质量矩阵形成荷载后投影','局部质量形成荷载再装配；全面协调后荷载加和已核验'],
['阻尼','标准Guyan、CB均由同一完整C投影','当前划分二统一完整框架Rayleigh系数；历史局部脚本使用各自10%阻尼'],
['既有实现覆盖','两种划分已有标准与旧实现结果','完整已验证延迟响应仅有划分二；划分一本轮只做代数诊断']
])+'''<p>这些差别在现稿第517、519、524、535行及第2—3节中有直接说明。它们包括旧Guyan构造差异，也包括不同研究设置，不能统一解释为“积分误差”或“代码错误”。现稿按各装配模型形成LQR设计模型，当前延迟包采用固定共同增益；报告将这一设置差异单列。</p>''')

coordrows=[]
for r in find['local_assembly']:
    coordrows.append([f"划分{r['division']}",coords(r['physical']),coords(r['numerical']),coords(r['actuated']),coords(r['uncoordinated']),f"{len(r['physical'])}+{len(r['numerical'])}−2={r['uncondensed_order']}"])
interface=section('interface','3．哪些界面条件没有保留',table(['划分','物理坐标','数值坐标','两作动坐标','未协调的共同坐标','只共享两坐标的阶数'],coordrows)+'''
<p>ψ₁、ψ₆、ψ₁₁分别为首层、中间层和顶层水平位移，其他ψ为节点转角。划分一遗漏的是3个转角协调；划分二遗漏中间层位移及3个转角协调。</p>
<p>相同的坐标编号在物理侧与数值侧各有一个变量。只共享两作动坐标时，剩余两侧变量独立：局部内部方程会各自求解，但没有额外乘子或装配关系强制两侧位移相等及传递原有界面作用。因此19自由度不是原15自由度模型的“更精细版本”。</p>
<div class="formula">完整协调映射 J：　x<sub>局部</sub> = J x<sub>完整</sub><br>Jᵀ M<sub>局部</sub> J = M<sub>完整</sub>，　Jᵀ C<sub>局部</sub> J = C<sub>完整</sub>，　Jᵀ K<sub>局部</sub> J = K<sub>完整</sub></div>
<p>J把一个完整框架坐标复制到对应的两侧局部变量；本轮对两种划分实际检查了约束秩、上述三个矩阵及荷载等式。划分一施加全部5个共有坐标协调、划分二施加全部6个协调后，都恢复原15自由度框架。这里只验证数学关系，没有把额外协调加入现有试验模型，也不据此声称两个作动器能够物理实现这些约束。</p>''')

limits=section('limits','4．Guyan与CB的极限检查结果',table(['检查','划分一','划分二','含义'],[
['全框架：CB零内部模态＝标准Guyan','通过','通过','两方法使用同一静态约束子空间'],
['全框架：CB全部内部模态恢复原15','通过（9个内部模态）','通过（10个内部模态）','矩阵、荷载与代数频域响应恒等检查通过'],
['局部装配：CB零内部模态＝标准Guyan','通过','通过','只能说明局部近似的零模态极限'],
['恢复全部独立局部坐标','18坐标系统','19坐标系统','恢复原15还需要额外界面协调'],
['普通质量正定CB全模态构造','有前提缺口，见下文','通过，并与已存19矩阵相符','不能将全部坐标恢复与普通全有限模态展开混为一谈']
])+'''<h3>划分一新增发现：数值侧有一个零质量坐标</h3><p>按现稿几何、坐标表以及历史MPrt集中质量分配构造数值侧剩余质量时，ψ₇的剩余质量为0。18坐标局部系统的质量秩为17；数值侧8个被缩聚坐标的无阻尼广义特征值包含7个有限值和1个无穷值。因此，不能直接对该M<sub>cc</sub>调用要求正定质量的全模态质量归一化流程。</p><p>这是一项明确质量分配下的诊断结果，不是已完成的划分一有时滞仿真。完整15框架的质量仍正定。保持全部内部坐标的可逆基底可证明18坐标装配关系；要形成统一的普通CB模态链，还需审查质量分配或含零质量坐标的方程处理方式。</p><p>本轮没有给零质量坐标添加小质量，没有修改参数以使检查通过。历史New_Ns2.m还存在坐标列表14项而矩阵11阶的不一致，不能直接当成现稿划分一数值侧的可运行来源。</p>''')

d=find['delay_operator_audit'][1]
delaysection=section('delay','5．有时滞时，全部模态仍不足以自动统一闭环',f'''<p>现稿及当前代码先构造缩聚矩阵，再使作动坐标对应列带时滞；物理恢复使用“延迟保留坐标＋当前内部模态”。这是一种明确的反馈路径定义。将同一个物理系统换成不同坐标时，时滞算子也需要随之变换。</p>
<div class="formula">先投影再按缩聚坐标选列：　Wᵀ K<sub>P</sub> W D<sub>q</sub>(z)<br>先按物理坐标选列再投影：　Wᵀ K<sub>P</sub> D<sub>x</sub>(z) W</div>
<p>W是完整、可逆的坐标变换；K<sub>P</sub>是物理部分刚度；D<sub>x</sub>、D<sub>q</sub>分别在物理坐标和变换后坐标中延迟同名作动分量。两式一致要求相关作用下的算子相容；一般不能直接把两个D都设成同样的对角选列规则。</p>
{table(['代数测试（划分二）','零时滞','等时滞3.90625 ms、9 Hz'],[['刚度两种顺序的相对矩阵差',num(find['delay_operator_audit'][0]['K_delay_projection_difference']),num(d['K_delay_projection_difference'])],['阻尼两种顺序的相对矩阵差',num(find['delay_operator_audit'][0]['C_delay_projection_difference']),num(d['C_delay_projection_difference'])]])}
<p>9 Hz仅用于检验一个矩阵恒等式，不是本轮选定的新激励。上述数值是固定坐标表示下的算子差异，用来证明两种顺序不等价，不能作为响应误差百分比。</p>
<div class="callout"><strong>对上一轮解释的修正：</strong>“全内部模态19与Full15的差异就是接口协调误差”只在匹配的零时滞设置下可作此解释。在非零时滞下，它还包含延迟恢复与选列约定的差异。现有19模型可保留为“当前恢复约定下的全内部模态参考”，不能直接替代原物理坐标定义的完整闭环。</div>''')

rows=[]
for ex in ['eq','chirp']:
    for model in ['Guyan6','CB12']:
        r=next(x for x in decomp if x['input']==ex and x['model']==model and x['floor']=='2' and float(x['delay_ms'])==3.90625)
        rows.append(['地震' if ex=='eq' else '扫频',model.replace('6','').replace('12',''),num(r['same_interface_nrmse_percent']),num(r['same_delay_full15_nrmse_percent'])])
componentrows=[]
for r in decomp:
    if r['floor']=='2' and float(r['delay_ms'])==3.90625:
        componentrows.append(['地震' if r['input']=='eq' else '扫频',r['model'].replace('6','').replace('12','')]+[num(r[k]) for k in ['reduction_fixed_scale_percent','reference_model_fixed_scale_percent','delay_fixed_scale_percent','control_and_integrator_fixed_scale_percent','total_to_original_passive_nrmse_percent']])
decomposition=section('decomposition','6．既有等时滞响应的误差分解',f'''<p>为使用户最初的原完整框架目标也进入分解，本轮保留四种响应：缩聚输出y<sub>r</sub>、当前全内部模态参考y<sub>U</sub>、当前同延迟完整框架参考y<sub>F</sub>，以及最初无控制RK4完整框架输出y<sub>原</sub>。</p>
<div class="formula">y<sub>r</sub><sup>τ</sup> − y<sub>原</sub><br>= (y<sub>r</sub><sup>τ</sup> − y<sub>U</sub><sup>τ</sup>)<br>+ (y<sub>U</sub><sup>τ</sup> − y<sub>F</sub><sup>τ</sup>)<br>+ (y<sub>F</sub><sup>τ</sup> − y<sub>F</sub><sup>0</sup>)<br>+ (y<sub>F</sub><sup>0</sup> − y<sub>原</sub>)</div>
<p>四项依次是：①当前恢复约定下的缩聚偏差；②参照模型差异（接口协调及延迟恢复路径）；③同一完整框架CR闭环的时滞影响；④相对于原无控制RK4基线的控制/积分设置合并差异。第四项不能在没有额外对照的情况下单独归给控制器或积分器。</p>
<p>实际复核6个等时滞组合×2输入×2缩聚方法×3楼层，共72条；直接使用封存的时程，未进行新积分。响应分解最大归一化残差 {find['decomposition']['max_response_identity_residual']:.3e}；平方误差包含交叉项后的闭合残差 {find['decomposition']['max_squared_energy_identity_residual']:.3e}。复算原指标的差为0。</p>
<p><strong>各项NRMSE不能相加。</strong>不同误差分量可能相互抵消；CSV保留各分量、总量和交叉项。分量统一用原无控制完整框架全记录峰峰值归一化；另列原报告各自参考的指标，避免混淆。</p>
<h3>等时滞3.90625 ms的中间层分量</h3><p>以下全部使用同一个原无控制完整框架尺度，单位均为%。分量大小显示影响来源，总误差仍由原始响应直接计算。</p>{table(['输入','方法','缩聚','参照模型','时滞','控制/积分','总误差'],componentrows)}
<h3>已有图不能直接支撑“CB更接近原完整框架”</h3><p>下表均为划分二、两个通道3.90625 ms、中间层全记录NRMSE；两列分别按各自参考的峰峰值归一化。</p>{table(['输入','方法','对当前全内部模态19，%','对同时滞完整15，%'],rows)}
<p>CB相对19参考的偏差明显更小，但相对当前Full15参考的偏差略大。这个结果完整保留。通过更换纵轴、加大时滞或延长激励，不能替代对参照系统与反馈路径的统一。</p>
<p>4.8828125 ms等时滞的失稳记录只用于代数分解闭合检查，不能与稳定工况一起按有限时长NRMSE评价精度。</p>''')

historicalrows=[]
for r in mr:historicalrows.append([f"划分{int(r['division'])}",num(r['source_mass_difference']),num(r['source_stiffness_difference']),num(r['source_damping_difference'])])
recommend=section('recommend','7．修正建议及受影响位置',table(['问题类别','已经查明的事实','建议与影响'],[
['实现修正','旧Guyan精度代码未统一采用合同质量/阻尼投影；标准版本已通过核验','后续使用标准Guyan；更新现稿第519行及依赖旧数值的表、图、摘要与结论'],
['研究设置不同','全框架直接缩聚与两通道局部装配是现稿明确的两种设置','不把两套结果拼成单因素时滞趋势；统一模型表、参照命名与输入输出'],
['接口理论','第182、485行明确未恢复未作动界面协调','若目标是同一原框架，需要重新说明这些坐标的运动协调与反力传递；影响eq:assembled-reduced、坐标表及局部阶数'],
['延迟路径理论','先投影再选列与先物理选列再投影不等价','统一物理信号路径并同步投影所有延迟/控制/输出算子；影响eq:delay-recovery、eq:delayed-eom、eq:z-matrix'],
['控制与积分','原精度链无控制/RK4；当前延迟链有共同反馈/CR','主比较同控制、同积分；原无控制框架仍作为工程目标另列，分离其基线变化'],
['划分一局部质量','既有集中质量分配产生一个数值侧零质量坐标','审查质量分配或描述方程处理，保留科学依据；不添加任意小质量'],
['案例选择','CB并非对所有现有参照都优于Guyan','先统一完整闭环，再以频响、极点、定频/自由及地震响应评价实际精度收益']
])+'''<h3>建议优先评估的一条统一数值路线</h3><p>先在原15自由度框架的物理坐标中明确两个作动通道的等时滞力路径、共同反馈和输出；随后对质量、无时滞项、每个延迟项、荷载及输出一致投影，分别形成Guyan和CB近似。这样可以把CB全空间恢复原定义闭环作为必检极限。</p><p>这是一项待讨论的理论/实现修订建议，本轮没有实施。它是否仍对应现稿规定的物理两作动器试验，需要独立说明其余界面的可实现协调或近似；不能把数值约束当成额外实际作动能力。</p><h3>历史局部脚本与当前统一几何/阻尼的实际对照</h3>'''+table(['来源','质量相对差','刚度相对差','阻尼相对差'],historicalrows)+'''<p>MATLAB直接执行冻结源脚本的矩阵定义前缀并核对。划分二刚度差来自已记录的两个额外转角对角项；两脚本均按自身局部模态采用10%阻尼。当前诊断按现稿第470行的完整框架统一Rayleigh系数重建。这些是明确的来源差异，不是本轮擅自更新原件。</p>''')

status=section('status','8．完成状态、验证与后续案例',f'''<p><strong>本轮完成：</strong>两种划分模型对照、接口约束及恢复极限、延迟算子次序检查、历史局部矩阵来源核对、72条既有时程分解、报告及交付保护。134项检查最大归一化残差为 {checks['max_normalized_residual']:.3e}，标准为10⁻¹⁰。</p>
<p><strong>尚未闭合：</strong>以原完整框架为同一等时滞闭环基准的理论与实现统一；划分一局部质量问题；对实际两作动器边界协调的说明。未完成新理论证明、Pro审查、临界值精细定位或新响应仿真。</p>
<p><strong>下一步应先决定模型路线。</strong>模型闭合后，再按“频响与误差→模态保留数→等时滞极点/稳定边界→定频与自由响应→地震工程误差”的顺序组织五组图。频段、时长与代表时滞由统一后的参考动力学确定；本轮不指定这些新数值。</p>
<p><strong>本轮一次检查迭代：</strong>审计程序初次采用稿件的数值保留坐标集合顺序，与封存代码交换了ψ₄/ψ₆的位置，导致直接矩阵比较失败。按原实现明确重排后，矩阵一致性通过。容差保持10⁻¹⁰，原案例矩阵及数据没有改变。</p>
<p><strong>复现：</strong>使用完整Python路径运行审计目录code/audit_models.py；MATLAB运行code/VERIFY_ALGEBRA.m并指定temp输出；最后运行code/build_report.py。脚本只检查代数或读取既有响应，不调用仿真。既有响应的绝对路径、SHA-256和来源副本见source_manifest.json。报告浏览器与打印验收见results/report_qa.json。</p>''')

evidence=section('evidence','9．证据入口',table(['证据','冻结文件','行号'],[[esc(a),'<code>'+esc(b)+'</code>',f'{c}—{d}'] for a,b,c,d in sources])+f'''<p>审计目录：<code>{esc(OUT)}</code></p><p>数值证据：results/algebra_checks.json、findings.json、matlab_source_checks.json、audit_matrices.mat、error_decomposition.csv。来源与旧案例完整性见source_manifest.json及results/source_protection_before.json、source_protection_after.json。交付验收见results/delivery_checks.json及delivery_manifest.json。</p><p>文献背景：Krattiger等，Interface reduction for Hurty/Craig-Bampton substructured models: Review and improvements，Mechanical Systems and Signal Processing 114 (2019), 579–603，DOI:10.1016/j.ymssp.2018.05.031。本报告的具体判断来自本地公式、矩阵及封存数据核查。</p>''')

css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2f5f8;color:#193349;font:15px/1.75 "Microsoft YaHei","Segoe UI",sans-serif}main{max-width:1120px;margin:auto;padding:28px 24px 60px}header,section{background:white;border:1px solid #d9e2ea;border-radius:10px;padding:24px;margin:0 0 20px}h1{font-size:28px;line-height:1.4;margin:10px 0}h2{font-size:22px;line-height:1.5;margin:0 0 14px}h3{font-size:17px;margin:20px 0 8px}p{margin:10px 0}.lead{font-size:18px}.badge{display:inline-block;background:#e4f0f8;color:#23648a;border-radius:20px;padding:3px 12px}.callout{padding:15px 18px;background:#edf5fa;border-left:4px solid #4477aa;margin:16px 0}.formula{font-family:Georgia,"Microsoft YaHei",serif;line-height:1.9;background:#f7f8fa;border:1px solid #e4e9ef;padding:16px;overflow-x:auto}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #dce5ed;min-width:105px}th{background:#edf3f7}code{font:13px/1.6 Consolas,"Microsoft YaHei",monospace;overflow-wrap:anywhere}nav{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}nav a{color:#23648a;text-decoration:none;border:1px solid #cbdde9;border-radius:5px;padding:5px 9px}section{scroll-margin-top:12px}footer{font-size:13px;color:#5a7288}strong{color:#102f48}@media(max-width:600px){main{padding:12px 8px}header,section{padding:17px 13px}h1{font-size:23px}h2{font-size:20px}.lead{font-size:16px}table{font-size:13px}td,th{padding:8px}nav{gap:6px}}@page{size:A4;margin:13mm}@media print{body{background:white;font-size:9pt;line-height:1.5}main{padding:0;max-width:none}header,section{border:0;padding:0;margin:0 0 8mm;border-radius:0}h1{font-size:18pt}h2{font-size:14pt;break-after:avoid}h3{font-size:11pt;break-after:avoid}p{orphans:3;widows:3}.lead{font-size:11pt}nav{display:none}.callout,.formula{break-inside:avoid}table{font-size:8pt;table-layout:fixed}td,th{min-width:0;padding:5px;overflow-wrap:anywhere}tr{break-inside:avoid}.table-wrap{overflow:visible}thead{display:table-header-group}code{font-size:7pt}section{break-before:page}}
'''
nav=''.join(f'<a href="#{i}">{label}</a>' for i,label in [('scope','范围'),('contract','模型对照'),('interface','接口'),('limits','极限'),('delay','延迟路径'),('decomposition','误差分解'),('recommend','修正建议'),('status','状态'),('evidence','证据')])
page=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原完整框架基准与两套模型一致性核查汇报</title><style>{css}</style></head><body><main><header><span class="badge">Doctor Bego · 模型核查 · 未新增时程仿真</span><h1>原完整框架基准与两套模型一致性核查汇报</h1>{intro}<nav>{nav}</nav></header>{scope}{contract}{interface}{limits}{delaysection}{decomposition}{recommend}{status}{evidence}<footer>2026-09-16 · 本地代数与既有数据核查。原稿及两个已封存案例保持。</footer></main></body></html>'
target=ROOT/'reports/原完整框架基准与两套模型一致性核查汇报.html';target.write_text(page,'utf-8')
print('REPORT_CREATED',str(target),target.stat().st_size)
