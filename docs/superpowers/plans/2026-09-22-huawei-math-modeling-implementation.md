# Huawei Math Modeling Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Huawei Cup/NPGMCM-specific Codex Skill that combines evidence-gated research execution with problem-specific modeling review, human checkpoints, LaTeX/DOCX delivery, and deterministic validation.

**Architecture:** A concise `SKILL.md` routes one active stage at a time to focused references. Standard-library Python scripts own workspace initialization, append-only workflow state, hashes, evidence validation, review issue deduplication, and submission gates; human judgment is required at four explicit checkpoints.

**Tech Stack:** Markdown Agent Skills, Python 3.10+ standard library, JSON/JSON Schema, `unittest`, optional XeLaTeX/LibreOffice/PDF tools discovered at runtime.

**Spec:** `docs/superpowers/specs/2026-09-22-huawei-math-modeling-design.md`

## Global Constraints

- Target only the China Postgraduate Mathematical Contest in Modeling (Huawei Cup/NPGMCM).
- Current-year official problem, template, and AI-use rules override bundled guidance.
- Keep the Skill repository separate from every contest workspace; never copy private contest artifacts into the repository.
- Support LaTeX and Word/DOCX, with both routes grounded in the uploaded official Huawei Cup template and one shared evidence layer.
- Stop at four user checkpoints: interpretation, model choice, result trust/enhancement, and final-draft approval.
- Never claim that automated gates prove mathematical correctness or guarantee an award.
- Reimplement general BZD-style methods; do not copy BZD text, templates, scoring data, model dictionary, scripts, or HTML.
- Preserve the upstream MIT notice for ideas or code adapted from `math-model-skills-v2`.
- Core scripts must run on Python 3.10+ using only the standard library.

---

## Planned File Map

```text
SKILL.md                              Stage router and non-negotiable rules
agents/openai.yaml                    UI metadata and default prompt
scripts/common.py                     Atomic JSON, hashing, path and event helpers
scripts/workspace_init.py             Safe contest workspace creation and intake registration
scripts/workflow.py                   Stage/checkpoint/rework state machine CLI
scripts/evidence_check.py             Result-evidence and model-identity validation
scripts/review_ledger.py              Root-cause issue deduplication and severity summaries
scripts/manuscript_check.py            Shared and format-specific manuscript checks
scripts/render_audit.py                Final-size figure/PDF audit with optional tool adapters
scripts/gate_check.py                 Stage gate aggregation and machine-readable output
scripts/quick_smoke.py                Synthetic end-to-end contract smoke test
assets/schemas/*.schema.json          Machine-readable state/evidence/review contracts
references/workflow.md                Stage transitions, rework and recovery rules
references/human-checkpoints.md       Evidence required for each user decision
references/evidence-contract.md       Traceability and model-identity rules
references/stages/*.md                One focused protocol per active stage
references/formats/{latex,docx}.md    Format-specific official-template workflows
tests/test_*.py                       Standard-library unit and integration tests
tests/helpers.py                      Reusable synthetic workflow fixtures for tests only
LICENSE                               MIT license for original repository content
THIRD_PARTY_NOTICES.md                Attribution and BZD non-copying boundary
```

---

### Task 1: Repository and Skill Scaffold

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`
- Create: `LICENSE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `.gitignore`
- Create: `tests/test_skill_structure.py`

**Interfaces:**
- Consumes: approved design specification.
- Produces: discoverable skill name `huawei-math-modeling`, progressive-reference links, and repository policy files used by all later tasks.

