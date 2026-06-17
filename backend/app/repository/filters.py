"""Helpers for building PostgREST filter expressions safely.

PostgREST parses filter expressions such as ``or=(col.ilike.value,col2.ilike.value)`` where commas
separate conditions, ``()`` group them, and values are dot-delimited (``column.operator.value``).
User-supplied data embedded into these expressions must be escaped so it cannot alter the filter
structure.
"""


def quote_postgrest_value(value: str) -> str:
    """Escape and double-quote a value for safe embedding in a PostgREST or()/filter string.

    Wrapping the value in double quotes makes PostgREST treat reserved characters (',', '.', ':',
    '(', ')') as literal data rather than filter syntax, preventing filter injection. Embedded
    backslashes and double quotes are escaped first so they cannot terminate the quoted value.

    Args:
        value: The raw (possibly user-supplied) value to embed in a filter expression.

    Returns:
        str: The value with backslashes and double quotes escaped, wrapped in double quotes.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
