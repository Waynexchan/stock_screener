import tempfile
import unittest
from pathlib import Path

import pandas as pd

import config
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
