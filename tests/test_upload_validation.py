"""Tests for the `/api/run` portfolio upload validation."""
import io

import pytest
from fastapi.testclient import TestClient

import app as app_module
from config import settings
from evaluator import EvaluationResult

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def _stub_agents(monkeypatch):
    # Keep the pipeline offline and cheap — we're only exercising the upload path.
    monkeypatch.setattr(app_module, "generate_portfolio", lambda *a, **k: None)
    monkeypatch.setattr(
        app_module,
        "evaluate_job_fit",
        lambda *a, **k: EvaluationResult(
            fit_score_out_of_100=40,
            technical_gaps=["everything"],
            go_no_go=False,
        ),
    )


def test_non_pdf_upload_is_rejected():
    resp = client.post(
        "/api/run",
        data={"job_description": "a role", "mock": "true"},
        files={"portfolio": ("not-a-pdf.pdf", io.BytesIO(b"hello world"), "application/pdf")},
    )
    assert resp.status_code == 400
    assert "not a valid PDF" in resp.json()["detail"]


def test_oversize_upload_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 32)
    oversize = b"%PDF-" + b"\x00" * 1024
    resp = client.post(
        "/api/run",
        data={"job_description": "a role", "mock": "true"},
        files={"portfolio": ("big.pdf", io.BytesIO(oversize), "application/pdf")},
    )
    assert resp.status_code == 413
    assert "maximum size" in resp.json()["detail"]


def test_valid_pdf_upload_runs_pipeline():
    fake_pdf = b"%PDF-1.4\n%fake but valid header for the magic-byte check\n"
    resp = client.post(
        "/api/run",
        data={"job_description": "a role", "mock": "true"},
        files={"portfolio": ("ok.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Evaluator is stubbed to return No-Go, so the pipeline should terminate cleanly.
    assert body["status"] == "terminated"
