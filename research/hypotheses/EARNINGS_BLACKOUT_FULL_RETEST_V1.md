# EARNINGS_BLACKOUT_FULL_RETEST_V1

Status: **PREREGISTERED ADAPTIVE ROBUSTNESS — NO UNTOUCHED HOLDOUT**

Production effect: **NONE**

## Hypothesis

The user treats an earnings announcement from the signal date through ten calendar days later, inclusive, as a non-negotiable no-entry condition. Every historical comparison should therefore begin from the same earnings-eligible signal universe before filters, trade simulation, ordering, or portfolio capacity are applied.

## Frozen scope

Recalculate all previously tested settings that did not already enforce the blackout:

- MODEL_0 baseline plus seven filter ablations: 8 settings.
- Five initial stops by four exits: 20 settings.
- Nine standalone portfolio policies: 9 settings.
- Five stops by four exits by nine portfolio policies: 180 settings.
- Six stops by seven exits by four exposure policies: 168 settings.

Total: 385 retested settings. Existing earnings-blackout V1 and staircase V2 results are compliant references rather than new independent runs.

The source experiment periods, entry timing, slippage, costs, stop/target ambiguity policy, candidate order, portfolio rules, metrics, and gates remain unchanged. Any source result dated 2024 or 2025 is labelled reused/contaminated robustness for this revised specification.

## Evidence limits

The price archive uses a current universe and has survivorship bias. The earnings archive was retrieved retrospectively and does not prove which scheduled date was known at each signal. Every historical period has already been inspected. This experiment may correct practical comparability and expose sensitivity to the user's actual rule, but it cannot create independent validation, restore an untouched holdout, validate a filter, or approve production.
