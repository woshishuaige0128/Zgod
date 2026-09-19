# 步骤4第一次正式编排失败记录

- 状态：`INFRASTRUCTURE_FAILURE_BEFORE_INPUT_COPY`
- 发生时间：2026-08-26 05:32（Asia/Shanghai）
- 失败阶段：输入暂存器核对步骤3顶层封签文件。
- 原因：暂存器把实际文件 `stage_summary.json`、`run_configs.csv`、`staged_input_manifest.csv` 写成了三组近似文件名；三个固定SHA-256本身与真实文件完全一致。
- 影响范围：未复制任何输入，未创建 `outputs/s4/`，未运行Python公式计算或MATLAB；仅保留1个总编排失败摘要和4个暂存/进程日志文件。
- 修正：只更正暂存器和独立验证器中的三个相对文件名，不修改固定哈希、数值容差、公式、历史路线合同或科学完成标准。
- 恢复性：原失败摘要和日志由正式目录完整移动到本目录，没有删除，可直接审计。
