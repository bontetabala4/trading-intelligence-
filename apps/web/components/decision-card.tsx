"use client";

import { FormEvent, useState } from "react";
import type { Decision } from "../lib/api";
import { getDecision } from "../lib/api";

export function DecisionCard() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setDecision(await getDecision(symbol.trim().toUpperCase()));
    } catch (caught) {
      setDecision(null);
      setError(caught instanceof Error ? caught.message : "Erreur inconnue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card" aria-labelledby="decision-heading">
      <h2 id="decision-heading">Analyse de marché</h2>
      <form onSubmit={submit} className="form-row">
        <label htmlFor="symbol">Instrument</label>
        <input id="symbol" value={symbol} onChange={(event) => setSymbol(event.target.value)} required pattern="[A-Za-z0-9._-]+" />
        <button disabled={loading}>{loading ? "Analyse…" : "Analyser"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {decision && (
        <div className="decision" aria-live="polite">
          <p className={`badge ${decision.direction === "NO_TRADE" ? "warning" : ""}`}>{decision.direction}</p>
          <p><strong>Stratégie :</strong> {decision.strategy}</p>
          <p><strong>Régime :</strong> {decision.market_regime}</p>
          <p><strong>Qualité :</strong> {decision.data_quality_status}</p>
          <ul>{decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
