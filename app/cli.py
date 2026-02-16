import typer
from app.config import load_settings
from app.db import init_db, connect

cli = typer.Typer(help="ApplyTracker CLI")


@cli.command()
def initdb(config: str = "config.yaml"):
    """Initialize SQLite database."""
    settings = load_settings(config)
    init_db(settings.database.path)
    typer.echo(f"✅ DB initialized at: {settings.database.path}")


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


if __name__ == "__main__":
    cli()
