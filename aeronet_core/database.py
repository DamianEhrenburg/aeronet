"""Local SQLite database for AeroNet applications with fail-safe persistence."""

import sqlite3
from typing import Optional, List
from aeronet_core.models import ApplicationData


class Database:
    """Manages local SQLite database operations."""

    def __init__(self, db_path: str = "aeronet.db"):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    fio TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    tariff TEXT NOT NULL,
                    comments TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Новая',
                    synced INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def save_application(self, app: ApplicationData) -> None:
        """Insert or update an application record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO applications (
                    user_id, username, fio, phone, address, tariff, comments, created_at, status, synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    fio=excluded.fio,
                    phone=excluded.phone,
                    address=excluded.address,
                    tariff=excluded.tariff,
                    comments=excluded.comments,
                    created_at=excluded.created_at,
                    status=excluded.status,
                    synced=excluded.synced
                """,
                (
                    app.user_id,
                    app.username,
                    app.fio,
                    app.phone,
                    app.address,
                    app.tariff,
                    app.comments,
                    app.created_at,
                    app.status,
                    1 if app.synced else 0,
                ),
            )
            conn.commit()

    def get_application(self, user_id: int) -> Optional[ApplicationData]:
        """Fetch application data by user ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM applications WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return None

            return ApplicationData(
                user_id=row["user_id"],
                username=row["username"] or "",
                fio=row["fio"],
                phone=row["phone"],
                address=row["address"],
                tariff=row["tariff"],
                comments=row["comments"] or "",
                created_at=row["created_at"],
                status=row["status"],
                synced=bool(row["synced"]),
            )

    def get_unsynced_applications(self) -> List[ApplicationData]:
        """Retrieve all applications that are not yet synchronized to Google Sheets."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM applications WHERE synced = 0 ORDER BY created_at ASC"
            ).fetchall()
            return [
                ApplicationData(
                    user_id=r["user_id"],
                    username=r["username"] or "",
                    fio=r["fio"],
                    phone=r["phone"],
                    address=r["address"],
                    tariff=r["tariff"],
                    comments=r["comments"] or "",
                    created_at=r["created_at"],
                    status=r["status"],
                    synced=bool(r["synced"]),
                )
                for r in rows
            ]

    def mark_as_synced(self, user_id: int) -> None:
        """Mark application as successfully synchronized."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE applications SET synced = 1 WHERE user_id = ?", (user_id,)
            )
            conn.commit()

    def update_status(self, user_id: int, status: str) -> None:
        """Update workflow status of an application."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE applications SET status = ?, synced = 0 WHERE user_id = ?",
                (status, user_id),
            )
            conn.commit()

    def delete_application(self, user_id: int) -> bool:
        """Delete an application record by user ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM applications WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
