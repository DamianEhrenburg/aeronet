"""Telegram event handlers and ConversationHandler FSM for AeroNet."""

import html
import logging
import time
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from aeronet_core.config import (
    PROVIDER_NAME,
    DEFAULT_TARIFFS,
    TARIFF_MAP,
    ADVANTAGES_TEXT,
    ADMIN_CHAT_ID,
)
from aeronet_core.models import ApplicationData
from aeronet_core.validation import (
    normalize_phone,
    sanitize_fio,
    sanitize_address,
    sanitize_comments,
)
from aeronet_core.database import Database
from aeronet_core.sheets import SheetsClient
from aeronet_core.keyboards import (
    get_main_menu_keyboard,
    get_advantages_keyboard,
    get_tariffs_keyboard,
    get_tariff_selection_keyboard,
    get_phone_request_keyboard,
    get_remove_keyboard,
    get_skip_comments_keyboard,
    get_confirm_menu_keyboard,
    get_revoke_confirm_keyboard,
    get_edit_fields_keyboard,
)

logger = logging.getLogger(__name__)

# --- FSM States ---
(
    STATE_MAIN,
    STATE_FIO,
    STATE_ADDRESS,
    STATE_PHONE,
    STATE_TARIFF,
    STATE_COMMENTS,
    STATE_CONFIRM,
) = range(7)


def format_card(data: dict) -> str:
    """Render a clean, human-readable summary of the application."""
    fio = html.escape(data.get("fio", "Не указано"))
    address = html.escape(data.get("address", "Не указано"))
    phone = html.escape(data.get("phone", "Не указан"))
    tariff = html.escape(data.get("tariff", "Не выбран"))
    comments = html.escape(data.get("comments", "Без комментариев"))

    return (
        "<b>Ваша заявка на подключение:</b>\n\n"
        f"👤 <b>ФИО:</b> {fio}\n"
        f"🏠 <b>Адрес:</b> {address}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"⚡ <b>Тариф:</b> {tariff}\n"
        f"💬 <b>Комментарий:</b> {comments}\n\n"
        "Проверьте данные. Вы можете скорректировать любое поле перед подтверждением."
    )


