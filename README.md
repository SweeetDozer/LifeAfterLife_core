# LifeAfterLife_core

## Что это

Backend API на FastAPI для работы с семейными деревьями. Проект хранит пользователей, деревья, персон и связи между персонами, а также умеет:

- искать путь между двумя персонами в графе связей;
- выдавать базовую интерпретацию родства по найденному пути.

Это не полный genealogical engine: blood-kinship интерпретация стала точнее для базовых прямых связей, cousin-веток и части removed cases, но логика родства здесь всё ещё ограниченная и местами намеренно упрощённая.

## Предметная цель

API позволяет:

- зарегистрировать пользователя и получить токен;
- создать семейное дерево;
- добавить в дерево персону;
- связать персон отношениями `parent`, `spouse`, `sibling`, `friend`;
- получить путь и базовую интерпретацию родства между двумя персонами.

## Стек

- Python 3.12
- FastAPI
- Pydantic v2
- asyncpg
- PostgreSQL
- python-dotenv
- unittest

Примечание: версия Python в проекте явно не зафиксирована через `pyproject.toml`. Локальный `venv` в репозитории создан на Python `3.12.10`.

## Структура `app/`

- `app/main.py` - создание FastAPI-приложения, подключение роутов, startup/shutdown через lifespan.
- `app/core/` - настройки из `.env` и логика токенов/аутентификации.
- `app/db/` - пул подключений к PostgreSQL и SQL CRUD-слой.
- `app/models/` - Pydantic-модели запросов и ответов.
- `app/routes/` - HTTP-роуты FastAPI.
- `app/services/` - бизнес-логика поверх CRUD: права доступа, граф, родство, создание связей.
- `app/utils/` - вспомогательный пакет, оставлен как явная точка расширения под общие утилиты.

## Что нужно для локального запуска

- Python 3.12+
- PostgreSQL
- `pip`

Минимальный сценарий на Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Или через `pyproject.toml` для editable-установки и dev-инструментов:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -e .[dev]
```

Если зависимости уже установлены в локальном `venv`, можно использовать его.

## Конфигурация окружения

Проект читает переменные окружения из `.env` через `python-dotenv`. В репозитории должен храниться только шаблон `.env.example`; реальный `.env` коммитить не нужно.

### Как создать `.env`

```powershell
Copy-Item .env.example .env
```

После копирования откройте `.env` и подставьте свои локальные значения для базы и секретного ключа.

### Обязательные переменные

- `DB_HOST` - хост PostgreSQL.
- `DB_NAME` - имя базы данных.
- `DB_USER` - пользователь базы данных.
- `DB_PASSWORD` - пароль пользователя базы данных.
- `SECRET_KEY` - ключ для подписи токенов, минимум 32 символа.

Без корректных `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` и `SECRET_KEY` приложение не стартует.

### Необязательные переменные

- `DB_PORT` - порт PostgreSQL, по умолчанию `5432`.
- `ACCESS_TOKEN_EXPIRE_MINUTES` - срок жизни access token, по умолчанию `15`.
- `REFRESH_TOKEN_EXPIRE_DAYS` - срок жизни refresh token / refresh session, по умолчанию `30`.
- `AUTH_LOGIN_IP_FAILURE_LIMIT` - сколько неудачных логинов допускается с одного IP в окне throttling; по умолчанию `20`.
- `AUTH_LOGIN_EMAIL_IP_FAILURE_LIMIT` - сколько неудачных логинов допускается для пары `email + IP`; по умолчанию `5`.
- `AUTH_LOGIN_THROTTLE_WINDOW_MINUTES` - окно для подсчёта неудачных логинов; по умолчанию `15`.
- `AUTH_LOGIN_LOCKOUT_MINUTES` - длительность lockout после достижения login-лимита; по умолчанию `15`.
- `AUTH_REGISTER_IP_ATTEMPT_LIMIT` - сколько регистраций допускается с одного IP в окне throttling; по умолчанию `10`.
- `AUTH_REGISTER_WINDOW_MINUTES` - окно для ограничения регистраций с одного IP; по умолчанию `60`.
- `CORS_ALLOW_ORIGINS` - список allowed origins через запятую; по умолчанию `http://localhost:5173,http://127.0.0.1:5173`.
- `CORS_ALLOW_ORIGINS` не должен содержать `*`, потому что приложение включает `allow_credentials=True`.

