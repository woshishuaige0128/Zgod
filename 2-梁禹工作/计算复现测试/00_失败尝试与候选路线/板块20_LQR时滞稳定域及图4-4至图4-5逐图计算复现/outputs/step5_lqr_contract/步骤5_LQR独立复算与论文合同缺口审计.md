# 板块20步骤5：作者离散LQR独立复算与论文合同缺口审计

## 1. 人话结论

本步骤用 Python/Scipy 从两份第二分区封签工作区中的 `MPren/CPren/KPren` 重新建立状态空间，独立执行精确ZOH离散化和离散DARE求解。程序没有读取步骤4的谱半径或极点结果。三条第一分区执行源中没有活动的 `dlqr` 调用，故统一标记为 `LQR_NOT_PRESENT_IN_EXECUTED_SOURCE`，不能凭文件名补出LQR。

严格绝对门禁固定为 `max(abs(independent-reference)) <= 1e-8`，不随结果放宽。ZOH得到的 `Ad/Bd` 和闭环 `Acl` 通过该门禁；`K_lqr/DeltaK/DeltaC` 没有全部通过。作为次级诊断，另报告 `abs(diff) <= 1e-8 + 1e-8*abs(reference)`；两条第二分区路线在这个尺度感知门禁下均通过。因此裁决是 `SCALE_AWARE_PASS_STRICT_ABS_FAIL`，不是无条件PASS。

这项结果只交叉验证历史主程序的 `c2d+dlqr` 核心，不会把它升级成硕士论文或当前小论文的连续CARE计算级复现。两篇论文的必填数值合同仍未闭合，结论保持 `待决定`。

## 2. 五条文件身份路线

| 路线 | 分区 | 活动dlqr数 | 裁决 |
|---|---:|---:|---|
| `main_ori_div1` | `div1` | 0 | `LQR_NOT_PRESENT_IN_EXECUTED_SOURCE` |
| `main_guyan_div1` | `div1` | 0 | `LQR_NOT_PRESENT_IN_EXECUTED_SOURCE` |
| `alt_guyan_div1_stable_full_ps3` | `div1` | 0 | `LQR_NOT_PRESENT_IN_EXECUTED_SOURCE` |
| `main_ori_div2` | `div2` | 1 | `SCALE_AWARE_PASS_STRICT_ABS_FAIL` |
| `main_guyan_div2` | `div2` | 1 | `SCALE_AWARE_PASS_STRICT_ABS_FAIL` |

两份第二分区执行源虽然文件名分别写有 Original 和 Guyan，但封签的LQR输入、作者工作区LQR输出以及本次独立复算数组均逐元素完全相同。它们必须保留两个文件身份，不能据此声称存在两套独立LQR设计。

## 3. 独立复算数值

| 路线 | 闭环设计谱半径 | ZOH严格门禁 | Acl严格门禁 | 增益严格门禁 | 尺度感知门禁 |
|---|---:|---|---|---|---|
| `main_ori_div2` | 0.99547020792374319 | `TRUE` | `TRUE` | `FALSE` | `TRUE` |
| `main_guyan_div2` | 0.99547020792374319 | `TRUE` | `TRUE` | `FALSE` | `TRUE` |

严格绝对门禁失败量如下；绝对差必须原样保留，不能用相对量级掩盖：

| 路线 | 变量 | 最大绝对差 | Frobenius相对差 | 次级尺度感知门禁 |
|---|---|---:|---:|---|
| `main_ori_div2` | `K_lqr` | 1.6386763945774874e-08 | 7.0758076407452527e-12 | `TRUE` |
| `main_ori_div2` | `DeltaK` | 2.3590284399688244e-05 | 7.0862137587267596e-12 | `TRUE` |
| `main_ori_div2` | `DeltaC` | 5.1531242206692696e-07 | 3.4038444579954372e-12 | `TRUE` |
| `main_guyan_div2` | `K_lqr` | 1.6386763945774874e-08 | 7.0758076407452527e-12 | `TRUE` |
| `main_guyan_div2` | `DeltaK` | 2.3590284399688244e-05 | 7.0862137587267596e-12 | `TRUE` |
| `main_guyan_div2` | `DeltaC` | 5.1531242206692696e-07 | 3.4038444579954372e-12 | `TRUE` |

闭环极点由独立 `Acl=Ad-Bd*K_lqr` 与封签作者 `Acl` 分别求特征值，再用最小总代价一一配对；各极点误差详见 `design_poles.csv`。

