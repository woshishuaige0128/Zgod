# 步骤4第二次正式编排失败记录

- 状态：`INFRASTRUCTURE_FAILURE_AFTER_MATLAB_A_PAYLOAD_COMPLETE`
- 发生时间：2026-08-26 05:35（Asia/Shanghai）
- 已完成部分：103项输入暂存PASS；Python第1轮PASS；MATLAB第1轮生成305,382条中间量和1,096条结果，自报PASS且进程退出码为0。
- 外层拒绝原因：MATLAB在写完终端JSON后，`onCleanup` 再次关闭已经手工关闭的文件句柄，产生本地编码警告；同时终端JSON包含中文绝对路径。完整stdout因此不能按“UTF-8、末行唯一JSON”合同解析。
- 影响范围：科学规范载荷已经写出，但两轮未完成、跨语言未验证，故不得算作步骤4完成或表4-1证据。
- 修正：关闭器先通过 `fopen('all')` 判断句柄仍打开才调用 `fclose`；MATLAB/Python终端JSON均移除非必要绝对输出路径。没有修改公式、输入、规范科学CSV/JSON字段、数值容差或完成标准。
- 保留范围：原输入暂存、Python第1轮、MATLAB第1轮、编排失败摘要和全部日志均在本目录，可恢复审计；没有删除或覆盖。
