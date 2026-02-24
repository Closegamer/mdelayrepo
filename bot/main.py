import os
import logging

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

STATE_WAITING_MESSAGE = "waiting_message"
DRAFT_MESSAGE_TEXT = "draft_message_text"

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Прочитать сообщения"], ["Написать сообщение"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def draft_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Когда отправить"], ["Кому отправить"], ["В главное меню"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"

    context.user_data[STATE_WAITING_MESSAGE] = False
    context.user_data.pop(DRAFT_MESSAGE_TEXT, None)

    await update.message.reply_text(
        f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
        f"Если Вы собираетесь в опасное путешествие или в подозрительное место, "
        f"Вы можете оставить сообщение, которое поможет Вас найти в случае "
        f"непредвиденной ситуации и при отсутствии у Вас связи.\n\n"
        f"Какое сообщение, кому и когда - решаете Вы.\n\n"
        f"Вы всегда сможете удалить свои сообщения, изменить даты отправки, "
        f"изменить адресатов.\n\n"
        f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно.\n\n",
        reply_markup=main_menu_keyboard(),
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == "Прочитать сообщения":
        await update.message.reply_text(
            "Ваши сообщения:\n\nСписок из базы...",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text == "Написать сообщение":
        context.user_data[STATE_WAITING_MESSAGE] = True
        context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
        await update.message.reply_text(
            "Введите текст сообщения одним сообщением.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if text == "Когда отправить":
        await update.message.reply_text(
            "Здесь будет настройка даты и времени отправки.",
            reply_markup=draft_menu_keyboard(),
        )
        return

    if text == "Кому отправить":
        await update.message.reply_text(
            "Здесь будет выбор получателя.",
            reply_markup=draft_menu_keyboard(),
        )
        return

    if text == "В главное меню":
        context.user_data[STATE_WAITING_MESSAGE] = False
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Если ожидаем текст сообщения, сохраняем черновик
    if context.user_data.get(STATE_WAITING_MESSAGE):
        if not text:
            await update.message.reply_text("Пустой текст. Напишите сообщение ещё раз.")
            return

        context.user_data[DRAFT_MESSAGE_TEXT] = text
        context.user_data[STATE_WAITING_MESSAGE] = False

        await update.message.reply_text(
            f"Сообщение сохранено:\n\n{text}\n\nВыберите следующий шаг:",
            reply_markup=draft_menu_keyboard(),
        )
        return

    # Текст вне сценария
    await update.message.reply_text(
        "Используйте кнопки меню ниже.",
        reply_markup=main_menu_keyboard(),
    )

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()