import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

STATE_WAITING_MESSAGE = "waiting_message"
DRAFT_MESSAGE_TEXT = "draft_message_text"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Прочитать сообщения", callback_data="read_messages")],
            [InlineKeyboardButton("Написать сообщение", callback_data="write_message")],
        ]
    )

    await update.message.reply_text(f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
                                    f"Если Вы собираетесь в опасное путешествие или в подозрительное место, Вы можете оставить сообщение, которое поможет Вас найти в случае непредвиденной ситуации и при отсутствии у Вас связи. \n\n"
                                    f"Какое сообщение, кому и когда - решаете Вы. \n\n"
                                    f"Вы всегда сможете удалить свои сообщения, изменить даты отправки, изменить адресатов.\n\n"
                                    f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно.\n\n",
                                    reply_markup=keyboard,
                                    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

async def start_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = user.username or ""
    language_code = user.language_code or ""

async def read_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(f"Ваши сообщения: \n\n"
                                  f""
                                  f"Список из базы...")

async def write_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    context.user_data[STATE_WAITING_MESSAGE] = True
    context.user_data.pop(DRAFT_MESSAGE_TEXT, None)

    await query.edit_message_text("Введите текст сообщения одним сообщением.")

async def receive_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get(STATE_WAITING_MESSAGE):
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустой текст. Напишите сообщение ещё раз.")
        return

    context.user_data[DRAFT_MESSAGE_TEXT] = text
    context.user_data[STATE_WAITING_MESSAGE] = False

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Когда отправить", callback_data="set_when")],
            [InlineKeyboardButton("Кому отправить", callback_data="set_who")],
        ]
    )

    await update.message.reply_text(
        f"Сообщение сохранено:\n\n{text}\n\nВыберите следующий шаг:",
        reply_markup=keyboard,
    )

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_click, pattern=r"^start_click$"))
    app.add_handler(CommandHandler("ping", ping))

    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
