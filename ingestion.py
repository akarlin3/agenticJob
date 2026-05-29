import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Define the Pydantic schema for structured output
class JobAnalysis(BaseModel):
    role_title: str = Field(description="The primary official title of the role.")
    required_tech_stack: list[str] = Field(description="List of primary programming languages, frameworks, databases, and DevOps tools required.")
    core_responsibilities: list[str] = Field(description="List of key daily responsibilities and deliverables.")
    domain_expertise: list[str] = Field(description="List of domains or business sectors required (e.g., FinTech, SaaS, Healthcare, AI).")

def ingest_job_description(job_description: str, mock: bool = False) -> JobAnalysis:
    """
    Accepts a raw job description string and returns a structured Pydantic object
    using Gemini 2.5 Flash and Pydantic structured output.
    """
    if mock:
        print("[Mock Mode] Bypassing Gemini Ingestion API...")
        return JobAnalysis(
            role_title="Senior Full Stack AI Orchestration Engineer (FinTech / SaaS)",
            required_tech_stack=["Python", "FastAPI", "React", "PostgreSQL", "Docker", "AWS", "Terraform", "GCP", "PyTorch"],
            core_responsibilities=[
                "Design, scale, and optimize high-throughput REST APIs using Python and PostgreSQL.",
                "Build reliable, stateful multi-agent frameworks using prompt routing.",
                "Lead the migration of core accounting interfaces to a modern React-based SPA.",
                "Manage container deployments, CI/CD integrations, and environment provisioning via Terraform."
            ],
            domain_expertise=["FinTech", "SaaS", "Payment Processing"]
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Please analyze the following job description and extract the required details:
    
    JOB DESCRIPTION:
    \"\"\"
    {job_description}
    \"\"\"
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=JobAnalysis,
            system_instruction="You are an expert technical recruiter and talent advisor. Extract clear, structured attributes from the provided job description.",
            temperature=0.1,
        ),
    )
    
    return response.parsed

if __name__ == "__main__":
    test_job = """
    We are looking for a Senior Full Stack Engineer to join our FinTech platform.
    Requirements: Experience with Python, Django, React.
    """
    try:
        print("Testing Ingestion Agent (Mock)...")
        analysis = ingest_job_description(test_job, mock=True)
        print(analysis.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
