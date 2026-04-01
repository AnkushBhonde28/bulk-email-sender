from flask import Flask, render_template, request
import pandas as pd

from sender import send_email
from utils import render_email_template


app = Flask(__name__)


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
            result = {
                "success": False,
                "message": f"Could not read the uploaded CSV file: {error}",
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        if "email" not in data_frame.columns:
            result = {
                "success": False,
                "message": 'The uploaded CSV file must contain an "email" column.',
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        if "name" not in data_frame.columns:
            data_frame["name"] = ""

        recipients = []

        for _, row in data_frame.iterrows():
            recipients.append(
                {
                    "name": str(row.get("name", "")).strip() if pd.notna(row.get("name", "")) else "",
                    "email": str(row.get("email", "")).strip() if pd.notna(row.get("email", "")) else "",
                }
            )

        if not recipients:
            result = {
                "success": False,
                "message": "No recipients found in the uploaded CSV file.",
            }
            return render_template("index.html", result=result, subject=subject, message=message)

        success_count = 0
        failure_count = 0

        try:
            for recipient in recipients:
                recipient_email = recipient.get("email", "").strip()
                recipient_name = recipient.get("name", "").strip() or "Subscriber"

                if not recipient_email:
                    failure_count += 1
                    continue

                email_body = render_email_template(message, recipient_name, recipient_email)

                if send_email(recipient_email, subject, email_body):
                    success_count += 1
                else:
                    failure_count += 1
        except Exception as error:
            result = {
                "success": False,
                "message": f"Something went wrong while sending emails: {error}",
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
