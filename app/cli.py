import typer
from datetime import datetime, timezone
from app.processor import EmailEventProcessor, ProcessorConfig, ProcessResult

from app.config import load_settings
from app.db import init_db, connect
from app.classify.rules import EmailLite, classify
from app.db.repo import EmailEventRow, insert_email_event, list_email_events

cli = typer.Typer(help="ApplyTracker CLI")


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


if __name__ == "__main__":
    cli()
