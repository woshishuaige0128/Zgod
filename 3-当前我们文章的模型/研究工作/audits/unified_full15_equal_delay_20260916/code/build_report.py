from pathlib import Path
import json,re,html
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1];R=OUT/'results'
def read(name):return json.loads((R/name).read_text('utf-8'))
py=read('validation_python.json');ma=read('validation_matlab.json');er=read('validation_error_identities.json')
def table(head,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def section(id,title,body):return f'<section id="{id}"><h2>{title}</h2>{body}</section>'
intro='''<p class="lead"><strong>已经得到两条数学一致的候选路线。</strong>两条路线都先定义原15自由度框架的等时滞反馈，再一致缩聚。全部内部模态能够恢复同一个完整闭环，原先“比较对象不同”的问题在候选数值模型中得到解决。</p>
<div class="callout"><strong>建议：</strong>以“完整框架直接缩聚”作为本论文缩聚误差理论的主验证，沿用原Guyan 6/5阶、CB 9/8阶设置，并保留划分二中间层位移被缩聚的研究问题。<br><strong>需要决定：</strong>是否接受这一研究定位；如果坚持物理与数值子结构分别缩聚，应采用完整共同界面路线，模型阶数及原有误差解释都要调整。</div>
<p>本轮完成候选公式、两种划分的代数原型、独立MATLAB核验及可转交审查的推导PDF。没有新的地震/扫频响应或稳定边界扫描。正式路线、实际两作动器的接口实现和外部理论审查分别记录，尚未认定完成。</p>'''
scope=section('scope','1．这次解决了什么', '''<p>上轮核查发现：无时滞案例直接缩聚完整15自由度框架，而旧有时滞路线只共享两个作动坐标，全部局部坐标恢复后为18/19自由度；有时滞时“恢复后选列”和“选列后恢复”还会改变反馈路径。</p>
<p>本轮把比较对象固定在原15个物理坐标：保留相同完整质量、刚度与阻尼；先写清哪些位移/速度信号延迟、反力如何作用，再对所有矩阵、荷载和输出做同一个基底变换。这样缩聚方法改变的是可表达的运动空间。</p>
<div class="flow"><span>原15坐标＋固定反馈路径</span><b>→</b><span>一致投影：结构、时滞、控制、荷载、输出</span><b>→</b><span>完整 / Guyan / CB</span></div>
<p><strong>共同物理假定：</strong>两个作动通道具有相同时滞；其他共同界面保持理想补充协调及力传递；惯性数值推进。两台实际作动器是否能配合装置、量测或数值耦合实现这些条件，是必须另行说明的实验问题。</p>''')
paths=section('paths','2．先定义完整框架的时滞，再缩聚', '''<p>“两个通道”指两个延迟的运动信号，不表示完整广义反力只作用在两个坐标。划分一的作动位置为首层和中间层，划分二为首层和顶层。</p>
<div class="formula">x<sub>P</sub>(t) = (I − BS)x(t) + BSx(t − τ)<br>
M ẍ + C<sub>0</sub> ẋ + K<sub>0</sub>x + U<sub>C</sub>Sẋ(t − τ) + U<sub>K</sub>Sx(t − τ) = f a<sub>g</sub>(t)</div>
<p>其中，x是15维完整数值坐标；S抽取两通道位移，B=Sᵀ；x<sub>P</sub>是物理侧反馈所用运动。C<sub>0</sub>、K<sub>0</sub>对应当前项，U<sub>C</sub>、U<sub>K</sub>把两个延迟信号转换为完整广义力。详细定义、控制项与符号单位见推导PDF。</p>
<p>用x≈Tq缩聚后，必须同时使用TᵀAT、TᵀU、ST和Tᵀf，并相应变换物理输出。不能只更新质量/刚度，再直接按缩聚矩阵的列号重新定义延迟。</p>
<div class="formula">Z<sub>缩聚</sub>(z,n) = Tᵀ Z<sub>完整</sub>(z,n) T<br>全部内部模态使T可逆 ⇒ 同输入、同历史、同输出下恢复同一个完整闭环。</div>
<p>这里Z是既定CR时间递推对应的特征矩阵，n是两通道共同的整数延迟步数。该关系已经逐项核验。零时滞恢复的是同控制器的完整框架；设控制增益为零才回到原被动框架方程。原RK4和当前CR的离散差异仍单列。</p>''')
choices=section('choices','3．两条路线的区别，必须在选案例之前说清',table(['项目','完整框架直接缩聚（建议用于主验证）','完整共同界面后的局部缩聚'],[
 ['基底怎么来','在原15自由度框架构造Guyan/CB','保留所有共同界面，分别构造物理与数值CB，再兼容装配'],
 ['划分一Guyan / 部分CB / 全模态','6 / 9（3个内部模态）/ 15','9 / 11或13 / 15'],
 ['划分二Guyan / 部分CB / 全模态','5 / 8（3个内部模态）/ 15','9 / 11或13 / 15'],
 ['划分二中间层位移','仍是内部坐标，可检验其动态遗漏影响','成为共享保留坐标，原来的解释须改写'],
 ['与原案例关系','延续原无时滞精度案例的保留坐标和阶数','延续局部子结构缩聚形式，但改变接口、阶数和模态数'],
 ['论文必须明确的变化','有时滞精度主线改为完整框架基底的一致投影','旧Guyan6/CB12不能继续当作新模型的阶数'],
 ['共同要求','原15结构为基准；全部时滞/控制/输出一致投影；说明理想补充界面','同左']
])+'''<p>两条路线都能满足“全模态恢复原15闭环”的代数条件。哪一条适合论文，取决于主问题是<strong>原保留坐标造成的缩聚误差</strong>，还是<strong>保持完整界面的局部子结构缩聚</strong>。本轮未用响应曲线筛选有利路线。</p>
<p>两种划分的作动位置和物理反馈矩阵不同，因此非零时滞下各自有对应的完整15阶参照。各划分内的完整、Guyan、CB保持同一路径；跨划分还需区分作动位置变化和截断变化。</p>''')
local=section('local','4．完整界面路线带来的两个新结论', '''<h3>划分一：零质量内部坐标可以通过正确保留界面解决</h3><p>原数值侧ψ₇是共同界面的转角。把它加入共享保留坐标后，它不再进入固定界面内部模态特征值问题。数值侧剩5个内部坐标，物理侧剩1个；两侧内部质量矩阵均正定，完整装配质量也正定。</p>
<p>在现有坐标和单位下，两侧内部质量块最小特征值均为51.0878119792。这是正定性检查数值；混合位移/转角的矩阵范数不直接解释为普通质量。本轮没有修改旧质量分配或添加小质量。</p>
<h3>划分二：每侧3个模态已经等于完整模型</h3><p>全部共同界面为ψ₁、ψ₃、ψ₆、ψ₈、ψ₁₁、ψ₁₃。保留它们后，物理和数值两侧分别只剩3个内部坐标，装配Guyan为9阶。</p>
<div class="formula">每侧1模态：9 + 1 + 1 = 11<br>每侧2模态：9 + 2 + 2 = 13<br>每侧3模态：9 + 3 + 3 = 15（全部内部模态）</div>
<p>所以“CB每侧3模态与完整模型重合”在这一路线中是精确恢复检验。若要量化有限阶CB的收益，应考察11/13阶等真正截断的模型。相应新响应尚未计算。</p>''')
error=section('error','5．怎样继续量化误差，而不靠人为放大曲线差距', '''<p>把缩聚解代回完整平衡方程，剩余的不平衡力可记为r。相同输入、相同物理输出的频域误差满足</p>
<div class="formula">r = f u − Z<sub>完整</sub>Tq<br>e = y<sub>缩聚</sub> − y<sub>完整</sub> = −Y<sub>完整</sub>Z<sub>完整</sub><sup>−1</sup>r</div>
<p>其中u为输入幅值，Y为共同输出映射。公式把误差来源分开：基底遗漏留下多少不平衡力，以及完整闭环会把这种不平衡放大多少。因此，临界附近、敏感频段和模态参与都可以从同一个模型解释。它不预设误差随时滞单调增加，也不预设CB每个指标都更好。</p>
<p>推导还给出遗漏模态的精确Schur补（把遗漏坐标代数消去），同时保留动态修正和荷载修正。两项恒等式完成了24项检查。对于地震和扫频采样，给出了固定整数延迟下的有限矩阵幂误差表达；该表达对应既定离散算法，后续才与独立时程比较。</p>''')
validation=section('validation','6．实际验证了什么',table(['检查','数量','最大归一化残差','结果'],[
 ['Python：两候选基底、零/部分/全部模态、荷载/输出、连续与CR算子、单步及增广关系',py['tests'],f"{py['max_normalized_residual']:.3e}",'通过'],
 ['MATLAB：独立模态构造、完整历史递推、全空间恢复与输出',ma['checks'],f"{ma['max_normalized_residual']:.3e}",'通过'],
 ['残量误差与遗漏模态Schur补恒等式',er['tests'],f"{er['max_normalized_residual']:.3e}",'通过']
])+'''<p>各项标准均为10⁻¹⁰。全部模态的增广状态满足相似关系，所以这是对同一离散闭环的坐标等价核验。本轮没有求新的稳定边界，也没有用新时程验证CB精度排序。</p>
<p>两条路线都在原完整正定质量空间中工作。局部路线还核验了两侧恢复的所有共同界面逐行相同、局部矩阵装配等于完整矩阵投影。</p>
<p>控制器取上一轮划分二已验证的固定增益，在本轮作为相同的代数测试系数使用；没有为划分一重新设计控制器或认定其控制性能。完整框架直接缩聚路线在划分二的完整15阶反馈系数与旧Full15参照逐项相等。</p>
<p>检查中发现一次MAT文件一维荷载向量默认保存为行向量，导致MATLAB与列向量相减时扩展成矩阵。已改为明确按列导出并重跑，容差和物理模型保持。延迟快捷选列的诊断也已修正为“先投影完整物理刚度再选列”的真实对照。</p>''')
changes=section('changes','7．采用后需要修改的公式与代码',table(['位置','具体变化','验证要求'],[
 ['完整模型与坐标表','先选完整框架基底或完整共同界面局部基底，统一列出阶数','空间维数、界面协调、零/全模态极限'],
 ['缩聚装配和延迟恢复','延迟定义放在原15坐标，随后一致投影','结构/当前/延迟项均满足投影恒等'],
 ['控制器、地震荷载、物理输出','同一比较使用同增益、输入和输出映射','控制零/非零、时滞零/非零各自口径清楚'],
 ['CR特征矩阵及状态递推','保留既定算法质量矩阵，同步投影各项','特征矩阵与状态递推一致；全模态相似'],
 ['案例与论文解释','按所选路线重算，重新确认划分二为何更敏感','响应、误差、极点与理论预测互相对应']
])+'''<p>这些修改目前以候选原型保存，原稿、两个旧案例和上一轮审计保持。下一轮先确定路线和接口解释，再决定控制策略、代表时滞与激励频段；新的五组图按已约定蓝图推进。</p>''')
decision=section('decision','8．建议与可直接审查的材料', '''<p><strong>我的建议是：优先把完整框架直接缩聚用于误差理论主验证。</strong>它与原15自由度精度目标直接对应，保留原来的Guyan/CB阶数及划分二中间层位移被缩聚的机制。论文相应定位为明确反馈路径下的虚拟等时滞RTHS缩聚误差研究，并说明补充界面采用理想协调。</p>
<p>如果论文的首要要求是两个子结构各自进行局部CB，则选择完整共同界面路线。该路线同样代数一致，并解决划分一内部质量正定性问题，但要接受Guyan9阶、不同局部模态数和新的划分二误差解释。</p>
<p><strong>本地材料：</strong>7页推导PDF、对应可编辑TeX、Python/MATLAB原型、冻结输入、全部验证结果和证据清单。审查问题聚焦：物理接口可实现性、两条路线的论文定位、延迟/控制位置、CR一致性及误差表达的条件。</p>
<p><strong>状态：</strong>候选方案本地验证完成；正式采用待Doctor Bego决定；Pro材料在本地准备，尚未发送、尚未收到反馈。按paper-writing“理论写完必须送Pro审查”的规则，依赖新理论的正式案例应在审查处理后推进。</p>''')
evidence=section('evidence','9．证据与复核入口',f'''<p>方案目录：<code>{html.escape(str(OUT))}</code></p>
<p>可读推导：<code>theory/unified_full15.pdf</code>；可编辑源：<code>theory/unified_full15.tex</code>。</p>
<p>实现：<code>code/unified_model.py</code>；核验：<code>verify_unified.py</code>、<code>VERIFY_UNIFIED.m</code>、<code>verify_error_identities.py</code>。数据：<code>sources/</code>与<code>source_manifest.json</code>。结果：<code>results/validation_python.json</code>、<code>validation_matlab.json</code>、<code>validation_error_identities.json</code>、<code>model_summary.json</code>。</p>
<p>科学来源：原完整框架与局部贡献来自上一轮冻结矩阵；原保留坐标来自标准Guyan代码；延迟与CR规则来自旧有时滞代码。文献背景为NASA Goddard的Scott Gordon《Craig Bampton Models》（1999，2008更新），其基底及投影说明用于术语核对。候选时滞公式由当前模型推导，外部文献不替代实验接口审查。</p>
<p>正式稿及旧案例无修改。本报告不依赖网络或旁置图片，移动后可独立阅读；代码、输入与验证通过版本清单定位。</p>''')
css='''*{box-sizing:border-box}body{margin:0;color:#18394c;background:#eef3f6;font:15px/1.8 "Microsoft YaHei","Segoe UI",sans-serif}main{max-width:1120px;margin:auto;padding:28px 24px}header,section{background:white;border:1px solid #d5e0e7;border-radius:10px;padding:26px;margin-bottom:20px}h1{font-size:28px;line-height:1.4;margin:10px 0}h2{font-size:22px;line-height:1.5;margin:0 0 16px}h3{font-size:17px;margin:20px 0 8px}p{margin:12px 0}.lead{font-size:18px}.badge{display:inline-block;padding:4px 12px;border-radius:16px;background:#e2f0f5;color:#226080}.callout{background:#eaf3f8;border-left:4px solid #386a8f;padding:16px 18px;margin:18px 0}.formula{background:#f5f7fa;border:1px solid #dbe5ec;padding:17px;line-height:2;overflow-x:auto;font-family:Georgia,"Microsoft YaHei",serif}.flow{display:flex;gap:10px;align-items:center;justify-content:center;margin:20px 0}.flow span{border:1px solid #d2e1eb;background:#f5f9fb;border-radius:6px;padding:12px;flex:1;text-align:center}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #dce5ec;text-align:left;vertical-align:top;padding:11px;min-width:110px}th{background:#edf4f7}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}nav a{color:#236488;border:1px solid #c8dce7;border-radius:5px;padding:5px 9px;text-decoration:none}code{font:13px/1.6 Consolas,"Microsoft YaHei",monospace;overflow-wrap:anywhere}section{scroll-margin-top:14px}footer{font-size:13px;color:#557186}strong{color:#102f44}@media(max-width:600px){main{padding:10px 8px}header,section{padding:18px 13px}h1{font-size:23px}h2{font-size:20px}.lead{font-size:16px}.flow{flex-direction:column;align-items:stretch}.flow b{text-align:center}td,th{padding:8px;font-size:13px}}@page{size:A4;margin:15mm}@media print{body{background:white;font-size:9pt;line-height:1.6}main{padding:0}header,section{border:0;border-radius:0;padding:0;margin-bottom:8mm}h1{font-size:18pt}h2{font-size:14pt;break-after:avoid}h3{font-size:11pt;break-after:avoid}.lead{font-size:11pt}nav{display:none}p{orphans:3;widows:3}table{font-size:8pt;table-layout:fixed}td,th{min-width:0;padding:5px;overflow-wrap:anywhere}tr,.callout,.formula,.flow{break-inside:avoid}thead{display:table-header-group}.table-wrap{overflow:visible}code{font-size:7pt}section{break-before:page}}
'''
nav=''.join(f'<a href="#{i}">{t}</a>' for i,t in [('scope','问题'),('paths','反馈路径'),('choices','路线选择'),('local','局部路线'),('error','误差公式'),('validation','验证'),('changes','修改范围'),('decision','建议'),('evidence','证据')])
page=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整框架等时滞统一模型方案汇报</title><style>{css}</style></head><body><main><header><span class="badge">Doctor Bego · 候选方案与代数验证</span><h1>完整框架等时滞统一模型方案汇报</h1>{intro}<nav>{nav}</nav></header>{scope}{paths}{choices}{local}{error}{validation}{changes}{decision}{evidence}<footer>2026-09-16 · 本地方案与核验完成；正式路线与外部理论审查分别记录。</footer></main></body></html>'
target=ROOT/'reports/完整框架等时滞统一模型方案汇报.html';target.write_text(page,'utf-8')
print('REPORT_CREATED',target.stat().st_size)
