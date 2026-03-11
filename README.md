# mDelay Bot

mDelayBot - (message delay bot) Telegram-бот для сценария "отложенной тревоги": пользователь оставляет сообщение перед поездкой/выходом, mDelayBot делает 3 проверки состояния и, если пользователь не подтвердил "Я в порядке", отправляет аварийное сообщение в службу спасения.

## Что делает проект

- Принимает и сохраняет пользовательские сообщения в PostgreSQL.
- По расписанию отправляет 3 проверки состояния пользователя.
- При ответе "Я в порядке" завершает наблюдение.
- При любом другом текстовом ответе немедленно отправляет тревогу.
- При полном отсутствии ответа после 3-й проверки тоже отправляет тревогу.

## Стек технологий

- Python 3.12
- `python-telegram-bot` (polling-бот)
- `psycopg[binary]` (работа с PostgreSQL)
- `httpx` (прямые запросы к Telegram Bot API из scheduler)
- PostgreSQL 16 (в Docker)
- Docker + Docker Compose
- GitHub Actions (CI/CD)

## Архитектура сервисов

В `docker-compose.yml` поднимаются 3 сервиса:

- `db` - PostgreSQL (хранение сообщений и статусов проверок)
- mDelayBot - Telegram-бот (сервис `bot`, команда `python -m bot.main`)
- `scheduler` - фоновый обработчик таймеров (`python -m scheduler.main`)

mDelayBot и `scheduler` используют одну и ту же таблицу `messages`.

## Структура данных

Таблица `messages` создается из `sql/create_messages_table.sql` и содержит:

- исходное сообщение пользователя (`message`, `timecreated`, user fields)
- время отправки 1/2/3 проверок (`check1_time`, `check2_time`, `check3_time`)
- результат каждой проверки (`check1_res`, `check2_res`, `check3_res`)
- признак, что ответ был произвольным текстом (`check*_is_text`)

Служебные значения в `check*_res`:

- `SENT` - проверка отправлена, ответ еще не получен
- `Я в порядке` - пользователь подтвердил, тревога не нужна
- `ESCALATED` - тревога уже отправлена в службу спасения

## Последовательность работы бота

1. Пользователь отправляет `/start` и видит главное меню.
2. Нажимает "Написать новое сообщение".
3. Отправляет текст одним сообщением.
4. mDelayBot сохраняет запись в `messages`.
5. `scheduler` циклически проверяет БД:
   - отправляет проверку 1,
   - затем проверку 2,
   - затем проверку 3 (после заданных интервалов).
6. Если пользователь отвечает "Я в порядке":
   - mDelayBot записывает этот ответ в последнюю активную проверку,
   - наблюдение по этой записи завершается.
7. Если пользователь отвечает любым другим текстом:
   - mDelayBot сохраняет текст как ответ на активную проверку,
   - немедленно отправляет аварийное сообщение в `ALERT_CHAT_ID`,
   - помечает запись как `ESCALATED`.
8. Если пользователь не отвечает до конца 3-й проверки:
   - `scheduler` отправляет аварийное сообщение в `ALERT_CHAT_ID`,
   - помечает запись как `ESCALATED`.
9. Пользователь может открыть "Прочитать свои сообщения" и удалить запись кнопками под сообщением.

## Переменные окружения

Минимальный набор для запуска:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST` (по умолчанию `db` внутри compose)
- `POSTGRES_PORT` (по умолчанию `5432`)
- `BOT_TOKEN`
- `ALERT_CHAT_ID` (ID Telegram-чата службы спасения для тревог)
- `BOT_TIMEZONE` (например `Europe/Moscow`)
- `SCHEDULER_POLL_SECONDS` (по умолчанию `60`)

## Локальный запуск

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
docker compose logs -f scheduler
```

Остановка:

```bash
docker compose down
```

Остановка с удалением тома БД:

```bash
docker compose down -v
```

## Развертывание на удаленном сервере

Ниже - базовый ручной сценарий для Linux-сервера с Docker.

### 1) Подготовка сервера (один раз)

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

### 2) Клонирование проекта

```bash
mkdir -p ~/apps
cd ~/apps
git clone <repo_url> mdelayrepo
cd mdelayrepo
```

### 3) Создание `.env` на сервере

```bash
cp .env.example .env 2>/dev/null || true
nano .env
```

### 4) Поднятие сервисов

```bash
docker compose up -d --build
docker compose ps
```

### 5) Проверить логи

```bash
docker compose logs -f db
docker compose logs -f bot
docker compose logs -f scheduler
```

### 6) Обновление версии на сервере

```bash
cd ~/apps/mdelayrepo
git pull
docker compose up -d --build
```

### 7) Резервное копирование БД (по необходимости)

```bash
docker exec -t mdelayrepo-postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

## CI/CD (GitHub Actions)

При пуше в `main` запускается workflow:

- CI: установка зависимостей, `compileall`, сборка Docker-образа
- CD: SSH на сервер, обновление кода и `docker compose up -d --build`

Необходимые GitHub Secrets:

- `DEPLOY_HOST` - IP/домен сервера
- `DEPLOY_PORT` - SSH порт
- `DEPLOY_USER` - пользователь деплоя
- `DEPLOY_SSH_KEY` - приватный SSH-ключ
- `DEPLOY_APP_DIR` - путь к проекту на сервере
- `GH_REPO_TOKEN` - токен для чтения репозитория
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `BOT_TOKEN`
- `ALERT_CHAT_ID`
