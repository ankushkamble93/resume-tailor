import { useState } from "react";
import { downloadPdf, generateCoverLetter, downloadCoverLetterPdf, ApiError } from "../api/client";
import type { TailorResponse, CoverLetterResponse } from "../types/resume";

interface Props {
  result: TailorResponse;
  jobDescription: string;
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
    >
      {copied ? (
        <>
          <svg className="h-3.5 w-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" />
          </svg>
          {label}
        </>
      )}
    </button>
  );
}

function SectionCard({
  title,
  copyText,
  children,
}: {
  title: string;
  copyText: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
          {title}
        </h3>
        <CopyButton text={copyText} label="Copy" />
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function Bullet({ text }: { text: string }) {
  return (
    <li className="flex gap-2 text-sm text-slate-700 leading-relaxed">
      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
      {text}
    </li>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ResultsDisplay({ result, jobDescription }: Props) {
  const { tailored_resume: r, keywords } = result;
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [coverLetter, setCoverLetter] = useState<CoverLetterResponse | null>(null);
  const [clLoading, setClLoading] = useState(false);
  const [clError, setClError] = useState<string | null>(null);
  const [clPdfLoading, setClPdfLoading] = useState(false);
  const [clPdfError, setClPdfError] = useState<string | null>(null);
  const [showWhyThis, setShowWhyThis] = useState(false);
  const [whyThisLoading, setWhyThisLoading] = useState(false);
  const [whyThisError, setWhyThisError] = useState<string | null>(null);

  const allKeywords = [
    ...keywords.technical_skills,
    ...keywords.infrastructure_keywords,
    ...keywords.core_competencies,
  ];

  const safeName = (s: string) => s.replace(/[^a-zA-Z0-9]/g, "_").replace(/_+/g, "_");
  const candidateName = safeName(r.contact.name);
  const companyName = safeName(keywords.company_name || "Company");

  const ensureCoverLetter = async (): Promise<CoverLetterResponse | null> => {
    if (coverLetter) return coverLetter;
    setClLoading(true);
    setClError(null);
    try {
      const cl = await generateCoverLetter({
        tailored_resume: r,
        job_description: jobDescription,
        keywords: allKeywords,
      });
      setCoverLetter(cl);
      return cl;
    } catch (err) {
      setClError(err instanceof ApiError ? err.message : "Cover letter generation failed.");
      return null;
    } finally {
      setClLoading(false);
    }
  };

  const handleDownloadCoverLetterPdf = async () => {
    setClPdfError(null);
    const cl = await ensureCoverLetter();
    if (!cl) return;

    setClPdfLoading(true);
    try {
      const blob = await downloadCoverLetterPdf(r, cl.cover_letter);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${candidateName}_Cover_Letter_${companyName}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setClPdfError(err instanceof ApiError ? err.message : "Cover letter PDF compilation failed.");
    } finally {
      setClPdfLoading(false);
    }
  };

  const handleWhyThisPosition = async () => {
    setWhyThisError(null);
    if (coverLetter) {
      setShowWhyThis((v) => !v);
      return;
    }
    setWhyThisLoading(true);
    const cl = await ensureCoverLetter();
    setWhyThisLoading(false);
    if (cl) setShowWhyThis(true);
    else setWhyThisError("Could not load Why This Position.");
  };

  const handleDownloadJson = () => {
    const blob = new Blob(
      [JSON.stringify(r, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tailored_resume.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPdf = async () => {
    setPdfLoading(true);
    setPdfError(null);
    try {
      const blob = await downloadPdf(r);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${candidateName}_Resume_2026.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setPdfError(err instanceof ApiError ? err.message : "PDF compilation failed.");
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* ── Header card ───────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 space-y-3">
        {/* Title + action buttons row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <span className="text-sm font-semibold text-emerald-800">
              Resume tailored for{" "}
              <span className="font-bold">{keywords.job_role_type}</span> role
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <CopyButton text={JSON.stringify(r, null, 2)} label="Copy JSON" />
            <button
              onClick={handleDownloadJson}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Download JSON
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={pdfLoading}
              className={[
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                pdfLoading
                  ? "cursor-not-allowed bg-slate-200 text-slate-400"
                  : "bg-indigo-600 text-white hover:bg-indigo-700",
              ].join(" ")}
            >
              {pdfLoading ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Compiling…
                </>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m.75 12 3 3m0 0 3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                  </svg>
                  Download PDF
                </>
              )}
            </button>
            <button
              onClick={handleDownloadCoverLetterPdf}
              disabled={clLoading || clPdfLoading}
              className={[
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                clLoading || clPdfLoading
                  ? "cursor-not-allowed bg-slate-200 text-slate-400"
                  : "bg-emerald-600 text-white hover:bg-emerald-700",
              ].join(" ")}
            >
              {clLoading ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating…
                </>
              ) : clPdfLoading ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Compiling…
                </>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                  </svg>
                  Download Cover Letter
                </>
              )}
            </button>
            <button
              onClick={handleWhyThisPosition}
              disabled={whyThisLoading || clLoading}
              className={[
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                whyThisLoading || clLoading
                  ? "cursor-not-allowed bg-slate-200 text-slate-400"
                  : showWhyThis
                  ? "bg-indigo-100 text-indigo-700 border border-indigo-300 hover:bg-indigo-200"
                  : "border border-indigo-200 bg-white text-indigo-600 hover:border-indigo-400 hover:bg-indigo-50",
              ].join(" ")}
            >
              {whyThisLoading || clLoading ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Loading…
                </>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
                  </svg>
                  Why This Position
                </>
              )}
            </button>
          </div>
        </div>

        {/* Why this position — shown only when button has been toggled on */}
        {showWhyThis && coverLetter && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-indigo-500">Why this position</p>
            <p className="text-sm leading-relaxed text-indigo-900">{coverLetter.why_this_job}</p>
          </div>
        )}

        {/* Inline error messages */}
        {(pdfError || clError || clPdfError || whyThisError) && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700 space-y-0.5">
            {pdfError && <p><span className="font-semibold">Resume PDF: </span>{pdfError}</p>}
            {clError && <p><span className="font-semibold">Cover letter: </span>{clError}</p>}
            {clPdfError && <p><span className="font-semibold">Cover letter PDF: </span>{clPdfError}</p>}
            {whyThisError && <p><span className="font-semibold">Why This Position: </span>{whyThisError}</p>}
          </div>
        )}
      </div>

      {/* ── Contact ───────────────────────────────────────────────────────── */}
      <SectionCard
        title="Contact"
        copyText={[r.contact.name, r.contact.email, r.contact.phone, r.contact.location, r.contact.linkedin, r.contact.github].filter(Boolean).join(" | ")}
      >
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 text-sm">
          <p><span className="font-medium text-slate-500">Name:</span> {r.contact.name}</p>
          <p><span className="font-medium text-slate-500">Email:</span> {r.contact.email}</p>
          <p><span className="font-medium text-slate-500">Phone:</span> {r.contact.phone}</p>
          <p><span className="font-medium text-slate-500">Location:</span> {r.contact.location}</p>
          {r.contact.linkedin && <p><span className="font-medium text-slate-500">LinkedIn:</span> {r.contact.linkedin}</p>}
          {r.contact.github && <p><span className="font-medium text-slate-500">GitHub:</span> {r.contact.github}</p>}
        </div>
      </SectionCard>

      {/* ── Summary ───────────────────────────────────────────────────────── */}
      <SectionCard title="Summary" copyText={r.summary}>
        <p className="text-sm leading-relaxed text-slate-700">{r.summary}</p>
      </SectionCard>

      {/* ── Skills ────────────────────────────────────────────────────────── */}
      <SectionCard
        title="Skills"
        copyText={r.skills.map((sg) => `${sg.category}: ${sg.skills.join(", ")}`).join("\n")}
      >
        <div className="space-y-2">
          {r.skills.map((sg) => (
            <div key={sg.category} className="flex flex-wrap gap-x-2 gap-y-1 text-sm">
              <span className="font-semibold text-slate-600 min-w-[7rem]">{sg.category}:</span>
              <span className="text-slate-700">{sg.skills.join(", ")}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Experience ────────────────────────────────────────────────────── */}
      <SectionCard
        title="Experience"
        copyText={r.experience
          .map((e) => `${e.role} @ ${e.company} (${e.start_date} – ${e.end_date})\n${e.bullets.map((b) => `• ${b}`).join("\n")}`)
          .join("\n\n")}
      >
        <div className="space-y-5">
          {r.experience.map((exp, i) => (
            <div key={i}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="font-semibold text-slate-800">{exp.role}</p>
                <p className="text-xs text-slate-400">{exp.start_date} – {exp.end_date}</p>
              </div>
              <p className="text-sm text-slate-500">{exp.company} · {exp.location}</p>
              <ul className="mt-2 space-y-1.5">
                {exp.bullets.map((b, j) => <Bullet key={j} text={b} />)}
              </ul>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Projects ──────────────────────────────────────────────────────── */}
      <SectionCard
        title="Projects"
        copyText={r.projects
          .map((p) => `${p.name} — ${p.role} (${p.status})\n${p.bullets.map((b) => `• ${b}`).join("\n")}`)
          .join("\n\n")}
      >
        <div className="space-y-5">
          {r.projects.map((proj, i) => (
            <div key={i}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <p className="font-semibold text-slate-800">{proj.name}</p>
                <p className="text-xs text-slate-400">{proj.status}</p>
              </div>
              <p className="text-sm text-slate-500">{proj.role}</p>
              <ul className="mt-2 space-y-1.5">
                {proj.bullets.map((b, j) => <Bullet key={j} text={b} />)}
              </ul>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Education ─────────────────────────────────────────────────────── */}
      <SectionCard
        title="Education"
        copyText={r.education.map((e) => `${e.degree} — ${e.institution}, ${e.location} (${e.graduation_date})`).join("\n")}
      >
        <div className="space-y-2">
          {r.education.map((edu, i) => (
            <div key={i}>
              <p className="font-semibold text-slate-800">{edu.degree}</p>
              <p className="text-sm text-slate-500">{edu.institution} · {edu.location} · {edu.graduation_date}</p>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Detected keywords ─────────────────────────────────────────────── */}
      <SectionCard
        title="Detected Keywords"
        copyText={[
          "Technical: " + keywords.technical_skills.join(", "),
          "Infrastructure: " + keywords.infrastructure_keywords.join(", "),
          "Competencies: " + keywords.core_competencies.join(", "),
        ].join("\n")}
      >
        <div className="space-y-2">
          {[
            { label: "Technical", items: keywords.technical_skills },
            { label: "Infrastructure", items: keywords.infrastructure_keywords },
            { label: "Competencies", items: keywords.core_competencies },
          ].map(({ label, items }) => (
            <div key={label} className="flex flex-wrap items-start gap-x-2 gap-y-1">
              <span className="text-xs font-semibold text-slate-500 min-w-[6rem]">{label}</span>
              <div className="flex flex-wrap gap-1">
                {items.map((kw) => (
                  <span key={kw} className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700 border border-indigo-100">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
