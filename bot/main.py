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

STATE = "state"
RECIPIENTS_LIST = "recipients_list"
DRAFT_MESSAGE_TEXT = "draft_message_text"
DRAFT_RECIPIENTS_SELECTED = "draft_recipients_selected"
DRAFT_WHEN = "draft_when"

IDLE = "idle"
WAIT_MESSAGE_TEXT = "wait_message_text"
WAIT_RECIPIENT_ADD = "wait_recipient_add"
WAIT_RECIPIENT_DELETE = "wait_recipient_delete"
WAIT_RECIPIENTS_MANUAL = "wait_recipients_manual"
WAIT_WHEN = "wait_when"

def split_recipients(raw: str) -> list[str]:
    items = [x.strip() for x in raw.split(",")]
    return [x for x in items if x]

def ensure_defaults(context: ContextTypes.DEFAULT_TYPE) -> None:
    if STATE not in context.user_data:
        context.user_data[STATE] = IDLE
    if RECIPIENTS_LIST not in context.user_data:
        context.user_data[RECIPIENTS_LIST] = []

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Написать сообщение"],
            ["Управление адресатами"],
            ["Прочитать сообщения"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def draft_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Когда отправить"], ["Кому отправить"], ["В главное меню"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def recipients_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Показать список адресатов"],
            ["Добавить адресата"],
            ["Удалить адресата"],
            ["Назад в главное меню"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def recipients_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Отправить по моему списку"],
            ["Выбрать адресатов вручную"],
            ["Назад в главное меню"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def flow_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Назад в главное меню"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"

    context.user_data[STATE] = IDLE
    context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
    context.user_data.pop(DRAFT_RECIPIENTS_SELECTED, None)
    context.user_data.pop(DRAFT_WHEN, None)

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

async def show_recipients_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    recipients = context.user_data.get(RECIPIENTS_LIST, [])
    if not recipients:
        await update.message.reply_text(
            "Список адресатов пуст.",
            reply_markup=recipients_menu_keyboard(),
        )
        return

    lines = "\n".join([f"{i + 1}. {value}" for i, value in enumerate(recipients)])
    await update.message.reply_text(
        f"Ваши адресаты:\n\n{lines}",
        reply_markup=recipients_menu_keyboard(),
    )

async def handle_idle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "Назад в главное меню":
        context.user_data[STATE] = IDLE
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return True

    if text == "Прочитать сообщения":
        await update.message.reply_text(
            "Здесь позже будет список ваших сообщений из базы.",
            reply_markup=main_menu_keyboard(),
        )
        return True

    if text == "Управление адресатами":
        context.user_data[STATE] = IDLE
        await update.message.reply_text(
            "Меню адресатов:",
            reply_markup=recipients_menu_keyboard(),
        )
        return True

    if text == "Показать список адресатов":
        await show_recipients_list(update, context)
        return True

    if text == "Добавить адресата":
        context.user_data[STATE] = WAIT_RECIPIENT_ADD
        await update.message.reply_text(
            "Введите адресата (@username или номер).\n"
            "Можно несколько через запятую.",
            reply_markup=flow_menu_keyboard(),
        )
        return True

    if text == "Удалить адресата":
        recipients = context.user_data.get(RECIPIENTS_LIST, [])
        if not recipients:
            await update.message.reply_text(
                "Список адресатов пуст.",
                reply_markup=recipients_menu_keyboard(),
            )
            return True

        lines = "\n".join([f"{i + 1}. {value}" for i, value in enumerate(recipients)])
        context.user_data[STATE] = WAIT_RECIPIENT_DELETE
        await update.message.reply_text(
            f"Кого удалить?\n\n{lines}\n\n"
            "Введите номер из списка или точное значение адресата.",
            reply_markup=flow_menu_keyboard(),
        )
        return True

    if text == "Написать сообщение":
        context.user_data[STATE] = WAIT_MESSAGE_TEXT
        context.user_data.pop(DRAFT_MESSAGE_TEXT, None)
        context.user_data.pop(DRAFT_RECIPIENTS_SELECTED, None)
        context.user_data.pop(DRAFT_WHEN, None)
        await update.message.reply_text(
            "Введите текст сообщения одним сообщением.",
            reply_markup=flow_menu_keyboard(),
        )
        return True

    if text == "Отправить по моему списку":
        recipients = context.user_data.get(RECIPIENTS_LIST, [])
        if not recipients:
            await update.message.reply_text(
                "Список адресатов пуст. Добавьте адресатов или выберите ввод вручную.",
                reply_markup=recipients_choice_keyboard(),
            )
            return True

        context.user_data[DRAFT_RECIPIENTS_SELECTED] = recipients[:]
        context.user_data[STATE] = WAIT_WHEN
        await update.message.reply_text(
            "Адресаты выбраны из вашего списка.\nВведите, когда отправить сообщение.",
            reply_markup=flow_menu_keyboard(),
        )
        return True

    if text == "Выбрать адресатов вручную":
        context.user_data[STATE] = WAIT_RECIPIENTS_MANUAL
        await update.message.reply_text(
            "Введите адресатов через запятую (например: @username1, @username2, ...).",
            reply_markup=flow_menu_keyboard(),
        )
        return True

    return False

async def handle_wait_recipient_add(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    values = split_recipients(text)
    if not values:
        await update.message.reply_text("Пустой ввод. Введите хотя бы одного адресата.")
        return

    current = context.user_data.get(RECIPIENTS_LIST, [])
    for v in values:
        if v not in current:
            current.append(v)
    context.user_data[RECIPIENTS_LIST] = current
    context.user_data[STATE] = IDLE

    lines = "\n".join([f"{i + 1}. {value}" for i, value in enumerate(current)])
    await update.message.reply_text(
        f"Адресаты сохранены.\n\nТекущий список:\n{lines}",
        reply_markup=recipients_menu_keyboard(),
    )

async def handle_wait_recipient_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    current = context.user_data.get(RECIPIENTS_LIST, [])
    if not current:
        context.user_data[STATE] = IDLE
        await update.message.reply_text("Список уже пуст.", reply_markup=recipients_menu_keyboard())
        return

    removed = None
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(current):
            removed = current.pop(idx)
    else:
        if text in current:
            current.remove(text)
            removed = text

    if removed is None:
        await update.message.reply_text("Не найдено. Введите корректный номер или точное значение.")
        return

    context.user_data[RECIPIENTS_LIST] = current
    context.user_data[STATE] = IDLE

    if not current:
        await update.message.reply_text(
            f"Удалено: {removed}\nСписок адресатов теперь пуст.",
            reply_markup=recipients_menu_keyboard(),
        )
        return

    lines = "\n".join([f"{i + 1}. {value}" for i, value in enumerate(current)])
    await update.message.reply_text(
        f"Удалено: {removed}\n\nТекущий список:\n{lines}",
        reply_markup=recipients_menu_keyboard(),
    )

async def handle_wait_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not text:
        await update.message.reply_text("Пустой текст. Введите сообщение ещё раз.")
        return

    context.user_data[DRAFT_MESSAGE_TEXT] = text
    context.user_data[STATE] = IDLE

    await update.message.reply_text(
        "Сообщение сохранено.\nВыберите, как задать адресатов.",
        reply_markup=recipients_choice_keyboard(),
    )

async def handle_wait_recipients_manual(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    recipients = split_recipients(text)
    if not recipients:
        await update.message.reply_text("Пустой ввод. Введите хотя бы одного адресата.")
        return

    context.user_data[DRAFT_RECIPIENTS_SELECTED] = recipients
    context.user_data[STATE] = WAIT_WHEN

    lines = "\n".join([f"- {x}" for x in recipients])
    await update.message.reply_text(
        f"Адресаты выбраны:\n{lines}\n\nВведите, когда отправить сообщение.",
        reply_markup=flow_menu_keyboard(),
    )

async def handle_wait_when(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not text:
        await update.message.reply_text("Пустой ввод. Укажите время отправки.")
        return

    context.user_data[DRAFT_WHEN] = text
    context.user_data[STATE] = IDLE

    message_text = context.user_data.get(DRAFT_MESSAGE_TEXT, "")
    recipients = context.user_data.get(DRAFT_RECIPIENTS_SELECTED, [])
    when_value = context.user_data.get(DRAFT_WHEN, "")

    recipients_lines = "\n".join([f"- {x}" for x in recipients]) if recipients else "- (пусто)"

    await update.message.reply_text(
        "Черновик создан:\n\n"
        f"Сообщение:\n{message_text}\n\n"
        f"Адресаты:\n{recipients_lines}\n\n"
        f"Когда отправить:\n{when_value}",
        reply_markup=main_menu_keyboard(),
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    text = (update.message.text or "").strip()

    if text == "Назад в главное меню":
        context.user_data[STATE] = IDLE
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
        return

    if await handle_idle_commands(update, context, text):
        return

    state = context.user_data.get(STATE, IDLE)

    if state == WAIT_RECIPIENT_ADD:
        await handle_wait_recipient_add(update, context, text)
        return

    if state == WAIT_RECIPIENT_DELETE:
        await handle_wait_recipient_delete(update, context, text)
        return

    if state == WAIT_MESSAGE_TEXT:
        await handle_wait_message_text(update, context, text)
        return

    if state == WAIT_RECIPIENTS_MANUAL:
        await handle_wait_recipients_manual(update, context, text)
        return

    if state == WAIT_WHEN:
        await handle_wait_when(update, context, text)
        return

    await update.message.reply_text(
        "Используйте кнопки меню.",
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