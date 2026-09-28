# CRM ИТ Школы Ростелеком — Backend

REST API для системы контроля взаимодействия с вузами по ИТ-направлениям.

---

## Стек

- **Runtime:** Node.js 20
- **Framework:** Express 4
- **Отчёты:** excel4node (xlsx), pdfkit (pdf), json2csv (csv)
- **Контейнеризация:** Docker + Docker Compose
- **Компоненты инфраструктуры:** Redis 7, MinIO (подняты в compose)

---

## Быстрый старт

### Локально

```bash
npm install
npm start
```

Сервер: `http://localhost:3000`

### Через Docker

```bash
docker compose up --build
```

Поднимаются три контейнера:
- `crm-api` — Node.js API на порту `3000`
- `crm-redis` — Redis на порту `6379`
- `crm-minio` — MinIO на портах `9000` (API) и `9001` (web UI, логин/пароль `minioadmin` / `minioadmin`)

Остановить:

```bash
docker compose down
```

---

## Структура проекта

```
crmRT/
├── src/
│   ├── index.js                    # точка входа, подключение роутов
│   ├── data/
│   │   └── mock.js                 # мок-данные (вузы, направления, продукты, пользователи)
│   ├── routes/
│   │   ├── universities.js         # список вузов, фильтры, карточка
│   │   ├── workflow.js             # смена этапов
│   │   ├── reports.js              # формирование отчётов
│   │   ├── catalogs.js             # каталоги
│   │   └── integrations.js         # интерфейс интеграций
│   ├── services/
│   │   └── reportService.js        # генерация xlsx / pdf / csv
│   └── middleware/
│       └── auth.js                 # RBAC через заголовок x-user-id
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── package.json
```

---

## Ролевая модель

Роль определяется заголовком `x-user-id` в HTTP-запросе. Если заголовка нет — подставляется пользователь `id=1` (роль `user`).

| ID | Имя     | Роль    | Права                                              |
|----|---------|---------|----------------------------------------------------|
| 1  | Тест 1  | user    | Видит только свои вузы (managerId = 1)             |
| 2  | Тест 2  | head    | Видит все вузы                                     |
| 3  | Тест 3  | admin   | Видит все вузы + импорт каталога                   |

Пример запроса с ролью admin:

```bash
curl -H "x-user-id: 3" http://localhost:3000/api/universities
```

---

## Эндпоинты

### Служебные

| Метод | URL      | Описание                       |
|-------|----------|--------------------------------|
| GET   | /health  | Проверка живости сервиса       |

### Вузы

| Метод | URL                    | Описание                |
|-------|------------------------|-------------------------|
| GET   | /api/universities      | Список вузов с фильтрами |
| GET   | /api/universities/:id  | Карточка вуза            |

Параметры фильтрации `/api/universities`:

- `direction` — ID ИТ-направления
- `product` — ID ИТ-продукта
- `stage` — индекс этапа workflow (0–13)
- `manager` — ID ответственного
- `q` — поиск по названию вуза и городу

Пример:

```bash
curl "http://localhost:3000/api/universities?direction=1&stage=6&q=вуз"
```

### Workflow

| Метод | URL                        | Описание                                             |
|-------|----------------------------|------------------------------------------------------|
| POST  | /api/workflow/:id/next     | Перевести вуз на следующий этап                      |
| POST  | /api/workflow/:id/prev     | Вернуть вуз на предыдущий этап (нужен комментарий)   |

Тело запроса:

```json
{ "comment": "Встреча прошла успешно" }
```

### Отчёты

| Метод | URL          | Описание                                     |
|-------|--------------|----------------------------------------------|
| POST  | /api/reports | Сформировать отчёт в xls / xlsx / pdf / csv  |

Тело запроса:

```json
{
  "periodFrom": "01.09.2026",
  "periodTo": "30.09.2026",
  "directionId": 1,
  "productId": 1,
  "managerId": 2,
  "columns": ["name", "direction", "product", "stage", "manager"],
  "format": "xlsx"
}
```

- `periodFrom`, `periodTo` — период в формате `ДД.ММ.ГГГГ` (необязательно)
- `directionId`, `productId`, `managerId` — фильтры по ID (необязательно)
- `columns` — какие колонки включить: `name`, `direction`, `product`, `stage`, `manager`
- `format` — `xlsx` (по умолчанию), `xls`, `pdf`, `csv`

Пример:

```bash
curl -X POST http://localhost:3000/api/reports \
  -H "Content-Type: application/json" \
  -H "x-user-id: 3" \
  -d '{"format":"xlsx","columns":["name","stage","manager"]}' \
  --output report.xlsx
```

### Каталоги

| Метод | URL                   | Описание                            |
|-------|-----------------------|-------------------------------------|
| GET   | /api/catalogs         | Справочники одним запросом          |
| POST  | /api/catalogs/import  | Импорт каталога (только admin)      |

### Интеграции

| Метод | URL                      | Описание                            |
|-------|--------------------------|-------------------------------------|
| GET   | /api/integrations/lms    | Получить данные из LMS              |
| GET   | /api/integrations/site   | Получить данные из сайта (Laravel)  |
| POST  | /api/integrations/sync   | Запустить синхронизацию             |

---

## Коды ошибок

| Код  | Когда возвращается                      |
|------|-----------------------------------------|
| 200  | Успешно                                 |
| 400  | Неверные данные в запросе               |
| 401  | Пользователь не авторизован             |
| 403  | Недостаточно прав                       |
| 404  | Объект не найден                        |
| 1001 | Ошибка импорта: неверный формат файла   |
| 1002 | Неверный формат загружаемого файла      |

Формат ответа об ошибке:

```json
{ "code": "401", "message": "Нет авторизации" }
```

---

## Проверка работоспособности

```bash
# 1. Проверка живости
curl http://localhost:3000/health

# 2. Список вузов как user (видит только свои — 3 шт)
curl http://localhost:3000/api/universities

# 3. Список вузов как admin (видит все 8)
curl -H "x-user-id: 3" http://localhost:3000/api/universities

# 4. Отчёт в xlsx
curl -X POST http://localhost:3000/api/reports \
  -H "Content-Type: application/json" \
  -H "x-user-id: 3" \
  -d '{"format":"xlsx"}' --output report.xlsx
```

---

## Репозиторий

- Ветка разработки backend: `backendAlena`