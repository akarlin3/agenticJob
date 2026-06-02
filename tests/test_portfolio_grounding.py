"""Regression guards for portfolio grounding (v1.0 blocking fix).

These cover the LIVE-mode path that the mock tests cannot reach: that the real
uploaded portfolio text actually reaches the tailor + coach agents' prompts, and
that the hiring company from JobAnalysis flows into the generated cover letter.

The Anthropic client is stubbed with a fake that captures the prompt it receives
and echoes it back as the generated materials, so we can assert on both the
*input* (prompt grounding) and the *output* (company naming) without any network.
"""
import json

import pytest

import tailor as tailor_module
import coach as coach_module
from ingestion import JobAnalysis


# A portfolio-text fingerprint that does NOT appear in the synthetic persona, so
# its presence in the prompt proves the real portfolio reached the agent.
REAL_PORTFOLIO_TEXT = (
    "Dakota Rivera — Principal Reliability Engineer at Northwind Telemetry. "
    "Led incident-response tooling reducing MTTR by 47% across 12 services."
)
REAL_FINGERPRINT = "Northwind Telemetry"
COMPANY = "Globex Dynamics"


class _FakeToolUseBlock:
    """Mimics an anthropic tool_use content block."""

    type = "tool_use"

    def __init__(self, payload: dict):
        self.input = payload


class _FakeResponse:
    def __init__(self, payload: dict):
        self.content = [_FakeToolUseBlock(payload)]


class _CapturingClient:
    """Stub anthropic.Anthropic that records the prompt and echoes inputs.

    ``captured`` is shared with the test so it can inspect the exact ``system``
    and user ``prompt`` strings the agent built. The echoed tool output embeds
    the captured user prompt, so assertions can check that grounding/company
    text both entered the prompt and surfaced in the materials.
    """

    def __init__(self, captured: dict, tool_name: str):
        self._captured = captured
        self._tool_name = tool_name
        self.messages = self

    def create(self, *, model, max_tokens, system, messages, tools, tool_choice):
        prompt = messages[0]["content"]
        self._captured["system"] = system
        self._captured["prompt"] = prompt
        if self._tool_name == "generate_application_materials":
            return _FakeResponse(
                {
                    "latex_resume": r"\documentclass{article}\begin{document}"
                    + prompt
                    + r"\end{document}",
                    "markdown_cover_letter": "Cover letter echo:\n" + prompt,
                }
            )
        # output_interview_prep
        return _FakeResponse(
            {
                "questions": [
                    {
                        "question": "Echo: " + prompt[:80],
                        "type": "Technical",
                        "rationale": prompt,
                        "suggested_strategy": "strategy",
                    }
                ]
            }
        )


@pytest.fixture
def _captured():
    return {}


def _install_fake(monkeypatch, module, tool_name, captured):
    monkeypatch.setattr(module.settings, "anthropic_api_key", "test-key")

    def _factory(*args, **kwargs):
        return _CapturingClient(captured, tool_name)

    monkeypatch.setattr(module.anthropic, "Anthropic", _factory)


class TestTailorLivePathGrounding:
    def test_portfolio_text_reaches_tailor_prompt(self, monkeypatch, _captured):
        _install_fake(monkeypatch, tailor_module, "generate_application_materials", _captured)

        resume, letter = tailor_module.tailor_application_materials(
            job_details_json="{}",
            gap_analysis_json="{}",
            portfolio_text=REAL_PORTFOLIO_TEXT,
            company=COMPANY,
            mock=False,
        )

        # Regression guard: the real portfolio text must be in the prompt sent
        # to the LLM, and the synthetic persona bio must NOT be.
        assert REAL_FINGERPRINT in _captured["prompt"]
        assert tailor_module.sample_data.PERSONA_BIO not in _captured["prompt"]

    def test_company_appears_in_cover_letter(self, monkeypatch, _captured):
        _install_fake(monkeypatch, tailor_module, "generate_application_materials", _captured)

        resume, letter = tailor_module.tailor_application_materials(
            job_details_json="{}",
            gap_analysis_json="{}",
            portfolio_text=REAL_PORTFOLIO_TEXT,
            company=COMPANY,
            mock=False,
        )

        # Company name flows into the prompt and (via the echoing stub) the letter.
        assert COMPANY in _captured["prompt"]
        assert COMPANY in letter

    def test_missing_company_uses_graceful_fallback(self, monkeypatch, _captured):
        _install_fake(monkeypatch, tailor_module, "generate_application_materials", _captured)

        tailor_module.tailor_application_materials(
            job_details_json="{}",
            gap_analysis_json="{}",
            portfolio_text=REAL_PORTFOLIO_TEXT,
            company="",
            mock=False,
        )

        # No empty-string employer leaks into the letter; a friendly fallback is used.
        assert "the hiring company" in _captured["prompt"]

    def test_empty_portfolio_falls_back_to_persona(self, monkeypatch, _captured):
        _install_fake(monkeypatch, tailor_module, "generate_application_materials", _captured)

        tailor_module.tailor_application_materials(
            job_details_json="{}",
            gap_analysis_json="{}",
            portfolio_text="",
            company=COMPANY,
            mock=False,
        )

        # With no real portfolio text, the synthetic persona bio is the fallback.
        assert tailor_module.sample_data.PERSONA_BIO in _captured["prompt"]


class TestCoachLivePathGrounding:
    def test_portfolio_text_reaches_coach_prompt(self, monkeypatch, _captured):
        _install_fake(monkeypatch, coach_module, "output_interview_prep", _captured)

        questions = coach_module.generate_interview_prep(
            job_details_json="{}",
            gap_analysis_json="{}",
            portfolio_text=REAL_PORTFOLIO_TEXT,
            company=COMPANY,
            mock=False,
        )

        assert REAL_FINGERPRINT in _captured["prompt"]
        assert COMPANY in _captured["system"]
        assert isinstance(questions, list) and questions


class TestJobAnalysisCompanyField:
    def test_company_round_trips_through_schema(self):
        analysis = JobAnalysis(
            role_title="Staff Engineer",
            company="Globex Dynamics",
            location="Remote",
            required_tech_stack=["Python"],
            core_responsibilities=["Build things"],
            domain_expertise=["SaaS"],
        )
        dumped = json.loads(analysis.model_dump_json())
        assert dumped["company"] == "Globex Dynamics"
        assert dumped["location"] == "Remote"

        # Round-trip back into the model.
        restored = JobAnalysis.model_validate(dumped)
        assert restored.company == "Globex Dynamics"

    def test_company_defaults_to_empty_string(self):
        # Older payloads without company/location must still validate.
        analysis = JobAnalysis(
            role_title="Engineer",
            required_tech_stack=["Python"],
            core_responsibilities=["x"],
            domain_expertise=["y"],
        )
        assert analysis.company == ""
        assert analysis.location == ""
