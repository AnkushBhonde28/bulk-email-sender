import smtplib
import ssl
import time
import logging
import re
from html import unescape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from config import (
    BATCH_DELAY,
    BATCH_SIZE,
    EMAIL,
    LOG_FILE,
    MAX_RETRIES,
    PASSWORD,
    RETRY_DELAY,
    SEND_DELAY,
    SENDER_NAME,
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
GREETING_VARIATIONS = [
    "Hope you are doing well.",
    "Wishing you a productive day.",
    "Thank you for taking a moment to read this.",
]


def mask_secret(secret):
    if not secret:
        return "(empty)"

    if len(secret) <= 4:
        return "*" * len(secret)

    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


def log_smtp_configuration():
    logger.info("SMTP configuration audit started.")
    logger.info("SMTP_SERVER=%s", SMTP_SERVER or "(empty)")
    logger.info("SMTP_PORT=%s", SMTP_PORT)
    logger.info("EMAIL=%s", EMAIL or "(empty)")
    logger.info("PASSWORD=%s", mask_secret(PASSWORD))

    print(f"SMTP server: {SMTP_SERVER or '(empty)'}")
    print(f"SMTP port: {SMTP_PORT}")
    print(f"Login email: {EMAIL or '(empty)'}")
    print(f"Password: {mask_secret(PASSWORD)}")


def get_configuration_issues():
    issues = []

    if not SMTP_SERVER:
        issues.append("SMTP_SERVER is empty.")

    if not SMTP_PORT:
        issues.append("SMTP_PORT is empty.")

    if not EMAIL:
        issues.append("EMAIL is empty.")

    if not PASSWORD:
        issues.append("PASSWORD is empty.")

    return issues


def strip_html_tags(html_content):
    text = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_greeting_variation(email_address):
    if not email_address:
        return GREETING_VARIATIONS[0]

    index = sum(ord(character) for character in email_address) % len(GREETING_VARIATIONS)
    return GREETING_VARIATIONS[index]


def build_email_content(body, email_address):
    greeting_line = get_greeting_variation(email_address)
    html_body = f"<p>{greeting_line}</p>{body}"
    plain_text_body = strip_html_tags(html_body)
    return plain_text_body, html_body


def create_message(to_email, subject, body):
    plain_text_body, html_body = build_email_content(body, to_email)
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = formataddr((SENDER_NAME, EMAIL))
    message["To"] = to_email
    message["Reply-To"] = EMAIL
    message["Message-ID"] = make_msgid()
    message["Date"] = formatdate(localtime=True)

    message.attach(MIMEText(plain_text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))
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


def classify_auth_error(smtp_code, smtp_error_text):
    error_text = smtp_error_text.lower()

    if smtp_code == 535 or "authentication failed" in error_text:
        return "Wrong email or app password."

    if "invalid credentials" in error_text or "bad credentials" in error_text:
        return "Wrong email or app password."

    if "not allowed" in error_text or "access denied" in error_text:
        return "Access blocked by the SMTP provider or security policy."

    if "app password" in error_text or "application-specific password" in error_text:
        return "An app password is required."

    return "Authentication failed. Check server, credentials, and provider security settings."


def open_smtp_connection():
    logger.info("Opening SMTP SSL connection to %s:%s", SMTP_SERVER, SMTP_PORT)
    print(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")

    ssl_context = ssl.create_default_context()
    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl_context)
    server.set_debuglevel(1)

    logger.info("SMTP connection established.")
    print("SMTP connection successful.")
    return server


def login_smtp_server(server):
    logger.info("Attempting SMTP login with %s", EMAIL)
    print(f"Attempting SMTP login with {EMAIL}...")
    server.login(EMAIL, PASSWORD)
    logger.info("SMTP login successful.")
    print("SMTP login successful.")


def test_smtp_connection(test_recipient=None):
    log_smtp_configuration()

    issues = get_configuration_issues()
    if issues:
        error_message = "Configuration error: " + " ".join(issues)
        logger.error(error_message)
        print(error_message)
        return False, error_message

    recipient = test_recipient or EMAIL
    logger.info("Running SMTP test email to %s", recipient)
    print(f"Running SMTP test email to {recipient}...")

    message = create_message(
        recipient,
        "SMTP Test Email",
        "<p>This is a test email used to verify SMTP connectivity.</p>",
    )

    try:
        with open_smtp_connection() as server:
            login_smtp_server(server)
            logger.info("Sending SMTP test email to %s", recipient)
            print(f"Sending SMTP test email to {recipient}...")
            server.sendmail(EMAIL, recipient, message.as_string())
        success_message = f"SMTP test email sent successfully to {recipient}"
        logger.info(success_message)
        print(success_message)
        return True, success_message
    except smtplib.SMTPAuthenticationError as error:
        smtp_error_text = error.smtp_error.decode("utf-8", errors="replace")
        reason = classify_auth_error(error.smtp_code, smtp_error_text)
        error_message = (
            f"SMTP test failed: authentication error. {reason} "
            f"Exact SMTP response: {error.smtp_code} {smtp_error_text}"
        )
    except smtplib.SMTPConnectError as error:
        error_message = (
            f"SMTP test failed: could not connect to {SMTP_SERVER}:{SMTP_PORT}. "
            f"Exact SMTP response: {error.smtp_code} {error.smtp_error!r}"
        )
    except OSError as error:
        error_message = (
            f"SMTP test failed: network or server issue while connecting to "
            f"{SMTP_SERVER}:{SMTP_PORT}. Error: {error}"
        )
    except smtplib.SMTPException as error:
        error_message = f"SMTP test failed: SMTP error: {error}"
    except Exception as error:
        error_message = f"SMTP test failed: unexpected error: {error}"

    logger.error(error_message)
    print(error_message)
    return False, error_message


def send_email(to_email, subject, body):
    log_smtp_configuration()

    configuration_issues = get_configuration_issues()
    if configuration_issues:
        message = "Failed to send email: " + " ".join(configuration_issues)
        print(message)
        logger.error(message)
        return False

    if not to_email:
        message = "Failed to send email: recipient email address is missing."
        print(message)
        logger.error(message)
        return False

    message = create_message(to_email, subject, body)
    started_at = time.time()

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            logger.info("Starting email attempt %s for %s", attempt, to_email)
            print(f"Starting email attempt {attempt} for {to_email}...")

            with open_smtp_connection() as server:
                login_smtp_server(server)
                logger.info("Sending email to %s", to_email)
                print(f"Sending email to {to_email}...")
                server.sendmail(EMAIL, to_email, message.as_string())

            elapsed_time = round(time.time() - started_at, 2)
            success_message = f"Email sent successfully to {to_email} in {elapsed_time} seconds"
            print(success_message)
            log_email_attempt(to_email, "success")
            return True
        except smtplib.SMTPAuthenticationError as error:
            smtp_error_text = error.smtp_error.decode("utf-8", errors="replace")
            reason = classify_auth_error(error.smtp_code, smtp_error_text)
            error_message = (
                "Failed to send email: SMTP authentication failed. "
                f"{reason} "
                f"Exact SMTP error: {error.smtp_code} {smtp_error_text}"
            )
            print(error_message)
            log_email_attempt(to_email, "failure", error_message)
            return False
        except smtplib.SMTPConnectError as error:
            error_message = (
                f"Attempt {attempt} failed for {to_email}: could not connect to "
                f"{SMTP_SERVER}:{SMTP_PORT}. Exact SMTP response: "
                f"{error.smtp_code} {error.smtp_error!r}"
            )
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


def chunk_recipients(recipients, batch_size):
    for index in range(0, len(recipients), batch_size):
        yield recipients[index:index + batch_size]


def send_bulk_emails(recipients, subject, body):
    total_recipients = len(recipients)
    success_count = 0
    failure_count = 0
    total_batches = (total_recipients + BATCH_SIZE - 1) // BATCH_SIZE if total_recipients else 0

    for batch_number, batch in enumerate(chunk_recipients(recipients, BATCH_SIZE), start=1):
        logger.info("Starting batch %s/%s", batch_number, total_batches)
        print(f"Starting batch {batch_number}/{total_batches}...")

        for recipient in batch:
            recipient_email = recipient.get("email", "").strip()
            recipient_name = recipient.get("name", "").strip() or "Subscriber"

            if not recipient_email:
                logger.warning("Skipped recipient with empty email in batch %s.", batch_number)
                print(f"Skipped recipient in batch {batch_number}: email is empty.")
                failure_count += 1
                continue

            personalized_body = body.replace("{name}", recipient_name).replace("{email}", recipient_email)

            if send_email(recipient_email, subject, personalized_body):
                success_count += 1
            else:
                failure_count += 1

            if SEND_DELAY > 0:
                logger.info("Waiting %s second(s) before the next email.", SEND_DELAY)
                print(f"Waiting {SEND_DELAY} second(s) before the next email...")
                time.sleep(SEND_DELAY)

        logger.info("Finished batch %s/%s", batch_number, total_batches)
        print(f"Finished batch {batch_number}/{total_batches}.")

        if batch_number < total_batches and BATCH_DELAY > 0:
            logger.info("Waiting %s second(s) before the next batch.", BATCH_DELAY)
            print(f"Waiting {BATCH_DELAY} second(s) before the next batch...")
            time.sleep(BATCH_DELAY)

    return {
        "success": success_count > 0,
        "message": (
            "Emails sent successfully."
            if success_count > 0
            else "Email sending failed. No emails were sent."
        ),
        "total": total_recipients,
        "sent": success_count,
        "failed": failure_count,
    }
