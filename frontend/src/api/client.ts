import type { ResumeSchema, TailorRequest, TailorResponse } from "../types/resume";

const BASE_URL = "/api";

// ── Typed error class ─────────────────────────────────────────────────────────

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Network error — could not reach the server. Is the backend running?");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // response body was not JSON; keep the default message
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * POST /api/tailor
 *
 * Sends the master resume and job description to the FastAPI backend, which
 * runs the full LLM tailoring pipeline and returns structured JSON.
 *
 * This call may take 1–3 minutes.
 */
export async function tailorResume(req: TailorRequest): Promise<TailorResponse> {
  return request<TailorResponse>("/tailor", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * GET /api/health
 *
 * Lightweight liveness check — resolves quickly if the server is up.
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
  return request("/health", { method: "GET" });
}

/**
 * GET /api/master-resume
 *
 * Returns the local master_resume.json pre-loaded from the server.
 * Used to skip the manual file-upload step during local development.
 */
export async function getMasterResume(): Promise<ResumeSchema> {
  return request<ResumeSchema>("/master-resume", { method: "GET" });
}

/**
 * POST /api/download-pdf
 *
 * Sends a tailored ResumeSchema to the backend, which compiles it through
 * the Typst template and returns raw PDF bytes for download.
 */
export async function downloadPdf(resume: ResumeSchema): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/download-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(resume),
    });
  } catch {
    throw new ApiError(0, "Network error — could not reach the server.");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch { /* ignore */ }
    throw new ApiError(response.status, detail);
  }

  return response.blob();
}
