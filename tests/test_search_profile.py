"""Offline unit tests for the resume -> search-profile discovery layer.

No network, no API keys — exercises the mock profile extraction, the query
composition rules, and the deterministic ranking heuristic.
"""
import io

import pytest
from fastapi.testclient import TestClient

import sample_data
from search_profile import (
    CandidateSearchProfile,
    extract_search_profile,
    build_search_query,
    rank_jobs,
)
from app import app

client = TestClient(app)


class TestExtractSearchProfileMock:
    def test_returns_valid_profile_from_persona(self):
        profile = extract_search_profile("", mock=True)
        assert isinstance(profile, CandidateSearchProfile)
        assert profile.suggested_titles
        assert profile.core_skills
        assert profile.suggested_query.strip()
        # Persona-derived, never a real identity.
        assert sample_data.PERSONA_TITLE in profile.suggested_titles
        assert "Python" in profile.core_skills


class TestBuildSearchQuery:
    def _profile(self):
        return CandidateSearchProfile(
            suggested_titles=["Backend Engineer"],
            core_skills=["Python", "FastAPI"],
            suggested_query="Backend Engineer Python FastAPI",
        )

    def test_resume_only(self):
        # Keywords absent -> suggested_query alone.
        q = build_search_query(self._profile(), None)
        assert q == "Backend Engineer Python FastAPI"
        # Empty string keywords behave the same as None.
        assert build_search_query(self._profile(), "   ") == q

    def test_resume_plus_keywords(self):
        # Keywords present -> resume query refined by the keywords.
        q = build_search_query(self._profile(), "remote startup")
        assert q == "Backend Engineer Python FastAPI remote startup"

    def test_keywords_only_empty_profile(self):
        empty = CandidateSearchProfile(
            suggested_titles=[], core_skills=[], suggested_query=""
        )
        assert build_search_query(empty, "data engineer") == "data engineer"

    @staticmethod
    def _assert_plain(query: str):
        # JSearch / Adzuna have no boolean support: the query must be plain.
        assert "AND" not in query
        assert " OR " not in query
        assert "(" not in query
        assert ")" not in query
        assert '"' not in query
        # Broad + short: a handful of plain, space-separated words.
        assert query == " ".join(query.split())
        assert len(query.split()) <= 6

    def test_outputs_are_always_plain_and_short(self):
        # resume-only, resume+keywords, and keywords-only all stay plain & short.
        self._assert_plain(build_search_query(self._profile(), None))
        self._assert_plain(build_search_query(self._profile(), "remote startup"))
        empty = CandidateSearchProfile(
            suggested_titles=[], core_skills=[], suggested_query=""
        )
        self._assert_plain(build_search_query(empty, "data engineer"))

    def test_boolean_query_is_flattened_regression(self):
        # The reported failing case: the LLM emits a boolean expression. It must
        # be flattened to a short plain string, never passed through verbatim.
        boolean = (
            '(Computational Physicist OR Data Scientist) AND '
            '(Python OR MATLAB) AND ("Medical Imaging" OR "Signal Processing")'
        )
        profile = CandidateSearchProfile(
            suggested_titles=["Computational Physicist", "Data Scientist"],
            core_skills=["Python", "MATLAB", "Medical Imaging"],
            suggested_query=boolean,
        )
        q = build_search_query(profile, None)
        self._assert_plain(q)
        # The leading title survives the flattening (recall is preserved).
        assert q.startswith("Computational Physicist")

    def test_keywords_with_boolean_are_stripped(self):
        # Defensive: even boolean-ish user keywords are flattened.
        empty = CandidateSearchProfile(
            suggested_titles=[], core_skills=[], suggested_query=""
        )
        q = build_search_query(empty, '(Backend OR Frontend) AND "Python"')
        self._assert_plain(q)
        assert q == "Backend Frontend Python"

    def test_mock_profile_query_is_plain(self):
        # MOCK output must also be a short plain phrase, not a boolean expression.
        profile = extract_search_profile("", mock=True)
        self._assert_plain(profile.suggested_query)
        assert profile.suggested_query  # non-empty


class TestRankJobs:
    def test_higher_overlap_sorts_first(self):
        profile = CandidateSearchProfile(
            suggested_titles=["Python Backend Engineer"],
            core_skills=["Python", "FastAPI", "PostgreSQL"],
            suggested_query="Python Backend Engineer",
        )
        strong = {
            "title": "Python Backend Engineer",
            "description": "Build FastAPI services backed by PostgreSQL.",
        }
        weak = {
            "title": "Marketing Coordinator",
            "description": "Manage social media campaigns and email outreach.",
        }
        ranked = rank_jobs([weak, strong], profile)
        assert ranked[0]["title"] == "Python Backend Engineer"
        assert ranked[0]["fit_score"] > ranked[1]["fit_score"]
        # Every job carries an attached numeric fit score.
        assert all(isinstance(j["fit_score"], (int, float)) for j in ranked)

    def test_empty_profile_scores_zero(self):
        empty = CandidateSearchProfile(
            suggested_titles=[], core_skills=[], suggested_query=""
        )
        ranked = rank_jobs([{"title": "Anything", "description": "x"}], empty)
        assert ranked[0]["fit_score"] == 0.0


def _tiny_pdf_bytes() -> bytes:
    # Minimal valid-enough PDF: starts with the magic bytes the upload guard checks.
    return b"%PDF-1.4\n%mock portfolio\n"


class TestSearchEndpoint:
    def test_resume_only_returns_ranked_results(self, tmp_path, monkeypatch):
        # Run from a clean dir so no stray master_portfolio.pdf interferes; the
        # uploaded portfolio supplies the "portfolio available" signal.
        monkeypatch.chdir(tmp_path)
        resp = client.post(
            "/api/search",
            data={"query": "", "location": "Remote", "mock": "true"},
            files={"portfolio": ("resume.pdf", _tiny_pdf_bytes(), "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["query"]  # the resume-derived query string is surfaced
        assert isinstance(body["jobs"], list) and body["jobs"]
        # Results are ranked: each carries a fit score, sorted descending.
        scores = [j["fit_score"] for j in body["jobs"]]
        assert scores == sorted(scores, reverse=True)

    def test_no_portfolio_no_keywords_returns_400(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # ensure no persisted master_portfolio.pdf
        resp = client.post(
            "/api/search",
            data={"query": "", "location": "", "mock": "true"},
        )
        assert resp.status_code == 400
        assert "portfolio" in resp.json()["detail"].lower()
