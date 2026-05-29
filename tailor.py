import os
from dotenv import load_dotenv
import anthropic

# Synthetic demo persona — not a real individual. Mock outputs are built from the
# single source of truth in sample_data.py.
import sample_data

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
        # Synthetic demo persona — not a real individual (see sample_data.py).
        latex_mock = r"""\documentclass{article}
\usepackage{geometry}
\usepackage{hyperref}
\geometry{letterpaper, margin=0.75in}
\begin{document}

\begin{center}
    {\Huge \textbf{""" + sample_data.PERSONA_NAME + r"""}} \\
    \vspace{2pt}
    """ + sample_data.PERSONA_TITLE + r""" \\
    \vspace{2pt}
    """ + sample_data.PERSONA_LOCATION + " | " + sample_data.PERSONA_EMAIL + " | " + sample_data.PERSONA_PHONE + r"""
\end{center}

\section*{Professional Summary}
Software engineer specializing in the design, development, and scaling of hybrid multi-agent orchestration systems and distributed backend architectures. Experienced at combining Gemini and Claude workflows with PostgreSQL/Django systems, and scaling infrastructure using AWS, Docker, Kubernetes, and Terraform.

\section*{Core Skills}
\begin{itemize}
    \item \textbf{Languages:} Python (FastAPI, Django), JavaScript, TypeScript (React, Next.js), SQL.
    \item \textbf{AI Orchestration:} Google GenAI SDK, Anthropic API, Multi-Agent Routing, Pydantic Schema Validation.
    \item \textbf{Databases \& DevOps:} PostgreSQL, Redis, Pinecone, AWS, Kubernetes, Docker, Terraform, GitHub Actions.
\end{itemize}

\section*{Professional Experience}
\textbf{Lead AI \& Backend Systems Engineer} \hfill 2023 -- Present \\
\textit{""" + sample_data.COMPANY_CURRENT + r"""}
\begin{itemize}
    \item Engineered a hybrid multi-agent workspace routing pipeline utilizing Gemini and Claude models, handling """ + sample_data.THROUGHPUT_PROMPTS + r""" in load tests.
    \item Implemented structured data ingestion and semantic search pipelines, improving vector indexing (PostgreSQL pgvector) and prompt latency.
    \item Built and deployed infrastructure using AWS ECS, Kubernetes, and Docker, provisioning with Terraform.
\end{itemize}

\textbf{Senior Full Stack Developer} \hfill 2020 -- 2023 \\
\textit{""" + sample_data.COMPANY_PREVIOUS + r"""}
\begin{itemize}
    \item Developed payment APIs in Django and PostgreSQL processing """ + sample_data.PAYMENT_VOLUME + r""" in a sandbox environment, with query tuning and connection pooling.
    \item Led migration of legacy user interfaces to a modern React + Next.js platform, improving Core Web Vitals.
\end{itemize}

\end{document}"""

        cover_letter_mock = "# Cover Letter - " + sample_data.PERSONA_NAME + """

Dear Hiring Manager,

I am writing to express my enthusiastic interest in the Senior Full Stack AI Orchestration Engineer role. Having designed and developed hybrid multi-agent pipelines and high-throughput backends, I was glad to read your requirements for an engineer skilled in LLM orchestration, FastAPI, and PostgreSQL performance tuning.

At """ + sample_data.COMPANY_CURRENT + """, I designed a multi-agent workspace routing engine that coordinates both Google's Gemini models and Anthropic's Claude APIs, handling high-volume workloads with stateful tracking and validation via Pydantic. Furthermore, at """ + sample_data.COMPANY_PREVIOUS + """, I optimized transactional APIs in Django and PostgreSQL in a sandbox environment. This experience in database query optimization, connection pooling, and asynchronous task management maps directly to your need for defending backend performance metrics.

I notice you have listed experience with GCP/GKE and PyTorch as preferred. While my primary deployments have centered on AWS, Kubernetes, and Terraform, I have experience setting up containerized environments and am eager to transition my container orchestration expertise to GKE. Additionally, my foundations in Python and agentic engineering make me well-suited to rapidly apply PyTorch-based sequence classifiers to your risk assessment hot-paths.

I look forward to discussing how my experience with AI systems and backend development can contribute to the success of your platform.

Sincerely,
""" + sample_data.PERSONA_NAME

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
    You are an elite executive resume writer and career coach. Your task is to customize the candidate's resume and write a matching cover letter based strictly on the supplied portfolio.
    
    Follow these instructions carefully:
    1. Tailor the LaTeX resume using standard, professional LaTeX (like article class, simple packages like geometry, hyperref, and modern CV patterns). Avoid highly customized template libraries that require local compilation dependencies (e.g. fontawesome5, unless standard) to ensure it compiles flawlessly out-of-the-box on standard LaTeX engines (e.g., pdfLaTeX).
    2. Emphasize the required tech stack and core responsibilities from the job details.
    3. Mitigate or frame the listed technical gaps gracefully in both materials.
    4. Write a compelling, elegant, and persuasive markdown cover letter.
    5. You MUST respond ONLY by invoking the tool `generate_application_materials`. Do not write any conversational preamble or postscript.
    """
    
    prompt = f"""
    CANDIDATE PORTFOLIO / BIO INFO:
    {sample_data.PERSONA_BIO}

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
