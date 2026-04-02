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

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            logger.info("Starting email attempt %s for %s", attempt, to_email)
            print(f"Starting email attempt {attempt} for {to_email}...")

            with open_smtp_connection() as server:
                login_smtp_server(server)
                logger.info("Sending email to %s", to_email)
                print(f"Sending email to {to_email}...")
                server.sendmail(EMAIL, to_email, message.as_string())

            success_message = f"Email sent successfully to {to_email}"
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
