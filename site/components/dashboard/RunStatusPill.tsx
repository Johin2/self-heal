type Status = "in_progress" | "succeeded" | "exhausted";

const styles: Record<Status, { label: string; classes: string }> = {
  in_progress: {
    label: "Running",
    classes: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  succeeded: {
    label: "Succeeded",
    classes: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  },
  exhausted: {
    label: "Exhausted",
    classes: "border-red-500/30 bg-red-500/10 text-red-300",
  },
};

export function RunStatusPill({ status }: { status: Status }) {
  const s = styles[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${s.classes}`}
    >
      <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {s.label}
    </span>
  );
}
