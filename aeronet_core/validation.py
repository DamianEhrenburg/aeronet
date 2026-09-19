"""Input validation and sanitization utilities for AeroNet."""

import re
from typing import Optional


def normalize_phone(raw: str) -> Optional[str]:
    """
    Validate and normalize phone numbers.
    Converts Russian numbers to '+7 (XXX) XXX-XX-XX'.
    Leaves international numbers in clean E.164-like form (+<digits>).
    Returns None if input is invalid or not a phone number.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # Check for non-phone characters (allow +, digits, spaces, dashes, parentheses)
    if not re.match(r"^[\+\d\s\-\(\)\.]+$", cleaned):
        return None

    # Extract digits and check for leading +
    has_plus = cleaned.startswith("+")
    digits = "".join(filter(str.isdigit, cleaned))

    if len(digits) < 10 or len(digits) > 15:
        return None

    # Russian number formatting: 11 digits starting with 7 or 8, or 10 digits without country code
    if len(digits) == 11 and digits[0] in ("7", "8"):
        area = digits[1:4]
        part1 = digits[4:7]
        part2 = digits[7:9]
        part3 = digits[9:11]
        return f"+7 ({area}) {part1}-{part2}-{part3}"

    if len(digits) == 10:
        area = digits[0:3]
        part1 = digits[3:6]
        part2 = digits[6:8]
        part3 = digits[8:10]
        return f"+7 ({area}) {part1}-{part2}-{part3}"

    # International number: must have started with +
    if has_plus and len(digits) >= 11:
        return f"+{digits}"

    return None


def sanitize_fio(raw: str) -> Optional[str]:
    """Sanitize customer full name."""
    if not raw or not isinstance(raw, str):
        return None

    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", raw).strip()

    if len(cleaned) < 2 or len(cleaned) > 100:
        return None

    # Must contain at least one letter (Latin or Cyrillic)
    if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", cleaned):
        return None

    return cleaned


def sanitize_address(raw: str) -> Optional[str]:
    """Sanitize connection address."""
    if not raw or not isinstance(raw, str):
        return None

    cleaned = re.sub(r"\s+", " ", raw).strip()

    if len(cleaned) < 4 or len(cleaned) > 200:
        return None

    # Must contain letters
    if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", cleaned):
        return None

    return cleaned


def sanitize_comments(raw: str) -> str:
    """Normalize user comments or notes."""
    if not raw or not isinstance(raw, str):
        return "Без комментариев"

    cleaned = re.sub(r"\s+", " ", raw).strip()
    lower = cleaned.lower()

    if not cleaned or lower in ("-", "—", "нет", "отсутствует", "none", "no", "пусто"):
        return "Без комментариев"

    return cleaned[:300]
