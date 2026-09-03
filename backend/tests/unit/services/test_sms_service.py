from unittest.mock import patch

import pytest

from app.service.sms.service import SMSService

URL = "https://app.example.com/confirm/abc"


@pytest.fixture
def service():
    # The Twilio client reaches out on construction; nothing here sends, so stub it out.
    with patch("app.service.sms.service.TwilioClient"):
        yield SMSService()


def notice_body(service, duties) -> str:
    """Send a notice and return the body that reached send_sms."""
    with patch.object(SMSService, "send_sms", return_value=True) as send:
        service.send_assignment_notice(
            to="+14165550101",
            worker_name="Ada",
            duties=duties,
            confirmation_url=URL,
        )
    return str(send.call_args.args[1])


class TestAssignmentNoticeBody:
    """The exact strings, because these go to real phones and nothing downstream inspects them."""

    def test_a_single_date_names_its_department(self, service):
        body = notice_body(service, [("Ushering", "Sun 02 Aug at 09:00")])
        assert body == (
            "Hi Ada, you have been scheduled for Sun 02 Aug at 09:00 in Ushering. "
            f"Please confirm or decline here: {URL}"
        )

    def test_several_dates_in_one_department_name_it_once(self, service):
        body = notice_body(
            service,
            [("Ushering", "Sun 02 Aug at 09:00"), ("Ushering", "Sun 09 Aug at 09:00")],
        )
        assert "you have been scheduled for 2 dates - Ushering: Sun 02 Aug at 09:00, Sun 09 Aug at 09:00." in body
        assert body.count("Ushering") == 1

    def test_several_departments_are_grouped_separately(self, service):
        body = notice_body(
            service,
            [
                ("Ushering", "Sun 02 Aug at 09:00"),
                ("Choir", "Sun 09 Aug at 09:00"),
                ("Ushering", "Sun 16 Aug at 09:00"),
            ],
        )
        assert (
            "you have been scheduled for 3 dates - "
            "Ushering: Sun 02 Aug at 09:00, Sun 16 Aug at 09:00; Choir: Sun 09 Aug at 09:00." in body
        )

    def test_an_unnameable_department_falls_back_to_dates_only(self, service):
        # Rather than a dangling ": ". The notice still has to go out.
        body = notice_body(service, [("", "Sun 02 Aug at 09:00"), ("Choir", "Sun 09 Aug at 09:00")])
        assert "you have been scheduled for 2 dates: Sun 02 Aug at 09:00, Sun 09 Aug at 09:00." in body
        assert "Choir" not in body

    def test_a_lone_unnameable_department_still_reads_as_a_sentence(self, service):
        body = notice_body(service, [("", "Sun 02 Aug at 09:00")])
        assert body == (
            f"Hi Ada, you have been scheduled for Sun 02 Aug at 09:00. Please confirm or decline here: {URL}"
        )

    @pytest.mark.parametrize(
        "duties",
        [
            [("Ushering", "Sun 02 Aug at 09:00")],
            [("Ushering", "Sun 02 Aug at 09:00"), ("Choir", "Sun 09 Aug at 09:00")],
            [("", "Sun 02 Aug at 09:00")],
        ],
    )
    def test_the_body_stays_inside_gsm_7(self, service, duties):
        # A character outside GSM-7 (an em dash, a curly quote) silently switches the whole message
        # to UCS-2, which cuts a segment from 160 characters to 70 and doubles the cost of a long
        # roster. The separator between groups is a plain hyphen for exactly this reason.
        gsm7 = set(
            "@£$¥èéùìòÇØøÅå_ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
            "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
            "\n\r\f^{}\\[~]|€"
        )
        body = notice_body(service, duties)
        assert not (set(body) - gsm7), f"non-GSM-7 characters: {sorted(set(body) - gsm7)}"
