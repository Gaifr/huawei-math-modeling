# 人工确认点协议

人工确认不得使用默认值、超时推定或代理自动代答。每次确认都必须由用户看过指定
材料后明确选择，并绑定截至该确认点的全部有效、非过期登记产物哈希。
可选决定只有：

- **approve**：材料与风险可接受，记录具体说明后继续。
- **request changes**：说明原因，对根因阶段执行 `rework`，修订后重新确认。
- **stop**：停止流程，保留现状，不启动下一阶段。

## DISCOVERY：题意确认（`interpretation`）

- 检查文件：`analysis/sentence-ledger.md`，以及其中引用的任务图、歧义登记、数据字典和交付清单。
- 必备证据：每条题目陈述有原文定位；每个编号任务有输入、输出、评价口径和依赖；附件字段有来源；歧义列出采用解释、备选解释及影响；交付要求来自当前官方材料。
- approve 后果：冻结当前题意解释，可以进入 `FORMULATION`。
- request changes 后果：返回 `DISCOVERY`，其后的模型、结果、图表和论文产物均需按影响重新生成。
- stop 后果：不开始 `FORMULATION`。

## FORMULATION：模型选择（`model_selection`）

- 检查文件：`modeling/model-decision.md`，及其引用的候选模型比较、假设、公式、输入输出和验证计划。
- 必备证据：主模型与备选模型身份明确；数学机制和求解算法分开描述；候选使用同一数据、约束、指标和计算预算比较；有可解释基线、失败条件、回退方案与跨问题兼容性说明。
- approve 后果：冻结主模型、备选模型和验证强度，可以进入 `COMPUTATION`。
- request changes 后果：返回 `FORMULATION`；后续计算及其证据、论文和审稿结论全部失效。
- stop 后果：不投入真实计算。

## COMPUTATION：结果可信与增强决策（`result_trust`）

- 检查文件：`results/result-evidence.json`，以及所引用的源码、运行日志、结构化结果、环境记录、基线对照、约束或残差检查。
- 必备证据：程序真实成功运行；输入和源码哈希可核对；随机种子在适用时固定；模型身份、机制与算法分离；基线结果存在；关键结论通过约束、误差、敏感性、稳健性或其他约定校验；失败运行没有冒充结果。
- approve 后果：用户明确选择“保持基线”或“进入增强”，并确认当前结果可作为证据整理的基础。
- request changes 后果：返回 `COMPUTATION`；若根因是模型不适配，应继续回退到 `FORMULATION`。
- stop 后果：不进入 `EVIDENCE`，未确认结果不得写成论文结论。

## REVIEW：终稿确认（`final_draft`）

- 检查文件：最终候选 `manuscript/paper.pdf`、`review/issue-ledger.json`，以及技术审稿和评委式审稿报告。
- 必备证据：审稿报告绑定当前 PDF 哈希；P0 为零；每项 P1 已修复或由用户逐项明确接受；数值与结构化结果一致；图表和引用可追溯；匿名、AI 披露及官方格式风险已列明；仍存在的限制写入交付风险清单。
- approve 后果：批准这一份哈希对应的终稿候选，可以进入 `DELIVERY` 做最终打包检查。
- request changes 后果：按根因回到 `MANUSCRIPT`、`EVIDENCE`、`COMPUTATION`、`FORMULATION` 或 `DISCOVERY`，不得只在终稿中遮盖上游问题。
- stop 后果：不进入 `DELIVERY`，也不产生“已批准提交”的表述。

确认只代表用户接受当前阶段的判断，并不保证数学正确、官方合规或竞赛结果。确认后的
绑定文件发生变化时，旧确认自动不可用于推进；必须显式返工并重新确认。
