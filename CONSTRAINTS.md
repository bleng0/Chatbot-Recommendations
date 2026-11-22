# Constraints — POME Phase 1

Last reviewed: 2026-11-22 · Status: DRAFT, awaiting owner approval (frozen on approval)

These numbers are committed before any scoring. They do not get weakened to make a
config pass or a test go green. Any change needs the owner's explicit approval in chat
and lands in its own commit, never alongside the code that was failing.

---

## A. Decision gates (product bar, profile `banking_mvp`)

A config is `eligible` only if every gate passes. A gate whose evidence is missing is
`unverified`, never `pass`. Evidence marked `modeled` can pass a gate but the config is
flagged `eligible (modeled)` and the UI says so.

| # | Gate | Threshold | Evidence | Why this number |
|---|------|-----------|----------|-----------------|
| G1 | Intent macro-F1, BANKING77 test sample (300, ~4/intent) | ≥ 0.80 | measured | Owner default; ~4/intent keeps cost low while covering all 77 labels |
| G2 | OOS recall, CLINC150 (100 OOS + 150 in-scope), OOS = positive class | ≥ 0.85 | measured | Missing an unknown query is the costlier error in banking |
| G3 | OOS precision, same sample | ≥ 0.80 | measured | Bounds false rejections of real queries |
| G4 | FAQ answer correctness, answerable items, per language | ≥ 0.80 | measured | Owner default |
| G5 | FAQ unanswerable correctly declined, per language | ≥ 0.80 | measured | Owner default |
| G6 | Language gap: Hindi vs English on every quality metric with both languages (MASSIVE hi-IN vs en-US macro-F1; FAQ G4, G5) | en − hi ≤ 0.10 | measured | Owner default (10 points absolute) |
| G7 | Language gap: Hinglish vs English on every quality metric with Hinglish data (FAQ G4, G5 only; no Hinglish intent benchmark exists) | en − hinglish ≤ 0.10 | measured | Owner default; scope per SPEC A3 |
| G8 | p95 latency at the concurrency level that sustains peak load | ≤ 3000 ms | measured (API) / modeled (self-host) | Owner default |
| G9 | Sustainable throughput (p95 ≤ G8 and error rate ≤ G10) | ≥ 8 req/s | measured / modeled | Profile peak |
| G10 | Error rate after retries, at that concurrency | ≤ 1.0% | measured / modeled | Default: errors above 1% at peak are visible to customers |
| G11 | Monthly cost at 100,000 tickets/month, measured avg tokens | ≤ $1,500 | measured tokens × vendor-doc prices; self-host modeled | Owner default |
| G12 | Data processed in India (documented regional ML-processing commitment) | required | vendor-doc | Owner default; no document = unverified |
| G13 | Provider retention of prompts/outputs | ≤ 30 days | vendor-doc | Owner default |
| G14 | Licence/terms permit commercial use | required | vendor-doc | Owner default |

Gate rules:
- Quality gates (G1–G7) compare the **mean point estimate over 3 runs**. Bootstrap 95%
  CIs are shown next to them but don't decide pass/fail. A CI that crosses the threshold
  is flagged "marginal".
- G8–G10: pass if at least one tested concurrency level reaches ≥ 8 req/s with p95 ≤ 3000 ms
  and errors ≤ 1%.
- G11 ticket definition: SPEC A4.
- Not legal certification: G12–G14 record documented evidence only.

## B. Spend and usage limits

| Limit | Value | Checked by |
|-------|-------|-----------|
| Gemini API spend, all eval + load runs, all keys combined | ≤ $5.00 total | `pome/providers/spend.py` ledger; run refuses to start if estimate + spent > cap; hard-stops when the ledger reaches cap |
| Pre-run approval | estimate shown from dated prices, owner says yes | executor |
| Response cache | every API response cached by (config_id, prompt_hash, run_idx); rerun = $0 | `tests/test_cache.py` |
| Load tests | paid-tier key only, public benchmark data only | key-pool tier flag |
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
| Secrets (external) | 0 findings | `gitleaks dir . --redact --no-banner` | before every commit |
| Gate thresholds in `profiles/banking_mvp.yaml` equal section A | exact match | `tests/test_constraints_sync.py` | every test run |

## D. Measured, not yet enforced
None yet. Filled after slice 6/7 runs (e.g. tokens/ticket, cache hit rate).

## E. Exceptions
None.
