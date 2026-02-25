import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATE = "state"
STATE_IDLE = "idle"
STATE_WAIT_MESSAGE_TEXT = "wait_message_text"
MESSAGES_LOG = "messages_log"

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE) -> None:
    if STATE not in context.user_data:
        context.user_data[STATE] = STATE_IDLE
    if MESSAGES_LOG not in context.user_data:
        context.user_data[MESSAGES_LOG] = []

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Написать новое сообщение"],
            ["Прочитать свои сообщения"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def flow_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Назад в главное меню"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def sender_to_str(user) -> str:
    if not user:
        return "Неизвестный отправитель"
    full_name = (user.full_name or "").strip() or "Пользователь"
    username = f"@{user.username}" if user.username else "-"
    return f"{full_name} (username: {username}, id: {user.id})"

def format_messages(items: list[dict]) -> str:
    if not items:
        return "У вас пока нет сохраненных сообщений."
    lines = []
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"{idx}. Текст: {item['text']}\n"
            f"   Отправитель: {item['sender']}\n"
            f"   Время отправки: {item['sent_at']}"
        )
    return "\n\n".join(lines)

def start_text(first_name: str) -> str:
    return (
        f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
        f"Если Вы собираетесь в опасное путешествие или в подозрительное место, "
        f"Вы можете оставить сообщение, которое поможет Вас найти в случае непредвиденной ситуации "
        f"и при отсутствии у Вас связи.\n\n"
        f"Через определенное время бот спросит, как у Вас дела. Если бот не получит ответа, он отправит Ваше сообщение в службу спасения.\n\n"
        f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно!"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"
    context.user_data[STATE] = STATE_IDLE
    await update.message.reply_text(
        start_text(first_name),
        reply_markup=main_menu_keyboard(),
    )

async def handle_idle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "Назад в главное меню":
        context.user_data[STATE] = STATE_IDLE
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return True
    if text == "Написать новое сообщение":
        context.user_data[STATE] = STATE_WAIT_MESSAGE_TEXT
        await update.message.reply_text("Введите текст одним сообщением.", reply_markup=flow_keyboard())
        return True
    if text == "Прочитать свои сообщения":
        items = context.user_data.get(MESSAGES_LOG, [])
        await update.message.reply_text(format_messages(items), reply_markup=main_menu_keyboard())
        return True
    return False

async def handle_wait_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    value = text.strip()
    if not value:
        await update.message.reply_text("Пустой текст. Введите сообщение еще раз.")
        return
    message_date = update.message.date if update.message else None
    sent_at = message_date.strftime("%d.%m.%Y %H:%M:%S") if message_date else datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    sender = sender_to_str(update.effective_user)
    items = context.user_data.get(MESSAGES_LOG, [])
    items.append(
        {
            "text": value,
            "sender": sender,
            "sent_at": sent_at,
        }
    )
    context.user_data[MESSAGES_LOG] = items
    context.user_data[STATE] = STATE_IDLE
    await update.message.reply_text(
        "Сообщение сохранено.\n\n"
        f"Текст: {value}\n"
        f"Отправитель: {sender}\n"
        f"Время отправки: {sent_at}",
        reply_markup=main_menu_keyboard(),
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    text = (update.message.text or "").strip()
    if await handle_idle_command(update, context, text):
        return
    state = context.user_data.get(STATE, STATE_IDLE)
    if state == STATE_WAIT_MESSAGE_TEXT:
        await handle_wait_message_text(update, context, text)
        return
    await update.message.reply_text("Используйте кнопки меню.", reply_markup=main_menu_keyboard())

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()