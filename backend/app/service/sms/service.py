import math
import threading
import time
from enum import Enum

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.core.config import settings
from app.core.exceptions import TooManyRequestsError
from app.core.logging import get_logger
from app.core.redaction import mask_phone
from app.repository.workers.repository import WorkerRepository

logger = get_logger(__name__)

# When each manual bulk send last went out, keyed by what it texted. Module-level because the
# service is built per request; per-process and lost on restart, like the feedback limiter — a
# guard against a repeated button, not an audit trail.
_manual_sends: dict[str, float] = {}
_manual_sends_lock = threading.Lock()

# Twilio errors that no retry can fix, because they are about the recipient's number: 21610 the
# person replied STOP, 21211 the number is invalid, 21614 it is not a mobile. Retrying one used to
# re-send every notice_interval_minutes until the duty date passed. 21408 (region not enabled) is
# deliberately absent - it is this account's configuration, not the person, and fixing it in the
# Twilio console should not leave a list of workers to unblock by hand.
PERMANENT_ERROR_CODES = frozenset({21610, 21211, 21614})


class SendResult(Enum):
    """How a send ended. Truthy only when it went out, so `if not sent:` still reads naturally."""

    SENT = "sent"
    FAILED = "failed"  # Worth retrying: a network blip, a Twilio outage, a rate limit.
    BLOCKED = "blocked"  # Never worth retrying; the number has been marked on its workers.

    def __bool__(self) -> bool:
        return self is SendResult.SENT


