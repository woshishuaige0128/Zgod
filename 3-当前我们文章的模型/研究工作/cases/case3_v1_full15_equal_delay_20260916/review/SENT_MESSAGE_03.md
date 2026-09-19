Doctor Bego已经授权采用前轮推荐路线并执行到案例分析完成：完整15坐标直接缩聚、明确虚拟补充协调、两个通道等时滞、零附加控制增益主研究，固定旧增益和慢扫频补充。现在请审查正式计算之前的理论修订与实现。

【传递范围】浏览器文件选择器连续超时，本消息没有声称成功上传新版附件。以下直接粘贴新版完整TeX、核心模型、两个Python核验入口和MATLAB交叉核验入口，连同模型定义及预先协议；矩阵仍是你前轮已经打开的3个MAT，逐文件SHA-256在末尾。新PDF已本地XeLaTeX编译并逐页看过，共5页、32式。ZIP虽已生成，未成功发送。请按实际收到的消息正文审查，不声称读取新版附件或复跑脚本。

【本地执行】Python核心1283项最大6.37013081146768e-12，补充224项最大2.3734906424859517e-12，MATLAB96项最大8.3275814403263974e-14，共1603项通过。矩阵恒等阈值1e-10，独立短序列推进阈值1e-9。新案例尚未扫描/计算；64步是实现核验。
【测试迭代如实说明】零目标T'KQ首轮错误地按1个SI单位归一，绝对残差约3.1e-10；改按乘积算子范数归一，阈值不变且原失败保存。连续算子导数的二点差分在大控制刚度下舍入误差1.12e-10，改成四阶中心差分，阈值未改。物理模型和数据不改动。

请重点回答：
1. 新版32式及代码中反馈投影、内部受载与输出误差、CR历史/行列式/有限卷积有无实质错误？逐条指出需改位置和替换式。
2. 是否可以据此启动匹配Full15的离散极点/频响及预定地震、定频撤载案例？若有阻断项，请限定为实质科学或数值问题。
3. 预先选点规则有无应在计算前修正的漏洞？不能事后按CB收益选点。整数延迟网格、临界精度、零/常态/近边界、稳态检查及不清除撤载历史是否齐全？
4. 第28—31式连续灵敏度只作局部解释，正式稳定边界由离散全根给出；是否需要额外明确简单根/遗漏块可逆等条件？

请先明确已读范围及是否实际运行，不把已有JSON数值称为独立复跑。控制在约2000字给明确结论即可，不扩展新论文路线；如需少量只读代数核查可做，避免运行正式工况。



===== MODEL_SPECIFICATION.md | SHA256 4a2eed85334b2e8ff591a10120978aba203ad7469d59e5293c8efd5d8298ffa6 =====
# 原完整框架的等时滞虚拟反馈模型

## 研究对象和来源
2026-09-16 用户授权执行紧邻讨论的完整框架直接缩聚路线。最终结构基准为原15自由度框架；所有科学输入冻结于data，SHA-256见source_manifest.json。两种划分分别定义其物理子结构贡献和作动坐标，缩聚均作用于已完整装配的15坐标。

| 项目 | 划分一 | 划分二 |
|---|---|---|
| 原坐标（1起算） | ψ1…ψ15 | ψ1…ψ15 |
| 保留坐标，按实现顺序 | 1,6,11,4,9,14 | 1,11,4,9,14 |
| 两个作动坐标 | 1,6 | 1,11 |
| 物理子结构坐标 | 1,2,3,6,7,8 | 1,2,3,6,7,8,11,12,13 |
| Guyan / CB保留3模态 / 全模态阶数 | 6 / 9 / 15 | 5 / 8 / 15 |
| 固定界面内部模态总数 | 9 | 10 |

## 运动、力、惯性和控制
S从15坐标选取两作动坐标，B=Sᵀ，D=BS。物理虚拟运动为xP=(I−D)x(t)+Dx(t−τ)。因此，未作动的物理内部坐标及未作动界面由当前数值运动补充协调；作动坐标使用同一纯时滞τ。物理反力为CP xP点+KP xP，数值贡献CN=C−CP、KN=K−KP。惯性Mx双点全部在数值侧推进。主案例附加控制增益为零，物理弹性/阻尼反馈保留。

这一定义明确了本研究的虚拟试验。它保留原完整结构的坐标兼容性，不能仅凭两个真实作动器就假定所有补充运动与力传递已实现。与旧18/19自由度的两坐标拼接系统属于不同的接口模型。

一般固定增益G=[Gd,Gv]时：C0=C−CPD，K0=K−KPD，Uc=CPB+BGv，Uk=KPB+BGd。运动方程为Mx双点+C0x点+K0x+UcSx点(t−τ)+UkSx(t−τ)=f ag。

## 缩聚、荷载和输出
Tg=[I;−Kcc⁻¹Kcr]按原坐标重排；CB在Tg后增加质量归一的固定界面内部模态。所有M/C/K/C0/K0采用TᵀAT，反馈采用TᵀU，测量采用ST，荷载采用Tᵀf，绝不在投影后重新挑选反馈列。

地震/扫频荷载f=Mγ，γ在楼层水平坐标1,6,11处为1；保持原记录符号、SI单位。数值楼层输出为Lx，物理恢复输出为L(I−D)x+LB Sx(t−τ)。主响应误差报告物理恢复，数值指令另存。层间角由三个楼层位移相邻作差除以0.635m。

划分二将中间层水平坐标6置于内部，因此fc不为零；Guyan的纯静力约束恢复缺少Kcc⁻¹fc ag项。该项是需验证的物理原因，不能偷偷补入标准Guyan以更改方法。

## 时间离散及初始历史
使用已指定CR算法，h=1/1024s，τ=nh，两通道n相同。Mhat=M+hC/2+h²K/4，仅含结构C/K。残余力req=f ag−C0v−K0q−UcSv延迟−UkSq延迟；算法加速度Mhat⁻¹req，平衡加速度M⁻¹req，二者明确区分。v下一步=v+h Mhat⁻¹req，q下一步=q+h v下一步。

状态为[qk,qk−1,Sqk−2,…,Sqk−n−1]，维数2r+2n。速度历史由相邻位移差/h定义；它是通道历史实现，不声称控制理论最小实现。输入u0…uN−1产生N+1个输出样本。地震用冻结的40961点时间轴，推进前40960个输入样本。初始与负时间历史为零；定频撤载仅把输入置零，历史完整延续。

## 两层精度参照
1. 缩聚误差：同划分、同τ、同增益、同CR、同输入输出的Full15。
2. 最终总偏差：原无时滞、无附加控制完整框架。CR基准与原RK4输入插值基准分别保存，使积分差异可分开。

不同划分的CP/KP与端口不同，有时滞Full15不是跨划分共用的一条响应。零时滞且零增益时两者均还原同一被动完整结构。



===== CASE_PROTOCOL.md | SHA256 4695924174d210fc9041fc93a3c0442afaa4a095a864630416ca2328ca21a5ad =====
# 预先计算与验收协议

写于新案例的边界扫描和时程计算之前，2026-09-16。所有调整保留原因和原规则，不按Guyan/CB曲线差值选择工况。

## 固定设置
原15自由度框架、原Rayleigh阻尼、两种划分、两个通道等常时滞。主比较零附加控制，物理反馈保留。主要缩聚为Guyan及CB保留3内部模态；保留数研究覆盖0至全部。基准步长1/1024s；既定40s地震输入不改变。输出为三个楼层位移及层间角，物理恢复主报告、数值输出保存。

