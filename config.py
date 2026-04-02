import os

from dotenv import load_dotenv


load_dotenv()


def get_int_env(name, default):
    value = os.getenv(name, str(default))

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Zoho notes:
# 1. Enable 2FA on your Zoho account.
# 2. Use an App Password instead of your regular account password.
EMAIL = os.getenv("EMAIL", "")
PASSWORD = os.getenv("PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.zoho.com")
SMTP_PORT = get_int_env("SMTP_PORT", 465)
MAX_RETRIES = 2
RETRY_DELAY = 2
LOG_FILE = "bulk_email.log"
