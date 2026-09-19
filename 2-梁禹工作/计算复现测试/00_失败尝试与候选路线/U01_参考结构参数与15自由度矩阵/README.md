# U01执行层失败迭代

U01的数值模型最终已在成功目录中达到**计算级复现**。本目录专门保留外层执行器的两次失败：

1. `run_reference_model_matlab_attempt1_mu_name_collision.log`：`tes.m` 的变量 `mu` 与工具箱同名函数冲突。
2. `run_reference_model_matlab_attempt2.log`：新增捕获命令的 `sprintf` 字符串数组语法无效。

两次都没有修改梁禹原脚本或数值门槛；最终只修正外层捕获方式。

