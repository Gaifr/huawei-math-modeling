# 证据契约

本文件定义“计算结果—图表—论文”之间的唯一追溯规则。任何阶段都不得绕过它。

## Result id

- 格式为 `<问题编号>.<短名>`，例如 `Q1.objective`、`Q3.sensitivity_elasticity`。
- 一旦被论文、图表或审稿引用，就不允许改名或复用；语义改变必须新建 id。
- 同一 id 在 `results/result-evidence.json` 中只能出现一次。

## Model identity

每条结果必须同时登记四项，且互不替代：

- `model_identity`：数学模型的类型，禁止填写求解器或算法名称。
- `mechanism`：该模型在本题中起作用的机制。
- `solver_algorithm`：实际使用的求解或数值算法。
- `value` 与 `display_value`：真实值与论文呈现值。

## 数值与精度

- `value` 保存计算得到的原始值，禁止为了对齐论文而修改。
- `display_value` 是论文中出现的字符串，`precision` 说明舍入方式。
- 论文中的数字必须能在某个结果记录的 `display_value` 或明确的推导式中找到。
- 允许的例外仅限年份、章节号、公式编号、文献编号等非结果数字。

## Source hashes 与 run records

- 每条结果的 `source_files` 与 `input_files` 记录路径与 `sha256`；
  文件内容变化即视为该结果过期。
- 计算得到的结果必须提供 `run_command` 与 `environment`；缺一即视为无证据。
- 涉及随机性的结果必须提供 `random_seed`。
- `results/run-logs/` 中的日志是运行事实的唯一凭证，日志丢失则该结果不可引用。

## Paper citation links

- 图表通过 `figures/figure-manifest.json` 的 `source_result_ids` 指回结果。
- 论文位置由 `paper_location` 记录，便于审稿按位置复核。
- 结果可以没有图表，但图表不可以没有结果。

## Stale behaviour

- 当上游产物进入 `.huawei-modeling/state.json` 的 `stale_artifacts`，引用它的证据、
  图表和论文段落一并视为过期。
- 过期证据不得作为门禁通过依据，也不得保留在终稿中等待“以后再改”。
- 使上游内容变化后，必须用 `python scripts/workflow.py --workspace <workspace>
  rework <stage> --reason "<原因>"` 传播影响，再重新走一遍受影响阶段。

## Authority

Paper prose never overrides computational truth。论文文字不得覆盖计算结果；发现冲突时
以结构化结果为准，并回溯定位是计算、图表还是表述出错。
