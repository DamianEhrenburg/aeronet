"""Tests for SheetsClient in aeronet_core/sheets.py."""

from unittest.mock import MagicMock, patch
import pytest
from aeronet_core.models import ApplicationData
from aeronet_core.sheets import SheetsClient


@pytest.fixture
def mock_sheets_client():
    client = SheetsClient(sheet_url="https://docs.google.com/spreadsheets/d/test/edit")
    client._sheet = MagicMock()
    return client


def test_ensure_headers_initializes_when_empty(mock_sheets_client):
    mock_sheets_client._sheet.row_values.return_value = []

    mock_sheets_client._ensure_headers_sync()

    mock_sheets_client._sheet.update.assert_called_once()
    _, kwargs = mock_sheets_client._sheet.update.call_args
    assert "values" in kwargs
    assert kwargs["range_name"] == "A1:I1"
    mock_sheets_client._sheet.freeze.assert_called_once_with(rows=1)


def test_ensure_headers_skips_when_headers_present(mock_sheets_client):
    mock_sheets_client._sheet.row_values.return_value = ["ID пользователя", "ФИО"]

    mock_sheets_client._ensure_headers_sync()

    mock_sheets_client._sheet.update.assert_not_called()


def test_save_or_update_appends_new_application(mock_sheets_client):
    mock_sheets_client._sheet.find.return_value = None

    app = ApplicationData(
        user_id=999,
        username="john_doe",
        fio="Иванов Иван",
        phone="+7 (988) 777-66-55",
        address="г. Москва, ул. Мира, д. 1",
        tariff="Комфорт 100 Мбит/с",
        comments="Без комментариев",
        created_at="2026-09-19 20:30:00",
        status="Новая",
        synced=False,
    )

    success = mock_sheets_client._save_or_update_sync(app)

    assert success is True
    mock_sheets_client._sheet.append_row.assert_called_once_with(app.to_sheet_row())


def test_save_or_update_updates_existing_row(mock_sheets_client):
    mock_cell = MagicMock()
    mock_cell.row = 5
    mock_sheets_client._sheet.find.return_value = mock_cell

    app = ApplicationData(
        user_id=888,
        username="jane_doe",
        fio="Петрова Анна",
        phone="+7 (988) 111-22-33",
        address="г. Белгород, ул. Победы, д. 10",
        tariff="Скорость 300 Мбит/с",
        comments="Установить до пятницы",
        created_at="2026-09-19 20:30:00",
        status="В обработке",
        synced=False,
    )

    success = mock_sheets_client._save_or_update_sync(app)

    assert success is True
    mock_sheets_client._sheet.update.assert_called_once_with(
        values=[app.to_sheet_row()], range_name="A5:I5"
    )
