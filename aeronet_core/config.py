"""Configuration and tariff catalog for AeroNet."""

import os
from typing import List, Optional
from dotenv import load_dotenv
from aeronet_core.models import Tariff

load_dotenv()

# --- Core Bot & Google Sheets Settings ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GOOGLE_SHEET_URL: str = os.getenv("GOOGLE_SHEET_URL", "").strip()
PROVIDER_NAME: str = os.getenv("PROVIDER_NAME", "AeroNet").strip()
CREDENTIALS_FILE: str = os.getenv("CREDENTIALS_FILE", "credentials.json").strip()
DB_PATH: str = os.getenv("DB_PATH", "aeronet.db").strip()
ADMIN_CHAT_ID: Optional[str] = os.getenv("ADMIN_CHAT_ID", "").strip() or None

# --- Standard Column Headers in Google Spreadsheet ---
SHEET_HEADERS: List[str] = [
    "ID пользователя",
    "Telegram Username",
    "ФИО",
    "Телефон",
    "Адрес",
    "Тариф",
    "Комментарий",
    "Дата заявки",
    "Статус",
]

# --- Catalog of Tariffs ---
DEFAULT_TARIFFS: List[Tariff] = [
    Tariff(
        code="comfort_100",
        title="Комфорт 100 Мбит/с",
        speed="100 Мбит/с",
        price="500 ₽/мес",
        description="Стабильный интернет для работы, соцсетей и видеозвонков.",
    ),
    Tariff(
        code="speed_300",
        title="Скорость 300 Мбит/с",
        speed="300 Мбит/с",
        price="700 ₽/мес",
        description="Быстрая загрузка файлов и просмотр видео в 4K на нескольких устройствах.",
    ),
    Tariff(
        code="max_500",
        title="Максимум 500 Мбит/с",
        speed="500 Мбит/с",
        price="900 ₽/мес",
        description="Высокая пропускная способность для умного дома и одновременного стриминга.",
    ),
    Tariff(
        code="ultra_1000",
        title="Ультра 1000 Мбит/с + ТВ",
        speed="1000 Мбит/с",
        price="1200 ₽/мес",
        description="Гигабитный интернет и пакет интерактивного ТВ (более 200 каналов).",
    ),
    Tariff(
        code="consultation",
        title="Консультация специалиста",
        speed="Индивидуально",
        price="Бесплатно",
        description="Помощь в выборе оборудования и проверка технической возможности по адресу.",
    ),
]

TARIFF_MAP = {t.code: t for t in DEFAULT_TARIFFS}

# --- Advantages Text ---
ADVANTAGES_TEXT = (
    f"🏆 <b>Преимущества подключения к «{PROVIDER_NAME}»:</b>\n\n"
    "• Скорость до 1000 Мбит/с по оптоволоконной линии (GPON/FTTB)\n"
    "• Стабильный пинг для онлайн-игр и удалённой работы\n"
    "• Бесплатный выезд инженера и настройка Wi-Fi оборудования\n"
    "• Круглосуточная служба технической поддержки\n"
    "• Быстрое подключение в течение 1–2 рабочих дней после заявки\n"
    "• Безопасность персональных данных: данные используются только для заключения договора"
)
