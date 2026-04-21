"""
Email sending utility for the Sacramento County CoI Dashboard.

Uses only Python stdlib (smtplib + email.mime) — no external dependencies.
Defaults to Gmail SMTP with STARTTLS on port 587.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailSender:
    """
    Thin wrapper around smtplib for sending plain-text and HTML emails.

    Parameters
    ----------
    smtp_host : str
        SMTP server hostname.  Default: "smtp.gmail.com"
    smtp_port : int
        SMTP server port.  Default: 587 (STARTTLS)
    sender_email : str
        The "From" address used to authenticate and send mail.
    sender_password : str
        Password or app-specific password for the sender account.
    """

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "",
        sender_password: str = "",
    ) -> None:
        self.smtp_host      = smtp_host
        self.smtp_port      = smtp_port
        self.sender_email   = sender_email
        self.sender_password = sender_password

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> smtplib.SMTP:
        """Open an authenticated SMTP connection using STARTTLS."""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(self.sender_email, self.sender_password)
        return server

    def _send_message(self, msg: MIMEMultipart) -> None:
        """Send an already-constructed MIMEMultipart message."""
        server = self._connect()
        try:
            server.sendmail(self.sender_email, msg["To"], msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, to: str, subject: str, body: str) -> None:
        """
        Send a plain-text email.

        Parameters
        ----------
        to : str
            Recipient email address.
        subject : str
            Email subject line.
        body : str
            Plain-text message body.

        Raises
        ------
        smtplib.SMTPAuthenticationError
            If credentials are rejected.  Callers should handle this
            specifically and guide users toward Gmail App Passwords.
        smtplib.SMTPException
            For any other SMTP-level error.
        OSError
            If the network connection cannot be established.
        """
        msg = MIMEMultipart("alternative")
        msg["From"]    = self.sender_email
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        self._send_message(msg)

    def send_html(self, to: str, subject: str, html_body: str) -> None:
        """
        Send an HTML email (with a plain-text fallback stripped from the HTML).

        Parameters
        ----------
        to : str
            Recipient email address.
        subject : str
            Email subject line.
        html_body : str
            Full HTML string for the message body.

        Raises
        ------
        smtplib.SMTPAuthenticationError
            If credentials are rejected.  Callers should handle this
            specifically and guide users toward Gmail App Passwords.
        smtplib.SMTPException
            For any other SMTP-level error.
        OSError
            If the network connection cannot be established.
        """
        # Build a minimal plain-text fallback by stripping HTML tags
        import re
        plain = re.sub(r"<[^>]+>", "", html_body)
        plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

        msg = MIMEMultipart("alternative")
        msg["From"]    = self.sender_email
        msg["To"]      = to
        msg["Subject"] = subject
        # RFC 2046: last part is preferred; put HTML last
        msg.attach(MIMEText(plain,     "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))
        self._send_message(msg)
