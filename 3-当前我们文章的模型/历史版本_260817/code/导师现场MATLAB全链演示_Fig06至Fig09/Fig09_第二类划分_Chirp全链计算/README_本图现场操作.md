# Fig.9 第二类划分 Chirp 全计算链现场操作

- 打开：`RUN_FIG09_FULLCHAIN.m`
- 激励：脚本现场生成0.1--10 Hz、40 s线性Chirp。
- 模型：`lvxvjie_guyan.slx` 的本地运行副本，并只在副本补齐三层Guyan/CB输出。
- 自由度：Original=15、Guyan=5、Craig--Bampton=8；状态维数30/10/16。
- 图中上排为一层、下排为三层；每排依次为0--40 s、13--14 s、38--38.3 s。
- 本机已验证的一层绝对峰值：Original 8.834959337877 mm，Craig--Bampton 8.837705713539 mm，Guyan 8.910721613883 mm。
- 本机已验证的三层绝对峰值：Original 34.561666695242 mm，Craig--Bampton 34.570533326171 mm，Guyan 38.487890056135 mm。

硕士论文图3-15的两个局部窗历史上混入了El Centro响应；本入口和当前小论文Fig.9使用物理一致的Chirp窗口。点击运行后，最后必须出现 `FULL_CHAIN=PASS`。
