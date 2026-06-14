"""
agent.py — Multi-pass autonomous loop that guarantees a 1-page PDF output.

Pass 1 — Compile & Check
    Write tailored JSON, invoke `typst compile`, count pages with pypdf.
    If page count == 1 → done.

Pass 2 — Geometry Tightening  (no LLM calls)
    Iteratively lower: font size (11 → 10 pt), top/bottom margins (2 → 1.2 cm),
    side margins (1.5 → 1.2 cm), line spacing (1.15 → 1.0).
    Re-compile and recheck after each micro-step.

Pass 3 — Semantic Content Reduction  (LLM compaction loop)
    When layout is at its safe minimum and the PDF is still > 1 page, call
    engine.compact_resume_content() to shorten the longest bullets, then
    recompile. Repeat up to `max_semantic_passes` times.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pypdf

from engine import (
    build_proof_pack,
    collect_diagnostics,
    compact_resume_content,
    evaluate_resume_quality,
    refine_resume_for_quality,
    tailor_resume_data,
)
from models import ResumeSchema

logger = logging.getLogger(__name__)

# ── Layout constraint constants ─────────────────────────────────────────────

FONT_DEFAULT = 11.0
FONT_FLOOR = 10.0
FONT_STEP = 0.25

TOP_DEFAULT = 2.0
TOP_FLOOR = 1.2

BOT_DEFAULT = 2.0
BOT_FLOOR = 1.2

SIDE_DEFAULT = 1.5
SIDE_FLOOR = 1.2

MARGIN_STEP = 0.1

LEADING_DEFAULT = 1.15
LEADING_FLOOR = 1.0
LEADING_STEP = 0.05


# ── Layout parameter dataclass ───────────────────────────────────────────────

@dataclass
class LayoutParams:
    font_size: float = FONT_DEFAULT
    top_margin: float = TOP_DEFAULT
    bottom_margin: float = BOT_DEFAULT
    side_margin: float = SIDE_DEFAULT
    line_spacing: float = LEADING_DEFAULT

    def at_minimum(self) -> bool:
        return (
            self.font_size <= FONT_FLOOR
            and self.top_margin <= TOP_FLOOR
            and self.bottom_margin <= BOT_FLOOR
            and self.side_margin <= SIDE_FLOOR
            and self.line_spacing <= LEADING_FLOOR
        )

    def tighten_one_step(self) -> bool:
        """
        Apply the smallest possible layout tightening in priority order.
        Returns True if a change was made, False when already at minimum.
        """
        r = round  # alias for brevity
        if self.font_size > FONT_FLOOR:
            self.font_size = r(self.font_size - FONT_STEP, 2)
            return True
        if self.top_margin > TOP_FLOOR:
            self.top_margin = r(self.top_margin - MARGIN_STEP, 2)
            return True
        if self.bottom_margin > BOT_FLOOR:
            self.bottom_margin = r(self.bottom_margin - MARGIN_STEP, 2)
            return True
        if self.side_margin > SIDE_FLOOR:
            self.side_margin = r(self.side_margin - MARGIN_STEP, 2)
            return True
        if self.line_spacing > LEADING_FLOOR:
            self.line_spacing = r(self.line_spacing - LEADING_STEP, 2)
            return True
        return False

    def describe(self) -> str:
        return (
            f"font={self.font_size}pt | "
            f"top={self.top_margin}cm | bot={self.bottom_margin}cm | "
            f"side={self.side_margin}cm | leading={self.line_spacing}"
        )


# ── Core helpers ─────────────────────────────────────────────────────────────

WORKSPACE_JSON = "tailored_resume.json"


def _write_json(data: ResumeSchema, workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / WORKSPACE_JSON
    path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    logger.info("  JSON payload written → %s", path)
    return path


def _compile_pdf(
    template: Path,
    output: Path,
    layout: LayoutParams,
) -> None:
    """
    Call `typst compile` via subprocess.

    The template reads the JSON from the fixed workspace path
    (./workspace/tailored_resume.json relative to template location).
    Layout geometry is injected via --input flags.
    """
    cmd: List[str] = [
        "typst",
        "compile",
        str(template),
        str(output),
        "--input", f"font_size={layout.font_size}",
        "--input", f"top_margin={layout.top_margin}",
        "--input", f"bottom_margin={layout.bottom_margin}",
        "--input", f"side_margin={layout.side_margin}",
        "--input", f"line_spacing={layout.line_spacing}",
    ]
    logger.debug("  CMD: %s", " ".join(cmd))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"typst compile failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
        )


def _page_count(pdf: Path) -> int:
    return len(pypdf.PdfReader(str(pdf)).pages)


# ── Compile already-tailored content to 1 page ──────────────────────────────

def compile_to_one_page(
    data: ResumeSchema,
    template_path: Path,
    output_path: Path,
    workspace: Path,
    max_semantic_passes: int = 8,
) -> ResumeSchema:
    """
    Take already-tailored resume data and compile it to a guaranteed 1-page PDF.

    Skips Pass 1 (LLM tailoring) — call this when the content is already
    tailored and you only need the geometry tightening and compaction loop.

    Returns the (possibly compacted) ResumeSchema that produced the 1-page PDF.
    """
    _check_typst_installed()

    layout = LayoutParams()
    _write_json(data, workspace)

    logger.info("Compiling PDF  [%s]", layout.describe())
    _compile_pdf(template_path, output_path, layout)
    pages = _page_count(output_path)
    logger.info("Page count: %d", pages)

    if pages == 1:
        logger.info("✅  1 page on first compile.")
        return data

    # ── PASS 2: Geometry tightening (no LLM) ─────────────────────────────────
    logger.info("━━━ PASS 2 — Geometry Tightening (%d page(s) → targeting 1)", pages)
    step = 0
    while True:
        changed = layout.tighten_one_step()
        if not changed:
            logger.info("  Layout at minimum. Proceeding to Pass 3.")
            break
        step += 1
        logger.info("  [step %2d]  %s", step, layout.describe())
        _compile_pdf(template_path, output_path, layout)
        pages = _page_count(output_path)
        logger.info("            page count: %d", pages)
        if pages == 1:
            logger.info("✅  Pass 2 success.")
            return data

    # ── PASS 3: Semantic compaction (LLM loop) ────────────────────────────────
    logger.info("━━━ PASS 3 — Semantic Compaction (still %d page(s))", pages)
    current = data
    for attempt in range(1, max_semantic_passes + 1):
        logger.info("  [compaction %d/%d]", attempt, max_semantic_passes)
        current = compact_resume_content(current)
        _write_json(current, workspace)
        _compile_pdf(template_path, output_path, layout)
        pages = _page_count(output_path)
        logger.info("  page count: %d", pages)
        if pages == 1:
            logger.info("✅  Pass 3 success.")
            return current

    logger.warning("⚠️  All passes exhausted. PDF has %d page(s).", pages)
    return current


# ── Main agent entry point ────────────────────────────────────────────────────

def run_agent(
    master_data: ResumeSchema,
    keywords: List[str],
    template_path: Path,
    output_path: Path,
    workspace: Path,
    max_semantic_passes: int = 8,
    emit_diagnostics: bool = False,
) -> None:
    """
    Orchestrate the full 3-pass pipeline to produce a guaranteed 1-page PDF.

    Args:
        master_data:         Validated ResumeSchema loaded from master_resume.json.
        keywords:            Keywords extracted from the target JD by engine.py.
        template_path:       Path to template.typ (project root).
        output_path:         Destination path for the final tailored_resume.pdf.
        workspace:           Directory where the intermediate JSON is written.
        max_semantic_passes: Safety ceiling on LLM compaction iterations.
    """
    _check_typst_installed()

    # ── PASS 1: Tailor content via LLM, compile, and check ───────────────────
    logger.info("")
    logger.info("━━━ PASS 1 — LLM Tailoring & Initial Compile ━━━━━━━━━━━━━━━━━━━━━━━━")
    proof_pack = build_proof_pack(master_data, keywords)
    tailored = tailor_resume_data(master_data, keywords, proof_pack=proof_pack)

    quality = evaluate_resume_quality(tailored)
    logger.info("  Quality gate: %s", "PASS" if quality.passed else "FAIL")
    logger.info("  Quality metrics: %s", json.dumps(quality.to_dict(), ensure_ascii=False))

    if not quality.passed:
        logger.info("  Triggering one targeted refinement pass before compile.")
        tailored = refine_resume_for_quality(tailored, keywords, proof_pack, quality)
        quality = evaluate_resume_quality(tailored)
        logger.info("  Quality metrics (after refinement): %s", json.dumps(quality.to_dict(), ensure_ascii=False))

    layout = LayoutParams()
    _write_json(tailored, workspace)

    if emit_diagnostics:
        diagnostics = collect_diagnostics(master_data, keywords, tailored, proof_pack=proof_pack)
        logger.info("  Diagnostics: %s", json.dumps(diagnostics, ensure_ascii=False))

    logger.info("  Compiling PDF   [%s]", layout.describe())
    _compile_pdf(template_path, output_path, layout)
    pages = _page_count(output_path)
    logger.info("  Page count: %d", pages)

    if pages == 1:
        logger.info("✅  Pass 1 success — PDF is exactly 1 page.")
        return

    # ── PASS 2: Geometry tightening (no LLM) ─────────────────────────────────
    logger.info("")
    logger.info("━━━ PASS 2 — Geometry Tightening (%d page(s) → targeting 1) ━━━━━━━━", pages)

    step = 0
    while True:
        changed = layout.tighten_one_step()
        if not changed:
            logger.info("  Layout is at its safe minimum. Switching to Pass 3.")
            break

        step += 1
        logger.info("  [step %2d]  %s", step, layout.describe())
        _compile_pdf(template_path, output_path, layout)
        pages = _page_count(output_path)
        logger.info("            page count: %d", pages)

        if pages == 1:
            logger.info("✅  Pass 2 success — geometry tightening achieved 1 page.")
            return

    # ── PASS 3: Semantic content compaction (LLM loop) ────────────────────────
    logger.info("")
    logger.info("━━━ PASS 3 — Semantic Compaction Loop (still %d page(s)) ━━━━━━━━━━━", pages)

    current_data = tailored
    for attempt in range(1, max_semantic_passes + 1):
        logger.info(
            "  [compaction %d/%d]  Requesting LLM to shorten longest bullets…",
            attempt,
            max_semantic_passes,
        )
        current_data = compact_resume_content(current_data)
        quality = evaluate_resume_quality(current_data)
        if not quality.passed:
            logger.info("  Compaction output failed quality gate; refining before compile.")
            current_data = refine_resume_for_quality(current_data, keywords, proof_pack, quality)

        _write_json(current_data, workspace)

        logger.info("  Recompiling with %s", layout.describe())
        _compile_pdf(template_path, output_path, layout)
        pages = _page_count(output_path)
        logger.info("  Page count after compaction: %d", pages)

        if pages == 1:
            logger.info("✅  Pass 3 success — semantic compaction achieved 1 page.")
            return

    logger.warning(
        "⚠️   All passes exhausted. Final PDF has %d page(s). "
        "Consider trimming the master resume or loosening constraints.",
        pages,
    )


# ── Preflight check ───────────────────────────────────────────────────────────

def _check_typst_installed() -> None:
    result = subprocess.run(["typst", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        raise EnvironmentError(
            "The `typst` CLI is not installed or not on PATH.\n"
            "Install it from https://github.com/typst/typst/releases "
            "or via `brew install typst` on macOS."
        )
    logger.info("  typst %s detected.", result.stdout.strip())
