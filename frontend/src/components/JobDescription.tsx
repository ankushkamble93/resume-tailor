interface Props {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const PLACEHOLDER = `Paste the full job description here…

Example:
We are looking for a Senior Software Engineer with experience in TypeScript, React,
Node.js, and cloud infrastructure (AWS/GCP). You will design and build scalable
microservices, mentor junior engineers, and collaborate with product teams...`;

export function JobDescription({ value, onChange, disabled }: Props) {
  return (
    <div className="flex flex-col h-full">
      <label className="block text-sm font-semibold text-slate-700 mb-2">
        Job Description{" "}
        <span className="font-normal text-slate-400">(paste or type)</span>
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={PLACEHOLDER}
        disabled={disabled}
        rows={14}
        className={[
          "flex-1 w-full resize-y rounded-xl border px-4 py-3 text-sm leading-relaxed transition-colors outline-none scrollbar-thin",
          "placeholder:text-slate-300",
          disabled
            ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
            : "border-slate-300 bg-white text-slate-800 hover:border-indigo-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100",
        ].join(" ")}
      />
      {value.length > 0 && (
        <p className="mt-1.5 text-right text-xs text-slate-400">
          {value.length.toLocaleString()} chars
        </p>
      )}
    </div>
  );
}
