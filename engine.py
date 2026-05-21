"""
engine.py — LLM-powered JD analysis and resume tailoring.

Uses the `instructor` library to enforce structured Pydantic outputs from
claude-3-5-sonnet-20241022 (falls back to gpt-4o if OPENAI_API_KEY is set
and ANTHROPIC_API_KEY is absent).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List

import instructor

from models import JDKeywords, ResumeSchema

logger = logging.getLogger(__name__)


def _make_client() -> tuple[object, str]:
    """Return an instructor-wrapped client and the model name to use."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        import anthropic

        raw = anthropic.Anthropic(api_key=anthropic_key)
        client = instructor.from_anthropic(raw)
        model = "claude-3-5-sonnet-20241022"
        logger.info("  LLM backend: Anthropic / %s", model)
        return client, model

    if openai_key:
        from openai import OpenAI

        raw = OpenAI(api_key=openai_key)
        client = instructor.from_openai(raw)
        model = "gpt-5.5"  # OpenAI's most capable model — professional work tier
        logger.info("  LLM backend: OpenAI / %s", model)
        return client, model

    raise EnvironmentError(
        "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
        "in your environment or a .env file."
    )


def analyze_job_description(jd_path: str) -> List[str]:
    """
    Read a plain-text job description and extract ATS-optimised keywords.

    Returns a flat, deduplicated list of keywords covering technical skills,
    infrastructure tooling, and core competencies mentioned in the JD.
    """
    jd_text = Path(jd_path).read_text(encoding="utf-8").strip()
    if not jd_text:
        raise ValueError(f"Job description at {jd_path!r} is empty.")

    logger.info("  Sending JD to LLM for keyword extraction…")
    client, model = _make_client()

    kwargs: dict = dict(
        messages=[
            {
                "role": "user",
                "content": (
                    "You are an expert technical recruiter and ATS optimization specialist.\n\n"
                    "Analyze the following job description and extract:\n"
                    "1. Technical skills — programming languages, frameworks, libraries.\n"
                    "2. Infrastructure keywords — cloud platforms, databases, CI/CD, DevOps tools.\n"
                    "3. Core competencies — domain skills and behavioural traits the role emphasises.\n\n"
                    "Rules:\n"
                    "- Extract only terms explicitly present or strongly implied in the JD.\n"
                    "- Deduplicate across categories.\n"
                    "- Use exact casing as found in the JD.\n\n"
                    f"Job Description:\n{jd_text}"
                ),
            }
        ],
        response_model=JDKeywords,
    )

    # Anthropic requires max_tokens; OpenAI ignores it gracefully
    if "claude" in model:
        kwargs["max_tokens"] = 1024
        kwargs["model"] = model
        result: JDKeywords = client.messages.create(**kwargs)
    else:
        kwargs["model"] = model
        result = client.chat.completions.create(**kwargs)

    keywords = result.all_keywords
    logger.info("  Extracted %d unique keywords.", len(keywords))
    return keywords


