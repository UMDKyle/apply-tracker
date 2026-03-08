from __future__ import annotations
import imaplib
import email
from email.header import decode_header
from typing import Optional

from app.classify.rules import EmailLite


def _build_xoauth2_string(username: str, access_token: str) -> bytes:
    auth_str = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    return auth_str.encode("utf-8")


def connect_gmail_imap(username: str, access_token: str, host: str = "imap.gmail.com", port: int = 993) -> imaplib.IMAP4_SSL:
    """
    Connects to Gmail IMAP via XOAUTH2.
    """
    imap = imaplib.IMAP4_SSL(host, port)
    imap.authenticate("XOAUTH2", lambda x: _build_xoauth2_string(username, access_token))
    return imap


def _decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="replace")
        else:
            out += text
    return out


def fetch_new_emails_since_uid(imap: imaplib.IMAP4_SSL, last_seen_uid: int) -> tuple[list[EmailLite], int]:
    """
    Returns (emails, new_last_seen_uid).
    Only fetch minimal headers + small snippet.
    """
    imap.select("INBOX")

    # UID search for anything greater than last_seen_uid
    criteria = f"(UID {last_seen_uid + 1}:*)"
    status, data = imap.uid("SEARCH", None, criteria)
    if status != "OK":
        return ([], last_seen_uid)

    uids = [int(x) for x in data[0].split()] if data and data[0] else []
    if not uids:
        return ([], last_seen_uid)

    new_last = max(uids)
    results: list[EmailLite] = []

    # Fetch headers + a bit of body (snippet)
    for uid in uids:
        status, msg_data = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.1024>)")
        if status != "OK" or not msg_data:
            continue

        # msg_data contains tuples; parse the raw bytes
        raw_header = None
        raw_text = b""
        for item in msg_data:
            if isinstance(item, tuple):
                if b"HEADER" in item[0]:
                    raw_header = item[1]
                else:
                    raw_text += item[1] or b""

        if not raw_header:
            continue

        msg = email.message_from_bytes(raw_header)
        message_id = (msg.get("Message-ID") or f"uid-{uid}").strip()
        from_email = _decode_mime_header(msg.get("From"))
        subject = _decode_mime_header(msg.get("Subject"))
        date = _decode_mime_header(msg.get("Date"))

        snippet = raw_text.decode("utf-8", errors="replace").strip()
        results.append(
            EmailLite(
                message_id=message_id,
                from_email=from_email,
                subject=subject,
                received_at=date,   # 先用 Date header；后面可统一转 UTC ISO
                snippet=snippet,
            )
        )

    return (results, new_last)


def get_latest_uid(imap: imaplib.IMAP4_SSL) -> int:
    """
    Get the latest (max) UID in the INBOX.
    Returns 0 if inbox is empty.
    """
    imap.select("INBOX")
    status, data = imap.uid("SEARCH", None, "ALL")
    if status != "OK":
        return 0
    
    uids = [int(x) for x in data[0].split()] if data and data[0] else []
    return max(uids) if uids else 0
