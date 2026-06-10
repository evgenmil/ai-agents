# Техническое видение проекта

## Технологии

**Основные технологии:**
- **Python 3.11+** — основной язык разработки
- **uv** — управление зависимостями и виртуальным окружением
- **aiogram 3.x** — Telegram Bot API (polling)
- **LangChain 1.0** — `create_agent()`, `@tool`, `MemorySaver`
- **langchain-openai** — ChatOpenAI, OpenAIEmbeddings через OpenRouter
- **langchain-community** — InMemoryVectorStore, BM25Retriever
- **langchain-huggingface** — HuggingFaceEmbeddings (локальные эмбеддинги)
- **openai** — клиент для работы с LLM через OpenRouter
- **sentence-transformers** — Cross-Encoder для reranking
- **rank-bm25** — BM25-индекс для keyword-поиска
- **pypdf** — загрузка и парсинг PDF-документов
- **python-dotenv** — переменные окружения
- **Make** — автоматизация сборки и запуска
- **langsmith** — трейсинг и evaluation в LangSmith
- **ragas** (>=0.2.0), **datasets** — batch-оценка качества RAG

**Референсы:**
- `docs/references/agent.ipynb` — обёртка `@tool`, `create_agent()`, streaming, системный промпт
- `docs/references/advanced-hybrid-rag.ipynb` — hybrid retrieval и reranker

## Принципы разработки

- **KISS** — максимальная простота решений
- **YAGNI** — только то, что нужно сейчас
- **Монолитная архитектура** — весь код в `src/`, без микросервисов
- **Модульность без оверинжиниринга** — отдельные файлы по зонам ответственности, без пакетов и DI

**Что НЕ делаем:** сложные паттерны, преждевременная оптимизация, функции «на будущее», лишние абстракции.

## Структура проекта

```
/
├── src/
│   ├── bot.py              # Точка входа, индексация при старте, polling
│   ├── handlers.py         # Telegram-команды и маршрутизация сообщений
│   ├── agent.py            # create_agent(), MemorySaver, agent_answer(), извлечение sources
│   ├── tools.py            # @tool rag_search
│   ├── retrieval.py        # Semantic / BM25 / Hybrid retriever
│   ├── reranker.py         # Cross-Encoder reranking
│   ├── embeddings.py       # Фабрика эмбеддингов (openai / huggingface)
│   ├── indexer.py          # Индексация PDF, vector store, чанки для BM25
│   ├── rag.py              # Вспомогательные функции: format_sources, documents → sources
│   ├── config.py           # Загрузка конфигурации из .env
│   ├── dataset_synthesizer.py
│   └── evaluation.py       # Async RAGAS evaluation через агента
├── data/
├── datasets/
├── prompts/
│   └── agent_system.txt    # Системный промпт агента (few-shot, инструкции по rag_search)
├── .env / .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

**Принцип:** плоская `src/` без пакетов. LCEL-цепочка RAG с query transformation **не используется** — поиск делегирован агенту через инструмент.

## Архитектура проекта

**Компоненты:**

1. **bot.py** — старт, индексация, инициализация retriever и агента, polling
2. **handlers.py** — `/start`, `/help`, `/index`, `/index_status`, `/evaluate_dataset`; передаёт сообщения в `agent_answer()`
3. **agent.py** — `create_agent(model, tools, system_prompt, checkpointer=MemorySaver())`; `agent_answer()` через `bank_agent.stream(..., stream_mode="values")`; логирование шагов; fallback при пустом `AIMessage`; `extract_sources_from_messages()` — sources только из `ToolMessage` с `rag_search` после последнего `HumanMessage`
4. **tools.py** — `rag_search(query: str) -> str`: retriever [→ reranker] → JSON `{"sources": [...]}` (`ensure_ascii=False`); каждый source: `source` (имя файла), `page_content` (полный текст), `page` (только для PDF)
5. **retrieval.py** — `build_retriever()` по `RETRIEVAL_MODE`
6. **reranker.py** — `rerank_documents()` для `hybrid+reranker`
7. **embeddings.py** — `get_embeddings()` по `EMBEDDING_PROVIDER`
8. **indexer.py** — PDF → chunks + vector store
9. **rag.py** — `format_sources()`, преобразование documents/sources для отображения в Telegram
10. **evaluation.py** — полностью async `evaluate_dataset()`; `target()` вызывает агента; `client.aevaluate()` + `async for result in experiment_results`; уникальный `thread_id` на каждый пример (изоляция в MemorySaver); contexts = `page_content` из documents

**Поток данных:**
```
Telegram → handlers.py →
agent_answer(thread_id=chat_id) →
  bank_agent.stream(stream_mode="values") →
    [ReAct: AIMessage + tool_calls → rag_search → ToolMessage → ... → финальный AIMessage]
