import os
import sys
import json
import argparse
from dotenv import load_dotenv

# Fallback to handle uvicorn loading main:app instead of app:app
try:
    from app import app
except ImportError:
    pass

# Load env variables
load_dotenv()

# Import the agent modules
from ingestion import ingest_job_description
from evaluator import evaluate_job_fit
from tailor import tailor_application_materials
from coach import generate_interview_prep

def print_banner(title: str):
    print("\n" + "=" * 60)
    print(f" {title.upper()} ".center(60, "-"))
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Hybrid Multi-Agent Job Application Pipeline")
    parser.add_argument("--job", type=str, default="sample_job.txt", help="Path to raw job description txt file")
    parser.add_argument("--portfolio", type=str, default="master_portfolio.pdf", help="Path to master portfolio PDF file")
    parser.add_argument("--outdir", type=str, default="output", help="Directory to save tailored outputs")
    parser.add_argument("--mock", action="store_true", help="Run the pipeline in validation / mock mode (bypasses active API billing)")
    
    args = parser.parse_args()
    
    # Check if mock mode is requested or if keys are missing
    run_mock = args.mock
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not run_mock:
        if not gemini_key or gemini_key == "YOUR_GEMINI_API_KEY" or not anthropic_key or anthropic_key == "YOUR_ANTHROPIC_API_KEY":
            print("[!] API Keys not fully configured. Defaulting to safe validation --mock mode to show integration flow.")
            run_mock = True
            
    # 1. Verification of inputs
    if not os.path.exists(args.job):
        print(f"Error: Job description file '{args.job}' not found.")
        print("Please create 'sample_job.txt' or provide a valid path using --job.")
        sys.exit(1)
        
    print_banner("Initializing Job Search Pipeline")
    print(f"Input Job File: {os.path.abspath(args.job)}")
    print(f"Master Portfolio: {os.path.abspath(args.portfolio)}")
    print(f"Output Directory: {os.path.abspath(args.outdir)}")
    print(f"Execution Mode: {'MOCK/VALIDATION' if run_mock else 'LIVE PRODUCTION API'}")
    
    # Read the job description
    with open(args.job, "r") as f:
        job_description = f.read().strip()
        
    if not job_description:
        print("Error: Job description file is empty.")
        sys.exit(1)
        
    # Create output directory
    os.makedirs(args.outdir, exist_ok=True)
    
    # 2. Agent 1 - Ingestion (Gemini 2.5 Flash)
    print_banner("Agent 1: Job Description Ingestion (Gemini 2.5 Flash)")
    try:
        print("Ingesting job description and extracting structured schema...")
        job_analysis = ingest_job_description(job_description, mock=run_mock)
        job_analysis_json = job_analysis.model_dump_json(indent=2)
        
        print("\n[+] Structured Ingestion Successful!")
        print(f"Role Title: {job_analysis.role_title}")
        print(f"Tech Stack: {', '.join(job_analysis.required_tech_stack)}")
        print(f"Responsibilities: {len(job_analysis.core_responsibilities)} key items extracted")
        print(f"Domain Expertise: {', '.join(job_analysis.domain_expertise)}")
        
        # Save ingestion JSON to output
        ingestion_save_path = os.path.join(args.outdir, "job_analysis.json")
        with open(ingestion_save_path, "w") as f:
            f.write(job_analysis_json)
        print(f"Saved ingestion schema to: {ingestion_save_path}")
        
    except Exception as e:
        print(f"[-] Critical Error in Ingestion Agent: {e}")
        sys.exit(1)
        
    # 3. Agent 2 - Evaluator (Gemini 2.5 Pro + Context Caching)
    print_banner("Agent 2: Portfolio Match & Fit Evaluation (Gemini 2.5 Pro)")
    try:
        print("Running candidate match evaluation utilizing Google's Context Caching API...")
        eval_result = evaluate_job_fit(job_analysis_json, args.portfolio, mock=run_mock)
        eval_result_json = eval_result.model_dump_json(indent=2)
        
        print("\n[+] Evaluation Successful!")
        print(f"Fit Score: {eval_result.fit_score_out_of_100}/100")
        print(f"Go/No-Go Decision: {'GO' if eval_result.go_no_go else 'NO-GO'}")
        print(f"Technical Gaps Identified: {len(eval_result.technical_gaps)}")
        for gap in eval_result.technical_gaps:
            print(f" - {gap}")
            
        # Save evaluation JSON
        eval_save_path = os.path.join(args.outdir, "fit_evaluation.json")
        with open(eval_save_path, "w") as f:
            f.write(eval_result_json)
        print(f"Saved evaluation analysis to: {eval_save_path}")
        
    except Exception as e:
        print(f"[-] Critical Error in Evaluator Agent: {e}")
        sys.exit(1)
        
    # 4. Process Go/No-Go Decision
    if not eval_result.go_no_go:
        print_banner("Pipeline Terminated")
        print(f"[-] Fit score ({eval_result.fit_score_out_of_100}) fell below threshold or critical blockers were found.")
        print("Skipping Tailoring and Interview Coaching agents. Good luck on your next search!")
        sys.exit(0)
        
    # 5. Agent 3 - Tailor (Claude 3.5 Sonnet)
    print_banner("Agent 3: Tailoring Application Materials (Claude 3.5 Sonnet)")
    try:
        print("Executing resume customization and cover letter tailoring...")
        latex_resume, markdown_cover_letter = tailor_application_materials(
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=run_mock
        )
        
        # Save LaTeX Resume
        resume_path = os.path.join(args.outdir, "tailored_resume.tex")
        with open(resume_path, "w") as f:
            f.write(latex_resume)
            
        # Save Cover Letter
        cover_letter_path = os.path.join(args.outdir, "cover_letter.md")
        with open(cover_letter_path, "w") as f:
            f.write(markdown_cover_letter)
            
        print("\n[+] Tailoring Successful!")
        print(f"Saved tailored LaTeX resume source to: {resume_path}")
        print(f"Saved tailored cover letter to: {cover_letter_path}")
        
    except Exception as e:
        print(f"[-] Critical Error in Tailor Agent: {e}")
        sys.exit(1)
        
    # 6. Agent 4 - Interview Coach (Claude 3.5 Sonnet)
    print_banner("Agent 4: Interview Preparation Strategy (Claude 3.5 Sonnet)")
    try:
        print("Generating custom interview preparation guide tailored to job specs and gaps...")
        questions = generate_interview_prep(
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=run_mock
        )
        
        # Compile questions into a beautiful Markdown guide
        coach_save_path = os.path.join(args.outdir, "interview_prep.md")
        with open(coach_save_path, "w") as f:
            f.write(f"# Interview Preparation Guide - {job_analysis.role_title}\n\n")
            f.write("This guide is custom-generated by your AI Interview Coach based on your match analysis and technical gaps.\n\n")
            f.write("## Targeted Interview Questions & Strategies\n\n")
            
            for idx, q in enumerate(questions, 1):
                f.write(f"### Q{idx}: {q['question']}\n")
                f.write(f"**Type:** {q['type']}  \n")
                f.write(f"**Why this is asked:** {q['rationale']}  \n")
                f.write(f"**Suggested Strategy:**\n{q['suggested_strategy']}\n\n")
                f.write("---\n\n")
                
        print("\n[+] Interview Prep Guide Created!")
        print(f"Saved custom preparation guide to: {coach_save_path}")
        print(f"Review the generated prep guide to refine your answers before the interview.")
        
    except Exception as e:
        print(f"[-] Critical Error in Coach Agent: {e}")
        sys.exit(1)
        
    print_banner("Orchestration Pipeline Complete")
    print(f"[SUCCESS] All agents have executed successfully! All output files are in '{args.outdir}/'.")

if __name__ == "__main__":
    main()
