import { useState, useEffect } from "react";
import { tailorResume, getMasterResume, ApiError } from "./api/client";
import type { ResumeSchema, TailorResponse } from "./types/resume";
import { ResumeUpload } from "./components/ResumeUpload";
import { JobDescription } from "./components/JobDescription";
import { TailorButton } from "./components/TailorButton";
import { ResultsDisplay } from "./components/ResultsDisplay";
import { ErrorAlert } from "./components/ErrorAlert";

type AppState = "idle" | "loading" | "done" | "error";

export default function App() {
  const [masterResume, setMasterResume] = useState<ResumeSchema | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [result, setResult] = useState<TailorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<AppState>("idle");
  const [autoLoaded, setAutoLoaded] = useState(false);

  // Auto-load master_resume.json from the backend on mount (local dev shortcut)
  useEffect(() => {
    getMasterResume()
      .then((resume) => {
        setMasterResume(resume);
        setAutoLoaded(true);
      })
      .catch(() => {
        // Silently ignore — user can still upload manually
      });
  }, []);

  const isLoading = state === "loading";
  const canSubmit = masterResume !== null && jobDescription.trim().length > 20;

  const handleGenerate = async () => {
    if (!masterResume || !jobDescription.trim()) return;

    setState("loading");
    setResult(null);
    setError(null);

    try {
      const response = await tailorResume({
        master_resume: masterResume,
        job_description: jobDescription,
      });
      setResult(response);
      setState("done");
      // Scroll to results after a short delay for the DOM to paint
      setTimeout(() => {
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err) {
      setState("error");
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-4">
          <svg className="h-7 w-7 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
          <div>
            <h1 className="text-lg font-bold leading-tight text-slate-900">Resume Tailor</h1>
            <p className="text-xs text-slate-400">LLM-powered, 1-page guarantee</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Powered by Claude / GPT
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        {/* ── Hero ────────────────────────────────────────────────────────── */}
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Tailor your resume in minutes
          </h2>
          <p className="mt-3 text-base text-slate-500 max-w-xl mx-auto">
            Upload your master resume, paste a job description, and let the AI
            craft a focused, keyword-optimised resume—every time.
          </p>
        </div>

        {/* ── Input grid ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 mb-8">
          <ResumeUpload onResumeParsed={(r) => { setMasterResume(r); setAutoLoaded(false); }} disabled={isLoading} autoLoaded={autoLoaded} autoLoadedName="master_resume.json" />
          <JobDescription value={jobDescription} onChange={setJobDescription} disabled={isLoading} />
        </div>

        {/* ── Error ───────────────────────────────────────────────────────── */}
        {error && (
          <div className="mb-6">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* ── CTA ─────────────────────────────────────────────────────────── */}
        <div className="flex justify-center mb-12">
          <TailorButton
            onClick={handleGenerate}
            loading={isLoading}
            disabled={!canSubmit}
          />
        </div>

        {/* ── Results ─────────────────────────────────────────────────────── */}
        {result && (
          <section id="results">
            <div className="mb-6 flex items-center gap-4">
              <h2 className="text-xl font-bold text-slate-900">Tailored Resume</h2>
              <div className="h-px flex-1 bg-slate-200" />
              <button
                onClick={() => { setResult(null); setState("idle"); }}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
              >
                Start over
              </button>
            </div>
            <ResultsDisplay result={result} jobDescription={jobDescription} />
          </section>
        )}
      </main>

      <footer className="mt-16 border-t border-slate-200 py-8 text-center text-xs text-slate-400">
        Resume Tailor &mdash; local LLM pipeline &middot; data never leaves your machine
      </footer>
    </div>
  );
}
