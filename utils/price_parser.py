"""Price parser that prefers currency-linked amounts over arbitrary numbers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from utils.logger import get_logger

logger = get_logger(__name__)

_FREE_TOKENS = ("free", "free shipping")
_NUMBER_PATTERN = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?"
_CURRENCY_PREFIX = re.compile(
    rf"(?P<currency>US\s*\$|USD|ILS|EUR|GBP|\$)\s*(?P<amount>{_NUMBER_PATTERN})",
    re.IGNORECASE,
)
_CURRENCY_SUFFIX = re.compile(
    rf"(?P<amount>{_NUMBER_PATTERN})\s*(?P<currency>USD|ILS|EUR|GBP)",
    re.IGNORECASE,
)
_ANY_NUMBER = re.compile(_NUMBER_PATTERN)
_CURRENCY_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "ILS": "ILS",
    "EUR": "EUR",
    "GBP": "GBP",
}


@dataclass(frozen=True)
class ParsedPrice:
    """A parsed monetary value extracted from UI text."""

    amount: float
    currency: str
    raw_text: str
    matched_text: str


def parse_price_info(
    text: str,
    *,
    preferred_currency: str | None = None,
    required_currency: str | None = None,
) -> ParsedPrice:
    """Parse UI text into a single monetary amount."""
    if not text or not text.strip():
        raise ValueError("Cannot parse price from empty text")

    normalized = text.strip()
    lowered = normalized.lower()
    if lowered in _FREE_TOKENS or "free shipping" in lowered:
        return ParsedPrice(
            amount=0.0,
            currency="USD",
            raw_text=text,
            matched_text=normalized,
        )

    currency_matches = _extract_currency_matches(normalized)
    if currency_matches:
        chosen = _choose_currency_match(
            currency_matches,
            preferred_currency=preferred_currency,
            required_currency=required_currency,
        )
        if chosen is None:
            raise ValueError(f"Could not find required currency in '{text}'")

        amount_text, currency_code, matched_text = chosen
        return ParsedPrice(
            amount=float(amount_text.replace(",", "")),
            currency=currency_code,
            raw_text=text,
            matched_text=matched_text,
        )

    numeric_matches = _ANY_NUMBER.findall(normalized)
    if not numeric_matches:
        raise ValueError(f"Cannot parse a numerical amount from '{text}'")

    # Fallback: prefer the last number so strings like "Subtotal (5 items) 438.90"
    # resolve to the monetary amount rather than the item count.
    amount_text = numeric_matches[-1]
    return ParsedPrice(
        amount=float(amount_text.replace(",", "")),
        currency=preferred_currency or required_currency or "USD",
        raw_text=text,
        matched_text=amount_text,
    )


def _extract_currency_matches(text: str) -> list[tuple[str, str, str]]:
    matches: list[tuple[int, str, str, str]] = []

    for match in _CURRENCY_PREFIX.finditer(text):
        currency_code = _normalize_currency(match.group("currency"))
        matches.append(
            (match.start(), match.group("amount"), currency_code, match.group(0))
        )

    for match in _CURRENCY_SUFFIX.finditer(text):
        currency_code = _normalize_currency(match.group("currency"))
        matches.append(
            (match.start(), match.group("amount"), currency_code, match.group(0))
        )

    matches.sort(key=lambda item: item[0])
    return [(amount, currency, matched_text) for _, amount, currency, matched_text in matches]


def _choose_currency_match(
    matches: list[tuple[str, str, str]],
    *,
    preferred_currency: str | None,
    required_currency: str | None,
) -> tuple[str, str, str] | None:
    if required_currency:
        for match in matches:
            if match[1] == required_currency:
                return match
        return None

    if preferred_currency:
        for match in matches:
            if match[1] == preferred_currency:
                return match

    return matches[0]


def _normalize_currency(token: str) -> str:
    compact = re.sub(r"\s+", "", token.upper())
    return _CURRENCY_MAP.get(compact, compact)
