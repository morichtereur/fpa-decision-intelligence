"""
Stage 1: pull the currency-neutral growth breakdown out of the two source
PDFs.

adidas doesn't disclose a price/volume bridge (see data/raw/README.md for
how that was checked before this design was picked). What it discloses,
consistently, is:

- Financial Highlights: net sales, gross profit, EBITDA, operating profit,
  net income, and the margin/working-capital/capex ratios behind them
- Net sales by product division: Footwear / Apparel / Accessories
- Net sales by channel: Wholesale / Direct-to-Consumer (only in the 2025
  report as an explicit euro table — the 2024 report only gives the DTC
  share of sales as a narrative percentage, so 2023/2024 channel euros are
  derived from that share, not directly disclosed)
- Targets – Results – Outlook: adidas's own stated guidance for the
  following fiscal year, which becomes this project's planning-assumption
  input for the backtest

A real restatement wrinkle showed up while extracting this: the FY2025
report's FY2024 comparatives don't match the FY2024 report's own FY2024
figures. Product division is the sharpest example — Accessories 2024 goes
from € 1,499m (as originally reported) to € 1,779m (as restated, footnoted
"reclassification within the product divisions") — an ~19% gap. This
module keeps both versions rather than picking one, tagged by which report
they came from; which one becomes "the" 2024 baseline for the model is a
decision made explicitly in src/model.py, not silently defaulted here.

The Targets–Results–Outlook table's cells wrap across PDF text lines in a
way that makes column-position parsing unreliable (a wrapped two-line
target description produces the same whitespace signature as an actual
column boundary). Rather than force a generic parser onto genuinely
ambiguous text, the guidance figures are extracted by searching for the
exact phrases confirmed present in the source text — verified against both
PDFs before being hardcoded as search targets. If adidas changes this
wording in a future report, the search fails loudly (raises) instead of
silently extracting the wrong number.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pypdf

from src import config as C


def _pdf_text(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _flatten(text: str) -> str:
    """Collapse all whitespace runs (including the \\xa0 pypdf emits for
    non-breaking spaces) to single spaces, for phrase search."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _to_number(raw: str):
    raw = raw.strip().replace("\xa0", " ")
    if raw in ("n.a.", "—", "-", ""):
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    raw = raw.rstrip("%").replace(",", "").replace("pp", "")
    try:
        value = float(raw) if "." in raw else int(raw)
    except ValueError:
        return None
    return -value if negative else value


def _parse_labeled_table(text: str, start_anchor: str, end_anchor: str, labels: dict) -> dict:
    """Split a table block into label -> [col1, col2, ...] for known labels.

    PDF-extracted table rows come out as "Label  val1  val2  val3" with
    runs of 2+ spaces between columns — real, observed formatting in both
    adidas reports, not assumed. Trailing footnote digits on labels (e.g.
    "Equity ratio1") are stripped before matching.
    """
    block = text.split(start_anchor, 1)[-1].split(end_anchor, 1)[0]
    out = {}
    for line in block.splitlines():
        line = line.replace("\xa0", " ").strip()
        if not line:
            continue
        parts = re.split(r"\s{2,}", line)
        if not parts:
            continue
        label = re.sub(r"\s*\d+$", "", parts[0])
        if label in labels:
            # Some labels (e.g. "Net cash generated from operating
            # activities") appear twice — once in € millions, once again
            # per-share further down. First occurrence wins; verified by
            # inspecting the actual table order in both reports.
            out.setdefault(labels[label], parts[1:])
    return out


FINANCIAL_HIGHLIGHTS_LABELS = {
    "Net sales": "net_sales",
    "Gross profit": "gross_profit",
    "EBITDA": "ebitda",
    "Operating profit": "operating_profit",
    "Net income attributable to shareholders": "net_income_attributable",
    "Net income/(loss) attributable to shareholders": "net_income_attributable",
    "Gross margin": "gross_margin_pct",
    "Operating margin": "operating_margin_pct",
    "Effective tax rate": "effective_tax_rate_pct",
    "Average operating working capital in % of net sales": "operating_working_capital_pct",
    "Capital expenditure": "capex",
    "Cash flows from operating activities": "cash_from_operations",
    "Net cash generated from operating activities": "cash_from_operations",
}

PRODUCT_DIVISION_LABELS = {
    "Footwear": "footwear",
    "Apparel": "apparel",
    "Accessories and Gear": "accessories",
    "Accessories": "accessories",
}

CHANNEL_LABELS = {
    "Wholesale": "wholesale",
    "Direct-to-Consumer (DTC)": "dtc",
}


