# Production Candidate Ordering

## Governance status

- Behaviour present in the current production path: Final Score descending,
  then normalized ticker ascending.
- Production effect: **YES**. When otherwise eligible candidates compete for
  scarce position, heat, daily-risk, industry, or sector capacity, this order can
  change which ticker receives risk.
- Approval evidence: **UNKNOWN / NEEDS VERIFICATION**. No separate explicit
  production-approval record was located during the Phase 1 review-fix task.
- This behaviour is not owned or authorized by Pattern Discovery Phase 1 and is
  not evidence from `PORTFOLIO_RANKING_PHASE_A_V1`.

## Current behavioural contract

1. Candidate eligibility remains owned by the canonical decision pipeline.
2. Eligible candidates are ordered by finite Final Score descending.
3. Missing, non-numeric, and non-finite Final Score ranks last.
4. Ties use normalized ticker ascending; input row order is never a tie-break.
5. Concentration and shared capacity are applied in that deterministic order.
6. The same candidate set produces the same selected allocation under input
   permutation.

## Acceptance criteria

1. Permuting identical candidates does not change selected tickers or sizing.
2. A finite score outranks a missing or non-finite score.
3. Equal finite scores use normalized ticker ascending.
4. No research factor, lane, report section, or AI field can change this order.
5. Any future modification requires separate explicit production approval,
   regression coverage, FULL verification, and independent review.

## Non-goals

This record does not approve the existing change retroactively, promote a
research ranker, or claim improved trading performance. It records the actual
production behaviour and the missing approval evidence so the change cannot be
misrepresented as `production_effect: NONE`.
