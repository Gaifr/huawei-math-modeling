# DISCOVERY 阶段协议

目标：把题面变成可追溯的“句子—任务—数据—产物”映射，并暴露所有实质歧义。
本阶段只读题、审数据、登记歧义，不选模型、不写代码。

## Required inputs

- `inputs/problem/` 中的当届赛题文本。
- `inputs/attachments/` 中的全部数据文件。
- INTAKE 登记的 `state.json` 与官方规则快照。

## Required outputs

- `analysis/sentence-ledger.md`：逐句或逐段登记题面，每一条都标注属于
  definitions、conditions、data、task、deliverable 还是 rule；不得遗漏编号任务。
- `analysis/task-graph.md`：用 Mermaid 画出各问之间的数据、变量、参数和结果传递，
  每条连线写明传的是什么。
- `analysis/data-audit.md`：逐个文件记录来源、维度、字段、单位、缺失、重复、异常值、
  时间与空间结构，以及“现有数据无法支撑的证据”。
- `analysis/ambiguity-register.md`：每个实质歧义至少给出两种解释、快速判别方法、
  拟采用解释、后果，以及需要用户决策的问题。

## Required checks

- 题面里每一个编号任务在句子台账和任务图中都出现，且交付要求明确到文件形式。
- 数据审计中的每个字段都能在附件中真实找到，不得凭常识补数据。
- Do not treat background paragraphs or submission rules as independent numbered questions；
  背景、格式规范、提交说明只能作为规则约束登记。
- 歧义登记中的每个“拟采用解释”都说明它如何影响后续模型与结果口径。

## Stop conditions

- 存在影响题目理解、但无法从题面自证的歧义：写入歧义登记并向用户提出确认。
- 附件缺失、损坏或字段含义无法判定：登记为阻塞项，只允许给出条件式方案。
- 任务图中出现无法连通的问：先解决跨问衔接，再进入 FORMULATION。
- 本阶段结束时必须完成一次人工确认，确认内容见 `references/human-checkpoints.md`。
