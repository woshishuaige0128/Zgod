# Step4 attempt03 failure summary

## 状态

- 尝试状态：`INFRASTRUCTURE_FAILURE_AFTER_MATLAB_A_SCIENTIFIC_PAYLOAD`
- 输入暂存：PASS，103项证据加14份案例合同均已生成。
- Python第1轮：PASS。
- MATLAB第1轮科学载荷：PASS，进程退出码0，输出305,382条数值和1,096条结果。
- 总编排：FAIL；未启动Python第2轮、MATLAB第2轮和正式独立验证。
- 表4-1：未裁决。

## 失败原因

MATLAB函数结束后，`onCleanup` 调用 `closeIfStillOpen`。该函数使用的 `fopen('all')` 在当前MATLAB版本被升级为弃用错误，导致已成功输出的唯一终端JSON后追加本地编码诊断文本。外层编排器因此不能把stdout解析成唯一UTF-8终端JSON，按机器合同拒绝本次尝试。

这不是公式、矩阵、历史目标值或CSV科学载荷失败。修复仅把清理查询改为 `fileName=fopen(fileId)`，只在返回非空时关闭该单一句柄；不改变任何公式、分支、数值格式或容差。

## 归档范围

- `outputs_s4i/`：本次输入暂存现场。
- `outputs_s4/`：Python第1轮及MATLAB第1轮载荷。
- `outputs_s4o/`：失败摘要。
- `logs_s4/`：原始stdout、stderr、命令、退出码和进程证据。
- 合计：141个文件，227,754,066字节。

本目录为失败证据，只读保留；不得作为正式成功结果发布。
