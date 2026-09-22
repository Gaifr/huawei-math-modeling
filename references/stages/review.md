# REVIEW 阶段协议

目标：以技术审稿和评委审稿两条独立轨道检查论文，并把问题按根因去重，回退到真正的
源头阶段。审稿不修改计算结果，也不替用户做最终决定。

## Required inputs

- 冻结的 `manuscript/source/` 与最终 PDF（以及它的 SHA-256）。
- `results/result-evidence.json`、`results/run-logs/`、`figures/figure-manifest.json`。
- `analysis/task-graph.md` 与 `modeling/model-decision.md`。
- 当届官方规则中的格式、页数、匿名与 AI 使用要求。

## Required outputs

- `review/issue-ledger.json`：去重后的问题台账，绑定当前 `paper_sha256`。
- `review/technical-review.md`、`review/judge-review.md`。
- `review/revision-rounds/`：每轮修改对应的台账快照。

## Required passes

每个 pass 独立执行，不允许用一次通读代替：

1. 任务覆盖与答案完整性：题面每个编号任务是否都有明确结论和交付物。
2. 模型必要性与数据支持：所选模型是否真的需要，参数是否有数据来源。
3. 假设、参数、单位、约束、推导与跨问衔接是否自洽。
4. 执行真实性：是否真的运行过、能否复现、有无验证、否证、敏感性、不确定性和可行性分析。
5. 章节质量：标题、摘要、关键词、问题分析、符号说明、模型章节、参考文献、附录、AI 披露。
6. 外行可读性与 AIGC/模板风险：非本领域读者能否读懂主线；是否存在明显的模板套话风险。
7. 评委综合：给出 3–5 条最高价值的修改建议，并说明优先级。

## Rules

- 评分细则必须在阅读论文质量之前，根据**当前题目**重新构建，不得套用往届题库结论。
- 任何数字分数必须标注为内部参考，不得推导获奖概率，也不得复用 CUMCM 的学校、赛区
  或指导教师历史分布。
- 问题按 `root_stage + root_key` 去重：同一根因即使出现在摘要、结果和格式多处，也只计
  一次，并合并位置、证据和影响的问题编号。
- 审稿结论必须回退到源头：表述问题回 MANUSCRIPT，图表支撑不足回 EVIDENCE，
  数值不可信或不可复现回 COMPUTATION，模型不适配回 FORMULATION，题意理解错误回 DISCOVERY。
- 禁止只改终稿文字来掩盖上游问题。

## Stop conditions

- 发现 P0（提交资格、题意、数据真实性、模型根本错误、结果伪造、关键文件缺失）：不得
  进入 DELIVERY，先用 `rework` 回退根因阶段。
- 台账的 `paper_sha256` 与当前 PDF 不一致：说明论文已变化，必须重新审稿。
- 本阶段结束时必须完成“终稿批准”人工确认；P1 必须逐项修复或被用户明确接受。
