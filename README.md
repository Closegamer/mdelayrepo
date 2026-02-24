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

## CI/CD (GitHub Actions)

При пуше в `main` запускается workflow:

- CI: установка зависимостей, `compileall`, сборка Docker-образа
- CD: SSH на сервер, `git pull` (через `fetch/reset`), обновление `.env`, `docker compose up -d --build`

Нужно создать secrets в GitHub (`Settings -> Secrets and variables -> Actions`):

- `DEPLOY_HOST` — IP/домен сервера
- `DEPLOY_PORT` — SSH порт (обычно `22`)
- `DEPLOY_USER` — пользователь деплоя (например `deploy`)
- `DEPLOY_SSH_KEY` — приватный SSH ключ (содержимое файла ключа)
- `DEPLOY_APP_DIR` — путь на сервере, например `/home/deploy/apps/mdelayrepo`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `BOT_TOKEN`
