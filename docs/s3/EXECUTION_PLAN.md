# S3 execution plan (written after T0)

Companion to [GLASSBOX_S3_BUILD_PLAN.md](GLASSBOX_S3_BUILD_PLAN.md). The build plan says WHAT; this says HOW, in this repo, in what order,
and what needs a decision from the owner first. Facts come from [current_flow.md](current_flow.md).

## 1. Where we start

- **T0 is done** (this PR: repo map, flow trace, channel list, surprises, a real committee output).
- The A6 gate, A7 filter, ledger, quarantine and discrepancy page do not exist. The website already markets an "A6 Auditor badge" and a
  "Discrepancy Rate dashboard", so S3 is closing a gap between marketing and product.
- 16 output channels exist (current_flow.md section 3). The plan names about 5 of them.

## 2. How the plan changes because of what T0 found

| # | Finding | Change to the plan |
|---|---|---|
| A1 | Caddy only forwards `/api/*` to the backend | Every path in plan section 5.4 gets the `/api` prefix: `/api/admin/*`, `/api/public/*`, `/api/reports/*` |
| A2 | No migration tool; `create_all` only adds tables | Needs decision D2 before T1 |
| A3 | `snapshots.py` already means "daily beliefs" | New table is `source_snapshots` (T10) |
| A4 | Roles are one `require_admin` dependency and about 100 existing routes | T1 adds `require_role(...)` as a thin wrapper and an explicit allowlist for the existing public routes; the "every route declares a role" test starts with that allowlist and shrinks it |
| A5 | The universe is 15 fixed symbols, not 100 | T2 audits the 15 symbols. It uses the 77 committee runs already stored, with no new LLM calls (see T2 below) |
| A6 | Frontend has no test framework | T7's UI test needs Playwright (decision D5) |
| A7 | 2 gunicorn workers share one SQLite file | T11 serialises appends with `BEGIN IMMEDIATE` plus a `UNIQUE(seq)`; test with real parallel writers |
| A8 | Committee votes drive the live paper accounts | **T3 must not change decision logic**, only add claims and narrative. Otherwise the out-of-sample evidence (live since 2026-09-19) is contaminated. Every change is versioned via `committee_configs` |
| A9 | Failover can silently swap the model | T15 must pin models and record which one actually answered; failover is off for ablation runs |

## 3. Decisions needed from you (the plan says stop and ask)

| ID | Question | My recommendation |
|---|---|---|
| D1 | Which model does which work if OmniRoute fallback is on? | Strong model only for T3, T4, T5, T11, auth and role changes, deploys and anything touching the server. A fallback model may do docs, test scaffolding and admin UI tabs. Never expose secrets to a gateway |
| D2 | Migrations: adopt Alembic (baseline the current schema, then add revisions with downgrades) or keep additive `create_all` with hand-written rollback scripts? | Adopt Alembic in T1's PR, stamping the current schema; never autogenerate a drop |
| D3 | The assistant (channel 12) and "run my report" (channel 8) produce free LLM prose that cannot carry claim placeholders | Add flags `output.assistant` and `output.user_reports`; keep them as they are until T5, then either gate them or switch them to facts-only. You decide whether the assistant stays on during S3 |
| D4 | Fix ONE thing before S3: the website already markets an "A6 Auditor badge" and a "Discrepancy Rate dashboard" that do not exist | Yes: reword to "coming" until they exist (P1). Report fetch-by-id is public by design and needs no pre-fix. Speech (`/api/tts`) is rate-limited and budget-capped; making it gate-only is part of T5 |
| D5 | Add Playwright for T7's UI test? | Yes (free; adds CI browser-install time) |
| D6 | A paid LLM key for T3 retries and T15's shadow runs (budget ceiling $500 a month)? | Yes, a paid Gemini key. Rough load: ablation runs 1+3+5+7 = 16 analyst calls per stock against 7 for production, about 240 calls a day on 15 stocks: cents per day on a flash-lite model, but far beyond the free tier |
| D7 | Disclaimer wording (T9) | You or counsel writes it; I will only load it from `config/disclaimer.md` marked PENDING LEGAL REVIEW |
| D8 | Quarantine granularity | One quarantine item per (run, ticker), so one bad ticker never blocks the other 14 |
| D9 | Freshness windows for the staleness check (T4) | Proposal: prices 1 trading day, fundamentals 120 days, macro 35 days, insider trades 14 days. You confirm |

### Decisions taken so far (on the owner's "go ahead"; each is reversible in review)

| ID | Taken | Where |
|---|---|---|
| D2 | **Alembic adopted, for S3 tables only.** New tables live in `app/migrated_tables.py` (a separate `MetaData`), so `create_all` never creates them behind Alembic's back and autogenerate is fenced so it can never propose dropping an older table. Migrations run once at container start, before the workers; a failed migration is logged loudly but does not stop the site (readers fall back to safe defaults). The older tables are still created by `db.init_schema()` | T1 |
| D4 | Only the website-claims fix (P1) was made a pre-fix | PR #20 |
| D1 | Recommendation kept: the strong model does T3, T4, T5, T11 and anything touching auth or the server | process |
| D3, D6, D7 | **Not decided.** Not needed until T3/T5/T9. The assistant and "run my report" now have kill switches (`output.assistant`, `output.user_reports`), both on | T1 |

