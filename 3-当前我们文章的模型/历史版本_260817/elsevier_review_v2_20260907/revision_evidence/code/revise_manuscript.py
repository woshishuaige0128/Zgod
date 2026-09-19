from pathlib import Path
import json,re,hashlib,difflib,shutil
ROOT=Path(__file__).resolve().parents[2]
TMP=Path(__file__).resolve().parent
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907'
if Path(__file__).resolve().parent.name=='code' and Path(__file__).resolve().parent.parent.name=='revision_evidence':NEW=Path(__file__).resolve().parents[2]
baseline=(NEW/'revision_evidence/baseline/main_before.tex').read_text(encoding='utf-8')
text=baseline;ops=[]
def rev(s):return r'\rev{'+s+'}'
def getpara(starts):
    matches=list(re.finditer('(?m)^'+re.escape(starts),text));assert len(matches)==1,(starts,len(matches))
    pos=matches[0].start();end=text.find('\n\n',pos)
    return text[pos:end if end>=0 else len(text)]
def change(old,new,title,why,category='必要文字修订',source='用户提供的审稿意见及本轮实际模型核查',old_zh='',new_zh=''):
    global text
    count=text.count(old)
    assert count==1,(title,count,old[:100])
    pos=text.index(old)
    text=text[:pos]+new+text[pos+len(old):]
    ops.append(dict(id=f'change-{len(ops)+1:03d}',title=title,category=category,old=old,new=new,reason=why,source=source,old_zh=old_zh,new_zh=new_zh))
def paragraph(starts,new,title,why,category='必要文字修订',**kwargs):
    old=getpara(starts)
    change(old,new,title,why,category,**kwargs)
def replace_in_para(starts,pairs,title,why,category='必要文字修订',**kwargs):
    old=getpara(starts);new=old
    for a,b in pairs:
        assert a in new,(title,a)
        new=new.replace(a,b)
    change(old,new,title,why,category,**kwargs)
def figure(file,label,caption,width='.98'):
    return '\n'.join([r'\begin{figure}[htbp]',r'\centering',rf'\includegraphics[width={width}\textwidth]{{{file}.pdf}}',r'\caption{'+rev(caption)+'}',rf'\label{{{label}}}',r'\end{figure}'])
def append_after_para(starts,addition,title,why,**kwargs):
    old=getpara(starts);change(old,old+'\n\n'+addition,title,why,**kwargs)

# The abstract retains the original argument and sentence order.
replace_in_para('Limited actuation channels',[
('Delay-free accuracy comparisons give a maximum relative error of 0.834\\%','Delay-free '+rev('full-frame')+' accuracy comparisons give a maximum relative error of '+rev('0.284\\%')),
('remains below 0.06\\%', rev('has a maximum of 0.138\\%')),
('24.575\\% and 19.059\\%',rev('30.574\\% and 26.858\\%')),
('Smaller modal redistribution ratios accompany less contraction of the stability domain.',rev('Expanded modal shapes and reconstructed middle-storey responses identify the response components affected by condensation.')),
('retained internal modal dynamics to response fidelity and delay tolerance','retained internal modal dynamics to response fidelity and '+rev('the delay tolerance of each model--regulator pair'))
],'摘要：数据联动与有依据的结论','更正三项最大误差；表5重算后不能保留原来的单调稳定性排序。保留原摘要结构，并纳入新增中层验证的实际贡献。',old_zh='原摘要报告0.834%、0.06%、24.575%和19.059%，并宣称模态指标与稳定域收缩同序。',new_zh='对应数值改为0.284%、0.138%、30.574%和26.858%；改用振型与中层重构结果支撑响应解释，稳定性归因包含配套控制器。')

# Necessary clarification of assembly, without prescribing an invented zero force.
replace_in_para(r'\noindent where \(\bm{x}_{\mathrm{n}}\)',[
('The interface coordinates are shared by the two substructures and the interface forces balance, \\(\\bm{\\lambda}_{\\mathrm{n}}+\\bm{\\lambda}_{\\mathrm{e}}=\\bm{0}\\).',rev('The interface reactions balance after the local force vectors are mapped to the same interface coordinates.'))
],'界面力维数：避免直接相加不同局部向量','两个子结构的局部自由度数可以不同，局部力向量不能直接相加；界面平衡必须先放到共同的界面坐标。',old_zh='原文直接写数值侧与物理侧局部界面力向量相加为零。',new_zh='明确先映射到同一界面坐标，再建立反力平衡。')
replace_in_para('The two substructures are condensed separately',[
('where the interface forces cancel.',rev('where the projected interface forces balance. The reduced coordinates of substructure \\(s\\) satisfy \\(\\bm q_s=\\mathbf A_s\\bm q\\), where \\(\\mathbf A_s\\) places its local coordinates in the assembled coordinate vector.'))
],'装配坐标：补充局部至整体的映射','原文没有写清两个不同局部缩聚空间如何装配。补充坐标映射是定义现有装配所必需，不另造未耦合界面零力条件。',old_zh='只说两个子结构分别缩聚后在共同保留坐标耦合。',new_zh='说明局部缩聚坐标由整体坐标映射获得，界面力按投影后的平衡装配。')
replace_in_para(r'\noindent where \(\bm{q}(t)\) collects the generalized coordinates of the two reduced substructures',[
('Only the interface coordinates retained by both reduced models are matched, since these are the coordinates that the transfer system can impose. A geometric interface coordinate outside the coupling set carries neither the compatibility condition nor the equilibrium condition of Eq. \\eqref{eq:substructure-eom}, and each reduced substructure recovers it from its own transformation.',rev('The reduced substructure matrices assemble as \\(\\mathbf M_{\\mathrm{red}}=\\sum_s\\mathbf A_s^{\\mathsf T}\\mathbf M_{s,\\mathrm{red}}\\mathbf A_s\\), with the same operation for damping, stiffness and external loads, where \\(s\\in\\{\\mathrm n,\\mathrm e\\}\\) identifies the numerical and physical parts. Interface forces satisfy \\(\\sum_s\\mathbf A_s^{\\mathsf T}\\mathbf T_s^{\\mathsf T}\\bm\\lambda_s=\\bm0\\) in this coupling space. Compatibility is imposed at the shared retained coordinates. At a geometric interface coordinate outside this set, each substructure has its own recovered displacement, so the two recovered values need not coincide.')),
('no loading system can enforce the numerical model there.',rev('the specified two-channel loading system does not impose an independent numerical command there.'))
],'装配平衡：纠正“既无协调也无平衡”的表述','界面力不能仅因某坐标被消去而被无条件删除。用现有投影装配的虚功平衡说明力的作用，同时保留部分界面位移可能不一致的事实。未将零力条件当作已验证的实现。',old_zh='原文断言未保留界面坐标既不满足协调也不满足平衡，并说任何加载系统都无法施加数值模型。',new_zh='写明缩聚矩阵与界面力的投影装配；位移协调只在共同保留坐标施加，加载限制限定于文中两通道系统。')

