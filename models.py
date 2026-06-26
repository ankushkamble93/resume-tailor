"""
Pydantic schemas that mirror the exact shape of data/master_resume.json.

Each field is strongly-typed so instructor can enforce structured LLM outputs
and so the Typst renderer receives a validated, predictable payload.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, field_validator


class ContactInfo(BaseModel):
    name: str
    location: str
    phone: str
    email: str
    linkedin: Optional[str] = None
    github: Optional[str] = None


class WorkExperience(BaseModel):
    company: str
    role: str
    location: str
    start_date: str
    end_date: str
    bullets: List[str]

    @field_validator("bullets")
    @classmethod
    def at_least_one_bullet(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("A work experience entry must have at least one bullet.")
        return v


class Project(BaseModel):
    name: str
    role: str
    status: str  # "Present" or a completion date string
    bullets: List[str]
    tech: Optional[str] = None          # comma-separated tech stack string
    live_url: Optional[str] = None      # deployed URL for the project
    github_url: Optional[str] = None    # source repository URL

    @field_validator("bullets")
    @classmethod
    def at_least_one_bullet(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("A project entry must have at least one bullet.")
        return v


class SkillGroup(BaseModel):
    category: str
    skills: List[str]


class Education(BaseModel):
    degree: str
    institution: str
    location: str
    graduation_date: str


class ResumeSchema(BaseModel):
    contact: ContactInfo
    summary: str
    skills: List[SkillGroup]
    experience: List[WorkExperience]
    projects: List[Project]
    education: List[Education]


# ── Intermediate schemas used by the LLM engine ────────────────────────────

class JDKeywords(BaseModel):
    """Structured result of job-description analysis."""

    technical_skills: List[str]
    """Programming languages, frameworks, and libraries explicitly mentioned."""

    infrastructure_keywords: List[str]
    """Cloud platforms, databases, CI/CD tools, infrastructure primitives."""

    core_competencies: List[str]
    """Behavioural or domain competencies the role emphasises (e.g. 'system design')."""

    job_role_type: Literal["SDET", "SDE", "DevOps", "unknown"] = "unknown"
    """Inferred primary role category for this job description."""

    @property
    def all_keywords(self) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for kw in self.technical_skills + self.infrastructure_keywords + self.core_competencies:
            lower = kw.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(kw)
        return result


# ── Cover letter length policy (1-page PDF guarantee) ─────────────────────

COVER_LETTER_MAX_PARAGRAPHS = 3
COVER_LETTER_MAX_WORDS_TOTAL = 300
COVER_LETTER_MAX_WORDS_PER_PARAGRAPH = 100
COVER_LETTER_MAX_SENTENCES_PER_PARAGRAPH = 4


def _count_words(text: str) -> int:
    return len(text.split())


class CoverLetter(BaseModel):
    """Structured cover letter output from the LLM."""

    greeting: str = "Dear Hiring Manager,"
    """Opening salutation."""

    paragraphs: List[str]
    """Exactly 3 body paragraphs — sized to fit one printed page."""

    closing: str = "Sincerely,"
    """Valediction before the signature."""

    @field_validator("paragraphs")
    @classmethod
    def enforce_paragraph_count(cls, v: List[str]) -> List[str]:
        if len(v) < 2:
            raise ValueError("Cover letter must have at least 2 body paragraphs.")
        if len(v) > COVER_LETTER_MAX_PARAGRAPHS:
            raise ValueError(
                f"Cover letter must have at most {COVER_LETTER_MAX_PARAGRAPHS} paragraphs."
            )
        return v

    def word_counts(self) -> List[int]:
        return [_count_words(p) for p in self.paragraphs]

    def total_words(self) -> int:
        return sum(self.word_counts())

    def exceeds_length_policy(self) -> bool:
        if len(self.paragraphs) > COVER_LETTER_MAX_PARAGRAPHS:
            return True
        if self.total_words() > COVER_LETTER_MAX_WORDS_TOTAL:
            return True
        return any(w > COVER_LETTER_MAX_WORDS_PER_PARAGRAPH for w in self.word_counts())


class WhyPosition(BaseModel):
    """1–3 sentence answer to 'Why are you interested in this position?'"""

    sentence: str
    """Plain text, 1–3 sentences maximum. No AI-sounding openers."""