## 计算顺序和选点
1. 被动结构模态、全模态收敛和静力内部受载检查。
2. 每个划分先扫描Full15的等整数延迟n=0…64，查首次单位圆越界；若无越界扩展至128/256，记录实际覆盖范围。再用相同网格比较缩聚模型。判据是全部增广极点的最大模，不能仅跟踪某一模态。若越界根在机器精度边界带，进一步高精度或邻点复核。
3. 正常延迟取Full15首次不稳定步数的约50%，近边界取最后稳定点。稳态频响与定频比较需要三模型共同稳定；若参考选点出现判断不一致，单列稳定性误判，再取不超过该点的最大共同稳定整数延迟作为响应点。零、正常和近边界均保留。
4. 频段以原0.1–10Hz及Full15相关共振为依据；主定频在Full15物理三楼层频响范数的峰值中选前两低频峰。另比较与首次失稳极点对应的可激励/可观测峰；若不在原频带内，单列并说明原因。不得以缩聚误差最大点来挑主案例。
5. 定频持续至少8个Full15相关衰减时间常数，并至少20周期；共同稳定模型需要更长时间才稳态时延长至实际收敛。稳态最后两个等长窗幅值/相位变化阈值0.5%/0.5度。撤载记录至少6时间常数、20周期，连续保留历史。自由响应识别需报告拟合窗和残差，不用包络拟合替代极点判稳。
6. 敏感段慢扫频以参考峰附近模态带宽确定覆盖，持续时间由参考衰减确定；扫速减半作收敛检查，以局部同步解调幅值相对准稳态FRF变化说明是否充分，未收敛就继续减半或如实保留为瞬态扫描。原40s快扫频作为输入效果对照，不直接认作稳态FRF。
7. 固定增益补充采用冻结旧增益，明确其设计来源，所有模型同增益。先检查同增益Full15在零时滞的稳定性；不把该补充解释为两划分控制器均已重新优化。

## 验证标准
- 矩阵、荷载、输出及误差恒等：归一化残差≤1e−10；零量按对应物理算子/输出尺度归一，定义写入代码。
- 独立Guyan实现不调用CB0；全模态用可逆变换验证Full15状态、荷载和输出。全历史与通道历史映射及额外零根用代数恒等核验。
- 独立二阶力平衡递推及MATLAB与状态推进对照：相对差≤1e−9；短记录有限卷积与非零初始历史也核验。
- 全部增广根数值残差≤1e−9；临界时滞报稳定/不稳定相邻整数格区间，不假设区间内无再入现象。h、h/2、h/4保持实际τ比较；继续细化只由未收敛或未解决差异触发。
- 正弦稳态幅值相对理论误差≤0.5%，相位≤0.5度；自由响应识别频率/衰减须给出模型拟合残差，阈值分别0.5%/2%，未达标先检查多模态干扰、窗口与记录长度。
- 地震误差给出全记录峰峰值NRMSE、相对L2、峰值偏差和最大绝对误差。响应差分量可相加，百分比不直接相加。
- 图像保留真实响应并单列误差，不修改数据以强化差异。用相同坐标范围、CB蓝/Guyan红/Full绿，CM9pt，矢量PDF与600dpiPNG；实际查看渲染。
- 原稿和旧案例哈希必须保持；全部测试在research/temp。新实质性理论本地验证、编译后送既有Pro对话，收到意见落实后开展依赖案例。

## 结果解释规则
CB的频率Ritz收敛可获得理论保证；点响应、总偏差和稳定边界精度需实际检验。报告CB优于Guyan的量化范围，也报告不优的频段/指标。增大稳定域不等于更准确。虚拟补充协调是明确的建模假定，不能隐去其与旧两接口系统的区别。



