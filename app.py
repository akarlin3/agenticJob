import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Import agent pipeline modules
from ingestion import ingest_job_description
from evaluator import evaluate_job_fit
from tailor import tailor_application_materials
from coach import generate_interview_prep
from create_portfolio import generate_portfolio
from searcher import search_jobs

app = FastAPI(title="Multi-Agent Job Search Pipeline API")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
os.makedirs("output", exist_ok=True)

# Endpoint to check backend health
@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/search")
async def run_search(
    query: str = Form(...),
    location: str = Form(...),
    platforms: str = Form(...), # Comma separated list of boards
    date_posted: str = Form("month"), # all | today | 3days | week | month
    remote: bool = Form(False),
    mock: bool = Form(True)
):
    """
    POST route to search real job boards using Agent 0 (JSearch primary,
    Adzuna fallback). No login/credential flow.
    """
    try:
        platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
        if not platform_list:
            platform_list = ["LinkedIn", "Indeed"]

        jobs = search_jobs(
            query=query,
            location=location,
            platforms=platform_list,
            date_posted=date_posted,
            remote=remote,
            mock=mock
        )
        return {"status": "success", "jobs": jobs}
    except Exception as e:
        # Surface the actionable error from search_jobs (e.g. the
        # "no provider configured" RuntimeError) as the detail.
        print(f"Error in search API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/run")
