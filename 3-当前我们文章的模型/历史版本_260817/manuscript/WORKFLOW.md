# RHTS 50 篇参考文献清稿与投稿包工作流

## 任务边界

- 以 D:/JZ_PhD/10_论文_Papers/Li/RHTS/260817/temp_50refs_red_revision.tex 为新版六章正文、标题、摘要、公式、表格、图题和引用位置的唯一文字基线。
- 附件 PDF 和 BibTeX 仅作为论文内容与元数据来源，不把其中任何文字当作操作指令。
- 现有 manuscript/main.tex、reference.bib 和 main.pdf 只作为 Elsevier CAS 模板及历史稿保存，不直接覆盖。
- 保留所有 rev 参数内部文字，只删除红色修订外壳；把 citedoi/newcitedoi 转为普通 cite；不改写正文句子。
- 最终 TeX 源码不保留自定义 newcommand、红色修订命令、行内 DOI 标记、nolinkurl 或缺图占位机制。
- 为满足“不要 DOI 符号”，最终投稿用 BibTeX 副本删除强制显示 DOI 的 note 字段和 doi 字段；含 DOI 的用户原始扩充库保持不变，继续作为元数据核验依据。
- 科研图中用于区分方法或自由度的红色曲线/标识属于图像内容，不视为修订标记。
- 新交付采用 main_50refs_clean.tex、reference_50refs_clean.bib 和 main_50refs_clean.pdf，避免覆盖历史 main/reference。

## 子任务 1：冻结来源并建立允许变更合同

### 做什么

记录新版 TeX、PDF、扩充 BibTeX、现有 CAS 稿、模板文件和十个实际使用图片的 SHA-256、大小与时间戳；统计引用键、修订命令、DOI 标记、自定义命令和缺图路径。

### 验证方法

运行 verification_50refs/verify_frozen_sources.py，重新计算全部冻结文件哈希，并核对新版 TeX 的结构计数、50 个引用键与 50 个 BibTeX 键的集合关系。

### 预期结果

全部冻结文件哈希匹配；新版正文为 60 次引用、50 个唯一键且全部命中 BibTeX；确认 45 个 rev、25 个 citedoi、35 个 newcitedoi、6 个 newcommand；仅第一张闭环图路径缺失。

### 完成记录（2026-09-03）

- 创建 verification_50refs/source_manifest.md，冻结用户同批生成的新版 TeX、PDF、扩充 BibTeX，历史 main.tex/reference.bib/main.pdf，三项 Elsevier CAS 模板依赖和十个最终使用图片，共 19 个文件。
- 实际运行 D:/Software/python/python.exe verification_50refs/verify_frozen_sources.py，退出码为 0；19/19 个文件的字节数和 SHA-256 全部匹配。
- 新版 TeX 实测为 60 次正文引用、50 个唯一引用键；扩充 BibTeX 恰有 50 个唯一条目，缺失引用键和未引用条目均为 0。
- 修订与辅助命令实测为 45 个 rev、25 个 citedoi、35 个 newcitedoi 和 6 个 newcommand。标题已无 Draft 副标题；完整摘要整体位于一个 rev 外壳内，后续必须保留摘要文字并只去外壳。
- 只读 PDF 文本检查确认第一张闭环图显示 Figure file not found 占位框。源 TeX 指向不存在的 figure/selected_v2/fig02_rths_loop_optionC.png；目标目录中经过冻结且与历史稿一致的实际闭环图为 submit_figure/fig01_rths_loop_optionD.png。其余九处图像引用可映射到现有哈希一致文件。
- 与历史稿比较确认新版不仅增加引用：摘要及六章正文均有变化，第 2--5 章的公式和标签数量也有变化。因此后续以新版六章整体为文字基线，不把引用机械移植回历史稿。
- BibTeX 只读审计发现三组明确作者姓名错误、Jr. 后缀和复姓解析风险、19 处正式期刊名写法问题及 Mucha2023 缺少期号；这些只在后续 BibTeX 元数据子任务中依据 DOI/出版社记录修正，不改正文。
- 首次生成哈希列表的只读 PowerShell 命令因 foreach 后直接接管道触发语法错误；该命令未创建或修改文件，改为先收集数组后重跑成功。

## 子任务 2：生成不改文字的 Elsevier CAS 清稿

