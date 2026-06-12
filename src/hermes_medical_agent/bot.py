from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from hermes_medical_agent.parser import parse_caption
from hermes_medical_agent.settings import load_settings
from hermes_medical_agent.storage import MedicalStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = load_settings()
store = MedicalStore(settings.medical_data_dir, settings.medical_db_path)
store.init()


def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    allowed = settings.allowed_user_ids
    return not allowed or user.id in allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Hermes Medical Agent MVP is running. Send a PDF/photo with caption: type/date/comment."
    )


async def timeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    rows = store.recent_timeline(limit=20)
    if not rows:
        await update.message.reply_text("Timeline is empty.")
        return
    text = "Recent timeline:\n" + "\n".join(
        f"- {date or 'date unknown'} — {title}: {body}" for date, title, body in rows
    )
    await update.message.reply_text(text[:4000])


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    message = update.effective_message
    if message is None:
        return

    attachment = None
    filename = None
    mime_type = None

    if message.document:
        attachment = message.document
        filename = message.document.file_name
        mime_type = message.document.mime_type
    elif message.photo:
        attachment = message.photo[-1]
        filename = "telegram_photo.jpg"
        mime_type = "image/jpeg"

    if attachment is None:
        await message.reply_text("Send a PDF/document or photo with an optional caption.")
        return

    tg_file = await context.bot.get_file(attachment.file_id)
    content = await tg_file.download_as_bytearray()
    metadata = parse_caption(message.caption)

    stored = store.store_bytes(bytes(content), filename)
    store.insert_document(
        document=stored,
        telegram_user_id=message.from_user.id,
        telegram_message_id=message.message_id,
        original_filename=filename,
        mime_type=mime_type,
        document_type=metadata.document_type,
        document_date=metadata.document_date,
        user_comment=metadata.comment,
    )

    await message.reply_text(
        "Stored medical document.\n"
        f"id: {stored.document_id}\n"
        f"type: {metadata.document_type or 'unknown'}\n"
        f"date: {metadata.document_date or 'unknown'}\n"
        f"sha256: {stored.sha256[:16]}…"
    )


async def text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "MVP command support: /start, /timeline. Send files to ingest. Search/LLM retrieval comes next."
    )


def main() -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("timeline", timeline))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_fallback))
    app.run_polling()


if __name__ == "__main__":
    main()
