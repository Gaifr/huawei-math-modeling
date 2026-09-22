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