def extract_financial_highlights(text: str, current_year: int, prior_year: int) -> dict:
    heading = f"Financial Highlights {current_year} (IFRS)"
    table = _parse_labeled_table(text, heading, "About this Report", FINANCIAL_HIGHLIGHTS_LABELS)
    result = {str(current_year): {}, str(prior_year): {}}
    for field, cols in table.items():
        if len(cols) < 2:
            continue
        result[str(current_year)][field] = _to_number(cols[0])
        result[str(prior_year)][field] = _to_number(cols[1])
    return result


def extract_product_division(text: str, current_year: int, prior_year: int, heading: str, end_anchor: str) -> dict:
    table = _parse_labeled_table(text, heading, end_anchor, PRODUCT_DIVISION_LABELS)
    result = {str(current_year): {}, str(prior_year): {}}
    for field, cols in table.items():
        result[str(current_year)][field] = _to_number(cols[0])
        result[str(prior_year)][field] = _to_number(cols[1])
    return result


def extract_channel_table(text: str, current_year: int, prior_year: int) -> dict:
    """Only present as an explicit euro table in the 2025 report."""
    table = _parse_labeled_table(text, "Net sales by channel", "Cost of sales", CHANNEL_LABELS)
    result = {str(current_year): {}, str(prior_year): {}}
    for field, cols in table.items():
        result[str(current_year)][field] = _to_number(cols[0])
        result[str(prior_year)][field] = _to_number(cols[1])
    return result


def extract_channel_share_narrative(text: str, current_year: int, prior_year: int) -> dict:
    """2024 report only discloses DTC/wholesale as a % share narrative:
    "wholesale remained our largest channel, accounting for 60% of total
    net sales in 2024 (2023: 59%) ... DTC ... was 40% in 2024 (2023: 41%)."
    """
    flat = _flatten(text)
    wholesale = re.search(
        r"wholesale remained our largest channel, accounting for (\d+)% of total net sales in "
        rf"{current_year} \({prior_year}: (\d+)%\)",
        flat,
    )
    dtc = re.search(
        rf"consisting of own retail and e-commerce sales, was (\d+)% in {current_year} \({prior_year}: (\d+)%\)",
        flat,
    )
    if not wholesale or not dtc:
        raise ValueError("Expected DTC/wholesale share narrative not found — check the source text.")
    return {
        str(current_year): {"wholesale_pct_of_sales": int(wholesale.group(1)), "dtc_pct_of_sales": int(dtc.group(1))},
        str(prior_year): {"wholesale_pct_of_sales": int(wholesale.group(2)), "dtc_pct_of_sales": int(dtc.group(2))},
    }


def extract_guidance_from_2024_report(text: str) -> dict:
    """FY2025 guidance as stated in the FY2024 report's "2025 Outlook"
    column — the planning assumption the backtest is built on. Extracted
    by phrase search, not table parsing; see module docstring.
    """
    flat = _flatten(text)
    required = [
        "between € 1.7 billion and € 1.8 billion",
        "high-single-digit rate",
        "between 21% and 22%",
        "around € 600 million",
    ]
    for phrase in required:
        if phrase not in flat:
            raise ValueError(f"Expected FY2025 guidance phrase not found: {phrase!r}")
    return {
        "cn_sales_growth": "high-single-digit rate",
        "operating_profit_eur_m_low": 1700,
        "operating_profit_eur_m_high": 1800,
        "operating_working_capital_pct_low": 21,
        "operating_working_capital_pct_high": 22,
        "capex_eur_m": 600,
        "source": "Adidas_Report_2024.pdf, Targets – Results – Outlook, 2025 Outlook column",
    }


def extract_guidance_from_2023_report(text: str) -> dict:
    """FY2024 guidance as stated in the FY2023 report's "2024 Outlook" column.

    This is the INITIAL guidance, published February 2024. It matters that it
    is the initial one: the FY2024 report's own targets column is labelled "As
    published on October 15, 2024" — guidance revised three quarters into the
    year it describes. Backtesting against a revised figure would be testing
    the model on information it could not have had.

    Two shape differences from the FY2025 guidance, both real:
    operating profit is guided as a point ("around EUR 500 million") rather
    than a range, and working capital is guided at 23-24% rather than 21-22%.
    """
    flat = _flatten(text)
    required = [
        "to increase at a mid-single-digit rate",
        "operating profit of around € 500 million",
        "to reach a level of between 23% and 24%",
        "to reach a level of around € 600 million",
    ]
    for phrase in required:
        if phrase not in flat:
            raise ValueError(f"Expected FY2024 guidance phrase not found: {phrase!r}")
    return {
        "cn_sales_growth": "mid-single-digit rate",
        # Guided as a single figure, not a band. Low and high are equal so the
        # same midpoint resolver works for both vintages without a special case.
        "operating_profit_eur_m_low": 500,
        "operating_profit_eur_m_high": 500,
        "operating_profit_guided_as": "point",
        "operating_working_capital_pct_low": 23,
        "operating_working_capital_pct_high": 24,
        "capex_eur_m": 600,
        "source": "Adidas_Report_2023.pdf, Targets – Results – Outlook, 2024 Outlook column (initial, published February 2024)",
    }


