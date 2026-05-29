import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

class EvaluationResult(BaseModel):
    fit_score_out_of_100: int = Field(description="Calculated fit score from 0 to 100 based on matching credentials.")
    technical_gaps: list[str] = Field(description="Technologies, tools, or concepts mentioned in the job description that are missing or weak in the portfolio.")
    go_no_go: bool = Field(description="True if fit_score_out_of_100 >= 70, otherwise False.")

def get_or_create_portfolio_cache(client: genai.Client, portfolio_path: str) -> str:
    """
    Finds an existing active context cache for the master portfolio,
    or uploads the PDF and creates a new context cache.
    Returns the cache name.
    """
    cache_display_name = "master_portfolio_cache"
    model_name = "gemini-2.5-pro"
    
    try:
        caches = client.caches.list()
        for c in caches:
            if c.display_name == cache_display_name and c.model == f"models/{model_name}":
                print(f"Found active existing context cache: {c.name} (Expires: {c.expire_time})")
                return c.name
    except Exception as e:
        print(f"Checking existing caches encountered a non-fatal error: {e}")

    if not os.path.exists(portfolio_path):
        print(f"Portfolio file '{portfolio_path}' not found. Generating it now using create_portfolio.py...")
        from create_portfolio import generate_portfolio
        generate_portfolio(portfolio_path)
        
    print(f"Uploading '{portfolio_path}' to Google Files API...")
    uploaded_file = client.files.upload(
        file=portfolio_path,
        config=types.UploadFileConfig(
            display_name="master_portfolio"
        )
    )
    
    print("Waiting for file upload to be processed...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(1)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise ValueError(f"File upload failed processing: {uploaded_file.name}")
        
    print(f"Uploaded successfully. File name: {uploaded_file.name}")

    print(f"Creating new context cache '{cache_display_name}' for model '{model_name}'...")
    cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            display_name=cache_display_name,
            system_instruction="You are an expert career strategist and recruiter. You have access to Avery Karlin's master portfolio. Use it to compare with incoming job specifications.",
            contents=[uploaded_file],
            ttl="3600s"
        ),
    )
    print(f"Context cache created. Cache name: {cache.name}")
    return cache.name

def evaluate_job_fit(job_json_str: str, portfolio_path: str = "master_portfolio.pdf", mock: bool = False) -> EvaluationResult:
    """
    Compares the job JSON against the cached portfolio PDF using gemini-2.5-pro,
    and returns a structured EvaluationResult.
    """
    if mock:
        print("[Mock Mode] Bypassing Gemini Caching & Evaluation API...")
        return EvaluationResult(
            fit_score_out_of_100=82,
            technical_gaps=[
                "Google Cloud Platform (GCP) and GKE experience",
                "PyTorch/TensorFlow (for fine-tuning basic classifiers)",
                "Rust/C++ (for hot-path backend optimization)"
            ],
            go_no_go=True
        )

    api_key = os.getenv("GEMINI_API_KEY")
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
    Set go_no_go to True if fit_score_out_of_100 >= 70, otherwise set it to False.
    """
    
    print("Running evaluation against cached portfolio using gemini-2.5-pro...")
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            cached_content=cache_name,
            response_mime_type="application/json",
            response_schema=EvaluationResult,
            temperature=0.2,
        )
    )
    
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
