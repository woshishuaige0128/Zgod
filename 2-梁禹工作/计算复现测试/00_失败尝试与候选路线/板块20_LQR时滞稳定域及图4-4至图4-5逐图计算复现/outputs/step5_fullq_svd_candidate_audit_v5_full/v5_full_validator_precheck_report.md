# Board20 Step5第四版正式全网格 / validator V5 full-only独立静态预检

> 结论：`PASS_STATIC_FULL_POSTCHECK_SEALED`。本次读取并验收了full元数据、manifest内18项与清单外17项文件哈希及五个检查点，但未进入10385点逐点科学验算，也没有启动任何计算。

## 人话结论

- V4合同、计算脚本、基础实现、根引擎和输入封签均与最终SHA-256一致。
- 候选自身preflight为58/58 PASS，synthetic selftest为80/80 PASS。
- V4保留原1e-8门槛；硬残差仍直接计算原P(z)和Laurent G(z)的归一sigma_min，旧伴随向量q块残差仅作诊断。
- V3永久失败及V1失败审计、V2失败证据、第一次compact validator的2项FAIL和条件性诊断裁决均保持不变。
- validator V5 full-only继承V4的科学公式和门槛；预检只核对授权、闸门、完整性和哈希，不进入10385点SVD循环。
- validator V4的49点pilot事后验收保持封签；validator V5 full-only已启用正式full事后验收，执行时仍须CLI显式授权，且validator本身永不启动候选计算。

## 后续硬门

- 10385点正式全网格必须完整通过CSV/HDF5/checkpoint/manifest身份检查。
- 每个门控物理根必须独立重算P(z)与G(z)归一SVD残差且均不超过1e-8。
- 与封签Step-4 MATLAB rho逐点绝对差不超过1e-8，rho<1分类逐点一致。
- 正式候选full不要求重算第二遍；V5 full-postcheck必须独立执行两遍且9项验收产物逐字节一致，五路线checkpoint HDF5哈希必须自洽。
