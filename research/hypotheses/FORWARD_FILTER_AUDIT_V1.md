# FORWARD_FILTER_AUDIT_V1 preregistration

Date preregistered: 2026-09-12. Status: **RESEARCH_ONLY**.

Freeze the earliest complete immutable production snapshot for each signal date. Preserve every candidate, including WATCH and NO TRADE, together with the decision, reasons, setup, RS, industry, volume, extension, entry, stop, target, risk/reward, and observed sector fields. Never rewrite snapshot inputs after outcomes arrive.

When a supplied OHLCV archive contains sufficient future sessions, calculate next-session-open 5/10/20/40-session return, MFE, and MAE. Rolling beta uses only the 126 sessions ending at the signal date. Utilities are identified from the sector stored in the snapshot, not a later classification lookup.

Interim raw outcomes diagnose opportunity cost but do not yet prove executable expectancy. A separately tested conservative plan-trigger simulator is required before using R expectancy as the primary result. Review requires at least 100 mature observations and must report missing outcomes. Forward evidence never changes production automatically.
