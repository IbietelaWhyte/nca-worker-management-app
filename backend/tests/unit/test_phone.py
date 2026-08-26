import pytest

from app.core.phone import normalize_phone, try_normalize_phone


class TestNormalizePhone:
    @pytest.mark.parametrize(
        "raw",
        [
            "+14165550101",
            "14165550101",
            "4165550101",
            "(416) 555-0101",
            "416-555-0101",
            "416.555.0101",
            "  416 555 0101  ",
            "+1 (416) 555-0101",
        ],
    )
    def test_accepts_the_formats_people_actually_type(self, raw):
        # Every one of these reaches Twilio as the same number, so all must normalize identically.
        assert normalize_phone(raw) == "+14165550101"

    def test_preserves_a_non_default_country_code(self):
        assert normalize_phone("+442071838750") == "+442071838750"

    @pytest.mark.parametrize("raw", ["", "   ", "banana", "555", "416555010", "abc4165550101", "+"])
    def test_rejects_unusable_values(self, raw):
        with pytest.raises(ValueError):
            normalize_phone(raw)

    def test_rejects_too_many_digits(self):
        with pytest.raises(ValueError, match="16 digits"):
            normalize_phone("+1234567890123456")

    def test_error_message_echoes_the_input(self):
        # The message is shown to a volunteer fixing a spreadsheet, so it must name the bad value.
        with pytest.raises(ValueError, match="'555'"):
            normalize_phone("555")


class TestTryNormalizePhone:
    def test_returns_none_instead_of_raising(self):
        # Used against values already in the database, which predate normalization.
        assert try_normalize_phone("banana") is None
        assert try_normalize_phone(None) is None
        assert try_normalize_phone("") is None

    def test_normalizes_when_it_can(self):
        assert try_normalize_phone("(416) 555-0101") == "+14165550101"
