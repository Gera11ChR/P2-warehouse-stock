# Economic Valuation of Project P2

**Estimate date:** 2026-09-30
**Subject:** P2 — Warehouse / stock control system for DMS-TELECOM fiber-optic logistics
**Status:** Estimate, not a formal appraisal · Source of truth for the summary published in [`../README.md`](../README.md) §11
**Language:** English

---

## 1. Purpose, nature and caveats

This document estimates the economic value of Project P2 under four complementary lenses, using only evidence available in this repository plus published 2026 market data.

**What this is:**

- A reasoned, source-cited **estimate of value** for internal planning, budgeting and build-vs-buy conversations.

**What this is not:**

- Not a formal appraisal, fairness opinion, audit or valuation under any accounting standard (IVS/ASA/USPAP).
- Not a claim about revenue, cash flow or enterprise value — the repository contains **no financial statements, no headcount, no inventory value and no user counts**.
- Not a commitment that any figure will be realized. Every range below is conditional on the assumptions in §11.

All project metrics were re-verified on **2026-09-30** directly against the repository and a running database. All external sources were accessed on the same date (§12).

---

## 2. Methodology

Four standard valuation lenses are applied. They are deliberately kept separate because they answer different questions and, in an AI-deflated market, they diverge widely.

| # | Lens | Question it answers | Headline range |
| --- | --- | --- | --- |
| A | **Cost of production** | What did it actually cost to produce this asset? | **$12k – $30k** |
| B | **Replacement / market value** | What would a buyer pay, or what would it cost to commission the same scope today? | **$75k – $200k** |
| C | **Value in use** | What is it worth to the operating business versus buying a SaaS alternative? | **$50k – $200k** (5-year, risk-adjusted) |
| D | **Product value** | What could it realize if commercialized as a licensed product? | **$92k – $185k** (3-year contract value) |

Approach **B is adopted as the headline figure**, because it is the only lens anchored to observable market prices rather than to internal cost or speculative upside. A and C bound it from below and above respectively.

---

## 3. Verified project baseline

Every figure below was measured in this repository on 2026-09-30 (LOC via `wc -l` over the listed trees; DB figures via `information_schema`/`pg_proc`; QA via `pytest`, `vitest`, `mypy`).

### 3.1 Code and artifacts

| Artifact | Measurement |
| --- | --- |
| Backend Python (`app/ + tests/ + alembic/ + scripts/`) | **14,471 LOC** — 5,040 application · 5,574 tests · 3,628 migrations · 229 scripts |
| Frontend TypeScript/TSX (`src/`) | **9,659 LOC** (of which 1,565 test LOC) |
| Canonical DDL (`backend/db/ddl.sql`) | **1,217 LOC** |
| Documentation & specs (`docs/ + openspec/`) | **6,561 LOC** |
| **Total repository artifacts** | **≈ 31,900 LOC** |

### 3.2 Functional surface

| Dimension | Count |
| --- | --- |
| HTTP endpoints (REST, `/api/v1`) | **43** |
| Alembic migrations | **15** (`0001` → `0015`) |
| PostgreSQL stored functions (`fn_*`) | **14** (transaction delegation, enforced by contract) |
| Physical tables in `p2` schema | **33** — 17 active domain tables + 16 legacy / pre-MFA tables no longer referenced by application code |
| Indexes in DDL + migrations | **12** |
| Frontend screens / components / hooks / services | **6 / 21 / 13 / 9** |
| Domain rules enforced by test harness | 16 domain tables truncated, 10 seed units of measure, `p2_test` isolation schema |

### 3.3 Quality evidence

| Gate | Result (2026-09-30) |
| --- | --- |
| Backend (`pytest tests/`) | **209 passed**, 19 files, ≈24 s |
| Frontend (`npm test`, vitest) | **45 passed**, 10 files, 7.42 s |
| Types (`mypy app/ tests/`) | **0 issues / 68 files** — *default configuration, not strict* (see README §10.2) |
| Production build (`npm run build`) | ✓ 667 ms · 2,077 modules · 488.62 kB JS / 22.93 kB CSS |
| Lint (`npm run lint`) | Clean |

### 3.4 Delivery envelope

