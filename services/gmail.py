"""
Gmail sender cho Zertdoo.

Gui email bang Gmail API (OAuth 2.0, scope: gmail.send).
Khong dung SMTP -- dung truc tiep Google API.

Chuc nang:
- send_email(): gui email HTML voi attachment (tuy chon)
- _build_mime_message(): tao MIME message
"""

import base64
import logging
import os
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from typing import Optional

from config import settings
from services.google_auth import build_service

logger = logging.getLogger("zertdoo.gmail")


def _get_gmail_service():
    """Tao Gmail API service."""
    return build_service("gmail", "v1")


def send_email(
    subject: str,
    body_html: str,
    to: Optional[str] = None,
    attachment_path: Optional[str] = None,
) -> dict:
    """
    Gui email qua Gmail API.

    Args:
        subject: Tieu de email
        body_html: Noi dung HTML
        to: Email nguoi nhan (mac dinh: GMAIL_RECIPIENT trong .env)
        attachment_path: Duong dan file dinh kem (tuy chon)

    Returns:
        dict: {"id": message_id, "threadId": thread_id}

    Raises:
        Exception neu gui that bai
    """
    recipient = to or settings.gmail_recipient
    if not recipient:
        raise ValueError("Khong co email nguoi nhan. Kiem tra GMAIL_RECIPIENT trong .env")

    # Tao MIME message
    message = _build_mime_message(
        to=recipient,
        subject=subject,
        body_html=body_html,
        attachment_path=attachment_path,
    )

    # Encode thanh base64url
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    # Gui qua Gmail API
    service = _get_gmail_service()
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    logger.info(
        "Da gui email den %s: subject='%s', message_id=%s",
        recipient, subject, result.get("id"),
    )
    return result


def _build_mime_message(
    to: str,
    subject: str,
    body_html: str,
    attachment_path: Optional[str] = None,
) -> MIMEMultipart:
    """
    Tao MIME message voi HTML body va attachment tuy chon.

    Args:
        to: Email nguoi nhan
        subject: Tieu de
        body_html: Noi dung HTML
        attachment_path: Duong dan file dinh kem

    Returns:
        MIMEMultipart message
    """
    msg = MIMEMultipart("mixed")
    msg["To"] = to
    msg["Subject"] = subject

    # HTML body
    html_part = MIMEText(body_html, "html", "utf-8")
    msg.attach(html_part)

    # Attachment (neu co)
    if attachment_path and os.path.exists(attachment_path):
        filename = os.path.basename(attachment_path)

        with open(attachment_path, "rb") as f:
            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(f.read())

        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f"attachment; filename={filename}",
        )
        msg.attach(attachment)
        logger.debug("Da dinh kem file: %s", filename)
    elif attachment_path:
        logger.warning("File dinh kem khong ton tai: %s", attachment_path)

    return msg


def format_report_html(report_text: str, title: str) -> str:
    """
    Chuyen bao cao plain text thanh HTML don gian.
    Khong dung framework -- tao HTML thu cong.

    Args:
        report_text: Bao cao plain text tu LLM
        title: Tieu de bao cao

    Returns:
        str: HTML hoan chinh
    """
    # Escape HTML
    import html as html_module
    escaped = html_module.escape(report_text)

    # Chuyen dong tach thành heading
    lines = escaped.split("\n")
    html_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<br>")
        elif stripped.startswith("BAO CAO") or stripped.startswith("BÁO CÁO"):
            html_lines.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #16213e;padding-bottom:8px;">{stripped}</h2>')
        elif stripped[0].isdigit() and "." in stripped[:3]:
            # Muc lon: "1. TONG QUAN", "2. PHAN TICH", ...
            html_lines.append(f'<h3 style="color:#16213e;margin-top:20px;">{stripped}</h3>')
        elif stripped.startswith("- "):
            html_lines.append(f'<li style="margin:4px 0;line-height:1.6;">{stripped[2:]}</li>')
        else:
            html_lines.append(f'<p style="margin:4px 0;line-height:1.6;">{stripped}</p>')

    body = "\n".join(html_lines)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 700px;
    margin: 0 auto;
    padding: 24px;
    background: #f5f5f5;
    color: #1a1a2e;
}}
.container {{
    background: white;
    padding: 32px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}}
h2 {{ font-size: 20px; }}
h3 {{ font-size: 16px; }}
p, li {{ font-size: 14px; }}
.footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #e0e0e0;
    font-size: 12px;
    color: #888;
}}
</style>
</head>
<body>
<div class="container">
{body}
<div class="footer">
Báo cáo được tạo tự động bởi Zertdoo - Hệ thống AI Agent cá nhân.
</div>
</div>
</body>
</html>"""

    return html
