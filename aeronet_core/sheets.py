"""Async Google Sheets synchronization client for AeroNet."""

import asyncio
import logging
from typing import Optional, List
import gspread
from aeronet_core.models import ApplicationData
from aeronet_core.config import GOOGLE_SHEET_URL, CREDENTIALS_FILE, SHEET_HEADERS
from aeronet_core.database import Database

logger = logging.getLogger(__name__)


class SheetsClient:
    """Non-blocking async wrapper around gspread."""

    def __init__(self, sheet_url: str = GOOGLE_SHEET_URL, creds_file: str = CREDENTIALS_FILE):
        self.sheet_url = sheet_url
        self.creds_file = creds_file
        self._client: Optional[gspread.Client] = None
        self._sheet: Optional[gspread.Worksheet] = None
        self._lock = asyncio.Lock()

    def _connect_sync(self) -> bool:
        """Establish synchronous gspread connection."""
        try:
            self._client = gspread.service_account(filename=self.creds_file)
            self._sheet = self._client.open_by_url(self.sheet_url).sheet1
            logger.info("Connected to Google Sheets: %s", self._sheet.title)
            return True
        except Exception as exc:
            logger.warning("Failed to connect to Google Sheets: %s", exc)
            self._sheet = None
            return False

    async def connect(self) -> bool:
        """Connect to Google Sheets asynchronously."""
        async with self._lock:
            if self._sheet is not None:
                return True
            return await asyncio.to_thread(self._connect_sync)

    def _ensure_headers_sync(self) -> None:
        """Ensure standard column headers exist on row 1."""
        if not self._sheet:
            return
        current = self._sheet.row_values(1)
        if not current:
            self._sheet.update(values=[SHEET_HEADERS], range_name="A1:I1")
            self._sheet.format("A1:I1", {"textFormat": {"bold": True}})
            self._sheet.freeze(rows=1)
            logger.info("Initialized Google Sheet headers.")

    async def ensure_headers(self) -> None:
        """Ensure header row exists."""
        if await self.connect():
            await asyncio.to_thread(self._ensure_headers_sync)

    def _find_row_by_user_id_sync(self, user_id: int) -> Optional[int]:
        """Find row number matching user ID in column A."""
        if not self._sheet:
            return None
        try:
            cell = self._sheet.find(str(user_id), in_column=1)
            return cell.row if cell else None
        except gspread.exceptions.CellNotFound:
            return None
        except Exception as exc:
            logger.warning("Error searching user %d in sheet: %s", user_id, exc)
            return None

    def _save_or_update_sync(self, app: ApplicationData) -> bool:
        """Insert or update application row synchronously."""
        if not self._sheet:
            return False

        row_data = app.to_sheet_row()
        try:
            existing_row = self._find_row_by_user_id_sync(app.user_id)
            if existing_row:
                # Update existing row
                range_name = f"A{existing_row}:I{existing_row}"
                self._sheet.update(values=[row_data], range_name=range_name)
                logger.info("Updated existing row %d for user %d", existing_row, app.user_id)
            else:
                # Append new row
                self._sheet.append_row(row_data)
                logger.info("Appended new application row for user %d", app.user_id)
            return True
        except Exception as exc:
            logger.warning("Failed to save application to Google Sheets: %s", exc)
            return False

    async def save_or_update_application(self, app: ApplicationData) -> bool:
        """Save application to Google Sheets asynchronously."""
        connected = await self.connect()
        if not connected:
            return False
        return await asyncio.to_thread(self._save_or_update_sync, app)

    def _delete_row_sync(self, user_id: int) -> bool:
        """Delete row matching user ID in column A."""
        if not self._sheet:
            return False
        try:
            row_idx = self._find_row_by_user_id_sync(user_id)
            if row_idx:
                self._sheet.delete_rows(row_idx)
                logger.info("Deleted row %d for user %d from Google Sheets", row_idx, user_id)
                return True
            return False
        except Exception as exc:
            logger.warning("Failed to delete user %d from Google Sheets: %s", user_id, exc)
            return False

    async def delete_application(self, user_id: int) -> bool:
        """Delete application from Google Sheets asynchronously."""
        connected = await self.connect()
        if not connected:
            return False
        return await asyncio.to_thread(self._delete_row_sync, user_id)

    async def sync_pending(self, db: Database) -> int:
        """Sync any unsynced applications from local SQLite to Google Sheets."""
        unsynced = db.get_unsynced_applications()
        if not unsynced:
            return 0

        connected = await self.connect()
        if not connected:
            return 0

        synced_count = 0
        for app in unsynced:
            success = await asyncio.to_thread(self._save_or_update_sync, app)
            if success:
                db.mark_as_synced(app.user_id)
                synced_count += 1

        if synced_count > 0:
            logger.info("Synced %d pending application(s) to Google Sheets.", synced_count)
        return synced_count
