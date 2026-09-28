# PORTFOLIO_RANKING_PHASE_A_V1

## Hypothesis

When canonical candidate eligibility and every non-ranking condition are held
fixed, continuous point-in-time Recent RS, industry strength, pivot/supply
quality, and volume quality may allocate scarce portfolio heat differently from
production Final Score. This is a candidate-order hypothesis, not a new entry,
stop, exit, market-regime, or exposure rule.

## Frozen comparison

The baseline is production Final Score descending with ticker ascending as the
business-key tie-break. The controls are a SHA-256 deterministic-random order,
the four individual factors, an exact 25% per-factor percentile composite, and
four leave-one-factor-out composites with exact one-third weights. Missing
factor values and non-finite values (`+inf` and `-inf`) remain missing in the
raw audit and receive percentile zero so they rank last. No threshold or weight
search is permitted.

The price/volume formulas are also frozen before outcomes: pivot/supply quality
is `10 - pivot_supply_days_10d`, where the supply count uses only bars through
the as-of date near the causal 126-session pivot; volume quality is the causal
50-session up/down-volume ratio. Recent RS and industry strength reuse the
existing causal research feature builders. Current classifications are not
historical classifications and must retain their explicit bias label.

Eligibility is computed and frozen before rankings. Risk per trade, total heat,
maximum positions, concentration, market/regime constraints, execution, entry,
stop, exit, costs, and outcome handling must be supplied once and reused without
change by every arm. Accepted positions consume heat until their effective exit;
capacity-blocked candidates are retained in the audit as unselected.
Production candidate-list concentration is reapplied after each arm establishes
its own order: normally one candidate per industry, one additional candidate for
a high-conviction industry score of at least 90, and at most five candidates per
sector. It is not precomputed with production ordering and folded into frozen
eligibility.

## Evidence plan

Evaluate only on appropriately frozen point-in-time data. Preserve one row per
as-of date and ticker, raw factor values, percentiles, score, rank, selection,
block reason, and heat before/after. Report every arm using the preregistered
portfolio metrics in the experiment file plus ticker-cluster uncertainty. Do
not choose a champion automatically.

The formal development window is 2026-09-21 through 2027-09-17, with outcomes
observed through 2027-11-19. Validation is 2027-11-22 through 2028-05-19, with
outcomes observed through 2028-07-21. The untouched holdout is 2028-07-24
through 2029-01-19, with outcomes observed through 2029-03-23; Phase A must not
access it. An exit after a stage observation cutoff is censored to open at the
cutoff: realised R, MFE, MAE, and holding duration are cleared, while the open
position continues consuming heat. Engineering replays outside those windows
are pipeline checks only and cannot satisfy the advancement gate.

The primary advancement metric is portfolio-accepted trade expectancy after
costs. A ranker may enter a Phase B review shortlist only when development and
validation each contain at least 100 mature accepted episodes for both the
production baseline and the challenger independently and, in both
stages, it improves expectancy by at least `0.05R`, produces strictly greater
total realised portfolio R, has profit factor no lower than production Final
Score, and has maximum drawdown no more than `1.0R` worse. Deterministic random
cannot advance. At most two qualifying rankers are shortlisted by validation
expectancy improvement descending, validation maximum drawdown ascending, then
ranker name ascending. This is a shortlist gate, not automatic champion
selection or production promotion; human review and a separately preregistered
Phase B protocol remain mandatory.

## Interpretation and decision boundary

Phase A implements and verifies the interface, causal factor calculation, input
contract, and runner only. It does not inspect a new outcome sample and supplies
no performance evidence. The runner requires a pre-allocation point-in-time
candidate journal that preserves canonical eligibility, original candidate
risk, applicable heat limit, production Final Score, and frozen plan outcomes.
Post-allocation production reports cannot reconstruct candidates rejected by
capacity and are therefore not a valid substitute. Local historical data is
still `NOT_READY`; any future current-universe engineering run must retain the
survivorship-bias label and cannot validate or promote a ranker.

The formal runner fails before loading current sector/industry mappings whenever
the data gate is not `READY`. Even a future `READY` declaration cannot enable
formal evidence until an effective-dated classification loader is implemented
and verified. Current classifications are permitted only in an explicitly
labelled `--engineering-replay`, where the shortlist gate is disabled.

Accordingly the current conclusion is: **the engineering portion of Phase A is
substantially implemented, but formal Phase A infrastructure is not complete;
the data/classification path remains blocked, and Phase B and Phase C are not
implemented.**

The historical decision fields remain unset until a separately authorized run.
Production is unchanged. Stop/target grids, exposure grids, earnings-blackout
combinations, SMA/ATR offsets, RS thresholds, and hard-filter combinations are
frozen benchmark-only families and must not be optimized again here.