# The force feedback path is read from the existing characteristic equation.
replace_in_para(r'\noindent where \(\Delta t\) is the integration time step',[
('The numerical substructure supplies the target displacement of each actuated coordinate, the transfer system imposes it on the physical substructure with the delay of Eq. \\eqref{eq:integer-delay}, and the measured displacement and restoring force are returned to the numerical substructure and to the regulator acting on the actuated coordinates.',rev('The numerical state supplies the target displacement of each actuated coordinate. The physical elastic and damping reactions return through the delayed channel terms. The additional regulator uses the numerical displacement and velocity and applies a delayed force at the same actuated coordinates.'))
],'闭环信号：明确调节器使用数值状态','式(3.5)使用S_a q和S_a qdot，原文却说使用实测位移。按保留的方程澄清输入，避免把位移跟踪器和附加力反馈混为一体。',old_zh='原文说实测位移和恢复力同时返回数值子结构及调节器。',new_zh='明确恢复力通过延迟通道返回，调节器读取数值位移和速度，再施加延迟力。')
replace_in_para('for Guyan and Craig--Bampton condensation, respectively.',[
('The second term of Eq. \\eqref{eq:cb-delay-recovery} accordingly carries no explicit delay operator, and it reaches the delayed motion of the retained coordinates only through the coupling of the reduced equations.',rev('The modal contribution in Eq. \\eqref{eq:cb-delay-recovery} is not directly delayed by an actuator; its evolution remains coupled to the delayed retained coordinates through the reduced equations.')),
('For the same actuated coordinates and the same actuator delays, the delayed channels reach the reconstructed response through the constraint-mode term alone under Craig--Bampton condensation, and through every term under Guyan condensation.',rev('The two methods therefore retain the same number of delay channels while representing their coupling to the internal response differently.'))
],'模态与时滞：区分直接延迟和动力耦合','未经过作动器的模态坐标仍与延迟物理坐标耦合；不能据此说模态方程没有时滞或通道数量减少。',old_zh='原文把延迟在CB中只进入约束模态项作为完整机制解释。',new_zh='明确模态项不直接延迟、但其演化仍与延迟坐标耦合；两种方法通道数相同。')
replace_in_para('The regulator output is a generalized force.',[
('Equation \\eqref{eq:lqr-law} therefore acts on the assembled equation as an equivalent feedback stiffness \\(\\mathbf{K}_{x}\\) and an equivalent feedback damping \\(\\mathbf{K}_{v}\\) on the actuated coordinates, and this action reaches the specimen through the actuator channels of Fig. \\ref{fig:rths-loop} with the same channel delays as the imposed displacement.',rev('Its applied value is \\(\\bm f_{\\mathrm{L,applied}}(z)=\\mathbf S_{\\mathrm a}^{\\mathsf T}\\mathbf H_{\\mathrm a}(z)\\bm f_{\\mathrm L}(z)\\), where \\(\\mathbf H_{\\mathrm a}(z)=\\mathrm{diag}(z^{-n_1},\\ldots,z^{-n_{\\mathrm a}})\\). This force enters the load summation of the numerical update, as shown in Fig. \\ref{fig:rths-loop}; the gain matrices provide the corresponding feedback stiffness and damping.'))
],'附加反馈力：写明延迟与力的施加位置','保留式(3.5)和式(3.6)，直接给出二者隐含的信号通路，不增加Riccati方程教材推导。',old_zh='原文笼统称力反馈通过位移作动通道作用于试件。',new_zh='给出S_a转置乘通道延迟矩阵再乘控制力的施加关系，并指出其进入数值更新的力求和点。')

# Benchmark settings: preserve prototype geometry while stating the numerical parameters.
replace_in_para('The reference structure is a simplified planar model',[
('built from the geometry and the material data','built from the geometry and '+rev('section arrangement')),
('The geometry and the section dimensions are shown in Fig. \\ref{fig:benchmark-geometry}, and the material properties are listed in Table \\ref{tab:materials}.','The geometry and the section dimensions are shown in Fig. \\ref{fig:benchmark-geometry}, and the material properties are listed in Table \\ref{tab:materials}. '+rev('The numerical model uses \\(E=206\\) GPa for both member types and the section properties stated below.'))
],'基准来源：区分原型截面与实际数值参数','当前代码使用206 GPa和明确的有效截面参数，不能将原型几何直接说成唯一可重建模型。保留原型截面信息。',old_zh='原文把几何和材料表作为数值模型全部来源。',new_zh='保留原型尺寸与截面安排，同时明确实际求解所用的弹性模量和有效截面参数。')
change('A36 (beams)      & 250 & 400--550 & 200 & 0.3 & 7850', 'A36 (beams)      & 250 & 400--550 & '+rev('206')+' & 0.3 & 7850','表1：梁弹性模量200改为206 GPa','PDmonicanshu.m实际使用E=206e9。','表格数据修正','当前全链PDmonicanshu.m')
change('A992 Gr.50 (columns) & 345 & 450--550 & 200 & 0.3 & 7850', 'A992 Gr.50 (columns) & 345 & 450--550 & '+rev('206')+' & 0.3 & 7850','表1：柱弹性模量200改为206 GPa','PDmonicanshu.m实际使用E=206e9。','表格数据修正','当前全链PDmonicanshu.m')
append_after_para('In the finite element idealization',rev(r'The numerical frame fixes all four column bases. Its effective section properties are \(A_{\mathrm c}=1.0774172\times10^{-3}\,\mathrm{m}^2\), \(I_{\mathrm c}=1.0489032\times10^{-6}\,\mathrm{m}^4\), \(A_{\mathrm b}=6.1096652\times10^{-4}\,\mathrm{m}^2\), and \(I_{\mathrm b}=2.5523311\times10^{-7}\,\mathrm{m}^4\). A diagonal lumped mass matrix assigns 6164.831 kg to each storey translation and rotational inertias of 51.088, 67.887, 67.887 and 51.088 kg\,m\(^{2}\) to its four nodes. These masses use an effective density multiplier of 190 relative to the steel density in Table \ref{tab:materials}; the multiplier sets the numerical mass level. The matrices and coordinate order are supplied with the paper.'),'模型复现：集中补充边界、截面与质量','实际全链矩阵是四柱脚固结、集中质量且密度乘190。只改表1不足以解释频率。集中补充一次，不在各节重复声明。',old_zh='原稿未说明柱脚转角处理、质量放大、各节点转动惯量或实际截面数值。',new_zh='给出实际四柱脚固结、四项截面参数、平移质量和转动惯量，并注明有效密度乘190及随附矩阵。')
replace_in_para('The full-order equation of motion is Eq.',[
('The first five natural frequencies of the idealized model are 2.7 Hz, 9.1 Hz, 18.0 Hz, 22.1 Hz and 23.6 Hz. The first five modes account for more than 90\\%',rev('The coefficients are \\(a_0=1.3184625\\,\\mathrm{s}^{-1}\\) and \\(a_1=1.3223424\\times10^{-3}\\,\\mathrm{s}\\); the reduced damping matrices are obtained from this same damping matrix. The first five natural frequencies of the idealized model are 2.7074 Hz, 9.3284 Hz, 18.4427 Hz, 22.6736 Hz and 24.2277 Hz. The first five modes account for 98.06\\%'))
],'固有频率与阻尼：按实际矩阵更新','实际M、K特征值与旧文9.1等不同；新增有效质量98.06%由质量归一化模态复算，阻尼系数由原矩阵核验。',old_zh='前五阶为2.7、9.1、18.0、22.1和23.6 Hz，有效质量只说超过90%。',new_zh='更新为实算五阶频率、98.06%有效质量，并给出Rayleigh系数及统一阻尼来源。')

