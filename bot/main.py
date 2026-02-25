import os
import re
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
STATE_WAIT_ADD_USERNAME = "wait_add_username"
STATE_WAIT_ADD_FORWARD = "wait_add_forward"

DRAFT_MESSAGE_TEXT = "draft_message_text"
DRAFT_RECIPIENTS_SELECTED = "draft_recipients_selected"
DRAFT_WHEN = "draft_when"
RECIPIENTS_BOOK = "recipients_book"

USERNAME_RE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE) -> None:
    if STATE not in context.user_data:
        context.user_data[STATE] = STATE_IDLE
    if RECIPIENTS_BOOK not in context.user_data:
        context.user_data[RECIPIENTS_BOOK] = []

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Написать новое сообщение"],
            ["Показать список адресатов"],
            ["Добавить адресата"],
            ["Прочитать свои сообщения"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def add_recipient_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Добавить вручную по @username"],
            ["Добавить пересылкой сообщения"],
            ["Назад в главное меню"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def draft_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Выбрать адресатов"],
            ["Отправить всем адресатам"],
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
    tg = item.get("telegram") or "-"
    return f"{item['name']} (TG: {tg})"

def format_recipients(book: list[dict]) -> str:
    if not book:
        return "Список адресатов пуст"
    return "\n".join([f"{idx}. {recipient_to_str(item)}" for idx, item in enumerate(book, start=1)])

def selected_to_lines(values: list[str]) -> str:
    if not values:
        return "- (пусто)"
    return "\n".join([f"- {x}" for x in values])

def recipient_key(item: dict) -> str:
    tg = item.get("telegram", "")
    tg_id = item.get("telegram_id")
    if tg:
        return f"tg:{tg.lower()}"
    if tg_id:
        return f"id:{tg_id}"
    return ""

def add_dynamic_recipient(context: ContextTypes.DEFAULT_TYPE, item: dict) -> bool:
    dynamic_list = context.user_data.get(RECIPIENTS_BOOK, [])
    new_key = recipient_key(item)
    if not new_key:
        return False
    existing = {recipient_key(x) for x in dynamic_list if recipient_key(x)}
    if new_key in existing:
        return False
    dynamic_list.append(item)
    context.user_data[RECIPIENTS_BOOK] = dynamic_list
    return True

def recipients_list(context: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    return context.user_data.get(RECIPIENTS_BOOK, [])

def parse_forwarded_recipient(message) -> dict | None:
    forward_from = getattr(message, "forward_from", None)
    if forward_from:
        username = f"@{forward_from.username}" if forward_from.username else ""
        telegram_value = username if username else f"id:{forward_from.id}"
        name = (forward_from.full_name or "").strip() or (forward_from.first_name or "Пользователь")
        return {"name": name, "telegram": telegram_value, "telegram_id": forward_from.id}

    forward_origin = getattr(message, "forward_origin", None)
    if forward_origin:
        sender_user = getattr(forward_origin, "sender_user", None)
        if sender_user:
            username = f"@{sender_user.username}" if sender_user.username else ""
            telegram_value = username if username else f"id:{sender_user.id}"
            name = (sender_user.full_name or "").strip() or (sender_user.first_name or "Пользователь")
            return {"name": name, "telegram": telegram_value, "telegram_id": sender_user.id}

    return None

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
    if text == "Прочитать свои сообщения":
        await update.message.reply_text(
            "Ваши сообщения:\n\nСписок из базы...",
            reply_markup=main_menu_keyboard(),
        )
        return True
    if text == "Показать список адресатов":
        book = recipients_list(context)
        await update.message.reply_text(
            "Список адресатов:\n\n" + format_recipients(book),
            reply_markup=main_menu_keyboard(),
        )
        return True
    if text == "Добавить адресата":
        context.user_data[STATE] = STATE_IDLE
        await update.message.reply_text(
            "Выберите способ добавления адресата:",
            reply_markup=add_recipient_keyboard(),
        )
        return True
    if text == "Добавить вручную по @username":
        context.user_data[STATE] = STATE_WAIT_ADD_USERNAME
        await update.message.reply_text(
            "Введите username (начинается с символа @)",
            reply_markup=flow_keyboard(),
        )
        return True
    if text == "Добавить пересылкой сообщения":
        context.user_data[STATE] = STATE_WAIT_ADD_FORWARD
        await update.message.reply_text(
            "Перешлите одно сообщение от нужного пользователя боту, и он добавится в Ваш список адресатов.",
            reply_markup=flow_keyboard(),
        )
        return True
    if text == "Написать новое сообщение":
        context.user_data[STATE] = STATE_WAIT_MESSAGE_TEXT
        context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
        context.user_data.pop(DRAFT_RECIPIENTS_SELECTED, None)
        context.user_data.pop(DRAFT_WHEN, None)
        await update.message.reply_text(
            "Введите текст одним сообщением",
            reply_markup=flow_keyboard(),
        )
        return True
    if text == "Отправить всем адресатам":
        book = recipients_list(context)
        if not book:
            await update.message.reply_text("Список адресатов пуст", reply_markup=main_menu_keyboard())
            return True
        selected = [recipient_to_str(x) for x in book]
        context.user_data[DRAFT_RECIPIENTS_SELECTED] = selected
        context.user_data[STATE] = STATE_WAIT_WHEN
        await update.message.reply_text(
            "Выбраны все адресаты.\nВведите, когда отправить сообщение.",
            reply_markup=flow_keyboard(),
        )
        return True
    if text == "Выбрать адресатов":
        book = recipients_list(context)
        if not book:
            await update.message.reply_text("Список адресатов пуст.", reply_markup=main_menu_keyboard())
            return True
        await update.message.reply_text(
            "Введите номера адресатов через запятую, например: 1,3,5\n\n" + format_recipients(book),
            reply_markup=flow_keyboard(),
        )
        context.user_data[STATE] = STATE_WAIT_RECIPIENT_PICK
        return True
    return False

async def handle_wait_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    value = text.strip()
    if not USERNAME_RE.match(value):
        await update.message.reply_text("Некорректный username. Пример: @example_user")
        return
    item = {"name": value, "telegram": value, "telegram_id": None}
    ok = add_dynamic_recipient(context, item)
    context.user_data[STATE] = STATE_IDLE
    if not ok:
        await update.message.reply_text("Такой username уже есть в списке.", reply_markup=add_recipient_keyboard())
        return
    await update.message.reply_text(f"Адресат добавлен: {value}", reply_markup=add_recipient_keyboard())

async def handle_wait_add_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    item = parse_forwarded_recipient(update.message)
    if not item:
        await update.message.reply_text("Не удалось определить адресата. Перешлите сообщение от пользователя.")
        return
    ok = add_dynamic_recipient(context, item)
    context.user_data[STATE] = STATE_IDLE
    if not ok:
        await update.message.reply_text("Такой адресат уже есть в списке.", reply_markup=add_recipient_keyboard())
        return
    await update.message.reply_text(
        f"Адресат добавлен: {recipient_to_str(item)}",
        reply_markup=add_recipient_keyboard(),
    )

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
    book = recipients_list(context)
    selected = []
    for token in raw:
        idx = int(token) - 1
        if idx < 0 or idx >= len(book):
            await update.message.reply_text(f"Некорректный номер: {token}")
            return
        value = recipient_to_str(book[idx])
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
    if state == STATE_WAIT_ADD_USERNAME:
        await handle_wait_add_username(update, context, text)
        return
    if state == STATE_WAIT_ADD_FORWARD:
        await handle_wait_add_forward(update, context)
        return
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