def tailor_resume_data(master_data: ResumeSchema, keywords: List[str]) -> ResumeSchema:
    """
    Feed master resume data + JD keywords to the LLM and receive a tailored
    ResumeSchema back.

    The model selects the top 3-4 most relevant bullets per role/project and
    rewrites them to surface matching keywords while preserving all metrics.
    """
    logger.info("  Sending master data to LLM for tailoring…")
    client, model = _make_client()

    keywords_str = ", ".join(keywords)

    # Strip contact from the LLM payload — restored via code after the call
    master_body = master_data.model_dump()
    del master_body["contact"]
    master_body_json = json.dumps(master_body, indent=2)

    system_msg = (
        "You are an expert resume writer. Your one job is to rewrite resume bullets "
        "so they surface specific target keywords. Returning a bullet that is word-for-word "
        "identical to the input is strictly forbidden — every bullet you output must be "
        "a genuine rewrite with different phrasing."
    )

    user_msg = (
        f"TARGET KEYWORDS: {keywords_str}\n\n"
        "MASTER RESUME BODY (do not invent any fact, tool, or metric not present here):\n"
        f"{master_body_json}\n\n"
        "━━━ SKILLS LOCK (non-negotiable) ━━━\n"
        "Copy the skills array EXACTLY as given — same categories, same order, same items. "
        "Do NOT add, remove, rename, or reorder any skill. Skills are factual and must not "
        "be inferred or expanded from the JD.\n\n"
        "━━━ STEP 1 — BULLET SELECTION ━━━\n"
        "For each experience entry keep the 3–4 bullets that map most naturally to the "
        "target keywords. Drop the rest.\n"
        "For each project keep the 3 most relevant bullets.\n\n"
        "━━━ STEP 2 — BULLET REWRITING (mandatory) ━━━\n"
        "Rewrite every kept bullet. The output text must differ from the input text.\n"
        "Rephrase the action verb, reframe the outcome in terms of the target keywords, "
        "and inject keyword language where the underlying claim supports it.\n\n"
        "Concrete example:\n"
        "  INPUT:   'Analyzed production performance metrics to isolate bottlenecks and "
        "deploy high-priority hotfixes, protecting user retention.'\n"
        "  OUTPUT:  'Queried production data pipelines via SQL to surface anomalous "
        "performance patterns; applied quantitative analysis to isolate root causes and "
        "deploy targeted hotfixes protecting user retention.'\n\n"
        "━━━ STEP 3 — SUMMARY ━━━\n"
        "Write a 2-sentence summary that leads with the skills most relevant to the "
        "target keywords. Do not copy the original summary.\n\n"
        "━━━ RULES ━━━\n"
        "- Preserve every number, %, and duration from the original exactly.\n"
        "- Do not invent tools, platforms, or metrics.\n"
        "- Return a valid ResumeSchema. For the contact block supply a placeholder — "
        "it will be overwritten in code and does not matter."
    )

    messages = [{"role": "user", "content": user_msg}]
    kwargs: dict = dict(response_model=ResumeSchema)

    if "claude" in model:
        kwargs["model"] = model
        kwargs["max_tokens"] = 4096
        kwargs["system"] = system_msg
        kwargs["messages"] = messages
        result: ResumeSchema = client.messages.create(**kwargs)
    else:
        kwargs["model"] = model
        kwargs["messages"] = [{"role": "system", "content": system_msg}] + messages
        result = client.chat.completions.create(**kwargs)

    # Programmatic contact restoration via dict reconstruction — guarantees
    # no hallucinated fields survive Pydantic re-validation
    merged = result.model_dump()
    merged["contact"] = master_data.contact.model_dump()
    result = ResumeSchema.model_validate(merged)

    logger.info("  Tailoring complete.")
    return result


def compact_resume_content(data: ResumeSchema) -> ResumeSchema:
    """
    Pass 3 compaction: ask the LLM to shorten the 2–3 longest bullets
    across all experiences and projects to reclaim vertical space.

    Called only when geometry tightening alone cannot achieve 1 page.
    """
    logger.info("  Requesting semantic compaction from LLM…")
    client, model = _make_client()

    prompt = (
        "The following resume is spilling over 1 typeset page and must be shortened.\n\n"
        "TASK: Find the 2–3 longest bullet points across ALL experience and project sections. "
        "Trim each one by 15–25% by cutting filler phrases, redundant adjectives, and "
        "over-qualified clauses — while keeping the core technical action and outcome intact.\n\n"
        "HARD RULES:\n"
        "- Keep ALL quantitative metrics (numbers, %, durations) exactly as written.\n"
        "- Keep ALL technical keywords (tool names, language names, platform names).\n"
        "- Do NOT merge two bullets into one.\n"
        "- Do NOT delete an entire bullet.\n"
        "- Do NOT touch the contact block — copy it exactly, nulls included.\n"
        "- Do NOT add any new content.\n"
        "- Return the complete, valid ResumeSchema.\n\n"
        f"RESUME DATA:\n{data.model_dump_json(indent=2)}"
    )

    kwargs = dict(
        messages=[{"role": "user", "content": prompt}],
        response_model=ResumeSchema,
    )

    original_contact = data.contact.model_dump()

    if "claude" in model:
        kwargs["max_tokens"] = 4096
        kwargs["model"] = model
        result: ResumeSchema = client.messages.create(**kwargs)
    else:
        kwargs["model"] = model
        result = client.chat.completions.create(**kwargs)

    merged = result.model_dump()
    merged["contact"] = original_contact
    return ResumeSchema.model_validate(merged)
