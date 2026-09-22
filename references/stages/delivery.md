# DELIVERY 阶段协议

目标：把论文和支撑材料整理成可提交包，并把所有未解决风险明确交给用户。
本阶段**绝不代替用户提交**，提交动作永远由用户完成。

## Required inputs

- `manuscript/paper.pdf`（最终 PDF）与 `manuscript/source/`。
- `manuscript/manuscript-check.json`、`manuscript/pdf-layout-report.json`。
- `review/issue-ledger.json`（绑定当前 `paper_sha256`）。
- 当届官方规则快照（页数、目录深度、匿名、文件命名、支撑材料要求）。

## Required outputs

- `delivery/submission-manifest.json`：所有拟提交文件的相对路径、SHA-256 和大小。
- `delivery/final-check.md`：面向用户的提交清单与未解决风险。
- `.huawei-modeling/gates/DELIVERY.json`：门禁结果。

## Required checks

1. 最终 PDF 存在且大小非零；记录的导出或编译命令可复现。
2. 必须存在 `.huawei-modeling/rule-snapshot.json`：快照缺失或与登记的官方规则
   哈希不一致时，DELIVERY 直接失败。页数超过 `max_pages`、目录深度超过
   `toc_max_depth`、命中身份信息、文件名不符合 `filename_pattern` 同样失败；
   快照中写为 `null` 的条款记为未验证而非通过。
3. 目录层级不超过当届允许深度。
4. 匿名性扫描：`gate_check.py` 扫描 `manuscript/source/` 中的邮箱、手机号以及
   「作者/单位/学校/学院/指导教师/学号/队号/队员」等标注，
   `anonymity_allowlist` 中的正则可豁免；人工仍需确认扫描未覆盖的表述和 PDF 页眉页脚。
5. AI 使用说明与工作区 `ai_disclosure` 登记一致。
6. 图表与公式经过视觉检查（`figures/visual-qa.json`、`pdf-layout-report.json`）。
7. 附录与支撑材料清单完整，且与 `submission-manifest.json` 一致。
8. 文件名符合当届规则（命名、扩展名、禁止特殊字符）。
9. 审稿台账中不存在未解决的 P0，也不存在未接受的 P1。
10. 论文、证据与审稿对应同一个 `paper_sha256`。

## Stop conditions

- 缺少最终 PDF、官方模板或支撑材料清单：不得进入提交准备。
- 存在未解决的 P0 或未接受的 P1：先 `rework` 回退根因阶段。
- 审稿台账的论文哈希与当前 PDF 不一致：重新审稿。
- 无法导出 PDF（缺少 LibreOffice/Word）：交回用户导出后重新检查，不得宣称完成。
- 官方规则快照缺失：页数、目录深度和命名只能标记为未验证。

## Final boundary

完成后向用户输出提交清单：要提交哪些文件、已知未验证项和残留风险，以及**由用户
自行上传提交**。Skill 不发起任何提交、上传或对外网络请求。
