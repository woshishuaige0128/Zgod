# Board20 Step5第三版full-q/SVD候选独立静态预检

> 结论：`PASS_STATIC_POSTCHECK_NOT_AUTHORIZED`。本次没有读取或验收pilot/full科学结果，也没有启动任何计算。

## 人话结论

- V3合同、计算脚本、基础实现、V2根引擎和输入封签均与最终SHA-256一致。
- 候选自身preflight为51/51 PASS，synthetic selftest为77/77 PASS。
- V3保留原1e-8门槛；硬残差改为直接计算原P(z)和Laurent G(z)的归一sigma_min，旧伴随向量q块残差仅作诊断。
- V2失败证据、第一次compact validator的2项FAIL和条件性诊断裁决均保持不变。
- pilot/full事后验收必须另行明确授权并带CLI显式标志；validator本身永不启动候选计算。

## 后续硬门

- 49点试点或10385点全网格必须完整通过CSV/HDF5/checkpoint/manifest身份检查。
- 每个门控物理根必须独立重算P(z)与G(z)归一SVD残差且均不超过1e-8。
- 与封签Step-4 MATLAB rho逐点绝对差不超过1e-8，rho<1分类逐点一致。
- repeatability必须声明baseline=repeat=实际科学manifest SHA，五路线checkpoint HDF5哈希必须自洽。
