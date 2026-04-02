from flask import Flask, render_template, request
import pandas as pd

from sender import get_logger, send_email, test_smtp_connection
from utils import recipients_from_dataframe, render_email_template


app = Flask(__name__)
logger = get_logger()


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    subject = ""
    message = ""

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        csv_file = request.files.get("csv_file")

        if not subject or not message or csv_file is None or not csv_file.filename:
            result = {
                "success": False,
                "message": "Subject, message, and CSV file are required.",
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        try:
            data_frame = pd.read_csv(csv_file)
        except Exception as error:
            logger.error("Could not read uploaded CSV file: %s", error)
            result = {
                "success": False,
                "message": f"Could not read the uploaded CSV file: {error}",
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        recipients, skipped_rows = recipients_from_dataframe(data_frame, logger=logger)

        if skipped_rows:
            for skipped_row in skipped_rows:
                print(skipped_row)

        if not recipients:
            result = {
                "success": False,
                "message": "No valid recipients found in the uploaded CSV file.",
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        success_count = 0
        failure_count = 0

        smtp_test_success, smtp_test_message = test_smtp_connection()
        if not smtp_test_success:
            result = {
                "success": False,
                "message": smtp_test_message,
                "total": len(recipients),
                "sent": 0,
                "failed": len(recipients),
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        try:
            for recipient in recipients:
                recipient_email = recipient.get("email", "").strip()
                recipient_name = recipient.get("name", "").strip() or "Subscriber"

                if not recipient_email:
                    logger.warning("Skipped recipient with empty email during send loop.")
                    failure_count += 1
                    continue

                email_body = render_email_template(message, recipient_name, recipient_email)

                logger.info("Attempting to send email to %s", recipient_email)
                if send_email(recipient_email, subject, email_body):
                    success_count += 1
                else:
                    failure_count += 1
        except Exception as error:
            logger.exception("Something went wrong while sending emails: %s", error)
            result = {
                "success": False,
                "message": f"Something went wrong while sending emails: {error}",
                "total": len(recipients),
                "sent": success_count,
                "failed": failure_count,
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        result = {
            "success": success_count > 0,
            "message": (
                "Emails sent successfully."
                if success_count > 0
                else "Email sending failed. No emails were sent."
            ),
            "total": len(recipients),
            "sent": success_count,
            "failed": failure_count,
        }

    return render_template("index.html", result=result, subject=subject, message=message)


if __name__ == "__main__":
    app.run(debug=True)
