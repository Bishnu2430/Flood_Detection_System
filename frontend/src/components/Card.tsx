import type { ReactNode } from "react";

export function Card(props: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200/70 bg-white/85 shadow-sm backdrop-blur-xl">
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-slate-900">
            {props.title}
          </h2>
          {props.subtitle ? (
            <p className="mt-0.5 text-xs text-slate-400">{props.subtitle}</p>
          ) : null}
        </div>
        {props.right ? <div className="shrink-0">{props.right}</div> : null}
      </div>
      <div className="px-5 py-4">{props.children}</div>
    </div>
  );
}