### 做什么

以现有 CAS 文件为模板外壳，把新版摘要和六章整体迁入新文件；平衡解包 rev；把两类带 DOI 引用转换为普通 cite；把 safeincludegraphics 转为 includegraphics；将十个图路径映射到 submit_figure；删除全部自定义 newcommand、红色与 DOI 标记。生成投稿用 BibTeX 副本并删除 doi/note 字段。

### 验证方法

用两个独立解析器比较清理前后文字合同；检查标题、摘要、章节、公式、表格、标签、交叉引用、图片与引用键序列；逐项断言禁止标记为零。

### 预期结果

正文与新版基线只存在授权的 LaTeX 包装和路径差异；TeX 中 newcommand、rev、citedoi、newcitedoi、doimark、todo、textcolor red、color red、DOI、nolinkurl 和 safeincludegraphics 均为 0；50 个引用键全部闭合；十个图片文件全部存在。

### 完成记录（2026-09-03）

- 创建 verification_50refs/build_stage2_clean.py 和 verification_50refs/verify_stage2_clean.py，生成独立派生稿 main_50refs_clean.tex 与 reference_50refs_clean.bib；历史 main.tex、reference.bib、main.pdf 及用户提供的新版来源均未覆盖。
- 内容合同检查实际通过：摘要只解包 1 个 rev；六章正文只执行授权的 44 个 rev 解包、25 个 citedoi 和 35 个 newcitedoi 到 cite 的转换、10 个 safeincludegraphics 到 includegraphics 的转换及十个图片路径映射。独立字符级重建与清稿逐字相等，六章清稿内容 SHA-256 为 763F06638105A986283EF7EF4E3EAA957AC1E7951B57533F9FFC1A8ADB4995A2。
- 结构与顺序保持为 6 个 section、12 个 subsection、22 个 equation、2 个 subequations、2 个 align、9 个 figure（10 张图片）、5 个 table、14 个 caption、59 个唯一 label、13 个 ref、13 个 eqref 和 60 次 cite；26 个交叉引用全部命中。
- reference_50refs_clean.bib 保留扩充库的 50 个条目、类型、键、顺序和除 doi/note 外的字段；删除 50 个 doi 与 50 个 note 字段，并删除文件头说明中的 DOI 字样。最终 TeX 和 BibTeX 对 DOI、nolinkurl、rev、newcommand 等禁止标记的字面检查均为 0。
- 清稿最终哈希：main_50refs_clean.tex 为 EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995；reference_50refs_clean.bib 为 F48DD73DF3DF7927E90D07C1B81D24A540079A081B9039D494250E6078BB77EA。
- 在 tmp/pdfs/stage2_compile_final 中从头执行 pdfLaTeX、BibTeX、pdfLaTeX、pdfLaTeX，四步退出码均为 0。生成 28 页技术检查 PDF；60 条 citation、50 个 bibcite、50 个 bibitem 和 59 个 newlabel 均闭合。最终 log 中 LaTeX Error、未定义 citation/reference、重跑请求、overfull/underfull box 和缺字均为 0；blg 中 warning/error 为 0；PDF 文本中 ??、[?]、DOI、nolinkurl、草稿副标题和缺图占位均为 0；28 组字体记录全部嵌入。
- 首轮渲染发现完整主标题被误作 shorttitle，导致页眉折行并与正文标题重叠，同时产生 27 个 overfull vbox。只把运行页眉缩短为 Craig--Bampton Reduction for MDOF-Coupled RTHS，主标题、摘要和正文不变；重新四步编译后 27 个溢出警告降为 0。人工抽查第 1、9、25、28 页，未见裁切、重叠、乱码、红色修订标记或 DOI。
- 首次独立检查器错误地要求摘要包含 10 个图片路径；该断言与“图片均位于六章正文”这一合同不符，修正检查器后重新运行通过。随后保护性生成器按设计拒绝覆盖与新 shorttitle 规则不一致的既有派生稿；用精确补丁同步两处元数据后，重新生成结果与现有文件完全一致，未发生来源覆盖或内容丢失。
- 第一幅源图 fig02_rths_loop_optionC.png 不存在，依照已冻结的合同映射为现有 fig01_rths_loop_optionD.png。该图片能正常编译，但图内为中文的一般 RHTS 闭环，未明确画出图题所称的独立执行器延迟通道；这是原始图片资产与图题的科学语义差异，未擅自改图或改写图题，保留为最终交付前需用户知悉的非阻塞事项。
- 现有来源没有作者单位和关键词；CAS 稿可正常编译，但投稿元数据仍不完整。未猜测或补写这些信息。

