# Information architecture audit

Written before any frontend change, against the inherited application at
`256c6e4` (forked from `fpa-decision-model@c32e90f`). Everything below is
grounded in the code as it exists — file references are to this repo.

---

## 1. Who this is for, and what they are deciding

| Persona | Frequency | The question they arrive with | Time budget |
|---|---|---|---|
| **CFO / Head of FP&A** (primary) | Weekly, before a review | *What needs my attention, and how much is at stake?* | ~30 seconds |
| **FP&A controller** | Daily during planning | *If this assumption moves, what happens?* | Minutes |
| **Business finance partner** | Monthly | *Which of my operational levers matters financially?* | Minutes |
| **Finance transformation consultant / reviewer** | Once, sceptically | *Is this method sound, or is it a demo?* | ~10 minutes |

The fourth persona is not in the original brief but is the one who actually
decides whether this project succeeds — a Senior Manager or Partner looking
for a reason to disbelieve it. The application already serves them unusually
well (see §5) and that must not be lost while serving the CFO better.

**The design tension:** personas 1 and 4 want opposite things. The CFO wants
a conclusion. The reviewer wants the conclusion's provenance and its
caveats. The current app resolves this by *interleaving* them — every screen
carries both the number and its limitations. That is honest but it costs the
CFO their 30 seconds.

**Resolution:** separate by *screen*, not by hiding. Conclusions and their
€ consequences move forward; provenance and method get their own destination
and stay one click away, always linked, never buried. Caveats that change how
a number should be read (e.g. the Monte Carlo range being disclosed guidance
rather than measured volatility) stay attached to the number itself.

---

## 2. What exists today

Four screens, numbered `01`–`04` in `components/Nav.tsx`:

| Route | Contains |
|---|---|
| `/` Outlook | Statement headline + 3 evidence lines; revenue/OP/FCF forecasts with backtest error deltas; split panel — backtest bars \| management attention; "largest financial exposure" as prose, computed live from a real scenario call |
| `/planner` Scenario Planner | 5 driver sliders, presets, out-of-guidance warning, scenario-vs-base table, FCF bridge waterfall, commentary panel |
| `/forecast-risk` Forecast & Risk | Backtest section + actuals table; forecast-vintage honest empty state; Monte Carlo histogram; driver priority list |
| `/model` Model & Assumptions | Calculation-chain driver tree; assumption register; data-lineage example; "What this is not" |

Backend already computes more decision logic than the UI implies:
`api/service.py::get_driver_priority()`, `compute_bridge()`,
`out_of_guidance()`, `get_assumption_register()`.

---

## 3. Findings

### F1 — The ranked-priority view is the product's core, and it has no home

`DriverPriorityList` renders on **two** screens against the same
`get_driver_priority()` data, under two different headings — "Management
attention" (`app/page.tsx:75`) and "Where should FP&A spend the next hour of
diligence?" (`app/forecast-risk/page.tsx`). Same component, same data, two
framings, neither authoritative.

This is the single most decision-relevant thing the application produces and
it is currently a sidebar in two places. **It earns a primary destination.**

### F2 — Priority is ranked on two axes, and neither is in euros

`get_driver_priority()` ranks by `|Monte Carlo correlation with FCF|`, tie-broken
by disclosure `confidence`. Two problems:

1. **Controllability is absent entirely.** A driver that is highly material
   and highly uncertain but that management cannot influence (FX) demands a
   different response from one that is equally material and *controllable*
   (inventory days). Today both sort identically. This is the substantive gap
   between the current app and a decision-support product.
2. **The output is a correlation coefficient.** `sensitivity_label()` softens
   it to High/Medium/Low, but the underlying ranking quantity is statistical,
   not financial. No CFO acts on `0.62`. **The ranking must be in euros.**

Note also that correlation conflates materiality and uncertainty — a driver
correlates strongly with FCF partly because it *matters* and partly because
it *varies* in the simulation. Separating the two axes is not cosmetic; it is
required for the three-axis model to mean anything.

### F3 — Outlook leads with evidence where it should lead with exposure

The split section gives backtest bars equal visual weight to management
attention, and the "largest financial exposure" — the best single paragraph
in the application, and a genuinely computed number — sits **last**, below
the fold. Order should be: management state → outlook → exposures →
priorities → *then* evidence.

