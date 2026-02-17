from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.classify.rules import EmailLite, classify, Category
from app.db.repo import EmailEventRow, insert_email_event
from app.notify.player import play_sound_windows
import sqlite3


class ProcessResult(str, Enum):
    INSERTED = "INSERTED"
    DUPLICATE = "DUPLICATE"


@dataclass
class ProcessorConfig:
    applied_keywords: list[str]
    rejected_keywords: list[str]
    # optional: path to a rejection sound
    rejection_sound_path: Optional[str] = None


class EmailEventProcessor:
    """
    The "business core" of the system.

    Input: EmailLite (regardless of where it comes from: fake, IMAP, Gmail API)
    Steps:
      1) classify
      2) persist (idempotent via DB unique constraint)
      3) optional side effects (notify)
    """

    def __init__(self, conn: sqlite3.Connection, cfg: ProcessorConfig):
        self.conn = conn
        self.cfg = cfg

    def process_one(self, email: EmailLite) -> tuple[ProcessResult, Category]:
        # 1) classify
        cat = classify(email, self.cfg.applied_keywords, self.cfg.rejected_keywords)

        # 2) persist (DB decides dedupe)
        inserted = insert_email_event(
            self.conn,
            EmailEventRow(
                message_id=email.message_id,
                from_email=email.from_email,
                subject=email.subject,
                received_at=email.received_at,
                snippet=email.snippet,
                category=str(cat.value),
            ),
        )

        if not inserted:
            return (ProcessResult.DUPLICATE, cat)

        # 3) side effects 
        if cat == Category.REJECTION and self.cfg.rejection_sound_path:
            try:
                play_sound_windows(self.cfg.rejection_sound_path)
            except Exception as e:
                # Log the error but don't crash the pipeline
                print(f"⚠️  Failed to play rejection sound: {e}")
            
        return (ProcessResult.INSERTED, cat)
