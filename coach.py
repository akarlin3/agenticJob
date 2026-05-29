import os
from dotenv import load_dotenv
import anthropic

# Synthetic demo persona — not a real individual (see sample_data.py).
import sample_data

# Load environment variables
load_dotenv()

def generate_interview_prep(job_details_json: str, gap_analysis_json: str, mock: bool = False) -> list[dict]:
    """
    Sends the job details and gap analysis to Claude 3.5 Sonnet to generate
    targeted behavioral and technical interview questions, complete with rationales
    and answering strategies.
    Returns a list of structured question dictionaries.
    """
    if mock:
        print("[Mock Mode] Bypassing Claude Interview Coaching API...")
        return [
            {
                "question": f"Can you walk us through the architectural design of the hybrid multi-agent routing system you built at {sample_data.COMPANY_CURRENT}? How did you delegate tasks between Gemini and Claude?",
                "type": "Technical",
                "rationale": "Directly tests the candidate's core domain expertise in AI systems engineering, agent design patterns, and handling high-volume workloads.",
                "suggested_strategy": "Explain the orchestrator and router patterns. Highlight how Gemini was used for high-speed, cost-effective structured ingestion (flash), while Claude was leveraged for deep reasoning (sonnet) or tailored coding. Mention managing latency, prompt routing, and parsing validation with Pydantic."
            },
            {
                "question": "The role mentions hot-path optimization with Rust/C++. While your main expertise is in Python and Go, how would you approach optimizing a high-latency service in our platform?",
                "type": "Technical",
                "rationale": "Evaluates how the candidate defends their gap in direct production Rust/C++ experience for performance engineering.",
                "suggested_strategy": "Frame Rust/C++ as highly performant toolings you are eager and ready to leverage. Pivot to showing how you've optimized Python hot-paths (using asynchronous FastAPI, multi-threading/processing, caching with Redis, or writing performance-critical C-extensions/Go microservices). Outline how you will profile the performance hotspots first before rewriting them."
            },
            {
                "question": "We deploy on GCP and use Google Kubernetes Engine (GKE). Your portfolio highlights AWS (ECS/Fargate/EKS). How would you manage the transition and ensure high reliability?",
                "type": "Technical",
                "rationale": "Defends the GCP/GKE knowledge gap by leveraging strong, existing AWS and container orchestration foundations.",
                "suggested_strategy": "Emphasize that the core containerization concepts (Docker, Helm, Kubernetes objects like Pods, Services, Ingress, Deployments) are cloud-agnostic. Contrast AWS EKS and GCP GKE, noting that GKE is highly automated. Highlight your deep Terraform capabilities to manage infrastructure as code, ensuring a seamless and reliable transition."
            },
            {
                "question": "The job description values PyTorch/TensorFlow experience for training or fine-tuning custom classifiers. How have you integrated custom ML classification models into your agentic platforms, and how would you build one here?",
                "type": "Technical",
                "rationale": "Defends the deep learning framework gap (PyTorch/TensorFlow) by leveraging extensive API-level AI experience and robust coding capabilities.",
                "suggested_strategy": "State that while your focus has been on LLM orchestration and vector embeddings, you possess excellent Python fundamentals. Explain how you would utilize libraries like Hugging Face or PyTorch for text sequence classifiers. Outline a rapid proof-of-concept pipeline: preparing labeled training data, tokenizing, fine-tuning a small BERT-based classifier, and containerizing it for low-latency FastAPI inference."
            },
            {
                "question": "Tell us about a time you had to defend backend performance metrics under high-throughput conditions. What database and API strategies did you use?",
                "type": "Behavioral",
                "rationale": "Evaluates the candidate's core backend performance defending responsibilities.",
                "suggested_strategy": f"Use the STAR method to describe a scenario at {sample_data.COMPANY_PREVIOUS} optimizing payment APIs. Detail the database optimizations: implementing connection pooling (e.g. pgBouncer), writing index queries, query profiling with EXPLAIN ANALYZE, and caching static lookups with Redis. Quantify the results (e.g., reduced API latency)."
            }
        ]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please set it in your .env file.")
        
    client = anthropic.Anthropic(api_key=api_key)
    
    tools = [
        {
            "name": "output_interview_prep",
            "description": "Output the list of structured interview preparation questions and strategies.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "List of targeted interview questions.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string", "description": "The exact question text."},
                                "type": {"type": "string", "enum": ["Technical", "Behavioral"], "description": "The type of interview question."},
                                "rationale": {"type": "string", "description": "Why this question is highly relevant to this specific role and the candidate's gaps."},
                                "suggested_strategy": {"type": "string", "description": "Actionable advice and key points the candidate should focus on using the STAR method or specific technical concepts."}
                            },
                            "required": ["question", "type", "rationale", "suggested_strategy"]
                        }
                    }
                },
                "required": ["questions"]
            }
        }
    ]
    
    system_prompt = f"""
    You are an elite technology interview coach. Your task is to prepare a candidate ({sample_data.PERSONA_NAME}) for an interview by generating highly targeted technical and behavioral questions.
    Focus heavily on:
    1. The core responsibilities and technical stack required by the job description.
    2. The technical gaps identified in the evaluation phase, to help the candidate prepare to address these weaknesses proactively.
    
    You MUST respond ONLY by invoking the tool `output_interview_prep`. Do not write any conversational preamble or postscript.
    """
    
    prompt = f"""
    JOB DETAILS:
    {job_details_json}
    
    GAP ANALYSIS / EVALUATION:
    {gap_analysis_json}
    
    Please generate 5-6 extremely relevant interview questions (mix of technical and behavioral) that the candidate should prepare for, especially focusing on how to defend their technical gaps.
    """
    
    print("Calling Claude 3.5 Sonnet to generate interview coach preparation guide...")
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2500,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt}
        ],
        tools=tools,
        tool_choice={"type": "tool", "name": "output_interview_prep"}
    )
    
    tool_use_block = next((block for block in response.content if block.type == "tool_use"), None)
    if not tool_use_block:
        raise RuntimeError("Claude did not call the expected tool 'output_interview_prep'.")
        
    return tool_use_block.input["questions"]

if __name__ == "__main__":
    try:
        print("Testing Coach Agent (Mock)...")
        prep = generate_interview_prep("{}", "{}", mock=True)
        print(f"Generated {len(prep)} questions successfully!")
    except Exception as e:
        print(f"Error: {e}")
