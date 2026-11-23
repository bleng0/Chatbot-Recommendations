# Constraints — POME Phase 1

Last reviewed: 2026-11-23 · Status: DRAFT, awaiting owner approval (frozen on approval)

These numbers are committed before any scoring. They do not get weakened to make a
config pass or a test go green. Any change needs the owner's explicit approval in chat
and lands in its own commit, never alongside the code that was failing.

---

## A. Decision gates (product bar, profile `banking_mvp`)

Proof-of-concept scope (owner decision 2026-11-22): G12 (data processed in India) and G13
(provider retention ≤ 30 days) are dropped from `banking_mvp`. The engine still supports them
as optional gates for a stricter profile; the app reports region and retention as information.

A config is `eligible` only if every gate passes. A gate whose evidence is missing is
`unverified`, never `pass`. Evidence marked `modeled` can pass a gate but the config is
flagged `eligible (modeled)` and the UI says so.
What-if profiles may omit gates or move a gate's threshold, for exploration only (owner
decision 2026-11-23); the recommendation always uses banking_mvp as written and its hash never
changes. Moved thresholds live only in the app session and never edit this file or the profile.
A config that passes only because a threshold was moved looser than recommended is labelled
"Not recommended" with the gate and the recommended value; the what-if suggestion is the
cheapest config that stays valid at the recommended thresholds, and a "Not recommended" one only
when nothing else passes. The app says "recommended" (not "official") for the banking_mvp values.
On screen (owner decision 2026-11-23) G10 and G11 are sidebar settings and the remaining gates
are numbered G1-G10 without gaps (G14 shows as G10); ids in this file and the code are unchanged.
Gap fill (owner decision 2026-11-23, replaces D2): a gate key POME did not measure is filled
with a vendor-doc value or a `modeled` proxy (formula and inputs in `pome/registry/gapfill.yaml`),
never `measured`. A config that passes on such evidence is only ever `eligible (modeled)`.

| # | Gate | Threshold | Evidence | Why this number |
|---|------|-----------|----------|-----------------|
| G1 | Intent macro-F1, BANKING77 test sample (300, ~4/intent) | ≥ 0.80 | measured, else modeled proxy | Owner default; ~4/intent keeps cost low while covering all 77 labels |
| G2 | OOS recall, CLINC150 (100 OOS + 150 in-scope), OOS = positive class | ≥ 0.85 | measured, else modeled proxy | Missing an unknown query is the costlier error in banking |
| G3 | OOS precision, same sample | ≥ 0.80 | measured, else modeled proxy | Bounds false rejections of real queries |
| G4 | FAQ answer correctness, answerable items, per language | ≥ 0.80 | measured, else modeled proxy | Owner default |
| G5 | FAQ unanswerable correctly declined, per language | ≥ 0.80 | measured, else modeled proxy | Owner default |
| G6 | Language gap: Hindi vs English on every quality metric with both languages (MASSIVE hi-IN vs en-US macro-F1; FAQ G4, G5) | en − hi ≤ 0.10 | measured, else modeled proxy | Owner default (10 points absolute) |
| G7 | Language gap: Hinglish vs English on every quality metric with Hinglish data (FAQ G4, G5 only; no Hinglish intent benchmark exists) | en − hinglish ≤ 0.10 | measured, else modeled proxy | Owner default; scope per SPEC A3 |
| G8 | p95 latency at the concurrency level that sustains peak load | ≤ 20000 ms | measured, else modeled (published medians / decode model) | Owner decision 2026-11-23 (was 3000 ms) |
| G9 | Sustainable throughput (p95 ≤ G8 and error rate ≤ G10) | ≥ 5 req/s | measured / modeled | Owner decision 2026-11-23: profile peak is 5 req/s (was 8) |
| G10 | Error rate after retries, at that concurrency | ≤ 1.0% by default; the user sets their own max error rate in the app sidebar | measured / modeled | Owner decision 2026-11-23: a user input, not a gate column |
| G11 | Monthly cost at the app's ticket volume | ≤ $1,500 by default (₹1,39,195); the user sets their own max monthly spend in the app sidebar | measured tokens × vendor-doc prices; self-host modeled | Owner decision 2026-11-23: budget is a user input, shown as a cost column, not a gate column |
| G14 | Licence/terms permit commercial use | required | vendor-doc | Owner default |