## 子任务 3：修正并核验 50 条 BibTeX 元数据

### 做什么

依据 DOI、出版社记录和旧核验库修正错误作者名、Jr. 后缀、复姓、期刊名与缺失卷期字段；不更改正文引用位置或论文措辞。

### 验证方法

对 50 个 DOI 逐项匹配标题和作者；运行 BibTeX 与 Biber 数据模型检查；检查重复键、重复 DOI、重复标题、必填字段和姓名解析输出。

### 预期结果

50 条记录全部真实可解析；缺失键、重复键、重复 DOI、重复标题、姓名倒置和 BibTeX/Biber 警告均为 0；最终无 DOI 显示字段。

### 完成记录（2026-09-03）

- 创建 verification_50refs/fetch_crossref_stage3.py，从受保护扩充库读取 50 个 DOI 并查询 Crossref；50/50 返回成功记录。结构化证据保存为 crossref_metadata_50.json，SHA-256 为 013C3C48255FFFFAF3102F065B0EC98B1189AD93E56C43CBA3DD221CB00199AF；DOI 只保留在核验证据中，未写回投稿用 BibTeX。
- 50 个题名在忽略大小写、花括号、HTML 实体、重音和连字符字形后全部与 DOI 登记题名一致；50 组作者的数量与顺序全部匹配。Zhang2024 的 Crossref 当前记录未带最终卷期页，依据 Wiley 正式页面保留 53(14):4334--4353；7 篇 online-first 年份与正式卷期年不同，继续采用卷期年；Guyan1965 的 380 与登记的 380--380 判为等价。
- 将全部 50 个 author 字段统一为 BibTeX 稳定的 Family, Given 格式，共 170 位作者。明确修正 Mahin1989 的 Pui-Shum B. Shing 与 Christopher R. Thewalt、Chae2013 的 Karim Kazemibidokhti、MacNeal1971 的 Richard H. MacNeal；7 个 Spencer 与 1 个 Craig 使用 Family, Jr., Given 三段式；Condori Uribe、Gutierrez Soto、van de Wouw 等复姓保持完整；两处 Stojadinović 使用稳定 TeX 重音写法。
- 将 18 条 Wiley 期刊名统一为 Earthquake Engineering \& Structural Dynamics，将 MacNeal1971 改为 Computers \& Structures；为 Mucha2023 增加 number={7}；为 Krattiger2019 的 {Hurty/Craig--Bampton} 增加专名保护。未改变引用键、条目类型、条目顺序、作者顺序、题名实质文字、年份、卷或页码。
- 创建 verification_50refs/build_stage3_bib.py，将修正先生成到隔离候选文件。候选独立通过 BibTeX 与 Biber 后才以补丁更新 reference_50refs_clean.bib；目标与候选逐字一致，最终 16,906 字节，SHA-256 为 7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A。
- 创建独立验证器 verification_50refs/verify_stage3_bib.py。修正前的负向测试能识别 170 个 Given Family 姓名、18 个错误 Wiley 刊名、错误作者和 Jr./复姓问题；修正后的完整模式退出码为 0：50 条记录、60 次引用、50 个唯一键、170/170 位作者、50 个 Crossref 题名和 50 组作者列表全部通过，重复键/题名、缺失键及 DOI 字面量均为 0。验证报告为 stage3_bib_validation.txt，详细证据为 stage3_metadata_audit.md。
- 传统 BibTeX 0.99e 使用 elsarticle-num-names.bst 生成 50 个 bibitem，退出码 0、warning 为 0；Biber 2.21 tool mode 数据模型检查退出码 0，输出 50 条，日志 warning/error 为 0。首次 Biber 进程继承了 Windows 上不可用的 C.UTF-8 区域设置并由 Perl 打印环境回退提示；清除该子进程的 LC_ALL/LC_CTYPE/LANG 后复跑，无环境提示且数据验证结果保持通过。
- 以未改动的 main_50refs_clean.tex 按 pdfLaTeX、BibTeX、pdfLaTeX、pdfLaTeX 完成技术编译，四步退出码均为 0。28 页检查 PDF 的 log/blg 中错误、未定义引用、重跑请求、溢出/欠满、缺字和 BibTeX 警告均为 0；60 条 citation、50 个 bibcite/bibitem、59 个 newlabel 全部闭合；PDF 文本无 ??、[?]、DOI、nolinkurl、草稿副标题或缺图提示，28 组字体全部嵌入。
- 第 25--28 页包含全部 50 条参考文献，已在 130 dpi 下逐页检查；未发现裁切、重叠、乱码、缺字、可见 DOI 或红色修订标记。实际文本确认 7 个 B. F. Spencer, Jr.、1 个 R. R. Craig, Jr. 及复姓、重音和专名均正确显示。
- 第一次尝试把 Git 标准数字区间 hunk 直接交给 apply_patch 时被语法解析器拒绝，目标 Bib 未改变；将同一已审查差异的区间头转换为工具支持的 @@ 形式后成功应用，并用目标/候选逐字哈希相等复核。

