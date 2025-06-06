# Foodgram «Продуктовый помощник»

Foodgram - это веб-сервис, где пользователи могут публиковать рецепты, добавлять чужие рецепты в избранное и подписываться на публикации других авторов. Сервис также предоставляет возможность создавать список покупок на основе выбранных рецептов.

## Технологический стек

- **Бэкенд:** Python, Django, Django REST framework, Djoser
- **База данных:** PostgreSQL (в Docker), SQLite3 (локально по умолчанию)
- **Фронтенд:** React
- **Контейнеризация:** Docker, Docker Compose
- **Веб-сервер:** Nginx

## Автор

- **ФИО:** Блинаев Никита
- **Контакт:** [nicklin11](https://github.com/nicklin11/)

## Развертывание проекта (с Docker)

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/nicklin11/foodgram-project.git
    cd foodgram-project
    ```

2.  **Создайте файл `.env` в директории `infra/`** со следующими переменными окружения (пример):
    ```env
    # infra/.env
    DB_ENGINE=django.db.backends.postgresql
    DB_NAME=postgres
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=postgres
    DB_HOST=db
    DB_PORT=5432

    SECRET_KEY=your_very_secret_key_for_django
    DEBUG=1 # 0 для продакшена
    ALLOWED_HOSTS=localhost,127.0.0.1,your_domain.com

    # Для Django (если backend/settings.py читает их напрямую)
    # DJANGO_SECRET_KEY=${SECRET_KEY}
    # DJANGO_DEBUG=${DEBUG}
    # DJANGO_ALLOWED_HOSTS=${ALLOWED_HOSTS}
    ```
    *Примечание: В `settings.py` проекта обычно используются переменные типа `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`. Если ваш `settings.py` ожидает переменные с префиксом `DJANGO_`, убедитесь, что они также установлены или что `settings.py` корректно считывает основные переменные.*

3.  **Соберите и запустите контейнеры:**
    Находясь в папке `infra/` (где лежит `docker-compose.yml`):
    ```bash
    docker-compose up --build
    ```
    При первом запуске контейнер `frontend` соберет статические файлы и завершит работу. Остальные сервисы (`db`, `backend`, `nginx`) продолжат работать.

4.  **Выполните миграции базы данных:**
    В новом терминале, **находясь в корневой папке проекта `foodgram-project/`** (или любой другой, откуда доступен `docker-compose` и указан путь к `docker-compose.yml` файлу, если он не в текущей директории):
    ```bash
    docker-compose -f infra/docker-compose.yml exec backend python manage.py migrate
    ```
    *Или, если вы уже находитесь в `infra/`:*
    ```bash
    docker-compose exec backend python manage.py migrate # migrate выполняется в директории backend при разворачивании проекта с помощью docker-compose
    ```

5.  **Создайте суперпользователя (опционально):**
    Команду выполнять аналогично пункту 4 (указывая путь к `docker-compose.yml` или находясь в `infra/`):
    ```bash
    docker-compose -f infra/docker-compose.yml exec backend python manage.py createsuperuser
    ```
    *Или из `infra/`:*
    ```bash
    docker-compose exec backend python manage.py createsuperuser
    ```

6.  **Загрузите ингредиенты из JSON-фикстуры:**
    Убедитесь, что файл `ingredients.json` находится в папке `backend/data/`.
    Команду выполнять аналогично пункту 4:
    ```bash
    docker-compose -f infra/docker-compose.yml exec backend python manage.py load_ingredients --path /app/data/ingredients.json
    ```
    *Или из `infra/`:*
    ```bash
    docker-compose exec backend python manage.py load_ingredients --path /app/data/ingredients.json
    ```
    *(Путь `/app/data/ingredients.json` соответствует расположению данных внутри контейнера `backend`)*

7.  **Соберите статику для Django Admin:**
    Команду выполнять аналогично пункту 4:
    ```bash
    docker-compose -f infra/docker-compose.yml exec backend python manage.py collectstatic --noinput
    ```
    *Или из `infra/`:*
    ```bash
    docker-compose exec backend python manage.py collectstatic --noinput
    ```

## Локальное развертывание (без Docker, для разработки)

1.  **Клонируйте репозиторий и перейдите в папку `backend`:**
    ```bash
    git clone https://github.com/nicklin11/foodgram-project.git
    cd foodgram-project/backend
    ```

2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # для Linux/macOS
    # venv\Scripts\activate    # для Windows
    ```

3.  **Установите зависимости:**
    ```bash
    pip install -r ../requirements.txt
    ```
    *(Убедитесь, что `requirements.txt` находится в корне проекта, т.е. в `foodgram-project/`)*

4.  **Настройте переменные окружения (опционально):**
    Можно создать файл `.env` в папке `backend/` (если `python-dotenv` используется в `settings.py`) или установить переменные системно.
    `settings.py` использует значения по умолчанию для `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` и `SQLite` базы данных, если переменные окружения не заданы.

5.  **Выполните миграции:**
    ```bash
    python manage.py migrate
    ```

6.  **Создайте суперпользователя:**
    ```bash
    python manage.py createsuperuser
    ```

7.  **Загрузите ингредиенты:**
    Убедитесь, что `ingredients.json` в `backend/data/`.
    ```bash
    python manage.py load_ingredients
    ```
    *(Команда использует путь по умолчанию `data/ingredients.json` относительно `BASE_DIR`)*

8.  **Запустите сервер разработки Django:**
    ```bash
    python manage.py runserver
    ```
    Бэкенд будет доступен по адресу [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Доступ к приложению

-   [Веб-приложение](http://localhost/) (при развертывании с Docker и Nginx)
-   [Административная панель Django](http://localhost/admin/) (или `http://127.0.0.1:8000/admin/` при локальном запуске Django)
-   [API документация (ReDoc)](http://localhost/api/docs/) (или `http://127.0.0.1:8000/api/docs/` при локальном запуске, если настроен соответствующий URL)
-   **API эндпоинты:** `http://localhost/api/` (например, `http://localhost/api/ingredients/`)

## Остановка Docker-контейнеров
Находясь в папке `infra/` (или указывая путь к `docker-compose.yml` файлу с флагом `-f`):
```bash
docker-compose down