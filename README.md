# ApplyTracker

A lightweight CLI tool that monitors your Gmail inbox for job application emails, classifies them as **applied** or **rejected** using keyword rules, and stores everything in a local SQLite database. Plays a sound on rejection.

## Features

- Polls Gmail via IMAP + OAuth2 at a configurable interval
- Keyword-based classification (applied / rejected / unknown)
- Local SQLite storage — no external services needed
- Sound notification on rejection (via pygame)
- Backfill command to import historical emails

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure Gmail OAuth2

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Gmail API**.
3. Create OAuth 2.0 credentials (Desktop app) and download the JSON file.
4. Place it at `secrets/client_secret.json`.

### 3. Create config

Copy the example config and fill in your Gmail address:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
gmail_imap:
  username: "you@gmail.com"   # your Gmail address
```

### 4. Initialize the database

```bash
python -m app.cli initdb
```

## Usage

### Start the polling loop

```bash
python -m app.cli run
```

On first run it skips existing emails and only watches for new ones going forward.

### Backfill historical emails

```bash
# Last 30 days
python -m app.cli backfill --days 30

# Last 100 emails
python -m app.cli backfill --limit 100
```

### List tracked events

```bash
python -m app.cli list-events
```

### Test without Gmail

```bash
python -m app.cli ingest-fake --subject "We received your application for SWE"
```

## Project Structure

```
app/
  cli.py          # CLI commands (typer)
  config.py       # Config loading (YAML)
  processor.py    # Email classification + DB insert logic
  db/             # SQLite helpers
  classify/       # Keyword-based classification rules
  ingest/         # Gmail OAuth + IMAP helpers
config.example.yaml
requirements.txt
```

## Notes

- `secrets/` and `config.yaml` are gitignored — never commit credentials.
- `data/` (SQLite DB) is also gitignored.
