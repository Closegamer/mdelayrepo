import os

from telegram.ext import Application


def main() -> None:
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