| Dimension | Value |
| --- | --- |
| Active window | **2026-09-02 → 2026-09-30 (29 days)** |
| Commits | **34**, linear history, single repository |
| Team model | **1 senior developer + AI agent fleet** (11 spec-driven agents, 8 phase gates) |
| Governance artifacts | 1 Constitution · operational flow phases 0–13 · 9 OpenSpec change packages (7 archived) |

This envelope is the single most important input to Approach A: a scope that market data prices at **4–6 months of agency time** (§4) was delivered in **29 calendar days**.

---

## 4. Market context (2026)

Published bands for building a warehouse management system in 2026. Sources in §12.

| Source (date) | What it prices | Band |
| --- | --- | --- |
| Rorix, *How to Build a Custom WMS* (2026-08-29) | Custom WMS, all-in | **$70,000 – $250,000+** |
| Rorix, *cost bands* (reviewed 2026-09-10) | Single-site with ERP integration | **$30,000 – $64,000** (3–4 months, 3–5 devs) |
| Rorix, same | Mid-level, multi-module + mobile | **$64,000 – $150,000** (3–6 months) |
| Rorix, same | Multi-site / RFID / heavy integration | **$80,000 – $180,000+** |
| Stfalcon, *WMS software cost* (2026-07-14) | Custom WMS build | **$80,000 – $300,000+** |
| Stfalcon, worked example | Production platform, 65 users / 5 sites | **≈ $150,000**, maintenance at **15%/yr** |
| YuSMP, *WMS development guide* (2026-07-18) | Starter WMS, single facility, 4 core modules | **$150k–$250k MVP · $250k–$400k production** (4–6 months) |
| YuSMP, same | Full WMS with ERP integration | **$250k–$450k MVP · $450k–$850k production** (6–10 months) |
| GoodFirms / Clutch survey data (cited by Rorix, 2026-07-26) | Most small/mid custom builds; Clutch average | **$30,000 – $100,000**; average **≈ $132,000** |
| OrderPilots, *implementation cost guide* (2026-08-25) | Mid-market cloud WMS, year 1 all-in | **$150,000 – $400,000** |

**Ongoing cost of a custom build:** **15–25% of build value per year** (Rorix), modelled at **15%** by Stfalcon in its 3-year TCO.

**Where P2 sits:** P2 is a single-organization, single-tenant system with 43 endpoints, 6 screens and a hard transactional core in PostgreSQL. It has **no ERP integration, no carrier/marketplace connectors, no barcode/RFID hardware layer, no mobile client and no multi-tenant isolation** — precisely the four drivers that push a build from the $30k–64k band to the $150k+ bands (Rorix and YuSMP both say so explicitly). It also exceeds a bare single-site CRUD build: it carries 14 stored functions, an immutable audit ledger, 209 backend tests and a documented governance process.

**Conclusion:** P2 belongs in the **"mid-level custom WMS, single site"** band — i.e. the intersection of Rorix's $64k–$150k and Stfalcon's $80k–$300k, with a quality-adjusted upward adjustment for its test and audit posture, and a downward adjustment for missing integrations. That intersection is the origin of the $75k–$200k headline.

---

## 5. The AI deflation factor (2026)

Cost and schedule for software production fell materially between 2024 and 2026. This report does not simply assert that; it prices it, and it records the counter-evidence.

### 5.1 Evidence of compression

| Finding | Source |
| --- | --- |
| **60–80% shorter overall timelines** and **30–50% better cost/delivery efficiency** on AI-first projects; team size down 30–80% | Phaedra Solutions, *AI-First Development Benchmark 2026* (45 projects, Jan 2025 – Jun 2026) |
| Project Delivery Rate improved **10–25%** (medians ~9–11 → **7–9 hours/FP**); delivery speed +10–30% | ISBSG, *Impact of AI on Productivity and Delivery Speed* (2026-02-05) |
| **31.8% reduction in PR cycle time** (150.5 h → 99.6 h, p=0.0018); code output **+60.1%** overall, +77% for juniors, across 300 engineers / 1 year | arXiv:2509.19708, *DeputyDev* (2025-09-24) |
| **67%** of US technology leaders say AI generates or significantly refactors **51–75%** of weekly code output | New Relic, *2026 State of AI Coding Report* (2026-06-10) |
| AI-first teams: MVP in 4–8 weeks at **$15k–$50k** vs. traditional 4–6 months at **$80k–$200k**; team 5–8 → 1–2 | Groovy Web, *AI-First vs Traditional Dev Teams* (2026-03-06) |
| SaaS WMS prices up **30–50% since 2023**, while custom build costs fell ~40% in 5 years and build time dropped 6–12 months → 8–14 weeks | Ekyon, *3PLs Building Custom WMS* (2026-04-25) |

