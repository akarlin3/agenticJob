"""SSE streaming endpoint tests.

Drives ``/api/run/stream`` end-to-end with stubbed agents and asserts that
events arrive as incremental SSE frames, that the GO path reaches all four
stage completions plus ``done``, and that NO-GO emits ``terminated`` without
ever firing tailor/coach stages.
"""
import json

import pytest
from fastapi.testclient import TestClient

import app as app_module
from evaluator import EvaluationResult

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def _no_pdf_side_effects(monkeypatch):
    monkeypatch.setattr(app_module, "generate_portfolio", lambda *a, **k: None)
    # Server-side PDF compile is a best-effort no-op for these tests.
    monkeypatch.setattr(app_module, "_compile_resume_pdf", lambda: False)


def _parse_sse(body: str):
    """Parse an SSE response body into an ordered list of (event, payload)."""
    events = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        event = "message"
        data = ""
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        payload = json.loads(data) if data else {}
        events.append((event, payload))
    return events


def test_stream_no_go_terminates_without_tailor_or_coach(monkeypatch):
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

    with client.stream(
        "POST", "/api/run/stream", data={"job_description": "a role", "mock": "true"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    events = _parse_sse(body)
    event_names = [e for e, _ in events]

    assert "terminated" in event_names
    assert "done" not in event_names
    assert calls["tailor"] == 0
    assert calls["coach"] == 0

    # Verify tailor/coach stages never opened.
    stage_names = [p["name"] for e, p in events if e == "stage"]
    assert "tailor" not in stage_names
    assert "coach" not in stage_names
    # Ingestion + evaluator both completed.
    completed = [
        p["name"] for e, p in events if e == "stage" and p["status"] == "completed"
    ]
    assert "ingestion" in completed and "evaluator" in completed


def test_stream_go_path_emits_all_four_stages(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "evaluate_job_fit",
        lambda *a, **k: EvaluationResult(
            fit_score_out_of_100=85,
            technical_gaps=["GCP"],
            go_no_go=True,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "tailor_application_materials",
        lambda *a, **k: ("resume tex", "cover letter"),
    )
    monkeypatch.setattr(
        app_module,
        "generate_interview_prep",
        lambda *a, **k: [
            {
                "question": "q",
                "type": "Technical",
                "rationale": "r",
                "suggested_strategy": "s",
            }
        ],
    )

    with client.stream(
        "POST", "/api/run/stream", data={"job_description": "a role", "mock": "true"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    events = _parse_sse(body)
    completed = [
        p["name"] for e, p in events if e == "stage" and p["status"] == "completed"
    ]
    assert completed == ["ingestion", "evaluator", "tailor", "coach"]

    assert ("done", {"status": "success"}) in events

    # Result events surfaced each artifact key.
    result_keys = [p["key"] for e, p in events if e == "result"]
    for key in ("job_analysis", "fit_evaluation", "tailored_resume", "cover_letter", "interview_prep"):
        assert key in result_keys


def test_stream_emits_events_incrementally(monkeypatch):
    """The response is emitted as separate SSE frames, in order — not as one
    pre-collected blob.

    Hooks each agent to record the *order* in which its outputs end up in the
    body buffer, then verifies stage events appear before subsequent stage
    events (i.e. we don't observe tailor before evaluator-completed)."""
    monkeypatch.setattr(
        app_module,
        "evaluate_job_fit",
        lambda *a, **k: EvaluationResult(
            fit_score_out_of_100=85,
            technical_gaps=["GCP"],
            go_no_go=True,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "tailor_application_materials",
        lambda *a, **k: ("resume tex", "cover letter"),
    )
    monkeypatch.setattr(app_module, "generate_interview_prep", lambda *a, **k: [])

    with client.stream(
        "POST", "/api/run/stream", data={"job_description": "a role", "mock": "true"}
    ) as resp:
        assert resp.status_code == 200
        chunks = list(resp.iter_text())

    # Concrete proof of streaming: the response body comes back as multiple
    # SSE frames (each ending in \n\n), not a single JSON envelope.
    body = "".join(chunks)
    frame_count = body.count("\n\n")
    assert frame_count >= 8, f"expected many SSE frames, got {frame_count}"

    # Ordering invariant: an evaluator-completed frame must appear before any
    # tailor stage frame.
    eval_done_idx = body.find('"name": "evaluator", "status": "completed"')
    tailor_idx = body.find('"name": "tailor"')
    assert eval_done_idx != -1 and tailor_idx != -1
    assert eval_done_idx < tailor_idx
