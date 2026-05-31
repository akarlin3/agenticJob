"""Offline unit tests for the discovery layer (searcher.py).

No network, no API keys — exercises the pure-logic helpers, the mock search
path, schema validation, and the malformed-row-dropped behaviour.
"""
import pytest

from searcher import _dedupe_key, _truncate, search_jobs, DiscoveredJob


class TestDedupeKey:
    def test_collapses_case_and_whitespace_variants(self):
        a = {"title": "Senior  Engineer", "company": "Example Labs"}
        b = {"title": "senior engineer", "company": "EXAMPLE LABS"}
        assert _dedupe_key(a) == _dedupe_key(b)

    def test_distinct_postings_differ(self):
        a = {"title": "Backend Engineer", "company": "Example Labs"}
        b = {"title": "Frontend Engineer", "company": "Example Labs"}
        assert _dedupe_key(a) != _dedupe_key(b)

    def test_handles_missing_fields(self):
        # Should not raise on absent keys.
        assert _dedupe_key({}) == "::"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("hello world", limit=320) == "hello world"

    def test_long_text_is_truncated_and_ellipsized(self):
        text = "x" * 500
        out = _truncate(text, limit=100)
        assert len(out) <= 100
        assert out.endswith("…")

    def test_collapses_internal_whitespace(self):
        assert _truncate("a   b\n\tc") == "a b c"

    def test_handles_none(self):
        assert _truncate(None) == ""


class TestSearchJobsMock:
    def test_returns_schema_valid_discovered_jobs(self):
        jobs = search_jobs("Python Engineer", "Anytown", ["LinkedIn"], mock=True)
        assert len(jobs) > 0
        for j in jobs:
            # Round-trips through the Pydantic schema without error.
            DiscoveredJob(**j)
            assert j["url"].startswith("http")
            assert j["description"]

    def test_mock_path_needs_no_keys(self, monkeypatch):
        # Ensure no provider env vars are required for the mock path.
        for var in ("RAPIDAPI_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert search_jobs("x", "y", mock=True)


class TestMalformedRowHandling:
    def test_malformed_row_is_dropped_not_fatal(self, monkeypatch):
        """A row missing required fields should be skipped, not crash search."""
        good = {
            "title": "Engineer",
            "company": "Example Labs",
            "location": "Anytown",
            "source": "LinkedIn",
            "url": "https://example.com/jobs/1",
            "snippet": "snippet",
            "description": "full description",
        }
        # 'url' is required by DiscoveredJob; omit it to force a validation drop.
        bad = {"title": "Broken", "company": "NoUrl Co"}

        # Mark a provider as configured so the live path proceeds past the
        # "no provider configured" guard and exercises the monkeypatched calls.
        monkeypatch.setenv("RAPIDAPI_KEY", "test-dummy")
        monkeypatch.setattr("searcher._search_jsearch", lambda *a, **k: [good, bad])
        monkeypatch.setattr("searcher._search_adzuna", lambda *a, **k: [])

        result = search_jobs("q", "loc", mock=False)
        assert len(result) == 1
        assert result[0]["company"] == "Example Labs"


class TestNoProviderConfigured:
    def test_live_path_raises_when_no_provider_env_vars_set(self, monkeypatch):
        """Live path must fail fast with an actionable RuntimeError, not return []."""
        for var in ("RAPIDAPI_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="No job search provider configured"):
            search_jobs("python", "NYC", mock=False)
