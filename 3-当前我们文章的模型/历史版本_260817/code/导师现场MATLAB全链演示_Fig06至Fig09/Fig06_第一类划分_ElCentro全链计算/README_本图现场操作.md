# Fig.6 第一类划分 El Centro 全计算链现场操作

- 打开：`RUN_FIG06_FULLCHAIN.m`
- 激励：El Centro 1940 NS原记录乘0.40。
- 模型：`lvxvjie_guyan_2.slx` 的本地运行副本。
- 自由度：Original=15、Guyan=6、Craig--Bampton=9；状态维数30/12/18。
- 图中上排为一层、下排为三层；每排依次为0--40 s、10--11 s、21.5--22.5 s。
- 成功尺寸：`response_mm = 40961×3×3`。
- 本机已验证的一层绝对峰值：Original 3.284839533336 mm，Craig--Bampton 3.289732633437 mm，Guyan 3.352565742347 mm。
- 本机已验证的三层绝对峰值：Original 12.351147303532 mm，Craig--Bampton 12.347535801365 mm，Guyan 12.321564441083 mm。

点击运行后，最后必须出现 `FULL_CHAIN=PASS`。当前CSV只在第9节用于末端比较，不参与计算或绘图。
