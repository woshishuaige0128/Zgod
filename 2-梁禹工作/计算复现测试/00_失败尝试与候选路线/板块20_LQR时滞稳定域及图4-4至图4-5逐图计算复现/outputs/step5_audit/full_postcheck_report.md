# 板块20最小步骤5 full-postcheck 独立验收报告

- 总体状态：`FAIL`
- 检查数：115
- 通过：108
- 独立诊断：5
- 失败：2
- 证据边界：Python独立计算与MATLAB步骤4结果严格分阶段；论文公式合同未闭合时不生成科学网格。

## 失败项

- `S5-POST-0095` main_ori_div2 MATLAB/Python rho逐点绝对差不超过1e-8：{"failure_count":4,"failure_points":[{"abs_diff":3.398668324550158e-08,"j":39,"l":11,"rho_matlab":1.0163977217624076,"rho_python":1.0163977557490909},{"abs_diff":1.4479864196559333e-08,"j":40,"l":15,"rho_matlab":1.0181382838457822,"rho_python":1.0181382983256464},{"abs_diff":2.114230190919386e-08,"j":41,"l":23,"rho_matlab":1.0167482880062317,"rho_python":1.0167483091485336},{"abs_diff":1.2270835236805056e-08,"j":43,"l":28,"rho_matlab":1.0200476120122581,"rho_python":1.0200476242830934}],"max_abs_diff":3.398668324550158e-08,"points":2077}
- `S5-POST-0108` main_guyan_div2 MATLAB/Python rho逐点绝对差不超过1e-8：{"failure_count":4,"failure_points":[{"abs_diff":3.398668324550158e-08,"j":39,"l":11,"rho_matlab":1.0163977217624076,"rho_python":1.0163977557490909},{"abs_diff":1.4479864196559333e-08,"j":40,"l":15,"rho_matlab":1.0181382838457822,"rho_python":1.0181382983256464},{"abs_diff":2.114230190919386e-08,"j":41,"l":23,"rho_matlab":1.0167482880062317,"rho_python":1.0167483091485336},{"abs_diff":1.2270835236805056e-08,"j":43,"l":28,"rho_matlab":1.0200476120122581,"rho_python":1.0200476242830934}],"max_abs_diff":3.398668324550158e-08,"points":2077}

## 工件

- JSON：`D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\test\00_失败尝试与候选路线\板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现\outputs\step5_audit\full_postcheck.json`
- CSV：`D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\test\00_失败尝试与候选路线\板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现\outputs\step5_audit\full_postcheck_checks.csv`
