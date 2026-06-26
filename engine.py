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
import re
from pathlib import Path
from typing import Dict, List

import instructor

from models import JDKeywords, ResumeSchema

logger = logging.getLogger(__name__)

GENERIC_PHRASES = [
    "leveraged",
    "utilized",
    "dynamic",
    "cutting-edge",
    "synergized",
    "innovative solutions",
    "results-driven",
    "fast-paced environment",
    "cross-functional teams",
]

INFRA_TEST_TERMS = {
    "automation",
    "framework",
    "ci/cd",
    "jenkins",
    "github actions",
    "pipeline",
    "performance testing",
    "regression",
    "integration testing",
    "rest api",
    "diagnostics",
    "root cause",
}

PRODUCT_COLLAB_TERMS = {
    "product manager",
    "product",
    "stakeholder",
    "roadmap",
    "customer",
    "feature delivery",
    "user retention",
    "collaborated",
    "partnered",
}


class QualityReport:
    """Deterministic quality report for anti-slop guardrails."""

    def __init__(
        self,
        generic_phrase_score: float,
        evidence_density: float,
        infra_test_coverage: bool,
        product_collab_coverage: bool,
        failed_checks: List[str],
    ) -> None:
        self.generic_phrase_score = generic_phrase_score
        self.evidence_density = evidence_density
        self.infra_test_coverage = infra_test_coverage
        self.product_collab_coverage = product_collab_coverage
        self.failed_checks = failed_checks

    @property
    def passed(self) -> bool:
        return not self.failed_checks

    def to_dict(self) -> Dict[str, object]:
        return {
            "generic_phrase_score": round(self.generic_phrase_score, 3),
            "evidence_density": round(self.evidence_density, 3),
            "infra_test_coverage": self.infra_test_coverage,
            "product_collab_coverage": self.product_collab_coverage,
            "failed_checks": self.failed_checks,
            "passed": self.passed,
        }


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


def analyze_job_description(jd_path: str) -> JDKeywords:
    """
    Read a plain-text job description and extract ATS-optimised keywords.

    Returns a structured JDKeywords object so callers can access both the
    flat keyword list (.all_keywords) and the inferred role type (.job_role_type).
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
                    "3. Core competencies — domain skills and behavioural traits the role emphasises.\n"
                    "4. Company name — the name of the hiring company exactly as it appears.\n\n"
                    "Rules:\n"
                    "- Extract only terms explicitly present or strongly implied in the JD.\n"
                    "- Deduplicate across categories.\n"
                    "- Use exact casing as found in the JD.\n"
                    "- If the company name cannot be determined, use 'Company'.\n\n"
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

    logger.info("  Extracted %d unique keywords.", len(result.all_keywords))
    return result


def _extract_bullet_anchors(bullet: str, keywords: List[str]) -> List[str]:
    """
    Extract deterministic evidence tokens from a bullet:
    - metrics (numbers, percentages)
    - tool/platform mentions from keywords
    - technical tokens containing delimiters (e.g. CI/CD, Python/REST)
    """
    anchors: List[str] = []
    lower = bullet.lower()

    # Metrics and quantitative markers
    for metric in re.findall(r"\b\d+(?:\.\d+)?%?\+?\b", bullet):
        if metric not in anchors:
            anchors.append(metric)

    # Explicit technical patterns
    tech_patterns = re.findall(
        r"\b[A-Za-z][A-Za-z0-9]*(?:/[A-Za-z0-9]+)+\b|\b[A-Z]{2,}(?:/[A-Z]{2,})?\b",
        bullet,
    )
    for token in tech_patterns:
        if token not in anchors:
            anchors.append(token)

    # Keywords actually supported by source text
    for kw in keywords:
        if kw.lower() in lower and kw not in anchors:
            anchors.append(kw)

    return anchors


def build_proof_pack(master_data: ResumeSchema, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Build per-entry proof anchors to force specific, source-grounded rewrites.
    """
    proof_pack: Dict[str, List[str]] = {}

    for i, exp in enumerate(master_data.experience, start=1):
        key = f"experience_{i}:{exp.company}"
        anchors: List[str] = []
        for bullet in exp.bullets:
            for anchor in _extract_bullet_anchors(bullet, keywords):
                if anchor not in anchors:
                    anchors.append(anchor)
        proof_pack[key] = anchors[:10]

    for i, proj in enumerate(master_data.projects, start=1):
        key = f"project_{i}:{proj.name}"
        anchors = []
        for bullet in proj.bullets:
            for anchor in _extract_bullet_anchors(bullet, keywords):
                if anchor not in anchors:
                    anchors.append(anchor)
        proof_pack[key] = anchors[:10]

    return proof_pack