# Separate the conceptual local assembly from the actual full-frame accuracy models.
replace_in_para('Both divisions are limited to two independent actuation channels.',[
('and the same assignment is adopted in the accuracy analysis and in the stability analysis.',rev('and these channel locations are used to select the coordinates monitored in the accuracy comparison and delayed in the stability formulation.'))
],'两种分析：保留通道位置而不混同模型','准确性四套CSV来自整体缩聚，不能继续暗示与部分界面子结构闭环是同一实现。',old_zh='原文把准确性和稳定性中的作动分配作为两套模型完全相同的暗示。',new_zh='限定一致的是通道位置及其在两种分析中的用途。')
append_after_para('The three fixed-interface modes of lowest frequency are retained for each substructure',rev(r'For the delay-free accuracy comparisons, the assembled fifteen-DOF frame is reduced directly. The retained physical coordinates are \(\{\psi_1,\psi_6,\psi_{11},\psi_4,\psi_9,\psi_{14}\}\) in division I and \(\{\psi_1,\psi_{11},\psi_4,\psi_9,\psi_{14}\}\) in division II. Three fixed-interface modes enrich each full-frame Craig--Bampton basis, giving orders 6/9 for Guyan/Craig--Bampton in division I and 5/8 in division II. Each response is expanded uniquely to the fifteen physical coordinates. These models evaluate the effect of the retained set on structural response; the local substructure coupling sets remain those in Table \ref{tab:dof-sets}.')+'\n\n'+rev(r'The Guyan accuracy implementation substitutes the static recovery relation into the retained equations, using \(\mathbf M_{\mathrm G}=\mathbf M_{\mathrm{rr}}+\mathbf M_{\mathrm{rc}}\bm\Psi_{\mathrm G}\), with analogous expressions for \(\mathbf C_{\mathrm G}\) and \(\mathbf K_{\mathrm G}\), and the load \(\mathbf T_{\mathrm G}^{\mathsf T}\bm f\). The Craig--Bampton matrices use Eq. \eqref{eq:general-projection}. Thus the accuracy comparison also includes this distinction in the Guyan matrix construction.'),'准确性模型：明确整体缩聚的实际阶数及Guyan实现','表3至表5的已核验数值属于15/6/9和15/5/8模型。原文6/12是子结构分别缩聚后的概念配置；两者不能互换。当前Guyan使用保留方程单侧质量/阻尼，必须说明。此项是数据修正的必要配套，供用户重点审阅。',old_zh='原稿只有两个子结构分别保留3个固定界面模态、装配6/12阶且两种划分同阶的说法。',new_zh='保留该子结构配置说明，并另明确实际精度模型整体缩聚为6/9和5/8阶、每套3个模态，以及Guyan单侧矩阵构造。')
paragraph('The full-order model, the Guyan condensed model and the Craig--Bampton condensed model are implemented in Simulink.',rev(r'The full-order model and the two full-frame condensed models are implemented as three parallel state-space systems in Simulink. The accuracy study uses zero actuator delay and zero regulator force, \(\bm f_{\mathrm L}=\bm0\), with no measurement noise. The equivalent seismic load is formed from the full mass matrix and projected to the reduced coordinates. A fixed-step fourth-order Runge--Kutta solver advances the systems at \(\Delta t=1/1024\) s over 40 s, and the transformations recover the three storey displacements. Differences from the full-order response therefore measure the accuracy of the stated reduction implementations.'),'准确性仿真：按真实并行状态空间运行说明','当前全链是三条并行状态空间和ode4，未执行原文所述双侧力回传。只说关闭控制器动态也不足以说明静态力反馈关闭。',old_zh='原文说三个模型进行不同界面集合的数值/物理子结构耦合，物理试件返回力。',new_zh='如实写为三条并行状态空间，反馈力为零，ode4在1/1024 s步长积分，并恢复三层响应。')
paragraph('Two excitations are adopted.',r'Two excitations are adopted. The first is the El Centro record scaled by a factor of 0.40'+rev(r', using the supplied north--south acceleration series in m/s\(^{2}\), with its 0.02 s samples linearly interpolated during integration. The response is evaluated with the linear model of Eq. \eqref{eq:full-order-eom}.')+r' The second is a chirp signal whose frequency increases linearly from 0.1 Hz to 10 Hz over 40 s. '+rev(r'Its acceleration is \(a_{\mathrm g}(t)=\sin[2\pi(0.1)t+\pi(9.9/40)t^2]\,\mathrm{m/s^2}\), with unit amplitude and zero initial phase. Both input histories are shown in Fig. \ref{fig:inputs}.')+r' The sweep covers the first two natural frequencies of the benchmark and follows the accuracy of the condensed model as the excitation frequency approaches and then exceeds the fundamental frequency.','激励定义：补充完整输入并删除未验证的屈服判断','现有资料没有逐杆应力验证，不能用缩放系数直接证明低于屈服。记录分量、单位、采样和扫频公式均有全链入口依据。',old_zh='原文以0.40缩放系数直接声称杆件不屈服，扫频只有频率范围和时长。',new_zh='明确地震分量、单位、插值和完整扫频公式；仅说明采用线性模型，不声称已做强度验证。')
append_after_para('Two excitations are adopted.',figure('fig11_excitation','fig:inputs','Ground-acceleration inputs. (a) Scaled El Centro record. (b) Linear chirp.'),'新增图：地震与扫频输入','输入幅值和时间历程决定毫米级响应；新增此图使案例加载条件可直接核对。',category='新增结果图',source='EQ.mat、全链入口第5段和new_excitation.csv')
replace_in_para(r'\noindent where \(\bm{\varphi}_{i}^{\mathrm{red}}\)',[
('A value close to unity indicates preserved mode shape components on the retained coordinates.',rev('Translations are expressed in metres and rotations in radians, with no additional coordinate scaling in this retained-coordinate MAC. A value close to unity indicates agreement under this coordinate convention.'))
],'MAC：明确平移与转角的单位','现有表值使用混合平移/转角欧氏MAC，变单位会改变指标。说明实际m/rad口径，新增纯水平振型图补充物理解释。',old_zh='原文只说保留坐标上的模态向量一致，未说明尺度。',new_zh='明确平移米、转角弧度，无额外缩放；表3值保持现有可核验定义。')
replace_in_para('For the chirp excitation, the NRMSE is evaluated separately',[
('which are 0.1 Hz to \\(0.7f_{1}\\), \\(0.7f_{1}\\) to \\(1.3f_{1}\\), \\(1.3f_{1}\\) to \\(2f_{1}\\), \\(2f_{1}\\) to \\(3f_{1}\\), and \\(3f_{1}\\) to 10 Hz, where \\(f_{1}\\) is the fundamental frequency of the structure. With \\(f_{1}=2.7\\) Hz these bands correspond to 0.1 to 1.9 Hz, 1.9 to 3.5 Hz, 3.5 to 5.4 Hz, 5.4 to 8.1 Hz and 8.1 to 10 Hz.',rev('with endpoints of 0.1, 1.9, 3.5, 5.4, 8.1 and 10 Hz. These fixed endpoints approximate multiples of the fundamental frequency, \\(f_1=2.7074\\) Hz, and are used exactly in the error integration.')),
('the band values accordingly trace the growth of the error with the excitation frequency.',rev('the band values accordingly track the variation of error across the sweep.'))
],'扫频积分：固定频带端点，修正单调增长暗示','表4重算采用印出的0.1/1.9/3.5/5.4/8.1/10 Hz，而不是精确倍频。新表也不支持误差单调增长。',old_zh='原文精确倍频与四舍五入频带混用，并说误差随频率增长。',new_zh='明确按表内固定端点积分，保留前段残余响应解释，把增长改为变化。')
replace_in_para('The effect of condensation on the stability is quantified through a modal redistribution ratio',[
('The effect of condensation on the stability is quantified through a modal redistribution ratio, which measures the low-order modal content moved onto the retained coordinates.',rev('The change in low-order modal distribution is described by a modal redistribution ratio, which combines the relative changes at the actuated coordinates.'))
],'模态指标定位：回到公式实际度量','式(4.4)是各坐标相对变化之和，不是延迟稳定性量，也不是总能量转移量。保留公式和指标框架。',old_zh='原文把指标定义为缩聚对稳定性的定量影响以及移到保留坐标的模态内容。',new_zh='定义为作动坐标相对份额变化的汇总。')
replace_in_para(r'\noindent where \(\gamma_{i}\) is the modal participation factor',[
('which evaluates the two shares on the same coordinates.',rev('and mass-normalized again using the full mass matrix. The participation weights are recomputed for each model, so both shares are evaluated on the same fifteen physical coordinates and mass convention.'))
],'模态扩展：补齐重归一化和权重的计算规则','扩展后用完整质量归一化，并为各模型重算参与权重，是表5可复现的必要步骤。',old_zh='原文只说通过各自变换矩阵扩展到完整坐标。',new_zh='补充扩展后按完整M归一化、每个模型独立计算参与权重，统一15个物理坐标。')
replace_in_para(r'\noindent where \(d_{k}\) is the \(k\)th actuated coordinate',[
('A larger \\(\\Delta E\\) therefore corresponds to a larger part of the modal content of the condensed coordinates carried by the coordinates that the actuators drive, and \\(\\Delta E\\) measures the response exposed to the actuator delay through the propagation of Section \\ref{sec:multiple-delay}.',rev('The terms have separate denominators and retain their signs; their sum is a modal-share indicator rather than a total energy-transfer measure or a stability criterion.'))
],'指标解释：删除“等于进入延迟通道的响应”','审稿意见给出的反例成立，新数据也出现负贡献。应保持带符号坐标指标的含义，而非直接推断稳定性。',old_zh='原文认为指标越大，越多模态内容转移到作动坐标，并可测量暴露于时滞的响应。',new_zh='说明独立分母和带符号求和；指标用于份额比较，稳定性仍由闭环极点确定。')

