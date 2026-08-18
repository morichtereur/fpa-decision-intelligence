import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import BridgeChart from "./BridgeChart";
import Disclaimers from "./Disclaimers";
import DriverTree from "./DriverTree";
import MetricMap from "./MetricMap";
import PriorityTable from "./PriorityTable";
import { driverConfig, priorityRow, summary } from "./renderRegressions.fixtures";

/**
 * One test per defect that reached a rendered page while the production build,
 * `tsc` and the whole Python suite stayed green. These are regressions, not
 * coverage for its own sake.
 */

describe("PriorityTable — exposure bars", () => {
  it("draws a bar with a real width for every row", () => {
    // Shipped once as a <span> with no display:block, so `width` did nothing
    // and the bars were invisible on a screen whose whole argument is that
    // you can see magnitude without reading a number.
    const { container } = render(
      <PriorityTable
        rows={[
          priorityRow({ driver_id: "a", exposure_magnitude: 640, priority: "Act" }),
          priorityRow({ driver_id: "b", exposure_magnitude: 60, priority: "Review" }),
        ]}
      />,
    );
    const bars = [...container.querySelectorAll<HTMLElement>("[class*='bar']")];
    expect(bars).toHaveLength(2);
    for (const bar of bars) {
      expect(parseFloat(bar.style.width)).toBeGreaterThan(0);
      // The inline width is not enough on its own: the bug shipped as a <span>
      // whose CSS left it inline, so the width was set and inert. jsdom
      // resolves the CSS module, so the rule itself can be asserted.
      expect(getComputedStyle(bar).display).not.toBe("inline");
    }
  });

  it("scales bars against the largest exposure on the page", () => {
    const { container } = render(
      <PriorityTable
        rows={[
          priorityRow({ driver_id: "a", exposure_magnitude: 100, priority: "Act" }),
          priorityRow({ driver_id: "b", exposure_magnitude: 25, priority: "Review" }),
        ]}
      />,
    );
    const [first, second] = [...container.querySelectorAll<HTMLElement>("[class*='bar']")];
    expect(parseFloat(first.style.width)).toBeCloseTo(100, 0);
    expect(parseFloat(second.style.width)).toBeCloseTo(25, 0);
  });

  it("groups rows under their priority band", () => {
    render(
      <PriorityTable
        rows={[
          priorityRow({ driver_id: "a", priority: "Act" }),
          priorityRow({ driver_id: "b", priority: "Monitor", materiality: "Medium" }),
        ]}
      />,
    );
    expect(screen.getByText("Act")).toBeInTheDocument();
    expect(screen.getByText("Monitor")).toBeInTheDocument();
  });

  it("explains a row only where the band is not what the exposure implies", () => {
    render(
      <PriorityTable
        rows={[
          priorityRow({ driver_id: "a", priority: "Act", rationale: "ACT REASON" }),
          priorityRow({
            driver_id: "b", priority: "Monitor", materiality: "Medium",
            controllability: "Low", rationale: "MONITOR REASON",
          }),
        ]}
      />,
    );
    // The three axis columns already say why an Act row is an Act row.
    expect(screen.queryByText("ACT REASON")).not.toBeInTheDocument();
    expect(screen.getByText("MONITOR REASON")).toBeInTheDocument();
  });
});

describe("BridgeChart — endpoints", () => {
  const waterfall = (first: string, last: string) => [
    { label: first, value: 1069, delta: null },
    { label: "Working capital", value: 700, delta: -369 },
    { label: last, value: 700, delta: null },
  ];

  it.each([
    ["Base", "Scenario"],
    ["Forecast", "Actual"],
  ])("draws a full-width endpoint bar for %s / %s", (first, last) => {
    // The endpoint test used to match the labels "Base" and "Scenario", so the
    // variance bridge's closing "Actual" bar collapsed to zero width. Endpoints
    // are the steps carrying no delta, whatever they are called.
    const { container } = render(<BridgeChart steps={waterfall(first, last)} />);
    const bars = [...container.querySelectorAll<HTMLElement>("[class*='bar']")];
    const widths = bars.map((b) => parseFloat(b.style.width));

    expect(widths[0]).toBeGreaterThan(50);
    expect(widths[widths.length - 1]).toBeGreaterThan(50);
  });
});

describe("DriverTree — the client's own drivers", () => {
  it("hangs each driver off the calculation step it feeds", () => {
    // Shipped with `maps_to` missing from the API payload, so the entire
    // right-hand column — the only client-specific content on the page —
    // rendered empty.
    render(<DriverTree drivers={driverConfig} />);
    expect(screen.getByText("Volume growth")).toBeInTheDocument();
    expect(screen.getByText("Price / mix")).toBeInTheDocument();
    expect(screen.getByText("Capex")).toBeInTheDocument();
  });

  it("marks a driver that is a component rather than the assumption itself", () => {
    render(<DriverTree drivers={driverConfig} />);
    expect(screen.getByText(/· add/)).toBeInTheDocument();
  });
});

describe("Disclaimers — per client, never inherited", () => {
  it("gives a public client its disclosure caveats", () => {
    render(<Disclaimers summary={summary()} />);
    expect(screen.getByText(/A track record/)).toBeInTheDocument();
    expect(screen.getByText(/A price\/volume analysis/)).toBeInTheDocument();
    expect(screen.queryByText(/A real company/)).not.toBeInTheDocument();
  });

  it("never tells a synthetic client it has a backtest or a disclosure split", () => {
    // The leak: adidas's caveats rendered under whichever model was loaded, so
    // the manufacturing client claimed not to be a price/volume analysis while
    // decomposing volume and price, and cited a backtest point it lacks.
    render(
      <Disclaimers
        summary={summary({
          id: "manufacturing_demo", short_label: "Manufacturing",
          is_synthetic: true, has_backtest: false,
          disclaimer: "Synthetic demonstration data.",
        })}
      />,
    );
    expect(screen.getByText(/A real company/)).toBeInTheDocument();
    expect(screen.getByText(/A validated model/)).toBeInTheDocument();
    expect(screen.queryByText(/A track record/)).not.toBeInTheDocument();
    expect(screen.queryByText(/A price\/volume analysis/)).not.toBeInTheDocument();
  });

  it("never claims to be advice, whatever the client", () => {
    for (const s of [summary(), summary({ is_synthetic: true, has_backtest: false })]) {
      const { unmount } = render(<Disclaimers summary={s} />);
      expect(screen.getByText(/Advice/)).toBeInTheDocument();
      unmount();
    }
  });
});

describe("MetricMap — both pack shapes", () => {
  it("renders account numbers for a ledger-backed client", () => {
    render(
      <MetricMap
        mappings={{
          net_sales: {
            source_accounts: ["400000", "401000"],
            statement: "Income statement",
            basis: "reported",
          },
        }}
      />,
    );
    expect(screen.getByText("400000, 401000")).toBeInTheDocument();
    expect(screen.getByText("reported")).toBeInTheDocument();
  });

  it("renders fact paths for a client built from filings, and flags derived metrics", () => {
    render(
      <MetricMap
        mappings={{
          free_cash_flow: {
            fact_path: null,
            statement: "Derived",
            basis: "derived",
            note: "NOPAT + D&A - change in working capital - capex.",
          },
        }}
      />,
    );
    const row = screen.getByText(/free cash flow/).closest("tr")!;
    expect(within(row).getByText("derived")).toBeInTheDocument();
  });
});
