import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID")
ESCALATED_TEXT = "ESCALATED"
try:
    APP_TZ = ZoneInfo(BOT_TIMEZONE)
except Exception:
    APP_TZ = timezone.utc
    logger.warning("Invalid BOT_TIMEZONE '%s', fallback to UTC", BOT_TIMEZONE)

STATE = "state"
STATE_IDLE = "idle"
STATE_WAIT_MESSAGE_TEXT = "wait_message_text"


def ensure_defaults(context: ContextTypes.DEFAULT_TYPE) -> None:
    if STATE not in context.user_data:
        context.user_data[STATE] = STATE_IDLE

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

def start_text(first_name: str) -> str:
    return (
        f"ВНИМАНИЕ! БОТ РАБОТАЕТ В ТЕСТОВОМ РЕЖИМЕ! ЗАПРОСЫ ПРИХОДЯТ 1 РАЗ В МИНУТУ!\n\n"
        f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
        f"Если Вы собираетесь в опасное путешествие или в подозрительное место, "
        f"Вы можете оставить сообщение, которое поможет Вас найти в случае непредвиденной ситуации "
        f"и при отсутствии у Вас связи.\n\n"
        f"Через определенное время бот спросит, как у Вас дела.\n\n"
        f"В первый раз бот спросит Вас через 5 часов, во второй раз - еще через 2 часа, в третий раз - еще через 1 час.\n\n"
        f"Если Вы ответите на любой из запросов фразой \"Я в порядке\", бот прекратит следить за данным сообщением.\n\n"
        f"Если Вы ответите что-то другое, бот сразу передаст сообщение службе спасения.\n\n"
        f"Если Вы не ответите на все три запроса, бот передаст исходное сообщение службе спасения.\n\n "
        f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно!\n\n"
        f"ВНИМАНИЕ! БОТ РАБОТАЕТ В ТЕСТОВОМ РЕЖИМЕ! ЗАПРОСЫ ПРИХОДЯТ 1 РАЗ В МИНУТУ!"
    )

def db_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

def format_dt_local(value: datetime | None) -> str:
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TZ).strftime("%d.%m.%Y %H:%M:%S")

def ensure_messages_table() -> None:
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_messages_table.sql"
    create_sql = sql_path.read_text(encoding="utf-8")
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS check1_is_text BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS check2_is_text BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS check3_is_text BOOLEAN NOT NULL DEFAULT FALSE")
        conn.commit()

def save_message_to_db(user, text: str, sent_at: datetime) -> None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (
                    userid, username, firstname, lastname, message, timecreated
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user.id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    text,
                    sent_at,
                ),
            )
        conn.commit()

def fetch_user_messages_from_db(user_id: int, limit: int = 20) -> list[dict]:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, message, timecreated, username, firstname, lastname
                FROM messages
                WHERE userid = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
    result = []
    for message_id, message, timecreated, username, firstname, lastname in rows:
        sender_name = " ".join(x for x in [firstname, lastname] if x) or "Пользователь"
        sender_username = f"@{username}" if username else "-"
        result.append(
            {
                "id": message_id,
                "text": message,
                "sender": f"{sender_name} (username: {sender_username}, id: {user_id})",
                "sent_at": format_dt_local(timecreated),
            }
        )
    return result

def delete_message_from_db(user_id: int, message_id: int) -> bool:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM messages WHERE id = %s AND userid = %s",
                (message_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted

def update_check_response(message_id: int, response_text: str, is_text: bool) -> bool:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE messages
                SET
                    check1_res = CASE WHEN check1_res = 'SENT' THEN %s ELSE check1_res END,
                    check1_is_text = CASE WHEN check1_res = 'SENT' THEN %s ELSE check1_is_text END,
                    check2_res = CASE WHEN check2_res = 'SENT' THEN %s ELSE check2_res END,
                    check2_is_text = CASE WHEN check2_res = 'SENT' THEN %s ELSE check2_is_text END,
                    check3_res = CASE WHEN check3_res = 'SENT' THEN %s ELSE check3_res END,
                    check3_is_text = CASE WHEN check3_res = 'SENT' THEN %s ELSE check3_is_text END
                WHERE id = %s
                """,
                (response_text, is_text, response_text, is_text, response_text, is_text, message_id),
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated

def mark_message_escalated(message_id: int) -> None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE messages
                SET check3_res = %s, check3_is_text = FALSE
                WHERE id = %s
                """,
                (ESCALATED_TEXT, message_id),
            )
        conn.commit()

