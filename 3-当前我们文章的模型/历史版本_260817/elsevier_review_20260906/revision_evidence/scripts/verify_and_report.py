from pathlib import Path
import re, json, hashlib, difflib, csv, shutil
import fitz
from PIL import Image, ImageDraw
ROOT=Path(r'D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master')
OUT=ROOT.parent/'260817/elsevier_review_20260906'
SRC=OUT.parent/'elsevier'
HERE=Path(__file__).resolve().parent
s=(OUT/'main.tex').read_text(encoding='utf-8')
orig=(SRC/'main.tex').read_text(encoding='utf-8')
rows=json.loads((OUT/'revision_evidence/table345_verified_values.json').read_text(encoding='utf-8'))['rows']
checks=[]
def ck(name,result,detail=None):
    checks.append({'check':name,'pass':bool(result),'detail':detail})
    assert result,(name,detail)
for label,table in [('tab:modal',3),('tab:nrmse',4),('tab:energy',5)]:
    a=s.index(r'\label{'+label+'}');b=s.index(r'\end{table}',a)
    lines=[line for line in s[a:b].splitlines() if re.search(r'^\s*(I\s|II\s|El Centro|Chirp,)',line)]
    expected=[r for r in rows if r['table']==table]; k=0
    for line in lines:
        cells=line.split('&')[(2 if table==3 else 1):]
        for cell in cells:
            r=expected[k];k+=1
            v=re.sub(r'\\rev\{([^{}]+)\}',r'\1',cell).replace(r'\\','').replace('$<$','<').strip()
            ck(f'table{table}_cell{r["id"]}',v==r['rounded_value'],{'expected':r['rounded_value'],'actual':v})
            ck(f'red_marker_cell{r["id"]}',(r'\rev{' in cell)==(r['status']=='不符'))
    ck(f'table{table}_count',k==len(expected))
for old in ['0.834','0.06\\%','24.575','19.059','13.040','0.3065','0.1879','0.3927','0.2021','at twelve','against twelve','at six generalized coordinates against twelve','rise to nearly twice','upper bound']:
    ck('old_claim_absent:'+old,old not in s)
for label in ['tab:materials','tab:dof-sets','tab:modal','tab:nrmse','tab:energy']:
    ck('unique_table:'+label,s.count(r'\label{'+label+'}')==1)
log=(OUT/'main.log').read_text(encoding='utf-8',errors='replace')
ck('compile_no_errors_or_unresolved',not re.search(r'^!|undefined|Rerun to get|Citation .* undefined|LaTeX Warning',log,re.M))
overflows=re.findall(r'Overfull.*',log)
ck('only_inherited_keyword_box_warning',len(overflows)==1 and '117.0831pt' in overflows[0],overflows)
source_hashes=json.loads((OUT/'revision_evidence/source_hashes.json').read_text(encoding='utf-8'))
ck('source_inventory_unchanged',set(source_hashes)=={str(p.relative_to(SRC)) for p in SRC.rglob('*') if p.is_file()})
for name,sha in source_hashes.items():ck('source_hash:'+name,hashlib.sha256((SRC/name).read_bytes()).hexdigest()==sha)
ck('bibliography_41_entries',len(re.findall(r'(?m)^@\w+\{',(OUT/'references.bib').read_text(encoding='utf-8')))==41)
ck('bibliography_no_duplicates',all(x not in (OUT/'references.bib').read_text(encoding='utf-8') for x in ['CraigBampton1968,','ChenRicles2008b,']))

doc=fitz.open(OUT/'main.pdf');text='\n'.join(p.get_text() for p in doc)
ck('pdf_no_question_mark_placeholders','??' not in text)
ck('pdf_tables_present',all(f'Table {i}' in text for i in range(1,6)))
ck('pdf_english_figures',not re.search('[\u4e00-\u9fff]',text))
spans=[sp for p in doc for block in p.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for sp in line['spans']]
redspans=[sp for sp in spans if sp['color']==0xFF0000]
ck('red_abstract_rendered',any('Limited' in sp['text'] and sp['color']==0xFF0000 for b in doc[0].get_text('dict')['blocks'] if 'lines' in b for ln in b['lines'] for sp in ln['spans']))
for val in ['19.040','30.574','0.138','26.858','-0.0414','0.8914']:
    ck('red_pdf_value:'+val,any(val in sp['text'] for sp in redspans))
