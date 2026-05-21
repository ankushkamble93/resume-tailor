"""
main.py — CLI entrypoint for the resume-tailor agent.

Usage:
    python main.py run \
        --master ./data/master_resume.json \
        --jd     ./data/job_description.txt \
        --output ./tailored_resume.pdf
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # loads .env from the current working directory

import typer
from rich.console import Console
from rich.logging import RichHandler

from agent import run_agent
from engine import analyze_job_description
from models import ResumeSchema

# ── Logging setup (rich-formatted, INFO by default) ──────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=False)],
)
logger = logging.getLogger(__name__)
console = Console()

# ── Typer app ────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="resume-tailor",
    help="Autonomous resume-tailoring agent — outputs a guaranteed 1-page PDF.",
    add_completion=False,
)


@app.command()
def run(
    master: Path = typer.Option(
        ...,
        "--master",
        exists=True,
        readable=True,
        help="Path to master_resume.json (structured resume data).",
    ),
    jd: Path = typer.Option(
        ...,
        "--jd",
        exists=True,
        readable=True,
        help="Path to the target job_description.txt.",
    ),
    output: Path = typer.Option(
        Path("./tailored_resume.pdf"),
        "--output",
        help="Destination path for the generated PDF.",
    ),
    workspace: Path = typer.Option(
        Path("./workspace"),
        "--workspace",
        help="Scratch directory for intermediate JSON artifacts.",
        show_default=True,
    ),
    template: Path = typer.Option(
        Path("./template.typ"),
        "--template",
        exists=True,
        readable=True,
        help="Path to the Typst resume template.",
        show_default=True,
    ),
    max_semantic_passes: int = typer.Option(
        8,
        "--max-passes",
        help="Maximum LLM compaction iterations in Pass 3.",
        show_default=True,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable DEBUG-level logging."
    ),
) -> None:
    """Tailor a master resume to a job description and produce a 1-page PDF."""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console.rule("[bold cyan]Resume Tailor — Autonomous Agent")

    # ── Step 1: Load and validate master resume ───────────────────────────────
    logger.info("Loading master resume from %s…", master)
    try:
        master_data = ResumeSchema.model_validate_json(master.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse master_resume.json: %s", exc)
        raise typer.Exit(code=1)

    logger.info(
        "  %d experience(s), %d project(s), %d skill group(s)",
        len(master_data.experience),
        len(master_data.projects),
        len(master_data.skills),
    )

    # ── Step 2: Analyse the job description ───────────────────────────────────
    logger.info("Analysing job description from %s…", jd)
    try:
        keywords = analyze_job_description(str(jd))
    except Exception as exc:
        logger.error("JD analysis failed: %s", exc)
        raise typer.Exit(code=1)

    logger.info("  Keywords: %s", ", ".join(keywords[:10]) + (" …" if len(keywords) > 10 else ""))

    # ── Step 3: Run the multi-pass agent ─────────────────────────────────────
    logger.info("Starting agentic optimization loop…")
    try:
        run_agent(
            master_data=master_data,
            keywords=keywords,
            template_path=template,
            output_path=output,
            workspace=workspace,
            max_semantic_passes=max_semantic_passes,
        )
    except EnvironmentError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        logger.error("Compile error: %s", exc)
        raise typer.Exit(code=1)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        raise typer.Exit(code=1)

    console.rule()
    console.print(f"[bold green]Output saved to:[/bold green] {output.resolve()}")


if __name__ == "__main__":
    app()
