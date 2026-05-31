import logging
import os
import json
import shutil
import subprocess
from typing import AsyncGenerator, Optional, Tuple

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# Import agent pipeline modules
from config import settings
from ingestion import ingest_job_description
from evaluator import evaluate_job_fit
from tailor import tailor_application_materials
from coach import generate_interview_prep
from create_portfolio import generate_portfolio
from searcher import search_jobs

PDF_MAGIC = b"%PDF-"
OUTPUT_DIR = "output"
RESUME_TEX_PATH = os.path.join(OUTPUT_DIR, "tailored_resume.tex")
RESUME_PDF_PATH = os.path.join(OUTPUT_DIR, "tailored_resume.pdf")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Job Search Pipeline API")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _resolve_portfolio(portfolio: Optional[UploadFile]) -> str:
    """Validate + persist an uploaded portfolio, or fall back to existing/sample.

    Raises HTTPException on invalid uploads; otherwise returns a filesystem path.
    """
    portfolio_path = "master_portfolio.pdf"
    if portfolio:
        contents = await portfolio.read(settings.max_upload_bytes + 1)
        if len(contents) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Uploaded portfolio exceeds maximum size of "
                    f"{settings.max_upload_bytes} bytes."
                ),
            )
        if not contents.startswith(PDF_MAGIC):
            raise HTTPException(
                status_code=400,
                detail="Uploaded portfolio is not a valid PDF file.",
            )
        try:
            with open(portfolio_path, "wb") as buffer:
                buffer.write(contents)
        except Exception as e:
            logger.error("Failed to save uploaded portfolio: %s", e)
            raise HTTPException(
                status_code=500, detail=f"Failed to save uploaded portfolio: {e}"
            )
        return portfolio_path

    if not os.path.exists(portfolio_path):
        try:
            await run_in_threadpool(generate_portfolio, portfolio_path)
        except Exception as e:
            logger.error("Failed to generate default portfolio: %s", e)
            raise HTTPException(
                status_code=500, detail=f"Failed to generate default portfolio: {e}"
            )
    return portfolio_path


