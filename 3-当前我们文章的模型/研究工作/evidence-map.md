# 研究证据入口

本表从当前已交付候选方案开始登记；前序材料按各自封存清单追溯。

## 2026-09-16 完整框架等时滞候选方案
- 逐项证据：audits/unified_full15_equal_delay_20260916/evidence-map.md。
- 公式与代码：同目录theory/unified_full15.tex/PDF、code/unified_model.py及三项验证入口。
- 实际结果：1066+432+24项检查，本地通过；详情同目录results/delivery_checks.json。
- 采用与审查：候选数学方案已验证，正式路线待Doctor Bego决定，Pro材料仅本地准备。旧案例和前轮审计保留，不用新候选结果覆盖旧模型结论。

## 2026-09-16 完整框架等时滞模型Pro讨论
- 来源：pro_reviews/unified_full15_equal_delay_20260916/PRO_RESPONSE_01.md、PRO_RESPONSE_02.md；对话6aaa6bc5-1168-83ea-9457-61a117792523。
- 状态：两轮讨论完成；建议尚未采纳，新增理论尚未本地验证，原候选审查包保持。
- 涉及：研究定位、虚拟界面/内部状态/反力/惯性说明、零附加增益主比较、内部荷载输出贡献、CR算法加速度及历史零根、双层完整参照、五组图及补充慢扫频。
- 审查范围更正：不登记Pro独立脚本复跑，依据第二轮明确撤回；本地1522项既有验证与外部阅读审查分开。

## 2026-09-16 统一15坐标等时滞正式案例（当前交付）
- 目录：cases/case3_v1_full15_equal_delay_20260916；入口：完整框架等时滞案例_图解汇报.html、CASE_ANALYSIS.md、README.md。
- 用户目标授权后按完整框架直接缩聚/虚拟协调执行；模型与算法定义见MODEL_SPECIFICATION.md，选点与验收见CASE_PROTOCOL.md。
- 理论：theory/full15_error_theory.tex/PDF，32式5页；本地1605项核验。实际Pro第三轮理论审读、第四轮结果摘要审读及范围在review/，无外部代码执行。
- 动力学/响应：results/dynamics.json、responses.json、critical_mechanism.json、case_validation.json、matlab_case_validation.json。84项正式响应检查、6组同地震记录交叉核验通过。
- 科研图：23组矢量/600dpi图，figures/figure_manifest.json和curve_provenance.json；新旧映射results/historical_figure_mapping.json。
- 可复现与保护：results/independent_reproduction.json、delivery_checks.json、source_protection_after.json；156文件delivery_manifest.json；521旧文件/3来源保持。
- HTML静态PASS，浏览器viewport因既有安全限制未运行；科学图及理论PDF实际渲染检查PASS。原稿未替换，硬件可实现性和临界根遗漏耦合贡献分解不在已完成结论内。
