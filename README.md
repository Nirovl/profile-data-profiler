# Data Quality Profiler

Инструмент для автоматизированной проверки качества данных на основе правил в формате JSON.
Он анализирует CSV-файлы и генерирует Markdown-отчёты по ключевым критериям качества данных.

## Что проверяет

- **Полнота** — есть ли пропуски
- **Уникальность** — есть ли дубликаты
- **Валидность** — соответствие форматам (даты, email, диапазоны)
- **Разумность** — статистические аномалии
- **Объективность** — перекосы в распределении данных
- **Согласованность** — бизнес-правила (`quantity × price = total`, другие формулы)
- **Точность** — соответствие справочникам и lookup-таблицам

## Для кого

- **Data-инженеры** — для проверки данных перед загрузкой и передачей
- **Аналитики** — для оценки качества выгрузок и подготовки отчётов
- **Бизнес-пользователи** — для контроля данных и поиска проблемных полей

## Установка

```bash
git clone https://github.com/Nirovl/data-quality-profiler.git
cd data-quality-profiler
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# или PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Запуск

### Через Docker

```bash
docker build -t data-quality-profiler .
```

#### Windows PowerShell

```powershell
docker run --rm -v "${PWD}:/app" data-quality-profiler hr_data_sample.csv hr_rules.json
```

#### macOS / Linux

```bash
docker run --rm -v "$(pwd):/app" data-quality-profiler hr_data_sample.csv hr_rules.json
```

### Локально через Python

```bash
source .venv/bin/activate      # macOS / Linux
# или PowerShell:
# .\.venv\Scripts\Activate.ps1
python profile_investor.py hr_data_sample.csv hr_rules.json
```

### Через Docker Compose

```bash
docker compose up --build
```

Этот `docker compose` запускает сервис с командой по умолчанию:

```bash
sales_data_sample.csv rules.json
```

## Примеры запуска с другими наборами данных

```bash
# HR
docker run --rm -v "${PWD}:/app" data-quality-profiler hr_data_sample.csv hr_rules.json

# Inventory
docker run --rm -v "${PWD}:/app" data-quality-profiler inventory_data_sample.csv inventory_rules.json
```

## Структура проекта

- `profile_investor.py` — основной скрипт профайлера
- `rules.json` — базовый набор правил для sales
- `hr_rules.json`, `inventory_rules.json` — правила для разных доменов
- `sales_data_sample.csv`, `hr_data_sample.csv`, `inventory_data_sample.csv` — примеры данных
- `Dockerfile` — контейнерная сборка
- `docker-compose.yml` — быстрый запуск сервиса
- `requirements.txt` — зависимости Python
- `README.md` — документация проекта

## Ручная публикация контейнера

В `.github/workflows/ci.yml` есть `workflow_dispatch` с параметром `push`.
При запуске вручную можно указать `push: true`, чтобы workflow собрал контейнер и отправил его в GHCR.

#### Windows PowerShell

```powershell
docker run --rm -v "${PWD}:/app" data-quality-profiler hr_data_sample.csv hr_rules.json
```

#### macOS / Linux

```bash
docker run --rm -v "$(pwd):/app" data-quality-profiler hr_data_sample.csv hr_rules.json
```

### Локально через Python

```bash
source .venv/bin/activate      # macOS / Linux
# или PowerShell:
# .\.venv\Scripts\Activate.ps1
python profile_investor.py hr_data_sample.csv hr_rules.json
```

### Через Docker Compose
>>>>>>> 2936490 (docs: update README)

# Inventory
docker run --rm -v "${PWD}:/app" data-quality-profiler inventory_data_sample.csv inventory_rules.json
📂 Структура проекта
profile_investor.py — основной скрипт профайлера

<<<<<<< HEAD
rules.json — базовый набор правил

hr_rules.json, inventory_rules.json — правила для разных доменов

sales_report.md, hr_report.md, inventory_report.md — сгенерированные отчёты

Dockerfile — контейнерная сборка

docker-compose.yml — быстрый запуск сервиса

requirements.txt — зависимости Python


### 🚀 Что делать дальше

1. **Скопируйте** этот текст.
2. **Откройте** файл `README.md` в VS Code или на GitHub.
3. **Вставьте** текст (полностью заменив старое содержимое).
4. **Сохраните** и запушите:
   ```bash
   git add README.md
   git commit -m "docs: полный README для инвесторов"
   git push
=======
Этот `docker compose` запускает сервис с командой по умолчанию:

```bash
sales_data_sample.csv rules.json
```

## Примеры запуска с другими наборами данных

```bash
# HR
docker run --rm -v "${PWD}:/app" data-quality-profiler hr_data_sample.csv hr_rules.json

# Inventory
docker run --rm -v "${PWD}:/app" data-quality-profiler inventory_data_sample.csv inventory_rules.json
```

## Структура проекта

- `profile_investor.py` — основной скрипт профайлера
- `rules.json` — базовый набор правил для sales
- `hr_rules.json`, `inventory_rules.json` — правила для разных доменов
- `sales_data_sample.csv`, `hr_data_sample.csv`, `inventory_data_sample.csv` — примеры данных
- `Dockerfile` — контейнерная сборка
- `docker-compose.yml` — быстрый запуск сервиса
- `requirements.txt` — зависимости Python
- `README.md` — документация проекта

## Ручная публикация контейнера

В `.github/workflows/ci.yml` есть `workflow_dispatch` с параметром `push`.
При запуске вручную можно указать `push: true`, чтобы workflow собрал контейнер и отправил его в GHCR.
>>>>>>> 2936490 (docs: update README)
