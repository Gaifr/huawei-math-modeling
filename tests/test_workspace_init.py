import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.common import append_event, atomic_write_json, sha256_file
from scripts.workspace_init import initialize_workspace


class WorkspaceInitTest(unittest.TestCase):
    def test_initializes_private_workspace_and_hashes_inputs(self):
        """A missing input copy or hash registration would make this fail."""
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
            self.assertTrue(
                (workspace / "inputs" / "problem" / "problem.pdf").is_file()
            )

    def test_initialization_keeps_absolute_source_paths_out_of_public_state(self):
        """Writing a source path into state.json or events.jsonl is a privacy bug."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            problem = root / "problem.pdf"
            template = root / "template.docx"
            rules = root / "rules.pdf"
            for source in (problem, template, rules):
                source.write_bytes(b"official")
            workspace = root / "contest"

            initialize_workspace(workspace, problem, template, rules, "latex", "off")

            state_text = (workspace / ".huawei-modeling" / "state.json").read_text(
                encoding="utf-8"
            )
            event_text = (workspace / ".huawei-modeling" / "events.jsonl").read_text(
                encoding="utf-8"
            )
            local_sources = json.loads(
                (workspace / ".huawei-modeling" / "local-sources.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn(str(problem.resolve()), state_text)
            self.assertNotIn(str(problem.resolve()), event_text)
            self.assertEqual(local_sources["problem"]["source_path"], str(problem.resolve()))

    def test_rejects_workspace_inside_skill_repository(self):
        """Allowing a contest workspace in the skill repository would leak materials."""
        with self.assertRaises(ValueError):
            initialize_workspace(
                Path.cwd() / "contest", Path("p"), Path("t"), Path("r"), "latex", "off"
            )

    def test_rejects_missing_or_non_file_source_before_creating_workspace(self):
        """Creating an intake workspace from incomplete official materials is invalid."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.docx"
            rules = root / "rules.pdf"
            template.write_bytes(b"template")
            rules.write_bytes(b"rules")
            workspace = root / "contest"

            with self.assertRaises(ValueError):
                initialize_workspace(
                    workspace, root / "missing.pdf", template, rules, "latex", "off"
                )

            self.assertFalse(workspace.exists())

    def test_refuses_existing_workspace_even_when_force_is_requested(self):
        """Force must never delete or overwrite an existing contest workspace."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            problem = root / "problem.pdf"
            template = root / "template.docx"
            rules = root / "rules.pdf"
            for source in (problem, template, rules):
                source.write_bytes(b"official")
            workspace = root / "contest"
            workspace.mkdir()
            marker = workspace / "keep.txt"
            marker.write_text("do not delete", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                initialize_workspace(
                    workspace, problem, template, rules, "latex", "off", force=True
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "do not delete")

    def test_common_helpers_write_durable_json_and_append_event(self):
        """A partial JSON write or non-append event log would break recovery."""
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "state.json"
            atomic_write_json(target, {"schema_version": 1})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"schema_version": 1})

            source = workspace / "source.bin"
            source.write_bytes(b"hash me")
            self.assertEqual(len(sha256_file(source)), 64)

            first = append_event(workspace, "first", {"sequence": 1})
            second = append_event(workspace, "second", {"sequence": 2})
            events = [
                json.loads(line)
                for line in (workspace / ".huawei-modeling" / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual([event["event"] for event in events], ["first", "second"])
            self.assertEqual(first["details"]["sequence"], 1)
            self.assertEqual(second["details"]["sequence"], 2)


if __name__ == "__main__":
    unittest.main()
