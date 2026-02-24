import os
import logging
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
STATE_WAIT_RECIPIENT_PICK = "wait_recipient_pick"
STATE_WAIT_WHEN = "wait_when"
DRAFT_MESSAGE_TEXT = "draft_message_text"
DRAFT_RECIPIENTS_SELECTED = "draft_recipients_selected"
DRAFT_WHEN = "draft_when"

HARD_RECIPIENTS = [
    {"name": "Мама", "telegram": "@mama_example", "email": "mama@example.com"},
    {"name": "Папа", "telegram": "@papa_example", "email": "papa@example.com"},
    {"name": "Брат", "telegram": "@brother_example", "email": "brother@example.com"},
    {"name": "Друг Илья", "telegram": "@ilya_example", "email": "ilya@example.com"},
    {"name": "Друг Анна", "telegram": "@anna_example", "email": "anna@example.com"},
]

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE) -> None:
    if STATE not in context.user_data:
        context.user_data[STATE] = STATE_IDLE

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Написать сообщение"],
            ["Показать тестовых адресатов"],
            ["Прочитать сообщения"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def draft_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Отправить всем тестовым адресатам"],
            ["Выбрать тестовых адресатов"],
            ["Назад в главное меню"],
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

def recipient_to_str(item: dict) -> str:
    return f"{item['name']} (TG: {item['telegram']}, Email: {item['email']})"

def format_recipients(book: list[dict]) -> str:
    return "\n".join([f"{idx}. {recipient_to_str(item)}" for idx, item in enumerate(book, start=1)])

def selected_to_lines(values: list[str]) -> str:
    if not values:
        return "- (пусто)"
    return "\n".join([f"- {x}" for x in values])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"

    context.user_data[STATE] = STATE_IDLE
    context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
    context.user_data.pop(DRAFT_RECIPIENTS_SELECTED, None)
    context.user_data.pop(DRAFT_WHEN, None)

    await update.message.reply_text(
        f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
        f"Если Вы собираетесь в опасное путешествие или в подозрительное место, "
        f"Вы можете оставить сообщение, которое поможет Вас найти в случае непредвиденной ситуации "
        f"и при отсутствии у Вас связи.\n\n"
        f"Какое сообщение, кому и когда - решаете Вы.\n\n"
        f"Вы всегда сможете удалить свои сообщения, изменить даты отправки, изменить адресатов.\n\n"
        f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно.\n\n",
        reply_markup=main_menu_keyboard(),
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

async def handle_idle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "Назад в главное меню":
        context.user_data[STATE] = STATE_IDLE
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return True

    if text == "Прочитать сообщения":
        await update.message.reply_text(
            "Ваши сообщения:\n\nСписок из базы...",
            reply_markup=main_menu_keyboard(),
        )
        return True

    if text == "Показать тестовых адресатов":
        await update.message.reply_text(
            "Тестовые адресаты:\n\n" + format_recipients(HARD_RECIPIENTS),
            reply_markup=main_menu_keyboard(),
        )
        return True

    if text == "Написать сообщение":
        context.user_data[STATE] = STATE_WAIT_MESSAGE_TEXT
        context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
        context.user_data.pop(DRAFT_RECIPIENTS_SELECTED, None)
        context.user_data.pop(DRAFT_WHEN, None)
        await update.message.reply_text(
            "Введите текст сообщения одним сообщением.",
            reply_markup=flow_keyboard(),
        )
        return True

    if text == "Отправить всем тестовым адресатам":
        selected = [recipient_to_str(x) for x in HARD_RECIPIENTS]
        context.user_data[DRAFT_RECIPIENTS_SELECTED] = selected
        context.user_data[STATE] = STATE_WAIT_WHEN
        await update.message.reply_text(
            "Выбраны все тестовые адресаты.\nВведите, когда отправить сообщение.",
            reply_markup=flow_keyboard(),
        )
        return True

    if text == "Выбрать тестовых адресатов":
        context.user_data[STATE] = STATE_WAIT_RECIPIENT_PICK
        await update.message.reply_text(
            "Введите номера адресатов через запятую, например: 1,3,5\n\n"
            + format_recipients(HARD_RECIPIENTS),
            reply_markup=flow_keyboard(),
        )
        return True

    return False

async def handle_wait_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not text:
        await update.message.reply_text("Пустой текст. Введите сообщение ещё раз.")
        return

    context.user_data[DRAFT_MESSAGE_TEXT] = text
    context.user_data[STATE] = STATE_IDLE

    await update.message.reply_text(
        "Сообщение сохранено. Выберите адресатов.",
        reply_markup=draft_choice_keyboard(),
    )

async def handle_wait_recipient_pick(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    raw = [x.strip() for x in text.split(",")]
    if not raw or any(not token.isdigit() for token in raw):
        await update.message.reply_text("Введите номера через запятую, например: 1,2")
        return

    selected = []
    for token in raw:
        idx = int(token) - 1
        if idx < 0 or idx >= len(HARD_RECIPIENTS):
            await update.message.reply_text(f"Некорректный номер: {token}")
            return
        value = recipient_to_str(HARD_RECIPIENTS[idx])
        if value not in selected:
            selected.append(value)

    context.user_data[DRAFT_RECIPIENTS_SELECTED] = selected
    context.user_data[STATE] = STATE_WAIT_WHEN

    await update.message.reply_text(
        "Вы выбрали адресатов:\n"
        + selected_to_lines(selected)
        + "\n\nВведите, когда отправить сообщение.",
        reply_markup=flow_keyboard(),
    )

async def handle_wait_when(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not text:
        await update.message.reply_text("Укажите, когда отправить сообщение.")
        return

    context.user_data[DRAFT_WHEN] = text
    context.user_data[STATE] = STATE_IDLE

    message_text = context.user_data.get(DRAFT_MESSAGE_TEXT, "")
    recipients = context.user_data.get(DRAFT_RECIPIENTS_SELECTED, [])
    when_value = context.user_data.get(DRAFT_WHEN, "")

    await update.message.reply_text(
        "Черновик создан:\n\n"
        f"Сообщение:\n{message_text}\n\n"
        f"Адресаты:\n{selected_to_lines(recipients)}\n\n"
        f"Когда отправить:\n{when_value}",
        reply_markup=main_menu_keyboard(),
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    text = (update.message.text or "").strip()

    if text == "Назад в главное меню":
        context.user_data[STATE] = STATE_IDLE
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return

    if await handle_idle_command(update, context, text):
        return

    state = context.user_data.get(STATE, STATE_IDLE)

    if state == STATE_WAIT_MESSAGE_TEXT:
        await handle_wait_message_text(update, context, text)
        return

    if state == STATE_WAIT_RECIPIENT_PICK:
        await handle_wait_recipient_pick(update, context, text)
        return

    if state == STATE_WAIT_WHEN:
        await handle_wait_when(update, context, text)
        return

    await update.message.reply_text("Используйте кнопки меню.", reply_markup=main_menu_keyboard())

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