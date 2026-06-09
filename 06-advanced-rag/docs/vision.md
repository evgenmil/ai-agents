# Техническое видение проекта

## Технологии

**Основные технологии:**
- **Python 3.11+** — основной язык разработки
- **uv** — управление зависимостями и виртуальным окружением
- **aiogram 3.x** — фреймворк для Telegram Bot API (polling)
- **LangChain** — фреймворк для построения RAG-приложений (LCEL)
- **langchain-openai** — ChatOpenAI, OpenAIEmbeddings через OpenRouter
- **langchain-community** — InMemoryVectorStore, BM25Retriever
- **langchain-huggingface** — HuggingFaceEmbeddings (локальные эмбеддинги)
- **openai** — клиент для работы с LLM через OpenRouter
- **sentence-transformers** — Cross-Encoder для reranking
- **rank-bm25** — BM25-индекс для keyword-поиска
- **pypdf** — загрузка и парсинг PDF-документов
- **python-dotenv** — переменные окружения
- **Make** — автоматизация сборки и запуска
- **langsmith** — трейсинг LangChain и evaluation в LangSmith
- **ragas** (>=0.2.0), **datasets** — batch-оценка качества RAG

**Референс:** `docs/references/advanced-hybrid-rag.ipynb` (Part 1: Hybrid RAG, Part 2: Cross-Encoder Reranking)

## Принципы разработки

**Принципы:**
- **KISS** — максимальная простота решений
- **YAGNI** — реализуем только то, что нужно сейчас
- **Монолитная архитектура** — весь код в одном месте, никаких микросервисов
- **Прямолинейный код** — минимум абстракций, максимум читаемости
- **Модульность без оверинжиниринга** — отдельные файлы по зонам ответственности, без пакетов и DI

**Что НЕ делаем:**
- Не создаем сложные архитектурные паттерны
- Не делаем преждевременную оптимизацию
- Не добавляем функции «на будущее»
- Не усложняем без крайней необходимости

## Структура проекта

```
/
├── src/
│   ├── bot.py              # Точка входа, polling
│   ├── handlers.py         # Обработчики Telegram
│   ├── rag.py              # RAG-цепочки (LCEL), query transformation
│   ├── retrieval.py        # Semantic / BM25 / Hybrid retriever
│   ├── reranker.py         # Cross-Encoder reranking
│   ├── embeddings.py       # Фабрика эмбеддингов (openai / huggingface)
│   ├── indexer.py          # Индексация PDF, vector store, чанки для BM25
│   ├── config.py           # Загрузка конфигурации из .env
│   ├── dataset_synthesizer.py
│   └── evaluation.py
├── data/
├── datasets/
├── prompts/
├── .env / .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

**Принцип:** Плоская папка `src/` без пакетов. Новые модули (`retrieval.py`, `reranker.py`, `embeddings.py`) выделяют зоны ответственности, не создавая лишних слоёв абстракции.

## Архитектура проекта

**Компоненты:**

1. **bot.py** — точка входа, индексация при старте, polling
2. **handlers.py** — команды (`/start`, `/help`, `/index`, `/index_status`, `/evaluate_dataset`), история диалогов в памяти
3. **indexer.py** — загрузка PDF, splitting, создание vector store и сохранение чанков (для BM25)
4. **embeddings.py** — `get_embeddings()` по `EMBEDDING_PROVIDER` (openai / huggingface)
5. **retrieval.py** — построение retriever по `RETRIEVAL_MODE`:
   - `semantic` — только векторный поиск
   - `hybrid` — `EnsembleRetriever` (semantic + BM25, RRF)
   - `hybrid+reranker` — hybrid retrieval + cross-encoder в цепочке
6. **reranker.py** — `rerank_documents(query, documents, top_k)` через `CrossEncoder`
7. **rag.py** — LCEL-цепочки:
   - `retrieval_query_transformation_chain` — трансформация запроса по истории (сохраняется!)
   - `get_rag_chain()` — query transform → retriever [→ reranker] → LLM → `{answer, documents}`
8. **config.py** — все настройки из `.env`
9. **evaluation.py** — RAGAS evaluation с поддержкой сравнения режимов retrieval

**Поток данных (RAG):**
```
Telegram → handlers.py (история) →
rag.py (query transformation → retriever [→ reranker] → context augmentation) →
LLM → handlers.py → Telegram
```

**Принцип:** Прямые вызовы функций. Глобальные переменные для `vector_store`, `chunks`, `retriever`. Без DI и интерфейсов.

## Режимы retrieval

| Режим (`RETRIEVAL_MODE`) | Semantic | BM25 | Reranker |
|--------------------------|----------|------|----------|
| `semantic`               | ✓        | —    | —        |
| `hybrid`                 | ✓        | ✓    | —        |
| `hybrid+reranker`        | ✓        | ✓    | ✓        |

Реализация по референсу `advanced-hybrid-rag.ipynb`:
- Semantic: `InMemoryVectorStore.as_retriever()`
- BM25: `BM25Retriever.from_documents(chunks)`
- Hybrid: `EnsembleRetriever(retrievers=[semantic, bm25], weights=[...])`
- Reranker: `CrossEncoder` из `sentence-transformers`, top-k после ensemble

## Модель данных

История диалогов — глобальный `dict[int, list]` в `handlers.py` (без БД). При перезапуске бота история теряется.

При индексации в памяти хранятся:
- `vector_store` — векторный индекс
- `chunks` — список чанков (нужен для BM25)

## Работа с LLM

**Провайдер:** OpenRouter (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`)