class SMSService:
    def __init__(self, worker_repo: WorkerRepository) -> None:
        """Initialize the SMSService with Twilio client configuration.

        Loads Twilio credentials from application settings and creates
        a Twilio client for sending SMS messages.

        Args:
            worker_repo: Repository for workers, to mark a number Twilio permanently refused.
        """
        self.worker_repo = worker_repo
        self.client = TwilioClient(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        self.from_number = settings.twilio_from_number

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="SMSService")

    def claim_manual_send(self, key: str) -> None:
        """Refuse a hand-triggered bulk send repeated within the cooldown; otherwise record it.

        Args:
            key: What is being texted, e.g. "schedule:<id>" or "prompt:<department id>".

        Raises:
            TooManyRequestsError: If the same send went out less than
                `settings.manual_send_cooldown_minutes` ago.
        """
        window = settings.manual_send_cooldown_minutes * 60
        now = time.monotonic()
        with _manual_sends_lock:
            last = _manual_sends.get(key)
            if last is not None and now - last < window:
                minutes = math.ceil((window - (now - last)) / 60)
                raise TooManyRequestsError(
                    f"These texts went out a few minutes ago. You can send them again in {minutes} "
                    f"minute{'s' if minutes != 1 else ''}."
                )
            _manual_sends[key] = now

    def send_sms(self, to: str, body: str) -> SendResult:
        """Send an SMS message to a phone number.

        A permanent refusal (see `PERMANENT_ERROR_CODES`) is recorded on every worker with this
        number, here rather than in each caller, so that every path - notice, reminder, prompt,
        cancellation - stops retrying it at once. The notification RPCs skip a marked worker.

        Args:
            to: Recipient phone number in E.164 format (e.g., +14165551234).
            body: Message text to send.

        Returns:
            SendResult: SENT, FAILED (worth retrying) or BLOCKED (never worth retrying).
        """
        # bind the method and masked recipient for better traceability in logs
        log = self.logger.bind(method="send_sms", to=mask_phone(to))
        log.info("attempting_to_send_sms", body_length=len(body))
        try:
            message = self.client.messages.create(  # type: ignore[no-untyped-call]
                to=to,
                from_=self.from_number,
                body=body,
            )
            log.info("sms_sent", sid=message.sid)
            return SendResult.SENT
        except TwilioRestException as e:
            if e.code not in PERMANENT_ERROR_CODES:
                log.error("sms_failed", error=str(e), error_code=e.code)
                return SendResult.FAILED
            log.warning("sms_recipient_blocked", error_code=e.code)
            try:
                self.worker_repo.mark_sms_blocked(to, e.code)
            except Exception as mark_error:
                # The send is still refused; the next attempt will try to record it again.
                log.error("sms_block_not_recorded", error=str(mark_error))
            return SendResult.BLOCKED
        except Exception as e:
            log.error("sms_failed", error=str(e))
            return SendResult.FAILED

    def send_reminder(
        self,
        to: str,
        worker_name: str,
        duties: list[tuple[str, str]],
    ) -> SendResult:
        """Remind a worker of every duty whose lead time falls today, in one message.

        The message is a statement, not a question. Nothing consumes inbound SMS — there is no
        Twilio webhook — so anything that invited a reply would invite one nobody reads. A worker
        who cannot make a date speaks to their head of department, who edits the rota.

        It takes a list for the same reason the notice does, and more urgently: a schedule now
        reminds at several lead times, so a ladder of three against four Sundays could put twelve
        separate texts on one phone in a month.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker receiving the reminder.
            duties: (department name, human-readable date) pairs, soonest first.

        Returns:
            SendResult: Whether the reminder went out; see `send_sms`.
        """
        body = f"Hi {worker_name}, a reminder that you are scheduled for {self._describe_duties(duties)}."
        self.logger.info("sending_reminder", to=mask_phone(to), dates=len(duties))
        return self.send_sms(to, body)

    def send_availability_prompt(
        self,
        to: str,
        worker_name: str,
        department_name: str,
        availability_url: str,
    ) -> SendResult:
        """Ask a worker for the dates they CANNOT serve.

        The question is asked negatively because the rota already answers it that way: a worker
        with no record at all is treated as available, so asking who is free collects an opinion
        nothing acts on, and someone who ignores the text is scheduled either way. Asking for the
        exceptions means silence and "I am free" say the same thing, which is what the volunteers
        who saw this expected.

        "No reply means you are free" is in the message rather than only on the page: most people
        read the SMS and never tap through, so the one who does nothing has to understand what
        doing nothing means.

        The link is deliberately token-based rather than pointing at the app: most workers have
        no login account, so a link to a sign-in page would reach almost nobody.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker being asked.
            department_name: The department asking.
            availability_url: Public link to the page where they mark themselves off.

        Returns:
            SendResult: Whether the prompt went out; see `send_sms`.
        """
        # Every character stays inside GSM-7, and the wording is kept short, so a name, a
        # department and a link still fit one 160-character segment. CANNOT is capitalised
        # because it is the single word that inverts the question this used to ask, and SMS
        # has no other way to stress it.
        body = (
            f"Hi {worker_name}, tell {department_name} any dates you CANNOT serve. "
            f"No reply means you are free: {availability_url}"
        )
        self.logger.info("sending_availability_prompt", to=mask_phone(to))
        return self.send_sms(to, body)

    def send_assignment_notice(
        self,
        to: str,
        worker_name: str,
        duties: list[tuple[str, str]],
    ) -> SendResult:
        """Tell a worker they have been scheduled, covering every date in one message.

        Sent shortly after a schedule is created, well before the pre-service reminder, so the
        worker has time to arrange cover if they cannot make a date. Monthly generation rosters
        somebody onto four or five Sundays at once, hence one message listing all of them rather
        than one text per date.

        Dates are grouped under their department rather than repeating the department per date: a
        worker can serve in more than one, and somebody on every Sunday of a month in a single
        department should not have to read its name five times.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker being notified.
            duties: (department name, human-readable date) pairs, soonest first. A pair rather than
                two parallel lists so a date cannot drift onto the wrong department.

        Returns:
            SendResult: Whether the notice went out; see `send_sms`.
        """
        body = f"Hi {worker_name}, you have been scheduled for {self._describe_duties(duties)}."
        self.logger.info("sending_assignment_notice", to=mask_phone(to), dates=len(duties))
        return self.send_sms(to, body)

    def send_assignment_cancelled(self, to: str, worker_name: str, department_name: str, when: str) -> SendResult:
        """Tell a worker they have been taken off a date.

        **The only message in the system with no retry.** The notice and the reminder are both
        swept from a database row, so a Twilio failure is picked up on the next run; here the
        assignment is already gone, and there is nothing left to sweep. A failure is reported
        back to the head as a warning so they can pass the word on themselves.

        "No action needed" is in the body because the first thing a volunteer wonders is
        whether they owe a reply. There is no inbound webhook, so anything question-shaped
        would go unread.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker being stood down.
            department_name: The department the duty was in; "" drops the framing.
            when: Human-readable date and time, e.g. "Sun 02 Aug at 09:00".

        Returns:
            SendResult: Whether the message went out; see `send_sms`.
        """
        # A department we could not name would render as a dangling " in ", so drop it rather
        # than half-applying it — the same rule _describe_duties follows.
        duty = f"{when} in {department_name}" if department_name else when
        body = f"Hi {worker_name}, you are no longer scheduled for {duty}. No action needed."
        self.logger.info("sending_assignment_cancelled", to=mask_phone(to))
        return self.send_sms(to, body)

    def send_duties_cancelled(self, to: str, worker_name: str, duties: list[tuple[str, str]]) -> SendResult:
        """Tell a worker several of their dates are gone, in one message.

        Deleting a month of finalized rotas would otherwise send one text per date to the same
        person. Like `send_assignment_cancelled` there is no retry behind it - the rows are gone -
        so a failure is reported back to the head.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker being stood down.
            duties: (department name, human-readable date) pairs, soonest first.

        Returns:
            SendResult: Whether the message went out; see `send_sms`.
        """
        body = f"Hi {worker_name}, you are no longer scheduled for {self._describe_duties(duties)}. No action needed."
        self.logger.info("sending_duties_cancelled", to=mask_phone(to), dates=len(duties))
        return self.send_sms(to, body)

    @staticmethod
    def _describe_duties(duties: list[tuple[str, str]]) -> str:
        """Render a worker's dates as an object phrase, e.g. "Sun 02 Aug at 09:00 in Ushering".

        Deliberately carries no verb: the notice announces ("you have been scheduled for ...") and
        the reminder recalls ("a reminder that you are scheduled for ..."), but the list of dates
        in between is the same list, and it is the part with the formatting traps in it.

        Every character here stays inside GSM-7. An em dash (or any other character outside it)
        forces the whole message to UCS-2, which halves a segment from 160 characters to 70 and so
        silently doubles the cost of a long roster.

        Args:
            duties: (department name, human-readable date) pairs, soonest first.

        Returns:
            str: The phrase, with neither a leading verb nor a trailing full stop.
        """
        dates = [when for _, when in duties]

        # A department we could not name would render as a dangling ": ", so drop the department
        # framing entirely rather than half-applying it. The message itself still has to go out.
        if any(not department for department, _ in duties):
            if len(dates) == 1:
                return dates[0]
            return f"{len(dates)} dates: {', '.join(dates)}"

        if len(duties) == 1:
            department, when = duties[0]
            return f"{when} in {department}"

        by_department: dict[str, list[str]] = {}
        for department, when in duties:
            by_department.setdefault(department, []).append(when)
        groups = "; ".join(f"{department}: {', '.join(whens)}" for department, whens in by_department.items())
        return f"{len(duties)} dates - {groups}"
