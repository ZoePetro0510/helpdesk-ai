import { useEffect, useState } from "react";
import { api, timeAgo, type AuditEvent, type HelpRequest, type Status } from "../api";
import { CategoryTag, Sources, StatusBadge, UrgencyTag } from "../components/Badges";

const FILTERS: { value: Status | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "answered", label: "Answered" },
  { value: "pending_approval", label: "Waiting" },
  { value: "ticket_created", label: "Tickets" },
  { value: "rejected", label: "Rejected" },
];

export function History() {
  const [filter, setFilter] = useState<Status | "">("");
  const [items, setItems] = useState<HelpRequest[] | null>(null);
  const [open, setOpen] = useState<HelpRequest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setItems(null);
    api.list(filter || undefined).then(setItems, (err) => setError(err.message));
  }, [filter]);

  return (
    <>
      <div className="eyebrow">Agent view</div>
      <h1>All requests</h1>
      <p className="lede">Every request with the agent's decision. Open one to see its full audit trail.</p>

      <div className="row" style={{ marginBottom: 14 }} role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className="chip"
            aria-pressed={filter === f.value}
            style={filter === f.value ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="error" role="alert">{error}</div>}
      {items && items.length === 0 && <div className="card empty">No requests here yet.</div>}
      {items && items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col" className="num">#</th>
                <th scope="col">Received</th>
                <th scope="col">Request</th>
                <th scope="col">Category</th>
                <th scope="col">Status</th>
                <th scope="col">Ticket</th>
                <th scope="col" className="num">Time</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} onClick={() => setOpen(r)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(r)}>
                  <td className="num mono">{r.id}</td>
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>{timeAgo(r.created_at)} · {r.channel}</td>
                  <td style={{ minWidth: 220 }}>{r.summary}</td>
                  <td><CategoryTag category={r.category} /></td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="mono">{r.ticket_key ?? "—"}</td>
                  <td className="num mono">{(r.latency_ms / 1000).toFixed(1)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && <Drawer req={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function Drawer({ req, onClose }: { req: HelpRequest; onClose: () => void }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    api.audit(req.id).then(setEvents, () => setEvents([]));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [req.id, onClose]);

  return (
    <>
      <div className="drawer-bg" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Request ${req.id}`}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Request #{req.id}</h2>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
        <div className="row">
          <StatusBadge status={req.status} />
          <CategoryTag category={req.category} />
          <UrgencyTag urgency={req.urgency} />
        </div>
        <p className="quote">{req.text_masked}</p>
        {req.answer && (
          <div>
            <span className="eyebrow">{req.status === "answered" ? "Answer sent" : "Suggested answer"}</span>
            <p style={{ margin: "6px 0 0" }}>{req.answer}</p>
            <Sources citations={req.citations} />
          </div>
        )}
        <div>
          <span className="eyebrow">Decision</span>
          <p style={{ margin: "6px 0 0" }}>{req.route_reason}</p>
          {req.decided_by && (
            <p className="muted" style={{ margin: "4px 0 0" }}>
              {req.status === "rejected" ? "Rejected" : "Approved"} by {req.decided_by}
              {req.ticket_key && ` · ${req.ticket_key}`}
              {req.decision_note && ` · “${req.decision_note}”`}
            </p>
          )}
        </div>
        <div className="meta" style={{ marginTop: 0 }}>
          <span>{req.model}</span>
          <span>{req.input_tokens} in / {req.output_tokens} out tokens</span>
          <span>retrieval {req.retrieval_score.toFixed(2)}</span>
          <span>{req.latency_ms} ms</span>
        </div>
        <div>
          <span className="eyebrow">Audit trail</span>
          {!events && <p className="muted">Loading…</p>}
          {events && (
            <ol className="timeline" style={{ marginTop: 10 }}>
              {events.map((e, i) => (
                <li key={i}>
                  <span />
                  <div>
                    <strong>{e.step}</strong> <span className="muted">{new Date(e.at).toLocaleTimeString()}</span>
                    <pre>{JSON.stringify(e.detail)}</pre>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </aside>
    </>
  );
}
