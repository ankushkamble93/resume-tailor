import { useCallback, useRef, useState } from "react";
import type { ResumeSchema } from "../types/resume";

interface Props {
  onResumeParsed: (resume: ResumeSchema) => void;
  disabled?: boolean;
  autoLoaded?: boolean;
  autoLoadedName?: string;
}

export function ResumeUpload({ onResumeParsed, disabled, autoLoaded, autoLoadedName }: Props) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Show the auto-loaded file as "active" until the user replaces it
  const activeFile = autoLoaded ? (autoLoadedName ?? "master_resume.json") : fileName;
  const isReady = autoLoaded || fileName !== null;

  const handleFile = useCallback(
    (file: File) => {
      if (!file.name.endsWith(".json")) {
        setParseError("Please upload a .json file.");
        setFileName(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const parsed = JSON.parse(e.target?.result as string) as ResumeSchema;
          setFileName(file.name);
          setParseError(null);
          onResumeParsed(parsed);
        } catch {
          setParseError("Could not parse JSON. Check your file format.");
          setFileName(null);
        }
      };
      reader.readAsText(file);
    },
    [onResumeParsed],
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div>
      <label className="block text-sm font-semibold text-slate-700 mb-2">
        Master Resume <span className="font-normal text-slate-400">(JSON file)</span>
      </label>
      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={[
          "relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 transition-colors",
          disabled
            ? "cursor-not-allowed border-slate-200 bg-slate-50"
            : isDragging
              ? "cursor-copy border-indigo-400 bg-indigo-50"
              : isReady
                ? "cursor-pointer border-emerald-400 bg-emerald-50"
                : "cursor-pointer border-slate-300 bg-white hover:border-indigo-400 hover:bg-indigo-50",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={onInputChange}
          disabled={disabled}
        />

        {isReady ? (
          <>
            <svg className="h-8 w-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <p className="text-sm font-medium text-emerald-700">{activeFile}</p>
            {autoLoaded && (
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
                Auto-loaded from server
              </span>
            )}
            <p className="text-xs text-emerald-500">Click to replace</p>
          </>
        ) : (
          <>
            <svg className="h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            <p className="text-sm text-slate-500">
              <span className="font-semibold text-indigo-600">Click to upload</span> or drag & drop
            </p>
            <p className="text-xs text-slate-400">master_resume.json</p>
          </>
        )}
      </div>
      {parseError && (
        <p className="mt-2 text-xs text-red-600">{parseError}</p>
      )}
    </div>
  );
}
