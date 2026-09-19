from pathlib import Path
import json,html,re,base64,io,difflib,hashlib,shutil
import fitz
from PIL import Image

TMP=Path(__file__).resolve().parent
ROOT=TMP.parents[1]
NEW=ROOT.parent/'260817/elsevier_review_v2_20260907'
EV=NEW/'revision_evidence'
REPORT=NEW/'RHTS第二版全文修改逐项对照与回退决策汇报.html'
ops=json.loads((EV/'change_operations.json').read_text('utf-8'))
figs=json.loads((EV/'figure_mapping.json').read_text('utf-8'))
validation=json.loads((EV/'validation_summary.json').read_text('utf-8'))
tables=json.loads((EV/'data/table345_verified_values.json').read_text('utf-8'))['rows']
before=(EV/'baseline/main_before.tex').read_text('utf-8')
after=(NEW/'main.tex').read_text('utf-8')
E=lambda s:html.escape(str(s),quote=True)

def img_uri(path,width=1500):
    if path.suffix.lower()=='.pdf':
        d=fitz.open(path);pix=d[0].get_pixmap(dpi=155);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
    else:im=Image.open(path).convert('RGB')
    im.thumbnail((width,2100))
    bio=io.BytesIO();im.save(bio,format='PNG',optimize=True)
    return 'data:image/png;base64,'+base64.b64encode(bio.getvalue()).decode()

def strip_wrapper(s,name):
    token='\\'+name+'{'
    while token in s:
        start=s.index(token);j=start+len(token);depth=1;k=j
        while k<len(s) and depth:
            if s[k]=='{' and (k==0 or s[k-1]!='\\'):depth+=1
            elif s[k]=='}' and (k==0 or s[k-1]!='\\'):depth-=1
            k+=1
        if depth:break
        s=s[:start]+s[j:k-1]+s[k:]
    return s

def readable(s):
    s=re.sub(r'(?m)^\s*%.*$','',s)
    for token in ['rev','textbf','textit','emph']:s=strip_wrapper(s,token)
    s=s.replace('\\%','%').replace('~',' ').replace('--','–')
    return s.strip()

def diffpair(a,b):
    a=re.findall(r'\s+|[^\s]+',readable(a));b=re.findall(r'\s+|[^\s]+',readable(b))
    left=[];right=[]
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        av=E(''.join(a[i:j]));bv=E(''.join(b[k:l]))
        left.append(av if tag=='equal' else '<del>'+av+'</del>')
        right.append(bv if tag=='equal' else '<ins>'+bv+'</ins>')
    return (''.join(left) if a else '<em>原稿无此内容。</em>'),(''.join(right) if b else '<em>已删除此重复内容。</em>')

def decision(key,title):
    return '<div class="decision" data-key="'+E(key)+'"><label>对此项的决定 <select aria-label="'+E(title)+'的审阅决定"><option value="pending">待审阅</option><option value="keep">保留</option><option value="rollback">回退</option><option value="revise">再修改</option></select></label><textarea rows="2" aria-label="'+E(title)+'的审阅备注" placeholder="可写明希望保留或撤回的具体句子"></textarea></div>'

