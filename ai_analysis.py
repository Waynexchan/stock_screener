"""AI commentary support for the Stage 2 swing trading screener.

Rule-based screening remains responsible for all stock selection. This module
only summarises the already-built Top Action List for the final human review.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from importlib import metadata
from typing import Any

import pandas as pd

import config

AI_SCORE_COLUMNS = [
    "AI Conviction Score",
    "AI Priority Rank",
    "AI Reason",
    "AI Bull Case",
    "AI Concern",
    "AI Confirmation",
]
LAST_AI_ANALYSIS_RESULT: "AIAnalysisResult | None" = None


class OpenAINotInstalledError(RuntimeError):
    pass


@dataclass
class AIAnalysisResult:
    commentary: str
    top_action_list: pd.DataFrame
    enabled: bool
    api_key_loaded: bool
    model: str
    tickers_analysed: int
    failed_safely: bool = False
    sdk_version: str = "Not installed"
    model_used: str = ""
    api_call_success: bool = False
    response_received: bool = False
    json_parsed: bool = False
    commentary_generated: bool = False
    response_time_seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    response_tokens: int | None = None
    error_type: str = ""
    error_code: str = ""
    http_status: int | None = None


def load_dotenv_if_available() -> None:
    """Load .env values when python-dotenv is installed; keep OS env support."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv not installed.")
        print("Run: pip install python-dotenv")
        return
    load_dotenv()


def load_openai_api_key() -> str | None:
    """Return the OpenAI API key from .env or existing environment variables."""
    load_dotenv_if_available()
    return os.environ.get("OPENAI_API_KEY")


def openai_sdk_version() -> str:
    try:
        return metadata.version("openai")
    except metadata.PackageNotFoundError:
        return "Not installed"


