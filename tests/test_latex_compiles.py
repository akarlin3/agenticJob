"""Compile the mock tailored LaTeX resume with Tectonic.

Skipped automatically when Tectonic isn't installed, so local `pytest -q`
runs cleanly without a LaTeX toolchain. CI installs Tectonic on the 3.12
matrix entry so this test runs there.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from tailor import tailor_application_materials


@pytest.mark.skipif(
    shutil.which("tectonic") is None,
    reason="tectonic not installed; skipping LaTeX compile test",
)
def test_mock_latex_resume_compiles(tmp_path: Path):
    resume_tex, _ = tailor_application_materials("{}", "{}", mock=True)

    tex_path = tmp_path / "tailored_resume.tex"
    tex_path.write_text(resume_tex, encoding="utf-8")

    result = subprocess.run(
        ["tectonic", "--keep-logs", "--outdir", str(tmp_path), str(tex_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Tectonic failed to compile mock resume.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    pdf_path = tmp_path / "tailored_resume.pdf"
    assert pdf_path.exists() and pdf_path.stat().st_size > 0, "PDF was not produced"
