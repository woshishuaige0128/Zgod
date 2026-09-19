# 子任务 1 验收：来源冻结与允许变更合同

验收日期：2026-09-03（Asia/Shanghai）

## 结论

PASS。新版 50 篇来源、历史 CAS 文件、模板和十个使用图片已冻结；引用集合闭合；所有待清理命令和唯一缺图路径均已定位。没有修改用户提供的 TeX、PDF、BibTeX，也没有覆盖 manuscript 中的历史 main.tex、reference.bib 或 main.pdf。

## 实际验证命令

PowerShell 中设置 PYTHONIOENCODING=utf-8 后运行：

    D:\Software\python\python.exe verification_50refs\verify_frozen_sources.py

退出码：0。

实际输出：

    PASS | frozen files: 19
    PASS | citation commands: 60
    PASS | unique citation keys: 50
    PASS | BibTeX entries: 50
    PASS | missing citation keys: 0
    PASS | uncited BibTeX entries: 0
    PASS | rev/citedoi/newcitedoi/newcommand: 45/25/35/6
    PASS | expected missing figure path: figure/selected_v2/fig02_rths_loop_optionC.png

## 文字基线判断

新版 temp_50refs_red_revision.tex 不是历史稿的“只加引用版”。它包含完整摘要，并在 Introduction、Sections 2--5 和 Conclusions 中均有文字或结构变化。后续只能把新版六章整体作为文字基线，不能把新增引用机械移植到历史 main.tex。

所有 rev 参数内部文字均属于新版基线。清稿时删除 rev 外壳而不是删除其内容；两类带 DOI 的引用保留第一个引用键并改为普通 cite。

## 图片问题

新版 TeX 有十处图片调用。第一处写入了不存在的 figure/selected_v2/fig02_rths_loop_optionC.png，因此用户提供的 PDF 显示缺图占位框。其实际可用且已冻结的对应图片是 manuscript/submit_figure/fig01_rths_loop_optionD.png。其余九处可映射到 manuscript/submit_figure 中的哈希一致文件。

## BibTeX 风险

- 50 条记录、50 个唯一 DOI 均可解析，无重复键、重复 DOI 或重复标题。
- 50 个 DOI 均由 Crossref 返回实际文献，未发现整条虚构记录。
- Mahin1989、Chae2013、MacNeal1971 存在明确作者名错误。
- Spencer Jr.、Craig Jr.、Condori Uribe、Gutierrez Soto 需要使用 BibTeX 可正确解析的姓氏格式。
- 18 条 Earthquake Engineering and Structural Dynamics 和 1 条 Computers and Structures 应恢复正式期刊名中的 \&。
- Mucha2023 相比旧核验库缺少 number={7}。
- 50 条 note={DOI \nolinkurl{...}} 会强制显示 DOI；最终投稿副本按用户要求移除 note 和 doi，原始扩充库保持不变。

出版社核验入口：

- ASCE，Mahin1989：https://ascelibrary.org/doi/abs/10.1061/%28asce%290733-9445%281989%29115%3A8%282113%29
- Wiley，Chae2013：https://onlinelibrary.wiley.com/toc/10969845/2013/42/11
- Elsevier，MacNeal1971：https://www.sciencedirect.com/science/article/pii/0045794971900319
- Frontiers，Condori2023：https://doi.org/10.3389/fbuil.2023.1270996