def _compact_records(frame: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    compact_columns = {
        "Ticker": "Ticker",
        "Category": "Category",
        "Action": "Action",
        "Review Tier": "Review Tier",
        "Noise Filter Reason": "Noise Filter Reason",
        "RS Score": "RS Score",
        "RS Trend": "RS Trend",
        "RS Trend Delta": "RS Trend Delta",
        "Industry Rank": "Industry Rank",
        "Industry Setup Count": "Industry Setup Count",
        "Risk/Reward Quality": "Risk/Reward Quality",
        "Pullback Quality": "Pullback Quality",
        "Extension Status": "Extension Status",
        "VCP Label": "VCP Label",
        "Tightness Label": "Tightness Label",
        "Volume Ratio": "Volume Ratio",
        "Nearest Support Distance ATR": "ATR Distance",
        "Distance From Pivot %": "Distance From Pivot %",
        "Support Signal": "Support Signal",
        "Price Data Warning": "Price Data Warning",
    }
    available = [column for column in compact_columns if column in frame.columns]
    compact = frame.head(limit)[available].rename(columns=compact_columns).copy()
    compact["Focus Reason"] = compact.apply(_focus_reason, axis=1)
    ordered = [
        "Ticker", "Category", "Action", "Focus Reason", "RS Score", "RS Trend", "RS Trend Delta",
        "Review Tier", "Noise Filter Reason", "Industry Rank", "Industry Setup Count",
        "Risk/Reward Quality", "Pullback Quality", "Extension Status", "VCP Label",
        "Tightness Label", "Volume Ratio", "ATR Distance", "Distance From Pivot %",
        "Support Signal", "Price Data Warning",
    ]
    return compact[[column for column in ordered if column in compact.columns]].fillna("").to_dict(orient="records")


def _industry_records(frame: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    columns = [
        "Industry", "Sector", "Industry Strength Score", "Candidate Count",
        "Avg RS Score", "Best RS Score", "Top 3 Leaders",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.head(limit)[available].fillna("").to_dict(orient="records")


def _focus_reason(row: pd.Series) -> str:
    category = row.get("Category", "")
    risk_reward = row.get("Risk/Reward Quality", "")
    pullback = row.get("Pullback Quality", "")
    extension = row.get("Extension Status", "")
    if category == "Pullback Candidates":
        return f"{pullback}; {risk_reward}; {extension}"
    if category == "Tight Consolidation Candidates":
        return f"Tight base review; {risk_reward}; {extension}"
    if category == "Extended Candidates":
        return f"Extension risk review; {risk_reward}; {extension}"
    return f"{category}; {risk_reward}; {extension}".strip("; ")


def build_ai_prompt(
    top_action_list: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
) -> str:
    """Build a constrained prompt using only the Top Action List."""
    max_tickers = min(config.AI_MAX_TICKERS, 15)
    tickers = _compact_records(top_action_list, max_tickers)
    industries = _industry_records(top_industries, 10)
    return f"""
You are assisting a Stage 2 swing trader.

Important constraints:
- Rule-based screening already selected the stocks.
- You must analyse only the Top Action List below.
- Do not introduce stocks that are not in the Top Action List.
- Do not make buy/sell decisions.
- Do not predict the market.
- The human trader makes the final decision.
- The AI Conviction Score means how well this ticker matches the Stage 2 swing trading system today.
- The AI Conviction Score does not mean probability of profit.
- Use a 1-10 conviction scale with clear separation:
  9-10 = strongest Stage 2 setup, leadership, tightness/VCP, support, confirmation, and risk/reward alignment.
  7-8 = strong but with one manageable imperfection.
  5-6 = useful watchlist candidate but needs confirmation, tighter action, or better entry.
  3-4 = technically valid but clearly secondary.
  1-2 = wait; setup is too extended, weak, or low priority today.
- Be strict. Do not assign 8-10 when VCP is Poor, tightness is Loose, price data has a warning, or confirmation is weak unless other evidence is exceptional.
- Use Review Tier and Noise Filter Reason as deterministic rule-engine context when explaining priority.
- Each ranking reason must include both the main positive and the main concern.
- Use RS Trend and Industry Setup Count when prioritising emerging leaders and real group sponsorship.

Market status:
{market_status}

Top industries:
{industries}

Top Action List:
{tickers}

Return strict JSON only, with this schema:
{{
  "market_summary": "Brief market context from the supplied market status.",
  "industry_rotation_summary": "Brief industry leadership context from supplied industries.",
  "market_character": "Concise label such as Strong Breakout Market, Healthy Pullback Market, Defensive Market, or Rotation Market.",
  "rankings": [
    {{
      "ticker": "Ticker from the Top Action List only",
      "priority_rank": 1,
      "conviction_score": 8,
      "reason": "Short reason using only supplied fields",
      "bull_case": "Best supplied positive evidence",
      "concern": "Most important supplied weakness or risk",
      "confirmation": "What the user should wait for or verify on the chart",
      "status": "Best Opportunity"
    }}
  ],
  "stocks_to_wait": ["Ticker and brief reason"],
  "reminder": "AI assists prioritisation only and trading decisions remain with the user."
}}

For rankings, rank every supplied Top Action List ticker exactly once.
Use status values only from: Best Opportunity, Watch, Wait.
For stocks_to_wait, include supplied tickers that should be watched or waited on with a short reason.
Do not add tickers.
""".strip()


def _debug(message: str) -> None:
    if config.DEBUG:
        print(message)


def _ai_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "market_summary": {"type": "string"},
            "industry_rotation_summary": {"type": "string"},
            "market_character": {"type": "string"},
            "rankings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "priority_rank": {"type": "integer"},
                        "conviction_score": {"type": "number"},
                        "reason": {"type": "string"},
                        "bull_case": {"type": "string"},
                        "concern": {"type": "string"},
                        "confirmation": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["Best Opportunity", "Watch", "Wait"],
                        },
                    },
                    "required": [
                        "ticker",
                        "priority_rank",
                        "conviction_score",
                        "reason",
                        "bull_case",
                        "concern",
                        "confirmation",
                        "status",
                    ],
                    "additionalProperties": False,
                },
            },
            "stocks_to_wait": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reminder": {"type": "string"},
        },
        "required": [
            "market_summary",
            "industry_rotation_summary",
            "market_character",
            "rankings",
            "stocks_to_wait",
            "reminder",
        ],
        "additionalProperties": False,
    }


def _response_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()

    parts = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            if getattr(content_item, "type", "") == "output_text":
                item_text = getattr(content_item, "text", "")
                if item_text:
                    parts.append(item_text)
    return "\n".join(parts).strip()


def _response_token_count(response: Any) -> int | None:
    _, _, total_tokens = _response_usage_counts(response)
    return total_tokens


