# Bulk Email Sender

A simple Flask-based bulk email sender that reads recipients from an uploaded CSV file and sends personalized emails using SMTP.

## Features

- CSV upload with `name` and `email` columns
- Personalized emails using `{name}` in the message
- Simple Flask UI for sending emails
- SMTP email sending with Gmail-compatible settings
- Retry and logging system for failed sends

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root:

```env
EMAIL=your_email
PASSWORD=your_app_password
```

3. Run the application:

```bash
python app.py
```

4. Open the UI in your browser:

`http://127.0.0.1:5000/`

## CSV Format

```csv
name,email
John,john@gmail.com
```

## Notes

- `EMAIL` and `PASSWORD` are loaded from environment variables using `python-dotenv`.
- Do not commit your `.env` file or log files to GitHub.
=======
# bulk-email-sender