def run() -> dict:
    text23 = _pdf_text(C.RAW / "Adidas_Report_2023.pdf")
    text24 = _pdf_text(C.RAW / "Adidas_Report_2024.pdf")
    text25 = _pdf_text(C.RAW / "Adidas_Report_2025.pdf")

    facts = {
        "company": C.COMPANY,
        "currency": "EUR",
        "unit": "millions",
        "group": {},
        "product_division": {},
        "channel": {},
        "guidance": {},
    }

    # The FY2023 report carries FY2022 as its comparative column. Without it
    # the FY2024 vintage has no prior year to extrapolate a naive run-rate
    # from, and the naive baseline is the thing the driver-based forecast is
    # being compared against.
    fh_2023 = extract_financial_highlights(text23, 2023, 2022)
    fh_2024 = extract_financial_highlights(text24, 2024, 2023)
    fh_2025 = extract_financial_highlights(text25, 2025, 2024)
    # FY2022 comes from the FY2023 report and carries only what its Financial
    # Highlights table holds — enough for the naive run-rate, which needs net
    # sales and nothing else.
    #
    # FY2023 stays sourced from the FY2024 report. That table carries working
    # capital % and cash flow, which the FY2023 report's own highlights table
    # does not, and the model needs them for a baseline year. The two reports
    # agree on every FY2023 figure they both state, so nothing is lost by
    # preferring the more complete one.
    facts["group"]["2022"] = {**fh_2023["2022"], "source": "Adidas_Report_2023.pdf"}
    facts["group"]["2023"] = {**fh_2024["2023"], "source": "Adidas_Report_2024.pdf"}
    facts["group"]["2024"] = {**fh_2024["2024"], "source": "Adidas_Report_2024.pdf"}
    facts["group"]["2024_restated"] = {**fh_2025["2024"], "source": "Adidas_Report_2025.pdf"}
    facts["group"]["2025"] = {**fh_2025["2025"], "source": "Adidas_Report_2025.pdf"}

    pd_2024 = extract_product_division(
        text24, 2024, 2023, "Net sales by product category", "Momentum broadening"
    )
    pd_2025 = extract_product_division(
        text25, 2025, 2024, "Net sales by product division", "Cost of sales"
    )
    facts["product_division"]["2023"] = {**pd_2024["2023"], "source": "Adidas_Report_2024.pdf"}
    facts["product_division"]["2024"] = {**pd_2024["2024"], "source": "Adidas_Report_2024.pdf"}
    facts["product_division"]["2024_restated"] = {**pd_2025["2024"], "source": "Adidas_Report_2025.pdf"}
    facts["product_division"]["2025"] = {**pd_2025["2025"], "source": "Adidas_Report_2025.pdf"}

    ch_share = extract_channel_share_narrative(text24, 2024, 2023)
    ch_2025 = extract_channel_table(text25, 2025, 2024)
    facts["channel"]["2023"] = {
        **ch_share["2023"],
        "note": "derived from % share narrative, not a direct euro table",
        "source": "Adidas_Report_2024.pdf",
    }
    facts["channel"]["2024"] = {
        **ch_share["2024"],
        "wholesale": round(facts["group"]["2024"]["net_sales"] * ch_share["2024"]["wholesale_pct_of_sales"] / 100),
        "dtc": round(facts["group"]["2024"]["net_sales"] * ch_share["2024"]["dtc_pct_of_sales"] / 100),
        "note": "derived from % share narrative, not a direct euro table",
        "source": "Adidas_Report_2024.pdf",
    }
    facts["channel"]["2024_restated"] = {**ch_2025["2024"], "source": "Adidas_Report_2025.pdf"}
    facts["channel"]["2025"] = {**ch_2025["2025"], "source": "Adidas_Report_2025.pdf"}

    facts["guidance"]["fy2024_initial"] = extract_guidance_from_2023_report(text23)
    facts["guidance"]["fy2025_initial"] = extract_guidance_from_2024_report(text24)

    C.FACTS.mkdir(parents=True, exist_ok=True)
    out_path = C.FACTS / "adidas_drivers.json"
    out_path.write_text(json.dumps(facts, indent=2, ensure_ascii=False))
    return facts


if __name__ == "__main__":
    result = run()
    print(f"Wrote {C.FACTS / 'adidas_drivers.json'}")
    print(f"Group net sales: 2023={result['group']['2023']['net_sales']}, "
          f"2024={result['group']['2024']['net_sales']}, "
          f"2025={result['group']['2025']['net_sales']}")