# Further result edits and figures are appended below.

replace_in_para('The three fixed-interface modes of lowest frequency are retained for each substructure',[
('The two divisions are therefore compared at the same reduced model size, and the differences between them do not come from the order of the reduced model.',rev('These substructure-level configurations have the same reduced order in the two divisions.'))
],'局部模型阶数：限定6/12阶的适用对象','保留原局部子结构阶数描述，但不让它继续覆盖不同阶数的实际全局精度模型。',old_zh='两种划分同阶，并据此排除阶数影响。',new_zh='只说明子结构层级的概念配置同阶；全局精度配置另按6/9与5/8说明。')
replace_in_para('The two condensed models of each division are compared with the full-order reference model',[
('with the idealized coupling, where condensation is the only source of error.',rev('for the full-frame reduction implementations defined in Section \\ref{sec:division}.')),
('The stability domains of the closed loop are then computed for pairs of actuator delays.',rev('The substructure-level delay domains are then compared for pairs of actuator delays.')),
('The modal redistribution ratio finally relates the two sets of results to the modal content moved onto the actuated coordinates by condensation.',rev('The modal redistribution ratio finally describes how the low-order modal shares at the actuated coordinates change under condensation.'))
],'结果节导语：明确两套分析的对象','避免把全局精度结果与历史子结构闭环直接当作同一矩阵的联合验证。保留原节次和阅读顺序。',old_zh='原文说响应误差仅由缩聚引起，随后计算稳定域，最后用指标把二者串成直接因果。',new_zh='对应到已说明的全局缩聚实现、子结构延迟域及份额变化三个结果对象。')
replace_in_para('The relative errors of the first two natural frequencies',[
('2.7 Hz and 9.1 Hz',rev('2.7074 Hz and 9.3284 Hz')),
('largest error of 0.834\\%', 'largest error of '+rev('0.284\\%')),
('13.040\\% and 24.575\\%',rev('19.040\\% and 30.574\\%'))
],'模态精度段：更新频率和最大误差','正文所有相关数值须与表3及实际矩阵一致。','表格联动文字',source='表3独立复算44项清单',old_zh='CB最大0.834%，Guyan第二种划分13.040%/24.575%。',new_zh='改为0.284%及19.040%/30.574%，完整模型前两阶9.3284 Hz等同步更新。')

# Table values are derived from the verified 44-cell manifest and only changed cells are red.
audit=json.loads((NEW/'revision_evidence/data/table345_verified_values.json').read_text(encoding='utf-8'))
tables=list(re.finditer(r'\\begin\{table\}.*?\\end\{table\}',text,re.S))
for tindex,table in enumerate(tables[2:5],3):
    block=table.group();rows=[r for r in audit['rows'] if r['table']==tindex];newblock=block
    if tindex==3:matches=list(re.finditer(r'(?m)^\s*(?:I|II)\s*&\s*[12]\s*&.*?\\\\',block));group=4;first=2
    elif tindex==4:matches=list(re.finditer(r'(?m)^\s*(?:El Centro|Chirp,).*?\\\\',block));group=4;first=1
    else:matches=list(re.finditer(r'(?m)^\s*(?:I|II)\s*&.*?\\\\',block));group=2;first=1
    cell_changes=[]
    for ri,match in enumerate(matches):
        oldrow=match.group();parts=oldrow.split('&');newparts=parts.copy()
        for j in range(group):
            record=rows[ri*group+j]
            if record['status']=='不符':
                oldvalue=record['manuscript_value'];value=record['rounded_value']
                assert oldvalue in parts[first+j],(record,parts)
                newparts[first+j]=parts[first+j].replace(oldvalue,rev(value),1)
                cell_changes.append(record)
        newblock=newblock.replace(oldrow,'&'.join(newparts))
    change(block,newblock,f'表{tindex}：逐格替换{len(cell_changes)}个错误数值','沿用实际出图模型和稿件指标定义，经MATLAB/Python独立复算；相符单元不改。','表格数据修正','table345_verified_values.json及原始全链矩阵/响应')
    ops[-1]['cells']=cell_changes

