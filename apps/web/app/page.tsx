import Link from "next/link";
import { DecisionCard } from "../components/decision-card";
import { StatusCard } from "../components/status-card";
import { getSystemStatus } from "../lib/api";

export default async function Home() {
  const status = await getSystemStatus().catch(() => null);
  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">ATIP V1</p>
          <h1>Recherche, signaux explicables et paper trading</h1>
          <p>Une aide à la décision : ni conseil financier, ni exécution automatique.</p>
        </div>
        <nav aria-label="Navigation principale">
          <Link href="#analyse">Analyse</Link><Link href="#strategie">Stratégies</Link><Link href="#paper">Paper trading</Link><Link href="#securite">Sécurité</Link>
        </nav>
      </header>
      <div className="grid">
        <StatusCard status={status} />
        <div id="analyse"><DecisionCard /></div>
        <section id="strategie" className="card"><h2>Stratégies</h2><p>Trend Following et Mean Reversion sont actives. EMA200, Breakout, Fibonacci et MTF restent expérimentales tant qu’elles ne sont pas validées hors échantillon.</p></section>
        <section id="paper" className="card"><h2>Paper trading</h2><p>Les résultats de simulation doivent être interprétés avec leurs coûts, périodes et limites. Aucun ordre réel n’est disponible dans V1.</p></section>
        <section id="securite" className="card"><h2>Sécurité</h2><p>Les données mock, le backtest et le paper trading sont distingués des données live. Une décision peut être refusée par la qualité des données ou le risque.</p></section>
      </div>
    </main>
  );
}
