"""Main entry point for AeroNet Telegram bot."""

import asyncio
import logging
import sys
from telegram import BotCommand
from telegram.error import TimedOut, NetworkError, BadRequest
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from aeronet_core.config import TELEGRAM_BOT_TOKEN, DB_PATH, GOOGLE_SHEET_URL
from aeronet_core.database import Database
from aeronet_core.sheets import SheetsClient
from aeronet_core.handlers import (
    BotHandlers,
    STATE_MAIN,
    STATE_FIO,
    STATE_ADDRESS,
    STATE_PHONE,
    STATE_TARIFF,
    STATE_COMMENTS,
    STATE_CONFIRM,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("aeronet")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates, suppressing benign network and UI race conditions."""
    err = context.error
    if isinstance(err, (TimedOut, NetworkError)):
        logger.warning("Network or timeout notice: %s", err)
        return
    if isinstance(err, BadRequest) and "Message is not modified" in str(err):
        return
    logger.error("Unhandled exception while processing update:", exc_info=err)


async def post_init(application: Application) -> None:
    """Setup Telegram command menu and initialize Google Sheets headers."""
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("my_application", "Моя анкета"),
        BotCommand("tariffs", "Тарифные планы"),
        BotCommand("advantages", "Преимущества"),
        BotCommand("reset", "Отозвать и сбросить анкету"),
        BotCommand("help", "Справка"),
        BotCommand("cancel", "Отменить текущее действие"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Configured Telegram command menu.")

    sheets: SheetsClient = application.bot_data["sheets"]
    await sheets.ensure_headers()

    application.create_task(sync_worker(application))


async def sync_worker(application: Application) -> None:
    """Periodic task to retry syncing unsynced records to Google Sheets."""
    db: Database = application.bot_data["db"]
    sheets: SheetsClient = application.bot_data["sheets"]

    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            await sheets.sync_pending(db)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Error in sync_worker: %s", exc)


def build_application() -> Application:
    """Build and configure the python-telegram-bot Application."""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set in environment.")
        sys.exit(1)

    db = Database(db_path=DB_PATH)
    db.init_db()

    sheets = SheetsClient(sheet_url=GOOGLE_SHEET_URL)

    handlers = BotHandlers(db=db, sheets=sheets)

    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=15.0,
        read_timeout=20.0,
        write_timeout=15.0,
        pool_timeout=5.0,
    )

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .concurrent_updates(True)
        .build()
    )

    app.add_error_handler(error_handler)

    app.bot_data["db"] = db
    app.bot_data["sheets"] = sheets

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", handlers.start),
            CommandHandler("my_application", handlers.my_application),
            CommandHandler("tariffs", handlers.show_tariffs),
            CommandHandler("advantages", handlers.show_advantages),
            CommandHandler("reset", handlers.reset_command),
            CallbackQueryHandler(handlers.start_form, pattern="^start_form$"),
            CallbackQueryHandler(handlers.restart_form, pattern="^restart_form$"),
            CallbackQueryHandler(handlers.revoke_application_prompt, pattern="^revoke_application$"),
            CallbackQueryHandler(handlers.confirm_revoke, pattern="^confirm_revoke$"),
            CallbackQueryHandler(handlers.my_application, pattern="^my_application$"),
            CallbackQueryHandler(handlers.show_advantages, pattern="^show_advantages$"),
            CallbackQueryHandler(handlers.show_tariffs, pattern="^show_tariffs$"),
        ],
        states={
            STATE_MAIN: [
                CallbackQueryHandler(handlers.start_form, pattern="^start_form$"),
                CallbackQueryHandler(handlers.my_application, pattern="^my_application$"),
                CallbackQueryHandler(handlers.show_advantages, pattern="^show_advantages$"),
                CallbackQueryHandler(handlers.show_tariffs, pattern="^show_tariffs$"),
                CallbackQueryHandler(handlers.start, pattern="^back_to_main$"),
            ],
            STATE_FIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_fio),
            ],
            STATE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_address),
            ],
            STATE_PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), handlers.handle_phone),
            ],
            STATE_TARIFF: [
                CallbackQueryHandler(handlers.handle_tariff_selection, pattern="^select_tariff_"),
            ],
            STATE_COMMENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_comments),
                CallbackQueryHandler(handlers.skip_comments, pattern="^skip_comments$"),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(handlers.confirm_save, pattern="^confirm_save$"),
                CallbackQueryHandler(handlers.edit_menu, pattern="^edit_menu$"),
                CallbackQueryHandler(handlers.cancel, pattern="^cancel_form$"),
                CallbackQueryHandler(handlers.start, pattern="^back_to_main$"),
                CallbackQueryHandler(handlers.restart_form, pattern="^restart_form$"),
                CallbackQueryHandler(handlers.revoke_application_prompt, pattern="^revoke_application$"),
                CallbackQueryHandler(handlers.confirm_revoke, pattern="^confirm_revoke$"),
                CallbackQueryHandler(handlers.my_application, pattern="^my_application$"),
                CallbackQueryHandler(handlers.request_edit_field, pattern="^edit_"),
                CallbackQueryHandler(handlers.back_to_confirmation, pattern="^back_to_confirm$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            CommandHandler("help", handlers.help_command),
            CommandHandler("reset", handlers.reset_command),
        ],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("tariffs", handlers.show_tariffs))
    app.add_handler(CommandHandler("advantages", handlers.show_advantages))
    app.add_handler(CommandHandler("reset", handlers.reset_command))

    return app


def main() -> None:
    """Run bot polling."""
    application = build_application()
    logger.info("Starting AeroNet bot polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