## 子任务 4：四步编译与 PDF 逐页验收

### 做什么

按 pdfLaTeX、BibTeX、pdfLaTeX、pdfLaTeX 顺序编译 main_50refs_clean.tex；渲染全部页面，检查首页、六章、全部公式/表格/图片和 50 条参考文献。

### 验证方法

检查四步返回码、log、blg、aux、bbl、PDF 文本、字体和逐页渲染图；搜索错误、未定义引用、问号占位、缺图框、DOI 和红色修订文字。

### 预期结果

四步返回码全为 0；LaTeX Error、未定义 citation/reference、??、BibTeX 警告、缺图占位和可见 DOI 均为 0；50 个 bibitem 全部生成；页面无裁切、重叠、乱码或缺图。

### 完成记录（2026-09-03）

- 从未改动的 main_50refs_clean.tex 和 reference_50refs_clean.bib 在 tmp/pdfs/stage4_compile 中完成有效的 pdfLaTeX、BibTeX、pdfLaTeX、pdfLaTeX 四步链，四个有效步骤退出码均为 0。第一次把含中文的完整绝对路径直接交给 BibTeX 时发生 Windows 路径转码失败，未生成可用 blg/bbl，也未修改正式源文件；将只读 BibTeX/样式副本放入隔离目录并以英文任务基名复跑后成功。该迭代已如实写入 stage4_full_pdf_audit.md。
- 最终隔离 PDF 为 28 页、1,431,589 字节，SHA-256 为 11E649BD0C471AFA831441AA2BB01CDF5B809383BEF4BAB31B65103A82323101。正式 TeX 与 BibTeX 的 SHA-256 仍分别为 EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995 和 7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A。
- 新建 verification_50refs/verify_stage4_pdf.py 并实际运行，stage4_pdf_validation.txt 状态为 PASS：6 章、12 小节、22 个 equation、2 个 subequations、2 个 align、5 个表格、9 个 figure/10 个图像、60 次引用、50 个唯一引用键、50 个 bibcite/bibitem 与 59 个标签全部闭合。
- log/blg 中 LaTeX 错误、未定义引用、重跑请求、overfull/underfull、缺字、缺文件及 BibTeX 警告/错误均为 0；PDF 文本中的 ??、[?]、DOI、nolinkurl、草稿副标题、缺图提示和可见修订命令均为 0；28 组字体全部嵌入，PDF 字符层红色正文为 0，字符越界为 0。
- 以 160 dpi 渲染全部 28 页，并由主任务和三个独立检查范围逐页查看。首页、摘要、六章、全部公式、5 个表格、9 个 figure/10 张图片及 [1]--[50] 参考文献均无裁切、重叠、乱码、缺字、缺图框、黑块、红色修订正文或可见 DOI。图中的红色曲线/坐标是科研内容，不是 rev 标记。
- 第 19 页末句在第 21 页完整续接，中间第 20 页为 Figure 5 和 Figure 6 的整页浮动排版；不存在文字丢失，按既定裁切、完整性和交叉引用标准判定为非阻塞。第一幅图与独立延迟通道图题的语义差异、原图内部中文图号、空 ORCID 栏以及未提供的作者单位/关键词继续作为来源与投稿元数据边界记录，未擅自修改。

