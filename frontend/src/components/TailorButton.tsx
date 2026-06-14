interface Props {
  onClick: () => void;
  loading: boolean;
  disabled: boolean;
}

function Spinner() {
  return (
    <svg
      className="h-5 w-5 animate-spin text-white"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function TailorButton({ onClick, loading, disabled }: Props) {
  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={onClick}
        disabled={disabled || loading}
        className={[
          "flex w-full max-w-sm items-center justify-center gap-3 rounded-xl px-8 py-4 text-base font-semibold shadow-md transition-all duration-200",
          disabled || loading
            ? "cursor-not-allowed bg-slate-200 text-slate-400 shadow-none"
            : "cursor-pointer bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-lg active:scale-95",
        ].join(" ")}
      >
        {loading ? (
          <>
            <Spinner />
            <span>Tailoring Resume…</span>
          </>
        ) : (
          <>
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
            </svg>
            <span>Generate Tailored Resume</span>
          </>
        )}
      </button>
      {loading && (
        <p className="text-center text-xs text-slate-400 max-w-xs">
          The LLM pipeline is running — this usually takes{" "}
          <span className="font-medium text-slate-500">1–3 minutes</span>.
          Please keep this tab open.
        </p>
      )}
      {!loading && disabled && (
        <p className="text-center text-xs text-slate-400">
          Upload a resume and add a job description to continue.
        </p>
      )}
    </div>
  );
}