### Пример `.env.example`

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=LAL
DB_USER=lal_user
DB_PASSWORD=change_me
SECRET_KEY=replace_with_a_long_random_string_at_least_32_chars
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
AUTH_LOGIN_IP_FAILURE_LIMIT=20
AUTH_LOGIN_EMAIL_IP_FAILURE_LIMIT=5
AUTH_LOGIN_THROTTLE_WINDOW_MINUTES=15
AUTH_LOGIN_LOCKOUT_MINUTES=15
AUTH_REGISTER_IP_ATTEMPT_LIMIT=10
AUTH_REGISTER_WINDOW_MINUTES=60
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Что нужно для локального запуска

Для локальной разработки достаточно:

- поднять PostgreSQL локально;
- создать базу и пользователя;
- заполнить обязательные `DB_*`;
- указать `SECRET_KEY` длиной не менее 32 символов;
- оставить значения по умолчанию для `DB_PORT`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, auth throttling-переменных и `CORS_ALLOW_ORIGINS`, если они вам подходят.

## Auth token TTL

- `ACCESS_TOKEN_EXPIRE_MINUTES` задает срок жизни stateless bearer access token. Значение по умолчанию: `15` минут.
- `REFRESH_TOKEN_EXPIRE_DAYS` задает срок жизни server-side refresh session. Значение по умолчанию: `30` дней.
- Более короткий access token уменьшает окно риска, если bearer token утек.
- Более длинный refresh token сохраняет нормальный DX: клиент может обновлять access token без постоянного повторного логина.
- Logout и revoke инвалидируют refresh sessions сразу, но уже выданные access tokens живут до своего `exp`.

## Auth flow

- `POST /auth/login` проверяет credentials и возвращает `access_token`, `refresh_token` и `token_type`.
- `access_token` используется в `Authorization: Bearer <token>` для защищённых роутов.
- `refresh_token` хранится и ротируется сервером: `POST /auth/refresh` выдаёт новую auth-пару, а старый refresh token перестаёт быть активным.
- `POST /auth/logout` отзывает текущую refresh session.
- `POST /auth/logout-all` отзывает все refresh sessions текущего пользователя.
- `POST /auth/revoke-session` позволяет отозвать конкретную refresh session, если у клиента есть её refresh token.
- Повторное использование уже ротированного refresh token считается replay/compromise сигналом и отзывает всю его token family.

## Temporary legacy auth compatibility

- Основной и поддерживаемый контракт для защищённых роутов: `Authorization: Bearer <access_token>`.
- Старый заголовок `token` больше не считается нормальным публичным контрактом и убран из `.env.example`.
- В backend всё ещё оставлен временный аварийный флаг `ALLOW_LEGACY_TOKEN_HEADER=true` для контролируемой миграции старых клиентов.
- `ALLOW_LEGACY_TOKEN_HEADER` по умолчанию выключен и должен использоваться только как краткоживущая совместимость.
- Текущий `LAL_web` уже использует `Authorization: Bearer`, поэтому отдельная фронтенд-миграция для header-формата не нужна.

## Auth brute-force protection

