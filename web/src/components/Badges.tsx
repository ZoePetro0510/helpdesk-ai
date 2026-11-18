import type { Citation, Priority, Status } from "../api";
import { CATEGORY_LABEL } from "../api";

const STATUS: Record<Status, { label: string; color: string; icon: "check" | "clock" | "ticket" | "x" }> = {
  answered: { label: "Answered", color: "var(--good)", icon: "check" },
  pending_approval: { label: "Waiting for approval", color: "var(--warning)", icon: "clock" },
  ticket_created: { label: "Ticket created", color: "var(--accent)", icon: "ticket" },
  rejected: { label: "Rejected", color: "var(--critical)", icon: "x" },
};

function Icon({ kind, color }: { kind: string; color: string }) {
  const common = { fill: "none", stroke: color, strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      {kind === "check" && <path d="M3 8.5l3 3 7-7" {...common} />}
      {kind === "clock" && (<><circle cx="8" cy="8" r="6" {...common} /><path d="M8 4.5V8l2.5 1.5" {...common} /></>)}
      {kind === "ticket" && <path d="M2 5h12v2a1.5 1.5 0 000 3v2H2v-2a1.5 1.5 0 000-3z" {...common} />}
      {kind === "x" && <path d="M4 4l8 8M12 4l-8 8" {...common} />}
    </svg>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS[status];
  return (
    <span className="badge">
      <Icon kind={s.icon} color={s.color} />
      {s.label}
    </span>
  );
}

const URGENCY_COLOR: Record<Priority, string> = { low: "var(--muted)", medium: "var(--serious)", high: "var(--critical)" };

export function UrgencyTag({ urgency }: { urgency: Priority }) {
  return (
    <span className="tag" style={{ boxShadow: `inset 3px 0 0 ${URGENCY_COLOR[urgency]}` }}>
      {urgency} urgency
    </span>
  );
}

export function CategoryTag({ category }: { category: string }) {
  return <span className="tag">{CATEGORY_LABEL[category] ?? category}</span>;
}

export function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <ul className="sources" aria-label="Sources">
      {citations.map((c) => (
        <li key={c.n}>
          <span className="n">[{c.n}]</span>
          <span>
            {c.title} › {c.section}
          </span>
        </li>
      ))}
    </ul>
  );
}
