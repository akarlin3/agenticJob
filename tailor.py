import os
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

def tailor_application_materials(job_details_json: str, gap_analysis_json: str, mock: bool = False) -> tuple[str, str]:
    """
    Sends job details, gap analysis, and optionally the master portfolio details to Claude 3.5 Sonnet.
    Uses forced tool use to strictly output a customized LaTeX resume and markdown cover letter.
    Returns (latex_resume, markdown_cover_letter).
    """
    if mock:
        print("[Mock Mode] Bypassing Claude Resume/Cover Letter Customization API...")
        latex_mock = r"""\documentclass{article}
\usepackage{geometry}
\usepackage{hyperref}
\geometry{letterpaper, margin=0.75in}
\begin{document}

\begin{center}
    {\Huge \textbf{Avery Karlin}} \\
    \vspace{2pt}
    Principal AI Systems Engineer \& Full Stack Architect \\
    \vspace{2pt}
    New York, NY | akarlin3@example.com | (555) 019-2831
\end{center}

\section*{Professional Summary}
Distinguished Principal Engineer specializing in the design, development, and scaling of hybrid multi-agent orchestration systems and distributed backend architectures. Proven expert at combining Gemini and Claude workflows with high-throughput PostgreSQL/Django systems. Proactively scaling infrastructure using AWS, Docker, Kubernetes, and Terraform.

\section*{Core Skills}
\begin{itemize}
    \item \textbf{Languages:} Python (FastAPI, Django), JavaScript, TypeScript (React, Next.js), SQL.
    \item \textbf{AI Orchestration:} Google GenAI SDK, Anthropic API, Multi-Agent Routing, Pydantic Schema Validation.
    \item \textbf{Databases \& DevOps:} PostgreSQL, Redis, Pinecone, AWS, Kubernetes, Docker, Terraform, GitHub Actions.
\end{itemize}

\section*{Professional Experience}
\textbf{Lead AI \& Backend Systems Engineer} \hfill 2023 -- Present \\
\textit{Cognitive Orchestration Labs}
\begin{itemize}
    \item Engineered a hybrid multi-agent workspace routing pipeline utilizing Gemini and Claude models, successfully scaling to process 10k+ prompt workloads per minute.
    \item Implemented structured data ingestion and semantic search pipelines, improving vector indexing (PostgreSQL pgvector) and prompt latency by 45\%.
    \item Built and deployed infrastructure using AWS ECS, Kubernetes, and Docker, provisioning with Terraform for 99.99\% reliability.
\end{itemize}

\textbf{Senior Full Stack Developer} \hfill 2020 -- 2023 \\
\textit{FinTech Core Solutions}
\begin{itemize}
    \item Developed payment APIs in Django and PostgreSQL processing over \$10M daily with deep query tuning and connection pooling.
    \item Led migration of legacy user interfaces to a modern React + Next.js platform, improving Core Web Vitals (LCP) by 1.2s.
\end{itemize}

\end{document}"""
        
        cover_letter_mock = """# Cover Letter - Avery Karlin

Dear Hiring Manager,

I am writing to express my enthusiastic interest in the Senior Full Stack AI Orchestration Engineer role. Having spent years designing and developing hybrid multi-agent pipelines and high-throughput financial backends, I was thrilled to read your requirements for an engineer skilled in LLM orchestration, FastAPI, and PostgreSQL performance tuning.

At Cognitive Orchestration Labs, I designed a multi-agent workspace routing engine that coordinates both Google's Gemini models and Anthropic's Claude APIs, handling high-volume workloads with stateful tracking and validation via Pydantic. Furthermore, at FinTech Core Solutions, I optimized transactional APIs in Django and PostgreSQL that processed over $10M in volume daily. This deep experience in database query optimization, connection pooling, and asynchronous task management maps directly to your need for defending backend performance metrics.

I notice you have listed experience with GCP/GKE and PyTorch as preferred. While my primary production deployments have been centered on AWS, Kubernetes, and Terraform, I have extensive experience setting up localized container environments, and I am eager to transition my container orchestration expertise to GKE. Additionally, my strong foundations in Python and modern agentic engineering make me extremely well-suited to rapidly apply PyTorch-based sequence classifiers to your risk assessment hot-paths.

I look forward to discussing how my experience with state-of-the-art AI systems and robust backend development can contribute to the success of your platform.

Sincerely,  
Avery Karlin"""
        
        return latex_mock, cover_letter_mock

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please set it in your .env file.")
        
    client = anthropic.Anthropic(api_key=api_key)
    
    tools = [
        {
            "name": "generate_application_materials",
            "description": "Outputs the tailored LaTeX resume and a matching markdown cover letter for the candidate.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "latex_resume": {
                        "type": "string",
                        "description": (
                            "Compilation-ready, professional, clean LaTeX source code of the tailored resume. "
                            "It should highlight the candidate's skills that match the job description and subtly "
                            "address the technical gaps. Do not include markdown wraps or backticks inside this field."
                        )
                    },
                    "markdown_cover_letter": {
                        "type": "string",
                        "description": (
                            "Full markdown-formatted cover letter addressed to the hiring manager of the role, "
                            "persuasively explaining how the candidate's background matches the requirements."
                        )
                    }
                },
                "required": ["latex_resume", "markdown_cover_letter"]
            }
        }
    ]
    
    system_prompt = """
    You are an elite executive resume writer and career coach. Your task is to customize the candidate's resume and write a matching cover letter.
    
    Follow these instructions carefully:
    1. Tailor the LaTeX resume using standard, professional LaTeX (like article class, simple packages like geometry, hyperref, and modern CV patterns). Avoid highly customized template libraries that require local compilation dependencies (e.g. fontawesome5, unless standard) to ensure it compiles flawlessly out-of-the-box on standard LaTeX engines (e.g., pdfLaTeX).
    2. Emphasize the required tech stack and core responsibilities from the job details.
    3. Mitigate or frame the listed technical gaps gracefully in both materials.
    4. Write a compelling, elegant, and persuasive markdown cover letter.
    5. You MUST respond ONLY by invoking the tool `generate_application_materials`. Do not write any conversational preamble or postscript.
    """
    
    prompt = f"""
    CANDIDATE PORTFOLIO / BIO INFO:
    Avery Karlin is a Principal AI Systems Engineer and Full Stack Architect with expertise in Python, Django, FastAPI, React, Next.js, PostgreSQL, Docker, AWS, Kubernetes, Terraform, and multi-agent orchestration.
    
    JOB DETAILS:
    {job_details_json}
    
    GAP ANALYSIS / EVALUATION:
    {gap_analysis_json}
    
    Please generate the tailored resume and cover letter.
    """
    
    print("Calling Claude 3.5 Sonnet to generate tailored application materials with forced tool use...")
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt}
        ],
        tools=tools,
        tool_choice={"type": "tool", "name": "generate_application_materials"}
    )
    
    tool_use_block = next((block for block in response.content if block.type == "tool_use"), None)
    if not tool_use_block:
        raise RuntimeError("Claude did not call the expected tool 'generate_application_materials'.")
        
    latex_resume = tool_use_block.input["latex_resume"]
    markdown_cover_letter = tool_use_block.input["markdown_cover_letter"]
    
    return latex_resume, markdown_cover_letter

if __name__ == "__main__":
    try:
        print("Testing Tailor Agent (Mock)...")
        resume, letter = tailor_application_materials("{}", "{}", mock=True)
        print("Generated tailored materials successfully!")
    except Exception as e:
        print(f"Error: {e}")
