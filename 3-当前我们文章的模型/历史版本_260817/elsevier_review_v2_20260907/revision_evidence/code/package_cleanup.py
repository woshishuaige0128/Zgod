from pathlib import Path
import json,shutil,hashlib,csv
TMP=Path(__file__).resolve().parent;ROOT=TMP.parents[1]
NEW=(ROOT.parent/'260817/elsevier_review_v2_20260907').resolve();EV=NEW/'revision_evidence'
def safe_move(src,dst):
    assert src.resolve().is_relative_to(NEW) and dst.resolve().is_relative_to(NEW),(src,dst)
    assert not dst.exists(),dst
    dst.parent.mkdir(parents=True,exist_ok=True);src.rename(dst)
for p in sorted((NEW/'submit_figure').glob('*option*.png')):
    safe_move(p,EV/'baseline/submit_figure'/p.name)
for ext in ['abs','aux','blg','log','out']:
    p=NEW/f'main.{ext}'
    if p.exists():safe_move(p,EV/'validation/production_compile'/p.name)
for name in ['verify_new_metrics.m','validate_package.py','check_portable_figures.py','build_report.py','qa_report.cjs']:
    shutil.copy2(TMP/name,EV/'code'/name)
readme=r'''# RHTS独立第二版：阅读与编译说明

Doctor Bego，本文件夹保存本轮可编辑修订稿、38页红字PDF、15幅编号图，以及逐项修改报告。原稿和上一版未覆盖。

## 先打开什么

1. `RHTS第二版全文修改逐项对照与回退决策汇报.html`：本次主报告，包含64项修改、表3至表5的30个单元格对照、全部15幅图及前四幅示意图的原图对照。可离线移动、搜索、筛选、逐项决定，并导入/导出审阅JSON。
2. `main.pdf`：38页红字论文。42处原负间距已完整保留；原有部分公式与下方文字重叠仍存在。
3. `main.tex`：可编辑英文主稿。`references.bib`为文献库，`main.bbl`为已经生成的参考文献正文。

## 文件结构

- 根目录：主稿、PDF、主报告和CAS编译模板依赖。
- `submit_figure/`：正文实际使用的15个矢量PDF、10个新增/重绘图的600 dpi PNG及4个可编辑TikZ源。
- `supplementary_data/`：完整与缩聚矩阵、四套三层位移CSV、地震输入及已有补充表。
- `revision_evidence/baseline/`：冻结原稿、原文献库和未在新版正文使用的旧图。
- `revision_evidence/data/`：三表44项原值/新值/复算值、新增图CSV、图件来源哈希和跨语言数值核对。
- `revision_evidence/code/`：图件生成脚本，以及改稿/验收过程档案。
- `revision_evidence/validation/`：技术检查、编译、独立再出图、正文视觉、HTML浏览器及最终交付验收结果。
- `文件清单_SHA256.csv`：交付文件哈希清单（清单自身不包含在内）。

全部临时计算、独立构建副本、浏览器截图和打印测试在原工作区的 `tmp/revision_v2_20260907/` 中，未进入论文根目录。

## 编译论文

在本文件夹执行：

```powershell
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

本轮实际使用TeX Live 2026按上述顺序编译，并复制必要文件到新空目录再编译；两份38页PDF逐页文字相同。无Error、未定义引用/文献或`??`。保留模板原有一条Overfull提示及两条Underfull提示，具体见编译日志。重新编译将自然生成aux/log等中间文件。

## 再生成新增图件

两个绘图入口已经在独立副本实际运行。请先复制本文件夹，再在副本中执行（将覆盖该副本的相应图件）：

```powershell
$env:PYTHONIOENCODING = "utf-8"
& 'D:/Software/python/python.exe' -X utf8 'revision_evidence/code/make_figures.py'
& 'D:/Software/python/python.exe' -X utf8 'revision_evidence/code/make_diagrams.py'
```

运行环境需要Python、NumPy、SciPy、Matplotlib、Pillow、PyMuPDF及可调用的pdfLaTeX。数据从本包读取；10幅再生成图在120 dpi渲染下与交付图逐像素相同，8个派生CSV逐字节相同。其余验收/改稿脚本为本轮过程档案，包含当时的工作区路径，不应作为任意位置的一键改稿入口。

## 数值和科学范围

表3至表5共44项均核对：30格需纠正、14格原相符；表1另更正梁柱弹性模量。新增图指标与表值一起共232项经MATLAB/Python独立对照，最大绝对差2.4478197246935451e-12。

当前精度证据为15自由度整体缩聚：Guyan/CB在两种划分分别为6/9阶和5/8阶。原文局部子结构配置为6/12阶。原稳定域对应的完整闭环矩阵、实际控制增益、双侧界面位移差及边界内外扰动时程尚未闭合；本轮没有用新增响应图替代这些科学验证。

## 如何回退

报告中的选择只保存审阅意见，不自动修改文件。先导出决定，再据具体条目修改主稿。`revision_evidence/change_operations.json`保存64项操作；`raw_hunks.json`及`main_changes.diff`保存最终TeX差异。恢复旧数值时需要同时检查关联图表和文字，不能只回退一个结论数字。
'''
(NEW/'阅读与编译说明.md').write_text(readme,encoding='utf-8')
print('Package arranged; no protected originals were moved or changed.')