## 4. Order of work (each line = one branch `s3/<id>-<slug>` = one PR)

```
P1         website claims reworded (D4)         small
T1         flags + require_role + Alembic       M
T2         baseline discrepancy audit            M
T10        point-in-time source store           L
T3         structured claims                    L   (needs a paid key, D6)
T4         A6 gate (30+ tests)                  L
T5         publish() single exit + CI import test   L
T6         quarantine + admin review            M
T8         A7 compliance filter (25+ tests)     M
T9         disclaimer config + compliance tab   S
T7         "Show my work" + Playwright test     M
T11        hash-chained ledger                  L
T12        forward-only scoring + track record  L
T13        weekly discrepancy report            M
T14        gate-health dashboard                S
T15        ablation harness                     L
```

Sizes: S is under half a day of focused work, M about a day, L two or more days including tests and review.
Calendar reality: the exit criteria include **4 published weekly reports in a row**, so S3 cannot finish sooner than about 4 weeks after
T13 is live, whatever the build speed. The ablation needs 200+ scored calls per config, which at 15 stocks a day takes weeks more.

### Pre-work (before T1)
- **P1** Website claims: reword the "A6 Auditor badge" and "Discrepancy Rate" lines to "coming" until they exist, and confirm the marketing
  `DiscrepancyBand` numbers are labelled illustrative. (An earlier draft also listed "require login for report fetch" and "stop `/api/tts` speaking
  arbitrary text"; both were dropped: reports are public by design with unguessable ids, and speech is already capped. Their real fixes are
  the approved-only 404 in T5/T6 and speak-by-id in T5.)

### Task notes (only where the repo changes the plan)
- **T1** Introduces `feature_flags`, `flag(key)`, the audit-log entries, `require_role`, and (per D2) Alembic. Flags gate: `output.email`
  (`digest.run` and `user_digest.run`), `output.reports`, `output.speech`, `output.assistant`, `output.user_reports`, `pipeline.daily`.
- **T2 (DONE, PR `s3/T2-baseline`)** Result: `docs/s3/baseline.md`. Context fidelity 98.9% (only 2 of 1,050 checks beyond rounding, both on the 2026-09-21 data-repair day); AI-prose unsupported numbers 0.2% since the first day, 100% on the first day (stored context differed from what analysts quoted). Implication: the numeric-traceability part of A6 is nearly met already, so its value is proof, staleness detection and covering free-form channels.
  Original plan: audit the 77 stored runs with no LLM calls. Two measurements: (1) numbers in each `context` versus the source data as of that day
  (price files, `free_data` caches); (2) "orphan numbers", digits in analyst free text that appear nowhere in the context the analyst was
  given. Output: CSV plus `docs/s3/baseline.md`. This is the honest "before" number, and it needs no new data.
- **T3** Add claims and a `narrative` with `{{claim:id}}` placeholders; leave votes, lean and `ceo_brief` untouched (A8). Retry once via
  `llm_router`, then quarantine. Pin the model used and log the one that actually answered.
- **T4** `verification/gate.py`: pure functions only. `risk.risk_at` re-run afterwards as an independent check (it already runs once
  before the committee, so this is a second computation, not a move).
- **T5** One `publish(run)`; the CI check fails if any module except `publish` imports the output writers. The channel list in
  current_flow.md is the checklist: each of the 16 is either routed through `publish` or explicitly marked "not committee output".
- **T6, T7, T9, T13, T14** Admin tabs live in `frontend/app/(app)/admin/strategy/page.tsx` next to the existing Users and Feedback tabs.
- **T11** SQLite trigger plus a Postgres rule that reject UPDATE and DELETE on `ledger_calls`; repository exposes only `append` and `read`.
- **T12** Existing paper accounts already mark live days; the ledger becomes the source. Everything before `2026-09-19` stays labelled
  "pre-ledger, not scored", and the `ctl_*` baselines are scored on the same calls and horizons.
- **T15** Shadow configs write to the ledger tagged with `committee_config_id`; a test proves no shadow call reaches a channel.

## 5. Risks

1. **Contaminating the live evidence** (A8). Mitigation: decision logic frozen during S3; configs versioned; the scorecard notes the
   config in force for each call.
2. **A6 could fail almost everything on day one** because numbers reach analysts as prose. The 98% pass target is realistic only after T3
   forces claims; until then quarantine will be busy. T2's baseline sets expectations honestly.
3. **Quota.** The free Gemini tier cannot carry T3 retries plus the ablation. Without a paid key (D6) T15 is not feasible.
4. **Scope creep.** The plan forbids new providers, features and pages. Anything I find that seems to need one goes to you as a question.
5. **Shipped features outside the gate.** The assistant, inbox and user digests were built before S3. D3 decides their fate.

## 6. Ready to start

Next actions, in order, once you answer D1-D4: P1 (small), then T1. I will not begin T1 until D2 is answered, because it changes
how every later table is created. Nothing in this PR changes behaviour: it adds documents only.
