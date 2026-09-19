# 板块21：能量指标与表4-1逐单元格计算复现

本目录是板块21的隔离计算与证据根。它只处理两个对象：

- 表4-1“两类划分Guyan与Craig--Bampton能量变化率”；
- 结论C06“能量变化率超过0.3时稳定风险增加”。

最小步骤1已完成：论文、作者“能量指标”目录、相关上游矩阵、稳定域证据和既有保护清单共53项均已按精确来源路径、冻结路径、字节数和SHA-256冻结，独立验证495/495项通过。三种目录替换时序已分别对冻结程序和独立验证程序做动态测试，六种组合均安全通过；真实断链目录联接也被不跟随目标的边界门识别。

最小步骤2也已完成：论文PDF第72页的式(4-41)至式(4-45)被固定为模态能量分配合同，不是接口力--速度时程积分；36个作者文件、7条能量候选路线、29个非汇总依赖、35条逐式裁决和26份Live Script富记录全部进入75项静态库存。独立验证为298/298 PASS，83项主工件闭合；两轮“静态构建→独立验证”各采集79个非空文件，缺失、额外和差异均为0。26份富记录除直接解析比较外还受逐文件固定SHA-256约束，针对未参与旧核心比较的 `source_name` 真实反例被验证器以297/298拒绝，恢复后无探针残留。

这两个步骤都没有运行MATLAB，没有创建对象正式成功目录，也没有把论文表值升级为计算级复现。当前准备最小步骤3：在隔离干净MATLAB会话中原样运行7条作者候选路线。主要入口：

- `input/input_manifest.csv`：53项冻结输入的来源、副本、字节数与哈希；
- `outputs/step1_validation/validation_summary.json`：独立验收摘要；
- `outputs/step1_validation/relative_handle_race_test.json`：冻结器和验证器在目录替换竞态下的实测结果；
- `report/板块21_最小步骤1_输入冻结验收.md`：人可读验收记录；
- `code/freeze_board21_inputs.py` 与 `code/validate_board21_step1.py`：冻结与不导入冻结器的独立验证入口；
- `code/test_board21_relative_handle_race.py`：两个实现、三种攻击时序的可重跑安全探针。
- `outputs/step2_static_inventory/inventory_summary.json`：75项静态库存摘要；
- `outputs/step2_validation/validation_summary.json`：298/298独立验证摘要；
- `outputs/step2_determinism/determinism_audit.json`：两轮79/79确定性审计；
- `report/板块21_最小步骤2_公式与历史脚本静态审计.md`：论文公式、7条路线、历史输出与错误变体的人可读裁决；
- `code/build_board21_step2_static_inventory.py`、`code/validate_board21_step2_static_inventory.py` 与 `code/run_board21_step2_determinism.py`：步骤2构建、独立验证和双轮复跑入口。
