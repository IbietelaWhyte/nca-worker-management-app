from app.repository.filters import quote_postgrest_value


class TestQuotePostgrestValue:
    def test_wraps_benign_value_in_quotes(self):
        assert quote_postgrest_value("%john%") == '"%john%"'

    def test_neutralizes_reserved_characters(self):
        # Commas/dots/parens are the PostgREST filter delimiters. A naive interpolation of this
        # payload would inject a second condition; wrapping it in quotes makes it inert literal data.
        payload = "%a,phone.eq.x()%"
        assert quote_postgrest_value(payload) == '"%a,phone.eq.x()%"'

    def test_escapes_embedded_double_quote(self):
        assert quote_postgrest_value('a"b') == '"a\\"b"'

    def test_escapes_embedded_backslash(self):
        assert quote_postgrest_value("a\\b") == '"a\\\\b"'

    def test_escapes_backslash_before_quote(self):
        # Backslash is escaped first so it cannot combine with the quote escaping to break out.
        assert quote_postgrest_value('a\\"b') == '"a\\\\\\"b"'

    def test_empty_string(self):
        assert quote_postgrest_value("") == '""'