def _proof_pack_prompt_block(proof_pack: Dict[str, List[str]]) -> str:
    lines = []
    for entry, anchors in proof_pack.items():
        joined = ", ".join(anchors) if anchors else "(no anchors extracted)"
        lines.append(f"- {entry}: {joined}")
    return "\n".join(lines)


def evaluate_resume_quality(data: ResumeSchema, job_role_type: str | None = None) -> QualityReport:
    """
    Deterministic quality gate to reduce generic AI-style output.
    """
    bullets = []
    for exp in data.experience:
        bullets.extend(exp.bullets)
    for proj in data.projects:
        bullets.extend(proj.bullets)

    joined_text = "\n".join(bullets).lower()
    bullet_count = max(len(bullets), 1)

    generic_hits = 0
    for phrase in GENERIC_PHRASES:
        generic_hits += joined_text.count(phrase)
    generic_phrase_score = generic_hits / bullet_count

    evidence_bullets = 0
    for bullet in bullets:
        has_metric = bool(re.search(r"\b\d+(?:\.\d+)?%?\+?\b", bullet))
        has_tech = bool(
            re.search(
                r"\b[A-Za-z][A-Za-z0-9]*(?:/[A-Za-z0-9]+)+\b|\b(?:API|CI/CD|SQL|REST|OAuth|DAU|MAU)\b",
                bullet,
            )
        )
        if has_metric or has_tech:
            evidence_bullets += 1
    evidence_density = evidence_bullets / bullet_count

    infra_test_coverage = any(term in joined_text for term in INFRA_TEST_TERMS)
    product_collab_coverage = any(term in joined_text for term in PRODUCT_COLLAB_TERMS)

    failed_checks: List[str] = []
    if generic_phrase_score > 0.35:
        failed_checks.append("generic_phrase_score_above_threshold")
    if evidence_density < 0.70:
        failed_checks.append("evidence_density_below_threshold")
    if not infra_test_coverage:
        failed_checks.append("missing_infra_test_signal")
    if not product_collab_coverage:
        failed_checks.append("missing_product_collaboration_signal")

    return QualityReport(
        generic_phrase_score=generic_phrase_score,
        evidence_density=evidence_density,
        infra_test_coverage=infra_test_coverage,
        product_collab_coverage=product_collab_coverage,
        failed_checks=failed_checks,
    )