def _compile_resume_pdf() -> bool:
    """Compile output/tailored_resume.tex -> output/tailored_resume.pdf via Tectonic.

    Returns True on success. Logs a warning and returns False if Tectonic is
    missing or the compile fails — never raises, so a PDF failure can't take
    down an otherwise-successful pipeline run.
    """
    if shutil.which("tectonic") is None:
        logger.info("Tectonic not installed; skipping server-side PDF render.")
        return False
    if not os.path.exists(RESUME_TEX_PATH):
        return False
    # Clear any stale PDF first so callers can trust file existence as success.
    if os.path.exists(RESUME_PDF_PATH):
        try:
            os.remove(RESUME_PDF_PATH)
        except OSError:
            pass
    try:
        result = subprocess.run(
            ["tectonic", "--outdir", OUTPUT_DIR, RESUME_TEX_PATH],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:
        logger.warning("Tectonic invocation failed: %s", e)
        return False
    if result.returncode != 0:
        logger.warning(
            "Tectonic returned %d compiling resume: %s",
            result.returncode,
            result.stderr.strip()[-500:],
        )
        return False
    return os.path.exists(RESUME_PDF_PATH) and os.path.getsize(RESUME_PDF_PATH) > 0


async def _pipeline_events(
    job_description: str, mock: bool, portfolio_path: str
) -> AsyncGenerator[Tuple[str, dict], None]:
    """Drive the multi-agent pipeline, yielding (event_type, payload) tuples.

    Event types:
      log         {"message": str}
      stage       {"name": str, "status": "active"|"completed"|"error"}
      result      {"key": str, "value": Any}
      terminated  {"reason": str}     (NO-GO path)
      error       {"stage": str, "message": str}
      done        {"status": "success"}
    """

    def _log(msg: str):
        logger.info("[Web Pipeline] %s", msg)

    _log("Initializing Hybrid Multi-Agent Job Search Pipeline...")
    yield "log", {"message": "Initializing Hybrid Multi-Agent Job Search Pipeline..."}

    # Agent 1 - Ingestion
    yield "stage", {"name": "ingestion", "status": "active"}
    yield "log", {
        "message": "Agent 1 (Ingestion): Analyzing job description and extracting structured metadata..."
    }
    try:
        job_analysis = await run_in_threadpool(
            ingest_job_description, job_description, mock=mock
        )
        job_analysis_dict = job_analysis.model_dump()
        job_analysis_json = job_analysis.model_dump_json(indent=2)
        with open(os.path.join(OUTPUT_DIR, "job_analysis.json"), "w") as f:
            f.write(job_analysis_json)
    except Exception as e:
        logger.exception("Agent 1 Ingestion failed")
        yield "stage", {"name": "ingestion", "status": "error"}
        yield "error", {"stage": "ingestion", "message": f"Agent 1 Ingestion failed: {e}"}
        return

    yield "result", {"key": "job_analysis", "value": job_analysis_dict}
    yield "log", {
        "message": f"Structured Ingestion Successful. Role identified: '{job_analysis.role_title}'"
    }
    yield "stage", {"name": "ingestion", "status": "completed"}

    # Agent 2 - Evaluator
    yield "stage", {"name": "evaluator", "status": "active"}
    yield "log", {
        "message": "Agent 2 (Evaluator): Evaluating candidate credentials against job requirements with Context Caching..."
    }
    try:
        eval_result = await run_in_threadpool(
            evaluate_job_fit, job_analysis_json, portfolio_path, mock=mock
        )
        eval_result_dict = eval_result.model_dump()
        eval_result_json = eval_result.model_dump_json(indent=2)
        with open(os.path.join(OUTPUT_DIR, "fit_evaluation.json"), "w") as f:
            f.write(eval_result_json)
    except Exception as e:
        logger.exception("Agent 2 Evaluator failed")
        yield "stage", {"name": "evaluator", "status": "error"}
        yield "error", {"stage": "evaluator", "message": f"Agent 2 Evaluator failed: {e}"}
        return

    yield "result", {"key": "fit_evaluation", "value": eval_result_dict}
    yield "log", {
        "message": (
            f"Evaluation Complete. Fit Score: {eval_result.fit_score_out_of_100}/100. "
            f"Go/No-Go: {'GO' if eval_result.go_no_go else 'NO-GO'}"
        )
    }
    yield "stage", {"name": "evaluator", "status": "completed"}

    if not eval_result.go_no_go:
        yield "log", {
            "message": "Pipeline terminated: candidate match score fell below Go threshold."
        }
        yield "terminated", {"reason": "fit_below_threshold"}
        return

    # Agent 3 - Tailor
    yield "stage", {"name": "tailor", "status": "active"}
    yield "log", {
        "message": "Agent 3 (Tailor): Tailoring application materials utilizing forced tool calling..."
    }
    try:
        tailored_resume, cover_letter = await run_in_threadpool(
            tailor_application_materials,
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=mock,
        )
        with open(RESUME_TEX_PATH, "w") as f:
            f.write(tailored_resume)
        with open(os.path.join(OUTPUT_DIR, "cover_letter.md"), "w") as f:
            f.write(cover_letter)
    except Exception as e:
        logger.exception("Agent 3 Tailor failed")
        yield "stage", {"name": "tailor", "status": "error"}
        yield "error", {"stage": "tailor", "message": f"Agent 3 Tailoring failed: {e}"}
        return

    yield "result", {"key": "tailored_resume", "value": tailored_resume}
    yield "result", {"key": "cover_letter", "value": cover_letter}
    yield "log", {
        "message": "Tailored LaTeX resume and cover letter successfully created and saved."
    }
    yield "stage", {"name": "tailor", "status": "completed"}

    # Best-effort PDF render — failure here must not abort the run.
    pdf_ok = await run_in_threadpool(_compile_resume_pdf)
    if pdf_ok:
        yield "log", {"message": "Compiled tailored_resume.pdf via Tectonic."}
        yield "result", {"key": "tailored_resume_pdf_available", "value": True}
    else:
        yield "log", {
            "message": "PDF render unavailable; .tex source is still downloadable."
        }
        yield "result", {"key": "tailored_resume_pdf_available", "value": False}

    # Agent 4 - Coach
    yield "stage", {"name": "coach", "status": "active"}
    yield "log", {
        "message": "Agent 4 (Interview Coach): Generating targeted preparation guide to defend technical gaps..."
    }
    try:
        questions = await run_in_threadpool(
            generate_interview_prep,
            job_details_json=job_analysis_json,
            gap_analysis_json=eval_result_json,
            mock=mock,
        )
        coach_save_path = os.path.join(OUTPUT_DIR, "interview_prep.md")
        with open(coach_save_path, "w") as f:
            f.write(f"# Interview Preparation Guide - {job_analysis.role_title}\n\n")
            f.write(
                "This guide is custom-generated by your AI Interview Coach based on your match analysis.\n\n"
            )
            f.write("## Targeted Interview Questions & Strategies\n\n")
            for idx, q in enumerate(questions, 1):
                f.write(f"### Q{idx}: {q['question']}\n")
                f.write(f"**Type:** {q['type']}  \n")
                f.write(f"**Why this is asked:** {q['rationale']}  \n")
                f.write(f"**Suggested Strategy:**\n{q['suggested_strategy']}\n\n")
                f.write("---\n\n")
    except Exception as e:
        logger.exception("Agent 4 Coach failed")
        yield "stage", {"name": "coach", "status": "error"}
        yield "error", {"stage": "coach", "message": f"Agent 4 Coaching failed: {e}"}
        return

    yield "result", {"key": "interview_prep", "value": questions}
    yield "log", {"message": "Custom interview prep guide compiled and saved successfully."}
    yield "stage", {"name": "coach", "status": "completed"}

    yield "log", {"message": "Multi-Agent Orchestration Pipeline completed successfully!"}
    yield "done", {"status": "success"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


@app.post("/api/search")
async def run_search(
    query: str = Form(...),
    location: str = Form(...),
    platforms: str = Form(...),
    date_posted: str = Form("month"),
    remote: bool = Form(False),
    mock: bool = Form(True),
):
    try:
        platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
        if not platform_list:
            platform_list = ["LinkedIn", "Indeed"]
        jobs = await run_in_threadpool(
            search_jobs,
            query=query,
            location=location,
            platforms=platform_list,
            date_posted=date_posted,
            remote=remote,
            mock=mock,
        )
        return {"status": "success", "jobs": jobs}
    except Exception as e:
        logger.error("Error in search API: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run")
async def run_pipeline(
    job_description: str = Form(...),
    mock: bool = Form(True),
    portfolio: UploadFile = File(None),
):
    """Batch endpoint kept for the existing test suite and any non-streaming
    consumers. Internally drains the same event generator and assembles a
    legacy JSON payload."""
    portfolio_path = await _resolve_portfolio(portfolio)

    logs: list = []
    results: dict = {
        "job_analysis": None,
        "fit_evaluation": None,
        "tailored_resume": None,
        "cover_letter": None,
        "interview_prep": None,
    }
    terminated = False
    error_payload: Optional[dict] = None

    async for event, payload in _pipeline_events(job_description, mock, portfolio_path):
        if event == "log":
            logs.append(payload["message"])
        elif event == "result":
            if payload["key"] in results:
                results[payload["key"]] = payload["value"]
        elif event == "terminated":
            terminated = True
        elif event == "error":
            error_payload = payload

    if error_payload is not None:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": error_payload["message"],
                "logs": logs,
            },
        )

    return {
        "status": "terminated" if terminated else "success",
        "job_analysis": results["job_analysis"],
        "fit_evaluation": results["fit_evaluation"],
        "tailored_resume": results["tailored_resume"],
        "cover_letter": results["cover_letter"],
        "interview_prep": results["interview_prep"],
        "logs": logs,
    }