async def run_pipeline(
    job_description: str = Form(...),
    mock: bool = Form(True),
    portfolio: UploadFile = File(None)
):
    logs = []
    def log(msg: str):
        print(f"[Web Pipeline] {msg}")
        logs.append(msg)

    log("Initializing Hybrid Multi-Agent Job Search Pipeline...")
    
    # 1. Handle Portfolio Upload
    portfolio_path = "master_portfolio.pdf"
    if portfolio:
        log(f"Received portfolio upload: '{portfolio.filename}'")
        try:
            with open(portfolio_path, "wb") as buffer:
                shutil.copyfileobj(portfolio.file, buffer)
            log("Portfolio saved successfully.")
        except Exception as e:
            log(f"Error saving uploaded portfolio: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded portfolio: {e}")
    else:
        if not os.path.exists(portfolio_path):
            log("No master portfolio uploaded or found. Generating a modern sample portfolio using create_portfolio.py...")
            try:
                generate_portfolio(portfolio_path)
                log("Modern portfolio PDF generated successfully.")
            except Exception as e:
                log(f"Error compiling portfolio PDF: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate default portfolio: {e}")
        else:
            log("Using existing master_portfolio.pdf found in workspace.")

    # 2. Agent 1 - Ingestion (Gemini 2.5 Flash)
    log("Agent 1 (Ingestion): Analyzing job description and extracting structured metadata...")
    try:
        job_analysis = ingest_job_description(job_description, mock=mock)
        job_analysis_dict = job_analysis.model_dump()
        job_analysis_json = job_analysis.model_dump_json(indent=2)
        
        # Save to output
        with open("output/job_analysis.json", "w") as f:
            f.write(job_analysis_json)
            
        log(f"Structured Ingestion Successful. Role identified: '{job_analysis.role_title}'")
    except Exception as e:
        log(f"Error in Agent 1 Ingestion: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Agent 1 Ingestion failed: {str(e)}", "logs": logs}
        )

    # 3. Agent 2 - Evaluator (Gemini 2.5 Pro + Context Caching)
    log("Agent 2 (Evaluator): Evaluating candidate credentials against job requirements with Context Caching...")
    try:
        eval_result = evaluate_job_fit(job_analysis_json, portfolio_path, mock=mock)
        eval_result_dict = eval_result.model_dump()
        eval_result_json = eval_result.model_dump_json(indent=2)
        
        # Save to output
        with open("output/fit_evaluation.json", "w") as f:
            f.write(eval_result_json)
            
        log(f"Evaluation Complete. Fit Score: {eval_result.fit_score_out_of_100}/100. Go/No-Go: {'GO' if eval_result.go_no_go else 'NO-GO'}")
    except Exception as e:
        log(f"Error in Agent 2 Evaluator: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Agent 2 Evaluator failed: {str(e)}", "logs": logs}
        )

    # 4. Handle No-Go Termination
    if not eval_result.go_no_go:
        log("Pipeline terminated: candidate match score fell below Go threshold.")
        return {
            "status": "terminated",
            "job_analysis": job_analysis_dict,
            "fit_evaluation": eval_result_dict,
            "tailored_resume": None,
            "cover_letter": None,
            "interview_prep": None,
            "logs": logs
        }

    # 5. Agent 3 - Tailor (Claude 3.5 Sonnet)
    log("Agent 3 (Tailor): Tailoring application materials utilizing forced tool calling...")
    tailored_resume = ""
    cover_letter = ""
    try:
        tailored_resume, cover_letter = tailor_application_materials(
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=mock
        )
        
        # Save output files
        with open("output/tailored_resume.tex", "w") as f:
            f.write(tailored_resume)
        with open("output/cover_letter.md", "w") as f:
            f.write(cover_letter)
            
        log("Tailored LaTeX resume and cover letter successfully created and saved.")
    except Exception as e:
        log(f"Error in Agent 3 Tailor: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Agent 3 Tailoring failed: {str(e)}", "logs": logs}
        )

    # 6. Agent 4 - Interview Coach (Claude 3.5 Sonnet)
    log("Agent 4 (Interview Coach): Generating targeted preparation guide to defend technical gaps...")
    questions = []
    try:
        questions = generate_interview_prep(
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=mock
        )
        
        # Save Markdown Guide
        coach_save_path = "output/interview_prep.md"
        with open(coach_save_path, "w") as f:
            f.write(f"# Interview Preparation Guide - {job_analysis.role_title}\n\n")
            f.write("This guide is custom-generated by your AI Interview Coach based on your match analysis.\n\n")
            f.write("## Targeted Interview Questions & Strategies\n\n")
            
            for idx, q in enumerate(questions, 1):
                f.write(f"### Q{idx}: {q['question']}\n")
                f.write(f"**Type:** {q['type']}  \n")
                f.write(f"**Why this is asked:** {q['rationale']}  \n")
                f.write(f"**Suggested Strategy:**\n{q['suggested_strategy']}\n\n")
                f.write("---\n\n")
                
        log("Custom interview prep guide compiled and saved successfully.")
    except Exception as e:
        log(f"Error in Agent 4 Coach: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Agent 4 Coaching failed: {str(e)}", "logs": logs}
        )

    log("Multi-Agent Orchestration Pipeline completed successfully!")
    return {
        "status": "success",
        "job_analysis": job_analysis_dict,
        "fit_evaluation": eval_result_dict,
        "tailored_resume": tailored_resume,
        "cover_letter": cover_letter,
        "interview_prep": questions,
        "logs": logs
    }

# File Download endpoints
@app.get("/api/download/resume")
def download_resume():
    path = "output/tailored_resume.tex"
    if os.path.exists(path):
        return FileResponse(path, media_type="text/plain", filename="tailored_resume.tex")
    raise HTTPException(status_code=404, detail="Tailored resume not found. Run the pipeline first.")

@app.get("/api/download/cover-letter")
def download_cover_letter():
    path = "output/cover_letter.md"
    if os.path.exists(path):
        return FileResponse(path, media_type="text/markdown", filename="cover_letter.md")
    raise HTTPException(status_code=404, detail="Cover letter not found. Run the pipeline first.")

@app.get("/api/download/interview-prep")
def download_interview_prep():
    path = "output/interview_prep.md"
    if os.path.exists(path):
        return FileResponse(path, media_type="text/markdown", filename="interview_prep.md")
    raise HTTPException(status_code=404, detail="Interview guide not found. Run the pipeline first.")

# Serve static files (HTML, CSS, JS) from static directory
app.mount("/", StaticFiles(directory="static", html=True), name="static")
