# Accessibility audit

Run against the deployed application. Findings and what was done about them.

## Fixed

**Exposure bars fell below the non-text contrast floor.** The priority scale
ran from the hairline tone (`#c6cac0`, **1.38:1** against the page) up to ink.
Those tokens paint the exposure bars on Priorities, which encode magnitude
rather than decorate, so WCAG 1.4.11 applies and the lightest two steps were
effectively invisible. The scale now starts at `border-strong` and every step
clears 3:1:

| Band | Ratio |
|---|---:|
| Critical | 4.76:1 |
| Act | 14.63:1 |
| Review | 5.15:1 |
| Monitor | 3.14:1 |

**No consistent focus indicator.** Three components styled their own; the
primary navigation, the scenario presets and every "more" link fell back to
whatever ring the browser draws. Nothing suppressed the default, so keyboard
users were never stranded — but the treatment was inconsistent and a future
`outline: none` would have had nothing deliberate to override. One
`:focus-visible` rule in `globals.css` now covers every control, including
ones not written yet. The slider keeps a wider offset, because its thumb sits
on a track with the guidance band drawn behind it.

**The Planner announced nothing.** Moving a slider rewrites the entire results
column — comparison table, bridge, threshold breaches — and a screen reader
was told none of it. The summary sentence is now `aria-live="polite"`, so each
update announces what moved and whether a threshold was crossed. Marking the
results column itself live was rejected: it would read every figure in the
table on every keystroke, which is worse than silence.

## Checked and sound

- **Text contrast** — body 14.63:1, secondary 5.15:1, accent 5.32:1, status
  colours 4.76–5.32:1. All above 4.5:1.
- **Headings** — one `h1` per page, no skipped levels.
- **Landmarks** — `header`, `nav`, `main` on every page.
- **Tables** — every table has a `caption` and every `th` a `scope`.
- **Controls** — all five Planner sliders carry `aria-label`; no unnamed
  buttons or links anywhere.
- **Images** — none without `alt`.
- **Reduced motion** — `prefers-reduced-motion` collapses every transition.
- **Scenario errors** — already `role="alert"`.

## Not verified

**The focus ring was not confirmed visually.** Synthetic key events do not
trigger Chrome's `:focus-visible` heuristic, so browser automation cannot
observe the state. The rule is present in the compiled stylesheet with the
correct declaration and nothing suppresses outlines, but it has not been seen
rendered. Worth one pass with a real keyboard.

**No screen-reader testing.** The semantics are correct by inspection; nobody
has driven this with VoiceOver or NVDA, and inspection is not the same as use.

**The hairline rule stays at 1.38:1.** A rule that only separates table rows
is exempt from 1.4.11, and darkening it would coarsen every table in the
product to fix a bar that no longer uses that token.
