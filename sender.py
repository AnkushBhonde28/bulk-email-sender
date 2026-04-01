import smtplib
import ssl
import time
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    EMAIL,
    LOG_FILE,
    MAX_RETRIES,
    PASSWORD,
    RETRY_DELAY,
    SMTP_PORT,
    SMTP_SERVER,
)


def get_logger():
    logger = logging.getLogger("bulk_email_sender")

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )

    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


logger = get_logger()


def create_message(to_email, subject, body):
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = EMAIL
    message["To"] = to_email

    message.attach(MIMEText(body, "html", "utf-8"))
    return message


def log_email_attempt(email_address, status, error_message=""):
    log_message = f"email={email_address} | status={status}"

    if error_message:
        log_message = f"{log_message} | error={error_message}"

    if status == "success":
        logger.info(log_message)
    else:
        logger.error(log_message)


def log_retry_attempt(email_address, attempt_number):
    retry_message = (
        f"Retrying email to {email_address} "
        f"(retry {attempt_number} of {MAX_RETRIES}) after {RETRY_DELAY} second(s)..."
    )
    print(retry_message)
    logger.info(retry_message)


def should_retry(attempt_number):
    return attempt_number <= MAX_RETRIES


def send_email(to_email, subject, body):
    if not to_email:
        message = "Failed to send email: recipient email address is missing."
        print(message)
        logger.error(message)
        return False

    if not EMAIL or not PASSWORD:
        message = "Failed to send email: EMAIL and PASSWORD must not be empty."
        print(message)
        logger.error(message)
        return False

    message = create_message(to_email, subject, body)
    ssl_context = ssl.create_default_context()

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl_context) as server:
                # Gmail requires:
                # 1. 2-Step Verification enabled on the Google account.
                # 2. A 16-character App Password instead of the normal Gmail password.
                # 3. The App Password should be pasted without spaces.
                server.set_debuglevel(1)
                server.login(EMAIL, PASSWORD)
                server.sendmail(EMAIL, to_email, message.as_string())

            success_message = f"Email sent successfully to {to_email}"
            print(success_message)
            log_email_attempt(to_email, "success")
            return True
        except smtplib.SMTPAuthenticationError as error:
            smtp_error_text = error.smtp_error.decode("utf-8", errors="replace")
            error_message = (
                "Failed to send email: Gmail authentication failed. "
                "Make sure smtp.gmail.com:465 is being used, 2-Step Verification is enabled, "
                "and config.py contains a 16-character App Password with no spaces. "
                f"Exact SMTP error: {error.smtp_code} {smtp_error_text}"
            )
            print(error_message)
            log_email_attempt(to_email, "failure", error_message)
            return False
        except smtplib.SMTPException as error:
            error_message = (
                f"Attempt {attempt} failed for {to_email}: SMTP error: {error}"
            )
        except OSError as error:
            error_message = (
                f"Attempt {attempt} failed for {to_email}: network error: {error}"
            )
        except Exception as error:
            error_message = (
                f"Attempt {attempt} failed for {to_email}: unexpected error: {error}"
            )

        print(error_message)
        log_email_attempt(to_email, "failure", error_message)

        if should_retry(attempt):
            log_retry_attempt(to_email, attempt)
            time.sleep(RETRY_DELAY)

    return False