→ extract_sources (текущий запрос) → handlers.py → Telegram
```

**Принцип:** прямые вызовы функций; глобальные `vector_store`, `chunks`, `retriever`, `bank_agent`; история диалога — в `MemorySaver`, не в ручном dict.

## Режимы retrieval

| Режим (`RETRIEVAL_MODE`) | Semantic | BM25 | Reranker |
|--------------------------|----------|------|----------|
| `semantic`               | ✓        | —    | —        |
| `hybrid`                 | ✓        | ✓    | —        |
| `hybrid+reranker`        | ✓        | ✓    | ✓        |

Режим влияет только на `rag_search` (внутри `tools.py` через `retrieval.py` / `reranker.py`). Агент не знает о режиме — переключение через `.env`.

## Модель данных

**История диалога:** `MemorySaver` + `thread_id` (= `chat_id` в Telegram, уникальный id в evaluation). При перезапуске бота in-memory checkpointer очищается.

**Индекс:** в памяти `vector_store` и `chunks` (для BM25).

**Формат `rag_search` → sources:**
```json
{
  "sources": [
    {
      "source": "credit_terms.pdf",
      "page_content": "полный текст чанка",
      "page": 3
    }
  ]
}
```
Поле `page` — только для PDF; для JSON и прочих источников опускается.

## Работа с LLM

**Провайдер:** OpenRouter (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`)

**Модели из .env:**
- `MODEL` — LLM агента (ReAct)

**Принцип:** `ChatOpenAI` в `create_agent()`; ответ через `stream(stream_mode="values")`; warning в лог при пустом `AIMessage` без `tool_calls`; обязательный fallback-текст для пользователя.

## Провайдеры эмбеддингов

Переключение через `EMBEDDING_PROVIDER`: `openai` | `huggingface`.  
Для RAGAS: `RAGAS_EMBEDDING_PROVIDER` + соответствующие модели.

## Подход к конфигурированию

Все настройки — только в `.env` через `config.py`.

**Ключевые переменные:**

```bash
# LLM (OpenRouter)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=openai/gpt-oss-20b:free

# Retrieval mode: semantic | hybrid | hybrid+reranker
RETRIEVAL_MODE=semantic

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
HUGGINGFACE_EMBEDDING_MODEL=intfloat/multilingual-e5-base

# Semantic / BM25 / Hybrid / Reranker
SEMANTIC_K=10
BM25_K=10
HYBRID_SEMANTIC_WEIGHT=0.5
HYBRID_BM25_WEIGHT=0.5
HYBRID_K=10
CROSS_ENCODER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKER_TOP_K=3

# RAGAS
RAGAS_LLM_MODEL=gpt-4o
RAGAS_EMBEDDING_PROVIDER=openai
RAGAS_EMBEDDING_MODEL=text-embedding-3-large
RAGAS_HUGGINGFACE_EMBEDDING_MODEL=intfloat/multilingual-e5-base

# Прочее
TELEGRAM_TOKEN=
DATA_DIR=data
SHOW_SOURCES=false
TOKENIZERS_PARALLELISM=false

# LangSmith (опционально)
LANGSMITH_API_KEY=
LANGSMITH_TRACING_V2=false
LANGSMITH_PROJECT=07-bank-agent
LANGSMITH_DATASET=05-rag-qa-dataset
```

`MODEL_QUERY_TRANSFORM` **не используется** — query transformation выполняет сам агент при вызове `rag_search`.

## Подход к логгированию

Стандартный `logging`, stdout. Логируем: старт, входящие сообщения, каждый шаг `bank_agent.stream()` (тип сообщения, tool_calls), warning при пустом ответе, ошибки retrieval/LLM.

## Сценарии работы

**Диалог с агентом:**
1. Пользователь отправляет сообщение
2. `agent_answer()` стримит граф с `thread_id=chat_id`
3. Агент при необходимости вызывает `rag_search(query)` с самостоятельно сформированной фразой
4. Инструмент возвращает JSON с sources; агент формирует ответ
5. Из state извлекаются sources текущего запроса; при `SHOW_SOURCES=true` — блок источников в Telegram

**Переиндексация (`/index`):** пересоздаёт vector store и BM25-индекс.

**Evaluation (`/evaluate_dataset`):** async прогон датасета через агента; каждый пример — свой `thread_id`; RAGAS contexts из `page_content`; метаданные `retrieval_mode` в LangSmith Experiments.

## Системный промпт агента

Файл `prompts/agent_system.txt`:
- роль: консультант Сбербанка
- когда вызывать `rag_search` (вопросы о продуктах, условиях, тарифах)
- когда не вызывать (приветствие, благодарность, уточнение без новых фактов)
- few-shot: 2–3 примера диалога с вызовом/без вызова инструмента
- подсказки: формулировать поисковый запрос конкретно, на русском, без лишних слов
