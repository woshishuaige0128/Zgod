# Fig.7 第二类划分 El Centro 全计算链现场操作

- 打开：`RUN_FIG07_FULLCHAIN.m`
- 激励：El Centro 1940 NS原记录乘0.40。
- 模型：`lvxvjie_guyan.slx` 的本地运行副本。
- 必要适配：只在副本中补齐 `Mux6/2 <- Demux4/3` 与 `Mux6/3 <- Demux5/3` 两条三层输出。
- 自由度：Original=15、Guyan=5、Craig--Bampton=8；状态维数30/10/16。
- 图中上排为一层、下排为三层；每排依次为0--40 s、10--11 s、21.5--22.5 s。
- 本机已验证的一层绝对峰值：Original 3.284839533336 mm，Craig--Bampton 3.286334645387 mm，Guyan 3.023044307363 mm。
- 本机已验证的三层绝对峰值：Original 12.351147303532 mm，Craig--Bampton 12.350893034542 mm，Guyan 13.425302846346 mm。

点击运行后，最后必须出现 `FULL_CHAIN=PASS`。黄色 `Demux2` 未连接警告来自被旁路的旧块，不代表有效计算链失败。
