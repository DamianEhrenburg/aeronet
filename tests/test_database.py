import pytest
import os
import sqlite3
from aeronet_core.models import ApplicationData
from aeronet_core.database import Database


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_aeronet.db")
    database = Database(db_path=db_path)
    database.init_db()
    return database


def test_save_and_get_application(db):
    app = ApplicationData(
        user_id=123456789,
        username="test_user",
        fio="Иванов Иван Иванович",
        phone="+7 (988) 777-66-55",
        address="г. Москва, ул. Ленина, д. 1",
        tariff="Скорость 300 Мбит/с",
        comments="Установить роутер",
        created_at="2026-09-19 20:00:00",
        status="Новая",
        synced=False,
    )

    db.save_application(app)
    retrieved = db.get_application(123456789)

    assert retrieved is not None
    assert retrieved.user_id == 123456789
    assert retrieved.username == "test_user"
    assert retrieved.fio == "Иванов Иван Иванович"
    assert retrieved.phone == "+7 (988) 777-66-55"
    assert retrieved.tariff == "Скорость 300 Мбит/с"
    assert retrieved.status == "Новая"
    assert retrieved.synced is False


def test_update_existing_application(db):
    app1 = ApplicationData(
        user_id=111,
        username="user1",
        fio="Первый",
        phone="+7 (900) 000-00-01",
        address="Адрес 1",
        tariff="Тариф 1",
        comments="Коммент 1",
        created_at="2026-09-19 10:00:00",
        status="Новая",
        synced=True,
    )
    db.save_application(app1)

    # User updates their address and phone
    app2 = ApplicationData(
        user_id=111,
        username="user1",
        fio="Первый",
        phone="+7 (900) 000-00-02",
        address="Новый Адрес",
        tariff="Тариф 2",
        comments="Коммент 2",
        created_at="2026-09-19 12:00:00",
        status="Обновлена",
        synced=False,
    )
    db.save_application(app2)

    updated = db.get_application(111)
    assert updated.phone == "+7 (900) 000-00-02"
    assert updated.address == "Новый Адрес"
    assert updated.tariff == "Тариф 2"
    assert updated.status == "Обновлена"
    assert updated.synced is False


def test_unsynced_and_mark_synced(db):
    app = ApplicationData(
        user_id=222,
        username="user2",
        fio="Второй",
        phone="+7 (900) 000-00-02",
        address="Адрес 2",
        tariff="Тариф 2",
        comments="Коммент",
        created_at="2026-09-19 11:00:00",
        status="Новая",
        synced=False,
    )
    db.save_application(app)

    unsynced = db.get_unsynced_applications()
    assert len(unsynced) == 1
    assert unsynced[0].user_id == 222

    db.mark_as_synced(222)
    assert len(db.get_unsynced_applications()) == 0

    app_synced = db.get_application(222)
    assert app_synced.synced is True


def test_delete_application(db):
    app = ApplicationData(
        user_id=333,
        username="user3",
        fio="Третий",
        phone="+7 (900) 000-00-03",
        address="Адрес 3",
        tariff="Тариф 3",
        comments="",
        created_at="2026-09-19 12:00:00",
        status="Новая",
        synced=True,
    )
    db.save_application(app)
    assert db.get_application(333) is not None

    deleted = db.delete_application(333)
    assert deleted is True
    assert db.get_application(333) is None

    # Deleting again returns False
    assert db.delete_application(333) is False
