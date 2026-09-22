# EVIDENCE 阶段协议

目标：把计算结果变成能支撑论点的图表，并让论文里的每个数字都能指回结果 id。
本阶段决定“哪些结果值得进论文”，不改变计算结果。

## Required inputs

- `results/result-evidence.json`、`results/metrics/`、`results/tables/`。
- `results/run-logs/` 中的成功运行记录。
- `analysis/task-graph.md` 与 `modeling/model-decision.md`，用于判断图表要论证什么。

## Required outputs

- `figures/figure-manifest.json`：每张图一条记录，字段至少包含 `claim`（该图支持
  的具体论点）、`source_result_ids`（对应的结果 id）、`publish`（是否进论文）、
  `paper_location`（论文位置）、`caption`、`generation_command`。
- `figures/data/`：由真实计算结果生成的数据图及其绘图脚本或命令。
- `figures/schematics/`：技术路线图、流程图等示意性图形，与数据图分开存放。
- `figures/visual-qa.json`：字号、裁切、标签重叠、图例完整性的检查结果。

## Required checks

- 每张 `publish: true` 的图都回答“它推进了哪个论点”，只“看起来高级”的图不进论文。
- 数据图的数值来自 `source_result_ids` 指向的结果，不接受手工填写或推算的数字。
- schematic 不得与数据图混用同一目录或同一编号体系，避免把示意图当成计算证据。
- 图表引用的数据来源、单位、置信区间或误差信息在 caption 中说明。
- 结果精度与论文呈现位数一致，舍入规则见 `references/evidence-contract.md`。
- 敏感性、稳健性或对照实验的结果同样登记，不得只保留有利结果。

## Stop conditions

- 某张图找不到对应结果 id：删除该图或补做计算，禁止先画图再补数据。
- 结果之间存在冲突：回到 COMPUTATION 复核，不得在图表层掩盖矛盾。
- 关键结论缺少任何图表或表格支撑：回到 COMPUTATION 补算。
- 视觉检查发现裁切、字号过小或标签重叠：修图后重跑检查，不接受“渲染后再说”。