paragraph('The two divisions differ in that division II condenses a horizontal storey coordinate',r'The two divisions differ in that division II condenses a horizontal storey coordinate '+rev(r'from the full-frame accuracy model. Once the middle-storey coordinate leaves the retained set, the static recovery is controlled by the retained lower- and upper-storey translations and the selected rotations. In the retained-equation Guyan implementation, the diagonal full mass matrix gives \(\mathbf M_{\mathrm G}=\mathbf M_{\mathrm{rr}}\), while the stiffness and load retain the static recovery contribution. The resulting change in the balance of stiffness and inertia raises the frequencies in this case. Craig--Bampton condensation includes internal modal inertia through its fixed-interface modes and retains the low-order frequencies much more closely. Figure \ref{fig:horizontal-modes} displays the actual frequencies together with the restored horizontal mode shapes.'),'频率机理：删除不适用的普遍上界推论','部分界面子结构装配并非原15维空间的子空间，且实际Guyan不是同余投影。不能用Ritz上界统一证明；改成代码支持的质量/刚度解释和本算例观察。',old_zh='原文认为两种缩聚均为完整模型子空间，故缩聚频率必然高于完整模型；中层惯性通过T重新分配。',new_zh='解释当前单侧Guyan在对角质量下保留Mrr，以及CB保留内部模态惯性；只报告本算例的频率方向。')
append_after_para('The two divisions differ in that division II condenses a horizontal storey coordinate',figure('fig12_horizontal_modes','fig:horizontal-modes','First two horizontal mode shapes expanded to the three storeys. Each shape is normalised by its largest horizontal component; the corresponding natural frequency is given in the legend.'),'新增图：前两阶实际频率与恢复水平振型','MAC只看保留坐标且混合m/rad；此图把三个水平坐标统一显示，并展示频率偏移方向。',category='新增结果图',source='M/K/T广义特征值、new_horizontal_modes.csv、new_modes_frequencies.csv')
replace_in_para('The MAC values behave differently.',[
('24.575\\%',rev('30.574\\%')),
('The Guyan transformation builds the condensed coordinates from a static deformation pattern that resembles the low-order mode shapes and carries no information on the inertia setting the frequencies.',rev('The static deformation pattern can resemble the retained components of a mode while the reduced mass representation changes its frequency. The restored second mode in Fig. \\ref{fig:horizontal-modes} also shows the larger spatial deviation of the division II Guyan model.'))
],'MAC解读：保留原判断，补上新振型证据','保留“MAC不足以单独验收”的论点；替换错误频率并用恢复振型加强现有分析。',old_zh='原段MAC最低0.9255对应频率误差24.575%，只从静态模式作解释。',new_zh='改为30.574%，结合新增水平振型指出第二阶空间形状偏差。')
replace_in_para('Figs. \\ref{fig:eq-div1} and \\ref{fig:eq-div2} compare',[
('The response of the second storey lies between the two and is omitted.',rev('The second-storey response is examined separately in Fig. \\ref{fig:middle-eq}, because its reconstruction is the critical additional approximation in division II.'))
],'地震结果：不再以幅值居中为由省略中层','幅值在首层和顶层之间不代表重构误差受二者控制。新增中层图直接回应审稿意见。',old_zh='原文以中层响应位于首层和顶层之间为由省略。',new_zh='明确中层是第二种划分的关键重构对象，转至新增图评价。')
anchor=r'\label{fig:eq-div2}'+'\n'+r'\end{figure}'
addition=rev(r'Figure \ref{fig:middle-eq} evaluates the middle-storey displacement recovered from the division II full-frame transformations. The Guyan NRMSE is 10.798\%, whereas the Craig--Bampton value is 0.031\% over the 40 s record. The separate error traces show that the small Craig--Bampton error persists through the strong-response interval, rather than following only the overall amplitude envelope. This comparison directly tests recovery of the omitted horizontal coordinate.')+'\n\n'+figure('fig13_middle_eq','fig:middle-eq','Reconstructed middle-storey displacement in division II under El Centro excitation. (a) Response comparison. (b) Guyan error. (c) Craig--Bampton error. Errors are measured relative to the full-order response; the two error panels use different vertical scales.')
change(anchor,anchor+'\n\n'+addition,'新增图与分析：中间楼层地震重构','以第二种划分三层数据中真实的中层输出补上关键缺口；不伪造两个子结构独立恢复值或界面差。','新增结果图','全链Fig07的中层三条响应；MATLAB/Python复核',old_zh='原文没有中层地震响应和误差。',new_zh='新增中层对比与两种方法独立误差图，NRMSE分别10.798%和0.031%。')
replace_in_para('In division I the Guyan response deviates',[
('first resonance peak near 13 s',rev('full-order first-storey response peak at 11.69 s')),
('falls to less than half of the reference at the first storey and rises to nearly twice the reference at the third storey.',rev('has peak-to-peak amplitudes of 46.1\\% and 80.5\\% of the reference at the first and third storeys, respectively, over 38.0--38.3 s.'))
],'扫频时程：修正峰值时刻和末端幅值判断','实际首层绝对峰值11.693359375 s；38.0–38.3 s区间第三层峰峰值比0.805而不是接近2。需同时指明统计窗口和幅值定义。','表格联动文字',source='additional_metrics.json与对应全链CSV',old_zh='原文首个共振峰约13 s，末端第三层Guyan接近参考2倍。',new_zh='完整模型首层峰值11.69 s；末端首/顶层峰峰值比分别46.1%和80.5%。')
anchor=r'\label{fig:chirp-div2}'+'\n'+r'\end{figure}'
addition=rev(r'The corresponding middle-storey sweep response is shown in Fig. \ref{fig:middle-chirp}. The Guyan and Craig--Bampton full-record NRMSE values are 11.749\% and 0.034\%, respectively. The Guyan error concentrates around the resonance passages, consistent with its shifted natural frequencies. The Craig--Bampton reconstruction follows the middle-storey oscillations through both passages, showing that its improvement extends to the horizontal coordinate excluded from the retained set.')+'\n\n'+figure('fig14_middle_chirp','fig:middle-chirp','Reconstructed middle-storey displacement in division II under chirp excitation. (a) Response comparison. (b) Guyan error. (c) Craig--Bampton error. The two error panels use different vertical scales.')
change(anchor,anchor+'\n\n'+addition,'新增图与分析：中间楼层扫频重构','用同一未保留水平坐标检验频率变化下的恢复性能，与地震图承担不同验证作用。','新增结果图','全链Fig09的中层三条响应；MATLAB/Python复核',old_zh='原文没有中层扫频响应和误差。',new_zh='新增中层扫频比较和两条误差，NRMSE分别11.749%和0.034%。')
replace_in_para('Table \\ref{tab:nrmse} gives the NRMSE',[
('0.758\\%',rev('0.802\\%')),('10.936\\%',rev('10.911\\%')),
('0.030\\% in division I and 2.996\\% in division II',rev('0.027\\% in division I and 0.719\\% in division II')),
('1.995\\% and 19.059\\%',rev('2.010\\% and 26.858\\%')),
('0.076\\%',rev('0.171\\%')),('0.745\\%',rev('2.041\\%')),
('In division II the error stays above 2.8\\% in every band. The Craig--Bampton error remains below 0.06\\% in every band of both divisions.',rev('In division II the Guyan error drops to 0.129\\% in the 5.4--8.1 Hz band and rises to 3.020\\% in the final band. Craig--Bampton gives a maximum band NRMSE of 0.138\\% in division I and 0.074\\% in division II.'))
],'首层误差分析：更新整段数值与非单调趋势','表4共21个改值，原文全频段大于2.8%和CB小于0.06%均不再成立。保留按频带分析的原段逻辑。','表格联动文字',source='表4固定频带积分复算',old_zh='原文最大19.059%、第二种划分各频带均超过2.8%、CB各频带小于0.06%。',new_zh='最大26.858%，第二种划分5.4–8.1 Hz降至0.129%，CB两种划分最大0.138%/0.074%。')
replace_in_para('Two observations follow.',[
('The two divisions produce assembled models of the same size and differ by more than an order of magnitude in the Guyan error, and the order of the reduced model therefore does not explain the accuracy by itself. Division II enlarges the physical substructure and condenses the middle-storey horizontal coordinate at the same time, and the combination of the two makes it the more demanding case.',rev('The Guyan errors differ by more than an order of magnitude between the divisions in the fundamental-frequency band. The accuracy models have six and five retained coordinates, respectively, and the loss of the middle-storey translation is the central change in division II. Figures \\ref{fig:middle-eq} and \\ref{fig:middle-chirp} show its effect directly at the reconstructed coordinate.'))
],'响应小结：删除精度模型同阶的错误论据','当前两种划分精度模型阶数不同，不能声称排除了阶数影响。保留两种划分显著不同的观察。',old_zh='原文以两种划分同阶为由排除阶数影响，并把物理子结构扩大和中层消去共同归因。',new_zh='明确6和5个物理保留坐标，指出中层消去这一实际变更，并引用新增中层证据。')
append_after_para('Two observations follow.',rev(r'Peak interstorey drifts provide a complementary measure of the recovered deformation pattern (Fig. \ref{fig:peak-drift}). Each drift is the relative displacement of adjacent floors divided by the 635 mm storey height, with zero base displacement. In division II, the Guyan third-storey peak drift rises from the reference 0.687\% to 0.798\% under El Centro excitation and from 1.784\% to 2.259\% under the chirp. The corresponding Craig--Bampton values are 0.689\% and 1.789\%. Thus the improved coordinate recovery also preserves the distribution of interstorey deformation, whereas an individual floor peak alone can conceal an error in the relative motion.')+'\n\n'+figure('fig15_peak_drift','fig:peak-drift','Peak absolute interstorey drift profiles. (a,b) El Centro excitation. (c,d) Chirp excitation. The left and right columns correspond to divisions I and II, respectively.'),'新增图与分析：峰值层间位移角分布','相邻楼层的相对变形提供不同于单层位移和NRMSE的工程响应证据。结果由三层真实位移差分得出，不作屈服判定。',category='新增结果图',source='四套全链楼层响应及635 mm层高；MATLAB/Python复核',old_zh='原稿只评价单层位移和首层NRMSE。',new_zh='新增四个组合下三层峰值层间位移角；说明第二种划分顶层相对变形的Guyan偏差。')

