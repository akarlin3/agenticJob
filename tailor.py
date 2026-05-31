import logging
import anthropic

from config import settings

logger = logging.getLogger(__name__)

# Synthetic demo persona — not a real individual. Mock outputs are built from the
# single source of truth in sample_data.py.
import sample_data

# LaTeX reserved characters that must be escaped when raw text (e.g. the persona
# fields from sample_data.py, which are also consumed by the reportlab PDF where
# these characters are literal) is interpolated into the LaTeX source. Without
# this, values like "...Engineer & Full Stack Developer" or "$1M ..." abort the
# Tectonic/pdfLaTeX compile ("Misplaced alignment tab" / "Missing $ inserted").
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_escape(text: str) -> str:
    """Escape LaTeX reserved characters in a plain-text value.

    Backslash is handled first via the dict ordering (Python 3.7+ preserves
    insertion order) so the replacements it introduces are not re-escaped.
    """
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def tailor_application_materials(job_details_json: str, gap_analysis_json: str, mock: bool = False) -> tuple[str, str]:
    """
    Sends job details, gap analysis, and optionally the master portfolio details to Claude 3.5 Sonnet.
    Uses forced tool use to strictly output a customized LaTeX resume and markdown cover letter.
    Returns (latex_resume, markdown_cover_letter).
    """
    if mock:
        logger.info("[Mock Mode] Bypassing Claude Resume/Cover Letter Customization API...")
        # Synthetic demo persona — not a real individual (see sample_data.py).
        # Escape the interpolated fields so LaTeX reserved characters (the "&" in
        # the title, the "$" in the payment volume) don't break compilation.
        name = _latex_escape(sample_data.PERSONA_NAME)
        title = _latex_escape(sample_data.PERSONA_TITLE)
        location = _latex_escape(sample_data.PERSONA_LOCATION)
        email = _latex_escape(sample_data.PERSONA_EMAIL)
        phone = _latex_escape(sample_data.PERSONA_PHONE)
        company_current = _latex_escape(sample_data.COMPANY_CURRENT)
        company_previous = _latex_escape(sample_data.COMPANY_PREVIOUS)
        throughput = _latex_escape(sample_data.THROUGHPUT_PROMPTS)
        payment_volume = _latex_escape(sample_data.PAYMENT_VOLUME)

        latex_mock = r"""\documentclass{article}
\usepackage{geometry}
\usepackage{hyperref}
\geometry{letterpaper, margin=0.75in}
\begin{document}

\begin{center}
    {\Huge \textbf{""" + name + r"""}} \\
    \vspace{2pt}
    """ + title + r""" \\
    \vspace{2pt}
    """ + location + " | " + email + " | " + phone + r"""
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
\textit{""" + company_current + r"""}
\begin{itemize}
    \item Engineered a hybrid multi-agent workspace routing pipeline utilizing Gemini and Claude models, handling """ + throughput + r""" in load tests.
    \item Implemented structured data ingestion and semantic search pipelines, improving vector indexing (PostgreSQL pgvector) and prompt latency.
    \item Built and deployed infrastructure using AWS ECS, Kubernetes, and Docker, provisioning with Terraform.
\end{itemize}

\textbf{Senior Full Stack Developer} \hfill 2020 -- 2023 \\
\textit{""" + company_previous + r"""}
\begin{itemize}
    \item Developed payment APIs in Django and PostgreSQL processing """ + payment_volume + r""" in a sandbox environment, with query tuning and connection pooling.
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

    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set. Please set it in your .env file.")
        
    # SDK-native retry + timeout: 3 retries with exponential backoff on
    # transient errors (timeouts, 429s, 5xx), 60s per-request timeout.
    client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=60.0)
    
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
    
    logger.info("Calling Claude 3.5 Sonnet to generate tailored application materials with forced tool use...")
    response = client.messages.create(
        model=settings.claude_model,
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
