import typer
import time
import email
from email.header import decode_header
from datetime import datetime, timezone, timedelta
from app.processor import EmailEventProcessor, ProcessorConfig, ProcessResult

from app.config import load_settings
from app.db import init_db, connect
from app.classify.rules import EmailLite, classify
from app.db.repo import EmailEventRow, insert_email_event, list_email_events

from app.ingest.gmail_oauth import load_credentials
from app.ingest.gmail_imap import (
    connect_gmail_imap, 
    fetch_new_emails_since_uid, 
    get_latest_uid,
)
from app.db.state_repo import get_state, set_state

cli = typer.Typer(help="ApplyTracker CLI")


def _decode_mime_header(value: str | None) -> str:
    """Decode MIME header (used in backfill command)."""
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


@cli.command()
def initdb(config: str = "config.yaml"):
    """Initialize SQLite database."""
    settings = load_settings(config)
    init_db(settings.database.path)
    typer.echo(f"[OK] DB initialized at: {settings.database.path}")


@cli.command()
def pingdb(config: str = "config.yaml"):
    """Quick sanity check: can we connect and query tables?"""
    settings = load_settings(config)
    conn = connect(settings.database.path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        typer.echo("Tables:")
        for r in rows:
            typer.echo(f" - {r['name']}")
    finally:
        conn.close()


@cli.command()
def ingest_fake(
    config: str = "config.yaml",
    subject: str = "We received your application for Software Engineer",
    snippet: str = "Thank you for applying. We received your application.",
    from_email: str = "no-reply@company.com",
    message_id: str = "fake-001",
):
    """
    Insert a fake email event to test pipeline (no Gmail needed).
    """
    settings = load_settings(config)

    email = EmailLite(
        message_id=message_id,
        from_email=from_email,
        subject=subject,
        received_at=datetime.now(timezone.utc).isoformat(),
        snippet=snippet,
    )

    conn = connect(settings.database.path)
    try:
        processor = EmailEventProcessor(
            conn,
            ProcessorConfig(
                applied_keywords=settings.rules.applied_keywords,
                rejected_keywords=settings.rules.rejected_keywords,
                rejection_sound_path=settings.notify.rejection_sound_path,
            ),
        )
        result, cat = processor.process_one(email)
    finally:
        conn.close()

    if result == ProcessResult.INSERTED:
        typer.echo(f"[OK] Inserted: category={cat.value} message_id={message_id}")
    else:
        typer.echo(f"[SKIP] Duplicate ignored: message_id={message_id}")


@cli.command()
def list_events(config: str = "config.yaml", limit: int = 20):
    """List latest stored email events."""
    settings = load_settings(config)
    conn = connect(settings.database.path)
    try:
        rows = list_email_events(conn, limit=limit)
    finally:
        conn.close()

    if not rows:
        typer.echo("(no events yet)")
        return

    for r in rows:
        typer.echo(f"[{r['id']}] {r['category']} | {r['received_at']} | {r['subject']} | {r['message_id']}")


@cli.command()
def backfill(
    config: str = "config.yaml",
    days: int = typer.Option(None, help="Backfill emails from the last N days"),
    limit: int = typer.Option(None, help="Backfill at most N recent emails"),
):
    """
    Backfill historical emails from Gmail.
    Use --days N to fetch emails from last N days, or --limit N for N most recent emails.
    """
    if days is None and limit is None:
        typer.echo("[ERROR] Must specify either --days or --limit")
        raise typer.Exit(1)
    
    if days is not None and limit is not None:
        typer.echo("[ERROR] Cannot specify both --days and --limit")
        raise typer.Exit(1)

    settings = load_settings(config)
    
    # OAuth credentials
    creds = load_credentials(
        client_secret_file=settings.gmail_oauth.client_secret_file,
        token_file=settings.gmail_oauth.token_file,
        scopes=settings.gmail_oauth.scopes,
    )
    
    if not settings.gmail_imap.username:
        raise ValueError("gmail_imap.username is empty in config.yaml")
    
    # Connect IMAP
    imap = connect_gmail_imap(
        username=settings.gmail_imap.username,
        access_token=creds.token,
        host=settings.gmail_imap.host,
        port=settings.gmail_imap.port,
    )
    
    conn = connect(settings.database.path)
    try:
        # Build search criteria
        imap.select("INBOX")
        
        if days is not None:
            # Search by date (last N days)
            since_date = datetime.now(timezone.utc) - timedelta(days=days)
            date_str = since_date.strftime("%d-%b-%Y")  # Format: "16-Feb-2026"
            typer.echo(f"[BACKFILL] Fetching emails since {date_str} (last {days} days)...")
            status, data = imap.uid("SEARCH", None, f"SINCE {date_str}")
        else:
            # Get all UIDs, then take the last N
            typer.echo(f"[BACKFILL] Fetching last {limit} emails...")
            status, data = imap.uid("SEARCH", None, "ALL")
        
        if status != "OK" or not data or not data[0]:
            typer.echo("[INFO] No emails found matching criteria")
            return
        
        uids = [int(x) for x in data[0].split()]
        
        if limit is not None and len(uids) > limit:
            # Take only the most recent N
            uids = sorted(uids)[-limit:]
        
        typer.echo(f"[INFO] Found {len(uids)} emails to process")
        
        processor = EmailEventProcessor(
            conn,
            ProcessorConfig(
                applied_keywords=settings.rules.applied_keywords,
                rejected_keywords=settings.rules.rejected_keywords,
                rejection_sound_path=None,  # Don't play sound during backfill
            ),
        )
        
        inserted_count = 0
        duplicate_count = 0
        
        for uid in uids:
            # Fetch email data
            status, msg_data = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.1024>)")
            if status != "OK" or not msg_data:
                continue
            
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
            
            email_lite = EmailLite(
                message_id=message_id,
                from_email=from_email,
                subject=subject,
                received_at=date,
                snippet=snippet,
            )
            
            result, cat = processor.process_one(email_lite)
            if result == ProcessResult.INSERTED:
                inserted_count += 1
                typer.echo(f"  [{inserted_count}] {cat.value} | {subject[:60]}")
            else:
                duplicate_count += 1
        
        typer.echo(f"[DONE] Inserted: {inserted_count}, Duplicates: {duplicate_count}")
        
        # Update last_seen_uid to the max UID we just processed
        if uids:
            new_last = max(uids)
            set_state(conn, "last_seen_uid", str(new_last))
            typer.echo(f"[UPDATE] Set last_seen_uid={new_last}")
    
    finally:
        conn.close()
        imap.logout()