### 5.2 Counter-evidence (recorded deliberately)

| Finding | Source |
| --- | --- |
| In mature open-source repos, early-2025 AI usage made experienced developers **19% slower**; a February 2026 follow-up estimated an 18% speed-up but METR calls the new data **unreliable and weak evidence** because 30–50% of developers withheld tasks they did not want to do without AI | METR (2025-07-10; 2026-02-24) |
| **74%** of leaders report ≥25% of AI code needs significant rework; **78%** report more incidents once shipped; **82%** had at least one AI-tied production failure in six months | New Relic, *2026 State of AI Coding Report* |
| AI gains concentrate in **pattern-heavy, well-specified work** (CRUD, standard UI, migrations); they shrink sharply for novel architecture and ambiguous requirements | ISBSG; Groovy Web (both caveats); Phaedra phase table (QA/rework is *negative if unmanaged*) |
| Quality/defect costs of AI-authored code are not yet visible in ISBSG delivery metrics | ISBSG (explicit limitation) |

### 5.3 How this report applies the factor

1. **Prices, not vibes.** Approach B is anchored to 2026 published price bands (§4), which *already* embed the market's AI adjustment — no further discount is applied.
2. **Schedule is observed, not assumed.** The 29-day delivery (§3.4) is a fact of this repository, so Approach A uses the actual effort envelope rather than a benchmarked estimate.
3. **Quality is paid for.** The counter-evidence in §5.2 is the reason Approach B is capped at $200k rather than pushed to the $250k+ tier: unmaintained or untested AI output trades price for liability, and P2's answer to that is its test and governance evidence, not its LOC.
4. **Where AI helped is recorded in §6.1**, line by line, so the deflation factor is auditable rather than rhetorical.

---

## 6. Approach A — AI-leveraged cost of production

### 6.1 Hours estimate (conventional sizing of the delivered scope)

| Layer | Basis | Low | High |
| --- | --- | --- | --- |
| Backend API, schemas, services, models (5,040 LOC) | 43 endpoints + Pydantic V2 contracts + domain services | 450 h | 600 h |
| Transactional database core (1,217 LOC DDL, 14 stored functions, 15 migrations) | Highest-density expertise layer; enforced by contract tests | 300 h | 450 h |
| Frontend (9,659 LOC: 6 screens, 21 components, 13 hooks, 9 services) | State-based navigation, 45 tests | 400 h | 550 h |
| QA (254 tests, `p2_test` isolation harness, fixtures, seed) | 19 backend files + 10 frontend files | 300 h | 400 h |
| SDD governance & documentation (6,561 LOC, 9 change packages, 11 agents) | Constitution, flow 0–13, ADRs, operational reports | 150 h | 250 h |
| **Total** | | **1,600 h** | **2,250 h** |

Cross-check: 1,600–2,250 h sits inside the **1,500–2,500 h** band that industry sources publish for a mid-complexity custom WMS, and inside Rorix's "3–6 engineers over 3–6 months" team shape (which implies roughly 1,400–2,600 person-hours once coordination overhead is netted out).

### 6.2 Cash cost actually incurred

| Component | Low | High |
| --- | --- | --- |
| Senior engineering labour, 1–1.5 FTE-months (LatAm fully-loaded, $7k–$10k/mo) | $7,000 | $15,000 |
| AI tooling and agent tokens (~$13/dev/day observed by Anthropic; 29-day window) | $400 | $1,200 |
| Infrastructure (dev/staging DB, hosting, CI) | $600 | $2,000 |
| Tooling, hardware amortization, overhead | $1,500 | $4,000 |
| Quality/review contingency | $2,500 | $7,800 |
| **Total production cost** | **$12,000** | **$30,000** |

### 6.3 Reading

Production cost is **~$12k–$30k**, i.e. the same work quoted at **$75k–$200k** in the market (Approach B). On midpoints that is a **≈6× spread** between what the asset cost to make and what it would cost to acquire. This is the defining economic property of AI-leveraged delivery in 2026: **value no longer tracks hours**.

It is also the reason Approach A must never be used as the asset's value — it is the seller's cost basis, not the buyer's price.

---

