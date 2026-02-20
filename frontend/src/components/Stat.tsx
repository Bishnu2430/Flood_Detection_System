type Tone = "good" | "warn" | "bad" | "neutral";

export function Stat(props: {
  label: string;
  value: string;
  tone: Tone;
  detail?: string;
}) {
  const toneCls =
    props.tone === "good"
      ? "text-emerald-600"
      : props.tone === "warn"
        ? "text-amber-600"
        : props.tone === "bad"
          ? "text-rose-600"
          : "text-slate-800";

  return (
    <div className="rounded-xl bg-slate-50/90 px-4 py-3 ring-1 ring-slate-200/80">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
        {props.label}
      </div>
      <div className={`mt-1.5 text-xl font-semibold leading-none ${toneCls}`}>
        {props.value}
      </div>
      {props.detail ? (
        <div
          className="mt-1.5 truncate text-xs text-slate-400"
          title={props.detail}
        >
          {props.detail}
        </div>
      ) : null}
    </div>
  );
}
