"""Phone number normalization to E.164.

``SMSService`` requires E.164 (``+14165551234``) but nothing upstream historically enforced it, so
numbers typed as ``(416) 555-0101`` reached Twilio unchanged and failed silently at send time. Every
phone number entering the system should pass through :func:`normalize_phone` first.

Deliberately hand-rolled rather than depending on ``phonenumbers``: this app serves one congregation in
one country. Swap in ``phonenumbers`` if that ever stops being true.
"""

import re

from app.core.config import settings

# Characters people habitually type inside phone numbers that carry no meaning.
_SEPARATORS = re.compile(r"[\s\-().]")
_DIGITS_ONLY = re.compile(r"^\d+$")

# E.164 allows at most 15 digits including the country code. The lower bound is a sanity floor:
# no real country code + subscriber number is shorter than 8 digits.
MIN_E164_DIGITS = 8
MAX_E164_DIGITS = 15


def normalize_phone(value: str) -> str:
    """Normalize a human-typed phone number to E.164.

    Accepts the formats people actually type — ``(416) 555-0101``, ``416-555-0101``, ``4165550101``,
    ``+1 416 555 0101`` — and returns ``+14165550101`` for all of them. A number given without a
    country code is assumed to be in ``settings.default_phone_country_code``.

    Args:
        value: The phone number as entered.

    Returns:
        str: The number in E.164 format, e.g. ``+14165550101``.

    Raises:
        ValueError: If the number cannot be interpreted, with a message safe to show a user.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Phone number is required")

    cleaned = _SEPARATORS.sub("", raw)
    country_code = settings.default_phone_country_code  # e.g. "+1"
    country_digits = country_code.lstrip("+")

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif _DIGITS_ONLY.match(cleaned) and len(cleaned) == 10:
        # A bare local number — assume the configured country.
        digits = f"{country_digits}{cleaned}"
    elif _DIGITS_ONLY.match(cleaned) and cleaned.startswith(country_digits):
        # Country code typed without the leading "+", e.g. "14165550101".
        digits = cleaned
    else:
        raise ValueError(f"'{raw}' is not a valid phone number — use 10 digits or +1 416 555 0101")

    if not _DIGITS_ONLY.match(digits):
        raise ValueError(f"'{raw}' is not a valid phone number — it contains letters or symbols")
    if not MIN_E164_DIGITS <= len(digits) <= MAX_E164_DIGITS:
        raise ValueError(f"'{raw}' is not a valid phone number — it has {len(digits)} digits")

    return f"+{digits}"


def try_normalize_phone(value: str | None) -> str | None:
    """Normalize a phone number, returning None instead of raising when it cannot be interpreted.

    For comparing against values already stored in the database, which predate normalization and may
    be in any format (or absent entirely).

    Args:
        value: The phone number to normalize, or None.

    Returns:
        str | None: The E.164 number, or None if it is missing or unparseable.
    """
    if not value:
        return None
    try:
        return normalize_phone(value)
    except ValueError:
        return None
