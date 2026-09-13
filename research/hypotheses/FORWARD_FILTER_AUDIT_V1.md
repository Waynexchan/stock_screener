# FORWARD_FILTER_AUDIT_V1 preregistration

Date preregistered: 2026-09-12. Status: **RESEARCH_ONLY**.

Freeze the earliest complete immutable production snapshot for each signal date. Preserve every candidate, including WATCH and NO TRADE, together with the decision, reasons, setup, RS, industry, volume, extension, entry, stop, target, risk/reward, and observed sector fields. Candidate-plan simulations are shadow counterfactuals; report actionable FULL/HALF outcomes separately and never describe WATCH or NO TRADE rows as authorized trades. Never rewrite snapshot inputs after outcomes arrive.

When a supplied OHLCV archive contains sufficient future sessions, calculate next-session-open 5/10/20/40-session return, MFE, and MAE. Rolling beta uses only the 126 sessions ending at the signal date. Utilities are identified from the sector stored in the snapshot, not a later classification lookup.

Interim raw outcomes diagnose opportunity cost. A valid planned entry may trigger during the next five sessions. A gap above entry fills at the open and an intraday touch fills at the planned entry, both with 5 bps adverse entry slippage. Stops gap through at the open; favorable target gaps receive only the target level; if stop and target can both be touched on one daily bar, stop is assumed first. A plan still open before 40 sessions is `OPEN_UNMATURED` with null realised R, never an early time exit. Review requires at least 100 mature triggered observations and must report missing and untriggered outcomes. Forward evidence never changes production automatically.
