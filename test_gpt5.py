"""Temporary safe GPT-5 Responses API test."""

from __future__ import annotations

import os


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def safe_error_code(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        nested = body.get("error", body)
        if isinstance(nested, dict):
            code = nested.get("code") or nested.get("type")
            if code:
                return str(code)
    code = getattr(exc, "code", None)
    return str(code) if code else "Unavailable"


def safe_http_status(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return str(status) if status is not None else "Unavailable"


def main() -> int:
    load_dotenv_if_available()
    api_key = os.environ.get("OPENAI_API_KEY")
    print("Configured Project: stock_screener (user confirmation)")
    print("Model Tested: gpt-5")

    if not api_key:
        print("HTTP Status: Unavailable")
        print("Safe Error Type: MissingAPIKey")
        print("Safe Error Code: Unavailable")
        print("Response: Unavailable")
        return 1

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=20.0)
        response = client.responses.create(
            model="gpt-5",
            input="Reply with exactly:\nGPT-5 connection successful.",
            max_output_tokens=50,
        )
        text = (getattr(response, "output_text", "") or "").strip()
        print("HTTP Status: Unavailable")
        print("Safe Error Type: None")
        print("Safe Error Code: Unavailable")
        print(f"Response: {text}")
        if text == "GPT-5 connection successful.":
            print("✓ GPT-5 API is available.")
            return 0
        return 1
    except ImportError:
        print("HTTP Status: Unavailable")
        print("Safe Error Type: OpenAINotInstalledError")
        print("Safe Error Code: Unavailable")
        print("Response: Unavailable")
        return 1
    except Exception as exc:
        print(f"HTTP Status: {safe_http_status(exc)}")
        print(f"Safe Error Type: {exc.__class__.__name__}")
        print(f"Safe Error Code: {safe_error_code(exc)}")
        print("Response: Unavailable")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
