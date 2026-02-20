import type { ReactNode } from "react";

type Variant = "neutral" | "ok" | "warn" | "danger";

export function Badge(props: { variant: Variant; children: ReactNode }) {
  const ringCls =
    props.variant === "ok"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : props.variant === "warn"
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : props.variant === "danger"
          ? "bg-rose-50 text-rose-700 ring-rose-200"
          : "bg-slate-50 text-slate-600 ring-slate-200";

  const dotCls =
    props.variant === "ok"
      ? "bg-emerald-500"
      : props.variant === "warn"
        ? "bg-amber-500"
        : props.variant === "danger"
          ? "bg-rose-500"
          : "bg-slate-400";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${ringCls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotCls}`} />
      {props.children}
    </span>
  );
}
