"""Pipeline control-flow tests via the FastAPI app (offline, mock mode).

Verifies the Go/No-Go branch: when the evaluator returns ``go_no_go=False`` the
pipeline terminates *without* invoking the tailor or coach agents.
"""
import pytest
from fastapi.testclient import TestClient

import app as app_module
from evaluator import EvaluationResult

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def _no_pdf_side_effects(monkeypatch):
    # Avoid writing a real PDF during the test.
    monkeypatch.setattr(app_module, "generate_portfolio", lambda *a, **k: None)


def test_no_go_terminates_without_tailor_or_coach(monkeypatch):
    calls = {"tailor": 0, "coach": 0}

    monkeypatch.setattr(
        app_module,
        "evaluate_job_fit",
        lambda *a, **k: EvaluationResult(
            fit_score_out_of_100=40,
            technical_gaps=["everything"],
            go_no_go=False,
        ),
    )

    def _spy_tailor(*a, **k):
        calls["tailor"] += 1
        return ("resume", "letter")

    def _spy_coach(*a, **k):
        calls["coach"] += 1
        return []

    monkeypatch.setattr(app_module, "tailor_application_materials", _spy_tailor)
    monkeypatch.setattr(app_module, "generate_interview_prep", _spy_coach)

    resp = client.post("/api/run", data={"job_description": "a role", "mock": "true"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "terminated"
    assert body["tailored_resume"] is None
    assert body["interview_prep"] is None
    assert calls["tailor"] == 0, "Tailor must not run on a No-Go decision"
    assert calls["coach"] == 0, "Coach must not run on a No-Go decision"


def test_go_runs_full_pipeline(monkeypatch):
    calls = {"tailor": 0, "coach": 0}

    monkeypatch.setattr(
        app_module,
        "evaluate_job_fit",
        lambda *a, **k: EvaluationResult(
            fit_score_out_of_100=85,
            technical_gaps=["GCP"],
            go_no_go=True,
        ),
    )

    def _spy_tailor(*a, **k):
        calls["tailor"] += 1
        return ("resume tex", "cover letter")

    def _spy_coach(*a, **k):
        calls["coach"] += 1
        return [
            {
                "question": "q",
                "type": "Technical",
                "rationale": "r",
                "suggested_strategy": "s",
            }
        ]

    monkeypatch.setattr(app_module, "tailor_application_materials", _spy_tailor)
    monkeypatch.setattr(app_module, "generate_interview_prep", _spy_coach)

    resp = client.post("/api/run", data={"job_description": "a role", "mock": "true"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert calls["tailor"] == 1
    assert calls["coach"] == 1
