# Задание 7 — FastAPI: тестирование, Docker и CI/CD

[![CI](https://github.com/troublegale/itmo-python-lab7/actions/workflows/ci.yml/badge.svg)](https://github.com/troublegale/itmo-python-lab7/actions/workflows/ci.yml)

Репозиторий: https://github.com/troublegale/itmo-python-lab7

В исходной директории был пустой репозиторий и PDF задания; поэтому API пользователей и задач реализован здесь с нуля. Стек: Python 3.14, FastAPI, SQLAlchemy asyncio, asyncpg, PostgreSQL 17, Alembic, pytest, Ruff.

## Запуск приложения

Требуются Docker Engine и Docker Compose v2:

```sh
docker compose up --build -d app
docker compose logs migrate app
```

Swagger UI: http://localhost:8000/docs. PostgreSQL проходит healthcheck; отдельный одноразовый сервис `migrate` выполняет `alembic upgrade head`. Приложение запускается только после успешной миграции. Данные приложения сохраняются в именованном томе. Пароль `tasks` используется только для учебного локального окружения.

API: `POST /users`, `POST /tasks`, `GET /tasks?done=true&offset=0&limit=20`, `GET/PATCH/DELETE /tasks/{id}`. Каждый HTTP-ответ содержит `X-Process-Time` в секундах.

## Тесты локально

Установите Python 3.14 и создайте виртуальное окружение:

```sh
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
docker compose --profile test up -d --wait test-db
$env:DATABASE_URL = "postgresql+asyncpg://tasks:tasks@localhost:5433/tasks_test"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
alembic upgrade head
python -m pytest -v
ruff check .
ruff format --check .
```

Linux/macOS:

```sh
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
docker compose --profile test up -d --wait test-db
export DATABASE_URL=postgresql+asyncpg://tasks:tasks@localhost:5433/tasks_test
export TEST_DATABASE_URL="$DATABASE_URL"
alembic upgrade head
python -m pytest -v
ruff check .
ruff format --check .
```

При использовании своей PostgreSQL заранее создайте отдельную БД `tasks_test` и настройте обе переменные подключения. Перед каждым тестом таблицы очищаются через `TRUNCATE ... RESTART IDENTITY CASCADE`. Защита фикстуры запрещает работу с БД, имя которой отличается от `tasks_test`. Зависимость `get_session` заменяется через `app.dependency_overrides`, после теста подмена удаляется. SQLite и моки БД не используются.

## Тесты через Docker Compose

```sh
docker compose --profile test run --build --rm test
docker compose --profile test down
```

Команда возвращает код завершения pytest, применяет миграции к отдельной PostgreSQL и не требует Python на хосте. Не запускайте тесты параллельно против одной `tasks_test`: фикстуры очищают общие таблицы.

## Покрытые сценарии

В `tests/test_api.py` находятся 12 тестов, включая все 9 обязательных:

| № | Проверка |
|---|---|
| 1 | Создание пользователя — 201 |
| 2 | Повторный email — 409 |
| 3 | Невалидный email — 422 |
| 4 | Создание задачи — 201, чтение сохранённой задачи |
| 5 | Несуществующий владелец — 404 |
| 6 | Фильтр done=true/false и пагинация |
| 7 | PATCH меняет только переданные поля и сохраняет результат |
| 8 | DELETE — 204, последующий GET — 404 |
| 9 | Заголовок X-Process-Time с неотрицательным временем |
| 10 | Явный null в PATCH — 422 |
| 11 | PATCH отсутствующей задачи — 404 |
| 12 | Некорректная пагинация — 422 |

## CI/CD и шаг 8

Workflow `.github/workflows/ci.yml` запускается на каждый push и pull request. Независимые jobs `lint` и `test` проверяют стиль и интеграцию с реальной PostgreSQL, включая запуск тестового Docker-образа через Compose. Job `build` зависит от обоих через `needs: [lint, test]` и публикует образ только для push в `main`. Сборка многоэтапная; production-образ не содержит тестовых зависимостей и работает от пользователя UID 10001.

Для GHCR используется `GITHUB_TOKEN` с `packages: write`. Для Docker Hub настроены секреты репозитория `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN`; их значения не хранятся в git. Оба реестра получают теги `latest` и полный SHA коммита.

В [PR №1](https://github.com/troublegale/itmo-python-lab7/pull/1) проверка времени намеренно заменена на невозможное условие `< 0`. [Запуск с ошибкой](https://github.com/troublegale/itmo-python-lab7/actions/runs/42089657961) завершился результатом **1 failed, 11 passed**; job build был пропущен. Затем проверка восстановлена на `>= 0`.

![Падающий pipeline PR №1](docs/ci-failure.png)

## Образы

- [GHCR](https://github.com/troublegale/itmo-python-lab7/pkgs/container/itmo-python-lab7): `ghcr.io/troublegale/itmo-python-lab7:latest`
- [Docker Hub](https://hub.docker.com/r/troublegale/itmo-python-lab7): `troublegale/itmo-python-lab7:latest`

```sh
docker pull ghcr.io/troublegale/itmo-python-lab7:latest
docker pull troublegale/itmo-python-lab7:latest
```

Образу для запуска требуется переменная `DATABASE_URL` и применённые миграции; готовая конфигурация есть в Compose.

## Ответы на контрольные вопросы

1. **CI и CD.** Continuous integration автоматически проверяет интеграцию изменений: стиль, тесты, сборку. Continuous delivery поддерживает проверенный артефакт готовым к выпуску, но решение о развёртывании остаётся ручным. Continuous deployment автоматически развёртывает прошедшие проверки изменения. В этой работе реализованы CI и публикация образов; автоматического развёртывания на сервер нет.

2. **dependency_overrides.** Это словарь FastAPI, где ключ — исходная функция зависимости, значение — её замена. FastAPI вызывает замену при разрешении Depends. В тестах подменяется get_session, чтобы запросы работали с отдельной тестовой PostgreSQL. После теста словарь очищается, чтобы подмена не влияла на другие сценарии.

3. **Многоэтапная сборка.** Этап builder загружает и собирает wheels. Runtime устанавливает только зависимости приложения из этих wheels. Инструменты сборки и тестовые библиотеки не попадают в конечный production-образ: он меньше, его поверхность атаки уже. Этап test отдельно добавляет pytest и тесты.

4. **Почему не root.** При уязвимости приложения root даёт атакующему больше возможностей менять файлы и воздействовать на окружение контейнера. Непривилегированный UID ограничивает последствия. Это дополняет изоляцию контейнера, ограничения capabilities и защиту хоста.

5. **Секреты GitHub Actions.** Секреты задаются в Settings → Secrets and variables → Actions и передаются через выражения secrets.NAME в нужный шаг. GitHub скрывает известные значения в логах, но намеренно печатать их нельзя. В git секрет остаётся в истории, клонах и форках даже после удаления файла; при утечке его нужно отозвать и перевыпустить. GITHUB_TOKEN создаётся автоматически, его права ограничены permissions.

6. **Если test упадёт.** build будет skipped, так как указан needs: [lint, test]. Без успешного завершения зависимых jobs публикация не начинается. Дополнительное if ограничивает build веткой main и событием push.

7. **Где применять миграции.** При старте удобно для локальной разработки: окружение поднимается одной командой. Минусы — замедление старта и гонки при запуске нескольких реплик. Отдельный шаг CD даёт один контролируемый запуск, журнал и возможность остановить релиз до обновления приложения; требует согласования версий схемы и приложения, стратегии отката и прав доступа к БД. Для production предпочтителен отдельный migration job с обратно совместимыми миграциями. Здесь Compose использует отдельный одноразовый сервис migrate перед стартом app, а CI применяет миграции перед тестами.
