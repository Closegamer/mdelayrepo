import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    first_name = user.first_name or "<Ваше имя не распознано>"
    username = user.username or "<ник не распознан>"
    language_code = user.language_code or ""

    await update.message.reply_text(f"Здравствуйте, {first_name}! Вас приветствует бот mDelay!\n\n"
                                    f"Если Вы собираетесь в опасное путешествие или в подозрительное место, Вы можете оставить сообщение, которое поможет Вас найти в случае непредвиденной ситуации и при отсутствии у Вас связи. \n\n"
                                    f"Какое сообщение, кому и когда - решаете Вы. \n\n"
                                    f"Вы всегда сможете удалить свои сообщения, изменить даты отправки, изменить адресатов.\n\n"
                                    f"Удачи Вам! Не теряйтесь - кому-то может быть без Вас грустно.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("pong")

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