@cli.command()
def run(config: str = "config.yaml"):
    """
    Run IMAP polling loop: fetch new emails and process them.
    """
    settings = load_settings(config)

    # 1) OAuth credentials (auto refresh)
    creds = load_credentials(
        client_secret_file=settings.gmail_oauth.client_secret_file,
        token_file=settings.gmail_oauth.token_file,
        scopes=settings.gmail_oauth.scopes,
    )

    if not settings.gmail_imap.username:
        raise ValueError("gmail_imap.username is empty in config.yaml (set it to your Gmail address)")

    # 2) Connect IMAP using access token
    imap = connect_gmail_imap(
        username=settings.gmail_imap.username,
        access_token=creds.token,
        host=settings.gmail_imap.host,
        port=settings.gmail_imap.port,
    )

    while True:
        conn = connect(settings.database.path)
        try:
            # read last_seen_uid
            last = get_state(conn, "last_seen_uid")
            last_seen_uid = int(last) if last else 0
            
            # First time run: skip history by setting to latest UID
            if last_seen_uid == 0:
                latest_uid = get_latest_uid(imap)
                if latest_uid > 0:
                    set_state(conn, "last_seen_uid", str(latest_uid))
                    typer.echo(f"[INIT] First run detected. Set last_seen_uid={latest_uid} (skipping history)")
                    last_seen_uid = latest_uid

            emails, new_last = fetch_new_emails_since_uid(imap, last_seen_uid)

            processor = EmailEventProcessor(
                conn,
                ProcessorConfig(
                    applied_keywords=settings.rules.applied_keywords,
                    rejected_keywords=settings.rules.rejected_keywords,
                    rejection_sound_path=settings.notify.rejection_sound_path,
                ),
            )

            for e in emails:
                result, cat = processor.process_one(e)
                typer.echo(f"{result.value}: {cat.value} | {e.subject}")

            if new_last > last_seen_uid:
                set_state(conn, "last_seen_uid", str(new_last))

        finally:
            conn.close()

        time.sleep(settings.app.poll_interval_seconds)



if __name__ == "__main__":
    cli()
