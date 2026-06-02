"""Resume -> search profile extraction for the discovery layer.

The discovery flow (Search tab) is driven by the candidate's portfolio rather
than by hand-typed keywords. This module turns the extracted portfolio text into
a compact, structured search profile (suggested titles, core skills, a ready-made
query string) and provides the helpers that the /api/search endpoint uses to:

  1. build the actual query string handed to ``searcher.search_jobs`` (optionally
     refined by user keywords), and
  2. re-rank the returned postings against the profile with a lightweight,
     deterministic relevance heuristic (NOT the heavy per-job LLM evaluator,
     which stays reserved for the single job the user picks to analyze).

LIVE mode mirrors ``ingestion.py``: Gemini 2.5 Flash with Pydantic structured
output and the same tenacity retry policy. MOCK mode returns a fixed profile
derived from ``sample_data`` so the test suite / CI smoke run stay fully offline.
"""
from __future__ import annotations

import logging
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import sample_data
from config import settings

logger = logging.getLogger(__name__)


# Retry policy for Gemini calls — mirrors ingestion.py: up to 3 attempts with
# exponential backoff on transient errors, reraising the final failure.
_gemini_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)


class CandidateSearchProfile(BaseModel):
    """Structured, resume-derived inputs for job discovery."""

    suggested_titles: list[str] = Field(
        description="Job titles this candidate is well suited to search for, "
        "most relevant first (e.g. 'Senior Backend Engineer').",
    )
    core_skills: list[str] = Field(
        description="The candidate's strongest, most marketable skills / "
        "technologies (languages, frameworks, tools, domains).",
    )
    suggested_query: str = Field(
        description="A single, clean job-board search query string built from the "
        "candidate's strongest titles and skills, suited to a keyword search API.",
    )


# Token used to split skills/titles into comparable lowercase words for ranking.
_WORD_RE = re.compile(r"[a-z0-9+#.]+")


def _mock_profile() -> CandidateSearchProfile:
    """Fixed profile derived from the synthetic persona (no API calls).

    Built from ``sample_data`` so MOCK output stays consistent with every other
    agent's mock branch and never references a real individual.
    """
    # Flatten the persona's skill buckets into a deduplicated, ordered list.
    seen: set[str] = set()
    core_skills: list[str] = []
    for bucket in sample_data.SKILLS.values():
        for skill in bucket.split(","):
            s = skill.strip()
            key = s.lower()
            if s and key not in seen:
                seen.add(key)
                core_skills.append(s)

    suggested_titles = [
        sample_data.PERSONA_TITLE,
        "Senior Backend Engineer",
        "AI Engineer",
        "Full Stack Engineer",
    ]

    # A compact query: the lead title plus a handful of the strongest skills.
    query = f"{sample_data.PERSONA_TITLE} {' '.join(core_skills[:6])}".strip()

    return CandidateSearchProfile(
        suggested_titles=suggested_titles,
        core_skills=core_skills,
        suggested_query=query,
    )


def extract_search_profile(
    portfolio_text: str, mock: bool = False
) -> CandidateSearchProfile:
    """Extract a :class:`CandidateSearchProfile` from raw portfolio text.

    LIVE: Gemini 2.5 Flash structured output. MOCK: a fixed persona profile from
    ``sample_data`` (no network), so CI stays offline.
    """
    if mock:
        logger.info("[Mock Mode] Bypassing Gemini search-profile extraction...")
        return _mock_profile()

    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. Please set it in your "
            ".env file."
        )

    if not portfolio_text or not portfolio_text.strip():
        raise ValueError(
            "Cannot extract a search profile from empty portfolio text. Provide a "
            "readable portfolio PDF or supply search keywords instead."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Analyze the following candidate resume / portfolio text and produce a concise
    job-search profile. Identify the job titles this person should search for, the
    strongest and most marketable skills/technologies they have, and a single clean
    search-query string (titles + key skills) suited to a job-board keyword search.

    Focus on what the candidate is genuinely strong in; do not invent skills that
    are not supported by the text.

    PORTFOLIO / RESUME TEXT:
    \"\"\"
    {portfolio_text}
    \"\"\"
    """

    @_gemini_retry
    def _call():
        return client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CandidateSearchProfile,
                system_instruction=(
                    "You are an expert technical recruiter. Build a focused job-search "
                    "profile from the candidate's own resume/portfolio."
                ),
                temperature=0.1,
            ),
        )

    response = _call()
    return response.parsed


def build_search_query(
    profile: CandidateSearchProfile, user_keywords: str | None
) -> str:
    """Compose the final search query string handed to ``search_jobs``.

    - keywords present -> resume-derived query refined by the user's keywords.
    - keywords absent   -> the profile's ``suggested_query`` alone.

    Always returns a clean, single-line query string.
    """
    base = (profile.suggested_query or "").strip()
    keywords = (user_keywords or "").strip()

    if keywords and base:
        combined = f"{base} {keywords}"
    elif keywords:
        combined = keywords
    else:
        combined = base

    # Collapse any whitespace into single spaces for a clean single-line query.
    return re.sub(r"\s+", " ", combined).strip()


def _tokenize(text: str) -> set[str]:
    """Lowercase word/token set used for overlap scoring."""
    return set(_WORD_RE.findall((text or "").lower()))


def _relevance_score(job: dict, profile: CandidateSearchProfile) -> float:
    """Deterministic overlap score of a job vs. the profile (no network, no LLM).

    Combines profile skills + suggested titles into terms, then measures how many
    of those terms appear in the job's title + description. Title matches are
    weighted higher than description matches. Returns a rounded 0-100 fit score.
    """
    terms = [t for t in (profile.core_skills + profile.suggested_titles) if t.strip()]
    if not terms:
        return 0.0

    title_tokens = _tokenize(job.get("title", ""))
    body_text = f"{job.get('title', '')} {job.get('description', '') or job.get('snippet', '')}"
    body_tokens = _tokenize(body_text)

    matched = 0.0
    for term in terms:
        term_tokens = _tokenize(term)
        if not term_tokens:
            continue
        # A term counts as present when all of its tokens appear in the field.
        if term_tokens <= title_tokens:
            matched += 1.0  # full weight for a title hit
        elif term_tokens <= body_tokens:
            matched += 0.5  # half weight for a description-only hit

    # Normalize against the max achievable (every term a title hit) -> 0..100.
    score = (matched / len(terms)) * 100.0
    return round(score, 1)


def rank_jobs(jobs: list[dict], profile: CandidateSearchProfile) -> list[dict]:
    """Return ``jobs`` sorted by descending relevance to ``profile``.

    Each returned job gets a ``fit_score`` (0-100) attached. Sorting is stable, so
    ties preserve the provider's original ordering. Lightweight and deterministic
    — this is the discovery re-rank, NOT the heavy per-job evaluator.
    """
    scored = []
    for job in jobs:
        enriched = dict(job)
        enriched["fit_score"] = _relevance_score(job, profile)
        scored.append(enriched)

    scored.sort(key=lambda j: j["fit_score"], reverse=True)
    return scored
