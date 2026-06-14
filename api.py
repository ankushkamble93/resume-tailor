"""
api.py — FastAPI HTTP layer for the resume-tailor pipeline.

Exposes the existing CLI engine as a JSON REST API so the React frontend
can invoke it without touching any of the existing Python modules.

Start with:
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from agent import LayoutParams
from engine import (
    analyze_job_description,
    build_proof_pack,
    evaluate_resume_quality,
    refine_resume_for_quality,
    tailor_resume_data,
)
from models import JDKeywords, ResumeSchema

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
MASTER_RESUME_PATH = PROJECT_ROOT / "data" / "master_resume.json"
TEMPLATE_PATH = PROJECT_ROOT / "template.typ"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
DESKTOP_RESUME_PATH = Path.home() / "Desktop" / "resume" / "Ankush_Kamble_Resume_2026.pdf"

# Serialise PDF compilation so concurrent requests don't clobber workspace/
_pdf_lock = threading.Lock()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Resume Tailor API",
    description="LLM-powered resume tailoring. POST your master resume and a job description; get back a tailored resume.",
    version="1.0.0",
)

# CORS — allow the Vite dev server and any production origin you add later
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:4173",   # Vite preview
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class TailorRequest(BaseModel):
    master_resume: ResumeSchema
    job_description: str


class TailorResponse(BaseModel):
    tailored_resume: ResumeSchema
    keywords: JDKeywords


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe — returns 200 when the server is up."""
    return HealthResponse(status="ok", version="1.0.0")


@app.get("/api/master-resume", response_model=ResumeSchema, tags=["resume"])
def get_master_resume() -> ResumeSchema:
    """
    Return the local master_resume.json as structured JSON.
    Used by the frontend to pre-load the resume on startup so you never
    have to upload the file manually during local development.
    """
    if not MASTER_RESUME_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"master_resume.json not found at {MASTER_RESUME_PATH}",
        )
    try:
        return ResumeSchema.model_validate_json(
            MASTER_RESUME_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse master_resume.json: {exc}") from exc


@app.post("/api/tailor", response_model=TailorResponse, tags=["resume"])
def tailor(body: TailorRequest) -> TailorResponse:
    """
    Tailor a master resume to a job description.

    Runs the full LLM pipeline (analyze JD → tailor content → quality gate)
    and returns the tailored resume as structured JSON.

    Note: this endpoint may take 1–3 minutes depending on your LLM provider
    and the length of the input. FastAPI runs sync routes in a thread pool so
    the event loop remains unblocked for other requests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write JD text to a temp file — analyze_job_description() expects a path
        jd_file = tmp / "job_description.txt"
        jd_file.write_text(body.job_description, encoding="utf-8")

        # ── Step 1: Extract keywords from JD ─────────────────────────────────
        logger.info("Analysing job description (%d chars)…", len(body.job_description))
        try:
            jd_result: JDKeywords = analyze_job_description(str(jd_file))
        except Exception as exc:
            logger.exception("JD analysis failed")
            raise HTTPException(status_code=500, detail=f"JD analysis failed: {exc}") from exc

        keywords = jd_result.all_keywords
        job_role_type = jd_result.job_role_type
        logger.info("Role type: %s | keywords: %d", job_role_type, len(keywords))

        # ── Step 2: Build proof pack ──────────────────────────────────────────
        try:
            proof_pack = build_proof_pack(body.master_resume, keywords)
        except Exception as exc:
            logger.exception("Proof-pack build failed")
            raise HTTPException(status_code=500, detail=f"Proof-pack build failed: {exc}") from exc

        # ── Step 3: Tailor resume content via LLM ────────────────────────────
        logger.info("Tailoring resume…")
        try:
            tailored = tailor_resume_data(
                body.master_resume,
                keywords,
                proof_pack=proof_pack,
                job_role_type=job_role_type,
            )
        except Exception as exc:
            logger.exception("Tailoring failed")
            raise HTTPException(status_code=500, detail=f"Resume tailoring failed: {exc}") from exc

        # ── Step 4: Quality gate + one refinement pass if needed ──────────────
        quality = evaluate_resume_quality(tailored, job_role_type=job_role_type)
        if not quality.passed:
            logger.info("Quality gate FAIL — running one refinement pass…")
            try:
                tailored = refine_resume_for_quality(
                    tailored, keywords, proof_pack, quality, job_role_type=job_role_type
                )
            except Exception as exc:
                logger.exception("Quality refinement failed")
                raise HTTPException(status_code=500, detail=f"Quality refinement failed: {exc}") from exc

        logger.info("Tailoring complete.")
        return TailorResponse(tailored_resume=tailored, keywords=jd_result)


@app.post("/api/download-pdf", tags=["resume"])
def download_pdf(body: ResumeSchema) -> Response:
    """
    Compile a ResumeSchema to a 1-page PDF using the Typst template and
    return the raw PDF bytes for direct browser download.

    Uses a threading lock so concurrent requests don't corrupt the shared
    workspace/tailored_resume.json file that Typst reads.
    """
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="template.typ not found — cannot compile PDF.")

    with _pdf_lock:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        json_path = WORKSPACE_DIR / "tailored_resume.json"
        json_path.write_text(body.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Compiling PDF from tailored resume JSON…")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            pdf_path = Path(tmp_pdf.name)

        try:
            layout = LayoutParams()
            cmd = [
                "typst", "compile",
                str(TEMPLATE_PATH),
                str(pdf_path),
                "--input", f"font_size={layout.font_size}",
                "--input", f"top_margin={layout.top_margin}",
                "--input", f"bottom_margin={layout.bottom_margin}",
                "--input", f"side_margin={layout.side_margin}",
                "--input", f"line_spacing={layout.line_spacing}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Typst compilation failed: {proc.stderr.strip()}",
                )

            pdf_bytes = pdf_path.read_bytes()
            logger.info("PDF compiled successfully (%d bytes).", len(pdf_bytes))

            # Save a copy to Desktop/resume for easy local access
            DESKTOP_RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
            DESKTOP_RESUME_PATH.write_bytes(pdf_bytes)
            logger.info("Saved copy to %s", DESKTOP_RESUME_PATH)

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="tailored_resume.pdf"'},
            )
        finally:
            pdf_path.unlink(missing_ok=True)
