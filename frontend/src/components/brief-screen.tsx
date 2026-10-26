"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { briefPayload, goals, saveBrief, segments } from "@/lib/brief";
import type { BriefRecord, Segment } from "@/lib/brief";
import { command } from "@/lib/run-api";
import { Badge, Header } from "./ui";

const crew = [["Or", "Orchestrator", "Plans, routes, retries, saves progress", "forest"], ["Sc", "Scout", "Finds and ranks candidate rivals", "lavender"], ["Re", "Researcher", "Products, prices, ingredients, reviews", "turmeric"], ["An", "Analyst", "Normalises data, compares, finds gaps", "rose"], ["Qa", "Reviewer", "Checks sources, maths and claims", "mint"]];

export function BriefScreen() {
  const router = useRouter();
  const [goal, setGoal] = useState(1);
  const [segment, setSegment] = useState<Segment>(segments[0]);
  const [missing, setMissing] = useState(2);
  const [authenticated, setAuthenticated] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<BriefRecord | null>(null);
  const [savedOpen, setSavedOpen] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [livePilot, setLivePilot] = useState<{ run_id: string; provider: string; model: string } | null>(null);
  const runKey = useRef("");
  const request = useRef({ body: "", key: "" });
  const signInEmail = useRef<HTMLInputElement>(null);
  useEffect(() => { let active = true; fetch("/api/session").then(response => response.json()).then(data => { if (active) setAuthenticated(data.authenticated === true); }).catch(() => {}); return () => { active = false; }; }, []);
  useEffect(() => { if (!authenticated) return; let active = true;
    fetch('/api/live-pilot').then(r => r.ok ? r.json() : null).then(value => { if (active && value?.enabled) setLivePilot(value); }).catch(() => {});
    return () => { active = false; }; }, [authenticated]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setAuthBusy(true); setAuthError("");
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const response = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message || "Sign-in could not be confirmed.");
      setAuthenticated(true); setAuthOpen(false); form.reset();
    } catch (cause) { setAuthError(cause instanceof Error ? cause.message : "Sign-in is unavailable."); }
    finally { setAuthBusy(false); }
  }

  async function queueRun() {
    if (!saved) return; setRunBusy(true); setError(""); runKey.current ||= crypto.randomUUID();
    try { const run = await command<{ id: string; version: number }>("/api/runs", { brief_id: saved.id, budget: { max_calls: 40, max_tokens: 0, max_cost_usd: "0" } }, runKey.current);
      await command(`/api/runs/${run.id}/resume`, { expected_run_version: run.version, deadline_seconds: 3600 }, `resume-${runKey.current}`);
      router.push(`/live?run=${run.id}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The run could not be queued."); } finally { setRunBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSaved(null); setSavedOpen(false); runKey.current = "";
    if (!authenticated) { setAuthOpen(true); setError("Sign in to save your brief. Your form is still here."); setTimeout(() => signInEmail.current?.focus(), 0); return; }
    try {
      const payload = briefPayload(event.currentTarget, goal, segment);
      const body = JSON.stringify(payload);
      if (request.current.body !== body) request.current = { body, key: crypto.randomUUID() };
      setBusy(true);
      setSaved(await saveBrief(payload, request.current.key));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Your brief could not be saved."); }
    finally { setBusy(false); }
  }

  return <div className="brief-page"><section className="forest brief-hero"><Header active="/" tagline/>
    <div className="brief-intro container"><div className="brief-copy"><p className="step-pill"><span/>Step 1 of 4 · Tell the crew what to look for</p>
      <h1>Know your rivals<br/>before you<br/><em>price your first bar.</em></h1>
      <p>Scout, research, compare and fact-check competitors, then review a sourced briefing. Nothing gets published or sent.</p>
    </div><div className="soap-stack" aria-hidden="true"><span className="stack-bar bar-rose"/><span className="stack-bar bar-yellow"/><span className="stack-bar bar-lavender">YOU?</span><i className="bubble b1"/><i className="bubble b2"/><i className="bubble b3"/></div></div>
  </section><main id="main" tabIndex={-1} className="container brief-grid">
    <div className="panel brief-card">{livePilot && <section className="save-success"><strong>LIVE research pilot</strong><p>One approved Petite Batch / India run using Tavily and {livePilot.provider}. Model selection is provisional. Spending is bounded by the approved run permit; inspect the saved run for usage.</p><Link className="button primary" href={`/live?run=${livePilot.run_id}`}>Open approved live research</Link></section>}<form onSubmit={submit} aria-busy={busy} onInput={event => { const data = new FormData(event.currentTarget); setMissing(["geography", "customer"].filter(key => !String(data.get(key) || "").trim()).length); }}>
      <div className="field objective-field"><label htmlFor="objective">What do you want to decide?</label><textarea id="objective" name="objective" maxLength={2000} rows={2} placeholder="e.g. How should I price my first four bars, and where can I stand out?"/>
        <div className="chips" aria-label="Research goal">{goals.map((label, i) => <button type="button" className="chip" key={label} aria-pressed={goal === i} onClick={() => setGoal(i)}>{label}</button>)}</div>
      </div>
      <div className="form-grid"><div className="field"><label htmlFor="category">Product category <b>*</b></label><input id="category" name="category" required maxLength={300} defaultValue="Handmade cold-process soap bars"/></div>
        <div className="field"><label htmlFor="geography">Target geography <b>*</b></label><input id="geography" className="highlight-input" name="geography" required maxLength={300} placeholder="e.g. India, online-first"/></div>
        <div className="field"><label htmlFor="customer">Target customer <b>*</b></label><input id="customer" className="highlight-input" name="customer" required maxLength={1000} placeholder="e.g. Urban 25–40, sensitive skin"/></div>
        <div className="field"><label htmlFor="known">Rivals you already know</label><input id="known" name="known" maxLength={6000} placeholder="Names or links, comma-separated"/></div></div>
      <fieldset className="segment-field"><legend>Price segment</legend><div className="segments">{segments.map((label, i) => <button key={label} type="button" className={`segment segment-${i}`} aria-pressed={segment === label} onClick={() => setSegment(label)}><strong>{["?", "₹", "₹₹", "₹₹₹"][i]}</strong><span>{label}</span></button>)}</div></fieldset>
      <details className="own-bar"><summary>Compare your bar (optional)</summary><p className="muted">A weight is needed to calculate a comparable price. Nothing is estimated.</p><div className="form-grid"><div className="field"><label htmlFor="own-price">Your bar price (₹)</label><input id="own-price" name="own_price" type="number" min="0" step="0.01"/></div><div className="field"><label htmlFor="own-weight">Total bar weight (g)</label><input id="own-weight" name="own_weight_g" type="number" min="0.01" step="0.01"/></div></div></details>
      {missing > 0 && <div className="clarification"><span>?</span><p><strong>{missing} highlighted {missing === 1 ? "field is" : "fields are"} empty.</strong> They change who counts as a competitor. Complete them before saving.</p></div>}
      <div className="save-row"><span className="muted">Two human reviews · shortlist, then final report</span><button className="button primary" disabled={busy}>{busy ? "Saving your brief…" : "Save brief →"}</button></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {saved && <div className="save-success" role="status"><strong>Brief saved to your account.</strong><p>Research has not started. Brief reference: <code data-testid="saved-brief-id">{saved.id}</code></p><button type="button" className="text-button" onClick={async () => { try { const response = await fetch(`/api/briefs/${saved.id}`); if (!response.ok) throw new Error(); setSaved(await response.json()); setSavedOpen(true); } catch { setError("Your saved brief could not be reloaded."); } }}>Reload saved brief</button> · <button type="button" className="button primary" disabled={runBusy} onClick={() => void queueRun()}>{runBusy ? "Queuing..." : "Queue recorded research"}</button><p>Recorded mode only: 40-call cap, zero paid spend allowed. A local worker processes the queued run; unmatched recordings stop with a limitation.</p>{savedOpen && <p>Saved geography: {saved.geography} · segment: {saved.preferences.price_segment}</p>}</div>}
    </form>
    <div className="session-panel"><span className="muted" role="status">{authenticated ? "Signed in · saving is available" : "Sign in to save to your account"}</span><button className="text-button" type="button" onClick={async () => { if (authenticated) { await fetch("/api/session", { method: "DELETE" }); setAuthenticated(false); } else setAuthOpen(!authOpen); }}>{authenticated ? "Sign out" : authOpen ? "Close sign-in" : "Sign in"}</button>
      {authOpen && <form className="signin-form" onSubmit={signIn} aria-label="Sign in" aria-busy={authBusy}><div className="field"><label htmlFor="email">Email</label><input ref={signInEmail} id="email" name="email" type="email" autoComplete="username" required maxLength={254}/></div><div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required maxLength={1024}/></div><button className="button primary" disabled={authBusy}>{authBusy ? "Signing in…" : "Sign in to account"}</button>{authError && <p role="alert" className="form-error">{authError}</p>}</form>}
    </div></div>
    <aside className="brief-aside"><section className="panel crew-card"><h2>Meet the crew</h2><p className="muted">Who does what on a research run</p><ul>{crew.map(([initial, name, job, tone]) => <li key={name}><Badge tone={tone}>{initial}</Badge><span><strong>{name}</strong><small>{job}</small></span></li>)}</ul></section>
      <section className="two-stops"><p className="eyebrow">Two stops for you</p><h2>The crew pauses to let you approve the shortlist, then the final report.</h2></section><Link className="history-teaser" href="/history"><span><strong>Your saved runs</strong></span><b>Compare →</b></Link></aside>
  </main></div>;
}
