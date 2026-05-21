"""
Pydantic schemas that mirror the exact shape of data/master_resume.json.

Each field is strongly-typed so instructor can enforce structured LLM outputs
and so the Typst renderer receives a validated, predictable payload.
"""

from __future__ import annotations

from typing import List, Optional

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