def tailor_resume_data(
    master_data: ResumeSchema,
    keywords: List[str],
    proof_pack: Dict[str, List[str]] | None = None,
    job_role_type: str | None = None,
) -> ResumeSchema:
    """
    Feed master resume data + JD keywords to the LLM and receive a tailored
    ResumeSchema back.

    The model selects the top 3-4 most relevant bullets per role/project and
    rewrites them to surface matching keywords while preserving all metrics.
    """
    logger.info("  Sending master data to LLM for tailoring…")
    client, model = _make_client()

    keywords_str = ", ".join(keywords)
    proof_pack = proof_pack or build_proof_pack(master_data, keywords)
    proof_pack_block = _proof_pack_prompt_block(proof_pack)

    # Strip contact from the LLM payload — restored via code after the call
    master_body = master_data.model_dump()
    del master_body["contact"]
    master_body_json = json.dumps(master_body, indent=2)

    system_msg = (
        "You are an elite technical recruiter and resume strategist. "
        "Write in a concrete, evidence-first style that sounds human and specific. "
        "Avoid generic filler, AI-cadence repetition, and vague claims."
    )

    user_msg = (
        f"TARGET KEYWORDS: {keywords_str}\n\n"
        "TARGET ROLE BLEND:\n"
        "- Primary: test/infrastructure framework ownership and technical depth.\n"
        "- Secondary: product engineering execution and collaboration with PM/stakeholders.\n\n"
        "MASTER RESUME BODY (do not invent any fact, tool, or metric not present here):\n"
        f"{master_body_json}\n\n"
        "PROOF-PACK ANCHORS (must preserve these concrete anchors when relevant to each entry):\n"
        f"{proof_pack_block}\n\n"
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
        "Every bullet should include at least one concrete signal from source facts: "
        "a metric, explicit tool/platform, API/integration detail, system boundary, "
        "or failure/optimization context.\n\n"
        "Sentence variation rule: do not start multiple bullets in a row with the same "
        "verb pattern (e.g., avoid repetitive 'Built...', 'Built...', 'Built...').\n\n"
        "Avoid these generic phrases unless literally necessary: leveraged, utilized, "
        "dynamic, cutting-edge, synergized, innovative solutions.\n\n"
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
        "- Keep writing direct and specific; remove abstract filler.\n"
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


def refine_resume_for_quality(
    tailored_data: ResumeSchema,
    keywords: List[str],
    proof_pack: Dict[str, List[str]],
    quality: QualityReport,
    job_role_type: str | None = None,
) -> ResumeSchema:
    """
    One targeted refinement pass when deterministic quality checks fail.
    """
    logger.info("  Running targeted anti-slop refinement pass…")
    client, model = _make_client()

    failure_list = ", ".join(quality.failed_checks) if quality.failed_checks else "none"
    prompt = (
        "You will refine a tailored resume that failed quality checks for generic language.\n\n"
        f"FAILED CHECKS: {failure_list}\n"
        f"TARGET KEYWORDS: {', '.join(keywords)}\n\n"
        "PROOF-PACK ANCHORS:\n"
        f"{_proof_pack_prompt_block(proof_pack)}\n\n"
        "TASK:\n"
        "- Rewrite only the minimum number of bullets needed to pass checks.\n"
        "- Increase concrete evidence density (metrics, tools, APIs, system details).\n"
        "- Preserve role blend: infra/test ownership + product collaboration signal.\n"
        "- Remove generic filler and repetitive AI phrasing.\n\n"
        "HARD RULES:\n"
        "- Keep all factual claims grounded in existing content.\n"
        "- Preserve all numbers, percentages, and durations.\n"
        "- Do not add new tools or achievements.\n"
        "- Return complete valid ResumeSchema.\n\n"
        f"CURRENT RESUME:\n{tailored_data.model_dump_json(indent=2)}"
    )

    kwargs: dict = dict(
        messages=[{"role": "user", "content": prompt}],
        response_model=ResumeSchema,
    )

    original_contact = tailored_data.contact.model_dump()

    if "claude" in model:
        kwargs["max_tokens"] = 4096
        kwargs["model"] = model
        result: ResumeSchema = client.messages.create(**kwargs)
    else:
        kwargs["model"] = model
        result = client.chat.completions.create(**kwargs)

    merged = result.model_dump()
    merged["contact"] = original_contact
    refined = ResumeSchema.model_validate(merged)
    logger.info("  Quality refinement complete.")
    return refined


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


def generate_why_this_job(
    tailored_resume: ResumeSchema,
    job_description: str,
    keywords: List[str],
) -> str:
    """
    Generate a 2-3 sentence "why this job" pitch for the candidate.

    Deliberately lean: no cover letter, no formatting — just the targeted blurb.
    Called as part of the main tailor pipeline so the result is immediately
    available in the UI without a separate button-triggered LLM call.
    The prompt enforces the full humanizer ruleset so output sounds like a
    real person, not a language model.
    """
    logger.info("  Generating why_this_job blurb…")
    client, model = _make_client()

    contact = tailored_resume.contact
    experience_summary = "\n".join(
        f"- {e.role} at {e.company} ({e.start_date}–{e.end_date})"
        for e in tailored_resume.experience
    )
    projects_summary = "\n".join(
        f"- {p.name}: {p.bullets[0] if p.bullets else ''}"
        for p in tailored_resume.projects
    )
    keywords_str = ", ".join(keywords[:15])

    prompt = f"""You are writing a 2-3 sentence personal blurb for {contact.name} explaining \
why this specific job appeals to them. Write in first person.

Candidate experience:
{experience_summary}

Candidate projects:
{projects_summary}

Job description (excerpt):
{job_description[:1500]}

Relevant JD keywords: {keywords_str}

─── HARD RULES — violating any of these makes the output unusable ───

BANNED WORDS AND PHRASES (do not use any of these):
- AI vocabulary: leverage, utilize, showcase, highlight, align with, delve, tapestry,
  landscape (abstract), pivotal, testament, fostering, garner, vibrant, intricate,
  underscore, cutting-edge, synergize, dynamic, innovative solutions, crucial, key (adj),
  valuable, enhance, emphasizing, enduring, interplay, additionally, groundbreaking,
  renowned, breathtaking, seamless
- Copula substitutes: serves as, stands as, boasts, features (verb), marks a, represents a
- Filler openers: "I am excited to apply", "I look forward to", "I would love to",
  "I am passionate about", "thrilled", "honored"

BANNED CONSTRUCTIONS:
- No em dashes (—). Use commas or periods instead.
- No "not only...but also..." or "it's not just...it's..." constructions.
- No rule of three: do not list three adjectives or three noun phrases in a row.
- No present-participle add-ons: avoid ending sentences with "ensuring...",
  "highlighting...", "reflecting...", "contributing to...", "showcasing...".
- No vague attributions: no "experts believe", "industry research shows".
- No generic upbeat conclusions: no "exciting opportunity", "bright future", "step in the right direction".
- No boldface, no bullet points, no headers.

STYLE REQUIREMENTS:
- Vary sentence length. Mix one short punchy sentence with a longer one.
- Be specific: name the company, name the tech, name something concrete from the JD.
- Use plain copulas: write "is", "are", "has" instead of "serves as" or "stands as".
- Sound like a person who genuinely thought about this role, not a form letter.
- Use "I" naturally. First person is honest, not unprofessional.
- 2-3 sentences maximum. No more.

Return only the blurb — no labels, no JSON, no commentary."""

    if "claude" in model:
        import anthropic as _anthropic
        raw_client = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        resp = raw_client.messages.create(
            model=model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    else:
        from openai import OpenAI as _OpenAI
        raw_client = _OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = raw_client.chat.completions.create(
            model=model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()


def generate_cover_letter(
    tailored_resume: ResumeSchema,
    job_description: str,
    keywords: List[str],
) -> Dict[str, str]:
    """
    Generate a "why this job" blurb and a full cover letter.

    Returns a dict with:
      - why_this_job: 2-3 sentence targeted pitch (used inline in the UI)
      - cover_letter: full 3-4 paragraph letter ready to copy/download

    The prompt embeds humanizer anti-patterns so the output sounds like
    a real person wrote it, not a language model.
    """
    logger.info("  Generating cover letter via LLM…")
    client, model = _make_client()

    contact = tailored_resume.contact
    skills_flat = ", ".join(
        skill
        for sg in tailored_resume.skills
        for skill in sg.skills
    )
    experience_summary = "\n".join(
        f"- {e.role} at {e.company} ({e.start_date}–{e.end_date})"
        for e in tailored_resume.experience
    )
    projects_summary = "\n".join(
        f"- {p.name}: {p.bullets[0] if p.bullets else ''}"
        for p in tailored_resume.projects
    )
    keywords_str = ", ".join(keywords[:20])

    prompt = f"""You are writing a cover letter for {contact.name}.

Candidate background:
{experience_summary}

Projects:
{projects_summary}

Key skills: {skills_flat}

Job description (excerpt to match against):
{job_description[:2000]}

Relevant JD keywords: {keywords_str}

---

YOUR TASK: Write two things.

1. WHY_THIS_JOB — 2-3 sentences max. Why does this specific role/company appeal to this candidate?
   Be specific to the JD. No generic "I am excited to apply" opener.

2. COVER_LETTER — A full cover letter, 3-4 short paragraphs. First-person. Professional but not stiff.
   Opening paragraph: hook with something specific about this company/role, not a cliché opener.
   Middle paragraphs: 1-2 concrete things from the candidate's background that map directly to this role.
   Closing: what they'd bring, brief ask for the interview. Skip the "thank you for your time" filler.

HARD RULES — violating any of these will make the output unusable:
- NO em dashes (—). Use commas or periods instead.
- NO AI vocabulary: do not use "leverage", "utilize", "showcase", "highlight", "align with",
  "delve", "tapestry", "landscape", "pivotal", "testament", "fostering", "garner", "vibrant",
  "intricate", "underscore", "cutting-edge", "synergize", "dynamic", "innovative solutions".
- NO "not only...but also" constructions.
- NO rule of three: don't list three adjectives or three noun phrases in a row.
- NO vague attributions like "experts believe" or "industry research shows".
- NO generic positive conclusions ("exciting opportunity", "I look forward to growing").
- NO present-participle add-ons: avoid ending sentences with "ensuring...", "highlighting...",
  "reflecting...", "contributing to...".
- Write in first person ("I built", "I shipped", not "the candidate built").
- Use plain copulas: write "is", "are", "has" instead of "serves as", "stands as", "boasts".
- Vary sentence length. Mix short sentences with longer ones.
- Be specific: name the company, name the tech, name the outcome. Vague claims get cut.
- Sound like a person who actually wants this job, not a form letter.

Return your response in this exact JSON format:
{{
  "why_this_job": "...",
  "cover_letter": "..."
}}

Do not add any commentary outside the JSON."""

    if "claude" in model:
        import anthropic as _anthropic
        raw_client = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        resp = raw_client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
    else:
        from openai import OpenAI as _OpenAI
        raw_client = _OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = raw_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()

    import json as _json
    parsed = _json.loads(text)
    why = parsed.get("why_this_job", "").strip()
    letter = parsed.get("cover_letter", "").strip()
    logger.info("  Cover letter generated (%d chars).", len(letter))
    return {"why_this_job": why, "cover_letter": letter}


def collect_diagnostics(
    master_data: ResumeSchema,
    keywords: List[str],
    tailored_data: ResumeSchema,
    proof_pack: Dict[str, List[str]] | None = None,
) -> Dict[str, object]:
    """
    Build lightweight diagnostics output for CLI visibility.
    """
    proof_pack = proof_pack or build_proof_pack(master_data, keywords)
    quality = evaluate_resume_quality(tailored_data)
    return {
        "keywords": keywords,
        "proof_pack": proof_pack,
        "quality": quality.to_dict(),
    }
