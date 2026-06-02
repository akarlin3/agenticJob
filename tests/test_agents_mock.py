"""Offline unit tests for each agent's ``mock=True`` branch.

These confirm the mock branches return schema-valid objects without network or
keys, and act as a regression guard against the old fabricated identity creeping
back in: every mock payload must reference the synthetic persona, never a real
name.
"""
import json

import sample_data
from ingestion import ingest_job_description, JobAnalysis
from evaluator import evaluate_job_fit, EvaluationResult
from tailor import tailor_application_materials
from coach import generate_interview_prep

# Strings that must never reappear anywhere in generated output.
FORBIDDEN = ["Avery Karlin", "Cognitive Orchestration", "FinTech Core", "akarlin3@"]


def _assert_no_real_identity(text: str):
    for token in FORBIDDEN:
        assert token not in text, f"Fabricated identity leaked: {token!r}"


class TestIngestionMock:
    def test_returns_valid_job_analysis(self):
        result = ingest_job_description("any jd", mock=True)
        assert isinstance(result, JobAnalysis)
        assert result.role_title
        assert result.required_tech_stack


class TestEvaluatorMock:
    def test_returns_valid_evaluation(self):
        result = evaluate_job_fit("{}", mock=True)
        assert isinstance(result, EvaluationResult)
        assert 0 <= result.fit_score_out_of_100 <= 100
        assert isinstance(result.go_no_go, bool)


class TestTailorMock:
    def test_returns_persona_consistent_materials(self):
        # Even when a real portfolio + company are supplied, MOCK mode must keep
        # returning the synthetic persona output unchanged (CI runs offline).
        resume, letter = tailor_application_materials(
            "{}",
            "{}",
            portfolio_text="Real Person at Real Corp — confidential bio.",
            company="Real Corp",
            mock=True,
        )
        assert sample_data.PERSONA_NAME in resume
        assert sample_data.PERSONA_NAME in letter
        assert sample_data.COMPANY_CURRENT in resume
        # The supplied real portfolio/company must NOT leak into mock output.
        assert "Real Corp" not in resume and "Real Corp" not in letter
        _assert_no_real_identity(resume)
        _assert_no_real_identity(letter)

    def test_resume_is_compilable_latex_skeleton(self):
        resume, _ = tailor_application_materials("{}", "{}", mock=True)
        assert r"\documentclass" in resume
        assert r"\begin{document}" in resume
        assert r"\end{document}" in resume


class TestCoachMock:
    def test_returns_schema_valid_questions(self):
        questions = generate_interview_prep("{}", "{}", mock=True)
        assert isinstance(questions, list) and questions
        for q in questions:
            assert set(q) >= {"question", "type", "rationale", "suggested_strategy"}
            assert q["type"] in ("Technical", "Behavioral")

    def test_references_synthetic_persona_not_real_identity(self):
        questions = generate_interview_prep(
            "{}",
            "{}",
            portfolio_text="Real Person at Real Corp — confidential bio.",
            company="Real Corp",
            mock=True,
        )
        blob = json.dumps(questions)
        assert "Real Corp" not in blob
        assert sample_data.COMPANY_CURRENT in blob or sample_data.COMPANY_PREVIOUS in blob
        _assert_no_real_identity(blob)
