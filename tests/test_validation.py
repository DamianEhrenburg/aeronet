import pytest
from aeronet_core.validation import (
    normalize_phone,
    sanitize_fio,
    sanitize_address,
    sanitize_comments,
)


def test_normalize_phone_valid_russian_numbers():
    assert normalize_phone("+7 (988) 777-66-55") == "+7 (988) 777-66-55"
    assert normalize_phone("89887776655") == "+7 (988) 777-66-55"
    assert normalize_phone("79887776655") == "+7 (988) 777-66-55"
    assert normalize_phone("+7 988 777 66 55") == "+7 (988) 777-66-55"
    assert normalize_phone("8-988-777-66-55") == "+7 (988) 777-66-55"


def test_normalize_phone_valid_international_numbers():
    assert normalize_phone("+375 29 123 45 67") == "+375291234567"
    assert normalize_phone("+995 555 12 34 56") == "+995555123456"


def test_normalize_phone_invalid_numbers():
    assert normalize_phone("8383838") is None
    assert normalize_phone("0999999") is None
    assert normalize_phone("phone number") is None
    assert normalize_phone("") is None
    assert normalize_phone("12345") is None


def test_sanitize_fio():
    assert sanitize_fio("  Иванов   Иван Иванович  ") == "Иванов Иван Иванович"
    assert sanitize_fio("Петров Петр") == "Петров Петр"
    assert sanitize_fio("Я") is None
    assert sanitize_fio("   ") is None
    assert sanitize_fio("123456") is None


def test_sanitize_address():
    assert sanitize_address("  г. Ставрополь, ул. Ленина, д. 10, кв. 5  ") == "г. Ставрополь, ул. Ленина, д. 10, кв. 5"
    assert sanitize_address("ул. Мира 1") == "ул. Мира 1"
    assert sanitize_address("ул") is None
    assert sanitize_address("   ") is None


def test_sanitize_comments():
    assert sanitize_comments("Позвонить после 18:00") == "Позвонить после 18:00"
    assert sanitize_comments("-") == "Без комментариев"
    assert sanitize_comments("  -  ") == "Без комментариев"
    assert sanitize_comments("нет") == "Без комментариев"
    assert sanitize_comments("") == "Без комментариев"
