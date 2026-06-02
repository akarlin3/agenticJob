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
        description="A SHORT, PLAIN job-board search query: the single best-fit "
        "target job title only (e.g. 'Computational Physicist'), 2-5 words. NO "
        "boolean operators (AND/OR), NO parentheses, NO quotes. Keyword job-board "
        "APIs treat these as literal text and return nothing; recall comes from a "
        "broad query, precision from re-ranking against titles + skills.",
    )


# Token used to split skills/titles into comparable lowercase words for ranking.
_WORD_RE = re.compile(r"[a-z0-9+#.]+")

# Boolean syntax that JSearch / Adzuna treat as literal text rather than search
# operators. We strip these defensively so a stray boolean query still degrades
# to a plain keyword string. Cap the final query to a handful of words: a broad
# query maximizes recall, and rank_jobs() supplies the precision.
_BOOLEAN_TOKENS = {"and", "or", "not"}
_QUERY_MAX_WORDS = 6


def _plainify_query(text: str) -> str:
    """Reduce ``text`` to a short, plain keyword string.

    Removes boolean operators (AND/OR/NOT), parentheses and double quotes,
    collapses whitespace, and caps the result at ``_QUERY_MAX_WORDS`` words.
    Keyword job-board APIs have no boolean support, so anything fancier just
    fails to match — this guarantees a clean string even if the LLM ignores the
    "plain phrase" instruction.
    """
    # Drop parentheses and quote characters outright.
    cleaned = re.sub(r'[()"]', " ", text or "")
    # Keep only non-operator tokens, preserving order, then cap the length.
    words = [w for w in cleaned.split() if w.lower() not in _BOOLEAN_TOKENS]
    return " ".join(words[:_QUERY_MAX_WORDS])


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

    # A SHORT, PLAIN query: the single best-fit target title, no operators. Recall
    # comes from this broad query; rank_jobs() re-ranks against titles + skills.
    query = _plainify_query("AI Engineer")

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
    job-search profile. Identify the job titles this person should search for and
    the strongest and most marketable skills/technologies they have.

    For ``suggested_query``, output a SHORT, PLAIN search phrase: the SINGLE
    best-fit target job title only (e.g. "Computational Physicist"), 2-5 words.
    Do NOT use boolean operators (AND/OR), parentheses, quotes, or combine
    multiple titles/skills — keyword job-board APIs treat those as literal text
    and return zero results. Keep it broad; downstream re-ranking handles
    precision.

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

    - keywords present -> the profile's best-fit title plus the user's keywords.
    - keywords absent   -> the profile's ``suggested_query`` alone.

    The result is always a SHORT, PLAIN keyword string: boolean operators,
    parentheses and quotes are stripped defensively (even if the LLM ignores its
    instructions) and the length is capped, because JSearch / Adzuna treat any
    boolean syntax as literal text and return zero jobs. Recall comes from the
    broad query; precision comes from ``rank_jobs`` re-ranking against the full
    profile (suggested_titles + core_skills).
    """
    base = (profile.suggested_query or "").strip()
    keywords = (user_keywords or "").strip()

    if base and keywords:
        combined = f"{base} {keywords}"
    elif keywords:
        combined = keywords
    else:
        combined = base

    return _plainify_query(combined)


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
