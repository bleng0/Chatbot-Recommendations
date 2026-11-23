# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
A reviewer or evaluation panel judging the POME Phase 1 prototype. They have a few minutes per
screen and need to see the answer, why it holds, and where every number came from.

## Product Purpose
POME picks the lowest-monthly-cost model and hosting option for a bank's customer-care bot that
passes every quality, serving, cost and licence gate in CONSTRAINTS.md (profile banking_mvp).
Success: a reviewer can trust the decision because each number shows its provenance and the
same inputs always give the same decision hash.

## Positioning
Every value is MEASURED by POME, published by a vendor or study, or MODELED from a stated
formula, and the screen says which. A gate with missing evidence is "unverified", never "pass".

## Operating Context
Streamlit app (pome/app/home.py) that replays recorded results from runs/records. Shown live in
a demo and opened by reviewers on laptops; dark and light themes follow the system setting.

## Capabilities and Constraints
- Replay only: the UI never calls an LLM API, even when a key is present (owner, 2026-11-23).
- Tweak mode (owner, 2026-11-23): reviewers switch gates off to see a what-if result. The
  official decision always uses banking_mvp unchanged and stays on top; thresholds are never
  edited.
- Provenance rules in CLAUDE.md section 2 are binding: a badge next to every number, no
  invented data.

## Evidence on Hand
runs/records (measured eval runs), pome/registry/configs.yaml (20 configs, published sources
with retrieval dates). No load tests were run: G8-G10 show "not tested".

## Product Principles
1. The official answer comes first, in one sentence.
2. Provenance is visible, never implied.
3. Missing evidence is shown as missing.
4. Exploration never changes the official decision.

## Accessibility & Inclusion
WCAG 2.1 AA contrast for text in both themes; status never by colour alone (icon + word);
motion reduced under prefers-reduced-motion.