replace_in_para('A linear quadratic regulator acts on the actuated coordinates',[
('supplies a generalized force that reaches the specimen through the actuator channels.',rev('supplies an additional generalized force at those coordinates through the delayed feedback path.'))
],'调节器引入句：与明确后的力求和点一致','对应图1和式(3.6)的附加力反馈解释，避免仍称该力直接经过位移跟踪系统。',old_zh='原文称控制力通过作动器通道直接到达试件。',new_zh='改为控制力经过延迟反馈路径作用于指定广义坐标。')
paragraph('The stability domains obtained from the pole criterion',rev(r'The reference delay-domain comparison is shown in Fig. \ref{fig:stability-domain}. The two axes give the channel delays in milliseconds, using the exact conversion \(\tau_\ell=1000n_\ell/1024\) ms from the integer delay steps. Each supplied boundary gives the largest stable second-channel delay for a prescribed first-channel delay, with the stable region on the side containing the origin. The Original boundary represents the unreduced fifteen-DOF reference with ideal coupling at the interface coordinates outside the two delayed channels. It provides the ideal-interface reference for this comparison.')+' '+rev(r'These boundaries are retained from the original boundary dataset; the available full-frame accuracy matrices do not establish the closed-loop matrices and regulator gains behind these curves.'),'稳定域：精确单位、参考模型及计算来源','轴已按1000/1024转换，原文“步数约等于毫秒”错误。完整模型只是本算例参考，不是数学上界。现有全链精度矩阵未能重建历史六条边界，因此不能声称本轮按式(3.6)计算出该图。',old_zh='原文称本图按现有极点方程扫描获得、步数约等于毫秒、完整模型为稳定性上界。',new_zh='写为原有边界数据的参考比较，毫秒精确换算，完整模型称理想界面参考；集中说明尚缺匹配的闭环矩阵和增益。')
paragraph('The recovery relations of Section \\ref{sec:multiple-delay} account for the ordering.',r'The recovery relations of Section \ref{sec:multiple-delay} '+rev(r'help interpret the difference between the two reduced closed loops. The Guyan recovery of the physical substructure depends entirely on delayed retained coordinates. Craig--Bampton adds internal modal coordinates that do not pass through the actuators, while their reduced equations remain coupled to the delayed coordinates. Both formulations still contain two delay channels. The larger Craig--Bampton region in the reference comparison is therefore a result for the specified model--regulator pair, consistent with retaining internal modal dynamics. The recovery relation alone does not determine the size of that region.'),'稳定性机理：保留物理解释，修正因果强度','两种方法均有两个延迟通道，模态方程仍耦合时滞；不能由无直接延迟的模态坐标推导必然更大的稳定域。不同增益也是差异来源。',old_zh='原文把Guyan每个子结构的所有内部响应暴露于时滞，并说CB只让时滞进入较少部分，从而解释稳定域排序。',new_zh='限定为物理子结构的恢复关系，说明两通道不变、模态耦合仍在；把稳定域排序归于给定模型和配套调节器。')

