"""Safe standalone OpenAI Responses API connection test."""

from __future__ import annotations

import config
from ai_analysis import load_openai_api_key, select_available_ai_model


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
    api_key = load_openai_api_key()

    if not api_key:
        print("Plain Text API Call: Failed")
        print(f"Model Used: {config.AI_MODEL}")
        print("Safe Error Type: MissingAPIKey")
        print("Safe Error Code: Unavailable")
        print("HTTP Status: Unavailable")
        return 1

    selection = select_available_ai_model(api_key=api_key, print_status=True)
    print("Available Preferred Models:")
    if selection.available_preferred_models:
        for model in selection.available_preferred_models:
            print(f"- {model}")
    else:
        print("- None")
    print("Available Compatible Models:")
    if selection.available_compatible_models:
        for model in selection.available_compatible_models:
            print(f"- {model}")
    else:
        print("- None")

    if selection.failed or not selection.selected_model:
        print("Plain Text API Call: Failed")
        print(f"Model Used: {selection.selected_model or config.AI_MODEL}")
        print(f"Safe Error Type: {selection.error_type or 'NoPreferredModelAvailable'}")
        print(f"Safe Error Code: {selection.error_code or 'Unavailable'}")
        print(f"HTTP Status: {selection.http_status if selection.http_status is not None else 'Unavailable'}")
        return 1

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=12.0)
        response = client.responses.create(
            model=selection.selected_model,
            input="Reply with exactly: OpenAI connection successful.",
            max_output_tokens=50,
        )
        text = (getattr(response, "output_text", "") or "").strip()
        success = text.strip() == "OpenAI connection successful."
        print(f"Plain Text API Call: {'Success' if success else 'Failed'}")
        print(f"Model Used: {selection.selected_model}")
        print("Safe Error Type: None" if success else "Safe Error Type: UnexpectedResponse")
        print("Safe Error Code: Unavailable")
        print("HTTP Status: Unavailable")
        return 0 if success else 1
    except ImportError:
        print("Plain Text API Call: Failed")
        print(f"Model Used: {selection.selected_model}")
        print("Safe Error Type: OpenAINotInstalledError")
        print("Safe Error Code: Unavailable")
        print("HTTP Status: Unavailable")
        return 1
    except Exception as exc:
        print("Plain Text API Call: Failed")
        print(f"Model Used: {selection.selected_model}")
        print(f"Safe Error Type: {exc.__class__.__name__}")
        print(f"Safe Error Code: {safe_error_code(exc)}")
        print(f"HTTP Status: {safe_http_status(exc)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