## 4. 硕士论文与当前小论文的必填字段合同

- 梁禹硕士论文：8/20 个必填字段标为 `SPECIFIED`；合同状态 `CONTRACT_NOT_CLOSED`。
- 当前小论文 `manuscript_0824.tex`：9/20 个必填字段标为 `SPECIFIED`；合同状态 `CONTRACT_NOT_CLOSED`。

这里的计数不是论文质量评分，只表示能否仅凭该文档形成唯一、可审计的数值输入。完整逐字段证据见 `thesis_manuscript_contract_matrix.csv`。决定性缺口包括：连续CARE的数值A/B或B_a、输入单位与归一化、CR标量alpha、反馈嵌入矩阵、清除负次幂的具体幂次、原点伪根数量/容差、根残差门槛，以及历史l/j矩阵行列与tau1/tau2的映射。

此外，两篇论文的第二分区和反馈位置不是同一合同：硕士论文第二分区写 `psi1,psi6` 两通道延迟且 `psi11` 无延迟，式(4-38)至式(4-40)把反馈放在H外；当前小论文作动 `psi1,psi11`、重构 `psi6`，并把反馈放在H_a内。两者必须分开实现和验证。

## 5. 证据边界与诚实标签

- `计算级复现`：步骤2的历史MATLAB执行证据另行封签。本步骤仅是独立LQR核心交叉验证；因纯绝对1e-8门禁未全部通过，不标记为无条件独立计算PASS。
- `绘图级复现`：本步骤没有画图，也没有创建成功图目录，不改变既有绘图级证据等级。
- `历史值`：图4-4/图4-5已有边界及论文5 ms/10 ms说法均不因本步骤升级。
- `待决定`：论文输入语义、第二分区权威定义、反馈位置、CR标量alpha和轴映射仍需明确选择后才能另建论文公式路线。

## 6. 独立性、封签与可重复性

- 只读输入：五路线manifest、五份提取后的执行源、两份第二分区 `workspace_complete.mat`、步骤3公式报告和冻结 `manuscript_0824.tex`。
- 禁止输入：`outputs/step4_rho_grids` 下任何谱半径、极点或稳定掩膜；本脚本读取列表中没有这些文件。
- 两份第二分区工作区在运行前后重新计算SHA-256；输入未变化。
- 数值矩阵以长表形式写入 `recomputed_lqr_matrices.csv`，可逐元素审计。
- 本脚本输出不写运行时间戳；连续两次执行应得到完全相同的文件哈希。

关键源文件SHA-256：

- `alt_guyan_div1_stable_full_ps3:source_m`: `D8965FD60986BF60854116E44686A206C79C5E9C794755F3B20ECFB35A71D90F`
- `analyze_board20_step5_lqr.py`: `10EE351233515A0A84FCF249F894A930A16290E9C046A90116FFB3A96F8D327E`
- `board20_step4_route_manifest.json`: `397564F6884DE082995D04DF9AB62F13244DFA8C6129BDDB1F18A2DF0BE88D6E`
- `main_guyan_div1:source_m`: `D8965FD60986BF60854116E44686A206C79C5E9C794755F3B20ECFB35A71D90F`
- `main_guyan_div2:source_m`: `49DA7B5D7E8B57E311C263555E94FADB053341D6B5BDA5AAEAC4C28445298624`
- `main_guyan_div2:workspace_complete.mat`: `5B677B11EDCEC3AA7EE4955BE7B46ADB3F1BC7957BD7A7673456AE3F24476F21`
- `main_ori_div1:source_m`: `E0E220E1B7549FA2F623DEDA02CE16C1726CEC061247626BF7A407438440D2FA`
- `main_ori_div2:source_m`: `7366D13BDDEC707AB7DD98F9BC7C359935CBE9AC0037A4FA28680B457BD4AADE`
- `main_ori_div2:workspace_complete.mat`: `7781807F01B9D95CA9554F3AE5449065C4DEB4C2FF8FFC62679E08BEC8757061`
- `manuscript_0824.tex`: `15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76`
- `板块20_公式语义审计_草稿.md`: `3BAC10BFC72E8B8FFC2FA54B20A518B134097DA8530DE52C35AF865DAF0B5C10`

第二分区跨文件身份逐元素相同性：

- 封签历史LQR输入与输出全部相同：`True`。
- 独立复算数组全部相同：`True`。