## 7. Approach B — Replacement / market value (headline)

### 7.1 Rate × effort matrix

| Delivery model | Rate band | × 1,600 h | × 2,250 h | Band |
| --- | --- | --- | --- | --- |
| Offshore / fully remote | $25 – $45 /h | $40,000 | $101,250 | **$40k – $101k** |
| Nearshore (LatAm / E. Europe) | $45 – $75 /h | $72,000 | $168,750 | **$72k – $169k** |
| Onshore (US / W. Europe) | $90 – $150 /h | $144,000 | $337,500 | **$144k – $338k** |

### 7.2 Market anchoring and adjustment

| Adjustment | Direction | Effect |
| --- | --- | --- |
| Raw nearshore cost-plus result | — | $72k – $169k |
| Quality premium: 254 tests, audit ledger, constitutionally-enforced DB contract, 6,561 LOC of governance | ↑ | +5–15% |
| Missing integration scope: no ERP, no carrier/marketplace, no barcode/RFID, no mobile, no multi-tenant | ↓ | −20–35% (the four drivers YuSMP and Rorix identify as the main cost escalators) |
| 2026 market prices already deflated by AI (§5.3) | ↓ | no further discount applied — bands are current |
| Clutch average for comparable projects ≈ $132,000; GoodFirms $30k–$100k | → | central tendency corroborates the midpoint |

### 7.3 Result

> **Replacement / market value: USD 75,000 – 200,000**
> Midpoint ≈ **USD 137,000**
> Illustrative FX conversion at 18 MXN/USD: **≈ $1.35M – $3.6M MXN** (indicative only; convert at the prevailing rate).

This is the number recommended for external use.

---

## 8. Approach C — Value in use (5-year, operator perspective)

What P2 is worth to the business that runs it, versus licensing a commercial WMS.

### 8.1 Annual economics

| Line item | Low | High | Source basis |
| --- | --- | --- | --- |
| SaaS WMS subscription avoided | $18,000 | $120,000 | Data Sensum: NetSuite ≈ **€18,240/yr** for 10 users; Ekyon: **$48k–$120k/yr** for a 3PL; Ekyon platform table: $18k–$120k/yr across ShipHero/Extensiv/Logiwa/Deposco |
| Per-user and API charges avoided | $0 | $40,000 | Ekyon hidden-cost analysis: per-user $100–$200/mo, API and connector fees |
| **Gross avoided cost** | **$18,000** | **$160,000** | |
| Less: maintenance of owned system (15–20% of a $75k–$125k build basis) | −$11,250 | −$25,000 | Rorix 15–25%; Stfalcon models 15% |
| Less: hosting & operations | −$4,000 | −$6,000 | Ekyon: $3,600–$6,000/yr |
| **Net annual saving** | **$5,000** | **$129,000** | |
| **Realistic band (10–20 users, single site)** | **$15,000** | **$60,000** | conservative operating case |

### 8.2 Five-year comparison

Published comparables for the same trade-off:

| Comparison | SaaS 5-yr | Custom 5-yr | Saving | Source |
| --- | --- | --- | --- | --- |
| 15-user warehouse | $352,992 | $113,000 | **$239,992** | Ekyon (2026-04-23) |
| Mid-size 3PL, 15 users | $476,198 | $120,800 | **$355,398** | Ekyon (2026-04-25) |
| 10-user warehouse | $183,153 | $42,600 | **$140,553** | Ekyon (2026-04-17) |
| SME custom (€75k–120k build) vs NetSuite | €91,200–96,200 | €131,000–232,000 | **custom is *more* expensive** | Data Sensum (2026-05-18) |
| 5 sites / 65 users, 3-year TCO | $470,166 | $273,500 | **$196,666** | Stfalcon (2026-07-14) |

The Data Sensum row is included because it is the honest counter-case: at **low user counts and modest subscription prices, buying beats building**, and P2's value in use depends on the operator actually paying more than ~$15k/yr for the alternative.

### 8.3 Result

Applying a risk discount for the fact that (a) not every avoided SaaS seat is real, (b) P2 still requires the §10.1 auth investment before it can displace a regulated platform, and (c) maintenance will drift upward:

> **Value in use: USD 50,000 – 200,000 over 5 years** (risk-adjusted)
> Unadjusted arithmetic range: $75k – $645k; Data Sensum-style counter-case: near zero or negative.

---

