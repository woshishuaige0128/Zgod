# Fig.8 第一类划分 Chirp 全计算链现场操作

- 打开：`RUN_FIG08_FULLCHAIN.m`
- 激励：脚本现场生成0.1--10 Hz、40 s线性Chirp，不读取既有响应。
- 模型：`lvxvjie_guyan_2.slx` 的本地运行副本。
- 自由度：Original=15、Guyan=6、Craig--Bampton=9；状态维数30/12/18。
- 图中上排为一层、下排为三层；每排依次为0--40 s、13--14 s、38--38.3 s。
- 本机已验证的一层绝对峰值：Original 8.834959337877 mm，Craig--Bampton 8.835888792425 mm，Guyan 8.925470338089 mm。
- 本机已验证的三层绝对峰值：Original 34.561666695242 mm，Craig--Bampton 34.564455680095 mm，Guyan 34.703859593335 mm。

点击运行后，最后必须出现 `FULL_CHAIN=PASS`。当前CSV只在第9节用于末端比较。
