import logging
import smtplib
import ssl
from email.message import EmailMessage

from . import config

logger = logging.getLogger("uvicorn.error")


def send_verification_email(to_email: str, link: str) -> None:
    """Verification email bhejta hay. SMTP configured na ho to link server console mai print karta hay."""
    if not config.SMTP_HOST:
        logger.warning(
            "SMTP configured nahi hay. %s ki verification link (browser mai kholo): %s", to_email, link
        )
        return

    message = EmailMessage()
    message["Subject"] = "Verify your WheelDeal account"
    message["From"] = config.SMTP_FROM
    message["To"] = to_email
    message.set_content(
        "Welcome to WheelDeal!\n\n"
        "Please confirm your email address by opening this link (valid for 24 hours):\n\n"
        f"{link}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    try:
        context = ssl.create_default_context()
        if config.SMTP_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        with server:
            if not config.SMTP_SSL and config.SMTP_STARTTLS:
                server.starttls(context=context)
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        # Signup ko fail nahi karte; user "resend" se dobara try kar sakta hay
        logger.exception("Verification email %s ko nahi ja saki.", to_email)
