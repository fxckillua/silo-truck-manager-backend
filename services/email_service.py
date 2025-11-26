from email.message import EmailMessage
import smtplib
from flask import current_app


def send_email(subject: str, recipients: list[str], body: str, html: str | None = None) -> None:
    """Send an email using SMTP settings defined in the app config."""
    if not recipients:
        return

    mail_server = current_app.config.get("MAIL_SERVER")
    mail_port = current_app.config.get("MAIL_PORT")
    mail_username = current_app.config.get("MAIL_USERNAME")
    mail_password = current_app.config.get("MAIL_PASSWORD")
    mail_use_tls = current_app.config.get("MAIL_USE_TLS", True)
    default_sender = current_app.config.get("MAIL_DEFAULT_SENDER") or mail_username

    if not all([mail_server, mail_port, mail_username, mail_password, default_sender]):
        raise RuntimeError("Parâmetros de e-mail não configurados. Verifique as variáveis de ambiente.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = default_sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    if html:
        message.add_alternative(html, subtype="html")

    with smtplib.SMTP(mail_server, mail_port) as server:
        if mail_use_tls:
            server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(message)
