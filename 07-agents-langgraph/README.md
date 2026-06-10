# ReAct-агент банковского обслуживания

Telegram-бот с автономным ReAct-агентом (LangChain 1.0) для консультирования клиентов по документам Сбербанка о кредитах и вкладах.

## ✨ Возможности

- 🤖 **ReAct-агент** — `create_agent()` + `MemorySaver`; агент сам решает, когда искать в базе знаний
- 🔧 **Инструмент rag_search** — поиск по документам с тремя режами retrieval
- 📚 **Индексация PDF + JSON** — автоматическая обработка документов при старте
- 💬 **Контекстный диалог** — история в MemorySaver (thread_id на чат)
- 🧠 **Advanced RAG** — semantic, hybrid (BM25 + semantic), hybrid+reranker (Cross-Encoder)
- 🔌 **Провайдеры эмбеддингов** - OpenAI (OpenRouter) или HuggingFace (локально)
- ⚡ **Асинхронная обработка** - поддержка множества пользователей одновременно
- 📝 **Логирование** - запись всех событий в файл для отладки

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - менеджер зависимостей

### Установка

1. Клонируйте репозиторий:
   ```bash
   git clone <repository-url>
   cd telegram-llm-bot
   ```

2. Установите зависимости:
   ```bash
   make install
   ```

3. Настройте переменные окружения:
   ```bash
   cp env.example .env
   ```

4. Отредактируйте `.env` (см. раздел "Конфигурация")

5. Запустите бота:
   ```bash
   make run
   ```

## ⚙️ Конфигурация

### Получение токенов

**Telegram Bot Token:**
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot` и следуйте инструкциям
3. Скопируйте токен

**API ключ провайдера:**

Бот использует **OpenRouter** (OpenAI-совместимый API) для LLM и эмбеддингов.

1. Зарегистрируйтесь на [OpenRouter.ai](https://openrouter.ai/)
2. Перейдите в раздел API Keys и создайте ключ

Для экспериментов с эмбеддингами можно дополнительно использовать локальный **Ollama** (потребуются правки кода в `create_vector_store` и зависимость `langchain-ollama`) — см. домашнее задание модуля 4.

### Пример конфигурации (.env)

```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token

# OpenRouter
OPENAI_API_KEY=sk-or-v1-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=openai/gpt-oss-20b:free
EMBEDDING_MODEL=openai/text-embedding-3-large

# Retrieval: semantic | hybrid | hybrid+reranker
RETRIEVAL_MODE=semantic
EMBEDDING_PROVIDER=openai
HUGGINGFACE_EMBEDDING_MODEL=intfloat/multilingual-e5-base
SEMANTIC_K=3
BM25_K=10
HYBRID_K=10
CROSS_ENCODER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKER_TOP_K=3

# Пути
DATA_DIR=data
PROMPTS_DIR=prompts
AGENT_SYSTEM_PROMPT_FILE=agent_system.txt
```

### Описание параметров

**Обязательные:**
- `TELEGRAM_TOKEN` - токен бота от @BotFather
- `OPENAI_API_KEY` - API ключ от выбранного провайдера
- `OPENAI_BASE_URL` - URL API провайдера

**Модели:**
- `MODEL` — LLM агента (ReAct)
- `EMBEDDING_MODEL` — эмбеддинги (при `EMBEDDING_PROVIDER=openai`)
- `RETRIEVAL_MODE` — `semantic`, `hybrid`, `hybrid+reranker`
- `EMBEDDING_PROVIDER` — `openai` или `huggingface`
- `CROSS_ENCODER_MODEL` — reranker (для `hybrid+reranker`)

**Пути:**
- `DATA_DIR` — директория с документами (по умолчанию: `data`)
- `PROMPTS_DIR` — промпты (по умолчанию: `prompts`)
- `AGENT_SYSTEM_PROMPT_FILE` — системный промпт агента с few-shot примерами

## 📚 Добавление документов

1. Поместите PDF файлы в директорию `data/`
2. Перезапустите бота (документы проиндексируются автоматически)
   
   ИЛИ
   
3. Используйте команду `/index` в Telegram для переиндексации

**Примечание:** Бот автоматически:
- Загружает все PDF из `data/`
- Разбивает на чанки по 500 символов
- Создает векторные эмбеддинги
- Сохраняет в памяти для быстрого поиска

## 💬 Использование

### Команды бота

- `/start` - Начать новый диалог (сбросить историю)
- `/help` - Показать справку
- `/index` - Переиндексировать документы
- `/index_status` - Проверить статус индексации

### Примеры диалогов

**Простой вопрос:**
```
👤 Какие условия потребительского кредита?
🤖 По документу, потребительский кредит предоставляется на сумму от 30 000 до 5 000 000 рублей, 
   на срок от 3 месяцев до 5 лет. Процентная ставка зависит от категории заемщика и составляет 
   от 12.9% до 19.9% годовых.
```

**Уточняющий вопрос:**
```
👤 Какие вклады есть в Сбербанке?
🤖 В документах указаны следующие виды вкладов: "Пополняй", "Управляй", "Сохраняй"...

