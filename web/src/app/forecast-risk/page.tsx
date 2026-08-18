import Link from "next/link";
import { api } from "@/lib/api";
import { clientFrom, withClient, type SearchParams } from "@/lib/client";
import { formatEur } from "@/lib/format";
import BacktestBars from "@/components/BacktestBars";
import VarianceBridge from "@/components/VarianceBridge";
import MonteCarloChart from "@/components/MonteCarloChart";
import styles from "./forecast-risk.module.css";

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
  const [backtest, monteCarlo, summary, variance] = await Promise.all([
    api.backtest(client),
    api.monteCarlo(client),
    api.client(client),
    api.variance("free_cash_flow", client),
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
              The driver-based forecast produced a smaller error than a naive extrapolation on
              every metric — but both undershot what {summary.short_label} actually delivered.
              Beating a naive baseline once is not the same claim as being reliable.
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

      {backtest && (
        <section className={styles.section}>
          <h2 className={styles.sectionHeading}>Forecast vintage</h2>
          <div className={styles.vintageEmpty}>
            <p>
              <strong>One backtest point, not a rolling history.</strong> A vintage timeline
              (plan → quarterly updates → actual) needs forecast snapshots taken through the
              year — this project has only the FY2024 report&rsquo;s initial FY2025 guidance and
              the FY2025 actuals, an annual cross-section rather than a rolling forecast. Showing
              a fabricated multi-point timeline here would overstate what this data supports.
            </p>
            <div className={styles.vintageTimeline}>
              <div className={styles.vintagePoint}>
                <span className={styles.vintageDot} />
                <span className={styles.vintageLabel}>FY2024 report</span>
                <span className={styles.vintageSub}>Guidance set</span>
              </div>
              <div className={styles.vintageLine} />
              <div className={styles.vintagePoint}>
                <span className={styles.vintageDot} />
                <span className={styles.vintageLabel}>FY2025 actual</span>
                <span className={styles.vintageSub}>Checked against</span>
              </div>
            </div>
          </div>
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
    </div>
  );
}
