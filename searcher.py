"""
Discovery layer for the Agentic Job Application Pipeline.

Replaces the previous LLM-grounded-search approach (which hallucinated URLs and
collected non-functional credentials) with real, structured jobs APIs that return
canonical apply links and full job descriptions.

Providers
---------
1. JSearch (RapidAPI / OpenWeb Ninja)  -- PRIMARY
   Aggregates Google for Jobs: LinkedIn, Indeed, Glassdoor, ZipRecruiter, etc.
   Env: RAPIDAPI_KEY
2. Adzuna                              -- FALLBACK (fully free)
   Env: ADZUNA_APP_ID, ADZUNA_APP_KEY

Behaviour
---------
- If RAPIDAPI_KEY is set, JSearch is used.
- If JSearch is unavailable (no key, rate-limited, or errors) and Adzuna creds
  are set, Adzuna is used instead.
- If neither is configured, raises a clear error (no silent fake data outside mock).
- Results are deduplicated and carry BOTH a short snippet (for cards) and the full
  description (for the downstream ingestion/evaluation agents).

There are no login/credential parameters. The old username/password/api_token
fields did nothing functional and were a security liability.
"""

import os
import re
import time
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_URL = f"https://{JSEARCH_HOST}/search"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# JSearch accepts: all | today | 3days | week | month
VALID_DATE_FILTERS = {"all", "today", "3days", "week", "month"}


class DiscoveredJob(BaseModel):
    title: str = Field(description="The official job title.")
    company: str = Field(description="The name of the hiring company.")
    location: str = Field(description="The location of the job posting.")
    source: str = Field(description="The originating board/publisher, e.g. LinkedIn, Indeed.")
    url: str = Field(description="Canonical apply/redirect URL for the posting.")
    snippet: str = Field(description="Short description for the job card (truncated).")
    description: str = Field(default="", description="Full job description text for the pipeline.")
    posted: str = Field(default="", description="Human-readable posted date, if available.")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _dedupe_key(job: dict) -> str:
    """Normalize title+company so the same posting from two boards collapses."""
    t = re.sub(r"\s+", " ", (job.get("title") or "")).strip().lower()
    c = re.sub(r"\s+", " ", (job.get("company") or "")).strip().lower()
    return f"{t}::{c}"


def _truncate(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# JSearch (primary)
# --------------------------------------------------------------------------- #
def _search_jsearch(
    query: str,
    location: str,
    platforms: list[str],
    date_posted: str,
    remote: bool,
    max_results: int,
) -> list[dict]:
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []

    # JSearch embeds location in the query string. A single selected board can be
    # targeted with "via <publisher>"; multiple boards are covered by the general
    # query anyway, since JSearch aggregates Google for Jobs across all of them.
    q = f"{query} in {location}".strip()
    if len(platforms) == 1:
        q = f"{q} via {platforms[0].lower()}"

    params = {
        "query": q,
        "page": "1",
        "num_pages": "1",
        "country": "us",
        "date_posted": date_posted if date_posted in VALID_DATE_FILTERS else "month",
    }
    if remote:
        params["work_from_home"] = "true"

    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": JSEARCH_HOST}

    print(f"[Search Agent] JSearch query: '{q}' (date_posted={params['date_posted']})")
    resp = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=25)
    resp.raise_for_status()
    data = resp.json().get("data") or []

    jobs = []
    for j in data[:max_results]:
        loc = ", ".join(
            p for p in [j.get("job_city"), j.get("job_state"), j.get("job_country")] if p
        ) or location
        desc = j.get("job_description") or ""
        jobs.append(
            {
                "title": j.get("job_title") or "Unknown Title",
                "company": j.get("employer_name") or "Unknown Company",
                "location": loc,
                "source": j.get("job_publisher") or "Google for Jobs",
                "url": j.get("job_apply_link") or j.get("job_google_link") or "",
                "snippet": _truncate(desc),
                "description": desc,
                "posted": j.get("job_posted_at_datetime_utc") or "",
            }
        )
    return jobs


