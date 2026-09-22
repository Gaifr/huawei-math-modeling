# FORMULATION 阶段协议

目标：为每一问选出可验证、可实现、可衔接的模型方案，并冻结决策。
模型身份、机制和求解算法是三件不同的事，必须分开登记。

## Required inputs

- `analysis/` 中的句子台账、任务图、数据审计和歧义登记。
- 当届官方规则中与模型、结果表达相关的约束。
- 用户对 DISCOVERY 歧义的裁定结果。

## Required outputs

- `modeling/candidate-models.md`：每问至少两个真正不同的候选（可行时），并给出统一
  对比表，列固定为：

```text
candidate | model identity | mechanism | solver | inputs | outputs | assumptions |
validation | failure conditions | implementation cost | downstream compatibility
```

- `modeling/model-decision.md`：选定的主模型、备选模型、选择理由、放弃理由、
  失败时的 fallback，以及该决定绑定的数据与假设。冻结后作为下游唯一依据。
- `modeling/formulation.md`：变量、参数、单位、目标函数与约束的完整数学表述。
- `modeling/validation-plan.md`：验证方式、对照条件、需要产出的结果 id 与判定标准。

## Required definitions

- **Model identity**：模型在数学上是什么（如混合整数规划、时空扩散方程、层次聚类）。
- **Problem-specific mechanism**：本题中该模型通过什么机制回答题目（约束来自哪里、
  状态如何演化、距离或权重如何定义）。
- **Solver algorithm**：实际用来求解的数值或启发式算法（如 HiGHS、Gurobi、
  模拟退火）。求解器永远不能被登记为 Model identity。

## Required checks

- 每个候选都写明 inputs、outputs 和 failure conditions，而不是只写名字。
- 先给出可解释、可复现的 baseline，再讨论增强方案；增强必须说明相对基线的增量收益。
- 候选之间的对比在公平条件下进行：同一数据口径、同一评价指标、同一约束集。
- 主模型说明其 downstream compatibility：中间结果能否被后续问题复用。
- 假设、参数和单位与 `analysis/data-audit.md` 的记录一致，不得出现无来源参数。

## Stop conditions

- 数据不足以支撑任何候选：回到 DISCOVERY 补充数据审计，不得虚构数据或参数。
- 主模型无法在剩余时间内实现：改选备选，并在 `model-decision.md` 记录原因。
- 本阶段结束时必须完成“模型选择”人工确认，未确认不得进入 COMPUTATION。
- 确认后 `modeling/model-decision.md` 冻结；实质修改必须走 `rework`。
