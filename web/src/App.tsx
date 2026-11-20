import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Ask } from "./pages/Ask";
import { Dashboard } from "./pages/Dashboard";
import { History } from "./pages/History";
import { Queue } from "./pages/Queue";

type Page = "ask" | "queue" | "history" | "dashboard";
const PAGES: Page[] = ["ask", "queue", "history", "dashboard"];

function pageFromHash(): Page {
  const h = window.location.hash.slice(1) as Page;
  return PAGES.includes(h) ? h : "ask";
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [pending, setPending] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const [demo, setDemo] = useState<{ llm_provider: string; ticket_backend: string } | null>(null);
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => h.demo_mode && setDemo(h))
      .catch(() => undefined);
  }, []);

  const refreshPending = useCallback(() => {
    api.list("pending_approval").then((l) => setPending(l.length), () => setPending(null));
  }, []);
  useEffect(refreshPending, [refreshPending]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  const link = (p: Page, label: string, count?: number | null) => (
    <a href={`#${p}`} aria-current={page === p ? "page" : undefined}>
      {label}
      {count != null && count > 0 && <span className="count">{count}</span>}
    </a>
  );

  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <div className="brand"><i aria-hidden="true" />Orbit Helpdesk</div>
        <div className="role">Employee</div>
        {link("ask", "Ask IT or HR")}
        <div className="role">Agents</div>
        {link("queue", "Approval queue", pending)}
        {link("history", "All requests")}
        <div className="role">Managers</div>
        {link("dashboard", "Overview")}
        <footer>Demo with a fictional company. No real employee data.</footer>
      </nav>
      <main>
        {demo && (
          <div className="demo-banner" role="note">
            <strong>Live demo.</strong> A fictional company with synthetic data that resets on restart. To keep it free,
            answers come from a {demo.llm_provider === "stub" ? "simple rule-based stand-in" : demo.llm_provider} instead of
            a language model, and tickets go to a built-in mock system. Please don't enter real personal details.{" "}
            <a href="https://github.com/ZoePetro0510/helpdesk-ai" target="_blank" rel="noreferrer">Code and eval results on GitHub</a>
          </div>
        )}
        {page === "ask" && <Ask onSubmitted={refreshPending} />}
        {page === "queue" && <Queue onChanged={refreshPending} toast={showToast} />}
        {page === "history" && <History />}
        {page === "dashboard" && <Dashboard />}
      </main>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
