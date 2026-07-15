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


if __name__ == "__main__":
    unittest.main()
