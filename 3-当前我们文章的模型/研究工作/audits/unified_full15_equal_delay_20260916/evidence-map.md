# 本轮方案的证据映射

本表仅覆盖统一完整框架等时滞候选方案。来源见source_manifest.json，当前公式见theory/unified_full15.tex/PDF；正式采用与外部审查均待定。

|结论/待审命题|公式与实现|实际证据|状态|
|---|---|---|---|
|先定义完整物理信号路径，再一致投影|eq:motion、eq:full、eq:projection；unified_model.full_model/project|validation_python：两种划分原系数、通道因子、荷载输出投影|代数通过；接口解释待审|
|CB0与标准Guyan闭环相同|eq:basis；cb_basis/project|validation_python：CB0_G各系数|通过|
|全内部模态恢复相应原15闭环|eq:fullspace、eq:discrete_projection、eq:similarity|Python全空间输出/命令与最小历史相似；MATLAB完整历史相似|本地通过|
|完整界面局部缩聚形成兼容15行基底|interface_basis|interface各模型compatibility、local_assembly、G9恒等；MATLAB独立局部质量装配|通过|
|划分一原零质量坐标转为保留后内部质量正定|完整界面路线表、interface_basis|model_summary内部坐标与最小特征值；MATLAB独立检查|在当前质量分配与保留集合下成立|
|划分二局部每侧3模态为完整15|局部路线表|model_summary：N3/P3/order15；全空间恢复检查|通过；不能作为有限截断优越性论据|
|残量误差恒等式、遗漏模态Schur补|eq:error、eq:schur；verify_error_identities|24项，最大1.2850326475838137e-11|本地代数通过，待外部理论审查|
|有限时程矩阵幂误差表达|eq:finite|来自线性状态递推的有限卷积推导，本轮无新时程验证|推导已整理，响应验证未执行|
|推荐完整框架基底作为主验证|推导第7节、HTML第8节|保持原保留集合、阶数与中间层位移遗漏机制|助手建议，待Doctor Bego决定|
|实际两台作动器可实现补充界面协调|推导第1/2/7节问题；REVIEW_REQUEST|现有资料没有装置/数值耦合实现证据|待审/待建模决定|

检验复数点用于算子恒等验证，不是本轮选择的新激励。两个物理划分的完整15阶延迟参照可能不同；各划分内部的缩聚精度参照保持一致。
