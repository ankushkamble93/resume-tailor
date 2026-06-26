// TypeScript interfaces mirroring the Pydantic models in models.py exactly.
// Keep in sync with any schema changes in the Python backend.

export interface ContactInfo {
  name: string;
  location: string;
  phone: string;
  email: string;
  linkedin?: string;
  github?: string;
}

export interface WorkExperience {
  company: string;
  role: string;
  location: string;
  start_date: string;
  end_date: string;
  bullets: string[];
}

export interface Project {
  name: string;
  role: string;
  status: string;
  bullets: string[];
}

export interface SkillGroup {
  category: string;
  skills: string[];
}

export interface Education {
  degree: string;
  institution: string;
  location: string;
  graduation_date: string;
}

export interface ResumeSchema {
  contact: ContactInfo;
  summary: string;
  skills: SkillGroup[];
  experience: WorkExperience[];
  projects: Project[];
  education: Education[];
}

export interface JDKeywords {
  technical_skills: string[];
  infrastructure_keywords: string[];
  core_competencies: string[];
  job_role_type: "SDET" | "SDE" | "DevOps" | "unknown";
}

// ── API shapes ────────────────────────────────────────────────────────────────

export interface TailorRequest {
  master_resume: ResumeSchema;
  job_description: string;
}

export interface TailorResponse {
  tailored_resume: ResumeSchema;
  keywords: JDKeywords;
}

export interface ApiError {
  detail: string;
}

export interface CoverLetterRequest {
  tailored_resume: ResumeSchema;
  job_description: string;
  keywords: string[];
}

export interface CoverLetterResponse {
  why_this_job: string;
  cover_letter: string;
}
