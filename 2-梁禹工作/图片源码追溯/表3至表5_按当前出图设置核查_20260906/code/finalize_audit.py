from pathlib import Path
import csv,hashlib,json
from html.parser import HTMLParser

OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    manifest=json.loads((OUT/'evidence/source_manifest.json').read_text(encoding='utf-8'))
    assert all(sha(Path(x['path']))==x['sha256'] for x in manifest)
    config=json.loads((OUT/'evidence/runtime_derivation.json').read_text(encoding='utf-8'))
    count=0
    for case in config:
        original=Path(case['source']);runtime=Path(case['runtime'])
        a=(original/case['entry']).read_text(encoding='utf-8-sig')
        b=(runtime/case['entry']).read_text(encoding='utf-8')
        assert b.startswith(a[:a.index('%% 8. 直接使用本轮')])
        assert b[b.index('%% 本文件以下为局部函数'):]==a[a.index('%% 本文件以下为局部函数'):]
        for p in (original/'输入模型与参数').rglob('*'):
            if p.is_file():
                q=runtime/'输入模型与参数'/p.relative_to(original/'输入模型与参数')
                assert sha(p)==sha(q);count+=1
    report=OUT/'表3至表5数值准确性核查汇报.html'
    text=report.read_text(encoding='utf-8')
    class Parser(HTMLParser):
        def __init__(self):super().__init__();self.ids=[];self.hrefs=[];self.resources=[]
        def handle_starttag(self,t,attrs):
            d=dict(attrs)
            if 'id' in d:self.ids.append(d['id'])
            if t=='a':self.hrefs.append(d.get('href',''))
            if t in ['script','img','link'] and ('src' in d or 'href' in d):self.resources.append(d)
    p=Parser();p.feed(text);assert not p.resources
    for link in p.hrefs:
        if link.startswith('#'):assert link[1:] in p.ids
        else:assert (OUT/link).exists(),link
    numeric=json.loads((OUT/'evidence/numerical_validation.json').read_text(encoding='utf-8'))
    browser=json.loads((OUT/'evidence/html_browser_qa.json').read_text(encoding='utf-8'))
    assert numeric['cross_language_metrics']==44 and numeric['computation_validation']=='PASS'
    assert all(not x.get('overflow',False) for x in browser)
    summary={'source_protection':f'{len(manifest)}/{len(manifest)} PASS','runtime_input_copies':f'{count}/{count} PASS',
             'original_calculation_sections_and_functions':'4/4 exact match','html_links':'PASS',
             'desktop_1440':'PASS','mobile_390':'PASS','offline_moved_single_file':'PASS',
             'visual_check':'PASS; top, Table 4, all six A4 pages; final contrast correction rechecked',
             'a4_print_pages':6,'html_sha256':sha(report),'table_agreement':numeric['table_agreement'],
             'status':'AUDIT_COMPLETE_MANUSCRIPT_NOT_MODIFIED'}
    (OUT/'evidence/final_acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    readme='''# 复算入口与证据

主汇报：本目录上一级的《表3至表5数值准确性核查汇报.html》。

本次核查从原入口第1--7节重新计算四套时程；原输入、计算段和局部函数保持字节内容一致。仅跳过出图和读取参考CSV的末端比较。临时计算的精确位置见 `evidence/runtime_derivation.json`。

复算顺序：
1. MATLAB执行 `tmp/table345_audit_20260906/temp/run_four_audit_cases.m`，会重新生成临时运行目录中的计算数据。
2. 用 `D:/Software/python/python.exe -X utf8` 运行 `code/compute_metrics.py`。
3. 在MATLAB将本目录 `code` 加入路径，运行 `compute_metrics_matlab`。
4. 用相同Python执行 `code/build_report.py`，比较两种实现并生成报告。
5. 用捆绑Node执行 `code/qa_report.cjs`，使用本机Chrome验证本地HTML并生成临时A4打印版；再执行 `code/finalize_audit.py`。

`prepare_audit.py` 仅用于建立首次来源冻结和隔离运行目录；如已有冻结清单会拒绝覆盖。没有必要重新运行它。

本报告的Python/MATLAB指标计算读取的是本轮重新生成的 `audit_snapshot.mat`。当前绘图CSV只用于新计算结束后的误差检查。原表数值仅用于最后的逐格判定，未参与模型、振型或响应计算。

原始图10生成模型不完整，本次表5以图6--9可执行模型套用现稿公式得到条件结果；这不等于证明它与图10历史稳定边界同模型。
'''
    (OUT/'README_复算与证据.md').write_text(readme,encoding='utf-8')
    w=ROOT/'WORKFLOW.md';s=w.read_text(encoding='utf-8')
    s=s.replace('- [ ] 板块29：完成当前main.tex三表44个数值的当前出图口径核查、复算和中文报告。',
                '- [x] 板块29：完成当前main.tex三表44个数值的当前出图口径核查、复算和中文报告。（完成于：2026-09-06；验证：四套仿真通过，时程最大差4.973799150320701e-14 mm，44项MATLAB/Python最大差2.490452288839151e-12；表3/4/5分别11/16、3/24、0/4格相符；72/72源文件不变，单文件HTML桌面/窄屏/离线/6页A4通过；核查完成不代表三表正确。）')
    details='''

### 板块29实际操作与验收记录（2026-09-06）
- 来源：用户指定 `260817/elsevier/main.tex`；由 `main.aux`确认表3/4/5标签。投稿图6--9四份PDF与 `figure/results_v2/PDF`逐字节相同，沿其输入CSV和当前全链演示入口定位模型。
- 隔离执行：运行 `figure/表3至表5_按当前出图设置核查_20260906/code/prepare_audit.py` 冻结72项输入；复制四个模型到 `tmp/table345_audit_20260906/temp`，保留原计算段1--7和全部局部函数原文，仅省去出图与读参考的末端环节。MATLAB `-batch` 执行 `run_four_audit_cases.m`，四套均 `AUDIT_FRESH_SIMULATION=PASS`；总入口退出码0。
- 数值验收：四份40961×10时程，0--40 s、dt=1/1024，与当前实际绘图CSV最大绝对差均为4.973799150320701e-14 mm，小于1e-12门限。`compute_metrics.py`和`compute_metrics_matlab.m`独立复算44项，最大差2.490452288839151e-12，小于1e-8门限。按原表精度相符数为表3 11/16、表4 3/24、表5 0/4。表4三种频段边界×两种积分/样本统计方式均保持3/24格相符。
- 主要结果：第二类Guyan两阶频率误差19.040%/30.574%；表4最大NRMSE26.858%，Craig--Bampton第一类最高频段0.138%；表5按现稿前5阶/完整坐标恢复公式为第一类Guyan -0.0414、Craig--Bampton0.0039，第二类0.8914/0.0365。表5仅验证当前可执行响应模型，未证明其与图10历史边界模型一致。
- 一致性发现：正文两类6/12自由度与当前出图6/9和5/8不一致；正文子结构分别双侧投影与当前整体缩聚/历史Guyan单侧质量阻尼路线不一致。与这些模型和表格相关的摘要、结果及结论标为待复核；本轮没有修改论文或改变模型。
- 报告：`figure/表3至表5_按当前出图设置核查_20260906/表3至表5数值准确性核查汇报.html`，另有逐格CSV、Markdown简表、代码和证据。Chrome实际验证1440/390像素无整页横向溢出、宽表容器滚动、目录/折叠可用，单文件移动后离线可读；A4打印6页经Poppler渲染查看。初次发现页头代码文字对比度低，已修正颜色并重新检查。首次QA缺少bs4时改用标准库HTMLParser；Playwright捆绑浏览器不存在时使用已安装Chrome，未安装新依赖。
- 源与交付保护：72/72冻结源哈希不变，24/24复制输入哈希一致，4/4原计算段和函数原文一致。日志保留未连接备用激励块等警告，未声称无警告。最终验收见 `evidence/final_acceptance.json`。图10参数研究的旧现场快照保存在本次 `evidence/before_current.md`，本轮未推进其他研究。
'''
    if '### 板块29实际操作与验收记录（2026-09-06）' not in s:s+=details
    w.write_text(s,encoding='utf-8')
    notice='<!-- 【在工作前，需要首先启动paper-writing skill，这一行不要删除！！】 -->\n'
    current=notice+'''# Current - 工作现场快照

## 当前所在 WORKFLOW 板块
本次表3、表4、表5核查已经完成；详细结果已同步WORKFLOW.md。无正在执行的新板块。

## 当前正在执行的具体操作
无；等待用户根据核查报告决定后续改稿或模型统一。

## 上一步操作的结果
三表44项已复算与交叉验证：相符数11/16、3/24、0/4。独立HTML及数据明细已验收，原稿未修改。

## 下一步计划
本轮停止。只有用户指定后才开展论文修改或恢复其他研究任务。

## 关键上下文
主汇报：figure/表3至表5_按当前出图设置核查_20260906/表3至表5数值准确性核查汇报.html。
待复核：正文模型6/12自由度与当前图6/9、5/8不一致；表5与图10生成模型来源尚未闭合。
此前图10参数研究的完整现场位于本次交付 evidence/before_current.md，原计算资产未改动。

## 遇到的问题/阻塞点
本次核查无未完成项。论文表格和相关结论尚未修正，模型取舍尚待用户决定。
'''
    (ROOT/'current.md').write_text(current,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
