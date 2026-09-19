"""Keyboards and interactive menus for AeroNet."""

from typing import List
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aeronet_core.config import DEFAULT_TARIFFS


def get_main_menu_keyboard(has_application: bool = False) -> InlineKeyboardMarkup:
    """Generate main menu buttons."""
    if has_application:
        buttons = [
            [InlineKeyboardButton("📋 Моя анкета", callback_data="my_application")],
            [InlineKeyboardButton("⚡ Тарифы", callback_data="show_tariffs")],
            [InlineKeyboardButton("⭐ Преимущества", callback_data="show_advantages")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton("📝 Оставить заявку", callback_data="start_form")],
            [InlineKeyboardButton("⚡ Тарифы", callback_data="show_tariffs")],
            [InlineKeyboardButton("⭐ Преимущества", callback_data="show_advantages")],
        ]
    return InlineKeyboardMarkup(buttons)


def get_advantages_keyboard() -> InlineKeyboardMarkup:
    """Keyboard under advantages text."""
    buttons = [
        [InlineKeyboardButton("📝 Подать заявку сейчас", callback_data="start_form")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Catalog of tariffs view."""
    buttons = [
        [InlineKeyboardButton(f"⚡ {t.title} ({t.price})", callback_data=f"tariff_info_{t.code}")]
        for t in DEFAULT_TARIFFS
    ]
    buttons.append([InlineKeyboardButton("📝 Подать заявку", callback_data="start_form")])
    buttons.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)


def get_tariff_selection_keyboard() -> InlineKeyboardMarkup:
    """Selection keyboard inside the application form."""
    buttons = [
        [InlineKeyboardButton(f"{t.title} — {t.price}", callback_data=f"select_tariff_{t.code}")]
        for t in DEFAULT_TARIFFS
    ]
    return InlineKeyboardMarkup(buttons)


def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """One-time reply keyboard to share contact securely."""
    button = KeyboardButton("📱 Поделиться номером телефона", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)


def get_remove_keyboard() -> ReplyKeyboardRemove:
    """Clear reply keyboard."""
    return ReplyKeyboardRemove()


def get_skip_comments_keyboard() -> InlineKeyboardMarkup:
    """Inline button to skip optional comments step."""
    button = [InlineKeyboardButton("Пропустить (без комментариев) ➡️", callback_data="skip_comments")]
    return InlineKeyboardMarkup([button])


def get_confirm_menu_keyboard() -> InlineKeyboardMarkup:
    """Confirmation before final submission."""
    buttons = [
        [InlineKeyboardButton("✅ Всё верно, отправить", callback_data="confirm_save")],
        [InlineKeyboardButton("✏️ Изменить поле", callback_data="edit_menu")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_form")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_edit_fields_keyboard() -> InlineKeyboardMarkup:
    """Field selection for editing."""
    buttons = [
        [InlineKeyboardButton("👤 Изменить ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton("🏠 Изменить Адрес", callback_data="edit_address")],
        [InlineKeyboardButton("📞 Изменить Телефон", callback_data="edit_phone")],
        [InlineKeyboardButton("⚡ Изменить Тариф", callback_data="edit_tariff")],
        [InlineKeyboardButton("💬 Изменить Комментарий", callback_data="edit_comments")],
        [InlineKeyboardButton("⬅️ Назад к проверке", callback_data="back_to_confirm")],
    ]
    return InlineKeyboardMarkup(buttons)
