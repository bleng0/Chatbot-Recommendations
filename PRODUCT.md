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
Every value is SELF-TESTED (a recorded run), published by a vendor or study, or MODELED from a
stated formula, and the screen says which. A gate with missing evidence is "unverified", never "pass".

## Operating Context
Streamlit app (pome/app/home.py) that replays recorded results from runs/records. Shown live in
a demo and opened by reviewers on laptops. Gossamer light theme only (owner, 2026-11-23); costs
shown in INR at the RBI reference rate noted in the footer.

## Capabilities and Constraints
- Replay only: the UI never calls an LLM API, even when a key is present (owner, 2026-11-23).
- Tweak mode (owner, 2026-11-23): reviewers switch gates off in the sidebar, or move a gate's
  threshold with the vertical slider above its column in the Gates table, to see a what-if
  result. The recommendation always uses banking_mvp unchanged and stays on top. A config that
  passes only because a threshold was loosened is labelled "Not recommended".
- Wording (owner, 2026-11-23): the screen says "recommended", never "official"; "self-tested",
  never the project name as tester; gates are numbered G1-G10 on screen with a short name each
  (Intent, Out-of-scope, No over-refusal, FAQ accuracy, FAQ decline, Hindi gap, Hinglish gap,
  Latency, Capacity, Licence); error limit and max monthly spend are sidebar settings.
- Provenance rules in CLAUDE.md section 2 are binding: a badge next to every number, no
  invented data.

## Evidence on Hand
runs/records (self-tested eval runs), pome/registry/configs.yaml (20 configs, published sources
with retrieval dates), pome/registry/gapfill.yaml (proxies and formulas for every gate key that
was not self-tested, so every gate has a value; none is labelled self-tested unless a run exists).
No load tests were run: serving figures are published or modeled.

## Product Principles
1. The answer comes first: the question names the model and the hosting plan, and the answer
   box fills exactly those two slots, then the monthly cost.
2. Provenance is visible, never implied.
3. Missing evidence is shown as missing.
4. Exploration never changes the recommendation.

## Accessibility & Inclusion
WCAG 2.1 AA contrast for text in both themes; status never by colour alone (icon + word);
motion reduced under prefers-reduced-motion.