class BotHandlers:
    """Encapsulates bot command handlers and state transitions."""

    def __init__(self, db: Database, sheets: SheetsClient):
        self.db = db
        self.sheets = sheets
        self._user_last_click: dict[int, float] = {}

    def _is_spam(self, user_id: int, cooldown: float = 0.4) -> bool:
        """Anti-flood: throttle rapid clicks from the same user."""
        now = time.monotonic()
        last = self._user_last_click.get(user_id, 0.0)
        if now - last < cooldown:
            return True
        self._user_last_click[user_id] = now
        return False

    async def _safe_edit(
        self, query, text: str, reply_markup=None, parse_mode=None
    ) -> None:
        """Edit message safely, ignoring harmless Message is not modified errors."""
        try:
            await query.edit_message_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except BadRequest as err:
            if "Message is not modified" in str(err):
                return
            raise

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /start command and render main menu."""
        user = update.effective_user
        existing_app = self.db.get_application(user.id)
        has_app = existing_app is not None

        greeting = (
            f"Здравствуйте, {html.escape(user.first_name)}.\n\n"
            f"Я бот провайдера «{PROVIDER_NAME}». Здесь вы можете подать заявку "
            f"на подключение интернета, выбрать подходящий тариф или узнать подробнее об услугах."
        )

        keyboard = get_main_menu_keyboard(has_application=has_app)

        if update.callback_query:
            await update.callback_query.answer()
            if self._is_spam(user.id):
                return STATE_MAIN
            await self._safe_edit(
                update.callback_query, greeting, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                greeting, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )

        return STATE_MAIN

    async def show_advantages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Display advantages of the provider."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_MAIN
            await self._safe_edit(
                query,
                ADVANTAGES_TEXT,
                reply_markup=get_advantages_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return STATE_MAIN

    async def show_tariffs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Display catalog of available internet plans."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_MAIN

        lines = [f"⚡ <b>Тарифные планы провайдера «{PROVIDER_NAME}»</b>\n"]
        for t in DEFAULT_TARIFFS:
            if t.code == "consultation":
                lines.append(f"🤝 <b>{t.title}</b> — {t.price}")
                lines.append(f"   {t.description}\n")
            else:
                lines.append(f"🌐 <b>{t.title}</b> — <b>{t.price}</b>")
                lines.append(f"   Скорость: <b>{t.speed}</b> · {t.description}\n")

        lines.append("Для оформления подключения нажмите «Оставить заявку».")
        text = "\n".join(lines)

        if query:
            await self._safe_edit(
                query, text, reply_markup=get_tariffs_keyboard(), parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                text, reply_markup=get_tariffs_keyboard(), parse_mode=ParseMode.HTML
            )
        return STATE_MAIN

    async def my_application(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show existing application card to the user."""
        user_id = update.effective_user.id
        app = self.db.get_application(user_id)

        if not app:
            msg = "У вас пока нет активной заявки. Вы можете оставить её прямо сейчас."
            kb = get_main_menu_keyboard(has_application=False)
            if update.callback_query:
                await update.callback_query.answer()
                if self._is_spam(user_id):
                    return STATE_MAIN
                await self._safe_edit(update.callback_query, msg, reply_markup=kb)
            else:
                await update.message.reply_text(msg, reply_markup=kb)
            return STATE_MAIN

        # Populate context for possible editing
        context.user_data.clear()
        context.user_data["fio"] = app.fio
        context.user_data["address"] = app.address
        context.user_data["phone"] = app.phone
        context.user_data["tariff"] = app.tariff
        context.user_data["comments"] = app.comments

        card_text = format_card(context.user_data)
        kb = get_confirm_menu_keyboard(is_submitted=True)

        if update.callback_query:
            await update.callback_query.answer()
            if self._is_spam(user_id):
                return STATE_CONFIRM
            await self._safe_edit(
                update.callback_query, card_text, reply_markup=kb, parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                card_text, reply_markup=kb, parse_mode=ParseMode.HTML
            )

        return STATE_CONFIRM

    async def start_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Begin new application questionnaire."""
        user_id = update.effective_user.id
        if update.callback_query:
            await update.callback_query.answer()
            if self._is_spam(user_id):
                return STATE_MAIN

        existing_app = self.db.get_application(user_id)

        if existing_app:
            # Prefill from existing application
            context.user_data.clear()
            context.user_data["fio"] = existing_app.fio
            context.user_data["address"] = existing_app.address
            context.user_data["phone"] = existing_app.phone
            context.user_data["tariff"] = existing_app.tariff
            context.user_data["comments"] = existing_app.comments

            query = update.callback_query
            if query:
                await self._safe_edit(
                    query,
                    format_card(context.user_data),
                    reply_markup=get_confirm_menu_keyboard(is_submitted=True),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await update.message.reply_text(
                    format_card(context.user_data),
                    reply_markup=get_confirm_menu_keyboard(is_submitted=True),
                    parse_mode=ParseMode.HTML,
                )
            return STATE_CONFIRM

        context.user_data.clear()
        prompt = (
            "📝 <b>Заполнение заявки на подключение</b>\n\n"
            "Шаг 1 из 5: Введите ваше <b>ФИО</b> (полностью):"
        )
        if update.callback_query:
            await self._safe_edit(update.callback_query, prompt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(prompt, parse_mode=ParseMode.HTML)

        return STATE_FIO

    async def restart_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Restart application questionnaire from scratch."""
        user_id = update.effective_user.id
        if update.callback_query:
            await update.callback_query.answer()
            if self._is_spam(user_id):
                return STATE_CONFIRM
        context.user_data.clear()
        prompt = (
            "📝 <b>Заполнение новой заявки на подключение</b>\n\n"
            "Шаг 1 из 5: Введите ваше <b>ФИО</b> (полностью):"
        )
        if update.callback_query:
            await self._safe_edit(update.callback_query, prompt, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(prompt, parse_mode=ParseMode.HTML)

        return STATE_FIO

    async def handle_fio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Validate and store FIO."""
        raw_text = update.message.text
        sanitized = sanitize_fio(raw_text)

        if not sanitized:
            await update.message.reply_text(
                "Пожалуйста, введите корректное ФИО (минимум 2 буквы):"
            )
            return STATE_FIO

        context.user_data["fio"] = sanitized

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")
            return await self._show_confirmation(update, context)

        await update.message.reply_text(
            "Шаг 2 из 5: Укажите точный <b>адрес подключения</b> "
            "(город, улица, номер дома и квартиры):",
            parse_mode=ParseMode.HTML,
        )
        return STATE_ADDRESS

    async def handle_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Validate and store address."""
        raw_text = update.message.text
        sanitized = sanitize_address(raw_text)

        if not sanitized:
            await update.message.reply_text(
                "Пожалуйста, укажите более подробный адрес (город, улица, дом):"
            )
            return STATE_ADDRESS

        context.user_data["address"] = sanitized

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")
            return await self._show_confirmation(update, context)

        await update.message.reply_text(
            "Шаг 3 из 5: Введите ваш <b>контактный номер телефона</b>\n"
            "или нажмите кнопку внизу, чтобы поделиться контактом:",
            reply_markup=get_phone_request_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return STATE_PHONE

    async def handle_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Validate and store phone number."""
        raw_phone = ""
        if update.message.contact:
            raw_phone = update.message.contact.phone_number
        elif update.message.text:
            raw_phone = update.message.text

        normalized = normalize_phone(raw_phone)
        if not normalized:
            await update.message.reply_text(
                "Не удалось распознать номер телефона. "
                "Пожалуйста, введите номер в формате +7 (988) 777-66-55 или 89887776655:",
                reply_markup=get_phone_request_keyboard(),
            )
            return STATE_PHONE

        context.user_data["phone"] = normalized

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")
            await update.message.reply_text("Номер сохранён.", reply_markup=get_remove_keyboard())
            return await self._show_confirmation(update, context)

        await update.message.reply_text(
            "Номер сохранён.",
            reply_markup=get_remove_keyboard(),
        )
        await update.message.reply_text(
            "Шаг 4 из 5: Выберите желаемый <b>тарифный план</b>:",
            reply_markup=get_tariff_selection_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return STATE_TARIFF

    async def handle_tariff_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Store selected tariff from inline buttons."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_TARIFF

        tariff_code = query.data.replace("select_tariff_", "") if query else ""
        tariff_item = TARIFF_MAP.get(tariff_code)

        if tariff_item:
            context.user_data["tariff"] = tariff_item.title
        else:
            context.user_data["tariff"] = "Консультация специалиста"

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")
            return await self._show_confirmation(update, context)

        selected_title = context.user_data["tariff"]
        if query:
            await self._safe_edit(
                query,
                f"Шаг 4 из 5: Выбран тариф <b>{html.escape(selected_title)}</b>.",
                parse_mode=ParseMode.HTML,
            )

        prompt = (
            "Шаг 5 из 5: При необходимости оставьте <b>комментарий</b> к заявке "
            "(удобное время звонка, наличие своего роутера и т.д.) "
            "или нажмите кнопку внизу:"
        )
        if query:
            await query.message.reply_text(
                prompt, reply_markup=get_skip_comments_keyboard(), parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                prompt, reply_markup=get_skip_comments_keyboard(), parse_mode=ParseMode.HTML
            )
        return STATE_COMMENTS

    async def handle_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Store comments and proceed to confirmation."""
        raw_text = update.message.text
        context.user_data["comments"] = sanitize_comments(raw_text)

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")

        return await self._show_confirmation(update, context)

    async def skip_comments(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Skip optional comments."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_COMMENTS
        context.user_data["comments"] = "Без комментариев"

        if context.user_data.get("_editing"):
            context.user_data.pop("_editing")

        return await self._show_confirmation(update, context)

    async def _show_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Render final confirmation card."""
        card_text = format_card(context.user_data)
        kb = get_confirm_menu_keyboard()

        if update.callback_query:
            await self._safe_edit(
                update.callback_query, card_text, reply_markup=kb, parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                card_text, reply_markup=kb, parse_mode=ParseMode.HTML
            )

        return STATE_CONFIRM

    async def edit_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Show list of fields that can be edited."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM
            await self._safe_edit(
                query,
                "Какое поле вы хотите изменить?",
                reply_markup=get_edit_fields_keyboard(),
            )
        return STATE_CONFIRM

    async def request_edit_field(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Prompt user for a specific field edit."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM

        action = query.data
        context.user_data["_editing"] = True

        if action == "edit_fio":
            await self._safe_edit(query, "Введите новое ФИО:")
            return STATE_FIO
        elif action == "edit_address":
            await self._safe_edit(query, "Введите новый адрес подключения:")
            return STATE_ADDRESS
        elif action == "edit_phone":
            await query.message.reply_text(
                "Введите новый номер телефона или поделитесь контактом:",
                reply_markup=get_phone_request_keyboard(),
            )
            return STATE_PHONE
        elif action == "edit_tariff":
            await self._safe_edit(
                query,
                "Выберите новый тарифный план:",
                reply_markup=get_tariff_selection_keyboard(),
            )
            return STATE_TARIFF
        elif action == "edit_comments":
            await self._safe_edit(
                query,
                "Введите новый комментарий:",
                reply_markup=get_skip_comments_keyboard(),
            )
            return STATE_COMMENTS

        return STATE_CONFIRM

    async def back_to_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Return from edit menu back to application confirmation card."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM
        return await self._show_confirmation(update, context)

    async def confirm_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Save application to local SQLite and sync to Google Sheets."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM

        user = update.effective_user
        data = context.user_data

        app = ApplicationData(
            user_id=user.id,
            username=user.username or "",
            fio=data.get("fio", "Не указано"),
            phone=data.get("phone", "Не указан"),
            address=data.get("address", "Не указано"),
            tariff=data.get("tariff", "Консультация специалиста"),
            comments=data.get("comments", "Без комментариев"),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="Новая",
            synced=False,
        )

        # 1. Local SQLite persistence (guaranteed, zero data loss)
        self.db.save_application(app)
        logger.info("Saved application for user %d to local database.", user.id)

        # 2. Async Google Sheets sync
        synced = await self.sheets.save_or_update_application(app)
        if synced:
            self.db.mark_as_synced(user.id)
            logger.info("Synchronized application for user %d to Google Sheets.", user.id)

        # 3. Optional Admin notification
        if ADMIN_CHAT_ID:
            try:
                admin_msg = (
                    "🚨 <b>Новая заявка на подключение!</b>\n\n"
                    f"👤 {app.fio} (@{app.username or 'N/A'})\n"
                    f"📞 {app.phone}\n"
                    f"🏠 {app.address}\n"
                    f"⚡ {app.tariff}\n"
                    f"💬 {app.comments}"
                )
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode=ParseMode.HTML
                )
            except Exception as exc:
                logger.warning("Could not notify admin: %s", exc)

        context.user_data.clear()

        success_text = (
            "✅ <b>Заявка успешно принята!</b>\n\n"
            f"Наш специалист свяжется с вами по номеру <code>{html.escape(app.phone)}</code> "
            "для согласования даты и времени подключения.\n\n"
            "Вы можете в любой момент посмотреть статус или изменить контакты через команду /my_application."
        )

        if query:
            await self._safe_edit(
                query,
                success_text,
                reply_markup=get_main_menu_keyboard(has_application=True),
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                success_text,
                reply_markup=get_main_menu_keyboard(has_application=True),
                parse_mode=ParseMode.HTML,
            )

        return STATE_MAIN

    async def revoke_application_prompt(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Prompt confirmation to revoke submitted application."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM
        text = (
            "⚠️ <b>Подтверждение отзыва заявки</b>\n\n"
            "Вы действительно хотите отозвать вашу заявку на подключение? "
            "Все сохранённые данные будут удалены."
        )
        if query:
            await self._safe_edit(
                query,
                text,
                reply_markup=get_revoke_confirm_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return STATE_CONFIRM

    async def confirm_revoke(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Execute application revocation from SQLite and Google Sheets."""
        query = update.callback_query
        if query:
            await query.answer()
            if self._is_spam(update.effective_user.id):
                return STATE_CONFIRM
        user_id = update.effective_user.id

        self.db.delete_application(user_id)
        await self.sheets.delete_application(user_id)
        context.user_data.clear()

        text = (
            "🗑️ <b>Заявка отозвана</b>\n\n"
            "Ваша заявка удалена. Вы можете подать новую заявку в любое время."
        )
        if query:
            await self._safe_edit(
                query,
                text,
                reply_markup=get_main_menu_keyboard(has_application=False),
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_main_menu_keyboard(has_application=False),
                parse_mode=ParseMode.HTML,
            )
        return STATE_MAIN

    async def reset_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Direct command /reset to wipe current user application."""
        user_id = update.effective_user.id
        self.db.delete_application(user_id)
        await self.sheets.delete_application(user_id)
        context.user_data.clear()

        text = (
            "🗑️ <b>Ваша анкета сброшена</b>\n\n"
            "Все сохранённые данные удалены. Вы можете заполнить анкету заново через /start."
        )
        await update.message.reply_text(
            text,
            reply_markup=get_main_menu_keyboard(has_application=False),
            parse_mode=ParseMode.HTML,
        )
        return STATE_MAIN

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel current operation and return to main menu."""
        user_id = update.effective_user.id
        existing_app = self.db.get_application(user_id)
        has_app = existing_app is not None
        context.user_data.clear()
        cancel_text = "Действие отменено."

        if update.callback_query:
            await update.callback_query.answer()
            if self._is_spam(user_id):
                return STATE_MAIN
            await self._safe_edit(
                update.callback_query,
                cancel_text,
                reply_markup=get_main_menu_keyboard(has_application=has_app),
            )
        else:
            await update.message.reply_text(
                cancel_text,
                reply_markup=get_main_menu_keyboard(has_application=has_app),
            )

        return STATE_MAIN

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display help instructions."""
        help_text = (
            f"<b>Команды бота «{PROVIDER_NAME}»:</b>\n\n"
            "/start — Главное меню\n"
            "/my_application — Посмотреть или изменить сохранённую анкету\n"
            "/tariffs — Список тарифных планов\n"
            "/advantages — Преимущества подключения\n"
            "/reset — Отозвать и удалить мою анкету\n"
            "/cancel — Отменить текущее действие\n"
            "/help — Показать эту справку"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