for n in range(1,len(doc)+1):ck(f'rendered_page_{n}',(HERE/f'final-page-{n:02}.png').exists())

for start in range(1,len(doc)+1,6):
    sheet=Image.new('RGB',(1800,1680),'#cccccc');draw=ImageDraw.Draw(sheet)
    for j,i in enumerate(range(start,min(start+6,len(doc)+1))):
        im=Image.open(HERE/f'final-page-{i:02}.png').convert('RGB');im.thumbnail((590,800))
        x=j%3*600+(600-im.width)//2;y=j//3*840+30
        sheet.paste(im,(x,y));draw.text((j%3*600+15,j//3*840+8),f'PAGE {i}',fill='black')
    sheet.save(HERE/f'final-contact-{start:02}.jpg')

(OUT/'revision_evidence/main.diff').write_text(''.join(difflib.unified_diff(orig.splitlines(True),s.splitlines(True),fromfile='protected_original/main.tex',tofile='revision/main.tex')),encoding='utf-8')
(OUT/'revision_evidence/validation.json').write_text(json.dumps({'pass_count':len(checks),'source_files':len(source_hashes),'pdf_pages':len(doc),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# 本轮修改说明

已完成当前出图口径下的表3、表4、表5及全文相关修订，新增和替换内容用红色标出；删除内容见 `revision_evidence/main.diff`。原始 `elsevier` 目录的 {len(source_hashes)} 个文件前后 SHA-256 全部一致。

这份稿件可用于逐处讨论修改。它尚不能作为科学问题全部闭合的投稿稿：当前响应图采用整体缩聚，稳定域图的历史生成参数尚未恢复，二者不能通过改写文字视为同一条计算链。

## 直接打开

- `main.pdf`：{len(doc)}页红色修订稿。
- `main.tex`：可继续编辑的主文件；在本目录运行 pdfLaTeX → BibTeX → pdfLaTeX 两遍。
- `supplementary_data`：本次精度模型的完整15自由度质量、阻尼、刚度矩阵及两类缩聚矩阵。
- `revision_evidence/table345_verified_values.json`：44项数值及来源；`validation.json`：自动验收。

## 数值与正文的必要修正

| 内容 | 原稿 | 本轮修订 |
|---|---|---|
| 表3 | 第二类划分Guyan频率误差13.040%、24.575% | 19.040%、30.574%；Craig–Bampton两类最大频率误差0.284% |
| 表4 | Craig–Bampton全部小于0.06%；Guyan最大19.059% | Craig–Bampton最大0.138%；Guyan最大26.858% |
| 表5 | 四个均为正值且可按大小排序稳定性 | 第一类Guyan −0.0414、Craig–Bampton 0.0039；第二类0.8914、0.0365。保留有符号原指标，删除0.3阈值和原稳定性排序 |
| 响应分析 | 首个峰值约13s；末段第三层接近参考两倍 | 参考绝对峰值约11.69s；38–38.3s第三层Guyan极差为参考的80.51% |
| 精度模型 | 两子结构分别缩聚装配，均为6/12自由度 | 整体15自由度缩聚，第一类6/9、第二类5/8；实际Guyan为保留方程的单侧实现，Craig–Bampton为双侧投影 |

三表44格中30格需要更改，其余14格保持原值。表3、4、5分别更改5、21、4格。正文中的摘要、模型设置、评价方法、结果和结论同步更新。

## 审稿意见逐条裁决

| 审稿意见 | 处理 | 理由与完成边界 |
|---|---|---|
| 1. 图表和扫频叙述不一致 | 已采纳 | 统一当前图的数据、频段端点和全记录极差归一化；修正三表和所有相关数值，纠正峰值时间及末段幅值判断 |
| 2. 部分界面装配与Ritz推论 | 采纳必要定义与推论修正，计算验证未闭合 | 给出子结构装配映射及释放界面零相互作用力这一方法定义；删除“缩聚频率必然高于完整模型”的泛化。当前精度结果是整体缩聚，不能用来验证部分界面装配 |
| 3. 模态扩展和能量解释 | 已采纳保留原指标方案 | 明确全局变换、坐标还原、以完整质量矩阵重新归一化、各模型前5阶及各自参与权重；称有符号模态份额指标，删除能量转移量和延迟暴露程度的直接等同 |
| 4. LQR闭环不统一 | 公式对应的图文已修正，历史闭环尚未验证 | 保留现有式(3.5)/(3.6)代表的延迟力反馈，明确输入为数值位移/速度、输出为广义力及其求和位置；重画图1。未将其声称为历史稳定域图的已验证生成闭环。精度计算明确关闭LQR |
| 5. 模态坐标无直接时滞的推论过强 | 已采纳 | 改为模态坐标与延迟保留坐标动态耦合；两种方法都有两条时滞通道。删除稳定域数学上界及单凭模态坐标便保证优势的论断 |
| 6. 未作动中层响应缺失 | 部分采纳 | 从既有全记录恢复数据增加中层位移NRMSE：地震10.798%/0.031%，扫频11.749%/0.034%（Guyan/Craig–Bampton）。当前整体模型只有一个恢复值，无法构造两个子结构之间的位移差，未编造该结果 |
| 7. 参数不足 | 精度模型参数已补，稳定模型仍缺 | 按代码补E=206GPa、截面A/I、集中质量及转动惯量、190倍有效质量密度、底部全固定、Rayleigh系数、激励公式/单位/插值及RK4步长；附精度矩阵。新的线性模型叙述不再声称已检验所有杆件未屈服 |
| 8. 同增益比较与模态阶数扫描 | 未新增算例 | 保留各模型及其配套调节器的比较语义。共同增益和阶数扫描属于增强研究；在历史闭环未闭合时新增这些扫描不能解决当前来源问题 |
| 9. 稳定边界内外时程验证 | 本轮未实施 | 缺少与历史曲线一致的模型及增益，不能把另一条候选闭环的衰减/增长当成该图验证 |

## 集中处理的表达与版式

- 精确说明1个延迟步为0.9765625ms；图9原坐标已是换算后的毫秒，不重改曲线。
- 保留原MAC计算，在方法中明确平移以m、转角以rad且未额外缩放；未将换坐标后的MAC冒充原表值。
- 图1至图4改为英文矢量示意，取消中文旧图号。新结构示意采用当前精度代码中的全固定柱脚，图1只说明文中数学力反馈路径。
- 合并Craig–Bampton原始文献和CR积分文献的重复引用，43个条目减为41个独立条目。
- 移除导致公式与说明重叠的42处负间距。章节/图表编号由LaTeX自动更新，不属于新增科学内容。
- 关键证据限制集中写在分析设置中；没有把审稿问答、反例推导、Riccati教材推导或长篇免责声明搬入正文。

## 验收

- 44/44表格值与已独立核查结果一致；30处改动单元格全部有红色标记，14处未改值不重复标红。
- 已执行pdfLaTeX、BibTeX及两遍pdfLaTeX；无编译错误、无未定义引用/文献、无??。
- 原稿自带的CAS关键词零宽定位盒产生一条117.0831pt警告，修订前后相同，页面实际无越界；正文无新增Overfull/Underfull警告。
- {len(doc)}页均已渲染；最终逐页视觉复核另记于`revision_evidence/visual_qa.json`。
- Python数值检查共{len(checks)}项通过，源文件保护{len(source_hashes)}/{len(source_hashes)}通过。

当前边界：修改与排版交付已完成；部分界面装配与历史稳定域之间的科学闭合仍需独立计算工作。
'''
(OUT/'修改说明.md').write_text(report,encoding='utf-8')
print(json.dumps({'checks':len(checks),'sources':len(source_hashes),'pages':len(doc)},ensure_ascii=False))
