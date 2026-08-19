import type { ClientSummary } from "@/lib/types";

/**
 * What this model is not — for THIS client.
 *
 * Extracted from the Evidence page so it can be tested. These were once
 * adidas's disclaimers rendered under whichever model was loaded, which told
 * a client that decomposes volume and price that it was "not a price/volume
 * analysis", and claimed a backtest point for a client that has none. A
 * disclaimer that is wrong is worse than no disclaimer, and those were wrong
 * in the direction of overclaiming.
 */
export default function Disclaimers({
  summary,
  className,
}: {
  summary: ClientSummary;
  className?: string;
}) {
  return (
    <ul className={className}>
      {summary.is_synthetic && (
        <li>
          <strong>A real company.</strong> {summary.disclaimer}
        </li>
      )}
      <li>
        <strong>A multi-company benchmark.</strong> One business, modelled in depth over a
        single planning horizon — not a peer comparison.
      </li>
      {summary.has_backtest ? (
        <>
          <li>
            <strong>A price/volume analysis.</strong> {summary.short_label} does not disclose
            that split, so product-division growth is the driver used here. The channel split
            (wholesale and direct-to-consumer) is extracted and available as an alternative
            segmentation, but the model runs one at a time.
          </li>
          <li>
            <strong>A track record.</strong> Two backtest points. Enough to show an error
            repeating and to expose a broken assumption; not enough to show the approach
            generalizes, and both forecasts missed by a lot.
          </li>
          <li>
            <strong>A trading or investment signal.</strong> A methodology exercise on public
            financial disclosures.
          </li>
        </>
      ) : (
        <>
          <li>
            <strong>A validated model.</strong> There is no outturn to test this forecast
            against, so nothing here demonstrates that the method works — only that it runs.
          </li>
          <li>
            <strong>Measured uncertainty.</strong> The simulation&rsquo;s ranges were chosen to
            be plausible, not observed. They carry no evidential weight.
          </li>
        </>
      )}
      <li>
        <strong>Advice.</strong> Nothing here is a recommendation. The management questions are
        prompts for a discussion, not conclusions from one.
      </li>
    </ul>
  );
}
