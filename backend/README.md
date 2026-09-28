# CRM ИТ Школы Ростелекома — Backend: Каталоги и Безопасность

Python/FastAPI-сервис для разделов **Каталоги данных** и **Безопасность и compliance**.

## Структура

```
backend/
├── app/
│   ├── main.py            # FastAPI app, lifespan, CORS
│   ├── database.py        # Async SQLAlchemy engine + session
│   ├── models.py          # ORM: User, Direction, Product, University, AuditLog, BlockedToken
│   ├── schemas.py         # Pydantic v2 схемы
│   ├── security.py        # JWT, Keycloak OIDC, роли, audit helper
│   └── routers/
│       ├── catalogs.py        # /api/catalogs/*
│       └── security_router.py # /api/security/*
├── seed.py                # Начальные данные (dev)
├── requirements.txt
└── .env.example
```

## Быстрый старт

### 1. Зависимости

```bash
pip install -r requirements.txt
```

### 2. PostgreSQL

```bash
# Локально (Docker)
docker run -d --name crmrt-db \
  -e POSTGRES_USER=crm -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=crmrt \
  -p 5432:5432 postgres:16-alpine
```

### 3. Переменные окружения

```bash
cp .env.example .env
# Отредактируй .env под свою среду
```

### 4. Запуск

```bash
# из папки crmRT/
uvicorn backend.app.main:app --reload --port 8000
```

### 5. Seed (начальные данные)

```bash
python backend/seed.py
```

### 6. Swagger UI

- http://localhost:8000/docs

---

## Роли

| Роль | Уровень | Что может |
|------|---------|-----------|
| `manager` | 0 | Чтение справочников, свои вузы |
| `head` | 1 | + Создание/редактирование каталогов, все вузы и пользователи |
| `admin` | 2 | + Удаление, импорт xlsx, управление пользователями, выгрузка аудита |

---

## API (краткое)

### Каталоги `/api/catalogs`

| Метод | Путь | Роль | Описание |
|-------|------|------|----------|
| GET | `/directions` | manager+ | Список направлений |
| POST | `/directions` | head+ | Создать направление |
| PUT | `/directions/{id}` | head+ | Обновить |
| DELETE | `/directions/{id}` | admin | Деактивировать |
| GET | `/products` | manager+ | Список продуктов |
| POST | `/products` | head+ | Создать продукт |
| GET | `/universities` | manager+ | Справочник вузов |
| POST | `/universities` | head+ | Добавить вуз |
| POST | `/import/universities` | admin | Импорт из xlsx |

### Безопасность `/api/security`

| Метод | Путь | Роль | Описание |
|-------|------|------|----------|
| POST | `/login` | — | JWT-логин (dev-режим) |
| POST | `/logout` | any | Отозвать токен |
| GET | `/me` | any | Текущий пользователь |
| GET | `/users` | head+ | Список пользователей |
| POST | `/users` | admin | Создать пользователя |
| PUT | `/users/{id}` | admin | Обновить пользователя |
| POST | `/users/{id}/block` | admin | Заблокировать (ФЗ-152) |
| POST | `/users/{id}/unblock` | admin | Разблокировать |
| GET | `/audit` | head+ | Журнал аудита |
| GET | `/audit/export` | admin | Выгрузка аудита в xlsx |

---

## Keycloak (prod)

В `.env` установи:
```
KEYCLOAK_ENABLED=true
KEYCLOAK_URL=https://your-keycloak.example.com
KEYCLOAK_REALM=crmrt
KEYCLOAK_CLIENT_ID=crm-backend
```

Сервер автоматически подтянет JWKS и будет верифицировать RS256 токены.  
Пользователи должны быть предварительно созданы в CRM с `keycloak_sub` = UUID из Keycloak.

---

## Соответствие ТЗ

| Требование | Реализация |
|---|---|
| Каталоги: направления, продукты, вузы | CRUD в `routers/catalogs.py` |
| Импорт справочников из xlsx | `POST /api/catalogs/import/universities` |
| Keycloak (п.10) | `security.py` — OIDC JWKS verify |
| Роли: manager / head / admin | `require_role()` dependency |
| ФЗ-152 — аудит доступа к ПД | `AuditLog` model + `write_audit()` на всех мутациях |
| ФЗ-117 — журнал событий безопасности | `audit_log` таблица, выгрузка в xlsx |
| Отзыв токенов (logout / блокировка) | `BlockedToken` blacklist, проверка в каждом запросе |

---