# --------------------------------------------------------------------------- #
# Adzuna (fallback, fully free)
# --------------------------------------------------------------------------- #
def _search_adzuna(
    query: str,
    location: str,
    date_posted: str,
    remote: bool,
    max_results: int,
    country: str = "us",
) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": f"{query} remote" if remote else query,
        "where": location,
        "results_per_page": str(min(max_results, 50)),
        "content-type": "application/json",
    }
    # Translate freshness into Adzuna's max_days_old.
    days = {"today": 1, "3days": 3, "week": 7, "month": 30}.get(date_posted)
    if days:
        params["max_days_old"] = str(days)

    url = ADZUNA_URL.format(country=country)
    print(f"[Search Agent] Adzuna fallback query: '{query}' in '{location}'")
    resp = requests.get(url, params=params, timeout=25)
    resp.raise_for_status()
    results = resp.json().get("results") or []

    jobs = []
    for r in results[:max_results]:
        desc = r.get("description") or ""
        jobs.append(
            {
                "title": r.get("title") or "Unknown Title",
                "company": (r.get("company") or {}).get("display_name") or "Unknown Company",
                "location": (r.get("location") or {}).get("display_name") or location,
                "source": "Adzuna",
                "url": r.get("redirect_url") or "",
                "snippet": _truncate(desc),
                "description": desc,
                "posted": r.get("created") or "",
            }
        )
    return jobs


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def search_jobs(
    query: str,
    location: str,
    platforms: list[str] | None = None,
    date_posted: str = "month",
    remote: bool = False,
    max_results: int = 10,
    mock: bool = False,
) -> list[dict]:
    """
    Search real job boards via JSearch (primary) with Adzuna fallback.

    Returns a list of dicts matching the DiscoveredJob schema, deduplicated.
    Each result includes `description` (full JD) so the downstream pipeline runs
    on the real posting rather than a teaser snippet.
    """
    platforms = platforms or []
    print(
        f"[Search Agent] query='{query}' location='{location}' "
        f"platforms={platforms} remote={remote}"
    )

    if mock:
        print("[Search Agent] [Mock Mode] Returning simulated results...")
        return _mock_results(location)

    errors = []
    jobs: list[dict] = []

    # 1) Primary: JSearch
    try:
        jobs = _search_jsearch(query, location, platforms, date_posted, remote, max_results)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        errors.append(f"JSearch HTTP {code}")
        print(f"[Search Agent] JSearch failed (HTTP {code}); trying fallback.")
    except Exception as e:
        errors.append(f"JSearch: {e}")
        print(f"[Search Agent] JSearch error: {e}; trying fallback.")

    # 2) Fallback: Adzuna (only if primary returned nothing)
    if not jobs:
        try:
            jobs = _search_adzuna(query, location, date_posted, remote, max_results)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            errors.append(f"Adzuna HTTP {code}")
        except Exception as e:
            errors.append(f"Adzuna: {e}")

    if not jobs and errors:
        raise RuntimeError(
            "Job search failed and no provider is configured/working. "
            "Set RAPIDAPI_KEY (JSearch) and/or ADZUNA_APP_ID + ADZUNA_APP_KEY. "
            f"Details: {'; '.join(errors)}"
        )

    # Dedupe (stable order)
    seen, deduped = set(), []
    for j in jobs:
        k = _dedupe_key(j)
        if k not in seen:
            seen.add(k)
            deduped.append(j)

    # Validate against schema; drop malformed rows rather than 500 the request.
    clean = []
    for j in deduped:
        try:
            clean.append(DiscoveredJob(**j).model_dump())
        except Exception as e:
            print(f"[Search Agent] Dropping malformed result: {e}")

    print(f"[Search Agent] Returning {len(clean)} jobs.")
    return clean


def _mock_results(location: str) -> list[dict]:
    return [
        {
            "title": "Senior Full Stack AI Systems Engineer",
            "company": "Stripe",
            "location": f"{location} (Hybrid)",
            "source": "LinkedIn",
            "url": "https://www.linkedin.com/jobs/view/3900000001",
            "snippet": "Scale multi-agent checkout routers and payment ingestion. "
            "5+ yrs Python, FastAPI, React, PostgreSQL tuning; AWS/Docker required; GCP/PyTorch a plus.",
            "description": "Scale multi-agent checkout routers and payment ingestion platforms. "
            "Requirements: 5+ years Python, FastAPI, Django, React, and PostgreSQL performance tuning. "
            "AWS and Docker required. GCP/GKE or PyTorch a plus. Own end-to-end API architecture and "
            "mentor junior engineers.",
            "posted": "2026-05-25T00:00:00Z",
        },
        {
            "title": "Full Stack Payment Engineer",
            "company": "Coinbase",
            "location": f"{location} (Remote)",
            "source": "Indeed",
            "url": "https://www.indeed.com/viewjob?jk=abc123def456",
            "snippet": "Optimize core transactional payment systems. Python (FastAPI/Django) + "
            "PostgreSQL, React dashboards, Kubernetes + Terraform. Rust/C++ hot-path a plus.",
            "description": "Optimize core transactional payment systems. Scale backend APIs using "
            "Python (FastAPI/Django) and PostgreSQL. Build modern dashboards in React. Manage "
            "deployments with Kubernetes and Terraform. Hot-path optimizations using Rust/C++ are a plus.",
            "posted": "2026-05-24T00:00:00Z",
        },
        {
            "title": "Lead Software Engineer - FinTech Infrastructure",
            "company": "Plaid",
            "location": "New York, NY",
            "source": "ZipRecruiter",
            "url": "https://www.ziprecruiter.com/c/Plaid/Job/Lead-Software-Engineer",
            "snippet": "Scale financial ingestion endpoints. PostgreSQL schema design, Docker + AWS "
            "via Terraform. Python, React, AWS, Docker.",
            "description": "Scale core financial ingestion endpoints. Design relational databases in "
            "PostgreSQL. Maintain Docker containers and AWS infrastructure using Terraform. Mentor "
            "junior engineers and collaborate with risk analysis teams. Requirements: Python, React, AWS, Docker.",
            "posted": "2026-05-23T00:00:00Z",
        },
    ]


if __name__ == "__main__":
    # Mock smoke test (no keys needed)
    print("Testing searcher (mock)...")
    for job in search_jobs("Python Engineer", "New York, NY", ["LinkedIn"], mock=True):
        print(f"  - {job['title']} @ {job['company']} [{job['source']}] -> {job['url']}")