def _sse_frame(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")


@app.post("/api/run/stream")
async def run_pipeline_stream(
    job_description: str = Form(...),
    mock: bool = Form(True),
    portfolio: UploadFile = File(None),
):
    """Server-Sent Events variant of /api/run. The portfolio upload is
    validated synchronously *before* streaming starts so a bad upload still
    returns a proper HTTP error status."""
    portfolio_path = await _resolve_portfolio(portfolio)

    async def event_source():
        try:
            async for event, payload in _pipeline_events(
                job_description, mock, portfolio_path
            ):
                yield _sse_frame(event, payload)
        except Exception as e:
            logger.exception("Streaming pipeline crashed")
            yield _sse_frame("error", {"stage": "pipeline", "message": str(e)})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# File Download endpoints
@app.get("/api/download/resume")
def download_resume():
    if os.path.exists(RESUME_TEX_PATH):
        return FileResponse(
            RESUME_TEX_PATH, media_type="text/plain", filename="tailored_resume.tex"
        )
    raise HTTPException(status_code=404, detail="Tailored resume not found. Run the pipeline first.")


@app.get("/api/download/resume-pdf")
def download_resume_pdf():
    if os.path.exists(RESUME_PDF_PATH) and os.path.getsize(RESUME_PDF_PATH) > 0:
        return FileResponse(
            RESUME_PDF_PATH, media_type="application/pdf", filename="tailored_resume.pdf"
        )
    raise HTTPException(
        status_code=404,
        detail="Tailored resume PDF not available (Tectonic missing or compile failed).",
    )


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
