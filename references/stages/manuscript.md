# MANUSCRIPT 阶段协议

目标：把已冻结的证据写成论文。LaTeX 与 DOCX 共用同一份内容证据层，两条路线只在
排版上分叉。本阶段不产生新数字。

## Required inputs

- `results/result-evidence.json`、`results/tables/`、`results/metrics/`。
- `figures/figure-manifest.json` 与 `figures/visual-qa.json`。
- `analysis/`、`modeling/` 中的题意、模型决策与验证计划。
- 当届官方纸纸模板：`inputs/official-template/`。
- 工作区的 `route` 与 `ai_disclosure` 登记值。

## Required outputs

- `manuscript/source/`：论文源文件，Markdown、LaTeX 或两者并存。
- `manuscript/manuscript-check.json`：由 `scripts/manuscript_check.py` 生成的检查报告。
- `manuscript/ai-usage-record.json`：当 `ai_disclosure = required` 时，基于真实工作日志
  生成的 AI 使用记录。
- 导出的 `manuscript/paper.pdf`（终稿候选）。

## Required checks

- 论文中的每一个结果数字都能在某个结果记录的 `display_value` 中找到；年份、章节号、
  公式编号和文献编号属于显式例外。
- 图与表的来源通过 `figure-manifest.json` 的 `source_result_ids` 指回结果。
- 模型名称与 `results/result-evidence.json` 登记的 `model_identity` 一致。
- 论文中不出现 `.huawei-modeling`、`workflow.py`、`P0/P1`、`rework` 等内部流程用语。
- 官方模板哈希与 INTAKE 登记一致；模板变化必须先返工再写作。
- 运行 `python scripts/manuscript_check.py --workspace <workspace> --route latex|docx`，
  P0/P1 必须清零。

## Stop conditions

- 存在无法追溯的数值：回到 COMPUTATION 或 EVIDENCE 补证据，禁止改数字迎合论文。
- 官方模板缺失或变化：停止排版，先回到 INTAKE 登记当届材料。
- 图表尚在 EVIDENCE 阶段未定稿：不得开始写对应章节。
- 本阶段结束时必须完成“论文叙事与可读性”的人工检查，再由 REVIEW 阶段接手。