def _response_usage_counts(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None, None
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total = getattr(usage, "total_tokens", None)
    if total is None and input_tokens is not None and output_tokens is not None:
        total = int(input_tokens) + int(output_tokens)
    return (
        int(input_tokens) if input_tokens is not None else None,
        int(output_tokens) if output_tokens is not None else None,
        int(total) if total is not None else None,
    )


def _is_invalid_model_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code != 400:
        return False
    error_code = ""
    error = getattr(exc, "body", None)
    if isinstance(error, dict):
        nested = error.get("error", error)
        if isinstance(nested, dict):
            error_code = str(nested.get("code", "") or nested.get("type", ""))
    return "model" in error_code.lower() or exc.__class__.__name__ == "BadRequestError"


def _safe_error_code(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        nested = body.get("error", body)
        if isinstance(nested, dict):
            code = nested.get("code") or nested.get("type")
            if code:
                return str(code)
    code = getattr(exc, "code", None)
    return str(code) if code else ""


def _safe_http_status(exc: Exception) -> int | None:
    return getattr(exc, "status_code", None)


def _responses_create(client: Any, model: str, prompt: str) -> Any:
    return client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=config.AI_MAX_OUTPUT_TOKENS,
        text={
            "format": {
                "type": "json_schema",
                "name": "stock_screener_ai_analysis",
                "strict": True,
                "schema": _ai_response_schema(),
            }
        },
    )


def _call_openai(prompt: str, api_key: str) -> tuple[str, str, int | None, int | None, int | None, float]:
    try:
        from openai import OpenAI
    except ImportError:
        _debug("OpenAI Error Type: OpenAINotInstalledError")
        raise OpenAINotInstalledError()

    client = OpenAI(api_key=api_key)
    model = config.AI_MODEL
    started = time.perf_counter()
    _debug("OpenAI request started...")
    try:
        response = _responses_create(client, model, prompt)
        elapsed = time.perf_counter() - started
        _debug("OpenAI request completed.")
        input_tokens, output_tokens, tokens = _response_usage_counts(response)
        if config.DEBUG:
            if tokens is not None:
                print(f"AI Response Tokens: {tokens}")
            print(f"Response Time: {elapsed:.1f} sec")
        text = getattr(response, "output_text", "")
        text = text.strip() if text else ""
        if not text:
            raise ValueError("EmptyOpenAIResponse")
        return text, model, input_tokens, output_tokens, tokens, elapsed
    except Exception as exc:
        _debug(f"OpenAI Error Type: {exc.__class__.__name__}")
        raise


def _safe_json_cleanup(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = _safe_json_cleanup(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(cleaned):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[index:])
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                continue
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _empty_ai_columns(frame: pd.DataFrame) -> pd.DataFrame:
    updated = frame.copy()
    for column in AI_SCORE_COLUMNS:
        if column not in updated.columns:
            updated[column] = ""
    return updated


def _normalise_score(value: Any) -> int | str:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return ""
    return max(1, min(10, score))


def _normalise_rank(value: Any) -> int | str:
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return ""
    return max(1, rank)


def _apply_ai_rankings(top_action_list: pd.DataFrame, rankings: list[dict[str, Any]]) -> pd.DataFrame:
    updated = _empty_ai_columns(top_action_list)
    if updated.empty:
        return updated

    by_ticker = {
        str(item.get("ticker", "")).upper(): item
        for item in rankings
        if item.get("ticker")
    }
    for index, row in updated.iterrows():
        ticker = str(row.get("Ticker", "")).upper()
        item = by_ticker.get(ticker)
        if not item:
            continue
        updated.at[index, "AI Conviction Score"] = _normalise_score(item.get("conviction_score"))
        updated.at[index, "AI Priority Rank"] = _normalise_rank(item.get("priority_rank"))
        updated.at[index, "AI Reason"] = str(item.get("reason", ""))[:240]
        updated.at[index, "AI Bull Case"] = str(item.get("bull_case", ""))[:180]
        updated.at[index, "AI Concern"] = str(item.get("concern", ""))[:180]
        updated.at[index, "AI Confirmation"] = str(item.get("confirmation", ""))[:180]
    return updated


def _commentary_from_payload(payload: dict[str, Any]) -> str:
    stocks_to_wait = payload.get("stocks_to_wait", [])
    wait_text = "\n".join(str(item) for item in stocks_to_wait) if isinstance(stocks_to_wait, list) else str(stocks_to_wait)
    best = []
    for item in payload.get("rankings", []) or []:
        if not isinstance(item, dict) or item.get("status") != "Best Opportunity":
            continue
        best.append(
            (
                f"{item.get('ticker', '')}: {item.get('reason', '')} "
                f"Concern: {item.get('concern', '')} "
                f"Confirm: {item.get('confirmation', '')}"
            ).strip()
        )
    best_text = "\n".join(best) if best else "No best-opportunity ranking returned."
    return "\n".join(
        [
            "Market Summary",
            str(payload.get("market_summary", "")).strip(),
            "",
            "Industry Rotation Summary",
            str(payload.get("industry_rotation_summary", "")).strip(),
            "",
            "Best Opportunities",
            best_text,
            "",
            "Stocks To Wait",
            wait_text or "No wait list returned.",
            "",
            "Overall Market Character",
            str(payload.get("market_character", "")).strip(),
            "",
            "Reminder",
            str(payload.get("reminder", "")).strip(),
        ]
    ).strip()


def analyse_top_action_list(
    top_action_list: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
) -> AIAnalysisResult:
    """Generate AI commentary and rankings without affecting report generation."""
    global LAST_AI_ANALYSIS_RESULT
    enabled = bool(config.ENABLE_AI_COMMENTARY)
    model = config.AI_MODEL
    sdk_version = openai_sdk_version()
    max_tickers = min(config.AI_MAX_TICKERS, 15)
    tickers_analysed = min(len(top_action_list), max_tickers)
    safe_top_action_list = _empty_ai_columns(top_action_list)
    api_key = load_openai_api_key()
    api_key_loaded = bool(api_key)

    if top_action_list.empty:
        LAST_AI_ANALYSIS_RESULT = AIAnalysisResult(
            commentary="AI Commentary: No Top Action List tickers were available to analyse.",
            top_action_list=safe_top_action_list,
            enabled=enabled,
            api_key_loaded=api_key_loaded,
            model=model,
            tickers_analysed=0,
            sdk_version=sdk_version,
            model_used=model,
        )
        return LAST_AI_ANALYSIS_RESULT

    if not enabled:
        LAST_AI_ANALYSIS_RESULT = AIAnalysisResult(
            commentary="AI Commentary disabled.",
            top_action_list=safe_top_action_list,
            enabled=enabled,
            api_key_loaded=api_key_loaded,
            model=model,
            tickers_analysed=0,
            sdk_version=sdk_version,
            model_used=model,
        )
        return LAST_AI_ANALYSIS_RESULT

    if not api_key:
        LAST_AI_ANALYSIS_RESULT = AIAnalysisResult(
            commentary="OPENAI_API_KEY not found.",
            top_action_list=safe_top_action_list,
            enabled=enabled,
            api_key_loaded=False,
            model=model,
            tickers_analysed=0,
            sdk_version=sdk_version,
            model_used=model,
        )
        return LAST_AI_ANALYSIS_RESULT

    try:
        scoped_top_action_list = top_action_list.head(max_tickers)
        prompt = build_ai_prompt(scoped_top_action_list, top_industries, market_status)
        raw_text, model_used, input_tokens, output_tokens, response_tokens, response_time = _call_openai(prompt, api_key)
        payload = json.loads(raw_text)
        commentary = _commentary_from_payload(payload) or "AI Commentary generated."
        rankings = payload.get("rankings", [])
        if not isinstance(rankings, list):
            rankings = []
        enriched = _apply_ai_rankings(top_action_list, rankings)
        LAST_AI_ANALYSIS_RESULT = AIAnalysisResult(
            commentary=commentary,
            top_action_list=enriched,
            enabled=enabled,
            api_key_loaded=True,
            model=model,
            tickers_analysed=len(scoped_top_action_list),
            sdk_version=sdk_version,
            model_used=model_used,
            api_call_success=True,
            response_received=True,
            json_parsed=True,
            commentary_generated=bool(commentary),
            response_time_seconds=response_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_tokens=response_tokens,
        )
        return LAST_AI_ANALYSIS_RESULT
    except Exception as exc:
        LAST_AI_ANALYSIS_RESULT = AIAnalysisResult(
            commentary="AI Commentary failed safely.",
            top_action_list=safe_top_action_list,
            enabled=enabled,
            api_key_loaded=True,
            model=model,
            tickers_analysed=tickers_analysed,
            failed_safely=True,
            sdk_version=sdk_version,
            model_used=model,
            error_type=exc.__class__.__name__,
            error_code=_safe_error_code(exc),
            http_status=getattr(exc, "status_code", None),
        )
        return LAST_AI_ANALYSIS_RESULT


def generate_ai_commentary(
    top_action_list: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
) -> str:
    """Backward-compatible commentary helper."""
    return analyse_top_action_list(top_action_list, top_industries, market_status).commentary


def get_last_ai_analysis_result() -> AIAnalysisResult | None:
    """Return metadata from the most recent AI commentary call."""
    return LAST_AI_ANALYSIS_RESULT
