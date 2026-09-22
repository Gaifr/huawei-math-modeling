---
name: huawei-math-modeling
description: Run or resume an evidence-gated Huawei Cup/NPGMCM mathematical-modeling project from official-material intake through modeling, real computation, LaTeX/DOCX manuscript production, judge-style review, and submission checks. Use only for the China Postgraduate Mathematical Contest in Modeling; require user decisions at interpretation, model selection, computed-result trust, and final-draft approval.
---

# Huawei Math Modeling

Determine the active stage from `.huawei-modeling/state.json`; initialize only when no state exists. Load only `references/stages/<active-stage>.md`, plus `references/formats/<route>.md` during MANUSCRIPT or DELIVERY.

Stages: `INTAKE -> DISCOVERY -> FORMULATION -> COMPUTATION -> EVIDENCE -> MANUSCRIPT -> REVIEW -> DELIVERY`.

Never bypass a pending human checkpoint. Never claim a computation ran without execution evidence. Current-year official materials override references. When an upstream artifact changes, use the workflow rework operation instead of silently editing downstream conclusions.
