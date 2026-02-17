from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    APPLIED_RECEIPT = "APPLIED_RECEIPT"
    REJECTION = "REJECTION"
    OTHER = "OTHER"


@dataclass
class EmailLite:
    message_id: str
    from_email: str | None
    subject: str | None
    received_at: str | None
    snippet: str | None


def _contains_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def classify(email: EmailLite, applied_keywords: list[str], rejected_keywords: list[str]) -> Category:
    """
    Rule-based classifier.
    Priority: REJECTION > APPLIED_RECEIPT > OTHER
    """
    combined = " ".join(
        [email.subject or "", email.snippet or "", email.from_email or ""]
    ).strip()

    if combined and _contains_any(combined, rejected_keywords):
        return Category.REJECTION
    if combined and _contains_any(combined, applied_keywords):
        return Category.APPLIED_RECEIPT
    return Category.OTHER
