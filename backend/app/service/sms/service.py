from twilio.rest import Client as TwilioClient

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redaction import mask_phone

logger = get_logger(__name__)


class SMSService:
    def __init__(self) -> None:
        """Initialize the SMSService with Twilio client configuration.

        Loads Twilio credentials from application settings and creates
        a Twilio client for sending SMS messages.
        """
        self.client = TwilioClient(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        self.from_number = settings.twilio_from_number

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="SMSService")

    def send_sms(self, to: str, body: str) -> bool:
        """Send an SMS message to a phone number.

        Args:
            to: Recipient phone number in E.164 format (e.g., +14165551234).
            body: Message text to send.

        Returns:
            bool: True if message sent successfully, False if sending failed.
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
            return True
        except Exception as e:
            log.error("sms_failed", error=str(e))
            return False

    def send_reminder(
        self,
        to: str,
        worker_name: str,
        schedule_title: str,
        scheduled_date: str,
        start_time: str,
        confirmation_url: str | None = None,
    ) -> bool:
        """Send a schedule reminder SMS to a worker.

        Formats and sends a reminder message with schedule details. When a
        confirmation_url is provided the message includes a link for the worker
        to confirm or decline; otherwise it falls back to a plain-text prompt.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker receiving the reminder.
            schedule_title: Title/name of the scheduled event.
            scheduled_date: Date of the scheduled event.
            start_time: Start time of the scheduled event.
            confirmation_url: Optional one-time confirmation link to embed in the SMS.

        Returns:
            bool: True if reminder sent successfully, False if sending failed.
        """
        body = (
            f"Hi {worker_name}, a reminder that you are scheduled for '{schedule_title}' "
            f"on {scheduled_date} at {start_time}."
        )
        # Nothing consumes inbound SMS — there is no Twilio webhook — so without a link there is
        # no action to offer. Saying "reply CONFIRM" would promise a reply nobody reads.
        if confirmation_url:
            body += f" Confirm or decline here: {confirmation_url}"
        self.logger.info(
            "sending_reminder",
            to=mask_phone(to),
            scheduled_date=scheduled_date,
        )
        return self.send_sms(to, body)

    def send_availability_prompt(
        self,
        to: str,
        worker_name: str,
        department_name: str,
        availability_url: str,
    ) -> bool:
        """Ask a worker to enter the dates they are available.

        The link is deliberately token-based rather than pointing at the app: most workers have
        no login account, so a link to a sign-in page would reach almost nobody.

        Args:
            to: Recipient phone number in E.164 format.
            worker_name: Name of the worker being asked.
            department_name: The department asking.
            availability_url: Public link to the page where they can set their dates.

        Returns:
            bool: True if the prompt was sent, False if sending failed.
        """
        body = (
            f"Hi {worker_name}, please let {department_name} know which dates you are available "
            f"to serve: {availability_url}"
        )
        self.logger.info("sending_availability_prompt", to=mask_phone(to))
        return self.send_sms(to, body)

    def send_assignment_notice(
        self,
        to: str,
        worker_name: str,
        duties: list[tuple[str, str]],
        confirmation_url: str,
    ) -> bool:
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
            confirmation_url: Link to the page where each date can be confirmed or declined.

        Returns:
            bool: True if the notice was sent, False if sending failed.
        """
        summary = self._describe_duties(duties)
        body = f"Hi {worker_name}, {summary}. Please confirm or decline here: {confirmation_url}"
        self.logger.info("sending_assignment_notice", to=mask_phone(to), dates=len(duties))
        return self.send_sms(to, body)

    @staticmethod
    def _describe_duties(duties: list[tuple[str, str]]) -> str:
        """Render the "you have been scheduled for ..." clause of an assignment notice.

        Every character here stays inside GSM-7. An em dash (or any other character outside it)
        forces the whole message to UCS-2, which halves a segment from 160 characters to 70 and so
        silently doubles the cost of a long roster.

        Args:
            duties: (department name, human-readable date) pairs, soonest first.

        Returns:
            str: The clause, without a trailing full stop.
        """
        dates = [when for _, when in duties]

        # A department we could not name would render as a dangling ": ", so drop the department
        # framing entirely rather than half-applying it. The notice itself still has to go out.
        if any(not department for department, _ in duties):
            if len(dates) == 1:
                return f"you have been scheduled for {dates[0]}"
            return f"you have been scheduled for {len(dates)} dates: {', '.join(dates)}"

        if len(duties) == 1:
            department, when = duties[0]
            return f"you have been scheduled for {when} in {department}"

        by_department: dict[str, list[str]] = {}
        for department, when in duties:
            by_department.setdefault(department, []).append(when)
        groups = "; ".join(f"{department}: {', '.join(whens)}" for department, whens in by_department.items())
        return f"you have been scheduled for {len(duties)} dates - {groups}"
