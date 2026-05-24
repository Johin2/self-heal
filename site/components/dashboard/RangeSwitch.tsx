import Link from "next/link";

export function RangeSwitch({
  options,
  active,
}: {
  options: string[];
  active: string;
}) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-900 bg-neutral-950/60 p-0.5 text-xs">
      {options.map((o) => (
        <Link
          key={o}
          href={`?range=${o}`}
          className={`rounded-md px-2.5 py-1 transition ${
            o === active
              ? "bg-neutral-800 text-neutral-100"
              : "text-neutral-500 hover:text-neutral-200"
          }`}
        >
          {o}
        </Link>
      ))}
    </div>
  );
}
