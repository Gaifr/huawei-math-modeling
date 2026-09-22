# INTAKE 阶段协议

目标：登记当届官方材料并冻结规则快照。本阶段只做材料登记，不读题、不建模。

## Required inputs

- 当届赛题文件（题目 PDF/DOCX 或题面文本）。
- 当届全部附件与数据文件。
- 当届官方论文模板（LaTeX 或 Word，以官方发布为准）。
- 当届官方规则，至少包含论文格式规范与人工智能工具及输出使用规定。
- 用户选择：交付路线 `latex` 或 `docx`；AI 使用说明 `required` 或 `off`。

## Required outputs

- 工作区目录 `inputs/problem/`、`inputs/attachments/`、`inputs/official-template/`、
  `inputs/official-rules/`，其中前三类由初始化命令写入登记副本。
- `.huawei-modeling/state.json`：`active_stage = "INTAKE"`，`route`、
  `ai_disclosure`、四项输入的文件名与 SHA-256。
- `.huawei-modeling/local-sources.json`：仅本地保存的原始绝对路径，禁止写入
  `state.json`、`events.jsonl` 或任何公开报告。
- `.huawei-modeling/events.jsonl` 的首条 `workspace_initialized` 事件。
- `.huawei-modeling/rule-snapshot.json`：从当届官方规则中提取的机器可读条款
  （`max_pages`、`toc_max_depth`、`anonymity_required`、`filename_pattern` 等），
  结构见 `assets/schemas/rule-snapshot.schema.json`。无法确定的条款一律写 `null`，
  对应检查会记为未验证，而不是误判为通过。

初始化命令：

```bash
python scripts/workspace_init.py --workspace <workspace> --problem <赛题> \
  --template <官方模板> --rules <规则> --route latex|docx --ai-disclosure required|off
```

## Required checks

- 三份来源文件都存在且是普通文件，哈希与 `state.json` 一致。
- 模板与规则确属当届发布；往届文件不得当作当届材料使用。
- 工作区位于 Skill 仓库之外。

## Stop conditions

- 缺少当届官方模板或规则：停在 INTAKE，允许先读题和建模，但禁止声称论文格式合规。
- 材料来源或届次不确定：向用户确认，不得默认沿用旧文件。
- 工作区被要求建在 Skill 仓库内部：拒绝初始化并说明原因。
- 官方模板与官方规则互相矛盾：请用户裁定，不自行取舍。
