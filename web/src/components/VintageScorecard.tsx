import type { BacktestVintage } from "@/lib/types";
import { formatSignedPct } from "@/lib/format";
import styles from "./VintageScorecard.module.css";

const METRICS = [
  ["revenue", "Revenue"],
  ["operating_profit", "Operating profit"],
  ["free_cash_flow", "Free cash flow"],
] as const;

/**
 * Forecast error by vintage, driver-based against naive.
 *
 * The point of showing two years side by side is not the size of either miss.
 * It is whether a miss repeats — and whether the method that wins one year
 * wins the next. Here it wins five of six, and the one it loses is the year a
 * large unforecast working-capital release left a flat extrapolation closer.
 */
export default function VintageScorecard({ vintages }: { vintages: BacktestVintage[] }) {
  const losses = vintages.flatMap((v) =>
    METRICS.filter(
      ([key]) =>
        Math.abs(v.driver_based[`${key}_error_pct`]!) >= Math.abs(v.naive[`${key}_error_pct`]!),
    ).map(([, label]) => `${label.toLowerCase()} in ${v.forecast_year}`),
  );

  return (
    <>
      <div className={styles.wrap}>
        <table className={styles.table}>
          <caption className="visually-hidden">
            Forecast error by metric and vintage, driver-based against a naive extrapolation.
            The closer of the two is shown in bold.
          </caption>
          <thead>
            <tr>
              <th scope="col">Error vs. actual</th>
              {vintages.map((v) => (
                <th key={v.vintage} colSpan={2} scope="colgroup">
                  <span className={styles.vintageHead}>{v.label}</span>
                  <span className={styles.published}>
                    guidance published {v.guidance_published}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              <th scope="col"></th>
              {vintages.map((v) => [
                <th key={`${v.vintage}-d`} scope="col">Driver-based</th>,
                <th key={`${v.vintage}-n`} scope="col">Naive</th>,
              ])}
            </tr>
          </thead>
          <tbody>
            {METRICS.map(([key, label]) => (
              <tr key={key}>
                <td className={styles.metric}>{label}</td>
                {vintages.map((v) => {
                  const driver = v.driver_based[`${key}_error_pct`]!;
                  const naive = v.naive[`${key}_error_pct`]!;
                  const driverWon = Math.abs(driver) < Math.abs(naive);
                  return [
                    <td
                      key={`${v.vintage}-${key}-d`}
                      className={`mono ${driverWon ? styles.won : styles.lost}`}
                    >
                      {formatSignedPct(driver)}
                    </td>,
                    <td
                      key={`${v.vintage}-${key}-n`}
                      className={`mono ${driverWon ? styles.lost : styles.won}`}
                    >
                      {formatSignedPct(naive)}
                    </td>,
                  ];
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {losses.length > 0 && (
        <p className={styles.note}>
          The driver-based method is not uniformly better. It lost on{" "}
          {losses.join(" and ")}: adidas released working capital far faster than its own
          guidance implied, and a naive extrapolation holding the prior year&rsquo;s ratio flat
          happened to land closer on cash. A method that wins on average can still lose the
          year that matters.
        </p>
      )}
    </>
  );
}
