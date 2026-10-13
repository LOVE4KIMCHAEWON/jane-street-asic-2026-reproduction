# ASIC 谜题复现

Python 3.10 或更新版本即可；不需要安装第三方包。

先下载 [Jane Street 原始仓库](https://github.com/janestreet/asic-puzzle-2026)，解压后运行：

```sh
python reproduce.py --puzzle-dir /path/to/asic-puzzle-2026 --out /path/to/generated
```

Windows 下把两个路径替换为本机路径；含空格的路径加双引号。

程序从原始 `puzzle.gds` 重新提取网表，回放示例 VCD，通过 121 次单星输入恢复区域地图，再用独立求解器求出唯一棋盘，最后仿真输出字符串。正常耗时约几十秒。生成答案、输入位、网格、JSON 网表、标准单元 Verilog 网表和详细验证记录。

同时验证 warm-up 的加法器、全零输入、全一输入、删除一颗星，以及保持所有计数正确但存在接触的棋盘。最后一个反例确保邻接检查确实起作用。

本工具针对原始 GDS 的 SHA-256；区域计数器编号来自公开电路分析，运行时通过实际电路单星探测恢复每格所属区域。它不是通用 GDS 提取器。`gdstk.py` 只实现这两个版图使用的正交几何子集，并已与原生 gdstk 提取结果逐项对比一致。

仿真采用零延迟的二值逻辑。原版图有一条悬空线，默认值取 0，使邻接失败提示显示为 `TWO"NOT TOUCH`；这条线不影响成功输出。Verilog 导出供检查，未用 HDL 仿真器验证，需要 SKY130 标准单元模型。

来源和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。
