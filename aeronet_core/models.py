"""Data models for AeroNet application bot."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ApplicationData:
    """Represents a customer connection application."""

    user_id: int
    username: str
    fio: str
    phone: str
    address: str
    tariff: str
    comments: str
    created_at: str
    status: str = "Новая"
    synced: bool = False

    def to_sheet_row(self) -> list[str]:
        """Convert application to a row matching Google Sheet column order."""
        clean_user = self.username or "N/A"
        if clean_user != "N/A" and not clean_user.startswith("@"):
            clean_user = f"@{clean_user}"

        return [
            str(self.user_id),
            clean_user,
            self.fio,
            self.phone,
            self.address,
            self.tariff,
            self.comments,
            self.created_at,
            self.status,
        ]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Tariff:
    """Internet plan representation."""

    code: str
    title: str
    speed: str
    price: str
    description: str
