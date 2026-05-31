import logging
import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings

logger = logging.getLogger(__name__)

# Retry policy for Gemini calls: up to 3 attempts with exponential backoff.
# See ingestion.py for the rationale on the broad exception filter.
_gemini_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)

# Synthetic demo persona — not a real individual (see sample_data.py).
import sample_data


class EvaluationResult(BaseModel):
    fit_score_out_of_100: int = Field(description="Calculated fit score from 0 to 100 based on matching credentials.")
    technical_gaps: list[str] = Field(description="Technologies, tools, or concepts mentioned in the job description that are missing or weak in the portfolio.")
    go_no_go: bool = Field(description=f"True if fit_score_out_of_100 >= {settings.fit_threshold}, otherwise False.")

def get_or_create_portfolio_cache(client: genai.Client, portfolio_path: str) -> str:
    """
    Finds an existing active context cache for the master portfolio,
    or uploads the PDF and creates a new context cache.
    Returns the cache name.
    """
    cache_display_name = "master_portfolio_cache"
    model_name = settings.gemini_pro_model
    
    try:
        caches = client.caches.list()
        for c in caches:
            if c.display_name == cache_display_name and c.model == f"models/{model_name}":
                logger.info("Found active existing context cache: %s (Expires: %s)", c.name, c.expire_time)
                return c.name
    except Exception as e:
        logger.warning("Checking existing caches encountered a non-fatal error: %s", e)

    if not os.path.exists(portfolio_path):
        logger.info("Portfolio file '%s' not found. Generating it now using create_portfolio.py...", portfolio_path)
        from create_portfolio import generate_portfolio
        generate_portfolio(portfolio_path)

    logger.info("Uploading '%s' to Google Files API...", portfolio_path)
    uploaded_file = client.files.upload(
        file=portfolio_path,
        config=types.UploadFileConfig(
            display_name="master_portfolio"
        )
    )
    
    logger.info("Waiting for file upload to be processed...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(1)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise ValueError(f"File upload failed processing: {uploaded_file.name}")

    logger.info("Uploaded successfully. File name: %s", uploaded_file.name)

    logger.info("Creating new context cache '%s' for model '%s'...", cache_display_name, model_name)

    @_gemini_retry
    def _create_cache():
        return client.caches.create(
            model=model_name,
            config=types.CreateCachedContentConfig(
                display_name=cache_display_name,
                system_instruction=f"You are an expert career strategist and recruiter. You have access to {sample_data.PERSONA_NAME}'s master portfolio. Use it to compare with incoming job specifications.",
                contents=[uploaded_file],
                ttl=f"{settings.portfolio_cache_ttl_seconds}s",
            ),
        )

    cache = _create_cache()
    logger.info("Context cache created. Cache name: %s", cache.name)
    return cache.name

def evaluate_job_fit(job_json_str: str, portfolio_path: str = "master_portfolio.pdf", mock: bool = False) -> EvaluationResult:
    """
    Compares the job JSON against the cached portfolio PDF using the configured
    Gemini Pro model, and returns a structured EvaluationResult.
    """
    if mock:
        logger.info("[Mock Mode] Bypassing Gemini Caching & Evaluation API...")
        return EvaluationResult(
            fit_score_out_of_100=82,
            technical_gaps=[
                "Google Cloud Platform (GCP) and GKE experience",
                "PyTorch/TensorFlow (for fine-tuning basic classifiers)",
                "Rust/C++ (for hot-path backend optimization)"
            ],
            go_no_go=True
        )

    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")

    client = genai.Client(api_key=api_key)
    cache_name = get_or_create_portfolio_cache(client, portfolio_path)

    prompt = f"""
    Compare the candidate's master portfolio with the following ingested job specifications:

    JOB ANALYSIS:
    {job_json_str}

    Calculate a fit score out of 100.
    Perform a gap analysis of missing or weak technical skills or experiences.
    Set go_no_go to True if fit_score_out_of_100 >= {settings.fit_threshold}, otherwise set it to False.
    """

    logger.info("Running evaluation against cached portfolio using %s...", settings.gemini_pro_model)

    @_gemini_retry
    def _call():
        return client.models.generate_content(
            model=settings.gemini_pro_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                cached_content=cache_name,
                response_mime_type="application/json",
                response_schema=EvaluationResult,
                temperature=0.2,
            ),
        )

    response = _call()
    return response.parsed

if __name__ == "__main__":
    import json
    test_job = json.dumps({"role_title": "Engineer"})
    try:
        print("Testing Evaluator Agent (Mock)...")
        result = evaluate_job_fit(test_job, mock=True)
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