===== theory/full15_error_theory.tex | SHA256 339e59265c0f542e1bbaf16dbfa9604bd9190f8d5530993b356bd1804c8519d7 =====
\documentclass[UTF8,11pt,a4paper]{ctexart}
\usepackage[margin=23mm]{geometry}
\usepackage{amsmath,amssymb,bm,booktabs,tabularx,enumitem,hyperref,fancyhdr}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\newcommand{\bM}[1]{\bm{#1}}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{完整框架等时滞缩聚：误差与离散闭环}
\fancyfoot[C]{\thepage}\setlength{\headheight}{15pt}
\title{完整框架等时滞缩聚的误差理论\\\large 正式案例所用模型、推导与可检验命题}
\author{Doctor Bego研究材料；Codex整理与本地核验}
\date{2026年9月16日}
\begin{document}\maketitle

\section{研究对象及适用范围}
研究将原15自由度线性框架作为最终精度基准。两通道采用同一常时滞，结构阻尼为$C=\alpha M+\beta K$。先在完整物理坐标定义反馈，再用固定基底做合同投影。Guyan保留静力约束运动；CB在其后增加固定界面内部模态，这一基底结构继承经典约束模态与固定界面模态方法\cite{craig1968}。

本文采用完整框架直接缩聚。未作动的物理内部坐标及未作动界面采用当前数值运动补充协调；两个作动坐标采用延迟运动。该假定构成明确的虚拟反馈模型。旧两坐标子结构拼接留下18/19自由度，其全部局部模态极限不同，不能作为本模型的全阶极限。

主案例附加控制增益为零，保留物理子结构弹性和阻尼反馈。固定增益作为补充。矩阵$M,K$对称正定，保留基底满列秩；输出只取位移及其线性组合。本文件的精确误差恒等式与局部灵敏度近似分别标明，不将近似当作全局保证。

\section{完整反馈模型和一致投影}
物理反馈采用的运动为
\begin{equation}\label{eq:xp}
x_P(t)=(I-BS)x(t)+BSx(t-\tau),\qquad B=S^T.
\end{equation}
其中，$x\in\mathbb R^{15}$为完整数值坐标，$S\in\mathbb R^{2\times15}$抽取作动坐标，$\tau$为两通道共同延迟。$C_P,K_P$为嵌入原坐标的物理子结构贡献，$C_N=C-C_P$、$K_N=K-K_P$。惯性$M\ddot x$全部在数值侧推进。附加反馈为$B[G_dSx(t-\tau)+G_vS\dot x(t-\tau)]$，放在平衡方程左侧。整理得到
\begin{align}
 M\ddot x+C_0\dot x+K_0x+U_cS\dot x(t-\tau)+U_kSx(t-\tau)&=f a_g(t),\label{eq:eom}\\
 C_0=C-C_PBS,\quad K_0=K-K_PBS,&\quad
 U_c=C_PB+BG_v,\quad U_k=K_PB+BG_d.\label{eq:coeff}
\end{align}
其中$f=M\gamma$；$\gamma$按原地震记录约定在三个楼层水平坐标为1，记录符号不改动。零增益、零时滞时恢复$M\ddot x+C\dot x+Kx=f a_g$。

令$x\simeq Tq$，左乘$T^T$得到缩聚模型。应同时投影
\begin{equation}\label{eq:projection}
 A_r=T^TAT\ (A=M,C,K,C_0,K_0),\quad U_{c,r}=T^TU_c,\quad
 U_{k,r}=T^TU_k,\quad S_r=ST,\quad f_r=T^Tf.
\end{equation}
先缩聚$K_P$再按缩聚坐标挑列一般不等于$T^TK_PB$；投影和延迟选列不可任意交换。

数值楼层输出和物理恢复输出分别为
\begin{equation}\label{eq:output}
 y_N=Lx,\qquad y_P=L(I-BS)x+LB Sx(t-\tau).
\end{equation}
其中$L$选取三个楼层水平位移。缩聚后仅将$x$替换为$Tq$。层间角是相邻楼层位移差除以层高，与输出误差保持相同线性关系。

\section{Guyan、CB和划分的作用}
按保留/内部坐标排列，约束基底和CB基底为
\begin{equation}\label{eq:basis}
 T_G=\begin{bmatrix}I\\-K_{cc}^{-1}K_{cr}\end{bmatrix},\qquad
 T_m=\begin{bmatrix}I&0\\-K_{cc}^{-1}K_{cr}&\Phi_m\end{bmatrix},\qquad
 K_{cc}\Phi=M_{cc}\Phi\Omega^2,\quad\Phi^TM_{cc}\Phi=I.
\end{equation}
其中$c$表示内部坐标，$r$表示保留坐标，$m$为保留内部模态数。$m=0$与标准Guyan相同；$m$取全部内部模态时$T_m$方阵可逆，恢复同一个完整反馈模型。

在被动结构的嵌套Ritz空间内，按从小到大排序的频率满足
\begin{equation}\label{eq:ritz}
 \omega_{F,j}^2\leq\omega_{m+1,j}^2\leq\omega_{m,j}^2\leq\omega_{G,j}^2,
\end{equation}
只比较各空间均存在的阶次。该结论来自对称正定广义特征值的极小极大原理。对欠阻尼Rayleigh模态，连续自由衰减率$d_j=(\alpha+\beta\omega_j^2)/2$；因此$d_{r,j}-d_{F,j}=\beta(\omega_{r,j}^2-\omega_{F,j}^2)/2$。过阻尼时不能把这一共同实部直接当作两实根各自的衰减率。阻尼比$\zeta_j=\alpha/(2\omega_j)+\beta\omega_j/2$不必单调。上述性质不保证点输出、延迟稳定边界或地震NRMSE逐项改善。

静力内部平衡给出
\begin{equation}\label{eq:staticload}
 x_c=-K_{cc}^{-1}K_{cr}x_r+K_{cc}^{-1}f_c a_g.
\end{equation}
标准Guyan虽采用正确等效荷载$T_G^Tf$，其纯基底输出恢复仍缺少第二项。恰当的误差分析必须包含内部受载与输出恢复。是否$ f_c=0$取决于保留集合；不能把这个条件默认用于两种划分。

\section{连续频域的精确误差和遗漏模态}
连续特征算子与物理输出算子为
\begin{equation}\label{eq:continuous}
 Z(s,\tau)=s^2M+sC_0+K_0+e^{-s\tau}(sU_c+U_k)S,\qquad
 Y(s,\tau)=L(I-BS)+e^{-s\tau}LBS.
\end{equation}
由于一致投影，$Z_r=T^TZT$。对单位输入，$q_r=Z_r^{-1}f_r$，残余力$\mathcal R=f-ZTq_r$，输出误差满足
\begin{equation}\label{eq:residual}
 e=y_r-y_F=-YZ^{-1}\mathcal R.
\end{equation}
该恒等式要求所用算子可逆；稳态频响的解释另外要求闭环渐近稳定。它把基底留下的残余力与完整闭环对该残余力的动态放大分开。范数上界$\|e\|\leq\|YZ^{-1}\|\|\mathcal R\|$依赖单位和坐标尺度，平移/转角混合时须先明确尺度，不能直接比较未经定标的条件数。

把全内部模态基底写为$W=[T,Q]$，分块后完整方程为
\begin{equation}\label{eq:blocks}
 \begin{bmatrix}Z_{rr}&Z_{ro}\\Z_{or}&Z_{oo}\end{bmatrix}
 \begin{bmatrix}q_F\\p_F\end{bmatrix}=
 \begin{bmatrix}f_r\\f_o\end{bmatrix}a_g,
 \qquad f_o=Q^Tf.
\end{equation}
若$Z_{oo}$可逆，消元得到
\begin{align}
 (Z_{rr}-Z_{ro}Z_{oo}^{-1}Z_{or})q_F
   &=(f_r-Z_{ro}Z_{oo}^{-1}f_o)a_g,\label{eq:schur}\\
 p_F&=Z_{oo}^{-1}(f_oa_g-Z_{or}q_F),\label{eq:omitted}\\
 e&=(Y_rZ_{rr}^{-1}Z_{ro}-Y_o)p_F,\quad Y_r=YT,\ Y_o=YQ.\label{eq:omittederror}
\end{align}
式\eqref{eq:omittederror}同时包含保留坐标的动力修正与遗漏模态对输出的直接贡献。只看Schur刚度修正会漏掉后一部分。

对固定界面遗漏模态，$SQ=0$且$Q^TMQ=I$。约束模态与固定界面模态在刚度下正交，保留/遗漏内部模态也在质量与刚度下正交。因此
\begin{align}
 Z_{oo}&=s^2I+s(\alpha I+\beta\Omega_o^2)+\Omega_o^2,\label{eq:zoo}\\
 Z_{ro}&=(s^2+\alpha s)T^TMQ,\label{eq:zro}\\
 Z_{or}&=(s^2+\alpha s)Q^TMT
 +(e^{-s\tau}-1)Q^T(sC_P+K_P)BS T.\label{eq:zor}
\end{align}
附加作动力位于保留端口，$Q^TB=0$，所以不进入最后一式的遗漏行。时滞不直接进入$Z_{oo}$，但改变耦合和完整闭环的放大作用。$Z_{oo}$的孤立奇异点不自动等于完整系统极点。零频时$Z_{ro}=0$，有$e(0)=-Y_o\Omega_o^{-2}f_o a_g$，这是内部受载的静力输出偏差。

\section{既定CR递推与历史状态}
算法采用相邻位移差定义速度，令
\begin{align}
 \widehat M&=M+\tfrac h2 C+\tfrac{h^2}{4}K,\label{eq:mhat}\\
 r_k&=f a_{g,k}-C_0v_k-K_0q_k-U_cSv_{k-n}-U_kSq_{k-n},\label{eq:resforce}\\
 \widetilde a_k&=\widehat M^{-1}r_k,\qquad
 v_{k+1}=v_k+h\widetilde a_k,\qquad q_{k+1}=q_k+h v_{k+1}.\label{eq:cr}
\end{align}
其中$h$为步长、$\tau=nh$且$n$为非负整数。平衡加速度为$a_k=M^{-1}r_k$，算法加速度为$\widetilde a_k=\widehat M^{-1}Ma_k$。式\eqref{eq:mhat}仅使用结构阻尼和刚度，不能把额外控制刚度再次并入其中。

取$q_k=z^kq$得到离散特征矩阵
\begin{equation}\label{eq:discrete}
 Z_h(z,n)=\frac{z-2+z^{-1}}{h^2}\widehat M
 +\frac{1-z^{-1}}h C_0+K_0
 +z^{-n}\left(\frac{1-z^{-1}}h U_c+U_k\right)S.
\end{equation}
这一定义适用于$z\ne0$。令$Y_h=L(I-BS)+z^{-n}LBS$，则$H_h=Y_h Z_h^{-1}f$。缩聚后保持$Z_{h,r}=T^TZ_hT$，式\eqref{eq:residual}、\eqref{eq:schur}、\eqref{eq:omittederror}可逐项替换为离散算子。

采用通道历史状态
\begin{equation}\label{eq:state}
 \eta_k=[q_k^T,q_{k-1}^T,(Sq_{k-2})^T,\ldots,(Sq_{k-n-1})^T]^T,
 \quad\eta_{k+1}=A_n\eta_k+b_n a_{g,k},\quad y_k=O_n\eta_k.
\end{equation}
其维数为$2r+2n$；$n=0$仅有前两个块。这是节省存储的通道历史实现，不声称控制理论最小实现。对方阵全模态变换$W$，$P=\operatorname{diag}(W,W,I_{2n})$满足
\begin{equation}\label{eq:similarity}
 A_FP=PA_r,\qquad b_F=Pb_r,\qquad O_FP=O_r.
\end{equation}
因此不只是固有频率，输入、输出及完整历史传播也一致。

另用每个时刻全坐标历史构造$A_H$，维数$r(n+2)$。映射$J=\operatorname{diag}(I_{2r},S,\ldots,S)$满足$A_nJ=JA_H$。当$\operatorname{rank}S=2$时，$J$满行秩，冗余历史经有限次移位消失。行列式关系为
\begin{align}
 \det(zI-A_n)&=\frac{h^{2r}}{\det\widehat M}
 z^{r+2n}\det Z_h(z,n),\quad z\ne0,\label{eq:det}\\
 \det(zI-A_H)&=z^{(r-2)n}\det(zI-A_n).\label{eq:zeroroot}
\end{align}
不能仅因某个极点接近零就将它删掉；式\eqref{eq:zeroroot}只解释两种历史表示间的额外零根。渐近稳定的判据是$\rho(A_n)<1$，单位圆上的重根/Jordan块需另判。

零时滞、零附加控制时，CR与连续被动算子满足
\begin{equation}\label{eq:bilinear}
 Z_h(z,0)=\frac{(z+1)^2}{4z}
 [s_b^2M+s_bC+K],\qquad s_b=\frac2h\frac{z-1}{z+1}.
\end{equation}
所以离散被动根$z=(1+hs/2)/(1-hs/2)$，并非精确的$e^{sh}$。有时滞或额外控制时不能直接套用这个退化关系。一般离散极点的有效衰减率、频率为$-\log|z|/h$及$\arg(z)/(2\pi h)$。

\section{解析形式、稳定灵敏度与可验证量}
对任意给定离散地震或扫频序列，零初始历史下输出差的有限解析形式为
\begin{equation}\label{eq:convolution}
 e_k=\sum_{j=0}^{k-1}
 (O_r A_r^{k-1-j}b_r-O_F A_F^{k-1-j}b_F)a_{g,j}.
\end{equation}
非零历史时另加$O_rA_r^k\eta_{r,0}-O_FA_F^k\eta_{F,0}$。这对给定积分算法是精确有限矩阵和；无需把任意地震记录拟成一个初等函数。它在有限时刻也适用于失稳系统，失稳时不能据此宣称存在稳态频响。对正弦输入，稳定系统可用$H_h(e^{i\omega h})$给出稳态幅值和相位；扫频是随时间变化的输入，只有通过扫速检查才能作准稳态解释。

连续时滞系统一般有无穷多特征根。对简单根及非零分母，局部灵敏度为
\begin{align}
 \frac{ds}{d\tau}&=-\frac{w^*Z_\tau v}{w^*Z_sv},\label{eq:delayderivative}\\
 Z_\tau&=-s e^{-s\tau}(sU_c+U_k)S,\\
 Z_s&=2sM+C_0+e^{-s\tau}[U_c-\tau(sU_c+U_k)]S.
\end{align}
其中$v,w$为右、左零向量。沿$Z_{rr}-\varepsilon\Sigma$，$\Sigma=Z_{ro}Z_{oo}^{-1}Z_{or}$，有
\begin{equation}\label{eq:truncderivative}
 \left.\frac{ds}{d\varepsilon}\right|_0=
 \frac{w^*\Sigma v}{w^*(\partial Z_{rr}/\partial s)v}.
\end{equation}
它描述简单根附近的首阶偏移，不能保证截断误差很大时仍准确。正式边界计算直接使用式\eqref{eq:state}全部离散根；整数$n$不能直接求导当作连续时滞参数。此处连续灵敏度用于解释，未作为未定义的分数延迟实现。

同一离散步长下，两层误差参照满足
\begin{equation}\label{eq:decompose}
 y_r^{\tau,G}-y_F^{0,0}
 =(y_r^{\tau,G}-y_F^{\tau,G})
 +(y_F^{\tau,G}-y_F^{0,G})
 +(y_F^{0,G}-y_F^{0,0}).
\end{equation}
若最终参照使用原RK4结果，再加$y_{F,CR}^{0,0}-y_{F,RK4}^{0,0}$。各项是同单位响应差；NRMSE百分比不能直接相加。

\section{案例映射和本地核验状态}
划分一保留原坐标1、6、11、4、9、14，作动1、6；划分二保留1、11、4、9、14，作动1、11。对应Guyan6/5阶、CB保留3内部模态9/8阶，全内部模态均15阶。划分二内部包含受载的中间层水平坐标6；这使$f_c\ne0$，需与内部模态参与、端口参与及目标输出共同解释，不能单凭保留数就宣称划分二所有误差都更大。

已实际完成Python核心1283项检查，最大残差$6.371\times10^{-12}$，包含独立块矩阵Guyan、全部保留数Ritz关系、全空间状态/输入/输出、历史行列式、静力内部受载、Schur输出误差、64步非零历史直接递推与有限卷积。另有224项遗漏耦合、离散Schur/残余力误差和连续算子导数检查，最大残差$2.374\times10^{-12}$。MATLAB独立力平衡及全历史系数完成96项检查，最大残差$8.328\times10^{-14}$。矩阵恒等阈值$10^{-10}$，有限记录独立推进阈值$10^{-9}$，共1603项通过。64步记录是实现验证，不是正式案例结果。

首轮测试中零频$T^TKQ=0$的检查错误地按1个SI数值单位归一，约$3.1\times10^{-10}$的绝对舍入残差未通过；现按预先约定的乘积算子尺度$\|T\|\|K\|\|Q\|$报告零目标后向残差。$10^{-10}$阈值、模型和输入未改变，失败原记录保留于temp。

后续工况先依据Full15极点和频响确定，再比较缩聚误差；理论预测用独立计算验证。地震记录保持，定频撤载保留历史，慢扫频检查扫速，临界时滞报告实际离散网格区间。单独配置误差图，让真实但较小的精度收益可读，不以视觉分离程度反选模型或激励。

\begin{thebibliography}{9}
\bibitem{craig1968} R. R. Craig Jr. and M. C. C. Bampton.
Coupling of Substructures for Dynamic Analyses. AIAA Journal, 6(7), 1313--1319, 1968.
\href{https://doi.org/10.2514/3.4741}{doi:10.2514/3.4741}.
\end{thebibliography}
\end{document}



===== code/full15_model.py | SHA256 d0ca588bac0066be5743b2381ae6abed3b5794864886736984a870e58d0cc0aa =====
"""Full-frame virtual RTHS with two equal-delay signals and consistent projection.

SI units; base record sign retained from the frozen source. The mass is advanced
numerically. Undriven physical coordinates are supplied by the current numerical
state. This is an explicit virtual-feedback model, not a two-actuator hardware
realizability claim. No calculation is run by importing this module.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.io import loadmat
from numba import njit

ROOT=Path(__file__).resolve().parents[1]
H=1/1024
FLOORS=np.array([0,5,10])
STORY_HEIGHT=0.635
RETAINED={1:np.array([0,5,10,3,8,13]),2:np.array([0,10,3,8,13])}
PORTS={1:np.array([0,5]),2:np.array([0,10])}

@dataclass(frozen=True)
class Model:
    M:np.ndarray
    C:np.ndarray
    K:np.ndarray
    C0:np.ndarray
    K0:np.ndarray
    Uc:np.ndarray
    Uk:np.ndarray
    S:np.ndarray
    f:np.ndarray
    Yn:np.ndarray
    Y0:np.ndarray
    Jd:np.ndarray
    T:np.ndarray
    division:int
    label:str
    @property
    def order(self):return self.M.shape[0]

@lru_cache(maxsize=1)
def load_sources():
    bundle=loadmat(ROOT/'data/calculation.mat',simplify_cells=True)['bundle']
    local=loadmat(ROOT/'data/audit_matrices.mat',simplify_cells=True)
    saved=loadmat(ROOT/'data/model_and_cases.mat',simplify_cells=True)
    return bundle['frame'],bundle['inputs'],local,np.asarray(saved['Full15']['gain'],float)

def timing(n,h):
    if isinstance(n,(bool,np.bool_)) or not isinstance(n,(int,np.integer)) or n<0:
        raise ValueError('Delay must be a nonnegative integer number of steps')
    if not np.isfinite(h) or h<=0:raise ValueError('Step size must be finite and positive')

def full_model(division,gain=None):
    if division not in RETAINED:raise ValueError('Division must be 1 or 2')
    frame,_,audit,_=load_sources()
    gain=np.zeros((2,4)) if gain is None else np.asarray(gain,float)
    if gain.shape!=(2,4) or not np.isfinite(gain).all():raise ValueError('Gain must be finite 2 by 4')
    p=np.array([0,1,2,5,6,7] if division==1 else [0,1,2,5,6,7,10,11,12])
    embed=np.eye(15)[p]
    Cp=embed.T@audit[f'div{division}_C_P']@embed
    Kp=embed.T@audit[f'div{division}_K_P']@embed
    M,C,K=[np.asarray(frame[k],float) for k in ['M','C','K']]
    S=np.eye(15)[PORTS[division]];B=S.T;D=B@S;L=np.eye(15)[FLOORS]
    F=Model(M,C,K,C-Cp@D,K-Kp@D,Cp@B+B@gain[:,2:],
            Kp@B+B@gain[:,:2],S,M@L.sum(axis=0),L,L@(np.eye(15)-D),L@B,
            np.eye(15),division,'Full15')
    validate_model(F)
    return F

def validate_model(F):
    r=F.order
    for k in ['M','C','K','C0','K0']:
        a=getattr(F,k)
        if a.shape!=(r,r) or not np.isfinite(a).all():raise ValueError(k+' shape or values')
    for k,shape in [('Uc',(r,2)),('Uk',(r,2)),('S',(2,r)),('f',(r,)),
                    ('Yn',(3,r)),('Y0',(3,r)),('Jd',(3,2)),('T',(15,r))]:
        a=getattr(F,k)
        if a.shape!=shape or not np.isfinite(a).all():raise ValueError(k+' shape or values')
    la.cholesky(F.M);la.cholesky(F.K)
    if np.linalg.matrix_rank(F.S)!=2:raise ValueError('Two independent ports required')

def guyan_basis(M,K,retained):
    """Static constraint map, using the explicit ordered retained coordinates."""
    r=np.asarray(retained,int);c=np.array([i for i in range(len(M)) if i not in r])
    if len(set(r))!=len(r) or len(r)==0 or min(r)<0 or max(r)>=len(M):
        raise ValueError('Invalid retained coordinate set')
    T=np.zeros((len(M),len(r)));T[r]=np.eye(len(r))
    T[c]=-la.solve(K[np.ix_(c,c)],K[np.ix_(c,r)],assume_a='pos')
    return T

def cb_basis(F,modes):
    if F.order!=15:raise ValueError('CB basis is defined in the original full frame')
    r=RETAINED[F.division];c=np.array([i for i in range(15) if i not in r])
    if isinstance(modes,(bool,np.bool_)) or not isinstance(modes,(int,np.integer)) or not 0<=modes<=len(c):
        raise ValueError('Invalid internal mode count')
    lam,phi=la.eigh(F.K[np.ix_(c,c)],F.M[np.ix_(c,c)])
    for j in range(phi.shape[1]):
        if phi[np.argmax(abs(phi[:,j])),j]<0:phi[:,j]*=-1
    T=np.zeros((15,len(r)+modes));T[:,:len(r)]=guyan_basis(F.M,F.K,r)
    T[np.ix_(c,np.arange(len(r),len(r)+modes))]=phi[:,:modes]
    return T,lam

def project(F,T,label):
    T=np.asarray(T,float)
    if T.ndim!=2 or T.shape[0]!=F.order or not np.isfinite(T).all() or np.linalg.matrix_rank(T)!=T.shape[1]:
        raise ValueError('Projection basis must be finite, compatible and full rank')
    mats={k:T.T@getattr(F,k)@T for k in ['M','C','K','C0','K0']}
    R=Model(**mats,Uc=T.T@F.Uc,Uk=T.T@F.Uk,S=F.S@T,f=T.T@F.f,
            Yn=F.Yn@T,Y0=F.Y0@T,Jd=F.Jd.copy(),T=F.T@T,division=F.division,label=label)
    validate_model(R)
    return R

def family(division,modes=(0,3),gain=None):
    F=full_model(division,gain);models={'Full15':F}
    for m in modes:
        T,_=cb_basis(F,m);label='Guyan' if m==0 else f'CB{m}'
        models[label]=project(F,T,label)
    return models

def algorithm_mass(F,h=H):
    timing(0,h)
    return F.M+h/2*F.C+h*h/4*F.K

def continuous(F,s,tau):
    if not np.isfinite(tau) or tau<0:raise ValueError('Delay must be finite and nonnegative')
    return s*s*F.M+s*F.C0+F.K0+np.exp(-s*tau)*(s*F.Uc+F.Uk)@F.S

def characteristic(F,z,n,h=H):
    timing(n,h)
    if z==0:raise ValueError('Use the augmented state matrix at z=0')
    dv=(1-1/z)/h;da=(z-2+1/z)/h**2
    return da*algorithm_mass(F,h)+dv*F.C0+F.K0+z**(-n)*(dv*F.Uc+F.Uk)@F.S

def state_space(F,n,h=H):
    """Port-history realization: [q_k, q_(k-1), S q_(k-2),...,S q_(k-n-1)]."""
    timing(n,h);r=F.order;size=2*r+2*n;Mh=algorithm_mass(F,h)
    A=np.zeros((size,size));A[:r,:r]=2*np.eye(r)-la.solve(Mh,h*F.C0+h*h*F.K0)
    A[:r,r:2*r]=-np.eye(r)+la.solve(Mh,h*F.C0);A[r:2*r,:r]=np.eye(r)
    if n:
        A[2*r:2*r+2,r:2*r]=F.S
        if n>1:A[2*r+2:,2*r:-2]=np.eye(2*(n-1))
    def add(U,lag):
        if lag<2:A[:r,lag*r:(lag+1)*r]+=U@F.S
        else:A[:r,2*r+2*(lag-2):2*r+2*(lag-1)]+=U
    add(-la.solve(Mh,h*F.Uc+h*h*F.Uk),n)
    add(la.solve(Mh,h*F.Uc),n+1)
    b=np.zeros(size);b[:r]=h*h*la.solve(Mh,F.f)
    return A,b

def state_output(F,n,kind='physical'):
    timing(n,H);r=F.order;O=np.zeros((3,2*r+2*n))
    if kind=='numerical':O[:,:r]=F.Yn
    elif kind=='physical':
        O[:,:r]=F.Y0
        if n<2:O[:,n*r:(n+1)*r]+=F.Jd@F.S
        else:O[:,2*r+2*(n-2):2*r+2*(n-1)]+=F.Jd
    else:raise ValueError('Output is physical or numerical')
    return O

def full_history(F,n,h=H):
    """Independent coordinate-history assembly, used as a cross-check."""
    timing(n,h);r=F.order;N=r*(n+2);A=np.zeros((N,N));Mh=algorithm_mass(F,h)
    coefficients=[np.zeros((r,r)) for _ in range(n+2)]
    coefficients[0]+=2*Mh-h*F.C0-h*h*F.K0
    coefficients[1]+=-Mh+h*F.C0
    coefficients[n]+=-h*F.Uc@F.S-h*h*F.Uk@F.S
    coefficients[n+1]+=h*F.Uc@F.S
    A[:r]=la.solve(Mh,np.concatenate(coefficients,axis=1))
    A[r:,:-r]=np.eye(N-r);b=np.zeros(N);b[:r]=h*h*la.solve(Mh,F.f)
    J=la.block_diag(np.eye(2*r),*([F.S]*n)) if n else np.eye(2*r)
    return A,b,J

def frequency_response(F,freq_hz,n,h=H,kind='physical'):
    if kind not in ('numerical','physical'):raise ValueError('Output is physical or numerical')
    z=np.exp(2j*np.pi*freq_hz*h);Z=characteristic(F,z,n,h)
    Y=F.Yn if kind=='numerical' else F.Y0+z**(-n)*F.Jd@F.S
    return Y@la.solve(Z,F.f)

@njit(cache=False)
def _advance(A,b,O,u,x0):
    size=A.shape[0];p=O.shape[0];steps=len(u);y=np.zeros((steps+1,p))
    x=x0.copy()
    for j in range(p):
        for k in range(size):y[0,j]+=O[j,k]*x[k]
    for t in range(steps):
        nx=np.zeros(size)
        for j in range(size):
            nx[j]=b[j]*u[t]
            for k in range(size):nx[j]+=A[j,k]*x[k]
        x=nx
        for j in range(p):
            for k in range(size):y[t+1,j]+=O[j,k]*x[k]
    return y,x

def simulate(F,n,u,h=H,x0=None):
    """Input has N samples u_0...u_(N-1); returns N+1 states' six outputs.

    Columns 0:3 are numerical floor commands, 3:6 are physical recovered floors.
    Historical state is retained during zero input, including after unloading.
    """
    A,b=state_space(F,n,h);O=np.vstack([state_output(F,n,'numerical'),state_output(F,n,'physical')])
    u=np.asarray(u,float)
    if u.ndim!=1 or not np.isfinite(u).all():raise ValueError('Input must be a finite vector')
    x0=np.zeros(len(A)) if x0 is None else np.asarray(x0,float)
    if x0.shape!=(len(A),) or not np.isfinite(x0).all():raise ValueError('Invalid initial history state')
    return _advance(np.ascontiguousarray(A),np.ascontiguousarray(b),np.ascontiguousarray(O),u,x0)

def independent_recurrence(F,n,u,h=H,history=None):
    """Explicit second-order force balance; intentionally does not use A or b."""
    timing(n,h);r=F.order;u=np.asarray(u,float)
    old=np.zeros((n+2,r)) if history is None else np.asarray(history,float).copy()
    if old.shape!=(n+2,r):raise ValueError('History rows are q_0,q_-1,...,q_-n-1')
    out=np.empty((len(u)+1,6));Mh=algorithm_mass(F,h)
    def output():return np.r_[F.Yn@old[0],F.Y0@old[0]+F.Jd@F.S@old[n]]
    out[0]=output()
    for k,forcing in enumerate(u):
        v=(old[0]-old[1])/h;vd=(old[n]-old[n+1])/h
        req=F.f*forcing-F.C0@v-F.K0@old[0]-F.Uc@F.S@vd-F.Uk@F.S@old[n]
        algorithm_acceleration=la.solve(Mh,req,assume_a='pos')
        qnew=old[0]+h*v+h*h*algorithm_acceleration
        old[1:]=old[:-1].copy();old[0]=qnew;out[k+1]=output()
    return out

def residual_error(F,R,z,n,h=H,kind='physical'):
    Zf=characteristic(F,z,n,h);Zr=characteristic(R,z,n,h)
    q=la.solve(Zr,R.f);residual=F.f-Zf@R.T@q
    Y=F.Yn if kind=='numerical' else F.Y0+z**(-n)*F.Jd@F.S
    return -Y@la.solve(Zf,residual),residual

def drift(floor_displacements):
    return np.asarray(floor_displacements)@np.array([[1,-1,0],[0,1,-1],[0,0,1]])/STORY_HEIGHT

def error_metrics(pred,ref):
    pred=np.asarray(pred);ref=np.asarray(ref);err=pred-ref
    rms=np.sqrt(np.mean(err*err,axis=0));span=np.ptp(ref,axis=0)
    energy=np.sqrt(np.mean(ref*ref,axis=0));peak=np.max(abs(ref),axis=0)
    return dict(nrmse_range_pct=(100*rms/span).tolist(),relative_l2_pct=(100*rms/energy).tolist(),
                peak_bias_pct=(100*(np.max(abs(pred),axis=0)-peak)/peak).tolist(),
                max_abs_error=np.max(abs(err),axis=0).tolist())



===== code/verify_model.py | SHA256 7c6bd6f06f90dc560ec6503fc23e2db45877e31a897c181b3ae0572943d68199 =====
"""Independent algebra and finite-record verification; artifacts go to --out."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy import linalg as la
from scipy.io import savemat
from full15_model import *

def main(out):
    out.mkdir(parents=True,exist_ok=True);checks=[];exports={};rng=np.random.default_rng(260916)
    def check(name,a,b,scale=None,tol=1e-10):
        a=np.asarray(a);b=np.asarray(b)
        den=max(float(la.norm(b.ravel())),1e-300) if scale is None else max(float(scale),1e-300)
        value=float(la.norm((a-b).ravel())/den)
        checks.append(dict(name=name,residual=value,tolerance=tol,passed=bool(value<=tol)))
    def predicate(name,ok):checks.append(dict(name=name,residual=0 if ok else 1,tolerance=0,passed=bool(ok)))
    frame,inputs,_,gain=load_sources();alpha,beta=np.asarray(frame['rayleigh']).ravel()
    for d in [1,2]:
        F=full_model(d);ridx=RETAINED[d];cidx=np.array([i for i in range(15) if i not in ridx]);nr=len(ridx)
        # Independently solve a permuted block problem and expand its mass, load,
        # and stiffness formulas. This path never calls cb_basis or guyan_basis.
        p=np.r_[ridx,cidx];M=F.M[np.ix_(p,p)];K=F.K[np.ix_(p,p)]
        Krr,Krc,Kcr,Kcc=K[:nr,:nr],K[:nr,nr:],K[nr:,:nr],K[nr:,nr:]
        L=-np.linalg.solve(Kcc,Kcr);Vind=np.vstack([np.eye(nr),L]);Tind=np.zeros((15,nr));Tind[p]=Vind
        Mg=M[:nr,:nr]+M[:nr,nr:]@L+L.T@M[nr:,:nr]+L.T@M[nr:,nr:]@L
        Kg=Krr+Krc@L;fg=F.f[ridx]+L.T@F.f[cidx]
        G=family(d)['Guyan'];check(f'd{d}_independent_G_basis',G.T,Tind)
        for key,ref in [('M',Mg),('K',Kg),('C',alpha*Mg+beta*Kg),('f',fg)]:check(f'd{d}_independent_G_{key}',getattr(G,key),ref)
        W,_=cb_basis(F,len(cidx));allR=project(F,W,'CBall');lamF=la.eigvalsh(F.K,F.M);last=None
        for m in range(len(cidx)+1):
            T,lam=cb_basis(F,m);R=project(F,T,f'CB{m}');vals=la.eigvalsh(R.K,R.M)
            predicate(f'd{d}_m{m}_Ritz_above_full',bool(np.all(vals>=lamF[:len(vals)]-1e-9*np.max(lamF))))
            if last is not None:predicate(f'd{d}_m{m}_nested_Ritz',bool(np.all(vals[:len(last)]<=last+1e-9*np.max(lamF))))
            last=vals
            if m==len(cidx):check(f'd{d}_full_modal_spectrum',vals,lamF)
        xs=la.solve(F.K,F.f);qg=la.solve(G.K,G.f);estat=G.Yn@qg-F.Yn@xs
        expected=np.zeros(15);expected[cidx]=-la.solve(Kcc,F.f[cidx])
        check(f'd{d}_static_internal_load_output',estat,F.Yn@expected,scale=la.norm(F.Yn@xs))
        predicate(f'd{d}_internal_load_present',bool((la.norm(F.f[cidx])>0)==(d==2)))
        for control in [False,True]:
            F=full_model(d,gain if control else None);mods=family(d,gain=gain if control else None)
            allR=project(F,W,'CBall')
            for n in [0,1,4,5]:
                prefix=f'd{d}_g{int(control)}_n{n}'
                AF,bF=state_space(F,n);AR,bR=state_space(allR,n)
                P=la.block_diag(W,W,np.eye(2*n)) if n else la.block_diag(W,W)
                check(prefix+'_full_state_similarity',AF@P,P@AR)
                check(prefix+'_full_input_similarity',bF,P@bR)
                for kind in ['numerical','physical']:check(prefix+'_full_output_'+kind,state_output(F,n,kind)@P,state_output(allR,n,kind))
                for name,R in mods.items():
                    tag=prefix+'_'+name;A,b=state_space(R,n);Ah,bh,J=full_history(R,n)
                    check(tag+'_history_intertwining',A@J,J@Ah)
                    check(tag+'_history_input',b,J@bh)
                    predicate(tag+'_history_map_full_row_rank',np.linalg.matrix_rank(J)==len(A))
                    history=rng.normal(size=(n+2,R.order))*1e-5
                    initial=J@history.ravel();u=rng.normal(size=64)
                    y,end=simulate(R,n,u,x0=initial)
                    independent=independent_recurrence(R,n,u,history=history)
                    check(tag+'_independent_force_recurrence',y,independent,tol=1e-9)
                    O=np.vstack([state_output(R,n,'numerical'),state_output(R,n,'physical')])
                    Oh=np.zeros((6,len(Ah)));Oh[:3,:R.order]=R.Yn;Oh[3:,:R.order]=R.Y0
                    Oh[3:,n*R.order:(n+1)*R.order]+=R.Jd@R.S
                    check(tag+'_history_output',O@J,Oh)
                    # Explicit matrix powers and finite convolution; includes
                    # nonzero history and the last finite sample.
                    yp=np.array([O@np.linalg.matrix_power(A,k)@initial+sum((O@np.linalg.matrix_power(A,k-1-j)@b*u[j] for j in range(k)),np.zeros(6)) for k in range(65)])
                    check(tag+'_finite_convolution_with_history',y,yp,tol=1e-9)
                    y1,x1=simulate(R,n,u[:32],x0=initial);y2,_=simulate(R,n,u[32:],x0=x1)
                    check(tag+'_unbroken_history',np.vstack([y1,y2[1:]]),y)
                    for z in [0.9+0.25j,np.exp(2j*np.pi*3*H),np.exp(2j*np.pi*9*H)]:
                        Z=characteristic(R,z,n);Zf=characteristic(F,z,n)
                        check(tag+f'_project_Z_{z}',Z,R.T.T@Zf@R.T)
                        # Transfer of a sampled exponential from state equation.
                        qs=la.solve(z*np.eye(len(A))-A,b)
                        for kind in ['physical','numerical']:
                            Y=R.Yn if kind=='numerical' else R.Y0+z**(-n)*R.Jd@R.S
                            check(tag+f'_state_transfer_{kind}_{z}',state_output(R,n,kind)@qs,Y@la.solve(Z,R.f))
                        # Scale-free determinant identities using complex logs.
                        def logdet(X):
                            sg,logabs=np.linalg.slogdet(X);return logabs+1j*np.angle(sg)
                        delta=logdet(z*np.eye(len(A))-A)-(2*R.order*np.log(H)-logdet(algorithm_mass(R))+(R.order+2*n)*np.log(z)+logdet(Z))
                        check(tag+f'_determinant_{z}',np.exp(delta),1.)
                        delta2=logdet(z*np.eye(len(Ah))-Ah)-((R.order-2)*n*np.log(z)+logdet(z*np.eye(len(A))-A))
                        check(tag+f'_redundant_zero_roots_{z}',np.exp(delta2),1.)
                    if not control:
                        z=.9+.3j;s=2/H*(z-1)/(z+1)
                        if n==0:check(tag+'_passive_bilinear_identity',characteristic(R,z,0),(z+1)**2/(4*z)*continuous(R,s,0))
                    key=tag.replace('Full15','Full')
                    exports[key+'_A']=A;exports[key+'_b']=b;exports[key+'_O']=O
                    exports[key+'_M']=R.M;exports[key+'_C']=R.C;exports[key+'_K']=R.K
                    for k in ['C0','K0','Uc','Uk','S','f','Yn','Y0','Jd']:exports[key+'_'+k]=getattr(R,k)
                    exports[key+'_u']=u;exports[key+'_history']=history;exports[key+'_y']=y;exports[key+'_n']=n
            # Continuous omitted-block identities include dynamic load and output.
            for m in [0,3]:
                T,_=cb_basis(F,m);R=project(F,T,f'CB{m}');r=R.order;Q=W[:,r:]
                for s in [0,2+19j,-.5+37j]:
                    tau=4*H;Z=continuous(F,s,tau);Zr=continuous(R,s,tau)
                    Zro=T.T@Z@Q;Zor=Q.T@Z@T;Zoo=Q.T@Z@Q
                    omega2=np.diag(Q.T@F.K@Q);fo=Q.T@F.f;fr=T.T@F.f
                    check(f'd{d}_g{control}_m{m}_Zoo_{s}',Zoo,s*s*np.eye(len(fo))+s*(alpha*np.eye(len(fo))+beta*np.diag(omega2))+np.diag(omega2))
                    # At s=0 the exact target is zero. Normalize its cancellation
                    # by the multiplying physical operators, not by 1 SI unit.
                    zro_scale=la.norm(T)*la.norm(F.K)*la.norm(Q) if s==0 else la.norm(Zro)
                    check(f'd{d}_g{control}_m{m}_Zro_{s}',Zro,(s*s+alpha*s)*(T.T@F.M@Q),scale=zro_scale)
                    # Whole modal-coordinate solve is a separate path from Schur.
                    coordinates=la.solve(W.T@Z@W,W.T@F.f);pf=coordinates[r:]
                    Y=F.Y0+np.exp(-s*tau)*F.Jd@F.S;Yr=Y@T;Yo=Y@Q
                    qt=la.solve(Zr,fr);error=Yr@qt-Y@la.solve(Z,F.f)
                    check(f'd{d}_g{control}_m{m}_Schur_output_{s}',error,(Yr@la.solve(Zr,Zro)-Yo)@pf,scale=la.norm(Y@la.solve(Z,F.f)))
                    residual=F.f-Z@T@qt
                    check(f'd{d}_g{control}_m{m}_residual_output_{s}',error,-Y@la.solve(Z,residual),scale=la.norm(Y@la.solve(Z,F.f)))
        # Isolated passive discrete roots equal the Cayley image, not exp(sh).
        F=full_model(d);Ac=np.block([[np.zeros((15,15)),np.eye(15)],[-la.solve(F.M,F.K),-la.solve(F.M,F.C)]])
        expected=(1+H*la.eigvals(Ac)/2)/(1-H*la.eigvals(Ac)/2);actual=la.eigvals(state_space(F,0)[0])
        from scipy.optimize import linear_sum_assignment
        rows,cols=linear_sum_assignment(abs(actual[:,None]-expected[None,:]))
        check(f'd{d}_passive_root_bilinear',actual[rows],expected[cols])
    for bad in [-1,1.5,True]:
        try:state_space(full_model(1),bad);ok=False
        except ValueError:ok=True
        predicate(f'invalid_delay_{bad}',ok)
    savemat(out/'crosscheck_inputs.mat',exports,oned_as='column',do_compression=True)
    summary=dict(status='PASS' if all(x['passed'] for x in checks) else 'FAIL',count=len(checks),
        maximum_residual=max(x['residual'] for x in checks),checks=checks,
        scope='Algebra and 64-step verification, no selected research cases or stability scan',
        code_sha256=hashlib.sha256(Path(__file__).with_name('full15_model.py').read_bytes()).hexdigest())
    (out/'model_validation.json').write_text(json.dumps(summary,indent=2),'utf-8')
    failed=[x for x in checks if not x['passed']]
    print(json.dumps(dict(status=summary['status'],count=len(checks),maximum=summary['maximum_residual'],failures=failed[:20]),ensure_ascii=False))
    if failed:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);main(parser.parse_args().out)



===== code/verify_theory.py | SHA256 623af24d6deb2a8f0de20f7fb61859d10bfbbec1950d4eb6ab54181753964ae2 =====
"""Targeted checks for the additional omitted-block and derivative formulas."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy import linalg as la
from full15_model import *

def main(out):
    checks=[];frame,_,_,gain=load_sources();alpha,beta=frame['rayleigh']
    def check(name,a,b,scale):
        val=float(la.norm(a-b)/max(scale,1e-300));checks.append(dict(name=name,residual=val,tolerance=1e-10,passed=val<=1e-10))
    for d in [1,2]:
        for controlled in [False,True]:
            F=full_model(d,gain if controlled else None);W,_=cb_basis(F,15-len(RETAINED[d]))
            for m in [0,3]:
                T,_=cb_basis(F,m);R=project(F,T,f'CB{m}');r=R.order;Q=W[:,r:]
                for s in [0,2+19j,-.5+37j]:
                    tau=4*H;Z=continuous(F,s,tau);Zor=Q.T@Z@T
                    pred=(s*s+alpha*s)*Q.T@F.M@T+(np.exp(-s*tau)-1)*Q.T@(s*(F.C-F.C0)+(F.K-F.K0))@T
                    check(f'd{d}_g{controlled}_m{m}_Zor_{s}',Zor,pred,la.norm(Q)*la.norm(Z)*la.norm(T))
                for n in [0,1,4,5]:
                    for freq in [3.,9.,20.]:
                        z=np.exp(2j*np.pi*freq*H);Z=characteristic(F,z,n);Zr=characteristic(R,z,n)
                        qf=la.solve(W.T@Z@W,W.T@F.f);qr=la.solve(Zr,R.f)
                        Y=F.Y0+z**(-n)*F.Jd@F.S;ref=Y@la.solve(Z,F.f)
                        e=Y@T@qr-ref;Zro=T.T@Z@Q
                        check(f'd{d}_g{controlled}_m{m}_discrete_Schur_n{n}_f{freq}',e,(Y@T@la.solve(Zr,Zro)-Y@Q)@qf[r:],la.norm(ref))
                        er,_=residual_error(F,R,z,n)
                        check(f'd{d}_g{controlled}_m{m}_discrete_residual_n{n}_f{freq}',e,er,la.norm(ref))
            s=-.7+28j;tau=4*H;ds=1e-2;dt=1e-5
            Zs=2*s*F.M+F.C0+np.exp(-s*tau)*(F.Uc-tau*(s*F.Uc+F.Uk))@F.S
            Zt=-s*np.exp(-s*tau)*(s*F.Uc+F.Uk)@F.S
            # Fourth-order central differences reduce cancellation in the
            # large controlled stiffness while preserving the 1e-10 threshold.
            Ds=(-continuous(F,s+2*ds,tau)+8*continuous(F,s+ds,tau)-8*continuous(F,s-ds,tau)+continuous(F,s-2*ds,tau))/(12*ds)
            Dt=(-continuous(F,s,tau+2*dt)+8*continuous(F,s,tau+dt)-8*continuous(F,s,tau-dt)+continuous(F,s,tau-2*dt))/(12*dt)
            check(f'd{d}_g{controlled}_continuous_s_derivative',Zs,Ds,la.norm(Zs))
            check(f'd{d}_g{controlled}_continuous_tau_derivative',Zt,Dt,la.norm(Zt))
    result=dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL',count=len(checks),maximum_residual=max(c['residual'] for c in checks),checks=checks)
    out.mkdir(parents=True,exist_ok=True);(out/'theory_validation.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}));print('failures',[c for c in checks if not c['passed']])
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)



===== code/VERIFY_MODEL.m | SHA256 c8f9458b95b512d7c61ef4dc21c85884d1a816b4f60e987f739583384a75f728 =====
function VERIFY_MODEL(inputfile,outputfile)
% Independent force-balance implementation; no Python state matrix is reused.
data=load(inputfile);fields=fieldnames(data);checks=struct('name',{},'residual',{},'tolerance',{},'passed',{});
for j=1:numel(fields)
    field=fields{j};
    if ~endsWith(field,'_history'),continue;end
    tag=extractBefore(field,strlength(field)-7); % strip '_history'
    tag=char(tag);r=size(data.([tag '_M']),1);h=1/1024;n=double(data.([tag '_n']));
    M=data.([tag '_M']);C=data.([tag '_C']);K=data.([tag '_K']);
    C0=data.([tag '_C0']);K0=data.([tag '_K0']);Uc=data.([tag '_Uc']);Uk=data.([tag '_Uk']);
    S=data.([tag '_S']);f=data.([tag '_f']);Yn=data.([tag '_Yn']);Y0=data.([tag '_Y0']);Jd=data.([tag '_Jd']);
    Mh=M+h*C/2+h^2*K/4;old=data.(field);u=data.([tag '_u']);N=numel(u);y=zeros(N+1,6);
    for t=1:N+1
        y(t,:)=[Yn*old(1,:)';Y0*old(1,:)'+Jd*S*old(n+1,:)']';
        if t>N,break;end
        v=(old(1,:)-old(2,:))'/h;vd=(old(n+1,:)-old(n+2,:))'/h;
        req=f*u(t)-C0*v-K0*old(1,:)'-Uc*S*vd-Uk*S*old(n+1,:)';
        anew=Mh\req;qnew=old(1,:)'+h*v+h^2*anew;
        old=[qnew';old(1:end-1,:)];
    end
    expected=data.([tag '_y']);v=norm(y-expected,'fro')/norm(expected,'fro');
    checks(end+1)=struct('name',[tag '_independent_MATLAB_response'],'residual',v,'tolerance',1e-9,'passed',v<=1e-9);
    % Separate coefficient assembly and projection to the port-history space.
    Ah=zeros(r*(n+2));coeff=zeros(r,r,n+2);
    coeff(:,:,1)=2*Mh-h*C0-h^2*K0;coeff(:,:,2)=-Mh+h*C0;
    coeff(:,:,n+1)=coeff(:,:,n+1)-h*Uc*S-h^2*Uk*S;
    coeff(:,:,n+2)=coeff(:,:,n+2)+h*Uc*S;
    for k=1:n+2,Ah(1:r,(k-1)*r+1:k*r)=Mh\coeff(:,:,k);end
    Ah(r+1:end,1:end-r)=eye(r*(n+1));J=eye(2*r);
    for k=1:n,J=blkdiag(J,S);end
    target=J*Ah;value=norm(data.([tag '_A'])*J-target,'fro')/norm(target,'fro');
    checks(end+1)=struct('name',[tag '_MATLAB_history_matrix'],'residual',value,'tolerance',1e-10,'passed',value<=1e-10);
end
result=struct('status','PASS','count',numel(checks),'maximum_residual',max([checks.residual]),'checks',checks);
if ~all([checks.passed]),result.status='FAIL';end
fid=fopen(outputfile,'w','n','UTF-8');fprintf(fid,'%s',jsonencode(result,PrettyPrint=true));fclose(fid);
fprintf('%s %d checks maximum %.17g\n',result.status,result.count,result.maximum_residual);
assert(all([checks.passed]),'Independent MATLAB verification failed');
end



===== source_manifest.json | SHA256 af8a5cd4e6a6e0ab0a874641122f3b0d6952ab832530dd9f3d890643ae25d216 =====
[
  {
    "source": "D:\\JZ_PhD\\10_论文_Papers\\Li\\RHTS\\260915\\research\\audits\\unified_full15_equal_delay_20260916\\sources\\calculation.mat",
    "copy": "data\\calculation.mat",
    "sha256": "c1a938c67964033b18f226e9c1dda773c7bed22bce94bdbaaa1ab51f551568a7"
  },
  {
    "source": "D:\\JZ_PhD\\10_论文_Papers\\Li\\RHTS\\260915\\research\\audits\\unified_full15_equal_delay_20260916\\sources\\audit_matrices.mat",
    "copy": "data\\audit_matrices.mat",
    "sha256": "6d4ef2686258bfb8adb1009dfb8f8a2f9c44ce6b001203fce43e087120713e1b"
  },
  {
    "source": "D:\\JZ_PhD\\10_论文_Papers\\Li\\RHTS\\260915\\research\\audits\\unified_full15_equal_delay_20260916\\sources\\model_and_cases.mat",
    "copy": "data\\model_and_cases.mat",
    "sha256": "5332b75118c7c6b01a891900dbf25fea52ae0b0d367fe768fca9f74297d0dda8"
  }
]