### F4 — Nav ordinals imply a sequence that does not exist

`01 Outlook → 02 Scenario Planner → 03 Forecast & Risk → 04 Model` reads as a
document to be walked through. That suits a portfolio piece read once; it
misdescribes a tool returned to weekly, where only Outlook is an entry point
and the others are destinations. With a fifth item and a client selector
arriving, the ordinals become noise.

**Drop ordinals from nav.** Keep the editorial eyebrow on each page — it is
doing real work — but as `Outlook · adidas · FY2025`, not `01 — Outlook`.

### F5 — Client identity is hardcoded in the chrome

`Nav.tsx` hardcodes `adidas AG · FY2025` as the wordmark subtitle;
`layout.tsx` hardcodes it in `<title>`. This is exactly the surface the client
selector should occupy (see §4).

### F6 — `/model` serves two audiences at once

Assumption register (a controller's working artefact) sits beside data
lineage and "What this is not" (a sceptic's credibility artefact). Under
client packs the first half grows substantially — driver definitions,
mappings, config. The two halves should separate.

### F7 — The Planner answers "what number changes", not "what decision follows"

Slider → comparison table → bridge → commentary is a clean loop, but it
terminates in a number. Nothing tells the user whether the resulting position
breaches a threshold, how it ranks, or what decision it creates.

### F8 — Things to preserve deliberately

Not problems. Named so they survive the refactor:

- **The forecast-vintage empty state** (`forecast-risk/page.tsx`) explains
  why a timeline is *absent* rather than fabricating one. This is the single
  most senior-looking thing in the application. Extend the pattern; never
  remove it.
- **"What this is not"** — four honest disclaimers. Keep, and add the
  synthetic-client disclaimer to it.
- **Out-of-guidance flagging** — moving outside disclosed guidance is allowed
  but visibly marked. This is the right pattern for the decision thresholds.
- **The `reported / derived / assumption` discipline** in `src/drivers.py`.
- **Commentary grounding + coherence** (`src/claims.py`) — two independent
  checks, correctly separated.

---

## 4. Proposed architecture

**Five primary destinations, client selector in the wordmark slot.**

```
FP&A Decision Intelligence            Outlook  Priorities  Planner  Model  Evidence
[ adidas · Public Data      ▾ ]
```

| Destination | Job | Primary persona |
|---|---|---|
| **Outlook** | What needs attention now, and what is at stake | CFO |
| **Priorities** | Ranked exposures: € materiality × uncertainty × controllability | CFO / FP&A |
| **Planner** | If this assumption moves, what decision follows | FP&A |
| **Model** | How this business creates financial outcomes (drivers, config, tree) | Controller / consultant |
| **Evidence** | Backtest, Monte Carlo, lineage, limitations | Reviewer |

Rationale for five rather than four: **Priorities** is promoted because of F1.
**Model** and **Evidence** stay separate because F6 splits them and client
packs will make Model substantially heavier. Five is the ceiling — nothing
further gets promoted to primary nav.

**The client selector replaces the hardcoded subtitle (F5).** Two arguments
for this position: it puts *which model am I looking at* adjacent to the
product name, where a reader already looks to orient; and it reads as
selecting an active planning model rather than as a settings toggle, which a
nav item or a gear icon would both imply. It is a labelled select, not a
segmented control or a pill switcher.

**Audience modes (CFO / FP&A / Business Owner) are not navigation.** They
re-weight emphasis within Outlook and Priorities. Implement as a control
scoped to those two screens, not as global chrome — a global mode switch
multiplies the perceived surface by three and invites the user to wonder what
they are missing in the other modes.

### Outlook, reordered (F3)

1. **Management state** — what breaches tolerance, how much is at stake
2. **Decision Brief** — the single editorial composition: what matters, € at
   risk, why, threshold status, controllability, suggested question, owner,
   next trigger
3. **Financial outlook** — revenue / OP / FCF
4. **Key exposures** — the computed sensitivities
5. **Top priorities** — three rows, linking to Priorities
6. **Confidence** — one line on backtest error, linking to Evidence

---

## 5. Materiality model to implement

Replacing the two-axis ranking in F2. All three axes stated explicitly, with
their epistemic status labelled — *computed* vs *declared judgement* — in the
UI as well as here.

| Axis | Source | Status |
|---|---|---|
| **Financial materiality** | € change in the objective KPI when the driver moves across its plausible range, computed by re-running `model.forecast()` — the same technique `compute_bridge()` already uses | **Computed** |
| **Uncertainty** | The inverse of the driver's declared disclosure confidence | **Declared** |
| **Controllability** | Management's ability to influence the driver within the horizon | **Declared** in the client pack |

> **As built.** This audit originally proposed combining disclosure confidence
> with Monte Carlo dispersion for the uncertainty axis. The implementation uses
> confidence alone. Mixing a declared judgement with a simulated statistic
> would have produced an axis that was neither auditable nor measured, and
> whose provenance could not be labelled honestly on screen. Simulated
> sensitivity is still shown, on Evidence, as the separate question it is.

Controllability cannot be derived from public financials. It is a judgement,
it must live in configuration, and the UI must say so — the same way
`confidence` is already presented as "a judgment call, not computed"
(`src/drivers.py` docstring). Presenting a declared input as a computed one
is the fastest way to lose the reviewer persona.

**Classification, not multiplication.** Priority is a stated rule over banded
inputs, not a product of three scores:

| Materiality | Uncertainty | Controllability | Priority |
|---|---|---|---|
| High | High | High | **Critical** |
| High | High | Low | **Monitor** — large, uncertain, not yours to fix |
| High | Low | High | **Act** |
| Medium | Any | High | **Review** |
| Low | Any | Any | **Monitor** |

The "high materiality, high uncertainty, low controllability → Monitor" cell
is the one that makes this model worth having: it is precisely where a naive
`materiality × uncertainty` ranking sends management to spend time it cannot
convert into outcomes. The methodology must be visible in the UI, including
this cell, with the full band table reachable from the Priorities screen.

---

## 6. What this audit does not settle

- **Visual identity inheritance.** The design system in `globals.css` is
  shared with the author's personal site. Keeping it makes the accelerator
  look like portfolio work; diverging costs coherence. Flagged for the author
  — not a UX decision.
- **Whether Evidence should be reachable from primary nav at all**, or only
  contextually from the numbers it substantiates. Revisit after Priorities
  exists.
- **Audience-mode depth.** Whether the three modes differ enough to justify
  themselves, or whether CFO/FP&A is the only real split, is better judged
  against a built Priorities screen than in advance.

---

## 7. Build order

1. Client-pack architecture; adidas migrated; backtest reproduction intact
2. Manufacturing Demo; client switching; no cross-client leakage
3. Controllability + € materiality → three-axis engine → **Priorities**
4. **Decision Brief** → Outlook reorder
5. Planner upgrade (F7); Model/Evidence split (F6); nav change (F4, F5)
6. Polish, responsive QA, docs, final design critique


---

## 8. Built against this audit

| Finding | Outcome |
|---|---|
| F1 — priority view had no home | **Priorities** is a primary destination; the duplicate is gone from Forecast & Risk |
| F2 — two-axis ranking, not in euros | Three-axis engine, exposure computed in euros (`src/materiality.py`) |
| F3 — Outlook led with evidence | Outlook opens with the Decision Brief; backtest moved below |
| F4 — nav ordinals implied a sequence | Dropped |
| F5 — client identity hardcoded in chrome | The wordmark subtitle is now the model selector |
| F6 — `/model` served two audiences | Partly. Model is client-driven and Evidence carries the credibility material, but the split is not yet clean |
| F7 — Planner ended at a number | Consequence panel: thresholds crossed, priority, question, owner, trigger |
| F8 — things to preserve | Vintage empty state, "what this is not", out-of-guidance flagging and the grounding/coherence split all survive |

Audience modes (§4) were **not built**. Having built Priorities and the Brief,
the three modes would mostly re-cut content already pitched correctly: the
Brief is the CFO view, Priorities is the FP&A view, and the owner/trigger rows
carry the business-owner framing. A global mode switch would add a control
whose main effect is to make a reader wonder what they are missing elsewhere.
