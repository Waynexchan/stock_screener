import tempfile
import unittest
from pathlib import Path

import pandas as pd

import config
import ai_analysis
import run_screener
import send_email


def valid_universe(count: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Ticker": [f"T{i}" for i in range(count)],
            "Symbol": [f"T{i}" for i in range(count)],
            "Security Name": [f"Company {i}" for i in range(count)],
            "Exchange": ["NASDAQ"] * count,
            "Sector": ["Technology"] * count,
            "Industry": ["Software"] * count,
            "Market Cap": [1_000_000_000] * count,
            "Avg Volume": [1_000_000] * count,
        }
    )


class DataQualityTests(unittest.TestCase):
    def test_min_rs_score_is_market_smith_style_75_or_higher(self):
        self.assertEqual(config.MIN_RS_SCORE, 75)

    def test_valid_universe_refresh_validation(self):
        universe = valid_universe(config.MIN_VALID_UNIVERSE_COUNT)
        valid, reason = run_screener.validate_universe_frame(universe, 0.70)
        self.assertTrue(valid, reason)

    def test_partial_universe_refresh_with_589_tickers_fails(self):
        universe = valid_universe(589)
        valid, reason = run_screener.validate_universe_frame(universe, 0.70)
        self.assertFalse(valid)
        self.assertIn("ticker count below", reason)

    def test_spy_qqq_download_failure_rejects_run(self):
        universe_result = run_screener.UniverseLoadResult(valid_universe(1600), 2000, 1600)
        market_result = run_screener.MarketConditionResult(
            frame=pd.DataFrame(),
            status="Unknown",
            spy_valid=False,
            qqq_valid=False,
            data_failure=True,
            stats=run_screener.DownloadStats(requested=2, successful=0, failed=2),
        )
        stats = run_screener.DownloadStats(requested=1600, successful=1500, failed=100)
        result = run_screener.validate_run_quality(universe_result, market_result, stats)
        self.assertFalse(result.valid)
        self.assertIn("market data unavailable", result.reason)

    def test_download_success_rate_below_70_rejects_run(self):
        universe_result = run_screener.UniverseLoadResult(valid_universe(1600), 2000, 1600)
        market_result = run_screener.MarketConditionResult(
            frame=pd.DataFrame(),
            status="Neutral",
            spy_valid=True,
            qqq_valid=False,
            data_failure=False,
            stats=run_screener.DownloadStats(requested=2, successful=1, failed=1),
        )
        stats = run_screener.DownloadStats(requested=1600, successful=1000, failed=600)
        result = run_screener.validate_run_quality(universe_result, market_result, stats)
        self.assertFalse(result.valid)
        self.assertIn("success rate below", result.reason)

    def test_successful_fallback_to_last_known_good_universe(self):
        universe_result = run_screener.UniverseLoadResult(
            universe=valid_universe(1600),
            total_downloaded=589,
            total_after_filter=1600,
            fallback_used=True,
            refresh_failed_validation=True,
        )
        self.assertTrue(universe_result.fallback_used)
        self.assertEqual(universe_result.total_after_filter, 1600)

    def test_invalid_run_does_not_overwrite_previous_valid_reports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "daily_watchlist.html"
            report.write_text("previous valid report", encoding="utf-8")
            run_quality = run_screener.RunQualityResult(
                valid=False,
                reason="Price download success rate below threshold.",
                universe_count=589,
                requested_tickers=589,
                successful_downloads=0,
                failed_downloads=589,
                success_rate=0.0,
                spy_valid=False,
                qqq_valid=False,
                fallback_used=True,
            )
            current_dir = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)
                run_screener.write_data_failure_report(run_quality)
            finally:
                os.chdir(current_dir)

            self.assertEqual(report.read_text(encoding="utf-8"), "previous valid report")
            self.assertTrue((Path(temp_dir) / run_screener.DATA_FAILURE_REPORT).exists())

    def test_invalid_run_warning_email_has_no_attachment(self):
        message = send_email.build_data_failure_message("sender@example.com", "recipient@example.com")
        self.assertEqual(message["Subject"], send_email.DATA_FAILURE_SUBJECT)
        self.assertFalse(message.is_multipart())
        self.assertIn("previous valid watchlist has been preserved", message.get_content())

    def test_review_priority_prefers_quality_setup_and_volume(self):
        high_quality = {
            "Category": "Breakout Candidates",
            "RS Score": 95,
            "Volume Ratio": 1.8,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Nearest Support Distance ATR": 0.8,
            "Industry Rank": 20,
        }
        weak_quality_hot_industry = {
            "Category": "Extended Candidates",
            "RS Score": 70,
            "Volume Ratio": 0.5,
            "Avg Volume": 600_000,
            "Risk/Reward Quality": "Poor R/R",
            "Pullback Quality": "D - Overextended Pullback",
            "Extension Status": "Overextended",
            "VCP Label": "Poor VCP",
            "Nearest Support Distance ATR": 4.0,
            "Industry Rank": 1,
        }
        self.assertGreater(
            run_screener.review_priority_score(high_quality),
            run_screener.review_priority_score(weak_quality_hot_industry),
        )

    def test_missing_industry_rank_does_not_receive_hot_industry_bonus(self):
        ranked = {
            "Category": "Pullback Candidates",
            "RS Score": 80,
            "Volume Ratio": 1.0,
            "Avg Volume": 1_000_000,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Average VCP",
            "Nearest Support Distance ATR": 1.0,
            "Industry Rank": 1,
        }
        unranked = dict(ranked)
        unranked["Industry Rank"] = float("nan")

        self.assertGreater(
            run_screener.review_priority_score(ranked),
            run_screener.review_priority_score(unranked),
        )

    def test_unknown_industry_excluded_from_top_industries_and_ranks(self):
        base = pd.DataFrame(
            [
                {"Ticker": "AAA", "Sector": "Unknown", "Industry": "Unknown", "RS Score": 99, "Industry Setup Count": float("nan"), "Avg Volume": 1_000_000},
                {"Ticker": "BBB", "Sector": "Unknown", "Industry": "Unknown", "RS Score": 98, "Industry Setup Count": float("nan"), "Avg Volume": 1_000_000},
                {"Ticker": "CCC", "Sector": "Technology", "Industry": "Semiconductors", "RS Score": 85, "Industry Setup Count": float("nan"), "Avg Volume": 1_000_000},
                {"Ticker": "DDD", "Sector": "Technology", "Industry": "Semiconductors", "RS Score": 82, "Industry Setup Count": float("nan"), "Avg Volume": 1_000_000},
            ]
        )

        industries = run_screener.build_top_industries(base)
        self.assertNotIn("Unknown", industries["Industry"].tolist())
        self.assertEqual(industries.iloc[0]["Industry"], "Semiconductors")

        ranked = run_screener.add_industry_ranks(base)
        unknown_ranks = ranked.loc[ranked["Industry"] == "Unknown", "Industry Rank"]
        known_ranks = ranked.loc[ranked["Industry"] == "Semiconductors", "Industry Rank"]
        self.assertTrue(unknown_ranks.isna().all())
        self.assertTrue((known_ranks == 1).all())
        self.assertTrue((ranked.loc[ranked["Industry"] == "Semiconductors", "Industry Setup Count"] == 2).all())

    def test_industry_setup_cluster_adds_review_priority_bonus(self):
        solo = {
            "Category": "Pullback Candidates",
            "RS Score": 85,
            "Volume Ratio": 1.0,
            "Avg Volume": 1_000_000,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Average VCP",
            "Nearest Support Distance ATR": 1.0,
            "Industry Rank": 10,
            "Industry Setup Count": 1,
        }
        cluster = dict(solo)
        cluster["Industry Setup Count"] = 5

        self.assertGreater(
            run_screener.review_priority_score(cluster),
            run_screener.review_priority_score(solo),
        )

    def test_rs_trend_labels_identify_emerging_and_fading_leaders(self):
        self.assertEqual(run_screener.rs_trend_label(80, 12), "Emerging Leader")
        self.assertEqual(run_screener.rs_trend_label(78, 6), "Improving")
        self.assertEqual(run_screener.rs_trend_label(90, 1), "Stable Leader")
        self.assertEqual(run_screener.rs_trend_label(82, -6), "Weakening")
        self.assertEqual(run_screener.rs_trend_label(82, -12), "Fading")

    def test_rs_trend_adds_review_priority_bonus_for_new_leaders(self):
        stable = {
            "Category": "Pullback Candidates",
            "RS Score": 80,
            "RS Trend": "Stable",
            "Volume Ratio": 1.0,
            "Avg Volume": 1_000_000,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Average VCP",
            "Nearest Support Distance ATR": 1.0,
            "Industry Rank": 10,
            "Industry Setup Count": 1,
        }
        emerging = dict(stable)
        emerging["RS Trend"] = "Emerging Leader"

        self.assertGreater(
            run_screener.review_priority_score(emerging),
            run_screener.review_priority_score(stable),
        )

    def test_poor_vcp_and_loose_action_reduce_priority(self):
        clean = {
            "Category": "Pullback Candidates",
            "RS Score": 95,
            "RS Trend": "Stable Leader",
            "Volume Ratio": 0.7,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Normal",
            "Nearest Support Distance ATR": 0.8,
            "Industry Rank": 5,
            "Industry Setup Count": 4,
        }
        loose = dict(clean)
        loose["VCP Label"] = "Poor VCP"
        loose["Tightness Label"] = "Loose"

        self.assertGreater(
            run_screener.review_priority_score(clean),
            run_screener.review_priority_score(loose),
        )
        self.assertLess(run_screener.review_priority_score(loose), 100)

    def test_review_tier_separates_immediate_review_from_noise(self):
        clean = {
            "Category": "Pullback Candidates",
            "Action": "Confirmed pullback entry review",
            "RS Score": 96,
            "RS Trend": "Stable Leader",
            "Volume Ratio": 0.8,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Normal",
            "Nearest Support Distance ATR": 0.6,
            "Industry Rank": 3,
            "Industry Setup Count": 3,
            "Support Signal": "EMA20 reclaim",
            "Review Priority Score": 70,
            "Price Data Warning": "",
        }
        noisy = dict(clean)
        noisy["Action"] = "Watch only"
        noisy["Extension Status"] = "Extended"
        noisy["RS Trend"] = "Weakening"

        self.assertEqual(run_screener.review_tier(clean), "Review Now")
        self.assertEqual(run_screener.review_tier(noisy), "Skip Today")
        self.assertIn("extended", run_screener.setup_noise_reasons(noisy))
        self.assertIn("weakening RS", run_screener.setup_noise_reasons(noisy))

    def test_confirmed_poor_vcp_loose_setup_is_not_top_action(self):
        row = {
            "Category": "Pullback Candidates",
            "Action": "Confirmed pullback entry review",
            "RS Score": 98,
            "RS Trend": "Stable Leader",
            "Volume Ratio": 0.8,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Poor VCP",
            "Tightness Label": "Loose",
            "Nearest Support Distance ATR": 0.4,
            "Industry Rank": 3,
            "Industry Setup Count": 5,
            "Support Signal": "EMA20 reclaim",
            "Review Priority Score": 80,
            "Price Data Warning": "",
        }

        self.assertEqual(run_screener.review_tier(row), "Watch Later")
        self.assertIn("poor VCP", run_screener.setup_noise_reasons(row))
        self.assertIn("loose action", run_screener.setup_noise_reasons(row))

    def test_watch_only_action_never_becomes_high_priority(self):
        row = {
            "Category": "Tight Consolidation Candidates",
            "Action": "Watch only",
            "RS Score": 96,
            "RS Trend": "Stable Leader",
            "Volume Ratio": 0.8,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Normal",
            "Nearest Support Distance ATR": 0.5,
            "Industry Rank": 3,
            "Industry Setup Count": 5,
            "Support Signal": "EMA20 reclaim",
            "Review Priority Score": 80,
            "Price Data Warning": "",
        }

        self.assertEqual(run_screener.review_tier(row), "Watch Later")
        self.assertIn("wait-only action", run_screener.setup_noise_reasons(row))

    def test_weak_pullback_quality_is_skipped_from_top_action(self):
        row = {
            "Category": "Tight Consolidation Candidates",
            "Action": "Monitor tight base",
            "RS Score": 96,
            "RS Trend": "Stable Leader",
            "Volume Ratio": 0.8,
            "Avg Volume": 2_000_000,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "D - Overextended Pullback",
            "Extension Status": "Moderately Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Tight",
            "Nearest Support Distance ATR": 0.5,
            "Industry Rank": 3,
            "Industry Setup Count": 5,
            "Support Signal": "Recent support",
            "Review Priority Score": 80,
            "Price Data Warning": "",
        }

        self.assertEqual(run_screener.review_tier(row), "Skip Today")
        self.assertIn("weak pullback quality", run_screener.setup_noise_reasons(row))

    def test_top_action_list_excludes_watch_later_and_skip_today_noise(self):
        quality = {
            "Category": "Pullback Candidates",
            "Ticker": "GOOD",
            "Sector": "Technology",
            "Industry": "Semiconductors",
            "RS Score": 96,
            "RS Trend": "Stable Leader",
            "RS Trend Delta": 2,
            "Price": 100,
            "Action": "Confirmed pullback entry review",
            "Review Tier": "",
            "Noise Filter Reason": "",
            "Review Priority Score": 70,
            "Price Data Warning": "",
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Normal",
            "Volume Ratio": 0.8,
            "Nearest Support Distance ATR": 0.6,
            "Industry Rank": 3,
            "Industry Setup Count": 3,
            "Avg Volume": 2_000_000,
            "Support Signal": "EMA20 reclaim",
            "TradingView": "https://example.com/GOOD",
        }
        noisy = dict(quality)
        noisy.update(
            {
                "Ticker": "NOISE",
                "Action": "Watch only",
                "RS Trend": "Weakening",
                "Extension Status": "Extended",
                "VCP Label": "Poor VCP",
                "Tightness Label": "Loose",
            }
        )
        categories = {
            "Pullback Candidates": pd.DataFrame([quality, noisy]),
            "Breakout Candidates": pd.DataFrame(columns=run_screener.DISCOVERY_COLUMNS),
            "Volume Surge Candidates": pd.DataFrame(columns=run_screener.DISCOVERY_COLUMNS),
            "Tight Consolidation Candidates": pd.DataFrame(columns=run_screener.DISCOVERY_COLUMNS),
            "Extended Candidates": pd.DataFrame(columns=run_screener.DISCOVERY_COLUMNS),
        }

        top_action = run_screener.build_top_action_list(categories)

        self.assertEqual(top_action["Ticker"].tolist(), ["GOOD"])
        self.assertEqual(top_action.iloc[0]["Review Tier"], "Review Now")

    def test_ai_compact_records_include_review_tier_and_noise_context(self):
        frame = pd.DataFrame(
            [
                {
                    "Ticker": "GOOD",
                    "Category": "Pullback Candidates",
                    "Action": "Confirmed pullback entry review",
                    "Review Tier": "Review Now",
                    "Noise Filter Reason": "",
                    "RS Score": 96,
                }
            ]
        )

        records = ai_analysis._compact_records(frame, 15)

        self.assertEqual(records[0]["Review Tier"], "Review Now")
        self.assertIn("Noise Filter Reason", records[0])

    def test_pullback_action_distinguishes_confirmed_and_quiet_setups(self):
        confirmed = {
            "Category": "Pullback Candidates",
            "Risk/Reward Quality": "Excellent R/R",
            "Extension Status": "Not Extended",
            "Support Signal": "EMA20 reclaim",
            "Volume Ratio": 0.7,
        }
        quiet = dict(confirmed)
        quiet["Support Signal"] = "Recent support"
        quiet["Volume Ratio"] = 0.4

        self.assertEqual(run_screener.action_for_row(confirmed), "Confirmed pullback entry review")
        self.assertEqual(run_screener.action_for_row(quiet), "Monitor quiet pullback")

    def test_price_data_warning_flags_extreme_latest_close(self):
        history = pd.DataFrame({"Close": [100.0] * 60 + [400.0], "Volume": [1_000_000] * 61})
        self.assertIn("20-day median", run_screener.price_data_warning(history))

    def test_ai_schema_requires_concern_and_confirmation(self):
        schema = ai_analysis._ai_response_schema()
        ranking_schema = schema["properties"]["rankings"]["items"]
        self.assertIn("bull_case", ranking_schema["required"])
        self.assertIn("concern", ranking_schema["required"])
        self.assertIn("confirmation", ranking_schema["required"])

    def test_review_flags_highlight_priority_and_caution_context(self):
        row = {
            "Action": "Confirmed pullback entry review",
            "RS Trend": "Emerging Leader",
            "VCP Label": "Poor VCP",
            "Tightness Label": "Loose",
            "Extension Status": "Not Extended",
            "Price Data Warning": "",
        }
        flags = run_screener.review_flags(row)
        self.assertIn("Confirmed", flags)
        self.assertIn("Emerging Leader", flags)
        self.assertIn("Poor VCP", flags)
        self.assertIn("Loose", flags)

    def test_html_table_renders_review_flag_badges(self):
        frame = pd.DataFrame(
            [
                {
                    "Ticker": "ABC",
                    "Action": "Confirmed pullback entry review",
                    "RS Trend": "Emerging Leader",
                    "VCP Label": "Good VCP",
                    "Tightness Label": "Tight",
                    "Extension Status": "Not Extended",
                    "Price Data Warning": "",
                    "TradingView": "https://example.com",
                }
            ]
        )
        html = run_screener.html_table(frame)
        self.assertIn("Review Flags", html)
        self.assertIn("badge flag-confirmed", html)
        self.assertIn("badge flag-emerging", html)
        self.assertIn("row-priority", html)

    def test_markdown_table_includes_review_flags(self):
        frame = pd.DataFrame(
            [
                {
                    "Ticker": "ABC",
                    "Action": "Monitor quiet pullback",
                    "RS Trend": "Stable",
                    "VCP Label": "Poor VCP",
                    "Tightness Label": "Loose",
                    "Extension Status": "Not Extended",
                    "Price Data Warning": "",
                }
            ]
        )
        markdown = run_screener.markdown_table(frame)
        self.assertIn("Review Flags", markdown)
        self.assertIn("Poor VCP", markdown)
        self.assertIn("Loose", markdown)

    def test_report_summary_counts_top_action_quality_flags(self):
        frame = pd.DataFrame(
            [
                {
                    "Ticker": "ABC",
                    "Action": "Confirmed pullback entry review",
                    "RS Trend": "Emerging Leader",
                    "VCP Label": "Good VCP",
                    "Tightness Label": "Tight",
                    "Extension Status": "Not Extended",
                    "Price Data Warning": "",
                },
                {
                    "Ticker": "XYZ",
                    "Action": "Monitor quiet pullback",
                    "RS Trend": "Stable",
                    "VCP Label": "Poor VCP",
                    "Tightness Label": "Loose",
                    "Extension Status": "Not Extended",
                    "Price Data Warning": "Latest close inconsistent with recent median.",
                },
            ]
        )

        counts = run_screener.report_summary_counts(frame)

        self.assertEqual(counts["top_action_count"], 2)
        self.assertEqual(counts["confirmed_setups"], 1)
        self.assertEqual(counts["emerging_leaders"], 1)
        self.assertEqual(counts["caution_rows"], 1)
        self.assertEqual(counts["price_warnings"], 1)

    def test_html_summary_panel_renders_top_action_counts(self):
        frame = pd.DataFrame(
            [
                {
                    "Ticker": "ABC",
                    "Action": "Confirmed pullback entry review",
                    "RS Trend": "Emerging Leader",
                    "VCP Label": "Good VCP",
                    "Tightness Label": "Tight",
                    "Extension Status": "Not Extended",
                    "Price Data Warning": "",
                }
            ]
        )

        html = run_screener.html_summary_panel(frame, "Caution")

        self.assertIn("Executive Summary", html)
        self.assertIn("Market Status", html)
        self.assertIn("Caution", html)
        self.assertIn("Confirmed Setups", html)
        self.assertIn("Emerging Leaders", html)
        self.assertIn("Price Warnings", html)
        self.assertIn("summary-grid", html)

    def test_daily_review_plan_prioritises_review_now_before_tracking(self):
        top_action = pd.DataFrame(
            [
                {
                    "Ticker": "ABC",
                    "Review Tier": "Review Now",
                    "Action": "Confirmed pullback entry review",
                },
                {
                    "Ticker": "DEF",
                    "Review Tier": "High Priority Watch",
                    "Action": "Monitor quiet pullback",
                },
            ]
        )
        daily_focus = pd.DataFrame(
            [
                {
                    "Ticker": "XYZ",
                    "Review Tier": "Watch Later",
                    "Action": "Watch only",
                }
            ]
        )

        markdown = run_screener.markdown_daily_review_plan(top_action, daily_focus, "Caution")
        html = run_screener.html_daily_review_plan(top_action, daily_focus, "Caution")

        self.assertIn("Open first: ABC.", markdown)
        self.assertIn("Review after confirmed setups: DEF.", markdown)
        self.assertIn("Market is defensive", markdown)
        self.assertIn("Daily Review Plan", html)
        self.assertIn("Open first: ABC.", html)

    def test_daily_review_plan_warns_when_top_action_is_empty(self):
        top_action = pd.DataFrame(columns=["Ticker", "Review Tier", "Action"])
        daily_focus = pd.DataFrame(
            [
                {
                    "Ticker": "XYZ",
                    "Review Tier": "Skip Today",
                    "Action": "Watch only",
                }
            ]
        )

        markdown = run_screener.markdown_daily_review_plan(top_action, daily_focus, "Neutral")

        self.assertIn("No clean first-review setups", markdown)
        self.assertIn("Skip today unless conditions improve: XYZ.", markdown)

    def test_report_history_delta_tracks_ticker_and_industry_rotation(self):
        current = {
            "generated_at": "2026-07-23 22:00:00",
            "top_action_count": 3,
            "confirmed_setups": 2,
            "emerging_leaders": 1,
            "caution_rows": 0,
            "price_warnings": 0,
            "top_action_tickers": "ABC; DEF; NEW",
            "top_industries": "Semiconductors; Biotechnology",
        }
        previous = {
            "generated_at": "2026-07-22 22:00:00",
            "top_action_count": 2,
            "confirmed_setups": 1,
            "emerging_leaders": 2,
            "caution_rows": 1,
            "price_warnings": 1,
            "top_action_tickers": "ABC; OLD",
            "top_industries": "Software; Biotechnology",
        }

        delta = run_screener.report_history_delta(current, previous)

        self.assertTrue(delta["has_previous"])
        self.assertEqual(delta["new_top_action_tickers"], ["DEF", "NEW"])
        self.assertEqual(delta["removed_top_action_tickers"], ["OLD"])
        self.assertEqual(delta["new_top_industries"], ["Semiconductors"])
        self.assertEqual(delta["removed_top_industries"], ["Software"])
        self.assertEqual(delta["count_deltas"]["confirmed_setups"], 1)
        self.assertEqual(delta["count_deltas"]["emerging_leaders"], -1)

    def test_report_history_append_and_load_last_snapshot(self):
        snapshot = {
            "generated_at": "2026-07-23 22:00:00",
            "market_status": "Neutral",
            "top_action_count": 1,
            "confirmed_setups": 1,
            "emerging_leaders": 0,
            "caution_rows": 0,
            "price_warnings": 0,
            "top_action_tickers": "ABC",
            "top_industries": "Semiconductors",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "summary_history.csv")
            run_screener.append_report_history(snapshot, path)
            loaded = run_screener.load_last_report_history(path)

        self.assertEqual(loaded["generated_at"], snapshot["generated_at"])
        self.assertEqual(int(loaded["top_action_count"]), 1)
        self.assertEqual(loaded["top_action_tickers"], "ABC")

    def test_html_history_panel_renders_daily_changes(self):
        delta = {
            "has_previous": True,
            "previous_generated_at": "2026-07-22 22:00:00",
            "new_top_action_tickers": ["NEW"],
            "removed_top_action_tickers": ["OLD"],
            "new_top_industries": ["Semiconductors"],
            "removed_top_industries": ["Software"],
            "count_deltas": {
                "top_action_count": 1,
                "confirmed_setups": 1,
                "emerging_leaders": -1,
                "caution_rows": 0,
                "price_warnings": 0,
            },
        }

        html = run_screener.html_history_panel(delta)

        self.assertIn("Daily Change", html)
        self.assertIn("+1", html)
        self.assertIn("NEW", html)
        self.assertIn("OLD", html)
        self.assertIn("Semiconductors", html)

    def test_report_history_trend_includes_current_snapshot_and_assessment(self):
        previous = [
            {
                "generated_at": "2026-07-21 22:00:00",
                "market_status": "Caution",
                "top_action_count": 4,
                "confirmed_setups": 1,
                "emerging_leaders": 0,
                "caution_rows": 2,
                "price_warnings": 1,
                "top_action_tickers": "AAA",
                "top_industries": "Software",
            },
            {
                "generated_at": "2026-07-22 22:00:00",
                "market_status": "Neutral",
                "top_action_count": 5,
                "confirmed_setups": 1,
                "emerging_leaders": 1,
                "caution_rows": 1,
                "price_warnings": 0,
                "top_action_tickers": "BBB",
                "top_industries": "Biotechnology",
            },
        ]
        current = {
            "generated_at": "2026-07-23 22:00:00",
            "market_status": "Strong",
            "top_action_count": 6,
            "confirmed_setups": 3,
            "emerging_leaders": 2,
            "caution_rows": 0,
            "price_warnings": 0,
            "top_action_tickers": "CCC",
            "top_industries": "Semiconductors",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "summary_history.csv")
            pd.DataFrame(previous).to_csv(path, index=False)
            trend = run_screener.report_history_trend(current, path=path, limit=10)

        self.assertTrue(trend["has_history"])
        self.assertEqual(len(trend["rows"]), 3)
        self.assertEqual(trend["rows"][-1]["generated_at"], current["generated_at"])
        self.assertEqual(trend["assessment"], "Improving opportunity quality")
        self.assertGreater(trend["rows"][-1]["quality_score"], trend["rows"][0]["quality_score"])

    def test_html_trend_panel_renders_mini_trend_table_and_bars(self):
        trend = {
            "assessment": "Improving opportunity quality",
            "has_history": True,
            "rows": [
                {
                    "generated_at": "2026-07-22 22:00:00",
                    "market_status": "Neutral",
                    "top_action_count": 5,
                    "confirmed_setups": 1,
                    "emerging_leaders": 1,
                    "caution_rows": 1,
                    "price_warnings": 0,
                    "quality_score": 2,
                },
                {
                    "generated_at": "2026-07-23 22:00:00",
                    "market_status": "Strong",
                    "top_action_count": 6,
                    "confirmed_setups": 3,
                    "emerging_leaders": 2,
                    "caution_rows": 0,
                    "price_warnings": 0,
                    "quality_score": 8,
                },
            ],
        }

        html = run_screener.html_trend_panel(trend)

        self.assertIn("Summary Trend", html)
        self.assertIn("Improving opportunity quality", html)
        self.assertIn("trend-table", html)
        self.assertIn("trend-bar", html)
        self.assertIn("Quality Score", html)

    def test_markdown_trend_section_renders_history_rows(self):
        trend = {
            "assessment": "Mixed or stable opportunity quality",
            "rows": [
                {
                    "generated_at": "2026-07-23 22:00:00",
                    "market_status": "Neutral",
                    "top_action_count": 4,
                    "confirmed_setups": 1,
                    "emerging_leaders": 1,
                    "caution_rows": 1,
                    "price_warnings": 0,
                    "quality_score": 2,
                }
            ],
        }

        markdown = run_screener.markdown_trend_section(trend)

        self.assertIn("Assessment: Mixed or stable opportunity quality", markdown)
        self.assertIn("Quality Score", markdown)
        self.assertIn("2026-07-23 22:00:00", markdown)

    def test_report_preview_uses_last_good_files_without_appending_history(self):
        watchlist = pd.DataFrame(
            [
                {
                    "Category": "Pullback Candidates",
                    "Ticker": "ABC",
                    "Sector": "Technology",
                    "Industry": "Semiconductors",
                    "RS Score": 95,
                    "RS Trend": "Emerging Leader",
                    "RS Trend Delta": 10,
                    "Action": "Confirmed pullback entry review",
                    "Review Priority Score": 90,
                    "Risk/Reward Quality": "Excellent R/R",
                    "Pullback Quality": "A - Ideal Pullback",
                    "Extension Status": "Not Extended",
                    "VCP Label": "Good VCP",
                    "Tightness Label": "Normal",
                    "Volume Ratio": 0.8,
                    "Nearest Support Distance ATR": 0.5,
                    "Avg Volume": 2_000_000,
                    "TradingView": "https://example.com",
                }
            ]
        )
        history = pd.DataFrame(
            [
                {
                    "generated_at": "2026-07-22 22:00:00",
                    "market_status": "Neutral",
                    "top_action_count": 1,
                    "confirmed_setups": 0,
                    "emerging_leaders": 0,
                    "caution_rows": 1,
                    "price_warnings": 0,
                    "top_action_tickers": "OLD",
                    "top_industries": "Software",
                },
                {
                    "generated_at": "2026-07-23 22:00:00",
                    "market_status": "Strong",
                    "top_action_count": 1,
                    "confirmed_setups": 1,
                    "emerging_leaders": 1,
                    "caution_rows": 0,
                    "price_warnings": 0,
                    "top_action_tickers": "ABC",
                    "top_industries": "Semiconductors",
                },
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "daily_watchlist_last_good.csv"
            history_path = Path(temp_dir) / "summary_history.csv"
            output = Path(temp_dir) / "daily_watchlist_preview.html"
            watchlist.to_csv(source, index=False)
            history.to_csv(history_path, index=False)

            code = run_screener.run_report_preview_command(
                source_csv=str(source),
                history_path=str(history_path),
                output_html=str(output),
            )
            history_after = pd.read_csv(history_path)
            html = output.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(len(history_after), 2)
        self.assertIn("Daily Change", html)
        self.assertIn("Summary Trend", html)
        self.assertIn("Report preview mode: AI was not run.", html)
        self.assertIn("ABC", html)

    def test_metadata_cache_enriches_unknown_profiles_without_fetch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "sector_industry_cache.csv"
            pd.DataFrame(
                [{"Ticker": "ABC", "Sector": "Technology", "Industry": "Software"}]
            ).to_csv(cache_path, index=False)

            current_dir = Path.cwd()
            try:
                import os

                os.chdir(temp_dir)
                profiles = {"ABC": {"Exchange": "NASDAQ", "Sector": "Unknown", "Industry": "Unknown"}}
                enriched = run_screener.enrich_profiles_with_metadata(profiles, ["ABC"])
            finally:
                os.chdir(current_dir)

            self.assertEqual(enriched["ABC"]["Sector"], "Technology")
            self.assertEqual(enriched["ABC"]["Industry"], "Software")


if __name__ == "__main__":
    unittest.main()
