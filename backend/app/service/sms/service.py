from twilio.rest import Client as TwilioClient

from app.core.config import settings
from app.core.logging import get_logger

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
        # bind the method and recipient for better traceability in logs
        log = self.logger.bind(method="send_sms", to=to)
        log.debug("attempting_to_send_sms", body=body)
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
        if confirmation_url:
            body = (
                f"Hi {worker_name}, you are scheduled for '{schedule_title}' "
                f"on {scheduled_date} at {start_time}. "
                f"Confirm or decline here: {confirmation_url}"
            )
        else:
            body = (
                f"Hi {worker_name}, this is a reminder that you are scheduled for "
                f"'{schedule_title}' on {scheduled_date} at {start_time}. "
                f"Please reply CONFIRM or DECLINE."
            )
        self.logger.debug(
            "sending_reminder",
            to=to,
            worker_name=worker_name,
            scheduled_date=scheduled_date,
        )
        return self.send_sms(to, body)