# The operation ledger is sequential. Pure insertions are displayed without the
# unchanged anchor; later token-level corrections are propagated to their final form.
normal=[]
for i,r in enumerate(ops):
    a,b=r['old'],r['new'];kind='替换'
    if b.startswith(a) and a:
        b=b[len(a):];a='';kind='新增'
    elif b.endswith(a) and a:
        b=b[:-len(a)];a='';kind='新增'
    if not b:kind='删除'
    for later in ops[i+1:]:
        if later.get('file','main.tex')!=r.get('file','main.tex'):continue
        lo,ln=later['old'],later['new']
        if lo and lo in b and not ln.startswith(lo) and not ln.endswith(lo):b=b.replace(lo,ln,1)
    if r['id']=='change-060':
        a=next(m.group() for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',before,re.S) if r'\label{fig:division}' in m.group())
        b=next(m.group() for m in re.finditer(r'\\begin\{figure\}.*?\\end\{figure\}',after,re.S) if r'\label{fig:division}' in m.group())
    normal.append({**r,'display_old':a,'display_new':b,'operation_kind':kind})

special={
'change-009':('梁弹性模量为200 GPa。','改为206 GPa；该值与当前计算入口一致。'),
'change-010':('柱弹性模量为200 GPa。','改为206 GPa；该值与当前计算入口一致。'),
'change-017':('原稿没有激励时程图。','新增图5：0.40倍El Centro地震输入和0.1–10 Hz线性扫频输入，均为实际计算输入。'),
'change-026':('表3共16个数值，其中5个与实际矩阵计算不符。','仅替换这5个数值，11个已相符的数值保留；下面逐格列出。'),
'change-027':('表4共24个数值，其中21个与当前输出按原公式复算不符。','替换这21个数值，3个已相符值保留；采用印出的频带端点和全记录极差。'),
'change-028':('表5四个数值为0.3065、0.1879、0.3927、0.2021。','依次改为−0.0414、0.0039、0.8914、0.0365，并联动修正解释。'),
'change-030':('原稿只有频率误差及保留坐标MAC表。','新增图6：两种划分前两阶的实际频率，以及恢复到三层后的水平振型。'),
'change-044':('原稿用表5的单一指标解释模态变化。','新增图15：显示15个坐标的份额，以及两个作动坐标各自的正负贡献。'),
'change-050':('旧图把位移跟踪控制、实测位移反馈和力反馈方程混在同一路径。','图1按保留的闭环方程重绘：数值位移/速度产生调节力，调节力和物理反力分别经过延迟返回力求和点。'),
'change-051':('旧图内有中文标注和旧中文图号，展示原型几何、混合柱脚及截面。','图2重绘为英文，保留原型尺寸、混合柱脚及截面信息；图注说明实际数值截面参数见正文。'),
'change-052':('旧理想模型图含15坐标和节点编号，但内侧柱脚画为铰支，与当前数值矩阵不符。','图3保留节点和全部15坐标，将数值模型内侧柱脚改为固结并标红。'),
'change-053':('旧两张分图包含两侧子结构及保留坐标，但有中文、旧图号及物理侧局部节点误号。','图4保留完整划分信息，合成英文矢量图；更正物理侧节点编号，并明确它说明的是局部子结构配置。'),
'change-054':('正文引用重复键CraigBampton1968。','统一使用已有键Craig1968，引用标红。'),
'change-055':('文献库同时包含同一篇1968年文献的两个条目。','删除重复条目CraigBampton1968，保留Craig1968。'),
'change-056':('正文引用重复键ChenRicles2008b。','统一使用已有键ChenCR2008，引用标红。'),
'change-057':('文献库同时包含同一篇CR积分算法文献的两个条目。','删除重复条目ChenRicles2008b，保留ChenCR2008。'),
'change-058':('原稿未限制图件跨越正文大节，新增图后曾积压到文献之后。','引入placeins的section选项，在节边界输出待排图件。'),
'change-059':('模板要求浮动页填充比例较高，阻碍中等大小图件及时单独成页。','将浮动页阈值设为0.65，使新增图及时排出。'),
'change-060':('原稿图4两张分图各按正文宽度89%排入，没有高度上限。','新版合成图4宽度上限98%、高度上限74%，保持纵横比，全部内容保留。'),
'change-061':('地震与扫频结果小节前没有浮动屏障。','在该小节前加入FloatBarrier，使模态结果图先排完。'),
'change-062':('稳定性结果小节前没有浮动屏障。','在该小节前加入FloatBarrier，使位移和层间位移角图先排完。'),
'change-063':('模态份额结果小节前没有浮动屏障。','在该小节前加入FloatBarrier，使稳定域图先排完。'),
'change-064':('参考文献开始前没有浮动屏障。','在参考文献前加入FloatBarrier，使正文全部图件先排完。')}

def rollback(r):
    i=int(r['id'].split('-')[-1])
    if i in [9,10,26,27,28]:return '单独恢复旧数值会重新造成图表或代码不一致。如决定换用另一套模型，应连同数据来源、相关正文和图件一起更新。'
    if i in [1,25,34,36,42,46,48,49]:return '此段包含已核验数值的联动。可以保留数值纠正、仅回退措辞；若整段回退，需要同时恢复或重新核验对应表格。'
    if i in [2,3,4,13,14,15,23,24,29,37,40,41,45]:return '这是涉及模型口径的重点审阅项。回退后需说明现有计算究竟支持哪套模型，不能让全局精度数据继续承担未完成的双侧界面验证。'
    if r['category']=='新增结果图':return '可独立撤回此图及对应新增解释；图号由LaTeX自动更新。若删除中层验证，需要同步调整摘要、结论和对审稿意见6的答复。'
    if r['category']=='示意图必要修订':return '可选择保留图面风格、局部回退图形修改；恢复旧图时须同步处理中文、节点/支座或信号路径与正文的一致性。'
    if r['category']=='格式与文献整理':return '通常可独立回退，但必须重新编译并检查图件位置、重复引用及总页数；42处原负间距不属于本项。'
    return '可保留原段结构并单独修改新增措辞。若恢复原句，请同时核对本项指出的公式、坐标定义或实际数据是否仍支持该句。'

figtitles={1:'附加力反馈与延迟回路',2:'原型几何与截面',3:'数值模型节点及15个自由度',4:'两种局部子结构划分',5:'实际地震与扫频输入',6:'前两阶频率与水平振型',7:'首层/中层设通道：地震首层与顶层响应',8:'首层/顶层设通道：地震首层与顶层响应',9:'未保留中层的地震重构与误差',10:'首层/中层设通道：扫频首层与顶层响应',11:'首层/顶层设通道：扫频首层与顶层响应',12:'未保留中层的扫频重构与误差',13:'峰值层间位移角分布',14:'原有双通道延迟稳定域',15:'模态份额及各作动坐标贡献'}
figpurposes={1:'统一图与式(3.5)–(3.6)的力反馈含义；尚不构成原稳定边界已重算的证明。',2:'保留原型几何信息，避免将它与实际采用的有效截面混同。',3:'让15个坐标、节点编号和当前数值柱脚条件一一对应。',4:'保留两侧子结构的具体划分与保留坐标；与全局精度模型分别说明。',5:'直观看到真实输入幅值、40 s时间范围以及扫频过程。',6:'补充MAC不能展示的实际频率偏移和中层空间形状。',7:'原图保留，用于整体准确性对比。',8:'原图保留，用于中层被消去方案的整体准确性对比。',9:'直接检验ψ6的单一全局重构值。Guyan/CB误差10.798%/0.031%。',10:'原图保留，正文修正峰值时间。',11:'原图保留，正文修正末端幅值判断。',12:'检验扫频下ψ6重构。Guyan/CB误差11.749%/0.034%。',13:'检验相邻楼层相对变形，补充单层位移无法直接反映的工程响应。',14:'保留原有边界数据，单位按1000/1024精确换算。匹配的闭环矩阵与增益仍待补齐。',15:'展示表5两个独立分母和正负抵消，避免把带符号指标解释为总能量。'}

reviews=[
('1','图表与NRMSE计算不一致','采纳，已验证','按当前四套真实时程和原式定义复算，改表3至表5共30格并联动正文；峰值时刻及末端幅值也核对。','表3、表4；新增图5、6、9、12、13；232项MATLAB/Python对照。','不能从图面近似值直接抄表；本轮使用原始CSV。'),
('2','部分界面装配与完整模型子空间混用','部分解决，重点审阅','补坐标/力投影装配，删除普遍Ritz上界；如实区分全局精度模型与原文局部子结构配置。','修改002–004、013–015、023–024、029、037。','双侧未匹配界面的实际计算实现尚未闭合，未宣称已解决该科学问题。'),
('3','模态份额扩展和能量解释','采纳保留公式的方案，已验证','保留式(4.4)，说明按完整质量重新归一化、各模型独立参与权重；将其解释为各作动坐标相对份额变化之和。','表5与新增图15；15个物理坐标份额及两通道贡献CSV。','当前表值属于唯一全局恢复；它不提供双侧界面恢复值，也不能预测稳定域。'),
('4','LQR力反馈、位移框图和信号不统一','图文已统一，闭环实现待补','保留现有方程，重绘图1并写明数值状态输入和延迟调节力施加位置。','修改005、007、039、050。','尚缺原稳定边界使用的实际增益和完整闭环矩阵，不能据新框图宣布边界已验证。'),
('5','无直接模态延迟被写成无时滞或必然更稳定','采纳，已修改','区分“不直接经过作动器”和“仍与延迟通道耦合”；两种方法都有两个通道。','修改006、041、047及结论。','没有添加未经验证的普遍稳定性定理。'),
('6','关键中层水平坐标未直接验证','单一全局重构已验证；双侧差值未完成','新增中层地震和扫频响应、两种误差轨迹及峰值层间位移角。','新增图9、12、13及完整三层时程。','当前程序只给一个全局恢复值，无法据此计算物理侧与数值侧的界面位移差。'),
('7','实际边界、质量、阻尼与输入参数不足','精度模型参数已补齐','补206 GPa、四柱脚固定、有效截面、190倍质量系数、质量矩阵对角值、Rayleigh系数及完整输入。','正文4.1–4.3；supplementary_data的M/C/K/T与输入。','这些矩阵闭合全局精度计算，不能替代原稳定性模型的缺失参数。'),
('8','不同控制增益的比较含义','采纳必要解释；增强计算未做','保留各模型配套调节器，稳定域表述为模型与调节器的联合结果。','修改041、049；原Q/R设置保留。','共同增益、R参数扫描和模态阶数扫描均未运行，不为凑图新增这些计算。'),
('9','边界内外需独立扰动时程核验','建议成立，本轮未实施','明确原稳定域来源和未补齐的计算条件，保留已有参考图。','图14及修改040。','必须先恢复生成该图的闭环矩阵、增益、离散实现，再做匹配时程；不能用精度模型伪造这一验证。')]
minor=[('整数延迟与毫秒','原图已精确换算；正文改为1步=0.9765625 ms。'),('混合平移/转角MAC','明确米和弧度且未额外缩放，保留原MAC定义，另加纯水平振型图。'),('误差非单调','改为随扫频阶段变化，保留前一频段衰减响应影响的说明。'),('NRMSE适用输出','摘要、方法适用性和结论明确第一层位移与全记录极差；中层结果单独报告。'),('图内中文和旧图号','前四幅示意图重绘为英文矢量图；保留原图重要信息。'),('重复文献','合并两组重复条目和引用键，实际重新执行BibTeX。')]

decisions=[]
def card(r):
    key=r['id'];title=r['title'];a=r['display_old'];b=r['display_new'];oldzh,newzh=special.get(key,(r.get('old_zh',''),r.get('new_zh','')))
    if not oldzh:oldzh='对应原文见下方逐字对照。'
    if not newzh:newzh='对应新版内容见下方逐字对照。'
    left,right=diffpair(a,b)
    decisions.append({'id':key,'title':title,'file':r.get('file','main.tex'),'category':r['category']})
    children=''
    if r.get('cells'):
        rows=[]
        for c in r['cells']:
            ck=f'table-cell-{c["id"]:02}'
            label=f'表{c["table"]} · 划分{c["division"]} · {c["item"]} · {c["method"]} · {c["metric"]}'
            decisions.append({'id':ck,'title':label,'category':'逐格数值','parent':key})
            rows.append('<div class="cell-change"><b>'+E(label)+'</b><p><del>'+E(c['manuscript_value'])+'</del><span class="arrow"> → </span><ins>'+E(c['rounded_value'])+'</ins></p><p>独立复算未舍入值：<code>'+E(format(c['recomputed'],'.14g'))+'</code>。按稿件原小数位显示；该单元在正文标红。</p>'+decision(ck,label)+'</div>')
        children='<details class="cells" open><summary>逐格核对与独立决定（'+str(len(rows))+'格）</summary>'+''.join(rows)+'</details>'
    return '<article class="change-card" id="'+key+'" data-category="'+E(r['category'])+'"><div class="card-head"><span class="badge">'+E(r['category'])+'</span><span class="serial">'+E(key.replace('change-','审阅编号 '))+'</span></div><h3>'+E(title)+'</h3><div class="summary-pair"><div><h4>原来</h4><p>'+E(oldzh)+'</p></div><div><h4>现在</h4><p>'+E(newzh)+'</p></div></div><p class="reason"><b>为什么改：</b>'+E(r['reason'])+'</p><p><b>依据：</b>'+E(r['source'])+'</p><p class="rollback"><b>回退影响：</b>'+E(rollback(r))+'</p>'+children+'<details class="exact"><summary>展开原文与新版完整对照（英文 / 公式源码，未截断）</summary><div class="before-after"><section><h4>冻结原稿</h4><pre>'+left+'</pre></section><section><h4>当前新版</h4><pre>'+right+'</pre></section></div><p class="small">为便于阅读，此处移除了红色标记命令；原始TeX操作记录保存在报告所附证据目录中。删除文字以划线显示，新增文字以红色显示。</p></details>'+decision(key,title)+'</article>'

maincards=''.join(card(r) for r in normal if r['category']!='格式与文献整理')
formatcards=''.join(card(r) for r in normal if r['category']=='格式与文献整理')

figurehtml=[];imagecount=0
for f in figs:
    n=f['number'];state='新增' if f['old_number'] is None else ('必要重绘' if n<=4 else '图形保留')
    gallery=''
    if n<=4:
        for old in f['old_files']:
            p=ROOT.parent/'260817/elsevier/submit_figure'/old
            if not p.exists():p=ROOT.parent/'260817/elsevier_review_20260906/submit_figure'/old
            assert p.exists(),p
            gallery+='<figure><figcaption>原图：'+E(old)+'</figcaption><img loading="eager" alt="'+E(figtitles[n])+'的原图" src="'+img_uri(p)+'"></figure>';imagecount+=1
    p=NEW/'submit_figure'/f['files'][0]
    gallery+='<figure><figcaption>新版图'+str(n)+' · 正文第'+str(f['page'])+'页</figcaption><img loading="eager" alt="新版图'+str(n)+'：'+E(figtitles[n])+'" src="'+img_uri(p)+'"></figure>';imagecount+=1
    figurehtml.append('<article class="figure-card" id="figure-'+str(n)+'"><h3>图'+str(n)+' · '+E(figtitles[n])+' <span class="badge">'+state+'</span></h3><p>'+E(figpurposes[n])+'</p><p class="small">'+('原稿无此图。' if f['old_number'] is None else '原稿图'+str(f['old_number'])+'。')+' 文件：<code>'+E(f['files'][0])+'</code></p><details class="figure-preview"><summary>展开内嵌图片'+('及原图对照' if n<=4 else '')+'</summary><div class="gallery">'+gallery+'</div></details></article>')

reviewhtml=''.join('<tr><td><b>'+E(n)+'. '+E(title)+'</b></td><td>'+E(status)+'</td><td>'+E(action)+'<p class="small">'+E(evidence)+'</p></td><td>'+E(limit)+'</td></tr>' for n,title,status,action,evidence,limit in reviews)
minorhtml=''.join('<tr><td>'+E(a)+'</td><td>'+E(b)+'</td></tr>' for a,b in minor)
raw=json.loads((EV/'raw_hunks.json').read_text('utf-8'))
rawhtml='<details class="raw"><summary>原稿与最终稿全部'+str(len(raw))+'处实际文本差异（底层完整性复核）</summary>'+''.join('<details><summary>原稿行'+str(h['old_start'])+'至'+str(h['old_end'])+' → 新稿行'+str(h['new_start'])+'至'+str(h['new_end'])+'</summary><pre>'+E(h['old'])+'</pre><pre>'+E(h['new'])+'</pre></details>' for h in raw)+'</details>'
visual={'status':'REVIEWED_WITH_INHERITED_LIMITATIONS','pages_reviewed':list(range(1,39)),'all_figure_captions_reviewed':15,'observations':['38页全部渲染检查；15幅图及5张表均在正文，图件无裁切，参考文献在36至38页。','第6、7、8、12、13、21、22页部分显示公式与下方文字紧贴或重叠；42处原负间距按用户要求完全保留。','编译存在原模板117.0831pt Overfull提示和两条Underfull提示，无Error、未定义引用或??。'],'not_claimed':'未声称版面零缺陷或原稳定性科学闭环已完成。','pdf_sha256':validation['pdf_sha256']}
(EV/'validation/manuscript_visual_review.json').write_text(json.dumps(visual,ensure_ascii=False,indent=2),encoding='utf-8')

style=r'''
:root{--ink:#192b3e;--muted:#57697c;--paper:#fff;--navy:#17374e;--line:#d6e0e8;--accent:#076c78;--red:#b52630;--soft:#eef6f7;--gold:#946119}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;background:#eff3f6;color:var(--ink);font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;font-size:16px;line-height:1.75}a{color:#075d70;text-underline-offset:3px}header{background:var(--navy);color:white;padding:48px max(24px,calc((100vw - 1150px)/2));}header h1{font-size:32px;line-height:1.4;max-width:1000px;margin:10px 0 18px}header p{max-width:1000px;color:#dce8ef}.eyebrow{letter-spacing:.12em;font-size:13px;color:#b6dce0}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:28px}.metric{border-top:2px solid #5492a3;padding-top:10px}.metric b{display:block;font-size:26px}.metric span{font-size:14px;color:#dce8ef}.toolbar{position:sticky;top:0;z-index:10;background:#fffefb;box-shadow:0 2px 12px #18304116;padding:12px max(20px,calc((100vw - 1150px)/2));display:flex;flex-wrap:wrap;gap:9px;align-items:center}button,input,select,textarea{font:inherit;color:inherit}button{border:1px solid #acc0cc;background:#fff;padding:7px 11px;border-radius:6px;cursor:pointer}button:hover{background:var(--soft)}button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #cb861f;outline-offset:2px}#search{min-width:200px;flex:1;border:1px solid #acc0cc;border-radius:6px;padding:8px}select{border:1px solid #acc0cc;border-radius:5px;background:white;padding:7px}main{max-width:1200px;margin:auto;padding:22px 25px 80px}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:26px;margin:22px 0}h2{font-size:25px;margin:0 0 15px;line-height:1.45}h3{font-size:20px;line-height:1.5;margin:10px 0 14px}h4{font-size:15px;margin:0 0 8px;color:#566a7e}p{margin:9px 0}ul{padding-left:24px}li{margin:7px 0}.toc{display:flex;gap:10px 22px;flex-wrap:wrap}.toc a{font-weight:bold}.notice{background:#fff4df;border-left:4px solid #c68626;padding:16px 20px;margin:20px 0}.good{background:var(--soft);border-left:4px solid var(--accent);padding:16px 20px}.table-wrap{overflow:auto;max-width:100%;margin:16px 0}table{border-collapse:collapse;width:100%;font-size:14px;min-width:620px}th,td{padding:12px;border:1px solid var(--line);vertical-align:top;text-align:left}th{background:#edf3f6;font-weight:bold}td p{margin:5px 0}.change-card,.figure-card{border:1px solid var(--line);border-radius:9px;background:#fff;padding:24px;margin:20px 0}.change-card:target,.figure-card:target{box-shadow:0 0 0 3px #75aeba}.card-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.badge{font-size:12px;color:#075862;background:#e9f4f5;padding:4px 9px;border-radius:20px;white-space:nowrap}.serial{font-size:12px;color:#6d7f8e}.summary-pair,.before-after{display:grid;grid-template-columns:1fr 1fr;gap:16px;min-width:0}.summary-pair>div{background:#f5f7f9;padding:15px;border-radius:6px;min-width:0}.summary-pair>div+div{background:#f0f8f5}.reason{padding-top:10px}.rollback{color:#765018}.small{font-size:13px;color:var(--muted);overflow-wrap:anywhere}code{font-family:Consolas,monospace;font-size:.92em;overflow-wrap:anywhere}pre{font-family:"Times New Roman",Consolas,serif;font-size:15px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-width:100%;margin:0;padding:14px;background:#f7f9fb;border:1px solid #dce5eb;border-radius:5px}del{color:#843b46;background:#fff0f0;text-decoration-color:#b24651}ins{color:var(--red);background:#fff1ee;text-decoration:none}.arrow{font-size:22px;color:#5f7586}.exact,.cells,.raw,.figure-preview{margin-top:16px}summary{cursor:pointer;color:#165e70;font-weight:600;padding:8px 0}.before-after section{min-width:0}.decision{background:#f1f5f8;border-radius:6px;padding:12px;margin-top:15px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}.decision label{display:flex;gap:10px;align-items:center;font-size:14px}.decision select{font-size:14px}.decision textarea{flex:1;min-width:220px;border:1px solid #bfced9;border-radius:5px;padding:8px;font-size:14px;resize:vertical;line-height:1.5}.cell-change{border-top:1px solid var(--line);padding:17px 0}.cell-change>p{font-size:14px}.cell-change>p:nth-child(2){font-size:20px}.gallery{display:grid;grid-template-columns:1fr;gap:18px}.gallery figure{margin:0;background:white;border:1px solid var(--line);padding:14px}.gallery figcaption{font-size:14px;color:var(--muted);margin-bottom:10px}.gallery img{width:100%;max-width:100%;height:auto;display:block}#status{font-size:13px;color:var(--muted)}.empty{display:none;padding:25px}.raw pre{font-size:12px}.filelist{font-size:14px}.filelist code{color:#305870}footer{margin-top:30px;color:#62788a;font-size:13px;border-top:1px solid var(--line);padding-top:18px}.hidden{display:none!important}#progress{font-size:14px;color:#426071}.hash{word-break:break-all}.keep-original{background:#f6f8fa;padding:14px;border-radius:5px}.scope-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:760px){body{font-size:15px}header{padding:28px 20px}header h1{font-size:25px}.metrics{grid-template-columns:1fr 1fr}.metric b{font-size:23px}.toolbar{position:static;padding:12px;gap:7px}.toolbar button{font-size:13px}main{padding:6px 12px 45px}.panel{padding:18px 15px}.change-card,.figure-card{padding:17px 14px}.summary-pair,.before-after,.scope-grid{grid-template-columns:1fr}.decision{display:block}.decision textarea{display:block;width:100%;min-width:0;margin-top:10px}.decision label{flex-wrap:wrap}.card-head{align-items:flex-start}h2{font-size:22px}h3{font-size:18px}.toc{gap:8px 16px}.badge{white-space:normal}.gallery figure{padding:7px}pre{font-size:14px}}
@page{size:A4;margin:16mm 14mm 17mm} @media print{html{scroll-behavior:auto}body{background:white;font-size:9.5pt;line-height:1.6;color:#111}header{padding:0 0 12pt;background:white;color:#111}header h1{font-size:21pt}header p,.eyebrow,.metric span{color:#333}.metrics{grid-template-columns:repeat(4,1fr);margin-top:12pt}.metric b{font-size:18pt}.toolbar,.decision,.toc,.no-print,#progress{display:none!important}main{max-width:none;padding:0}.panel{padding:12pt 0;margin:16pt 0;border:0;border-radius:0}.change-card,.figure-card{padding:10pt 12pt;border:1px solid #aaa;margin:12pt 0;border-radius:0;break-inside:auto}h2{font-size:16pt;break-after:avoid}h3{font-size:12.5pt;break-after:avoid}h4{break-after:avoid}p{orphans:3;widows:3}.summary-pair{grid-template-columns:1fr 1fr;gap:12pt}.summary-pair>div{padding:8pt;background:#fafafa}table{font-size:8pt;min-width:0}th,td{padding:6pt}tr,.cell-change{break-inside:avoid}.table-wrap{overflow:visible}thead{display:table-header-group}.notice,.good{padding:10pt 12pt;background:#fff}.badge{background:#eee;color:#111}.exact,.raw{display:none!important}body.print-full .exact{display:block!important}.exact pre{font-size:8.5pt}.before-after{display:block}.before-after section{margin-top:8pt}.cells>summary{display:none}.gallery img{max-height:175mm;object-fit:contain}.gallery figure{break-inside:avoid}.figure-preview summary{display:none}.figure-preview{margin-top:8pt}.gallery{display:block}.small{font-size:8pt}footer{display:none}.hidden{display:block!important}.empty{display:none!important}}
'''

script=r'''
const meta=JSON.parse(document.getElementById('report-meta').textContent);const storageKey='rths-v2-review-'+meta.main_sha256;let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){};
const states={pending:'待审阅',keep:'保留',rollback:'回退',revise:'再修改'};
function persist(){try{localStorage.setItem(storageKey,JSON.stringify(saved));document.getElementById('status').textContent='决定已保存在当前浏览器'}catch(e){document.getElementById('status').textContent='浏览器不允许本地保存，请使用导出决定'}updateCount()}
function updateCount(){const all=meta.decisions.length;const reviewed=Object.values(saved).filter(x=>x.state&&x.state!=='pending').length;document.getElementById('progress').textContent=`已审阅 ${reviewed} / ${all} 个决定位置（含逐格决定）`}
document.querySelectorAll('.decision').forEach(box=>{const key=box.dataset.key;const sel=box.querySelector('select'),note=box.querySelector('textarea');if(saved[key]){sel.value=saved[key].state||'pending';note.value=saved[key].note||''}function change(){saved[key]={state:sel.value,note:note.value};persist()}sel.addEventListener('change',change);note.addEventListener('input',change)});updateCount();
function filter(){const q=document.getElementById('search').value.trim().toLowerCase();const cat=document.getElementById('category').value;let count=0;document.querySelectorAll('.change-card').forEach(card=>{const show=(!q||card.textContent.toLowerCase().includes(q))&&(!cat||card.dataset.category===cat);card.classList.toggle('hidden',!show);if(show)count++});document.getElementById('search-count').textContent=`当前显示 ${count} / 64 项修改`;document.getElementById('empty').style.display=count?'none':'block'}
document.getElementById('search').addEventListener('input',filter);document.getElementById('category').addEventListener('change',filter);filter();
document.getElementById('expand').onclick=()=>document.querySelectorAll('.exact').forEach(d=>d.open=true);document.getElementById('collapse').onclick=()=>document.querySelectorAll('.exact').forEach(d=>d.open=false);
document.getElementById('export').onclick=()=>{const payload={report_title:meta.title,main_sha256:meta.main_sha256,pdf_sha256:meta.pdf_sha256,exported_at:new Date().toISOString(),scope:'审阅决定；未修改任何论文文件',decisions:meta.decisions.map(d=>({...d,...(saved[d.id]||{state:'pending',note:''})}))};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='RHTS第二版审阅与回退决定.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
document.getElementById('import').onclick=()=>document.getElementById('import-file').click();document.getElementById('import-file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const p=JSON.parse(await f.text());if(p.main_sha256!==meta.main_sha256)throw Error('决定文件对应另一版正文，未导入');for(const d of p.decisions||[]){if(meta.decisions.some(x=>x.id===d.id)&&states[d.state])saved[d.id]={state:d.state,note:String(d.note||'')}}document.querySelectorAll('.decision').forEach(b=>{const d=saved[b.dataset.key];if(d){b.querySelector('select').value=d.state;b.querySelector('textarea').value=d.note}});persist()}catch(err){document.getElementById('status').textContent='导入失败：'+err.message}e.target.value=''};
let printState=[];function beforePrint(){printState=[...document.querySelectorAll('details')].map(d=>[d,d.open]);document.querySelectorAll('.cells,.figure-preview').forEach(d=>d.open=true);if(document.body.classList.contains('print-full'))document.querySelectorAll('.exact').forEach(d=>d.open=true)}function afterPrint(){printState.forEach(([d,o])=>d.open=o);printState=[]}window.addEventListener('beforeprint',beforePrint);window.addEventListener('afterprint',afterPrint);
document.getElementById('print').onclick=()=>{document.body.classList.toggle('print-full',document.getElementById('full-print').checked);window.print()};
'''

meta={'title':'RHTS第二版全文修改逐项对照与回退决策汇报','main_sha256':validation['main_sha256'],'pdf_sha256':validation['pdf_sha256'],'operations':64,'table_cell_subdecisions':30,'decisions':decisions,'embedded_images':imagecount}
assert len(decisions)==94 and imagecount==20
text='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RHTS第二版全文修改逐项对照与回退决策汇报</title><style>'''+style+'''</style></head><body>
<header><div class="eyebrow">RTHS · 保留原稿结构的独立第二版 · 2026年9月7日</div><h1>全文修改逐项对照<br>与回退决策汇报</h1><p>Doctor Bego，本轮已在独立文件夹完成修订稿：按真实计算纠正表格与关联文字，选择性采纳必要审稿意见，并将编号图片由9幅增至15幅。这里逐项说明原来是什么、现在是什么、为什么改，以及回退会影响哪里。正文可编辑、修改标红，原稿和上一版保留。</p><div class="metrics"><div class="metric"><b>64 项</b><span>正文与文献修改操作</span></div><div class="metric"><b>30 + 2 格</b><span>三张结果表 + 材料表改值</span></div><div class="metric"><b>15 幅 / 38 页</b><span>已编译的新版论文</span></div><div class="metric"><b>42 / 42</b><span>原负间距命令完整保留</span></div></div></header>
<div class="toolbar no-print"><input id="search" type="search" aria-label="搜索修改" placeholder="搜索修改、数值、原因…"><select id="category" aria-label="筛选修改类型"><option value="">所有修改类型</option>'''+''.join('<option>'+E(c)+'</option>' for c in sorted({r['category'] for r in ops}))+'''</select><button id="expand">展开全文对照</button><button id="collapse">收起全文对照</button><button id="export">导出决定</button><button id="import">导入决定</button><input id="import-file" type="file" accept=".json" hidden><button id="print">打印</button></div>
<main><nav class="panel toc" aria-label="报告目录"><a href="#overview">现在完成了什么</a><a href="#reviews">审稿意见如何处理</a><a href="#changes">逐项修改</a><a href="#figures">15幅图及原图对照</a><a href="#evidence">验证与文件入口</a><a href="#decision-help">如何决定回退</a><a href="#formatting">最后：格式与文献</a></nav>
<section class="panel" id="overview"><h2>现在完成了什么</h2><div class="scope-grid"><div><h3>修订与数据工作已经完成</h3><ul><li>表3至表5共44项按当前出图数据复算：30格需改、14格原已相符。表1另将梁柱弹性模量各改为206 GPa。</li><li>摘要、结果讨论、方法适用性和结论同步更新。原稿引言逐字保留，未以压缩篇幅为目标。</li><li>新增6幅结果图，重绘4幅必要示意图，5幅已有数值图保留。</li><li>232项数值经MATLAB与Python独立对照，最大绝对差2.448×10⁻¹²；350项技术检查通过。</li></ul></div><div><h3>需要分别理解的两套证据</h3><p>当前精度图表来自完整15自由度框架的整体缩聚：划分I保留首层、中层、顶层平移及3个转角，Guyan/CB为6/9阶；划分II去掉中层平移，为5/8阶。</p><p>原文的局部子结构配置只合并两个界面坐标，Guyan/CB为6/12阶。原稳定边界对应的完整闭环矩阵和实际控制增益尚未恢复。两套证据不能互相代替。</p></div></div><div class="notice"><b>本轮完成的是可审阅的修订稿，不是全部科学问题的闭合。</b> 双侧界面位移差、原稳定边界的闭环重建及边界内外扰动时程尚未完成。新增中层图验证了当前全局模型的恢复响应。第6、7、8、12、13、21、22页部分公式仍与下方文字紧贴或重叠，这是保留原负间距后的已知版面问题。</div><div class="keep-original"><b>保留内容：</b>原论文研究动机、引言、主要方程框架、两通道约束、原始几何信息、已有五幅数值图和42处负间距。仅增加必要定义、纠正证据不支持的判断，并补充有用途的结果图。</div><h3>读后文只需记住几个概念</h3><p><b>Guyan静力缩聚</b>用静态变形关系恢复被消去的坐标；<b>Craig–Bampton（CB）缩聚</b>再加入固定界面模态以保留内部动力作用。<b>自由度</b>是独立运动坐标，<b>阶数</b>是模型独立坐标的数量。</p><p><b>NRMSE</b>是位移误差均方根除以完整模型全记录峰峰值；表4只针对首层。<b>MAC</b>比较振型在指定坐标上的相似性，本文坐标含米和弧度。<b>模态份额指标ΔE</b>相加的是各作动坐标各自的相对变化，带符号且分母不同。<b>LQR</b>是根据数值位移和速度产生反馈力的线性二次调节器。</p><p>正文划分I的两个作动位置为首层和中层；划分II为首层和顶层，中层水平坐标ψ6由缩聚模型恢复。报告中的“原稿”固定指上一版修订前的冻结原稿，避免把上一版不满意的改动当作本轮基准。</p></section>
<section class="panel" id="reviews"><h2>审稿意见如何处理</h2><p>按照“判断是否正确 → 是否必要 → 现有材料能否验证”的顺序逐条裁决。补充计算与未完成事项在同一行说明，避免只列成功项。</p><div class="table-wrap"><table><thead><tr><th style="width:20%">意见与问题</th><th style="width:16%">本轮判断</th><th style="width:37%">做了什么及依据</th><th>仍需区分的范围</th></tr></thead><tbody>'''+reviewhtml+'''</tbody></table></div><h3>其余六项集中意见</h3><div class="table-wrap"><table><thead><tr><th>问题</th><th>处理</th></tr></thead><tbody>'''+minorhtml+'''</tbody></table></div><p>审稿意见中关于保留完整荷载投影、虚拟试件模态状态、数值表示惯性及固定两通道比较目标的肯定意见予以保留。没有新增测量模态坐标方案、普遍稳定性证明或同阶比较要求。</p></section>
<section id="changes"><div class="panel"><h2>逐项修改：先数据与内容</h2><p>每项先用中文说明变化，再提供未截断的原文与当前新版对照。表3至表5的30个变化单元另有逐格决定。已有段落中的未改文字保留在对照中，新增图以“原稿无此内容”显示。</p><p id="progress"></p><p id="search-count" class="small"></p><p id="status" role="status" aria-live="polite">决定仅记录在浏览器；不会修改论文文件。</p><p class="small no-print"><label><input id="full-print" type="checkbox"> 打印时附上完整英文和公式源码对照（默认打印中文说明、逐格数据和全部图件）</label></p></div><p id="empty" class="empty">没有匹配的修改，请清空搜索或切换类型。</p>'''+maincards+'''</section>
<section class="panel" id="figures"><h2>15幅图：每幅回答什么问题</h2><p>新增图5、6、9、12、13、15均由真实输入、完整响应或随包矩阵计算得到。图1至图4提供原图与新版的内嵌对照。数值曲线沿用原图配色：完整模型灰色、Guyan蓝色、Craig–Bampton红色；新增和修改的图注在正文标红。</p>'''+''.join(figurehtml)+'''<p>新增图件分别补足输入、模态、关键消去坐标、相邻楼层相对变形与份额分布信息。它们服务于不同的论证环节；历史稳定域的独立动力验证仍单独列为未完成事项。</p></section>
<section class="panel" id="evidence"><h2>验证结果与文件入口</h2><div class="table-wrap"><table><thead><tr><th>检查对象</th><th>实际结果</th><th>证明范围</th></tr></thead><tbody><tr><td>当前四套全链响应与三张结果表</td><td>44项表值一致；只对30个不符格标红修正。</td><td>当前15/6/9和15/5/8模型的表值与图数据一致。</td></tr><tr><td>新增频率、振型派生值、重构误差、层间位移角、模态份额</td><td>与三表一起共232项；MATLAB/Python最大差2.448×10⁻¹²。</td><td>验证真实数据到新图和文字数字的计算，未重新运行一个不同的RTHS闭环。</td></tr><tr><td>独立论文编译</td><td>新空目录复制必要文件，pdfLaTeX → BibTeX → pdfLaTeX两次；38页文字与生产稿逐页相同。</td><td>无Error、未定义引用/文献、??；15个图注均存在。</td></tr><tr><td>修改完整性</td><td>62项主稿操作可正向恢复最终稿、反向恢复冻结原稿，覆盖56个实际TeX差异块；2项文献删除单独核对。</td><td>全部正文差异均有记录；格式操作在报告末尾。</td></tr><tr><td>源文件保护</td><td>94个原稿、上一版及冻结来源文件SHA-256一致。</td><td>已有稿件和数据未被本轮覆盖。</td></tr><tr><td>负间距及图件</td><td>42条负间距的内容、顺序和有效状态一致；15幅PDF均为矢量且无Type3字体。</td><td>用户要求已保持；不代表继承的重叠问题已消除。</td></tr><tr><td>逐页视觉检查</td><td>38页已全部渲染查看；15幅图及5张表均在正文内，图件未裁切。</td><td>保留原负间距导致的公式紧贴/重叠；两条Underfull和原模板Overfull警告记录在案。</td></tr></tbody></table></div>
<h3>独立版本的目录</h3><div class="filelist"><p><code>main.tex / main.pdf</code>：可编辑红字稿及38页PDF。</p><p><code>submit_figure/</code>：正文使用的图件及新增图的PNG预览、可编辑TikZ示意图。</p><p><code>supplementary_data/</code>：两种划分的M/C/K/T、四套真实三层时程、地震输入等。</p><p><code>revision_evidence/baseline/</code>：本轮冻结原稿及原文献库；旧图资料归档于此。</p><p><code>revision_evidence/data/</code>：三表44格清单、新图数值CSV、指标和MATLAB验证结果。</p><p><code>revision_evidence/code/</code>：图件生成与验证脚本；<code>revision_evidence/validation/</code>：编译、数值、视觉和HTML验收记录。</p><p><code>change_operations.json / raw_hunks.json / main_changes.diff</code>：位于证据目录，分别保存64项操作、最终差异块和完整文本差异。</p><p><code>文件清单_SHA256.csv</code>：用于检查交付文件完整性；<code>阅读与编译说明.md</code>：打开、编译和再出图的方法。</p></div><p class="small hash">本报告对应main.tex：'''+validation['main_sha256']+'''</p><p class="small hash">本报告对应main.pdf：'''+validation['pdf_sha256']+'''</p>'''+rawhtml+'''</section>
<section class="panel" id="decision-help"><h2>如何保留或回退</h2><p>您可以先审阅数值，再集中判断模型口径、力反馈解释和结论措辞。报告保存的是逐项决定，论文文件不会随选择自动变化。选择完成后点击“导出决定”，得到带有本版正文校验值的JSON；移动报告到其他位置或换浏览器时可导入继续审阅。</p><ol><li><b>数值纠正：</b>表3至表5及弹性模量均有计算依据。若认可当前数据来源，建议保留改值；文字风格可以单独调整。</li><li><b>模型口径：</b>重点看“准确性模型：明确整体缩聚的实际阶数及Guyan实现”和“稳定域：精确单位、参考模型及计算来源”。它们处理实际程序与原文不同的问题。</li><li><b>新增图片：</b>可逐幅判断价值。如撤回中层图，需要同时调整对应摘要、结论和审稿答复；其他图可结合图号自动更新独立移除。</li><li><b>后续科学验证：</b>若希望恢复论文中统一模型的完整论证，需要重建双侧部分界面模型、核实未匹配坐标载荷与控制器，再重算稳定域和边界内外时程。该工作尚未执行，应单独确定计算路线。</li></ol><p>本轮给出的下一步是集中审阅这份修订稿。用户确认、专家接受和后续计算完成属于后续状态，均未以本轮技术检查通过替代。</p></section>
<section id="formatting"><div class="panel"><h2>最后：格式与文献整理</h2><p>下列操作只处理引用重复、图件浮动及尺寸。42处原负间距未删除、未注释、未改值，也未通过相反方向的间距命令抵消。格式改动不能解决已保留的公式重叠，因此报告将其列为已知版面限制。</p></div>'''+formatcards+'''</section><footer>独立第二版 · 冻结原稿与上一版保留 · 本文件的文字、样式、脚本和20张理解所需图片均内嵌，可移动后离线阅读。报告中的决定不会自动写入论文。</footer></main><script type="application/json" id="report-meta">'''+json.dumps(meta,ensure_ascii=False).replace('</',r'<\/')+'''</script><script>'''+script+'''</script></body></html>'''
REPORT.write_text(text,encoding='utf-8')
(EV/'report_manifest.json').write_text(json.dumps({'report':REPORT.name,**meta,'bytes':REPORT.stat().st_size},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report':str(REPORT),'operations':64,'decisions':len(decisions),'embedded_images':imagecount,'bytes':REPORT.stat().st_size},ensure_ascii=False))
