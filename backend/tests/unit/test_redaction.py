from app.core.redaction import mask_email, mask_phone


class TestMaskEmail:
    def test_masks_local_part_keeps_domain(self):
        assert mask_email("john.doe@example.com") == "j***@example.com"

    def test_short_local_part(self):
        assert mask_email("a@b.com") == "a***@b.com"

    def test_non_email_value(self):
        assert mask_email("notanemail") == "n***"

    def test_none_and_empty(self):
        assert mask_email(None) == "<none>"
        assert mask_email("") == "<none>"


class TestMaskPhone:
    def test_keeps_last_four_digits(self):
        assert mask_phone("+14165550101") == "***0101"

    def test_short_value(self):
        assert mask_phone("12") == "***"

    def test_none(self):
        assert mask_phone(None) == "***"
