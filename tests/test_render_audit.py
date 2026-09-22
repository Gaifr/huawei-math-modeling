"""Tests for the final-size render audit."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.render_audit import audit_rendered_output, report_is_fresh


def _pdf_with_content(content: bytes) -> bytes:
    """Build a small, structurally valid single-page PDF around *content*."""
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(len(bodies) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(out)


def minimal_pdf(text: str = "Synthetic paper") -> bytes:
    """Build a small, structurally valid single-page PDF without dependencies."""
    return _pdf_with_content(f"BT /F1 12 Tf 72 760 Td ({text}) Tj ET\n".encode("ascii"))


def overlapping_pdf() -> bytes:
    """Single page with two text runs drawn at the same position."""
    return _pdf_with_content(
        b"BT /F1 12 Tf 72 700 Td (AAAA) Tj ET\n"
        b"BT /F1 12 Tf 72 700 Td (BBBBBBBB) Tj ET\n"
    )


def write_paper(root: Path, payload: bytes | None = None) -> Path:
    (root / "manuscript").mkdir(parents=True, exist_ok=True)
    paper = root / "manuscript" / "paper.pdf"
    paper.write_bytes(payload if payload is not None else minimal_pdf())
    return paper


class RenderAuditTest(unittest.TestCase):
    def test_missing_final_pdf_is_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manuscript").mkdir()
            report = audit_rendered_output(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(
                (root / "manuscript" / "pdf-layout-report.json").is_file()
            )

    def test_changed_pdf_makes_saved_report_stale(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = write_paper(root)
            first = audit_rendered_output(root)
            self.assertIn(first["status"], {"pass", "warn"})
            saved = json.loads(
                (root / "manuscript" / "pdf-layout-report.json").read_text(encoding="utf-8")
            )
            self.assertTrue(report_is_fresh(saved, root))

            paper.write_bytes(paper.read_bytes() + b"% revision\n")
            self.assertFalse(report_is_fresh(saved, root))

    def test_report_records_hash_pages_and_unavailable_checks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paper(root)
            report = audit_rendered_output(root)
            self.assertIn("paper_sha256", report)
            self.assertEqual(len(report["paper_sha256"]), 64)
            self.assertTrue(report["checked_pages"] or report["uninspected_pages"])
            self.assertEqual(
                len(report["checked_pages"]) + len(report["uninspected_pages"]),
                report["page_count"],
            )
            self.assertIn("figure_hashes", report)
            self.assertIn("unavailable", report)
            self.assertIn("toc_max_depth", report)

    def test_strict_mode_rejects_missing_pdf(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manuscript").mkdir()
            report = audit_rendered_output(root, strict=True)
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["passed"])

    def test_audit_writes_visual_qa_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paper(root)
            audit_rendered_output(root)
            self.assertTrue((root / "figures" / "visual-qa.json").is_file())

    def test_missing_pdf_library_leaves_pages_uninspected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paper(root)
            with patch("importlib.util.find_spec", return_value=None):
                report = audit_rendered_output(root)
            self.assertEqual(report["checked_pages"], [])
            self.assertEqual(report["uninspected_pages"], [1])
            self.assertTrue(
                any("pdf_layout_checks" in item for item in report["unavailable"])
            )

    def test_strict_mode_fails_on_uninspected_pages(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paper(root)
            with patch("importlib.util.find_spec", return_value=None):
                report = audit_rendered_output(root, strict=True)
            self.assertFalse(report["passed"])
            self.assertIn("uninspected_pages", {i["code"] for i in report["findings"]})

    @unittest.skipUnless(
        importlib.util.find_spec("fitz"), "requires PyMuPDF for per-span geometry"
    )
    def test_detects_overlapping_text(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paper(root, overlapping_pdf())
            report = audit_rendered_output(root)
            self.assertIn("text_overlap", {i["code"] for i in report["findings"]})


if __name__ == "__main__":
    unittest.main()
