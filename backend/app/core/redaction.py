"""Helpers for masking personally identifiable information (PII) in logs.

Logs ship to stdout/aggregators, so emails and phone numbers must be masked before being logged.
These helpers keep just enough of a value to be useful for tracing/debugging while removing the
identifying parts.
"""


def mask_email(value: str | None) -> str:
    """Mask an email address for safe logging, keeping the first character and the domain.

    Examples: ``"john.doe@example.com"`` -> ``"j***@example.com"``; an empty/None value -> ``"<none>"``.

    Args:
        value: The email address to mask, or None.

    Returns:
        str: The masked email, or ``"<none>"`` when no value is provided.
    """
    if not value:
        return "<none>"
    local, sep, domain = value.partition("@")
    if not sep:
        # Not an email shape; mask everything but the first character.
        return f"{value[0]}***"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str | None) -> str:
    """Mask a phone number for safe logging, keeping only the last 4 digits.

    Examples: ``"+14165550101"`` -> ``"***0101"``; a short/None value -> ``"***"``.

    Args:
        value: The phone number to mask, or None.

    Returns:
        str: The masked phone number.
    """
    if not value or len(value) < 4:
        return "***"
    return f"***{value[-4:]}"