## 9. Approach D — Product / commercial value

If P2 were packaged and sold to comparable operators:

| Model | Price point | Basis |
| --- | --- | --- |
| Perpetual license, single site | **$60,000 – $120,000** | Rorix single-site $30k–64k (bare) → mid-level $64k–150k; discounted for missing integrations, uplifted for test/audit posture |
| Support & updates | **18% of license / year** | Industry maintenance norms 15–25% (Rorix, Incora, perpetual-license AMC) |
| SaaS opex alternative | **$1,500 – $3,000 / month** ($18k–$36k/yr) | Mid-market bands $1,500–$15,000/mo (Fynd); low end for a narrow single-tenant product |

> **Product value: USD 92,000 – 185,000** over a 3-year contract (license + 3 × 18% support).

**Gate on this figure:** it is conditional on closing README §10.1 (external IdP / OAuth2) and §10 scope gaps. Without them the product is not saleable to a third party, and this range falls to raw source-code sale value (typically a small fraction of the license figure).

---

## 10. Consolidated ranges

| Approach | Interpretation | Range (USD) | Confidence |
| --- | --- | --- | --- |
| **A — Cost of production** | What it cost to make (AI-leveraged) | **12,000 – 30,000** | High — measured, not estimated |
| **B — Replacement / market value** | What it would cost to acquire the same scope | **75,000 – 200,000** | Medium — modelled from published price bands |
| **C — Value in use** | 5-year economic benefit vs. buying SaaS | **50,000 – 200,000** | Medium-low — depends on a SaaS alternative being actually displaced |
| **D — Product value** | 3-year commercial contract if productized | **92,000 – 185,000** | Low — gated on auth and scope gaps |

**Headline for external use: USD 75,000 – 200,000 (Approach B).**
Illustrative conversion at 18 MXN/USD: **≈ $1,350,000 – $3,600,000 MXN.**

Leverage implied: market value is **≈ 4×–7× production cost** on midpoints — the measurable economic effect of AI-deflated delivery on a spec-driven, tested codebase.

---

## 11. Assumptions and sensitivity

### 11.1 Assumptions (each one is a lever on the number)

1. **Scope as delivered:** single site, single tenant, 43 endpoints, no ERP/carrier/hardware/mobile integration.
2. **Effort band 1,600–2,250 h** is conventional sizing, not a time-tracked measurement.
3. **Rate bands** are 2026 published market rates for the stated delivery model; actual quotes vary ±30%.
4. **FX 18 MXN/USD** is illustrative only.
5. **One senior developer with AI agents** is the relevant production model — a 4-person agency would incur coordination overhead this build did not pay.
6. **Quality gates pass as measured** (209/45/mypy-clean); a codebase failing them would lose the §7.2 quality premium.
7. **Maintenance 15–20%/yr** of a $75k–$125k build basis; higher tiers raise Approach C's costs proportionally.
8. **Value in use assumes** an alternative WMS subscription would actually be bought; if the operator would simply run spreadsheets, Approach C collapses toward zero.
9. **Approach D assumes** the product is licensed externally, which requires §10.1 and §10 scope items first.
10. **Market bands are vendor-published** and may be strategically positioned; Clutch/GoodFirms aggregates are used as a cross-check.

### 11.2 Sensitivity — Approach B (rate × effort)

| | 1,600 h | 1,925 h | 2,250 h |
| --- | --- | --- | --- |
| **$45/h** | $72,000 | $86,625 | $101,250 |
| **$75/h** | $120,000 | $144,375 | $168,750 |
| **$110/h** | $176,000 | $211,750 | $247,500 |

Three variables move the answer most, in order:

1. **Integration scope** (ERP / hardware / mobile) — can double or halve the number; this is the largest single lever.
2. **Delivery model and rate** — offshore vs. onshore is a ~4× spread on the same hours.
3. **Whether the QA and governance evidence is valued by the buyer** — the difference between "code" ($40k–$100k) and "verified system" ($75k–$200k).

### 11.3 What would make these figures wrong

- Evidence that P2 duplicates an existing internal system (zero marginal value).
- Discovery of a required integration not visible in the repository (raises value).
- Failure to close §10.1 before any external use (caps value at internal-use levels).
- A material regression in the QA gates (removes the quality premium).

---

## 12. Sources

All URLs accessed **2026-09-30**.

**Market pricing (build):**

