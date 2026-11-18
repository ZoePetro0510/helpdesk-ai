import { useEffect, useState } from "react";
import { api, CATEGORY_LABEL, type Metrics } from "../api";

const fmt = new Intl.NumberFormat("en-US");

export function Dashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.metrics().then(setM, (err) => setError(err.message));
  }, []);

  return (
    <>
      <div className="eyebrow">Manager view</div>
      <h1>Helpdesk overview</h1>
      <p className="lede">How many requests the agent resolves on its own, what still needs people, and what it costs.</p>
      {error && <div className="error" role="alert">{error}</div>}
      {m && m.total === 0 && <div className="card empty">No requests yet. Send one from “Ask IT or HR”.</div>}
      {m && m.total > 0 && <Content m={m} />}
    </>
  );
}

function Content({ m }: { m: Metrics }) {
  const local = m.cost_usd === 0;
  return (
    <>
      <div className="kpis">
        <Kpi label="Requests" value={fmt.format(m.total)} sub={`${m.by_status.ticket_created} became tickets`} />
        <Kpi
          label="Resolved automatically"
          value={`${Math.round(m.auto_resolve_rate * 100)}%`}
          sub={`${m.by_status.answered} answered with sources`}
        />
        <Kpi
          label="Time saved"
          value={`${(m.minutes_saved / 60).toFixed(1)} h`}
          sub={`Assumes ${m.minutes_per_auto_answer} min per answered question`}
        />
        <Kpi
          label="Waiting for approval"
          value={fmt.format(m.pending)}
          sub={m.pending ? `Oldest: ${formatAge(m.oldest_pending_minutes)}` : "Queue is clear"}
        />
        <Kpi label="Response time" value={`${(m.latency_ms.avg / 1000).toFixed(1)} s`} sub={`p95 ${(m.latency_ms.p95 / 1000).toFixed(1)} s`} />
        <Kpi
          label="Model cost"
          value={local ? "$0" : `$${m.cost_usd.toFixed(2)}`}
          sub={`${fmt.format(m.tokens.input + m.tokens.output)} tokens${local ? " · local model" : ""}`}
        />
      </div>

      <div className="charts">
        <CategoryChart data={m.by_category} />
        <DailyChart data={m.per_day} />
      </div>
      <p className="muted" style={{ fontSize: 12.5, marginTop: 14 }}>Models: {m.models.join(", ")}</p>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card kpi">
      <div className="eyebrow">{label}</div>
      <div className="value">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

function formatAge(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h`;
  return `${Math.round(minutes / 60 / 24)} days`;
}

/* Horizontal stacked bars: answered automatically vs. sent to a person, per category */
function CategoryChart({ data }: { data: Metrics["by_category"] }) {
  const [asTable, setAsTable] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(...data.map((d) => d.auto + d.person), 1);

  return (
    <section className="card" aria-labelledby="cat-title">
      <div className="chart-head">
        <h2 id="cat-title" style={{ margin: 0 }}>Requests by category</h2>
        <div className="row">
          <div className="legend">
            <span><i style={{ background: "var(--series-auto)" }} />Answered automatically</span>
            <span><i style={{ background: "var(--series-person)" }} />Sent to a person</span>
          </div>
          <button className="linkbtn" onClick={() => setAsTable((v) => !v)}>{asTable ? "Show chart" : "Show table"}</button>
        </div>
      </div>
      {asTable ? (
        <table>
          <thead>
            <tr><th>Category</th><th className="num">Automatic</th><th className="num">Person</th><th className="num">Total</th></tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.category} style={{ cursor: "default" }}>
                <td>{CATEGORY_LABEL[d.category] ?? d.category}</td>
                <td className="num">{d.auto}</td>
                <td className="num">{d.person}</td>
                <td className="num">{d.auto + d.person}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="hbars">
          {data.map((d) => {
            const total = d.auto + d.person;
            const label = CATEGORY_LABEL[d.category] ?? d.category;
            return (
              <div
                className="hbar"
                key={d.category}
                tabIndex={0}
                onMouseEnter={() => setHover(d.category)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(d.category)}
                onBlur={() => setHover(null)}
                aria-label={`${label}: ${d.auto} automatic, ${d.person} sent to a person`}
              >
                <span className="label" title={label}>{label}</span>
                <span className="track" style={{ width: `${(total / max) * 100}%` }}>
                  {d.auto > 0 && <span className="seg" style={{ flex: d.auto, background: "var(--series-auto)" }} />}
                  {d.person > 0 && <span className="seg" style={{ flex: d.person, background: "var(--series-person)" }} />}
                </span>
                <span className="total">{total}</span>
                {hover === d.category && (
                  <span className="tip" style={{ left: "auto", right: 0, transform: "none" }}>
                    {label}: {d.auto} automatic · {d.person} to a person
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

/* One series over time: requests per day */
function DailyChart({ data }: { data: Metrics["per_day"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.count), 1);
  const ceiling = Math.ceil(max / 4) * 4; // gridlines at quarters of a round number
  const short = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });

  return (
    <section className="card" aria-labelledby="day-title">
      <div className="chart-head">
        <h2 id="day-title" style={{ margin: 0 }}>Requests per day</h2>
        <span className="muted" style={{ fontSize: 12.5 }}>Last {data.length} days · gridlines every {ceiling / 4}</span>
      </div>
      <div className="cols">
        <div className="plot">
          {data.map((d, i) => (
            <div
              className="col"
              key={d.date}
              tabIndex={0}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              aria-label={`${short(d.date)}: ${d.count} requests`}
            >
              <div className="bar" style={{ height: `${(d.count / ceiling) * 100}%` }} />
              {hover === i && <span className="tip">{short(d.date)}: {d.count} requests</span>}
            </div>
          ))}
        </div>
        <div className="xaxis">
          {data.map((d, i) => (
            <span key={d.date}>{i % 3 === 0 || i === data.length - 1 ? short(d.date) : ""}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