## 子任务 5：最终交付与来源复核

### 做什么

复算新 TeX、BibTeX、PDF、验证报告和全部受保护来源的哈希；生成自包含交付清单。

### 验证方法

检查全部交付物存在且非空；重新运行来源冻结检查与最终合同检查；核对文件路径、哈希、页数、引用数和参考文献数。

### 预期结果

Doctor Bego 可直接在 manuscript 目录获得可复编译的清稿、BibTeX 和 PDF；历史 main/reference 与用户新提供的三个来源文件哈希不变。

### 完成记录（2026-09-03）

- 将子任务 4 已逐页验收的隔离 PDF 按原字节复制为 `manuscript/main_50refs_clean.pdf`；正式 PDF 与验收 PDF 逐字节相同，均为 28 页、1,431,589 字节，SHA-256 为 `11E649BD0C471AFA831441AA2BB01CDF5B809383BEF4BAB31B65103A82323101`。
- 三个正式交付件已复算：`main_50refs_clean.tex` 为 52,644 字节，SHA-256 `EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995`；`reference_50refs_clean.bib` 为 16,906 字节，SHA-256 `7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A`。
- 新建并实际运行 `verification_50refs/verify_stage5_delivery.py`，`stage5_delivery_validation.txt` 状态为 PASS。来源冻结、正文转换合同、BibTeX 元数据、编译日志、PDF 文本/字体/边界/颜色与正式文件哈希检查全部通过。
- 最终结构为 6 章、12 小节、22 个 equation、5 个表格、9 个 figure/10 张图片；60 次引用覆盖 50 个唯一键和 50 条参考文献。LaTeX/BibTeX 错误、未定义引用/交叉引用、缺图、`??`、可见 DOI、红色修订正文及禁用命令均为 0，28/28 组字体记录全部嵌入。
- 交付目录内本地 CAS 模板、参考文献样式、十张实际引用图片均存在并被清单记录；已生成 `final_delivery_manifest.md`，包含文件路径、字节数、哈希、验收结果与本地复编译命令。
- 三个独立只读复核均为 PASS：第一组核对三个正式交付件、逐字节 PDF 一致性和历史文件；第二组核对清单中 26/26 条文件/字节数/哈希记录、10/10 张实际引用图片及本地支持件；第三组独立统计 28 页、[1]--[50] 连续文献、60 次引用及禁用标记为 0。未发现遗漏或矛盾。
- 19/19 个受保护输入哈希不变，包括用户提供的新版 TeX/PDF/BibTeX、历史 `main.tex`/`reference.bib`/`main.pdf`、模板及十张图片；用户提供的 `apply_rths_references.py` 始终未执行。
- 最终交付仍如实保留来源边界：第一幅中文通用 RHTS 闭环图未明确展示图题中的独立执行器延迟通道；部分受保护图片内部保留中文旧图号；作者单位、关键词和 ORCID 值未提供，因而没有猜测或补写。

## TODO List

- [x] 子任务 1：冻结来源并建立允许变更合同（完成于：2026-09-03，验证结果：19/19 冻结文件哈希匹配；60 次引用、50 个唯一键与 50 条 BibTeX 完全闭合；唯一缺图路径已定位）
- [x] 子任务 2：生成不改文字的 Elsevier CAS 清稿（完成于：2026-09-03，验证结果：授权转换后摘要与六章正文逐字一致；60 次引用/50 条文献与 59 个标签闭合；四步技术编译退出码全 0、日志与代表页渲染无异常）
- [x] 子任务 3：修正并核验 50 条 BibTeX 元数据（完成于：2026-09-03，验证结果：50/50 DOI、题名与作者列表核验通过；170/170 位作者稳定解析；BibTeX/Biber/四步技术编译均退出 0，无警告、未定义引用或 DOI 显示）
- [x] 子任务 4：四步编译与 PDF 逐页验收（完成于：2026-09-03，验证结果：有效四步编译退出码全 0；28 页逐页渲染验收通过；错误、未定义引用、溢出、缺字、缺图、DOI 与红色正文均为 0）
- [x] 子任务 5：最终交付与来源复核（完成于：2026-09-03，验证结果：三个正式交付件齐全且哈希锁定；正式 PDF 与 28 页验收版逐字节相同；19/19 受保护来源不变；最终综合验证 PASS）
