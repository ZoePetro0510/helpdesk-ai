import { useEffect, useState } from "react";
import { api, timeAgo, type HelpRequest, type Priority, type Team } from "../api";
import { CategoryTag, Sources, UrgencyTag } from "../components/Badges";

const APPROVER_KEY = "helpdesk.approver";

function loadApprover(): string {
  try {
    return localStorage.getItem(APPROVER_KEY) ?? "";
  } catch {
    return "";
  }
}

export function Queue({ onChanged, toast }: { onChanged: () => void; toast: (msg: string) => void }) {
  const [items, setItems] = useState<HelpRequest[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(keep?: number | null) {
    try {
      const list = await api.list("pending_approval");
      setItems(list);
      setSelected(keep && list.some((r) => r.id === keep) ? keep : (list[0]?.id ?? null));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const current = items?.find((r) => r.id === selected) ?? null;

  return (
    <>
      <div className="eyebrow">Agent view</div>
      <h1>Approval queue</h1>
      <p className="lede">
        Requests the agent didn't answer on its own. Check the draft, edit it if needed, then approve to create the
        ticket or reject it with a reason. Nothing reaches the ticket system without your approval.
      </p>
      {error && <div className="error" role="alert">{error}</div>}
      {items && items.length === 0 && (
        <div className="card empty">
          <h2>The queue is empty</h2>
          Requests that need a person will appear here.
        </div>
      )}
      {items && items.length > 0 && (
        <div className="split">
          <div className="list" role="list">
            {items.map((r) => (
              <button key={r.id} aria-pressed={r.id === selected} onClick={() => setSelected(r.id)}>
                <span className="row" style={{ justifyContent: "space-between" }}>
                  <span className="tag">{r.team}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{timeAgo(r.created_at)}</span>
                </span>
                <span className="title">{r.summary}</span>
                <span className="row">
                  <UrgencyTag urgency={r.urgency} />
                </span>
              </button>
            ))}
          </div>
          {current && (
            <Review
              key={current.id}
              req={current}
              onDone={(msg) => {
                toast(msg);
                onChanged();
                load(null);
              }}
            />
          )}
        </div>
      )}
    </>
  );
}

function Review({ req, onDone }: { req: HelpRequest; onDone: (msg: string) => void }) {
  const draft = req.ticket_draft;
  const [title, setTitle] = useState(draft?.title ?? req.summary);
  const [team, setTeam] = useState<Team>(draft?.team ?? req.team);
  const [priority, setPriority] = useState<Priority>(draft?.priority ?? req.urgency);
  const [approver, setApprover] = useState(loadApprover);
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function rememberApprover() {
    try {
      localStorage.setItem(APPROVER_KEY, approver);
    } catch {
      /* storage unavailable: fine */
    }
  }

  async function approve() {
    setBusy(true);
    setError(null);
    rememberApprover();
    try {
      const r = await api.approve(req.id, { approver, title, team, priority, note: note || undefined });
      onDone(`Ticket ${r.ticket_key} created for the ${r.ticket_draft?.team} team`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    setBusy(true);
    setError(null);
    rememberApprover();
    try {
      await api.reject(req.id, approver, reason);
      onDone(`Request #${req.id} rejected`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const canAct = approver.trim().length >= 2 && !busy;

  return (
    <section className="card stack" aria-label={`Request ${req.id}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Request #{req.id}</h2>
        <div className="row">
          <CategoryTag category={req.category} />
          <UrgencyTag urgency={req.urgency} />
        </div>
      </div>

      <div className="field">
        <span className="eyebrow">What the employee wrote (masked)</span>
        <p className="quote">{req.text_masked}</p>
      </div>

      <div className="field">
        <span className="eyebrow">Why it needs a person</span>
        <span>{req.route_reason}</span>
      </div>

      {req.answer && (
        <div className="field">
          <span className="eyebrow">Suggested answer · check before using</span>
          <p style={{ margin: 0 }}>{req.answer}</p>
          <Sources citations={req.citations} />
        </div>
      )}

      <div className="grid3">
        <div className="field">
          <label htmlFor="t-title">Ticket title</label>
          <input id="t-title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="t-team">Team</label>
          <select id="t-team" value={team} onChange={(e) => setTeam(e.target.value as Team)}>
            <option>IT</option>
            <option>HR</option>
            <option>OPS</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="t-priority">Priority</label>
          <select id="t-priority" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      <div className="grid3" style={{ gridTemplateColumns: "1fr 2fr" }}>
        <div className="field">
          <label htmlFor="t-approver">Your name</label>
          <input id="t-approver" type="text" value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Noa (IT)" />
        </div>
        <div className="field">
          <label htmlFor="t-note">Note for the team (optional)</label>
          <input id="t-note" type="text" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {!rejecting ? (
        <div className="row">
          <button className="btn primary" disabled={!canAct || title.trim().length < 3} onClick={approve}>
            {busy ? "Creating ticket…" : "Approve and create ticket"}
          </button>
          <button className="btn danger" disabled={!canAct} onClick={() => setRejecting(true)}>
            Reject
          </button>
          {approver.trim().length < 2 && <span className="muted">Enter your name to approve or reject.</span>}
        </div>
      ) : (
        <div className="stack">
          <div className="field">
            <label htmlFor="t-reason">Reason for rejecting</label>
            <input id="t-reason" type="text" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Duplicate of HD-104" />
          </div>
          <div className="row">
            <button className="btn danger" disabled={!canAct || reason.trim().length < 3} onClick={reject}>
              {busy ? "Rejecting…" : "Confirm rejection"}
            </button>
            <button className="btn" onClick={() => setRejecting(false)}>Cancel</button>
          </div>
        </div>
      )}
    </section>
  );
}
