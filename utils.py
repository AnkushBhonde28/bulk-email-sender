import pandas as pd


def load_emails(file_path):
    try:
        data_frame = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"CSV file not found: {file_path}")
        return []
    except Exception as error:
        print(f"Error reading CSV file: {error}")
        return []

    if "email" not in data_frame.columns:
        print('CSV file must contain an "email" column.')
        return []

    emails = (
        data_frame["email"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    return [email for email in emails if email]


def read_recipients_from_csv(csv_file_path):
    try:
        data_frame = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"CSV file not found: {csv_file_path}")
        return []
    except Exception as error:
        print(f"Error reading CSV file: {error}")
        return []

    if "email" not in data_frame.columns:
        print('CSV file must contain an "email" column.')
        return []

    if "name" not in data_frame.columns:
        data_frame["name"] = ""

    recipients = []

    for _, row in data_frame.iterrows():
        name = row.get("name", "")
        email = row.get("email", "")
        recipients.append(
            {
                "name": str(name).strip() if pd.notna(name) else "",
                "email": str(email).strip() if pd.notna(email) else "",
            }
        )

    return recipients


def load_email_template(template_path):
    try:
        with open(template_path, "r", encoding="utf-8") as template_file:
            return template_file.read()
    except FileNotFoundError:
        print(f"Template file not found: {template_path}")
    except Exception as error:
        print(f"Error reading template file: {error}")

    return ""


def render_email_template(template_content, name, email):
    return template_content.format(name=name, email=email)


def chunk_recipients(recipients, batch_size):
    for index in range(0, len(recipients), batch_size):
        yield recipients[index:index + batch_size]