**Модели из .env:**
- `MODEL` — основная LLM для ответов
- `MODEL_QUERY_TRANSFORM` — LLM для трансформации запроса

**Принцип:** Асинхронный запрос-ответ через LangChain `ChatOpenAI`. Без retry, очередей, streaming.

## Провайдеры эмбеддингов

Переключение через `EMBEDDING_PROVIDER`:
- `openai` — `OpenAIEmbeddings` (модель `EMBEDDING_MODEL`, через OpenRouter)
- `huggingface` — `HuggingFaceEmbeddings` (модель `HUGGINGFACE_EMBEDDING_MODEL`, локально на CPU)

Аналогично для RAGAS: `RAGAS_EMBEDDING_PROVIDER` + `RAGAS_EMBEDDING_MODEL` / `RAGAS_HUGGINGFACE_EMBEDDING_MODEL`.

## Подход к конфигурированию

Все настройки — только в `.env` через `config.py`. Нет YAML/JSON-конфигов, нет окружений dev/prod.

**Ключевые переменные:**

```bash
# LLM (OpenRouter)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=openai/gpt-oss-20b:free
MODEL_QUERY_TRANSFORM=openai/gpt-oss-20b:free

# Retrieval mode: semantic | hybrid | hybrid+reranker
RETRIEVAL_MODE=semantic

# Embeddings
EMBEDDING_PROVIDER=openai          # openai | huggingface
EMBEDDING_MODEL=text-embedding-3-large
HUGGINGFACE_EMBEDDING_MODEL=intfloat/multilingual-e5-base

# Semantic retriever
SEMANTIC_K=10

# BM25 retriever
BM25_K=10

# Hybrid (EnsembleRetriever)
HYBRID_SEMANTIC_WEIGHT=0.5
HYBRID_BM25_WEIGHT=0.5
HYBRID_K=10                      # итоговое k после ensemble

# Cross-Encoder reranker (для hybrid+reranker)
CROSS_ENCODER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKER_TOP_K=3

# Legacy (обратная совместимость, если не заданы SEMANTIC_K / HYBRID_K)
RETRIEVER_K=3

# RAGAS
RAGAS_LLM_MODEL=gpt-4o
RAGAS_EMBEDDING_PROVIDER=openai
RAGAS_EMBEDDING_MODEL=text-embedding-3-large
RAGAS_HUGGINGFACE_EMBEDDING_MODEL=intfloat/multilingual-e5-base

# Прочее
TELEGRAM_TOKEN=
DATA_DIR=data
SHOW_SOURCES=false
TOKENIZERS_PARALLELISM=false       # для HuggingFace на CPU

# LangSmith (опционально)
LANGSMITH_API_KEY=
LANGSMITH_TRACING_V2=false
LANGSMITH_PROJECT=06-rag-assistant
LANGSMITH_DATASET=05-rag-qa-dataset
```

**Принципы:**
- Все имена моделей (LLM, embedding, cross-encoder) — через env
- Раздельные настройки k и весов для semantic, BM25 и hybrid
- Секреты только в `.env`

## Подход к логгированию

Стандартный `logging` Python, вывод в stdout. Без structlog, файлов, внешних систем.

Логируем: старт/остановка, входящие сообщения, ошибки LLM/retrieval, режим retrieval при инициализации.

## Сценарии работы

**Диалог с RAG:**
1. Пользователь отправляет сообщение
2. Сообщение добавляется в историю
3. Query transformation формирует поисковый запрос из истории
4. Retriever (semantic / hybrid) находит чанки
5. При `hybrid+reranker` — cross-encoder переранжирует и обрезает до `RERANKER_TOP_K`
6. LLM генерирует ответ по контексту и истории
7. Ответ сохраняется в историю; при `SHOW_SOURCES=true` — блок источников

**Переиндексация (`/index`):** пересоздаёт vector store и BM25-индекс из чанков.

**Evaluation (`/evaluate_dataset`):** RAGAS-метрики; возможность сравнить режимы retrieval в LangSmith Experiments.