- `POST /auth/login` защищён двумя лимитами: более мягким `per-IP` и более строгим `per email + IP`.
- После серии неудачных логинов backend включает временный lockout и отвечает `429 Too Many Requests` с `Retry-After`.
- `POST /auth/register` ограничен по количеству попыток с одного IP, чтобы endpoint не был бесконечной мишенью для abuse.
- Счётчики throttling хранятся в БД, а не только в памяти процесса, поэтому защита остаётся полезной и при нескольких инстансах backend.
- Текущая реализация использует `request.client.host`; если backend стоит за reverse proxy/load balancer, важно корректно настроить передачу реального client IP на уровне инфраструктуры.

Если frontend запускается локально на Vite, дефолтный `CORS_ALLOW_ORIGINS` уже покрывает `http://localhost:5173` и `http://127.0.0.1:5173`.

## Как подготовить PostgreSQL и таблицы

В репозитории есть SQL-скрипт [`create_LAL_DB_PG_.sql`](./create_LAL_DB_PG_.sql). Он создаёт enum-типы и таблицы:

- `users`
- `family_trees`
- `persons`
- `relationships`
- `tree_access`

Важно:

- активного механизма миграций нет;
- строка `CREATE DATABASE ...` в SQL-файле закомментирована;
- роль/пользователя БД нужно создать самостоятельно, если его ещё нет.
- для новой БД, созданной сразу из [`create_LAL_DB_PG_.sql`](./create_LAL_DB_PG_.sql), старые миграции не нужны: этот файл уже описывает текущее каноническое состояние схемы;
- для уже существующей БД миграции остаются legacy upgrade шагом: [`migrations/2026_04_09_tree_access_role_hardening.sql`](./migrations/2026_04_09_tree_access_role_hardening.sql) переводит `tree_access` на роли `viewer/editor`, удаляет дубли owner в `tree_access` и усиливает ограничения на уровне схемы;

### Delete / Cascade semantics

- `DELETE /trees/{tree_id}` удаляет строку из `family_trees` в коде. `persons`, `relationships` и делегированные записи `tree_access` удаляет PostgreSQL через `ON DELETE CASCADE`.
- `DELETE /persons/{person_id}` удаляет строку из `persons` в коде. Связанные `relationships` удаляет PostgreSQL через `ON DELETE CASCADE`.
- `DELETE /relationships/{relationship_id}` удаляется кодом: `parent` удаляет одну направленную связь, `spouse` / `sibling` / `friend` удаляют всю симметричную пару.
- Инварианты: после удаления `tree` или `person` не остаётся висячих записей; после удаления `spouse` / `sibling` / `friend` не остаётся половины пары.
- Этот контракт обеспечен схемой для `family_trees -> persons`, `family_trees -> relationships`, `family_trees -> tree_access` и `persons -> relationships`, плюс сервисной логикой для симметричных `relationship`.
- Для уже существующей БД это нужно довести миграциями: [`migrations/2026_04_09_tree_access_role_hardening.sql`](./migrations/2026_04_09_tree_access_role_hardening.sql) и [`migrations/2026_04_09_explicit_delete_contracts.sql`](./migrations/2026_04_09_explicit_delete_contracts.sql).

Минимальная последовательность:

1. Создать пользователя PostgreSQL и базу данных вручную.
2. Выдать этому пользователю права на базу.
3. Применить SQL-скрипт.

Пример запуска скрипта:

```powershell
psql -h localhost -U lal_user -d LAL -f .\create_LAL_DB_PG_.sql
```

Если `psql` не установлен, его тоже нужно поставить вместе с клиентскими инструментами PostgreSQL.

## Как стартовать FastAPI-приложение

```powershell
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

После старта документация FastAPI будет доступна по адресу `http://127.0.0.1:8000/docs`.

Приложение при запуске:

- валидирует env-переменные;
- пытается подключиться к PostgreSQL;
- не поднимается, если база не готова или не задан `SECRET_KEY`.

## Основные группы роутов