👤 А какие проценты по вкладу "Сохраняй"?
🤖 По вкладу "Сохраняй" процентная ставка составляет от 4% до 6% годовых в зависимости 
   от суммы и срока вклада...
```

**Вопрос вне контекста:**
```
👤 Какая погода сегодня?
🤖 Я не нашел ответа на ваш вопрос в доступных документах.
```

## 🏗️ Архитектура

### Структура проекта

```
├── src/
│   ├── bot.py          # Точка входа, индексация, polling
│   ├── agent.py        # create_agent(), agent_answer(), MemorySaver
│   ├── tools.py        # @tool rag_search
│   ├── handlers.py     # Telegram-команды
│   ├── indexer.py      # Индексация PDF
│   ├── embeddings.py   # Фабрика эмбеддингов
│   ├── retrieval.py    # Semantic / BM25 / Hybrid
│   ├── reranker.py     # Cross-Encoder reranking
│   ├── rag.py          # retrieval helpers, format_sources
│   └── evaluation.py   # Async RAGAS evaluation
├── prompts/
│   └── agent_system.txt    # Системный промпт агента
├── data/               # PDF документы для индексации
├── logs/               # Логи работы бота
├── .env                # Конфигурация (не в git)
├── env.example         # Пример конфигурации
├── Makefile            # Команды для работы
├── pyproject.toml      # Зависимости
└── README.md           # Документация
```

### Как работает агент

1. **Индексация** (при старте):
   ```
   PDF + JSON → чанки → эмбеддинги → vector store + BM25-индекс
   ```

2. **Обработка вопроса**:
   ```
   Telegram → agent_answer(thread_id) → ReAct-цикл →
   [при необходимости: rag_search → retriever → JSON sources] → ответ
   ```

3. **Контекстный диалог**:
   - История в `MemorySaver` (thread_id = chat_id)
   - Агент сам формирует поисковые запросы для `rag_search`
   - Источники извлекаются из ToolMessage текущего запроса

### Технологический стек

- **aiogram 3.x** - Telegram Bot API
- **LangChain 1.0** — `create_agent()`, `@tool`, ReAct
- **LangGraph** — `MemorySaver` для истории диалога
- **LangChain OpenAI** - интеграция с OpenAI-совместимыми API
- **PyPDF** - парсинг PDF документов
- **InMemoryVectorStore** - векторное хранилище в памяти
- **rank-bm25** + **EnsembleRetriever** - гибридный поиск
- **sentence-transformers** - Cross-Encoder reranking

## 🔧 Разработка

### Команды Makefile

```bash
make install    # Установить зависимости
make run        # Запустить бота
```

### Редактирование промптов

Промпты находятся в `prompts/` и могут редактироваться без изменения кода:

**`prompts/agent_system.txt`** — роль агента, правила вызова `rag_search`, few-shot примеры.

### Логи

Логи записываются в `logs/bot.log` и дублируются в консоль.

**Логируются:**
- Старт/остановка бота
- Процесс индексации документов
- Входящие сообщения от пользователей
- Ошибки и исключения

**Пример лога:**
```
2025-11-07 18:32:37,399 - __main__ - INFO - Starting indexing...
2025-11-07 18:32:38,384 - indexer - INFO - Split into 377 chunks
2025-11-07 18:32:41,314 - indexer - INFO - Created vector store with 377 chunks
2025-11-07 18:32:41,314 - __main__ - INFO - Indexing completed successfully
```

### Настройка параметров RAG

В `src/indexer.py` и `src/bot.py` можно настроить:

- **Размер чанков**: `chunk_size=800`, `chunk_overlap=80` (в `RecursiveCharacterTextSplitter`; см. [результаты теста](docs/chunk-size-testing.md))
- **Перекрытие чанков**: ~10% от `chunk_size`
- **Режим retrieval**: `RETRIEVAL_MODE` в `.env`
- **Количество чанков**: `SEMANTIC_K`, `BM25_K`, `HYBRID_K`, `RERANKER_TOP_K`
- **Temperature** для LLM: `temperature=0.7` (в `agent.py`)

## ⚠️ Ограничения

- История в MemorySaver in-memory (теряется при перезапуске)
- Векторное хранилище в памяти (требует переиндексации после перезапуска)
- Только текстовые сообщения (нет поддержки фото, файлов, голосовых)
- Ответы основаны только на проиндексированных документах
- При большом количестве документов может требоваться больше памяти

## 🐛 Устранение неполадок

**Проблема: Бот не отвечает на вопросы**
- Проверьте `/index_status` - должны быть проиндексированы документы
- Убедитесь, что PDF файлы находятся в `data/`
- Проверьте логи в `logs/bot.log`

**Проблема: Ошибка при индексации**
- Проверьте корректность `EMBEDDING_MODEL` для вашего провайдера
- Убедитесь, что API ключ валиден и имеет доступ к embeddings

**Проблема: Бот отвечает "Я не нашел ответа" на все вопросы**
- Возможно, вопросы не связаны с содержимым документов
- Попробуйте задать более конкретные вопросы по тематике документов
- Проверьте, что индексация прошла успешно (`/index_status`)

## 📝 Лицензия

MIT