1. Rorix Technologies — *How to Build a Custom Warehouse Management System (2026)*, 2026-08-29. <https://www.rorixtech.com/blogs/warehouse/how-to-build-a-custom-warehouse-management-system>
2. Rorix Technologies — *How to Evaluate a Warehouse Software Development Company* (published cost bands; bands published 2026-09-01, reviewed 2026-09-10), 2026-07-26. <https://www.rorixtech.com/blogs/warehouse/warehouse-management-software-development-companies>
3. Rorix Technologies — *Custom WMS vs Off-the-Shelf WMS: When to Build*, reviewed 2026-09-10. <https://www.rorixtech.com/compare/custom-wms-vs-off-the-shelf-wms>
4. Stfalcon — *WMS Software Cost: SaaS Subscription vs. Custom Build Comparison*, 2026-07-14. <https://stfalcon.com/en/blog/post/wms-software-cost>
5. YuSMP Group — *Warehouse Management System Development: 2026 Guide*, 2026-07-18. <https://yusmpgroup.com/blog/wms-development>
6. OrderPilots — *Best WMS Implementation Cost Guide: 2026 Pricing Strategy*, 2026-08-25. <https://orderpilots.com/wms-implementation-cost-guide/>

**Market pricing (buy / TCO):**

7. Ekyon — *3PLs Building Custom WMS: The $355K Case*, 2026-04-25. <https://ekyon.io/blog/3pls-building-custom-warehouse-management-software>
8. Ekyon — *Custom WMS vs SaaS: 5-Year Cost Race*, 2026-04-23. <https://ekyon.io/blog/custom-wms-vs-saas-comparison>
9. Ekyon — *WMS Software Pricing & Cost Guide 2026*, 2026-04-17. <https://ekyon.io/blog/warehouse-software-pricing-guide-2026>
10. Data Sensum — *WMS Cost for SMEs: Custom Dev vs SaaS vs Low-Code*, 2026-05-18. <https://www.datasensum.com/wms-cost-comparison>

**AI productivity and cost deflation:**

11. Phaedra Solutions — *AI-First Development Benchmark 2026*, 2026-09-07. <https://www.phaedrasolutions.com/blog/ai-first-software-development-benchmark>
12. ISBSG — *Impact of AI on Productivity and Delivery Speed*, 2026-02-05. <https://www.isbsg.org/2026/02/05/impact-of-ai-on-productivity-and-delivery-speed/> (paper: <https://www.isbsg.org/wp-content/uploads/2026/02/Short-Paper-2026-02-Impact-of-AI-Assisted-Development-on-Productivity-and-Delivery-Speed.pdf>)
13. METR — *Measuring the Impact of Early-2025 AI on Experienced Open-Source Developers*, 2025-07-10. <https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/>
14. METR — *We are Changing our Developer Productivity Experiment Design* (follow-up results), 2026-02-24. <https://metr.org/blog/2026-02-24-uplift-update/>
15. New Relic — *Introducing the State of AI Coding 2026*, 2026-06-10. <https://newrelic.com/blog/ai/state-of-ai-coding-2026> (press release: <https://newrelic.com/press-release/20260610>)
16. Edubilli, A. et al. — *Intuition to Evidence: Measuring AI's True Impact on Developer Productivity*, arXiv:2509.19708, 2025-09-24. <https://arxiv.org/abs/2509.19708>
17. Groovy Web — *AI-First vs Traditional Dev Teams: Cost & Velocity Comparison 2026*, 2026-03-06. <https://www.groovyweb.co/blog/ai-first-vs-traditional-dev-teams-cost-velocity-2026>
18. Fynd — *WMS cost in 2026: Real pricing, hidden fees & ROI*, 2025-06-09. <https://www.fynd.com/blog/warehouse-management-system-cost-wms-pricing-hidden-costs-and-roi-fynd>
19. Incora Software — *Warehouse Management Software Cost in 2026: Pricing Guide*, 2026-04-24. <https://incora.software/insights/warehouse-management-system-cost>

**Repository evidence:** this repository, measured 2026-09-30 — see §3 and README §4/§8/§10.

---

## 13. Change control

- This file is the **single source of truth** for P2's economic figures. The summary table in `README.md` §11 must be updated whenever this file's §10 ranges change.
- Re-run §3's verification commands after any material change in scope, and re-check market bands at least annually (they are the most volatile input).
