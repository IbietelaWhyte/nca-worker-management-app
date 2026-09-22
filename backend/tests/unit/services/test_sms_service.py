from unittest.mock import patch

import pytest

from app.service.sms.service import SMSService

PROMPT_URL = "https://app.example.com/availability/abc"

# A character outside this alphabet silently switches the whole message to UCS-2, which cuts a
# segment from 160 characters to 70 and so doubles or triples the cost of a long message.
GSM7 = set(
    "@£$¥èéùìòÇØøÅå_ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
    "\n\r\f^{}\\[~]|€"
)


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
        )
    return str(send.call_args.args[1])


class TestAssignmentNoticeBody:
    """The exact strings, because these go to real phones and nothing downstream inspects them."""

    def test_a_single_date_names_its_department(self, service):
        body = notice_body(service, [("Ushering", "Sun 02 Aug at 09:00")])
        assert body == "Hi Ada, you have been scheduled for Sun 02 Aug at 09:00 in Ushering."

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
        assert body == "Hi Ada, you have been scheduled for Sun 02 Aug at 09:00."

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
        body = notice_body(service, duties)
        assert not (set(body) - GSM7), f"non-GSM-7 characters: {sorted(set(body) - GSM7)}"


def reminder_body(service, duties=None) -> str:
    """Send a pre-service reminder and return the body that reached send_sms."""
    with patch.object(SMSService, "send_sms", return_value=True) as send:
        service.send_reminder(
            to="+14165550101",
            worker_name="Ada",
            duties=duties if duties is not None else [("Ushering", "Sun 02 Aug at 09:00")],
        )
    return str(send.call_args.args[1])


class TestReminderBody:
    """Untested until the confirmation link came out of it, which is how the tail survived so long."""

    def test_it_is_a_statement_with_nothing_to_answer(self, service):
        # No link and no "reply CONFIRM": there is no Twilio inbound webhook, so anything that
        # invited a reply would invite one nobody reads.
        assert reminder_body(service) == (
            "Hi Ada, a reminder that you are scheduled for Sun 02 Aug at 09:00 in Ushering."
        )

    def test_several_due_dates_arrive_as_one_sentence(self, service):
        # A ladder of lead times across a month of Sundays is what makes this a list rather than
        # a single date: the sweep groups a person's due duties, so the body has to carry them.
        body = reminder_body(
            service,
            [("Ushering", "Sun 02 Aug at 09:00"), ("Ushering", "Sun 09 Aug at 09:00")],
        )
        assert body == (
            "Hi Ada, a reminder that you are scheduled for "
            "2 dates - Ushering: Sun 02 Aug at 09:00, Sun 09 Aug at 09:00."
        )

    def test_an_unnameable_department_still_reads_as_a_sentence(self, service):
        assert reminder_body(service, [("", "Sun 02 Aug at 09:00")]) == (
            "Hi Ada, a reminder that you are scheduled for Sun 02 Aug at 09:00."
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
        body = reminder_body(service, duties)
        assert not (set(body) - GSM7), f"non-GSM-7 characters: {sorted(set(body) - GSM7)}"


def prompt_body(service, worker_name="Ada", department_name="Ushering", url=PROMPT_URL) -> str:
    """Send an availability prompt and return the body that reached send_sms."""
    with patch.object(SMSService, "send_sms", return_value=True) as send:
        service.send_availability_prompt(
            to="+14165550101",
            worker_name=worker_name,
            department_name=department_name,
            availability_url=url,
        )
    return str(send.call_args.args[1])


class TestAvailabilityPromptBody:
    """The exact string, because this is the whole feature for anyone without a login account."""

    def test_it_asks_for_the_dates_they_cannot_serve(self, service):
        # Negative, and unambiguously so. The rota treats an unrecorded date as available, so a
        # message asking who is free collects an answer nothing acts on.
        assert prompt_body(service) == (
            f"Hi Ada, tell Ushering any dates you CANNOT serve. No reply means you are free: {PROMPT_URL}"
        )

    def test_it_says_what_doing_nothing_means(self, service):
        # Most people read the text and never tap through, so the one who ignores it has to
        # learn from the message itself that silence counts as "I am free".
        assert "No reply means you are free" in prompt_body(service)

    def test_the_body_stays_inside_gsm_7(self, service):
        body = prompt_body(service)
        assert not (set(body) - GSM7), f"non-GSM-7 characters: {sorted(set(body) - GSM7)}"

    def test_the_wording_stays_within_its_character_budget(self, service):
        # A second segment doubles the cost of prompting a whole department, every month. Name,
        # department and URL are all out of this code's hands — a 36-character token alone eats
        # half a segment — so what is guarded is the wording itself, which is the only part a
        # future edit can inflate. 70 is a little above today's 68: enough to reword, not enough
        # to add a sentence.
        body = prompt_body(service, worker_name="", department_name="", url="")
        assert len(body) <= 70, f"the fixed wording now costs {len(body)} characters: {body!r}"

    def test_a_typical_prompt_fits_one_segment(self, service):
        # The ordinary case: a first name, a short department, and a link on a real host.
        body = prompt_body(
            service,
            worker_name="Ada",
            department_name="Ushering",
            url="https://rota.example.ca/availability/" + "0" * 36,
        )
        assert len(body) <= 160, f"{len(body)} characters spills into a second segment: {body}"
