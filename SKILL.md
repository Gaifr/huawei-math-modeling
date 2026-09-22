---
name: huawei-math-modeling
description: Run or resume an evidence-gated Huawei Cup/NPGMCM mathematical-modeling project from official-material intake through modeling, real computation, LaTeX/DOCX manuscript production, judge-style review, and submission checks. Use only for the China Postgraduate Mathematical Contest in Modeling; require user decisions at interpretation, model selection, computed-result trust, and final-draft approval.
---

# Huawei Math Modeling

Determine the active stage from `.huawei-modeling/state.json`; initialize only when no state exists. Load only `references/stages/<active-stage>.md`, plus `references/formats/<route>.md` during MANUSCRIPT or DELIVERY.

Stages: `INTAKE -> DISCOVERY -> FORMULATION -> COMPUTATION -> EVIDENCE -> MANUSCRIPT -> REVIEW -> DELIVERY`.

Never bypass a pending human checkpoint. Never claim a computation ran without execution evidence. Current-year official materials override references. When an upstream artifact changes, use the workflow rework operation instead of silently editing downstream conclusions.

## Initialize or resume

```bash
python scripts/workspace_init.py --workspace <contest-workspace> \
  --problem <problem-file> --template <official-template> \
  --rules <official-rules> --route latex|docx --ai-disclosure required|off

python scripts/workflow.py --workspace <contest-workspace> status
```

Initialize once per contest; afterwards resume from `status` rather than re-initializing.
Always read `references/workflow.md` before advancing stages and
`references/evidence-contract.md` before writing results or paper numbers.

## Stage reference loading

| Active stage | Load |
|---|---|
| INTAKE | `references/stages/intake.md` |
| DISCOVERY | `references/stages/discovery.md` |
| FORMULATION | `references/stages/formulation.md` |
| COMPUTATION | `references/stages/computation.md` |
| EVIDENCE | `references/stages/evidence.md` |
| MANUSCRIPT | `references/stages/manuscript.md` + `references/formats/<route>.md` |
| REVIEW | `references/stages/review.md` |
| DELIVERY | `references/stages/delivery.md` + `references/formats/<route>.md` |

## Human checkpoints

Message the user and wait. Never approve on their behalf, never assume a default,
never infer consent from silence. Details: `references/human-checkpoints.md`.

1. **DISCOVERY** — "题意、歧义解释和交付要求是否确认？"
2. **FORMULATION** — "主模型与备选模型是否确认？"
3. **COMPUTATION** — "结果是否可信？是否投入模型增强？"
4. **REVIEW** — "是否批准该终稿候选版本？"

```bash
python scripts/workflow.py --workspace <ws> request-approval <STAGE>
python scripts/workflow.py --workspace <ws> approve <STAGE> --note "<用户原话>"
```

Approvals bind the hashes of every registered artifact up to that checkpoint, so
editing an approved file invalidates the approval.

## Standard versus enhanced computation

First produce a reproducible baseline. After the result-trust checkpoint passes,
ask the user to choose: stop at the baseline (standard) or invest further in model
enhancement. Enhancement never replaces the baseline — keep both, compare under the
same data, metric and constraints, and record the measured increment. Prefer the
simplest model that answers the question.

## Gates and rework

```bash
python scripts/gate_check.py --workspace <ws> --stage <STAGE>
python scripts/evidence_check.py --workspace <ws>
python scripts/manuscript_check.py --workspace <ws> --route latex|docx
python scripts/render_audit.py --workspace <ws>
python scripts/workflow.py --workspace <ws> rework <STAGE> --reason "<原因>"
```

Gates check artifacts, hashes, freshness, approvals and reports — never mathematical
correctness, and never an award prediction. A P0 always blocks; every P1 must be
fixed or explicitly accepted by the user. Missing optional tools are reported as
`unverified`, never as passing.

## Privacy boundary

This repository stays separate from every contest workspace. Never copy real
problems, papers, team numbers, personal data, or absolute local paths into it, and
never commit generated papers, inputs, run logs, caches or `.huawei-modeling/`. Public
reports carry filenames and hashes only; absolute source paths stay in the workspace's
git-ignored `local-sources.json`.

## Final boundary

Finish with a prepared submission package and a user-facing checklist: files to
submit, unverified items, and residual risks. The user performs the actual contest
submission — this Skill never uploads, submits, or makes external network requests,
and never claims that automated gates prove the mathematics or guarantee a result.
