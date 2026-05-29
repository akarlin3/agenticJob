import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Synthetic demo persona — not a real individual. All résumé content below is read
# from sample_data.py, the single source of truth for the bundled sample portfolio.
import sample_data

def generate_portfolio(output_path="master_portfolio.pdf"):
    """
    Generates a professional master portfolio PDF for the synthetic demo persona
    (see sample_data.py). This is illustrative sample data, not a real person's
    credentials — users supply their own portfolio via upload or local file.
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
    story.append(Paragraph(sample_data.PERSONA_NAME, title_style))
    story.append(Paragraph(
        f"{sample_data.PERSONA_TITLE} | {sample_data.PERSONA_EMAIL} | {sample_data.PERSONA_LOCATION}",
        subtitle_style
    ))

    # Professional Summary
    story.append(Paragraph("Professional Summary", section_heading))
    story.append(Paragraph(sample_data.PROFESSIONAL_SUMMARY, body_style))

    # Core Expertise (two-column layout)
    story.append(Paragraph("Core Technical Expertise", section_heading))
    skills_items = list(sample_data.SKILLS.items())
    skills_data = []
    for i in range(0, len(skills_items), 2):
        left = skills_items[i]
        row = [Paragraph(f"<b>{left[0]}:</b> {left[1]}", body_style)]
        if i + 1 < len(skills_items):
            right = skills_items[i + 1]
            row.append(Paragraph(f"<b>{right[0]}:</b> {right[1]}", body_style))
        else:
            row.append(Paragraph("", body_style))
        skills_data.append(row)

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
    for job in sample_data.EXPERIENCE:
        story.append(Paragraph(
            f"<b>{job['role']}</b> | {job['company']} ({job['dates']})", body_style
        ))
        for bullet in job["bullets"]:
            story.append(Paragraph(f"&bull; {bullet}", bullet_style))
        story.append(Spacer(1, 6))

    # Projects
    story.append(Paragraph("Selected Key Projects", section_heading))
    for project in sample_data.PROJECTS:
        story.append(Paragraph(
            f"<b>{project['name']}:</b> {project['description']}", bullet_style
        ))

    # Education
    story.append(Paragraph("Education", section_heading))
    story.append(Paragraph(
        f"<b>{sample_data.EDUCATION['degree']}</b> | {sample_data.EDUCATION['institution']}",
        body_style
    ))

    doc.build(story)
    print(f"Master portfolio successfully generated at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    generate_portfolio()
