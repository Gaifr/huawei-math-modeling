# 工作流状态与返工协议

## 固定阶段

工作流只允许按以下顺序推进：

`INTAKE → DISCOVERY → FORMULATION → COMPUTATION → EVIDENCE → MANUSCRIPT → REVIEW → DELIVERY`

`begin` 只能启动当前阶段的直接下一阶段，不能跳阶段。`complete` 只完成当前
活动阶段，并为每个声明的产物计算 SHA-256。`DISCOVERY`、`FORMULATION`、
`COMPUTATION` 和 `REVIEW` 完成后还必须依次执行 `request-approval` 和
`approve`；缺少确认、确认已失效或确认绑定的文件发生变化时，下一阶段不能开始。
每个确认点绑定截至该阶段的全部有效、非过期登记产物；因此 `REVIEW`
后的终稿确认同时绑定当前 `manuscript/paper.pdf` 及其上游证据。

典型命令如下：

```powershell
python scripts/workflow.py --workspace <workspace> status
python scripts/workflow.py --workspace <workspace> complete INTAKE inputs/problem/problem.pdf
python scripts/workflow.py --workspace <workspace> begin DISCOVERY
python scripts/workflow.py --workspace <workspace> complete DISCOVERY analysis/sentence-ledger.md
python scripts/workflow.py --workspace <workspace> request-approval DISCOVERY
python scripts/workflow.py --workspace <workspace> approve DISCOVERY --note "题意与歧义处理已确认"
python scripts/workflow.py --workspace <workspace> begin FORMULATION
```

## 中断恢复

所有成功迁移先持久化到 `.huawei-modeling/state.json`，审批保存在
`.huawei-modeling/approvals.json`，事件追加到 `.huawei-modeling/events.jsonl`。
进程或会话中断后，先运行 `status`，按 `active_stage` 与对应 `status` 恢复：

- `active`：继续制作该阶段产物，完成后再执行 `complete`；不要重复 `begin`。
- `awaiting_approval`：重新检查人工确认材料，再选择批准、要求修改或停止。
- `complete`：若当前阶段有确认点，先检查审批；否则开始直接下一阶段。
- `pending`：尚未到达，不能提前开始。

恢复时不得根据聊天记录猜测进度；磁盘状态、审批记录和事件日志才是可恢复依据。

## 过期产物

发现上游根因后执行：

```powershell
python scripts/workflow.py --workspace <workspace> rework FORMULATION --reason "主模型改变"
```

返工会把目标阶段重新设为 `active`，后续阶段设为 `pending`，把后续阶段已登记的
产物加入 `stale_artifacts`，并显式使目标阶段及后续阶段的旧审批失效。文件不会被
删除，便于比较与追溯；但过期文件不能作为当前结论、论文或交付依据。阶段重新完成
且同一路径产物重新登记后，该路径才从过期清单移除。每次返工都会写入原因、受影响
产物和失效审批事件。

返工落盘采用两阶段事件：先追加含 `operation_id` 的
`stage_rework_requested`，再写入审批和状态，最后追加
`stage_rework_completed`。如果意图事件无法写入，返工不会改变状态；如果只有
意图而没有同 `operation_id` 的完成事件，说明操作曾中断，应核对当前状态后
使用相同目标阶段和原因重试。

## 为什么手工改文件不等于返工

直接编辑已登记文件不会更新状态机、不会传播下游影响，也不会留下根因事件。文件
哈希一旦与完成记录或人工确认不一致，后续 `begin` 会拒绝推进。正确做法是先对根因
阶段执行 `rework`，再重新生成、`complete` 并在需要时重新请求人工确认。禁止只改
论文文字或覆盖旧文件来掩盖上游变化。