- [ ] **Step 1: Write the failing structure test**

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillStructureTest(unittest.TestCase):
    def test_entrypoint_and_metadata_exist(self):
        self.assertTrue((ROOT / "SKILL.md").is_file())
        self.assertTrue((ROOT / "agents" / "openai.yaml").is_file())

    def test_entrypoint_has_required_frontmatter_and_routes(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: huawei-math-modeling", text)
        self.assertIn("description:", text)
        for stage in ("INTAKE", "DISCOVERY", "FORMULATION", "COMPUTATION",
                      "EVIDENCE", "MANUSCRIPT", "REVIEW", "DELIVERY"):
            self.assertIn(stage, text)
        self.assertIn("references/stages/", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the scaffold is absent**

Run: `python -m unittest tests.test_skill_structure -v`

Expected: FAIL because `SKILL.md` and `agents/openai.yaml` do not exist.

- [ ] **Step 3: Create the minimal entrypoint and UI metadata**

`SKILL.md` must contain this frontmatter and routing contract:

```markdown
---
name: huawei-math-modeling
description: Run or resume an evidence-gated Huawei Cup/NPGMCM mathematical-modeling project from official-material intake through modeling, real computation, LaTeX/DOCX manuscript production, judge-style review, and submission checks. Use only for the China Postgraduate Mathematical Contest in Modeling; require user decisions at interpretation, model selection, computed-result trust, and final-draft approval.
---

# Huawei Math Modeling

Determine the active stage from `.huawei-modeling/state.json`; initialize only when no state exists. Load only `references/stages/<active-stage>.md`, plus `references/formats/<route>.md` during MANUSCRIPT or DELIVERY.

Stages: `INTAKE -> DISCOVERY -> FORMULATION -> COMPUTATION -> EVIDENCE -> MANUSCRIPT -> REVIEW -> DELIVERY`.

Never bypass a pending human checkpoint. Never claim a computation ran without execution evidence. Current-year official materials override references. When an upstream artifact changes, use the workflow rework operation instead of silently editing downstream conclusions.
```

`agents/openai.yaml`:

```yaml
interface:
  display_name: "Huawei Math Modeling"
  short_description: "华为杯研究生数模全流程建模、计算、论文与审稿"
  default_prompt: "使用 $huawei-math-modeling 启动或恢复华为杯研究生数学建模项目，并在关键节点等待我的确认。"
```

Create an MIT `LICENSE`. In `THIRD_PARTY_NOTICES.md`, include the 2026 Meta-model-agent MIT notice and state that BZD inspired general review concepts but no unlicensed text/assets are redistributed. `.gitignore` must exclude `.huawei-modeling/`, contest inputs, generated papers, logs, caches, and Python bytecode without excluding repository tests or schemas.

- [ ] **Step 4: Validate the scaffold**

Run: `python -m unittest tests.test_skill_structure -v`

Expected: PASS.

Run in PowerShell: `python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .`

Expected: valid skill with no unfinished placeholders.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md agents/openai.yaml LICENSE THIRD_PARTY_NOTICES.md .gitignore tests/test_skill_structure.py
git commit -m "feat: scaffold Huawei modeling skill"
```

---

### Task 2: Schemas and Safe Workspace Initialization

**Files:**
- Create: `assets/schemas/workflow-state.schema.json`
- Create: `assets/schemas/result-evidence.schema.json`
- Create: `assets/schemas/review-report.schema.json`
- Create: `scripts/common.py`
- Create: `scripts/workspace_init.py`
- Create: `tests/test_workspace_init.py`

**Interfaces:**
- Produces: `sha256_file(path) -> str`, `atomic_write_json(path, payload) -> None`, `append_event(workspace, event, details) -> dict`, and CLI `workspace_init.py --workspace PATH --problem FILE --template FILE --rules FILE --route latex|docx --ai-disclosure required|off`.
- State version: integer `1`; initial stage: `INTAKE`; stage status values: `pending|active|awaiting_approval|complete|rework|required|blocked`.

- [ ] **Step 1: Write failing initialization tests**

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.workspace_init import initialize_workspace


class WorkspaceInitTest(unittest.TestCase):
    def test_initializes_private_workspace_and_hashes_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            problem = root / "problem.pdf"
            template = root / "template.docx"
            rules = root / "rules.pdf"
            problem.write_bytes(b"problem")
            template.write_bytes(b"template")
            rules.write_bytes(b"rules")
            workspace = root / "contest"

            state = initialize_workspace(
                workspace, problem, template, rules, "docx", "required"
            )

            self.assertEqual(state["active_stage"], "INTAKE")
            self.assertEqual(state["route"], "docx")
            self.assertEqual(len(state["inputs"]["problem"]["sha256"]), 64)
            self.assertTrue((workspace / ".huawei-modeling" / "events.jsonl").is_file())
            self.assertFalse((workspace / "problem.pdf").exists())

    def test_rejects_workspace_inside_skill_repository(self):
        with self.assertRaises(ValueError):
            initialize_workspace(Path.cwd() / "contest", Path("p"), Path("t"), Path("r"), "latex", "off")
```

- [ ] **Step 2: Run the tests and verify import failure**

Run: `python -m unittest tests.test_workspace_init -v`

Expected: FAIL with `ModuleNotFoundError` or missing `initialize_workspace`.

- [ ] **Step 3: Implement helpers, schemas, and initializer**

`initialize_workspace` must:

```python
def initialize_workspace(
    workspace: Path,
    problem: Path,
    template: Path,
    rules: Path,
    route: str,
    ai_disclosure: str,
) -> dict:
    """Create a contest workspace, register immutable source metadata, and return state."""
```

Required behavior:

- Resolve paths and reject a workspace inside the Skill repository.
- Require all three source files to exist and be regular files.
- Copy them under `inputs/problem`, `inputs/official-template`, and `inputs/official-rules` with original names.
- Create the directories from the approved runtime tree.
- Record absolute source paths only in `.huawei-modeling/local-sources.json`, which `.gitignore` excludes; public reports use filenames and hashes only.
- Write `state.json`, empty `approvals.json`, and the first `workspace_initialized` event atomically.
- Refuse to overwrite an existing state unless `--force` is provided; `--force` must still preserve an existing workspace by returning an error rather than deleting it.

Schema minimums:

```json
{
  "schema_version": 1,
  "active_stage": "INTAKE",
  "route": "latex",
  "ai_disclosure": "off",
  "stages": {"INTAKE": {"status": "active"}},
  "inputs": {},
  "artifacts": {},
  "stale_artifacts": [],
  "blocking_issues": []
}
```

- [ ] **Step 4: Run initialization tests**

Run: `python -m unittest tests.test_workspace_init -v`

Expected: PASS.

- [ ] **Step 5: Exercise the CLI**

Run: `python scripts/workspace_init.py --help`

Expected: documents every required option and exits 0.

- [ ] **Step 6: Commit**

```bash
git add assets/schemas scripts/common.py scripts/workspace_init.py tests/test_workspace_init.py
git commit -m "feat: initialize evidence-tracked contest workspaces"
```

---

### Task 3: Workflow State Machine, Human Approvals, and Rework

**Files:**
- Create: `scripts/workflow.py`
- Create: `tests/test_workflow.py`
- Create: `tests/helpers.py`
- Create: `references/workflow.md`
- Create: `references/human-checkpoints.md`

**Interfaces:**
- Consumes: state created by `initialize_workspace`.
- Produces: `Workflow.load(workspace)`, `begin(stage)`, `complete(stage, artifacts)`, `request_approval(stage)`, `approve(stage, note)`, `rework(stage, reason)`, `status()` and CLI subcommands with the same names. `tests/helpers.py` produces `make_workflow_fixture(root, through=None, severities=None, stale=None)` for later tests.

- [ ] **Step 1: Write failing transition tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.workflow import TransitionError
from tests.helpers import make_workflow_fixture


class WorkflowTest(unittest.TestCase):
    def test_cannot_skip_stage_or_approval(self):
        with TemporaryDirectory() as tmp:
            workflow = make_workflow_fixture(Path(tmp))
            with self.assertRaises(TransitionError):
                workflow.begin("FORMULATION")
            workflow.complete("INTAKE", ["inputs/problem/problem.pdf"])
            workflow.begin("DISCOVERY")
            workflow.complete("DISCOVERY", ["analysis/sentence-ledger.md"])
            with self.assertRaises(TransitionError):
                workflow.begin("FORMULATION")

    def test_rework_marks_downstream_artifacts_stale(self):
        with TemporaryDirectory() as tmp:
            workflow = make_workflow_fixture(Path(tmp), through="MANUSCRIPT")
            workflow.rework("FORMULATION", "model changed")
            status = workflow.status()
            self.assertEqual(status["active_stage"], "FORMULATION")
            self.assertIn("manuscript/paper.pdf", status["stale_artifacts"])
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_workflow -v`

Expected: FAIL because `scripts.workflow` does not exist.

- [ ] **Step 3: Implement the transition table and approvals**

Use this immutable stage order and checkpoint map:

```python
STAGES = (
    "INTAKE", "DISCOVERY", "FORMULATION", "COMPUTATION",
    "EVIDENCE", "MANUSCRIPT", "REVIEW", "DELIVERY",
)
CHECKPOINTS = {
    "DISCOVERY": "interpretation",
    "FORMULATION": "model_selection",
    "COMPUTATION": "result_trust",
    "REVIEW": "final_draft",
}
```

Completion must hash every declared artifact. Approvals must store `checkpoint`, `decision`, `note`, `timestamp`, and `artifact_hashes`. Beginning a downstream stage must fail if the required approval is missing or its hashes no longer match. `rework(stage)` resets the target stage to `active`, later stages to `pending`, and registers later artifacts as stale without deleting them.

Implement `tests/helpers.py` by creating the minimum state and artifacts through the public `Workflow` methods; it must not add test-only methods to production code. Its optional `severities` value writes a matching review ledger and `stale` extends the state list.

- [ ] **Step 4: Write the human-readable protocols**

`references/workflow.md` must define normal progression, recovery from interruption, stale-artifact behavior, and why manual file edits never substitute for `rework`.

`references/human-checkpoints.md` must give the user, for each checkpoint: files to inspect, decision options, consequences, and the exact evidence that must be present. It must prohibit default approval and allow `approve`, `request changes`, and `stop`.

- [ ] **Step 5: Run workflow tests and CLI snapshot**

Run: `python -m unittest tests.test_workflow -v`

Expected: PASS.

Run: `python scripts/workflow.py --help`

Expected: lists `status`, `begin`, `complete`, `request-approval`, `approve`, and `rework`.

- [ ] **Step 6: Commit**

```bash
git add scripts/workflow.py tests/test_workflow.py tests/helpers.py references/workflow.md references/human-checkpoints.md
git commit -m "feat: add checkpointed workflow state machine"
```

---

### Task 4: Discovery, Modeling, Computation, and Evidence Protocols

**Files:**
- Create: `references/stages/intake.md`
- Create: `references/stages/discovery.md`
- Create: `references/stages/formulation.md`
- Create: `references/stages/computation.md`
- Create: `references/stages/evidence.md`
- Create: `references/evidence-contract.md`
- Create: `tests/test_stage_protocols.py`

**Interfaces:**
- Consumes: active stage, official inputs, and prior-stage artifacts.
- Produces: the exact runtime artifact names in the design, without changing workflow state directly.

- [ ] **Step 1: Write failing protocol-contract tests**

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StageProtocolTest(unittest.TestCase):
    def test_protocols_define_inputs_outputs_and_stop_conditions(self):
        for name in ("intake", "discovery", "formulation", "computation", "evidence"):
            text = (ROOT / "references" / "stages" / f"{name}.md").read_text(encoding="utf-8")
            self.assertIn("## Required inputs", text)
            self.assertIn("## Required outputs", text)
            self.assertIn("## Stop conditions", text)

    def test_formulation_separates_model_mechanism_and_solver(self):
        text = (ROOT / "references" / "stages" / "formulation.md").read_text(encoding="utf-8")
        for term in ("Model identity", "Problem-specific mechanism", "Solver algorithm"):
            self.assertIn(term, text)
```

- [ ] **Step 2: Run tests and verify missing protocols**

Run: `python -m unittest tests.test_stage_protocols -v`

Expected: ERROR for missing files.

- [ ] **Step 3: Write `INTAKE` and `DISCOVERY` protocols**

Required `DISCOVERY` outputs:

- `analysis/sentence-ledger.md`: every problem sentence/paragraph mapped to definitions, conditions, data, task, deliverable, or rule.
- `analysis/task-graph.md`: Mermaid graph with labeled transfers between questions.
- `analysis/data-audit.md`: files, dimensions, fields, units, missingness, duplicates, anomalies, time/space structure, and unavailable evidence.
- `analysis/ambiguity-register.md`: at least two interpretations for material ambiguities, quick tests, adopted interpretation, consequences, and user decision request.

The protocol must forbid treating background paragraphs or submission rules as independent numbered questions.

- [ ] **Step 4: Write `FORMULATION` protocol**

For every question, require at least two genuinely different candidates when feasible and this decision table:

```text
candidate | model identity | mechanism | solver | inputs | outputs | assumptions |
validation | failure conditions | implementation cost | downstream compatibility
```

Require a baseline before enhancement, fair comparison conditions, explicit fallback, and a frozen `modeling/model-decision.md` approved by the user.

- [ ] **Step 5: Write `COMPUTATION` and `EVIDENCE` protocols**

`COMPUTATION` must require executable code, environment capture, deterministic seeds where applicable, baseline comparison, constraint or residual checks, structured results, and no claim without a successful run log.

`EVIDENCE` must require `figure-manifest.json` entries with `claim`, `source_result_ids`, `publish`, `paper_location`, `caption`, and `generation_command`; separate data figures from schematics; and judge whether each figure advances an argument rather than merely looking sophisticated.

- [ ] **Step 6: Write the evidence contract**

Define stable result IDs, model identity fields, rounding rules, source hashes, run records, paper citation links, and stale-evidence behavior. Explicitly state that paper prose cannot overwrite computational truth.

- [ ] **Step 7: Run protocol tests**

Run: `python -m unittest tests.test_stage_protocols -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add references/stages references/evidence-contract.md tests/test_stage_protocols.py
git commit -m "docs: define research and evidence stage protocols"
```

---

### Task 5: Deterministic Evidence and Model-Identity Validation

**Files:**
- Create: `scripts/evidence_check.py`
- Create: `tests/test_evidence_check.py`

**Interfaces:**
- Consumes: `results/result-evidence.json` and `code/code-manifest.json`.
- Produces: `validate_evidence(workspace) -> list[dict]`; an empty list means machine validation passed. Each issue contains `issue_id`, `severity`, `code`, `message`, and `paths`.

- [ ] **Step 1: Write failing validation tests**

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.evidence_check import validate_evidence


class EvidenceCheckTest(unittest.TestCase):
    def test_rejects_solver_used_as_model_identity(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "code").mkdir()
            (root / "results" / "result-evidence.json").write_text(json.dumps({
                "schema_version": 1,
                "results": [{
                    "id": "Q1.objective",
                    "model_identity": "Gurobi",
                    "mechanism": "capacity constraints",
                    "solver_algorithm": "Gurobi",
                    "value": 12.5,
                    "source_files": []
                }]
            }), encoding="utf-8")
            (root / "code" / "code-manifest.json").write_text(
                json.dumps({"schema_version": 1, "files": []}), encoding="utf-8"
            )
            issues = validate_evidence(root)
            self.assertIn("solver_as_model", {item["code"] for item in issues})

    def test_detects_missing_or_mismatched_source_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "code").mkdir()
            source = root / "code" / "q1.py"
            source.write_text("print(1)\n", encoding="utf-8")
            (root / "results" / "result-evidence.json").write_text(json.dumps({
                "schema_version": 1,
                "results": [{
                    "id": "Q1.value",
                    "model_identity": "linear programming",
                    "mechanism": "capacity constraints",
                    "solver_algorithm": "HiGHS",
                    "value": 1,
                    "source_files": [{"path": "code/q1.py", "sha256": "0" * 64}]
                }]
            }), encoding="utf-8")
            (root / "code" / "code-manifest.json").write_text(
                json.dumps({"schema_version": 1, "files": []}), encoding="utf-8"
            )
            codes = {item["code"] for item in validate_evidence(root)}
            self.assertIn("source_hash_mismatch", codes)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_evidence_check -v`

Expected: FAIL because `validate_evidence` does not exist.

- [ ] **Step 3: Implement validation**

Reject:

- duplicate or unstable result IDs;
- missing source files or mismatched hashes;
- absent run command/environment for computed results;
- common solver names used as `model_identity` (`gurobi`, `highs`, `cplex`, `genetic algorithm`, `particle swarm`, `branch and bound`);
- result citations pointing to missing figures or manuscript locations;
- precision declarations inconsistent with stored display values;
- evidence built from stale artifacts registered in workflow state.

Return all findings; do not stop after the first failure. The CLI exits 0 for no P0/P1 issue and 1 otherwise, while still writing `results/evidence-check.json`.

- [ ] **Step 4: Run evidence tests**

Run: `python -m unittest tests.test_evidence_check -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/evidence_check.py tests/test_evidence_check.py
git commit -m "feat: validate result evidence and model identity"
```

---

### Task 6: Manuscript Routes and Shared Consistency Checks

**Files:**
- Create: `references/stages/manuscript.md`
- Create: `references/formats/latex.md`
- Create: `references/formats/docx.md`
- Create: `scripts/manuscript_check.py`
- Create: `scripts/render_audit.py`
- Create: `tests/test_manuscript_check.py`
- Create: `tests/test_render_audit.py`

**Interfaces:**
- Consumes: official template metadata, `result-evidence.json`, figure manifest, manuscript source, and route.
- Produces: `check_manuscript(workspace, route) -> list[dict]`, `audit_rendered_output(workspace, strict=False) -> dict`, `manuscript/manuscript-check.json`, `figures/visual-qa.json`, and `manuscript/pdf-layout-report.json`.

- [ ] **Step 1: Write failing consistency tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from scripts.manuscript_check import check_manuscript


class ManuscriptCheckTest(unittest.TestCase):
    def test_flags_number_not_backed_by_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results").mkdir()
            (root / "manuscript" / "source").mkdir(parents=True)
            (root / "results" / "result-evidence.json").write_text(
                json.dumps({"schema_version": 1, "results": []}), encoding="utf-8"
            )
            (root / "manuscript" / "source" / "paper.md").write_text(
                "最优目标值为 123.456。", encoding="utf-8"
            )
            codes = {i["code"] for i in check_manuscript(root, "docx")}
            self.assertIn("untraced_numeric_claim", codes)
```

`tests/test_render_audit.py` must verify that a missing final PDF produces `status="blocked"`, and that changing the PDF bytes after an audit makes the saved report stale because its `paper_sha256` no longer matches.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_manuscript_check -v`

Expected: FAIL because the checker does not exist.

- [ ] **Step 3: Implement shared manuscript checks**

Check placeholders, internal workflow leakage, missing figure paths, unreferenced publishable figures, model-name inconsistency, numeric claims not represented in evidence display values, missing local symbol definitions, AI disclosure mismatch, and source/template hash mismatch. Allow years, section numbers, citations, and equation labels through explicit exclusions rather than globally accepting all numbers.

- [ ] **Step 4: Write format protocols**

`latex.md` must require official-template comparison, `xelatex`/BibTeX discovery, two-pass compilation after bibliography, relative asset paths, non-forced ordinary floats, PDF page/metadata checks, and a recorded inability when tools are absent.

`docx.md` must require the uploaded official `.doc`/`.docx` as the base, preservation of page settings and styles, 1–3 level table of contents, aspect-ratio-locked figures, LibreOffice export when available, Word-export handoff otherwise, and PDF preview registration before delivery.

Both protocols must prohibit declaring format compliance from source alone.

- [ ] **Step 5: Implement final-render audit adapters**

`audit_rendered_output` must hash the final PDF, discover optional `pdftoppm`, `mutool`, or `magick`, and render pages into a temporary audit directory when one is available. If optional PyMuPDF (`fitz`) is importable, record page sizes, text spans below 9 pt, text blocks outside page bounds, and suspicious intersections; if it is absent, mark those checks `unverified` rather than passing them. Read `*.visual.json` companions when figures provide them and report declared label/font/overlap failures. Save the PDF hash, figure hashes, tool versions, checked pages, findings, and unavailable checks. Strict mode fails on missing/stale reports, text below 9 pt, clipping, unapproved overlap, empty pages, or uninspected pages.

- [ ] **Step 6: Run manuscript and render-audit tests**

Run: `python -m unittest tests.test_manuscript_check tests.test_render_audit -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add references/stages/manuscript.md references/formats scripts/manuscript_check.py scripts/render_audit.py tests/test_manuscript_check.py tests/test_render_audit.py
git commit -m "feat: add evidence-bound LaTeX and DOCX manuscript routes"
```

---

### Task 7: Review Protocol and Root-Cause Issue Ledger

**Files:**
- Create: `references/stages/review.md`
- Create: `scripts/review_ledger.py`
- Create: `tests/test_review_ledger.py`

**Interfaces:**
- Consumes: section reviews, technical findings, manuscript hash, and current problem/task matrix.
- Produces: `merge_issues(existing, incoming) -> list[dict]`, `summarize_issues(issues) -> dict`, and `review/issue-ledger.json`.

- [ ] **Step 1: Write failing deduplication tests**

```python
import unittest
from scripts.review_ledger import merge_issues, summarize_issues


class ReviewLedgerTest(unittest.TestCase):
    def test_same_root_cause_is_not_double_counted(self):
        issues = merge_issues([], [
            {"root_stage": "COMPUTATION", "root_key": "Q2.metric_missing",
             "severity": "P1", "locations": ["abstract"], "message": "摘要指标无证据"},
            {"root_stage": "COMPUTATION", "root_key": "Q2.metric_missing",
             "severity": "P1", "locations": ["results"], "message": "结果指标无法复现"},
        ])
        self.assertEqual(len(issues), 1)
        self.assertEqual(set(issues[0]["locations"]), {"abstract", "results"})
        self.assertEqual(summarize_issues(issues)["P1"], 1)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_review_ledger -v`

Expected: FAIL because the ledger module does not exist.

- [ ] **Step 3: Implement issue merging**

Canonical identity is `root_stage + root_key`. Merge locations, evidence, affected questions, and messages; retain the highest severity using `P0 > P1 > P2 > P3`; never sum duplicate deductions. Require `paper_sha256` for every formal review and reject importing findings from another paper version.

- [ ] **Step 4: Write the review protocol**

Require separate passes for:

1. task coverage and answer completeness;
2. model necessity and data support;
3. assumptions, parameters, units, constraints, derivation, and cross-question flow;
4. execution authenticity, reproducibility, validation, falsification, sensitivity, uncertainty, and feasibility;
5. title, abstract, keywords, problem analysis, symbols, model sections, references, appendix, and AI disclosure;
6. informed-outsider readability and AIGC/template risks;
7. final judge synthesis with 3–5 highest-value revisions.

The rubric must be reconstructed from the current problem before reading the paper for quality. Any numeric score must be labeled internal and must not produce an award promise or reuse CUMCM school/region distributions.

- [ ] **Step 5: Run review tests**

Run: `python -m unittest tests.test_review_ledger -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add references/stages/review.md scripts/review_ledger.py tests/test_review_ledger.py
git commit -m "feat: add deduplicated technical and judge review"
```

---

### Task 8: Stage Gates and Delivery Protocol

**Files:**
- Create: `references/stages/delivery.md`
- Create: `scripts/gate_check.py`
- Create: `tests/test_gate_check.py`

**Interfaces:**
- Consumes: workflow state, stage artifacts, evidence/manuscript/review reports, route, and official-rule snapshot.
- Produces: `check_gate(workspace, stage) -> dict` with `passed`, `issues`, `checked_hashes`, `timestamp`; writes `.huawei-modeling/gates/<stage>.json`.

- [ ] **Step 1: Write failing gate tests**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.gate_check import check_gate
from tests.helpers import make_workflow_fixture


class GateCheckTest(unittest.TestCase):
    def test_review_gate_rejects_p0_and_unaccepted_p1(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="REVIEW", severities=["P0", "P1"])
            result = check_gate(root, "REVIEW")
            self.assertFalse(result["passed"])
            self.assertEqual({i["severity"] for i in result["issues"]}, {"P0", "P1"})

    def test_delivery_rejects_stale_manuscript(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_workflow_fixture(root, through="DELIVERY", stale=["manuscript/paper.pdf"])
            result = check_gate(root, "DELIVERY")
            self.assertFalse(result["passed"])
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_gate_check -v`

Expected: FAIL because `check_gate` does not exist.

- [ ] **Step 3: Implement gate aggregation**

Each gate must check required artifacts, freshness, required report status, matching hashes, checkpoint status, and stage-specific hard failures. A missing optional external tool may create `unverified` only when official compliance does not depend on it; missing final PDF, official template, unresolved P0, unaccepted P1, stale evidence, or mismatched manuscript/review hashes must fail.

- [ ] **Step 4: Write delivery protocol**

Require final PDF existence and nonzero size, registered export/compile command, page count against current official rule snapshot, table of contents depth, anonymity scan, AI disclosure consistency, figure and equation visual inspection, appendix/supporting-material inventory, filename checks, and a `delivery/submission-manifest.json` containing hashes of every file intended for submission.

The protocol must end with a user-facing submission checklist and must never perform the actual contest submission.

- [ ] **Step 5: Run gate tests**

Run: `python -m unittest tests.test_gate_check -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add references/stages/delivery.md scripts/gate_check.py tests/test_gate_check.py
git commit -m "feat: enforce stage and submission gates"
```

---

### Task 9: Synthetic End-to-End Smoke Test and Final Validation

**Files:**
- Create: `scripts/quick_smoke.py`
- Create: `tests/test_end_to_end.py`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: every public script and protocol built in Tasks 1–8.
- Produces: a temporary synthetic contest workspace and a final machine-readable smoke summary; never reads real workspace data.

- [ ] **Step 1: Write the failing end-to-end test**

```python
import unittest
from scripts.quick_smoke import run_smoke


class EndToEndTest(unittest.TestCase):
    def test_synthetic_workflow_reaches_delivery_without_private_artifacts(self):
        summary = run_smoke()
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["final_stage"], "DELIVERY")
        self.assertEqual(summary["private_path_leaks"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m unittest tests.test_end_to_end -v`

Expected: FAIL because `run_smoke` does not exist.

- [ ] **Step 3: Implement the synthetic fixture**

Use `TemporaryDirectory`, three fake official input files, one simple linear model identity, one deterministic Python computation, one structured result, one tiny generated SVG plus its figure-manifest record, a short synthetic manuscript, an empty P0/P1 review ledger, and four explicit test approvals. Exercise every legal transition, every gate, one rework path, and recovery by reloading workflow state from disk.

The smoke test must scan generated public artifacts for the temporary absolute path and fail on leakage. It must not call network services, XeLaTeX, Word, LibreOffice, or DrawIO.

- [ ] **Step 4: Complete the `SKILL.md` operating instructions**

Add:

- initialization and resume commands;
- active-stage reference loading table;
- four checkpoint messages;
- standard versus enhanced computation decision;
- gate and rework commands;
- privacy boundary;
- final-delivery boundary stating that submission itself remains the user's action.

Keep detailed procedures in references rather than duplicating them in `SKILL.md`.

- [ ] **Step 5: Run the complete suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

Run: `python scripts/quick_smoke.py`

Expected: JSON summary with `"passed": true` and `"final_stage": "DELIVERY"`.

Run in PowerShell: `python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .`

Expected: `Skill is valid!` or equivalent success.

Run: `git diff --check`

Expected: no output and exit 0.

- [ ] **Step 6: Inspect repository privacy and provenance**

Run: `rg -n "[A-Za-z]:[\\\\/]|API[_ -]?KEY|TOKEN|TEAM[0-9]{8,}|真实赛题|真实论文" . --glob '!docs/superpowers/**'`

Expected: no matches in distributable Skill files.

Run: `rg -n "BZD|math-model-skills-v2|Meta-model-agent" THIRD_PARTY_NOTICES.md LICENSE SKILL.md references scripts`

Expected: attribution appears only where intended; no copied promotional block or unlicensed BZD content.

- [ ] **Step 7: Commit**

```bash
git add SKILL.md scripts/quick_smoke.py tests/test_end_to_end.py
git commit -m "test: verify complete Huawei modeling workflow"
```

- [ ] **Step 8: Create the delivery branch and pull request**

Push the implementation branch `feat/huawei-modeling-skill`, open a PR titled `Build evidence-gated Huawei Cup modeling skill`, and include:

- the design and plan links;
- completed stages and four checkpoints;
- test commands and fresh results;
- known limitations: mathematical correctness and official submission remain human responsibilities;
- provenance statement for both upstream inspirations.
