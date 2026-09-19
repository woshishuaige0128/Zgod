from pathlib import Path
import re, json, hashlib, shutil, difflib

ROOT=Path(r'D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master')
SRC=ROOT.parent/'260817/elsevier'
OUT=ROOT.parent/'260817/elsevier_review_20260906'
AUD=ROOT/'figure/表3至表5_按当前出图设置核查_20260906'
HERE=Path(__file__).resolve().parent
assert not OUT.exists(), 'Refuse to overwrite an existing derivative'
OUT.mkdir()
(OUT/'submit_figure').mkdir()
(OUT/'revision_evidence').mkdir()
source_hashes={str(p.relative_to(SRC)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SRC.rglob('*') if p.is_file()}
(OUT/'revision_evidence/source_hashes.json').write_text(json.dumps(source_hashes,indent=2),encoding='utf-8')
for p in SRC.iterdir():
    if p.is_file() and p.suffix in ('.cls','.sty','.bst','.jpeg','.bib'):
        shutil.copy2(p,OUT/p.name)
for p in (SRC/'submit_figure').iterdir():
    if p.is_file(): shutil.copy2(p,OUT/'submit_figure'/p.name)
original=(SRC/'main.tex').read_text(encoding='utf-8')
s=original
changes=[]
def rep(old,new,reason):
    global s
    assert old in s, (reason,old[:120])
    s=s.replace(old,new)
    changes.append(reason)
def red(t): return r'\rev{'+t+'}'
def para(start,new,reason):
    old=next((x for x in s.split('\n\n') if x.startswith(start)),None)
    assert old is not None,start
    rep(old,red(new),reason)
def region(start,end,new,reason):
    a=s.index(start);b=s.index(end,a)
    rep(s[a:b],new+'\n\n',reason)

# One user-authorized revision board; preserve all unrelated research boards.
wf=ROOT/'WORKFLOW.md'
w=wf.read_text(encoding='utf-8')
plan='''## 板块30：表3至表5修正与审稿意见选择性改稿（2026-09-06）

用户已要求按当前出图设置修改三表及全文相关内容，审稿意见仅采纳正确且必要的部分，修改标红并遵循 anti-defensive-writing。交付为独立 `260817/elsevier_review_20260906`，原稿、原图和计算资产不改。

1. 冻结源目录 SHA-256，建立可独立编译副本；验证全部源文件前后哈希一致。
2. 按已核查的44项数据修改三表、摘要、方法、结果、结论，核对当前整体缩聚及6/9、5/8自由度；验证表格逐格与审计JSON一致、旧数值与旧阶数结论清零。
3. 逐条裁决审稿意见，修正过强推论、模态指标含义、LQR信号示意、激励/质量/阻尼设置及图内语言；当前证据不支持的新计算不冒充已完成，写入修改说明。
4. pdfLaTeX→BibTeX→pdfLaTeX两遍，零错误、零未定义引用与??；逐页渲染核对文字、表格与红色标注，交付PDF、TeX及修改说明。

'''
w=w.replace('## TODO List',plan+'## TODO List',1)
w+='\n- [ ] 板块30：表3至表5修正与审稿意见选择性改稿（用户授权2026-09-06；执行中）\n'
wf.write_text(w,encoding='utf-8')
(ROOT/'current.md').write_text('''<!-- 【在工作前，需要首先启动paper-writing skill，这一行不要删除！！】 -->
# Current - 工作现场快照

## 当前所在 WORKFLOW 板块
板块30：表3至表5修正与审稿意见选择性改稿。

## 当前正在执行的具体操作
建立独立副本，按真实出图设置修正三表和全文；以红色标注，压缩无必要解释。

## 上一步操作的结果
三表44项双语复核通过；当前模型为整体缩聚6/9和5/8自由度，历史稳定域生成参数未闭合。

## 下一步计划
实际编译、逐页渲染、数值与标红检查，更新验收结果。

## 关键上下文
原稿260817/elsevier/main.tex；副本260817/elsevier_review_20260906/main.tex；测试tmp/manuscript_review_20260906。

## 遇到的问题/阻塞点
稳定域历史图不能由当前可用参数唯一复算；如实保留该科学边界，不阻塞有依据的修订。
''',encoding='utf-8')

rep(r'\usepackage{xurl}',r'\usepackage{xurl}'+'\n'+r'\usepackage{tikz}'+'\n'+r'\usetikzlibrary{arrows.meta,positioning,calc}', '图内英文矢量示意')
rep('% C5 text is current; non-DOI revision wrappers are removed while DOI placeholders remain red.','% Revisions dated 2026-09-06 are marked in red; the source manuscript is preserved.', '修订标识')

# Concise abstract tied to the verified accuracy route.
region('Limited actuation channels motivate',r'\end{abstract}',red(r'''Limited actuation channels motivate the condensation of interface degrees of freedom (DOFs) in multi-degree-of-freedom real-time hybrid simulation (RTHS). This study examines the accuracy of static and Craig--Bampton reductions and formulates a channel-specific delay model with CR integration and linear quadratic regulator feedback. Two coordinate selections associated with divisions of a three-storey frame are evaluated. The delay-free benchmark uses whole-structure reductions with six and five retained physical coordinates, respectively; Craig--Bampton enrichment adds three fixed-interface modal coordinates. Its maximum relative error in the first two natural frequencies is 0.284\%, and its first-storey displacement normalized root mean square error reaches 0.138\% over the earthquake record and evaluated chirp bands, using the full-record response range for normalization. For the static model that condenses the middle-storey horizontal DOF, the corresponding maxima are 30.574\% and 26.858\%. The reported stability boundaries place Craig--Bampton above the static model in both divisions. A signed modal-share index describes changes at the actuated coordinates, while admissible delays are assessed through the closed-loop poles. The results show the accuracy gained by retaining internal modal dynamics and identify the model and feedback definitions required for delay-dependent comparison.'''),'摘要数值与证据范围同步')
para('This paper establishes a joint accuracy',r'''This paper examines condensation accuracy and formulates delay-dependent stability for actuation-constrained MDOF RTHS. Static constraint modes and Craig--Bampton enrichment provide the reduced representations, and channel-specific delay operators describe their feedback paths. A discrete-time characteristic equation incorporates CR integration and a linear quadratic regulator. Frequency errors and displacement errors assess the implemented reductions, while a signed modal-share index describes changes at the actuated coordinates.''','引言贡献与实际证据一致')

# Theory: write a complete conditional released-interface assembly, not a claim of validation.
para('The two substructures are condensed separately',r'''For separately condensed substructures, assembly identifies the interface coordinates retained on both sides. The coordinate maps and assembled mass matrix are
\(\bm q_s=\mathbf A_s\bm q\) and
\(\mathbf M_{\mathrm{red}}=\sum_{s\in\{\mathrm n,\mathrm e\}}\mathbf A_s^{\mathsf T}\mathbf T_s^{\mathsf T}\mathbf M_s\mathbf T_s\mathbf A_s\),
where \(\mathbf A_s\) maps the assembled coordinates to the reduced coordinates of substructure \(s\). Damping, stiffness and loading are assembled by the corresponding transformations. The assembled equation is''','明确子结构装配映射')
para(r'\noindent where \(\bm{q}(t)\) collects the generalized coordinates of the two',r'''\noindent where \(\bm q(t)\) counts each shared retained interface coordinate once. At these coordinates, displacement compatibility and interface-force equilibrium are enforced. A released, unactuated interface has zero interaction force, and its coordinates are recovered separately on each side. This defines a partially coupled parent model.''','未耦合接口力学条件明确')

para(r'\noindent where \(\Delta t\) is the integration time step',r'''\noindent where \(\Delta t\) is the integration time step, \(n_\ell\) is a non-negative integer, \(n_{\mathrm a}\) is the number of actuator channels, and \(u_{\mathrm r,\ell}\) and \(\hat u_{\mathrm r,\ell}\) are the commanded and imposed displacements. The pure-delay model represents the phase lag of each channel. Figure \ref{fig:rths-loop} shows the signal paths used in the virtual closed-loop formulation: numerical states generate the displacement command and the regulator force, and channel delays act on both paths.''','时滞和反馈信号统一')
rep(r'\includegraphics[width=0.96\textwidth]{fig01_rths_loop_optionD.png}',r'\input{submit_figure/fig01_force_feedback.tex}','用力反馈图对应式3.6')
rep(r'\caption{Closed loop of an MDOF RTHS with multiple actuators.}',r'\caption{\rev{Signal paths of the virtual RTHS with delayed restoring-force and LQR feedback.}}','反馈图图注')
para('for Guyan and Craig--Bampton condensation, respectively.',r'''for Guyan and Craig--Bampton condensation, respectively. The Guyan reconstruction depends on the delayed retained coordinates. The Craig--Bampton modal coordinates \(\bm\eta\) evolve numerically and couple to the delayed retained coordinates through the reduced equations. They do not pass directly through an actuator channel.''','模态坐标不直接时滞不等于方程无时滞')
para('A linear quadratic regulator acts on the actuated coordinates',r'''An LQR supplies an additional force at the actuated coordinates. Its design model is obtained by static condensation of the assembled model onto those coordinates, using their displacements and velocities as states and the applied forces as inputs. The quadratic state and input weights \(\mathbf Q\) and \(\mathbf R\) define the feedback law''','控制器定义简化')
para('The regulator output is a generalized force.',r'''The regulator uses the numerical states \(\mathbf S_{\mathrm a}\bm q\) and \(\mathbf S_{\mathrm a}\dot{\bm q}\). Its applied force is
\(\bm f_{\mathrm{L,applied}}(z)=\mathbf S_{\mathrm a}^{\mathsf T}\mathbf H_{\mathrm a}(z)\bm f_{\mathrm L}(z)\),
which enters the right-hand force sum of Eq. \eqref{eq:delayed-eom}. Here \(\mathbf H_{\mathrm a}\) is diagonal with entries \(z^{-n_\ell}\). The law is an output feedback on the assembled model. Equal \(\mathbf Q\) and \(\mathbf R\) yield model-dependent gains, so the resulting domains compare each model together with its regulator.''','明确力输入求和点与联合比较')

# Actual benchmark and model route.
rep('and the material data of the multi-axial RTHS benchmark frame','of the multi-axial RTHS benchmark frame','避免基准物性与实际模型混称')
rep('The geometry and the section dimensions are shown in Fig. \\ref{fig:benchmark-geometry}, and the material properties are listed in Table \\ref{tab:materials}.',red(r'The geometry is shown in Fig. \ref{fig:benchmark-geometry}, and Table \ref{tab:materials} lists the material properties used in the model.'),'材料设置实际口径')
rep(r'\includegraphics[width=0.89\textwidth]{fig03_benchmark_geometry_optionC.png}',r'\input{submit_figure/fig02_geometry.tex}','基准框架英文示意')
rep(r'\caption{Geometry and member sections of the benchmark frame.}',r'\caption{\rev{Geometry of the three-storey frame used in the accuracy benchmark. Dimensions are in mm.}}','几何图图注')
rep('& 200 & 0.3 & 7850',r'& \rev{206} & 0.3 & 7850','实际弹性模量206GPa')
rep(r'\includegraphics[width=0.77\textwidth]{fig04b_dof_idealized_optionD.png}',r'\input{submit_figure/fig03_dofs.tex}','15自由度英文矢量图')
rep(r'\caption{Degrees of freedom of the idealized model.}',r'\caption{\rev{Coordinate order of the fifteen-DOF model: three storey translations and twelve nodal rotations.}}','自由度图图注')
para('The full-order equation of motion is Eq.',r'''The accuracy benchmark fixes the translations and rotations at all four column bases. It uses \(A_{\mathrm c}=1.670\,\mathrm{in}^{2}\), \(A_{\mathrm b}=0.947\,\mathrm{in}^{2}\), \(I_{\mathrm c}=2.520\,\mathrm{in}^{4}\) and \(I_{\mathrm b}=0.6132\,\mathrm{in}^{4}\). The diagonal mass matrix repeats one five-entry block per storey: a translational mass of 6164.8306 kg followed by rotational inertias of 51.0878, 67.8872, 67.8872 and 51.0878 kg\,m\(^{2}\). These values use an effective mass density of \(190\times7850\) kg/m\(^{3}\) in the lumped-mass construction. Rayleigh damping, \(\mathbf C=a_0\mathbf M+a_1\mathbf K\), gives 5\% damping at the first two modes, with \(a_0=1.3184625\) s\(^{-1}\) and \(a_1=0.0013223424\) s. The same full-order damping matrix is reduced with each model. The first five frequencies are 2.7074, 9.3284, 18.4427, 22.6736 and 24.2277 Hz, accounting for 98.0608\% of the horizontal effective modal mass. The full matrices and coordinate order are supplied in the supplementary data.''','质量阻尼基底边界及频率按真实代码修正')
rep('The physical substructure holds about 40\\% of the DOFs of the whole structure.','', '删除按接口重复计数给出的比例')
rep('More DOFs are kept at the interface, which represents the modal coupling between the storeys more completely, and the physical substructure holds about 60\\% of the DOFs of the whole structure.','', '删除扩大接口即更完整的推论')
para('Both divisions are limited to two independent actuation channels.',r'''Both divisions assign two actuator channels. They act at \(\psi_1,\psi_6\) in division I and at \(\psi_1,\psi_{11}\) in division II. The accuracy comparison uses the corresponding whole-structure coordinate selections in Table \ref{tab:dof-sets}. Division II condenses the middle-storey translation \(\psi_6\), whereas division I retains all three storey translations. Both selections retain the rotations \(\psi_4,\psi_9,\psi_{14}\).''','明确整体保留坐标与作动坐标不同')
para('Three rotations of the numerical substructure are retained',r'''For the accuracy calculations, reduction is applied once to the assembled fifteen-DOF matrices. Each reduced response is expanded to the original coordinate order, giving one recovered value per coordinate.''','当前精度模型单一恢复值')
region(r'\includegraphics[width=0.89\textwidth]{fig05a_divisionI_concept_optionD.png}',r'\label{fig:division}',r'''\input{submit_figure/fig04_divisions.tex}
\caption{\rev{Substructure divisions and actuator assignments. Shading marks the designated physical region; arrows mark the two actuator channels.}}
''','划分图英文统一')
start=s.rfind(r'\begin{table}',0,s.index(r'\label{tab:dof-sets}'))
end=s.index(r'\end{table}',start)+len(r'\end{table}')
rep(s[start:end],r'''\begin{table}[htbp]
\centering
\caption{\rev{Whole-structure coordinate selections used in the accuracy calculations.}}
\label{tab:dof-sets}
{\color{red}
\begin{tabular}{lllcc}
\toprule
Division & Retained coordinate indices & Actuated indices & Static order & CB order\\
\midrule
I & 1, 6, 11, 4, 9, 14 & 1, 6 & 6 & 9\\
II & 1, 11, 4, 9, 14 & 1, 11 & 5 & 8\\
\bottomrule
\end{tabular}}
\end{table}''','表2改为与真实计算一致的坐标与阶数')
para('The three fixed-interface modes of lowest frequency are retained',r'''The Craig--Bampton models use the three lowest fixed-interface modes of the global condensed set and the congruent projection of Eq. \eqref{eq:general-projection}. The static implementation used for the reported accuracy results retains the first block row after imposing \(\bm u_{\mathrm c}=\bm\Psi_{\mathrm G}\bm u_{\mathrm r}\):
\(\mathbf M_{\mathrm G}=\mathbf M_{\mathrm{rr}}+\mathbf M_{\mathrm{rc}}\bm\Psi_{\mathrm G}\),
\(\mathbf C_{\mathrm G}=\mathbf C_{\mathrm{rr}}+\mathbf C_{\mathrm{rc}}\bm\Psi_{\mathrm G}\), and
\(\mathbf K_{\mathrm G}=\mathbf K_{\mathrm{rr}}+\mathbf K_{\mathrm{rc}}\bm\Psi_{\mathrm G}\), with
\(\bm f_{\mathrm G}=\mathbf T_{\mathrm G}^{\mathsf T}\bm f\).
It is labelled Guyan in the tables and response plots. This retained-equation implementation differs from the congruent Guyan projection of Section \ref{sec21}; the accuracy results refer to the stated implementation.''','准确标出Guyan单侧实现而非冒充双侧投影')
para('The full-order model, the Guyan condensed model',r'''The full-order and reduced equations are integrated in Simulink using fixed-step fourth-order Runge--Kutta integration, with \(\Delta t=1/1024\) s, a 40 s duration and zero initial conditions. Accuracy calculations set \(\bm f_{\mathrm L}=\bm0\) and all delays to zero. The full seismic force is projected into each reduced system, and storey displacements are recovered through its transformation matrix.''','真实求解器且LQR明确关闭')
para('Two excitations are adopted.',r'''The earthquake input is the El Centro 1940 north--south acceleration record in m/s\(^{2}\), multiplied by 0.40 and linearly interpolated during integration. The chirp acceleration is \(a_{\mathrm g}(t)=\sin[2\pi(0.1)t+\pi(0.2475)t^2]\) m/s\(^{2}\) for \(0\leq t\leq40\) s, with unit amplitude and zero initial phase. Its instantaneous frequency, \(f(t)=0.1+0.2475t\), crosses the first two modes.''','激励定义与删除未验证屈服保证')
para('The stability analysis adopts the closed loop',r'''The stability formulation uses the same sampling period and the two channel assignments above, with independent constant delays. The specified regulator weights are \(\mathbf Q=\mathrm{diag}(10^6,10^6,10^4,10^4)\) and \(\mathbf R=\mathrm{diag}(10^{-2},10^{-2})\), ordered by the two displacements and then their velocities. Figure \ref{fig:stability-domain} retains the boundary data from the original analysis; its generating substructure matrices and regulator gains are not available as a complete reproducible set. The current whole-structure accuracy calculations therefore supply Tables \ref{tab:modal}--\ref{tab:energy} independently of those boundary data.''','科学缺口集中写一次')
rep('A value close to unity indicates preserved mode shape components on the retained coordinates.',red(r'The retained translations are expressed in metres and rotations in radians without further scaling. This MAC is specific to that coordinate convention.'),'MAC混合量纲坐标约定')
para('For the chirp excitation, the NRMSE is evaluated separately',r'''The chirp bands use the frequency limits 0.1, 1.9, 3.5, 5.4, 8.1 and 10 Hz. These limits approximate multiples of the 2.7074 Hz fundamental frequency and are used directly to define the integration intervals through \(t=(f-0.1)/0.2475\). Squared errors are integrated by the trapezoidal rule, with linear interpolation at the band endpoints. The 1.9--3.5 Hz band spans 7.2727--13.7374 s. Each band includes transients generated earlier in the sweep, so the values describe changes across sweep stages.''','固定实际频段与数值积分约定')
para('The effect of condensation on the stability is quantified',r'''A signed modal-share index describes the change at the actuated coordinates. For mass-normalized modes, the coordinate share is''','指标定义去除能量转移等同')
rep('The mode shapes of a condensed model are expanded to the full coordinate set through its own transformation matrix before Eq. \\eqref{eq:dof-energy} is applied, which evaluates the two shares on the same coordinates. The modal redistribution ratio is then obtained as',red(r'Each reduced mode is expanded by its global transformation, restored to the original fifteen-coordinate order and normalized using \(\bm\varphi_i^{\mathsf T}\mathbf M\bm\varphi_i=1\) with the full-order mass matrix. The first five modes of each model are used, with their own participation weights. The signed index is'),'扩展模式归一化闭合')
para(r'\noindent where \(d_{k}\) is the',r'''\noindent where \(d_k\) is an actuated coordinate and \(E^{\mathrm{full}}\) and \(E^{\mathrm{red}}\) are the corresponding modal shares. The index sums their relative changes and retains their signs. It describes a mass-weighted modal distribution; the closed-loop poles determine delay stability.''','保留原公式改物理解释')
para('The two condensed models of each division are compared',r'''The results compare the modal properties and delay-free responses of the implemented reductions, followed by the reported stability boundaries and the signed modal-share indices.''','结果导语简化')

# Exact 44-cell replacement, only changed cells marked red.
rows=json.loads((AUD/'results/python_results.json').read_text(encoding='utf-8'))['rows']
for label,table in [('tab:modal',3),('tab:nrmse',4),('tab:energy',5)]:
    a=s.index(r'\label{'+label+'}');b=s.index(r'\end{table}',a)
    body=s[a:b];items=[r for r in rows if r['table']==table];k=0
    new=[]
    for line in body.splitlines():
        if '&' in line and re.search(r'^\s*(I\s|II\s|El Centro|Chirp,)',line):
            cells=line.split('&');offset=2 if table==3 else 1
            for j in range(offset,len(cells)):
                r=items[k];k+=1
                val=r['rounded_value'];val=val.replace('<',r'$<$')
                if r['status']=='不符':val=red(val)
                tail=r'\\' if j==len(cells)-1 else ''
                cells[j]=' '+val+tail
            line='&'.join(cells)
        new.append(line)
    assert k==len(items),(label,k)
    rep(body,'\n'.join(new)+'\n',f'表{table}逐格数据校正')

para('The relative errors of the first two natural frequencies',r'''Table \ref{tab:modal} compares the two reference modes within the 0.1--10 Hz excitation range, at 2.7074 and 9.3284 Hz. The maximum Craig--Bampton frequency error is 0.284\%. The Guyan errors are 0.648\% and 5.411\% in division I, increasing to 19.040\% and 30.574\% in division II.''','模态结果数值同步')
para('The two divisions differ in that division II condenses',r'''Condensing the middle-storey translation makes the static model more sensitive to the approximation of internal dynamics. The implemented Guyan model shifts both frequencies upward in division II. Craig--Bampton enrichment retains internal vibration patterns and reduces these errors to 0.024\% and 0.108\%.''','删除完整模型Ritz上界推论')
para('The MAC values behave differently.',r'''The retained-coordinate MAC remains above 0.92 in every case. In division II, the Guyan second-mode MAC is 0.9255 despite a 30.574\% frequency error. Retained-coordinate correlation alone therefore gives an incomplete measure of dynamic accuracy; it must be considered alongside the frequency and response errors.''','MAC结论简洁且不过度归因')
para('Figs. \\ref{fig:eq-div1} and',r'''Figs. \ref{fig:eq-div1} and \ref{fig:eq-div2} compare first- and third-storey displacements under El Centro excitation. The Guyan deviation is modest in division I and more pronounced in division II, while Craig--Bampton follows the reference closely. The recovered middle-storey displacement in division II gives full-record NRMSE values of 10.798\% for Guyan and 0.031\% for Craig--Bampton. These values evaluate the single global recovery of \(\psi_6\) used in the accuracy model.''','加入未保留中层已有数据误差')
para('Figs. \\ref{fig:chirp-div1} and',r'''Figs. \ref{fig:chirp-div1} and \ref{fig:chirp-div2} show the chirp responses. The sweep crosses the reference fundamental frequency at 10.5351 s, and the largest absolute reference displacement occurs near 11.69 s. The 13--14 s insets show the subsequent resonant response.''','纠正13s峰值和扫频过频时间')
para('In division I the Guyan response deviates',r'''In division I, the Guyan deviation grows again in the 38--38.3 s window, near the second-mode response. In division II, the shifted static-model resonances produce larger amplitude and phase differences. Over that final window, its first- and third-storey peak-to-peak displacements are 46\% and 81\% of the reference values, respectively. Craig--Bampton follows the reference throughout the sweep. For the recovered middle-storey displacement in division II, the full-record NRMSE is 11.749\% for Guyan and 0.034\% for Craig--Bampton.''','纠正第三层近两倍错误并补中层误差')
para('Table \\ref{tab:nrmse} gives',r'''Table \ref{tab:nrmse} reports first-storey displacement errors. Under El Centro excitation, the Guyan NRMSE is 0.802\% in division I and 10.911\% in division II; the Craig--Bampton values are 0.014\% and 0.029\%. For the chirp, division II gives the largest Guyan error, 26.858\%, in the 1.9--3.5 Hz band. Its error falls to 0.129\% in the 5.4--8.1 Hz band and rises to 3.020\% in the final band. In division I, the final band gives the largest Guyan and Craig--Bampton errors, 2.041\% and 0.138\%, respectively. The shared full-record denominator expresses these as errors relative to the total response range.''','表4全文分析重写防止单调与小于0.06误报')
para('Two observations follow.',r'''The errors depend on both the retained coordinate set and the sweep stage. Retaining the middle-storey translation improves the static response, while fixed-interface modal enrichment preserves accuracy when that translation is condensed. The differing physical coordinate counts are part of this comparison.''','删除两类同阶断言')
para('The stability domains obtained from the pole criterion',r'''Figure \ref{fig:stability-domain} shows the reported boundaries in physical delay units. The plotted values use \(\tau_\ell=n_\ell\Delta t\), with one integer step equal to 0.9765625 ms. The Original curves represent the ideal full-interface reference.''','边界单位准确且不虚构新极点验证')
para('The recovery relations of Section',r'''The two reductions couple the physical substructure to the delayed channels differently. Guyan recovers its condensed response from the actuated coordinates, whereas Craig--Bampton adds numerical modal states coupled to those coordinates. Both retain two delay channels. The stability ordering also depends on the reduced matrices, regulator gains and integration algorithm.''','稳定性机制限定为耦合关系')
para('The stability domain of the unreduced model is itself smaller',r'''The reference region is smaller in division II, which changes both the physical substructure and the second actuator location. The separations within each panel compare the reduced models together with their corresponding regulators.''','稳定域归因含调节器')
rep(r'\subsection{Modal redistribution ratio and applicability of the two methods}',r'\subsection{\rev{Signed modal-share index and model accuracy}}','指标小节名')
para('The modal redistribution ratio of Eq.',r'''Table \ref{tab:energy} gives the signed modal-share index from Eq. \eqref{eq:energy-change}, evaluated using the same models as the accuracy comparison. Craig--Bampton gives 0.0039 and 0.0365 in divisions I and II, respectively. Guyan gives -0.0414 and 0.8914, showing a much larger change in division II.''','表5分析与新值一致')
rep(r'\caption{Modal redistribution ratio of the four condensed models.}',r'\caption{\rev{Signed modal-share index of the four accuracy models.}}','表5表意修正')
region('Table \\ref{tab:energy} is the quantitative counterpart',r'\section{Conclusions}',red(r'''The small Craig--Bampton indices accompany its low frequency and displacement errors. The negative Guyan value in division I shows why the signed index cannot provide a universal ranking of delay tolerance. Its role is to describe changes in the modal shares at the selected coordinates.

For the tested coordinate selections, Craig--Bampton provides the more accurate reduced response. The Guyan implementation uses three fewer generalized coordinates, but its maximum first-storey NRMSE rises from 2.041\% in division I to 26.858\% in division II. The choice of retained physical coordinates and the representation of internal dynamics both matter for response fidelity.''')+'\n\n','删除能量转移解释和0.3阈值排序')
region('This study establishes a joint assessment',r'\bibliographystyle',red(r'''This study formulates channel-specific delay feedback for condensed MDOF RTHS and evaluates the accuracy of two whole-structure coordinate selections. Craig--Bampton enrichment adds numerical fixed-interface modal coordinates that couple to the delayed retained coordinates through the reduced equations.

The largest Craig--Bampton error in the first two natural frequencies is 0.284\%. Its first-storey displacement NRMSE reaches 0.138\% over the earthquake record and evaluated chirp bands, using the full-record response range for normalization. The corresponding Guyan maxima in division II are 30.574\% and 26.858\%. The recovered middle-storey displacement also benefits from modal enrichment: its full-record NRMSE is 0.031\% under earthquake excitation and 0.034\% under the chirp. A retained-coordinate MAC above 0.92 coexists with large static-model frequency errors, supporting the joint use of modal and response measures.

The reported boundaries place Craig--Bampton above Guyan in both divisions for their respective model--regulator combinations. The signed modal-share index describes the coordinate redistribution, while a delay-stability decision requires the complete closed-loop matrices and gains. Within the verified accuracy calculations, retaining three internal modes substantially improves response fidelity when the middle-storey translation is condensed.''')+'\n\n','结论同步数值证据并删除不支持排序')

# Deduplicate citations and bibliography (generated numbering changes automatically).
for alias,canonical in [('CraigBampton1968','Craig1968'),('ChenRicles2008b','ChenCR2008')]:
    s=s.replace(r'\cite{'+alias+'}',red(r'\cite{'+canonical+'}'))
bib=(OUT/'references.bib').read_text(encoding='utf-8')
for key in ['CraigBampton1968','ChenRicles2008b']:
    m=re.search(r'(?m)^@\w+\{'+key+r',',bib)
    assert m,key
    start=m.start(); nxt=re.search(r'(?m)^@',bib[m.end():]);end=m.end()+nxt.start() if nxt else len(bib)
    bib=bib[:start]+bib[end:]
(OUT/'references.bib').write_text(bib,encoding='utf-8')
(OUT/'main.tex').write_text(s,encoding='utf-8')
(OUT/'revision_evidence/main.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='protected_original/main.tex',tofile='revision/main.tex')),encoding='utf-8')
(OUT/'revision_evidence/change_operations.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(AUD/'results/python_results.json',OUT/'revision_evidence/table345_verified_values.json')
print('DERIVATIVE_CREATED',OUT)
print('EDIT_OPERATIONS',len(changes))
