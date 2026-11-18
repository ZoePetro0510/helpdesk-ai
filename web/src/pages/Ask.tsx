import { useState } from "react";
import { api, type HelpRequest } from "../api";
import { CategoryTag, Sources, StatusBadge, UrgencyTag } from "../components/Badges";

const EXAMPLES = [
  "How many vacation days can I carry over to next year?",
  "How do I connect to the VPN from home?",
  "My laptop screen cracked this morning and half of it is black.",
  "I clicked a link in a suspicious email and typed my password.",
];

export function Ask({ onSubmitted }: { onSubmitted: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HelpRequest | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (text.trim().length < 3) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.submit(text.trim()));
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="eyebrow">Employee view</div>
      <h1>Ask IT or HR</h1>
      <p className="lede">
        Describe what you need. Common questions get an answer right away, with the policy it comes from. Anything that
        needs a person is sent to the right team.
      </p>

      <div className="stack" style={{ maxWidth: 760 }}>
        <form className="card stack" onSubmit={submit}>
          <div className="field">
            <label htmlFor="ask-text">Your request</label>
            <textarea
              id="ask-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="For example: I changed banks. How do I update the account for my salary?"
              maxLength={4000}
            />
            <span className="hint">Personal details such as phone numbers or emails are masked before anything is stored.</span>
          </div>
          <div className="row">
            {EXAMPLES.map((ex) => (
              <button type="button" className="chip" key={ex} onClick={() => setText(ex)}>
                {ex.length > 46 ? ex.slice(0, 44) + "…" : ex}
              </button>
            ))}
          </div>
          <div className="row">
            <button className="btn primary" type="submit" disabled={busy || text.trim().length < 3}>
              {busy ? "Sending…" : "Send request"}
            </button>
          </div>
        </form>

        {error && <div className="error" role="alert">{error}</div>}

        {result && (
          <section className="card" aria-live="polite">
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
              <StatusBadge status={result.status} />
              <div className="row">
                <CategoryTag category={result.category} />
                <UrgencyTag urgency={result.urgency} />
              </div>
            </div>
            {result.status === "answered" ? (
              <>
                <p className="answer">{result.answer}</p>
                <Sources citations={result.citations} />
              </>
            ) : (
              <>
                <p className="answer">
                  Thanks. Your request was sent to the <strong>{result.team}</strong> team, and someone will follow up.
                </p>
                <p className="muted" style={{ margin: "8px 0 0" }}>{result.route_reason}</p>
              </>
            )}
            <div className="meta">
              <span>Request #{result.id}</span>
              <span>{(result.latency_ms / 1000).toFixed(1)} s</span>
              <span>{result.input_tokens + result.output_tokens} tokens · {result.model}</span>
              {result.pii_found.length > 0 && <span>Masked: {result.pii_found.join(", ")}</span>}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
