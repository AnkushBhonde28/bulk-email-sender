import os

from dotenv import load_dotenv


load_dotenv()


EMAIL = os.getenv("EMAIL", "")
APP_PASSWORD = os.getenv("PASSWORD", "")
PASSWORD = APP_PASSWORD

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
MAX_RETRIES = 2
RETRY_DELAY = 2
LOG_FILE = "bulk_email.log"
