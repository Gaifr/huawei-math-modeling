# COMPUTATION 阶段协议

目标：用真实运行的程序得到结果，并让每个结果都能被复现和追责。本阶段只产出
可执行代码、运行日志和结构化结果，不写论文。

## Required inputs

- 冻结的 `modeling/model-decision.md`、`modeling/formulation.md`、
  `modeling/validation-plan.md`。
- `analysis/data-audit.md` 与 `inputs/attachments/` 中的原始数据。
- 当届规则中对数据使用、结果报告和 AI 使用的约束。

## Required outputs

- `code/` 下的可执行程序，入口清晰，按问题（如 `code/problems/q1.py`）组织。
- `code/code-manifest.json`：每个源文件的路径、SHA-256、用途、入口命令和依赖。
- `results/run-logs/`：每次运行的原始日志、退出码、开始与结束时间。
- `results/result-evidence.json`：结构化结果，字段与
  `assets/schemas/result-evidence.schema.json` 一致。
- `results/metrics/`、`results/tables/`：指标与表格产物，供 EVIDENCE 阶段引用。

## Required checks

- 每个关键结论都绑定 `run_command` 与 `environment`（解释器/求解器版本）。
- 先跑通 baseline 并记录其指标，再与增强方案对比；两者共用同一数据与指标。
- 涉及随机的算法必须声明 `random_seed` 并实际固定，日志中可核验。
- 优化类问题检查 constraint 满足情况与 residual，评价类问题检查指标与权重定义，
  预测类问题检查留出集误差。
- 输入文件与源文件的 `sha256` 如实登记；证据里引用的文件必须真实存在。
- Do not report a value that no successful run produced；失败运行只能作为失败证据记录。

## Stop conditions

- 求解失败：保存日志、参数和最后可行状态，允许有限次重试；仍失败则回到
  FORMULATION 改选模型或算法，不得用文字遮掩失败。
- 数据字段与假设冲突：回到 DISCOVERY 或 FORMULATION，不得就地改数据。
- 结果与领域常识明显矛盾：先做合理性检查，再决定是否返工。
- 本阶段结束时必须完成“结果可信度”人工确认，由用户决定是否进入模型增强。
