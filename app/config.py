from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class AppConfig:
    poll_interval_seconds: int


@dataclass
class DatabaseConfig:
    path: str


@dataclass
class GmailImapConfig:
    host: str
    port: int
    username: str
    auth_mode: str


@dataclass
class RulesConfig:
    applied_keywords: list[str]
    rejected_keywords: list[str]


@dataclass
class NotifyConfig:
    rejection_sound_path: str | None

@dataclass
class Settings:
    app: AppConfig
    database: DatabaseConfig
    gmail_imap: GmailImapConfig
    rules: RulesConfig
    notify: NotifyConfig





def load_settings(config_path: str = "config.yaml") -> Settings:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p.resolve()}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))

    return Settings(
        app=AppConfig(poll_interval_seconds=int(raw["app"]["poll_interval_seconds"])),
        database=DatabaseConfig(path=str(raw["database"]["path"])),
        gmail_imap=GmailImapConfig(
            host=str(raw["gmail_imap"]["host"]),
            port=int(raw["gmail_imap"]["port"]),
            username=str(raw["gmail_imap"].get("username", "")),
            auth_mode=str(raw["gmail_imap"].get("auth_mode", "oauth")),
        ),
        rules=RulesConfig(
            applied_keywords=[s.lower() for s in raw["rules"]["applied_keywords"]],
            rejected_keywords=[s.lower() for s in raw["rules"]["rejected_keywords"]],
        ),
        notify=NotifyConfig(
            rejection_sound_path=raw.get("notify", {}).get("rejection_sound_path")
        ),

    )