paragraph('The modal redistribution ratio of Eq. \\eqref{eq:energy-change} is listed',r'The modal redistribution ratio of Eq. \eqref{eq:energy-change} is listed in Table \ref{tab:energy}. '+rev(r'It is evaluated from the full-frame accuracy models using their first five modes. Guyan gives \(-0.0414\) in division I and \(0.8914\) in division II; the corresponding Craig--Bampton values are \(0.0039\) and \(0.0365\). Craig--Bampton is closer to zero in magnitude in both divisions, indicating a smaller change in the selected coordinate shares. The signed values do not have the same ordering in both divisions.'),'表5结果：重写已失效的稳定域同序关系','第一种划分Guyan负值小于CB，原文“CB数值始终更小且对应更大稳定域”已失效。更接近零是当前数据支持的准确描述。','表格联动文字',source='表5四值及15坐标份额复算',old_zh='原文宣称四个模态指标与稳定域收缩同序。',new_zh='给出-0.0414/0.8914和0.0039/0.0365；说明CB绝对值较小，带符号排序并不统一。')
paragraph('Table \\ref{tab:energy} is the quantitative counterpart',rev(r'Figure \ref{fig:modal-shares} resolves this change into the physical-coordinate distribution and the two actuator contributions. In division II, Guyan increases the first-storey share by 113.87\% and decreases the third-storey share by 24.73\%, whose signed relative contributions sum to \(\Delta E=0.8914\). Craig--Bampton gives changes of 3.94\% and \(-0.29\%\) at the same coordinates. The figure thus locates the redistribution that the scalar index combines, while also showing why its sign cannot be read as a change in total modal energy.'),'模态份额解释：用具体坐标贡献替代能量转移断言','新增图可直接显示指标两项来源；各坐标分母不同且可一正一负，所以不得等同于总能量。',old_zh='原文把指标作为恢复机理的定量对应，并直接称其测量迟滞通道承载的响应。',new_zh='分别解释第二种划分首层+113.87%、顶层-24.73%等贡献，定位分布变化，保留其带符号指标含义。')
append_after_para(r'\rev{Figure \ref{fig:modal-shares} resolves',figure('fig16_modal_shares','fig:modal-shares',r'Low-order modal-share distribution and actuator contributions. (a,c) Shares on the fifteen physical coordinates. (b,d) Signed relative changes at the two actuated coordinates, whose sum gives the ratio in Table \ref{tab:energy}. The top and bottom rows correspond to divisions I and II, respectively.'),'新增图：15个物理坐标份额与两通道贡献','展示标量表5无法表现的位置分布及正负抵消，支撑对指标作用的审慎但直接解释。',category='新增结果图',source='前五阶恢复振型、new_modal_shares.csv和new_actuator_share_contributions.csv')
paragraph('The two models with a modal redistribution ratio above 0.3',rev(r'The modal-share ratio is available once a reduced model has been formed and can be used alongside frequency and response errors to inspect the effect of a retained-coordinate choice. Its separate coordinate contributions are particularly useful when a horizontal coordinate is condensed. Stability is assessed from the delayed closed-loop model, including its regulator and integration algorithm; the present ratio provides no threshold for the admissible channel delays.'),'删除0.3阈值及扫描前稳定性排名','新数据中只有第二种划分Guyan超过0.3；旧文“两种Guyan都超过0.3”的经验依据已经不存在。保留指标作为缩聚诊断的使用价值。',old_zh='原文称两种Guyan均超过0.3，并据此可在扫描前给稳定性排序。',new_zh='改为结合频率与响应误差检查保留坐标选择，稳定性仍由实际延迟闭环评估。')
replace_in_para('The accuracy and the stability results together indicate',[
('keeps the frequency error below 1\\% and the NRMSE below 0.06\\% in every case examined',rev('limits the first-two-mode frequency error to 0.284\\% and the first-storey NRMSE to 0.138\\% over the evaluated earthquake record and chirp bands')),
('Guyan condensation produces the smallest reduced model, at six generalized coordinates against twelve for Craig--Bampton.',rev('The full-frame Guyan models use six and five generalized coordinates, compared with nine and eight for Craig--Bampton.')),
('its NRMSE reaches 1.995\\% in the band around the fundamental frequency',rev('its NRMSE reaches 2.010\\% in the fundamental-frequency band and 2.041\\% in the highest band')),
('24.575\\% and its NRMSE reaches 19.059\\%',rev('30.574\\% and its NRMSE reaches 26.858\\%'))
],'方法适用性：保留原段，更新误差与实际阶数','保留原有工程取舍讨论，删除过时数值和6/12阶对当前精度模型的误用。','表格联动文字',source='表3/4、实际缩聚矩阵维数',old_zh='CB误差低于1%/0.06%，Guyan六阶对CB十二阶，第二种划分最大24.575%/19.059%。',new_zh='CB最大0.284%/0.138%，实际精度模型6/9和5/8阶；Guyan第二种划分30.574%/26.858%。')
replace_in_para('This study establishes a joint assessment',[
('whose equations carry no explicit actuator-delay operator but remain dynamically coupled to the delayed channels.',rev('which are not directly delayed by the actuators and remain dynamically coupled to the delayed channels.'))
],'结论第一段：纠正模态方程不含延迟的说法','与正文恢复关系保持一致，保留原方法总结及其工程动机。',old_zh='原文说模态坐标方程没有显式作动器延迟算子。',new_zh='改为模态坐标不直接经过作动器，仍与延迟通道动态耦合。')
replace_in_para('The numerical results for the two divisions',[
('0.834\\%',rev('0.284\\%')),
('remains below 0.06\\%', rev('has a maximum of 0.138\\%')),
('24.575\\% and 19.059\\%',rev('30.574\\% and 26.858\\%')),
('This division combines a larger physical substructure with condensation of the middle-storey horizontal DOF.',rev('This retained-coordinate set eliminates the middle-storey horizontal DOF. At that reconstructed coordinate, the Guyan earthquake/chirp NRMSE values are 10.798\\%/11.749\\%, compared with 0.031\\%/0.034\\% for Craig--Bampton.')),
('with six generalized DOFs compared with twelve for Craig--Bampton',rev('with six/five generalized DOFs compared with nine/eight for Craig--Bampton in divisions I/II'))
],'结论第二段：表格联动并纳入中层验证','更正所有定量总结，同时把新增图的主要结果写入结论，使新增图片服务于论文结论。','表格联动文字',source='三表与新增中层指标的独立复核',old_zh='原结论重复旧最大误差和六阶/十二阶，并未验证中层。',new_zh='更新误差、实际阶数，并加入未保留中层在地震/扫频下的四个NRMSE。')
replace_in_para('In both divisions, the Craig--Bampton model has a larger stable delay region',[
('In both divisions, the Craig--Bampton model has a larger stable delay region than the Guyan model.',rev('In the reference delay-domain comparison, the Craig--Bampton model--regulator pair has a larger stable region than the Guyan pair in both divisions.')),
('The modal redistribution ratios are 0.1879 and 0.2021 for Craig--Bampton and 0.3065 and 0.3927 for Guyan in divisions I and II, respectively. Their ordering is consistent with the relative contraction of the stability regions and supports their use as a comparative model-selection indicator, with stability determined by the closed-loop poles.',rev('The full-frame modal redistribution ratios are 0.0039 and 0.0365 for Craig--Bampton and \\(-0.0414\\) and 0.8914 for Guyan in divisions I and II, respectively. Their coordinate-wise contributions describe the change in low-order modal distribution; closed-loop poles remain the criterion for delay stability.')),
('provides the stronger accuracy--stability balance in the cases examined.',rev('combines higher response accuracy with the larger reference delay domains in the cases examined.'))
],'结论第三段：更新指标并限制稳定性归因','表5数值和排序均改变，且当前响应矩阵不等于历史稳定性矩阵；以参考比较和模型-控制器联合结果措辞表达已知信息。','表格联动文字',source='表5复算、历史边界来源及审稿意见3/8',old_zh='原结论给0.1879/0.2021与0.3065/0.3927，并宣称指标能为稳定域排序。',new_zh='改为0.0039/0.0365与-0.0414/0.8914；指标解释份额，稳定性结论限定于参考模型与配套调节器。')

