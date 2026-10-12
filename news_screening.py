"""Conservative Alpaca news screening for research signals.

Keyword-based first-pass screening, not a validated sentiment model.
Never places orders. API errors and inconclusive results fail closed.
"""
import os
import re
from datetime import datetime, timedelta, timezone

from alpaca.data.historical import NewsClient
from alpaca.data.requests import NewsRequest


SEVERE_NEGATIVE_PATTERNS = [
    r"\bbankruptcy\b",
    r"\binsolvency\b",
    r"\baccounting fraud\b",
    r"\bSEC investigation\b",
    r"\bcriminal investigation\b",
    r"\brestatement of financial results\b",
    r"\bgoing concern\b",
    r"\bproduct recall\b",
    r"\bclinical trial (?:failed|failure|halted)\b",
    r"\btrial (?:failed|failure|halted)\b",
    r"\bFDA rejects?\b",
    r"\bFDA rejection\b",
    r"\bearnings warning\b",
    r"\bwithdraws? (?:its )?guidance\b",
    r"\bslashes? (?:its )?guidance\b",
    r"\bmajor data breach\b",
    r"\bdefault(?:s|ed)? on (?:its )?debt\b",
    r"\bchapter 11\b",
]
COMPILED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in SEVERE_NEGATIVE_PATTERNS
]


def _result(
    status,
    *,
    checked_at,
    articles_checked=0,
    matched_headlines=None,
    reason="",
):
    return {
        "news_status": status,
        "news_check_passed": status == "CLEAR",
        "severe_negative_news": status == "SEVERE_NEGATIVE",
        "news_checked_at_utc": checked_at,
        "news_articles_checked": articles_checked,
        "news_matched_headlines": matched_headlines or [],
        "news_reason": reason,
    }


def _extract_articles(response):
    """Extract articles from Alpaca NewsSet or supported dictionary shapes."""
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            articles = data.get("news")
            if isinstance(articles, (list, tuple)):
                return list(articles)
        articles = response.get("news")
        if isinstance(articles, (list, tuple)):
            return list(articles)
        if isinstance(data, (list, tuple)):
            return list(data)
        return None

    data = getattr(response, "data", None)
    if isinstance(data, dict):
        articles = data.get("news")
        if isinstance(articles, (list, tuple)):
            return list(articles)
        return None
    if isinstance(data, (list, tuple)):
        return list(data)

    return None


def _field(article, name, default=""):
    if isinstance(article, dict):
        return article.get(name, default)
    return getattr(article, name, default)


def screen_news(ticker, *, lookback_hours=72, limit=50):
    """Screen recent news for one ticker; fail closed if screening is inconclusive."""
    now = datetime.now(timezone.utc)
    checked_at = now.isoformat()

    if not isinstance(ticker, str) or not ticker.strip():
        return _result(
            "UNAVAILABLE",
            checked_at=checked_at,
            reason="Ticker is missing or invalid.",
        )

    if (
        isinstance(lookback_hours, bool)
        or not isinstance(lookback_hours, int)
        or lookback_hours < 1
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
    ):
        return _result(
            "UNAVAILABLE",
            checked_at=checked_at,
            reason="lookback_hours and limit must be positive integers.",
        )

    ticker = ticker.strip().upper()
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        return _result(
            "UNAVAILABLE",
            checked_at=checked_at,
            reason="Alpaca API credentials are not configured.",
        )

    try:
        client = NewsClient(api_key, secret_key)
        request = NewsRequest(
            symbols=ticker,
            start=now - timedelta(hours=lookback_hours),
            end=now,
            limit=limit,
            sort="desc",
            include_content=False,
        )
        response = client.get_news(request)
        articles = _extract_articles(response)

        if articles is None:
            return _result(
                "UNAVAILABLE",
                checked_at=checked_at,
                reason="News API returned an unrecognized response format.",
            )

        if not articles:
            return _result(
                "UNAVAILABLE",
                checked_at=checked_at,
                reason="No news articles returned; screening is inconclusive.",
            )

        matched = []
        for article in articles:
            headline = str(_field(article, "headline", "") or "")
            summary = str(_field(article, "summary", "") or "")
            searchable_text = f"{headline}\n{summary}"

            rules = [
                pattern.pattern
                for pattern in COMPILED_PATTERNS
                if pattern.search(searchable_text)
            ]

            if rules:
                matched.append(
                    {
                        "headline": headline,
                        "url": str(_field(article, "url", "") or ""),
                        "created_at": str(_field(article, "created_at", "") or ""),
                        "matched_rules": rules,
                    }
                )

        if matched:
            return _result(
                "SEVERE_NEGATIVE",
                checked_at=checked_at,
                articles_checked=len(articles),
                matched_headlines=matched,
                reason="One or more articles matched a severe-negative keyword rule.",
            )

        return _result(
            "CLEAR",
            checked_at=checked_at,
            articles_checked=len(articles),
            reason=(
                "No configured severe-negative keywords matched the returned "
                "articles. This does not establish that the news is positive."
            ),
        )

    except Exception as exc:
        return _result(
            "UNAVAILABLE",
            checked_at=checked_at,
            reason=f"News screening failed: {type(exc).__name__}: {exc}",
        )
