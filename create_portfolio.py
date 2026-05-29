import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_portfolio(output_path="master_portfolio.pdf"):
    """
    Generates a professional master portfolio PDF for Avery Karlin
    containing modern tech stacks and engineering credentials.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles for a beautiful premium design
    title_style = ParagraphStyle(
        'PortfolioTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1A365D'), # Deep navy blue
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'PortfolioSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#4A5568'), # Slate grey
        spaceAfter=15
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2B6CB0'), # Royal blue
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'PortfolioBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2D3748'), # Charcoal
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'PortfolioBullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    story = []
    
    # Header Section
    story.append(Paragraph("Avery Karlin", title_style))
    story.append(Paragraph("Principal AI Systems Engineer & Full Stack Architect | akarlin3@example.com | New York, NY", subtitle_style))
    
    # Professional Summary
    story.append(Paragraph("Professional Summary", section_heading))
    story.append(Paragraph(
        "Highly accomplished Principal Engineer specializing in the design, development, and scaling of hybrid multi-agent orchestration engines and AI-driven platforms. "
        "Proven expertise in combining cutting-edge LLMs (Gemini, Claude, GPT) with robust enterprise backend systems, distributed architectures, and scalable cloud infrastructure. "
        "Passionate about workflow automation, structured data intelligence, and state-of-the-art developer tools.",
        body_style
    ))
    
    # Core Expertise
    story.append(Paragraph("Core Technical Expertise", section_heading))
    
    # Two-column layout for skills using Table
    skills_data = [
        [
            Paragraph("<b>Languages:</b> Python, JavaScript, TypeScript, Go, SQL, Bash", body_style),
            Paragraph("<b>AI/ML:</b> Google GenAI SDK, Anthropic Claude API, LangChain, Pydantic", body_style)
        ],
        [
            Paragraph("<b>Back-End:</b> FastAPI, Django, Flask, Node.js (Express)", body_style),
            Paragraph("<b>Front-End:</b> React, Next.js, HTML5, CSS3, Tailwind CSS", body_style)
        ],
        [
            Paragraph("<b>Cloud & DevOps:</b> AWS, Docker, Kubernetes, Terraform, GitHub Actions", body_style),
            Paragraph("<b>Databases:</b> PostgreSQL, Redis, MongoDB, Pinecone, ChromaDB", body_style)
        ]
    ]
    
    skills_table = Table(skills_data, colWidths=[250, 250])
    skills_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(skills_table)
    story.append(Spacer(1, 10))
    
    # Professional Experience
    story.append(Paragraph("Professional Experience", section_heading))
    
    # Job 1
    story.append(Paragraph("<b>Lead AI & Backend Systems Engineer</b> | Cognitive Orchestration Labs (2023 - Present)", body_style))
    story.append(Paragraph("&bull; Designed and developed a hybrid multi-agent workspace routing engine processing 10k+ prompt workloads per minute.", bullet_style))
    story.append(Paragraph("&bull; Implemented semantic search indexation utilizing PostgreSQL (pgvector) and Pinecone, reducing prompt latency by 45%.", bullet_style))
    story.append(Paragraph("&bull; Architected robust CI/CD pipelines deploying Docker containers to AWS ECS/Fargate using Terraform, maintaining 99.99% uptime.", bullet_style))
    story.append(Paragraph("&bull; Built structured data parsers leveraging Pydantic v2 and LLM schemas to ingest diverse legal and financial documents.", bullet_style))
    story.append(Spacer(1, 6))
    
    # Job 2
    story.append(Paragraph("<b>Senior Full Stack Developer</b> | FinTech Core Solutions (2020 - 2023)", body_style))
    story.append(Paragraph("&bull; Developed high-throughput payment APIs in Django and PostgreSQL processing over $10M in transaction volume daily.", bullet_style))
    story.append(Paragraph("&bull; Orchestrated the migration of legacy monolith frontend to a modern Next.js + React architecture, improving Core Web Vitals (LCP) by 1.2s.", bullet_style))
    story.append(Paragraph("&bull; Managed localized container orchestration utilizing Kubernetes (EKS) and local Helm charts.", bullet_style))
    story.append(Paragraph("&bull; Mentored a cross-functional team of 6 engineers and established comprehensive automated integration testing suites.", bullet_style))
    
    # Projects
    story.append(Paragraph("Selected Key Projects", section_heading))
    story.append(Paragraph("<b>AgentFlow Orchestration Engine:</b> Open-source visual workspace for orchestration of Gemini and Claude subagents using advanced async Python workflows.", bullet_style))
    story.append(Paragraph("<b>TailorResume Pipeline:</b> Autonomous Python CLI engine which matches raw job specs against structured portfolios, creating tailored resume artifacts and LaTeX source files dynamically.", bullet_style))
    
    # Education
    story.append(Paragraph("Education", section_heading))
    story.append(Paragraph("<b>Bachelor of Science in Computer Science</b> | New York University (NYU)", body_style))
    
    doc.build(story)
    print(f"Master portfolio successfully generated at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    generate_portfolio()
