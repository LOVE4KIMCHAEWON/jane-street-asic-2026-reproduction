# 来源与修改

`extract2.py`、`sim.py` 来自 Mubin Shaikh 的 [ASIC puzzle solution](https://github.com/shaikhmubin02/asic-puzzle-2026-solution)，commit `1dc04232f333df5a06626d733403f2d86c009b23`，MIT 许可。这两个文件保持原样；许可证见 `LICENSE-MIT.txt`。

`cellsdb.json` 是从 [SkyWater SKY130 HD 官方 functional Verilog](https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd) 解析的门级行为模型。上游 commit `ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1`，Copyright 2020 The SkyWater PDK Authors，Apache-2.0；见 `LICENSE-APACHE-2.0.txt`。解析工具来自上述 MIT 仓库。

`gdstk.py`、`star_solver.py`、`reproduce.py` 在本次任务中编写。标准库 GDS 读取器代替第三方依赖；独立约束求解器代替原公开工具的 SAT 求解器；主程序添加原始波形回放、正反例验证和结果导出。

完整发布版还增加了 `extract_easter_geometry.py`、`analyze_signals.py`、`audit_floating.py` 和根目录的 `run_all.py`，用于六个彩蛋和悬空线问题的源数据证据提取。`paper/build_pdf.py` 使用 ReportLab 将本次技术报告排版为 PDF。新增代码和报告均在本次任务中借助 AI 编写，采用根目录 MIT 许可。

原始数据来自 [Jane Street ASIC puzzle](https://github.com/janestreet/asic-puzzle-2026)，commit `ffd53e0ba24e2fc1c1b12dc824e8eac5888c19a9`。复现包不包含原始 GDS/VCD，请从上游下载。

官方最终答案及背景：[Results from the ASIC puzzle](https://blog.janestreet.com/asic-puzzle-results/)，2026-10-02。本任务参考公开解析及开源提取/仿真工具，然后从原始版图重新提取、求解、验证；不声称是未参考公开答案的独立破解。
