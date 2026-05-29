"""
Synthetic demo persona — not a real individual.

This module is the SINGLE SOURCE OF TRUTH for the bundled sample résumé/portfolio
used by the demo and by every agent's ``mock=True`` branch. Nothing here describes
a real person: the name, employers, metrics, email, and phone number are all
obviously illustrative placeholders so the repository never ships invented
credentials under anyone's real identity.

Users supply their own real portfolio by uploading a PDF in the web UI or by
pointing the pipeline at their own ``master_portfolio.pdf`` / ``.env`` config.
"""

# --- Identity (placeholders only) -----------------------------------------
PERSONA_NAME = "Jordan Sample"
PERSONA_TITLE = "Senior AI Systems Engineer & Full Stack Developer"
PERSONA_EMAIL = "jordan.sample@example.com"
PERSONA_PHONE = "(555) 000-0000"
PERSONA_LOCATION = "Anytown, USA"

# --- Employers / institutions (clearly fictional) -------------------------
COMPANY_CURRENT = "Example Labs"
COMPANY_PREVIOUS = "Sample FinTech Inc."
UNIVERSITY = "Example State University"

# Round, obviously-illustrative figures (not claims of real performance)
THROUGHPUT_PROMPTS = "1,000+ prompts per minute"
PAYMENT_VOLUME = "$1M in sample transaction volume daily"

PROFESSIONAL_SUMMARY = (
    "Software engineer focused on the design and scaling of hybrid multi-agent "
    "orchestration systems and AI-driven platforms. Experienced in combining LLMs "
    "(Gemini, Claude) with backend services, distributed architectures, and cloud "
    "infrastructure. Interested in workflow automation, structured data extraction, "
    "and developer tooling."
)

SKILLS = {
    "Languages": "Python, JavaScript, TypeScript, Go, SQL, Bash",
    "AI/ML": "Google GenAI SDK, Anthropic Claude API, LangChain, Pydantic",
    "Back-End": "FastAPI, Django, Flask, Node.js (Express)",
    "Front-End": "React, Next.js, HTML5, CSS3, Tailwind CSS",
    "Cloud & DevOps": "AWS, Docker, Kubernetes, Terraform, GitHub Actions",
    "Databases": "PostgreSQL, Redis, MongoDB, Pinecone, ChromaDB",
}

# --- Experience -----------------------------------------------------------
EXPERIENCE = [
    {
        "role": "Lead AI & Backend Systems Engineer",
        "company": COMPANY_CURRENT,
        "dates": "2023 - Present",
        "bullets": [
            f"Designed and developed a hybrid multi-agent workspace routing engine "
            f"handling {THROUGHPUT_PROMPTS} in load tests.",
            "Implemented semantic search indexation using PostgreSQL (pgvector) and "
            "Pinecone, reducing prompt latency in benchmarks.",
            "Architected CI/CD pipelines deploying Docker containers to AWS ECS/Fargate "
            "with Terraform.",
            "Built structured data parsers leveraging Pydantic v2 and LLM schemas to "
            "ingest diverse documents.",
        ],
    },
    {
        "role": "Senior Full Stack Developer",
        "company": COMPANY_PREVIOUS,
        "dates": "2020 - 2023",
        "bullets": [
            f"Developed payment APIs in Django and PostgreSQL processing {PAYMENT_VOLUME} "
            f"in a sandbox environment, with query tuning and connection pooling.",
            "Migrated a legacy monolith frontend to a modern Next.js + React architecture, "
            "improving Core Web Vitals.",
            "Managed container orchestration using Kubernetes (EKS) and Helm charts.",
            "Mentored a small team of engineers and established automated integration "
            "testing suites.",
        ],
    },
]

PROJECTS = [
    {
        "name": "AgentFlow Orchestration Engine",
        "description": "Sample visual workspace for orchestrating Gemini and Claude "
        "subagents using async Python workflows.",
    },
    {
        "name": "TailorResume Pipeline",
        "description": "Sample Python CLI that matches raw job specs against structured "
        "portfolios, creating tailored résumé artifacts and LaTeX source dynamically.",
    },
]

EDUCATION = {
    "degree": "Bachelor of Science in Computer Science",
    "institution": UNIVERSITY,
}

# Short one-line bio used in prompt context for the tailoring agent.
PERSONA_BIO = (
    f"{PERSONA_NAME} is a {PERSONA_TITLE} with experience in Python, Django, FastAPI, "
    "React, Next.js, PostgreSQL, Docker, AWS, Kubernetes, Terraform, and multi-agent "
    "orchestration."
)
