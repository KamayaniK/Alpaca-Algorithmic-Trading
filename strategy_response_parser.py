
"""Parse MCP indicator responses into trading research signals."""

import json

from trading_strategy import generate_signal


def analyze_indicator_response(response_text: str) -> dict:
    """Parse an MCP response and fail safely to HOLD on invalid input."""
    try:
        payload = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return {
            "signal": "HOLD",
            "reason": "MCP response is not valid JSON.",
            "risk_flags": ["Invalid JSON response"],
            "evidence": {},
        }

    if not isinstance(payload, dict):
        return {
            "signal": "HOLD",
            "reason": "MCP response must be a JSON object.",
            "risk_flags": ["Invalid response format"],
            "evidence": {},
        }

    if payload.get("error"):
        return {
            "ticker": payload.get("ticker"),
            "signal": "HOLD",
            "reason": "Indicator tool returned an error.",
            "risk_flags": [str(payload["error"])],
            "evidence": {},
        }

    ticker = payload.get("ticker")
    indicators = payload.get("latest_indicators")

    if not isinstance(ticker, str) or not ticker.strip():
        return {
            "signal": "HOLD",
            "reason": "Indicator response has an invalid ticker.",
            "risk_flags": ["Invalid MCP response"],
            "evidence": {},
        }

    if not isinstance(indicators, dict):
        return {
            "ticker": ticker.strip().upper(),
            "signal": "HOLD",
            "reason": "Indicator response has an unexpected format.",
            "risk_flags": ["Invalid MCP response"],
            "evidence": {},
        }

    result = generate_signal(indicators)
    return {"ticker": ticker.strip().upper(), **result}
