"""
Pre-generates management commentary for the Base case and all four named
presets, verifies it, and writes data/commentary.json.

Run once (or after any model or prompt change) with `make commentary`. The
live app serves these instantly rather than calling the LLM on every page
load — custom (non-preset) scenarios still get a live, on-demand call from the
Scenario Planner, gated behind an explicit "Generate" action, not triggered
automatically on every slider move.

**This is a gate, not a report.** Two checks run on every paragraph: grounding
(is each number in the output table?) and coherence (is it used to say
something the table supports?). If any paragraph fails either, nothing is
written and the command exits non-zero. The previous version printed a
grounding rate and wrote the file regardless, which is how five paragraphs
carrying seven false statements came to be committed with a perfect score
next to each of them.

`--allow-findings` writes anyway, for inspecting what a prompt change did
before deciding whether it is an improvement. It is deliberately not the
default.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from api import service
from src import config as C, drivers


def run(allow_findings: bool = False) -> int:
    results = {}
    failed: list[str] = []

    for scenario_id in drivers.PRESETS:  # "base" is itself one of the presets
        values = (
            service.base_driver_values()
            if scenario_id == "base"
            else service.resolve_preset(scenario_id)
        )
        # "base" is the driver-based forecast itself; every other preset is a
        # scenario and is labelled as one, so the commentary does not describe
        # a stress case as the driver-based model.
        series_name = "driver_based" if scenario_id == "base" else scenario_id
        commentary = service.generate_live_commentary(values, series_name=series_name)
        results[scenario_id] = {
            **commentary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        grounding = commentary["grounding"]["grounding_rate"]
        coherence = commentary["coherence"]
        status = "ok" if coherence["clean"] and grounding == 1.0 else "REJECTED"
        print(f"{scenario_id:20s} grounding {grounding}  coherence {coherence['finding_count']} finding(s)  {status}")
        for finding in coherence["findings"]:
            print(f"    [{finding['kind']}] {finding['detail']}")
            print(f"      in: {finding['sentence']}")
        if status == "REJECTED":
            failed.append(scenario_id)

    if failed and not allow_findings:
        print(
            f"\nRejected {len(failed)} of {len(results)} paragraph(s): {', '.join(failed)}.\n"
            "Nothing written. Re-run to resample, adjust the prompt in src/commentary.py, "
            "or pass --allow-findings to write anyway and inspect the output."
        )
        return 1

    (C.DATA / "commentary.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {C.DATA / 'commentary.json'}")
    if failed:
        print(f"WARNING: written with findings in {', '.join(failed)} (--allow-findings).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="generate_commentary",
        description="Generate and verify the preset management commentary.",
    )
    parser.add_argument(
        "--allow-findings",
        action="store_true",
        help="Write the file even if a paragraph fails verification.",
    )
    args = parser.parse_args()
    return run(allow_findings=args.allow_findings)


if __name__ == "__main__":
    raise SystemExit(main())