Gate rules:
- Quality gates (G1–G7) compare the **point estimate of 1 run** (Phase 1 prototype, owner decision 2026-11-22: simplify, no multi-hour runs; was 3 runs). Bootstrap 95%
  CIs are shown next to them but don't decide pass/fail. A CI that crosses the threshold
  is flagged "marginal".
- G8–G10: if no load test was run (free tier cannot load-test), the gate is `not tested`:
  shown in the app, does not block selection. At equal cost a config with serving evidence
  ranks first. Since the gap fill (2026-11-23) every config has a published or modeled serving
  value, so `not tested` does not appear for `banking_mvp` today. Serving evidence that is present but fails or is invalid still counts.
- Minimum sample: a quality metric needs at least 15 scored items (successful calls) to be
  used; below that it stays unverified (owner decision 2026-11-22, was 30).
- G8–G10: pass if at least one tested concurrency level reaches ≥ 5 req/s with p95 ≤ 20000 ms
  and errors ≤ 1%.
- G11 ticket definition: SPEC A4.
- Not legal certification: G14 records documented evidence only.

## B. Spend and usage limits

| Limit | Value | Checked by |
|-------|-------|-----------|
| Gemini API spend, all eval + load runs, all keys combined | ≤ $20.00 total (raised from $5.00 by owner, 2026-11-22) | `pome/providers/spend.py` ledger; run refuses to start if estimate + spent > cap; hard-stops when the ledger reaches cap |
| Pre-run approval | estimate shown from dated prices, owner says yes | executor |
| Response cache | every API response cached by (config_id, prompt_hash, run_idx); rerun = $0 | `tests/test_cache.py` |
| API tier, all eval + load runs | free tier (owner decision 2026-11-22: all keys are free-tier; use free for everything). Public benchmark data only, because free-tier content may be used to improve Google products. Ledger records $0 charged, tokens and list prices kept | `spend.py` tier field, `--tier free` |
| Claude weekly usage | ≤ 55% working, 60% hard | owner reports `/usage` each slice |

## C. Engineering bar

### Floor (always enforced)
- No new suppressions: `# noqa`, `# type: ignore`, `pytest.mark.skip`/`xfail` without a reason in the commit message
- No unimplemented stubs: `raise NotImplementedError`, bare `except: pass`, `TODO` in place of code
- No skipped/deleted tests or removed assertions to get green
- No secrets in source or logs; key pool logs the key index only
- This file does not get weakened to make a change pass

### Enforced with numbers

| Dimension | Rule | Checked by | Runs at |
|-----------|------|-----------|---------|
| Tests | 0 failures | `uv run pytest -q` | every slice end |
| Lint | 0 errors | `uv run ruff check .` | every slice end |
| Coverage, changed lines in `pome/selection`, `pome/cost`, `pome/eval`, `pome/providers` | ≥ 80% | `uv run pytest --cov=pome --cov-report=lcov` + git diff | slice end |
| `select()` purity | no I/O, randomness or clock imports in `pome/selection/` | `tests/test_select_purity.py` (AST import scan) | every test run |
| Determinism | same snapshot + profile → identical decision SHA256, twice | `tests/test_determinism.py` + live check at slice end | every slice end |
| Provenance | every evidence value has value, unit, provenance ∈ {measured, vendor-doc, modeled}, source, retrieved_at | pydantic schema + `tests/test_schema.py` | every test run |
| Secrets (external) | 0 findings | `gitleaks git . --redact --no-banner` (commit history; owner ran it 2026-11-23, clean; 15 verified false positives on config IDs listed by fingerprint in `.gitleaksignore`) | before every push |
| Gate thresholds in `profiles/banking_mvp.yaml` equal section A | exact match | `tests/test_constraints_sync.py` | every test run |

## D. Measured, not yet enforced
None yet. Filled after slice 6/7 runs (e.g. tokens/ticket, cache hit rate).

## E. Exceptions
None.