- `/auth` - регистрация и логин, выдача bearer token.
- `/trees` - создание, обновление и удаление деревьев, получение списка доступных деревьев, а также минимальный API управления `tree_access`.
- `/persons` - создание, обновление и удаление персон, получение одной персоны и списка персон дерева.
- `/relationships` - создание связей между персонами и удаление существующей связи.
- `/graph` - поиск пути между персонами в графе связей.
- `/kinship` - попытка интерпретировать найденный путь как родство. Лучше поддерживаются `parent/child`, `sibling`, `aunt/uncle`, `niece/nephew`, `first/second/third cousin` и часть `removed`-случаев.

Практически все роуты, кроме `/auth`, требуют `Authorization: Bearer <token>`.

## Модель доступа к дереву

Для дерева используется простая role-based модель:

- `owner` - владелец дерева. Источник истины для owner: `family_trees.user_id`.
- `editor` - может читать и редактировать содержимое дерева.
- `viewer` - может только читать дерево.

Что может каждая роль:

- `owner`: просмотр дерева, редактирование дерева и его содержимого, просмотр списка доступов, выдача доступа, смена роли, отзыв доступа, удаление дерева.
- `editor`: просмотр дерева, редактирование дерева и его содержимого, без управления доступами.
- `viewer`: только просмотр дерева, без редактирования и без управления доступами.

Endpoints, связанные с доступом:

- `GET /trees/{tree_id}/access` - список пользователей с доступом к дереву.
- `POST /trees/{tree_id}/access` - выдать доступ пользователю.
- `PATCH /trees/{tree_id}/access/{target_user_id}` - изменить роль пользователя.
- `DELETE /trees/{tree_id}/access/{target_user_id}` - отозвать доступ пользователя.

Ограничения и инварианты:

- у дерева всегда должен быть `owner`;
- `owner` определяется отдельно через `family_trees.user_id`, а не через редактируемую запись в `tree_access`;
- `editor` и `viewer` не управляют доступом;
- `tree_access` хранит только делегированный доступ для ролей `editor` и `viewer`;
- нельзя выдать доступ owner, понизить owner или отозвать owner через access API.

## Тесты

В проекте есть два практических слоя тестов:

- unit tests для `crud`, security и сервисной логики;
- route-level / integration tests для основных HTTP-сценариев без использования рабочей PostgreSQL.

Запуск всего набора:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

Что сейчас покрыто:

- auth: регистрация, логин, ошибки валидации и неверные credentials;
- защищённые роуты: доступ с токеном и без токена;
- persons / relationships / kinship happy path;
- CORS preflight;
- tree access и базовые update/delete сценарии.

## Текущие ограничения и недоделки

- Нет Alembic/миграций: схема разворачивается вручную одним SQL-файлом.
- Нет `docker-compose`, контейнеризации и готового one-command setup.
- Для `tree_access` есть простой role-based API (`owner/editor/viewer`) без расширенной ACL-модели и без аудита изменений.
- Update/delete-операции теперь есть для деревьев и персон, а для связей доступно удаление; отдельная операция смены типа связи пока не введена.
- Интерпретация родства по-прежнему ограниченная: лучше поддерживаются basic direct blood relations, cousins и часть `removed`-случаев, но `step`, `adoptive`, `in-law` и другие небазовые family semantics пока не реализованы полноценно.
- Выбор пути для kinship стал лучше для равных shortest-path вариантов, но shortest-path подход всё ещё не гарантирует наиболее генеалогически осмысленный путь во всех графах.
- Mixed / ambiguous relations и неочевидные комбинации связей по-прежнему могут сводиться к `"unknown"` или `"сложное родство"`.
- Integration tests покрывают ключевые route-level сценарии, но это всё ещё не прогон против реальной PostgreSQL и не full end-to-end окружение.
- Нет аудита изменений, soft delete и миграционной истории для update/delete операций.

## Быстрая проверка

Запуск тестов:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

В текущем локальном `venv` тесты проходят. Если запускать тем `python`, где не установлены зависимости, тесты упадут уже на импортах.