async def send_emergency_now(context: ContextTypes.DEFAULT_TYPE, user, recorded: dict) -> None:
    if not ALERT_CHAT_ID:
        raise RuntimeError("ALERT_CHAT_ID is not set")
    username_text = f"@{user.username}" if user and user.username else "-"
    full_name = " ".join(x for x in [(user.first_name if user else ""), (user.last_name if user else "")] if x) or "Пользователь"
    created_text = format_dt_local(recorded.get("timecreated"))
    alert_text = (
        "АВАРИЙНОЕ СООБЩЕНИЕ\n\n"
        f"id сообщения: {recorded.get('id')}\n"
        f"user id: {user.id if user else '-'}\n"
        f"username: {username_text}\n"
        f"имя: {full_name}\n\n"
        f"Время создания сообщения: {created_text}\n\n"
        f"Текст сообщения:\n{recorded.get('message', '')}\n\n"
        f"Ответ пользователя:\n{recorded.get('response_text', '')}"
    )
    await context.bot.send_message(chat_id=ALERT_CHAT_ID, text=alert_text)

def mark_latest_pending_as_ok(user_id: int) -> dict | None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, message, timecreated
                FROM messages
                WHERE userid = %s
                  AND check1_time IS NOT NULL
                  AND check3_res IS DISTINCT FROM 'Я в порядке'
                  AND (
                        check1_res = 'SENT'
                        OR check2_res = 'SENT'
                        OR check3_res = 'SENT'
                  )
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        message_id, message_text, timecreated = row
    changed = update_check_response(message_id, "Я в порядке", True)
    if not changed:
        return None
    return {
        "id": message_id,
        "message": message_text,
        "timecreated": timecreated,
    }

def mark_latest_pending_with_text(user_id: int, response_text: str) -> dict | None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, message, timecreated
                FROM messages
                WHERE userid = %s
                  AND check1_time IS NOT NULL
                  AND (
                        check1_res = 'SENT'
                        OR check2_res = 'SENT'
                        OR check3_res = 'SENT'
                  )
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        message_id, message_text, timecreated = row
    changed = update_check_response(message_id, response_text, True)
    if not changed:
        return None
    return {
        "id": message_id,
        "message": message_text,
        "timecreated": timecreated,
        "response_text": response_text,
    }

def format_message_item(idx: int, item: dict) -> str:
    return (
        f"{idx}. Текст: {item['text']}\n"
        f"Время отправки: {item['sent_at']}"
    )

def delete_keyboard(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Удалить", callback_data=f"msg_delete:{message_id}")]]
    )

def confirm_delete_keyboard(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Подтвердить", callback_data=f"msg_delete_confirm:{message_id}"),
            InlineKeyboardButton("Отмена", callback_data=f"msg_delete_cancel:{message_id}"),
        ]]
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
        user = update.effective_user
        if not user:
            await update.message.reply_text("Не удалось определить пользователя.", reply_markup=main_menu_keyboard())
            return True
        try:
            items = fetch_user_messages_from_db(user.id)
            if not items:
                await update.message.reply_text("У вас пока нет сохраненных сообщений.", reply_markup=main_menu_keyboard())
                return True
            await update.message.reply_text(
                f"Ваши сообщения ({len(items)}):",
                reply_markup=main_menu_keyboard(),
            )
            for idx, item in enumerate(items, start=1):
                await update.message.reply_text(
                    format_message_item(idx, item),
                    reply_markup=delete_keyboard(item["id"]),
                )
        except Exception:
            logger.exception("Failed to read messages from database")
            await update.message.reply_text("Не удалось прочитать сообщения из базы.", reply_markup=main_menu_keyboard())
        return True
    return False

