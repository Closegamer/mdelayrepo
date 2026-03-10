import logging
import os
import time
from datetime import timezone
from zoneinfo import ZoneInfo

import httpx
import psycopg

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# CHECK1_HOURS = 5
# CHECK2_HOURS = 2
# CHECK3_HOURS = 1
CHECK1_MINUTES = 1
CHECK2_MINUTES = 1
CHECK3_MINUTES = 1
POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "60"))
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", "@Closegamer")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
try:
    APP_TZ = ZoneInfo(BOT_TIMEZONE)
except Exception:
    APP_TZ = timezone.utc
    logger.warning("Invalid BOT_TIMEZONE '%s', fallback to UTC", BOT_TIMEZONE)
OK_TEXT = "Я в порядке"
SENT_TEXT = "SENT"
ESCALATED_TEXT = "ESCALATED"

def db_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

def format_dt_local(value) -> str:
    if not value:
        return "-"
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TZ).strftime("%d.%m.%Y %H:%M:%S")

def send_telegram_message(chat_id, text: str) -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    response = httpx.post(url, data=payload, timeout=20.0)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")

def send_check(row: tuple, check_no: int) -> bool:
    message_id, user_id, username, firstname, lastname, message_text = row
    text = (
        f"Проверка {check_no}/3.\n"
        f"Как дела?\n\n"
        f"Если всё хорошо, напишите фразу \"Я в порядке\"\n\n"
        f"Ваше сообщение:\n{message_text}"
    )
    try:
        send_telegram_message(chat_id=user_id, text=text)
        return True
    except Exception:
        logger.exception("Failed to send check %s for message_id=%s", check_no, message_id)
        return False

def send_emergency(row: tuple) -> bool:
    message_id, user_id, username, firstname, lastname, message_text, timecreated = row
    user_title = " ".join(x for x in [firstname, lastname] if x) or "Пользователь"
    username_text = f"@{username}" if username else "-"
    created_text = format_dt_local(timecreated)
    alert_text = (
        "АВАРИЙНОЕ СООБЩЕНИЕ\n\n"
        f"id сообщения: {message_id}\n"
        f"user id: {user_id}\n"
        f"username: {username_text}\n"
        f"имя: {user_title}\n\n"
        f"Время создания сообщения: {created_text}\n\n"
        f"Текст сообщения:\n{message_text}"
    )
    try:
        send_telegram_message(chat_id=ALERT_CHAT_ID, text=alert_text)
        return True
    except Exception:
        logger.exception("Failed to send emergency for message_id=%s", message_id)
        return False

def fetch_due_check1(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, userid, username, firstname, lastname, message
            FROM messages
            WHERE check1_time IS NULL
              AND timecreated <= NOW() - INTERVAL '{CHECK1_MINUTES} minute'
              AND COALESCE(check1_res, '') <> %s
              AND COALESCE(check2_res, '') <> %s
              AND COALESCE(check3_res, '') <> %s
            ORDER BY id
            """,
            (OK_TEXT, OK_TEXT, OK_TEXT),
        )
        return cur.fetchall()

def fetch_due_check2(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, userid, username, firstname, lastname, message
            FROM messages
            WHERE check1_time IS NOT NULL
              AND check2_time IS NULL
              AND check1_time <= NOW() - INTERVAL '{CHECK2_MINUTES} minute'
              AND check1_res = %s
              AND COALESCE(check2_res, '') <> %s
              AND COALESCE(check3_res, '') <> %s
            ORDER BY id
            """,
            (SENT_TEXT, OK_TEXT, OK_TEXT),
        )
        return cur.fetchall()

def fetch_due_check3(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, userid, username, firstname, lastname, message
            FROM messages
            WHERE check2_time IS NOT NULL
              AND check3_time IS NULL
              AND check2_time <= NOW() - INTERVAL '{CHECK3_MINUTES} minute'
              AND check2_res = %s
              AND COALESCE(check1_res, '') <> %s
              AND COALESCE(check2_res, '') <> %s
              AND COALESCE(check3_res, '') <> %s
            ORDER BY id
            """,
            (SENT_TEXT, OK_TEXT, OK_TEXT, OK_TEXT),
        )
        return cur.fetchall()

def fetch_due_emergency_immediate(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, userid, username, firstname, lastname, message, timecreated
            FROM messages
            WHERE check3_res IS DISTINCT FROM %s
              AND (
                    (check1_res IS NOT NULL AND check1_res NOT IN (%s, %s))
                    OR (check2_res IS NOT NULL AND check2_res NOT IN (%s, %s))
                    OR (check3_res IS NOT NULL AND check3_res NOT IN (%s, %s))
                  )
            ORDER BY id
            """,
            (ESCALATED_TEXT, SENT_TEXT, OK_TEXT, SENT_TEXT, OK_TEXT, SENT_TEXT, OK_TEXT),
        )
        return cur.fetchall()

def fetch_due_emergency(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, userid, username, firstname, lastname, message, timecreated
            FROM messages
            WHERE check3_time IS NOT NULL
              AND check3_time <= NOW() - INTERVAL '{CHECK3_MINUTES} minute'
              AND check3_res = %s
              AND COALESCE(check1_res, '') <> %s
              AND COALESCE(check2_res, '') <> %s
              AND COALESCE(check3_res, '') <> %s
            ORDER BY id
            """,
            (SENT_TEXT, OK_TEXT, OK_TEXT, OK_TEXT),
        )
        return cur.fetchall()

def mark_check_sent(conn: psycopg.Connection, message_id: int, check_no: int) -> None:
    col_time = f"check{check_no}_time"
    col_res = f"check{check_no}_res"
    col_is_text = f"check{check_no}_is_text"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE messages
            SET {col_time} = NOW(), {col_res} = %s, {col_is_text} = FALSE
            WHERE id = %s
            """,
            (SENT_TEXT, message_id),
        )

def mark_emergency_sent(conn: psycopg.Connection, message_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE messages
            SET check3_res = %s
            WHERE id = %s
            """,
            (ESCALATED_TEXT, message_id),
        )

def run_once() -> None:
    with db_connect() as conn:
        due_emergency_immediate = fetch_due_emergency_immediate(conn)
        for row in due_emergency_immediate:
            if send_emergency(row):
                mark_emergency_sent(conn, row[0])

        due1 = fetch_due_check1(conn)
        for row in due1:
            if send_check(row, 1):
                mark_check_sent(conn, row[0], 1)

        due2 = fetch_due_check2(conn)
        for row in due2:
            if send_check(row, 2):
                mark_check_sent(conn, row[0], 2)

        due3 = fetch_due_check3(conn)
        for row in due3:
            if send_check(row, 3):
                mark_check_sent(conn, row[0], 3)

        due_emergency = fetch_due_emergency(conn)
        for row in due_emergency:
            if send_emergency(row):
                mark_emergency_sent(conn, row[0])

        conn.commit()

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    logger.info("Scheduler started with poll interval %ss", POLL_SECONDS)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Scheduler iteration failed")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
