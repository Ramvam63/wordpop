"""Sending email over SMTP (e.g. Gmail with an App Password).

If SMTP is not configured (local development), the email is printed to the
terminal instead, so you can still click the reset link while testing.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger("wordpop.mail")


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    s = get_settings()
    if not (s.smtp_host and s.smtp_user and s.smtp_password):
        line = "-" * 52
        print(f"\n{line}\nEMAIL (SMTP not configured, printing instead)\nTo: {to}\n"
              f"Subject: {subject}\n\n{text}\n{line}\n", flush=True)
        return

    msg = EmailMessage()
    msg["From"] = f"WordPop <{s.mail_from}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    if s.smtp_port == 465:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=15) as server:
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
    log.info("Sent '%s' email to user", subject)


def password_reset_email(link: str, minutes: int) -> tuple[str, str, str]:
    subject = "Reset your WordPop password"
    text = (
        "Hi,\n\nSomeone (hopefully you) asked to reset your WordPop password.\n\n"
        f"Open this link to choose a new password:\n{link}\n\n"
        f"The link works once and expires in {minutes} minutes.\n"
        "If you didn't ask for this, you can ignore this email - your password won't change.\n\n"
        "- WordPop"
    )
    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:auto;color:#111827">
  <h2 style="color:#4F46E5">Reset your WordPop password</h2>
  <p>Someone (hopefully you) asked to reset your WordPop password.</p>
  <p><a href="{link}" style="display:inline-block;background:#4F46E5;color:#fff;padding:12px 20px;
     border-radius:10px;text-decoration:none;font-weight:600">Choose a new password</a></p>
  <p style="color:#6B7280;font-size:14px">The link works once and expires in {minutes} minutes.
     If you didn't ask for this, you can ignore this email.</p>
</div>"""
    return subject, text, html