# Figure replacements are explicit operations and keep their substantive reasons separate.
for oldfile,newfile,title,caption in [
('fig01_rths_loop_optionD.png','fig01_force_feedback.pdf','图1：按式(3.6)重绘附加力反馈路径','Virtual MDOF RTHS model with delayed physical reactions and an additional delayed force feedback.'),
('fig03_benchmark_geometry_optionC.png','fig02_geometry.pdf','图2：英文原型几何与截面图','Geometry and member sections of the reference frame; dimensions in mm. The numerical section properties are specified in the text.'),
('fig04b_dof_idealized_optionD.png','fig03_dofs.pdf','图3：保留节点及15坐标，修正数值柱脚','Degrees of freedom and node numbering of the idealized numerical model.')]:
    old=next(x.group() for x in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',text,re.S) if oldfile in x.group())
    new=old.replace(oldfile,newfile)
    new=re.sub(r'\\caption\{[^\n]+\}',lambda _:r'\caption{'+rev(caption)+'}',new)
    reason={'fig01_rths_loop_optionD.png':'原图位移跟踪器与保留的延迟力反馈方程不一致，图中明确两条延迟反力/调节力回路。','fig03_benchmark_geometry_optionC.png':'统一图内英文并去除旧中文图号，保留原型混合支座、W5×16、梁I截面和关键尺寸；将原型几何与实际数值模型分开。','fig04b_dof_idealized_optionD.png':'当前数值矩阵四柱脚固定；保留节点编号和全部15个坐标，避免上一版删减信息。'}[oldfile]
    change(old,new,title,reason,'示意图必要修订','原图、实际矩阵、正文闭环方程')
old=next(x.group() for x in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',text,re.S) if 'fig05a_divisionI_concept_optionD.png' in x.group())
new=figure('fig04_divisions','fig:division','Substructure divisions and local retained coordinates. (a) Division I. (b) Division II. The physical and numerical coordinate sets are listed in Table \\ref{tab:dof-sets}.','.98')
change(old,new,'图4：保留双侧子结构与坐标信息的英文重绘','保留两种划分、数值侧/物理侧分开示意、作动通道和主要保留坐标；物理侧柱脚节点由原图2/3更正为全局编号1/2，首层节点由6/7更正为5/6（标红）。图注说明这是局部配置，避免误认成实际整体精度模型。','示意图必要修订','原两张图、图3全局节点顺序、表2坐标集合')

# Exact duplicates are merged, with retained entries left otherwise unchanged.
bib=(NEW/'revision_evidence/baseline/references_before.bib').read_text(encoding='utf-8')
for duplicate,retained in [('CraigBampton1968','Craig1968'),('ChenRicles2008b','ChenCR2008')]:
    old=rf'\cite{{{duplicate}}}';change(old,rev(rf'\cite{{{retained}}}'),f'重复文献引用：{duplicate}合并到{retained}','同一篇文献重复占用编号；只统一引用键，保留已有文献资料。','格式与文献整理','原references.bib重复条目')
    pattern=rf'(?ms)^@\w+\{{{duplicate},.*?(?=^@|\Z)';m=re.search(pattern,bib);assert m,duplicate
    removed=m.group();bib=bib[:m.start()]+bib[m.end():]
    ops.append(dict(id=f'change-{len(ops)+1:03d}',title=f'文献库：删除重复条目{duplicate}',category='格式与文献整理',old=removed,new='',retained_entry=retained,reason='两个引用键指向同一文献，避免参考文献列表重复。',source='references_before.bib',file='references.bib'))

# Format-only changes follow all content operations. The original negative skips stay active.
change(r'\usepackage{lineno}',r'\usepackage{lineno}'+'\n'+r'\usepackage[section]{placeins}',
       '浮动图：限定图片在相应正文节内','逐页检查发现大图使后续图片全部积压到参考文献后。使用节边界浮动控制，让图片回到对应分析区域。','格式与文献整理','本轮真实PDF版面检查')
change(r'\allowdisplaybreaks',r'\allowdisplaybreaks'+'\n'+r'\renewcommand{\floatpagefraction}{.65}',
       '浮动页：允许较大图片及时单独成页','原CAS要求浮动页占用90%，使部分大图无法及时输出。只调整图件浮动阈值，保留所有公式负间距。','格式与文献整理','本轮真实PDF版面检查')
change(r'\includegraphics[width=.98\textwidth]{fig04_divisions.pdf}',r'\includegraphics[width=.98\textwidth,height=.74\textheight,keepaspectratio]{fig04_divisions.pdf}',
       '图4尺寸：增加等比例高度上限','两行子结构示意图较高，为其增加正文高度74%的上限；保持纵横比和全部内容。','格式与文献整理','本轮真实PDF版面检查')
for marker in [r'\subsection{Response accuracy under earthquake and chirp excitation}',r'\subsection{Stability domains under multiple actuator delays}',r'\subsection{Modal redistribution ratio and applicability of the two methods}',r'\bibliographystyle{elsarticle-num-names}']:
    change(marker,r'\FloatBarrier'+'\n'+marker,'图文相邻：在'+marker.split('{')[1].split('}')[0]+'之前输出前序图片','使相应结果图留在该小节内，避免读者在后文寻找图件；不调整公式行距。','格式与文献整理','本轮真实PDF版面检查')

assert re.findall(r'\\vspace\{-[^}]+\}',text)==re.findall(r'\\vspace\{-[^}]+\}',baseline)
assert len(re.findall(r'\\vspace\{-[^}]+\}',text))==42
assert text.count(r'\begin{figure}')==15,text.count(r'\begin{figure}')
assert not any(ord(c)<32 and c not in '\n\t' for c in text),'Unexpected control character'
(NEW/'main.tex').write_text(text,encoding='utf-8')
(NEW/'references.bib').write_text(bib,encoding='utf-8')
(NEW/'revision_evidence/change_operations.json').write_text(json.dumps(ops,ensure_ascii=False,indent=2),encoding='utf-8')
(NEW/'revision_evidence/main_changes.diff').write_text(''.join(difflib.unified_diff(baseline.splitlines(True),text.splitlines(True),fromfile='main_before.tex',tofile='main.tex')),encoding='utf-8')
if Path(__file__).resolve()!=(NEW/'revision_evidence/code/revise_manuscript.py').resolve():shutil.copy2(__file__,NEW/'revision_evidence/code/revise_manuscript.py')
print(json.dumps({'operations':len(ops),'negative_spacing_preserved':42,'figures':15,'old_characters':len(baseline),'new_characters':len(text)},ensure_ascii=False))