async def handle_wait_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    value = text.strip()
    if not value:
        await update.message.reply_text("Пустой текст. Введите сообщение еще раз.")
        return

    user = update.effective_user
    if not user:
        await update.message.reply_text("Не удалось определить пользователя.", reply_markup=main_menu_keyboard())
        context.user_data[STATE] = STATE_IDLE
        return

    message_date = update.message.date if update.message else None
    sent_at = message_date or datetime.now(timezone.utc)
    sender = sender_to_str(user)

    try:
        save_message_to_db(user=user, text=value, sent_at=sent_at)
    except Exception:
        logger.exception("Failed to write message to database")
        await update.message.reply_text("Не удалось сохранить сообщение в базу.", reply_markup=main_menu_keyboard())
        context.user_data[STATE] = STATE_IDLE
        return

    context.user_data[STATE] = STATE_IDLE
    await update.message.reply_text(
        "Сообщение сохранено.\n\n"
        f"Текст: {value}\n"
        f"Отправитель: {sender}\n"
        f"Время отправки: {format_dt_local(sent_at)}",
        reply_markup=main_menu_keyboard(),
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_defaults(context)
    text = (update.message.text or "").strip()
    state = context.user_data.get(STATE, STATE_IDLE)

    if state == STATE_IDLE and text not in ("Я в порядке", "Написать новое сообщение", "Прочитать свои сообщения", "Назад в главное меню"):
        user = update.effective_user
        if user:
            try:
                recorded = mark_latest_pending_with_text(user.id, text)
                if recorded:
                    created_text = format_dt_local(recorded["timecreated"])
                    try:
                        await send_emergency_now(context, user, recorded)
                        mark_message_escalated(recorded["id"])
                        await update.message.reply_text(
                            "Ответ на проверку сохранен.\n"
                            "Ответ отличается от \"Я в порядке\", аварийное сообщение отправлено сразу.\n\n"
                            f"id сообщения: {recorded['id']}\n"
                            f"Время создания: {created_text}\n"
                            f"Ваш ответ: {recorded['response_text']}",
                            reply_markup=main_menu_keyboard(),
                        )
                    except Exception:
                        logger.exception("Failed to send immediate emergency alert")
                        await update.message.reply_text(
                            "Ответ на проверку сохранен, но аварийное сообщение пока не отправилось.",
                            reply_markup=main_menu_keyboard(),
                        )
                    return
            except Exception:
                logger.exception("Failed to save custom check response")

    if text == "Я в порядке" or text == "Я в порядке.":
        user = update.effective_user
        if not user:
            await update.message.reply_text("Не удалось определить пользователя.", reply_markup=main_menu_keyboard())
            return
        try:
            stopped = mark_latest_pending_as_ok(user.id)
            if stopped:
                created_text = format_dt_local(stopped["timecreated"])
                await update.message.reply_text(
                    "Принято. Вы в порядке.\n"
                    "Бот прекращает следить за этим сообщением.\n\n"
                    f"id сообщения: {stopped['id']}\n"
                    f"Время создания: {created_text}\n"
                    "Сообщение остается в базе.",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                await update.message.reply_text("Нет активной проверки для подтверждения.", reply_markup=main_menu_keyboard())
        except Exception:
            logger.exception("Failed to mark check response from text")
            await update.message.reply_text("Не удалось обработать ответ.", reply_markup=main_menu_keyboard())
        return
    if await handle_idle_command(update, context, text):
        return
    if state == STATE_WAIT_MESSAGE_TEXT:
        await handle_wait_message_text(update, context, text)
        return
    await update.message.reply_text("Используйте кнопки меню.", reply_markup=main_menu_keyboard())

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    logger.info("Callback received: %s", data)
    if data.startswith("msg_delete:"):
        try:
            message_id = int(data.split(":", 1)[1])
        except Exception:
            await query.answer("Некорректный идентификатор сообщения.", show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=confirm_delete_keyboard(message_id))
        return

    if data.startswith("msg_delete_cancel:"):
        try:
            message_id = int(data.split(":", 1)[1])
        except Exception:
            await query.answer("Некорректный идентификатор сообщения.", show_alert=True)
            return
        await query.answer("Удаление отменено.")
        await query.edit_message_reply_markup(reply_markup=delete_keyboard(message_id))
        return

    if not data.startswith("msg_delete_confirm:"):
        await query.answer()
        return
    user = query.from_user
    if not user:
        await query.answer("Не удалось определить пользователя.", show_alert=True)
        return
    try:
        message_id = int(data.split(":", 1)[1])
    except Exception:
        await query.answer("Некорректный идентификатор сообщения.", show_alert=True)
        return
    try:
        deleted = delete_message_from_db(user.id, message_id)
        if not deleted:
            await query.answer("Сообщение не найдено или уже удалено.", show_alert=True)
            return
        await query.answer("Сообщение удалено.")
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text("Сообщение удалено.")
    except Exception:
        logger.exception("Failed to delete message from database")
        await query.answer("Не удалось удалить сообщение.", show_alert=True)

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    ensure_messages_table()
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
