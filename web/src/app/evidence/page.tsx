import Link from "next/link";
import { api } from "@/lib/api";
import { clientFrom, withClient, type SearchParams } from "@/lib/client";
import { formatEur } from "@/lib/format";
import BacktestBars from "@/components/BacktestBars";
import VarianceBridge from "@/components/VarianceBridge";
import MonteCarloChart from "@/components/MonteCarloChart";
import Disclaimers from "@/components/Disclaimers";
import VintageScorecard from "@/components/VintageScorecard";
import styles from "./evidence.module.css";

export const dynamic = "force-dynamic";

/** The simulation samples model assumptions, not business drivers, so its
 *  variable names are the model's. Translated here rather than shown raw. */
const SENSITIVITY_LABELS: Record<string, string> = {
  working_capital_pct: "Working capital, % of sales",
  operating_profit_target: "Operating profit within guidance",
  capex: "Capital expenditure",
  growth: "Revenue growth",
  ebitda_margin_pct: "EBITDA margin",
};

export default async function ForecastRiskPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const client = clientFrom(await searchParams);
  const [backtest, monteCarlo, summary, variance, vintages] = await Promise.all([
    api.backtest(client),
    api.monteCarlo(client),
    api.client(client),
    api.variance("free_cash_flow", client),
    api.backtestVintages(client),
  ]);

  return (
    <div className={styles.page}>
      <div className={`label ${styles.eyebrow}`}>
        Evidence · {summary.short_label} · {summary.fiscal_year}
      </div>
      <h1 className={styles.heading}>How confident should we be in the forecast?</h1>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>
          {backtest ? "Backtest: better model, not accurate model" : "No backtest"}
        </h2>
        {backtest ? (
          <>
            <p className={styles.sectionIntro}>
              Across the two vintages this data supports, the driver-based forecast landed
              closer than a naive extrapolation on all six metric-year pairs. That is a
              statement about a weak baseline, not about accuracy: both methods undershot in
              both years, and the FY2024 operating-profit forecast was wrong by 63%. Beating a
              naive baseline is not the same claim as being reliable.
            </p>
            <div className={styles.backtestLayout}>
              <BacktestBars backtest={backtest} />
              <table className={styles.actualsTable}>
                <thead>
                  <tr>
                    <th></th>
                    <th className={styles.num}>Naive</th>
                    <th className={styles.num}>Driver-based</th>
                    <th className={styles.num}>Actual</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["Revenue", "revenue"],
                      ["Operating profit", "operating_profit"],
                      ["Free cash flow", "free_cash_flow"],
                    ] as const
                  ).map(([label, key]) => (
                    <tr key={key}>
                      <td>{label}</td>
                      <td className={`mono ${styles.num}`}>{formatEur(backtest.naive[key])}</td>
                      <td className={`mono ${styles.num}`}>{formatEur(backtest.driver_based[key])}</td>
                      <td className={`mono ${styles.num}`}>{formatEur(backtest.actual[key])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className={styles.vintageEmpty}>
            <p>
              <strong>This client&rsquo;s data is synthetic, so there is nothing to backtest
              against.</strong>{" "}
              A forecast error measured against invented actuals would look like evidence and be
              none of it. The simulation below still shows the range the plan could land in —
              but that range is constructed from stated assumptions, not from anything that
              happened.
            </p>
          </div>
        )}
      </section>

      {variance && (
        <section className={styles.section}>
          <h2 className={styles.sectionHeading}>Why it missed</h2>
          <p className={styles.sectionIntro}>
            The backtest says by how much. This says which assumption was wrong — each driver
            walked from what was forecast to what was reported, one at a time, with whatever the
            drivers do not explain left visible as a residual rather than absorbed into the last
            step. {variance.order_note}
          </p>
          {variance.offsetting_note && (
            <p className={styles.offsetting}>{variance.offsetting_note}</p>
          )}
          <VarianceBridge bridge={variance} />
        </section>
      )}

      {vintages && vintages.length > 1 && (
        <section className={styles.section}>
          <h2 className={styles.sectionHeading}>Does the error repeat?</h2>
          <p className={styles.sectionIntro}>
            Two vintages, each built from the initial guidance in the prior year&rsquo;s report —
            never a figure revised part-way through the year it describes. One point shows the
            size of a miss; two show whether it recurs. Both years undershoot operating profit,
            because {summary.short_label} guided conservatively in both and beat its own
            guidance in both. That is a property of the input, not of the arithmetic.
          </p>
          <VintageScorecard vintages={vintages} />
        </section>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Monte Carlo range</h2>
        <p className={styles.sectionIntro}>{monteCarlo.caveat}</p>
        <MonteCarloChart
          monteCarlo={monteCarlo}
          actualFcf={backtest ? backtest.actual.free_cash_flow : undefined}
        />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Which assumption explains the most variance?</h2>
        <p className={styles.sectionIntro}>
          The simulation ranks assumptions by how much of the free-cash-flow spread each one
          explains. That is a statistical reading, and it is not the same question as where
          management should spend its attention — an assumption can dominate the variance and
          still be one nobody can move. Priorities answers that second question.
        </p>
        <ul className={styles.varianceList}>
          {Object.entries(monteCarlo.sensitivity_to_fcf).map(([name, correlation]) => (
            <li key={name}>
              <span>{SENSITIVITY_LABELS[name] ?? name}</span>
              <span className="mono">{correlation.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        <Link href={withClient("/priorities", client)} className={styles.moreLink}>
          Ranked management priorities →
        </Link>
      </section>
      {summary.has_backtest && (
      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Data lineage — an example</h2>
        <div className={styles.lineage}>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Source disclosure</span>
            <span className={styles.lineageValue}>
              adidas_Report_2024.pdf, Targets – Results – Outlook, &ldquo;2025 Outlook&rdquo; column
            </span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Extracted fact</span>
            <span className={styles.lineageValue}>Operating profit guidance: €1.7bn – €1.8bn</span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Model assumption</span>
            <span className={styles.lineageValue}>
              EBITDA margin back-solved to hit the €1.75bn midpoint at 8% revenue growth (11.6%)
            </span>
          </div>
          <div className={styles.lineageArrow}>↓</div>
          <div className={styles.lineageStep}>
            <span className={styles.lineageLabel}>Forecast output</span>
            <span className={styles.lineageValue}>Base-case operating profit: €1.75bn</span>
          </div>
        </div>
      </section>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>What this is not</h2>
        <Disclaimers summary={summary} className={styles.notList} />
      </section>
    </div>
  );
}
