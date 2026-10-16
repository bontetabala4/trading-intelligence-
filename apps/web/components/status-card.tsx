import type { SystemStatus } from "../lib/api";

export function StatusCard({ status }: { status: SystemStatus | null }) {
  if (!status) {
    return <section className="card" aria-live="polite">Connexion API indisponible.</section>;
  }

  const mockMode = status.mode === "ANALYSIS_ONLY";
  return (
    <section className="card" aria-live="polite">
      <p className={mockMode ? "badge warning" : "badge"}>{mockMode ? "MODE ANALYSE / MOCK" : status.mode}</p>
      <h2>État système</h2>
      <dl className="metrics">
        <div><dt>Application</dt><dd>{status.application}</dd></div>
        <div><dt>Base de données</dt><dd>{status.database}</dd></div>
        <div><dt>Broker</dt><dd>{status.mt5}</dd></div>
        <div><dt>Données marché</dt><dd>{status.market_data}</dd></div>
      </dl>
      <p className="muted">Aucun ordre réel n’est transmis par cette application.</p>
    </section>
  );
}
