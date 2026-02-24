# mdelayrepo

Базовый каркас проекта:

- Postgres в Docker (`mdelayrepo`)
- Python-контейнер с Telegram-ботом
- Бот пустой (без хендлеров/команд)

## Запуск

```bash
docker compose up --build
```

Контейнер базы поднимается с параметрами из `.env`.
