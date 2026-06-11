# Техническое видение проекта

## Технологии

**Основные технологии:**
- **Python 3.11+** — основной язык разработки
- **uv** — управление зависимостями и виртуальным окружением
- **aiogram 3.x** — Telegram Bot API (polling)
- **LangChain 1.0** — `create_agent()`, `@tool`, `MemorySaver`
- **langchain-mcp-adapters** — `MultiServerMCPClient`, подключение MCP-инструментов к агенту
- **FastMCP** — MCP-сервер `mcp-bank-agent` (streamable-http)
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

**Внешние API:**
- **ExchangeRate-API** (`open.er-api.com`) — `currency_convert` (без ключа)
- **API Ninjas Mortgage Calculator** (`api.api-ninjas.com`) — `loan_calc` (ключ `API_NINJAS_KEY`; без ключа — локальная аннуитетная формула)

**Референсы:**
- `docs/references/agent.ipynb` — обёртка `@tool`, `create_agent()`, streaming, системный промпт
- `docs/references/advanced-hybrid-rag.ipynb` — hybrid retrieval и reranker
- `slides/notebook/09-mcp/agent-mcp.ipynb` — раздел «Агент с MCP инструментами»

## Принципы разработки

- **KISS** — максимальная простота решений
- **YAGNI** — только то, что нужно сейчас
- **Монолитная архитектура** — код агента в `src/`, MCP-сервер — отдельный подпроект в `mcp/`
- **Модульность без оверинжиниринга** — отдельные файлы по зонам ответственности, без пакетов и DI
- **Graceful degradation** — агент работает без MCP при недоступности сервера

**Что НЕ делаем:** сложные паттерны, преждевременная оптимизация, функции «на будущее», лишние абстракции.

## Структура проекта

```
/
├── src/
│   ├── bot.py              # Точка входа, индексация при старте, polling
│   ├── handlers.py         # Telegram-команды и маршрутизация сообщений
│   ├── agent.py            # create_bank_agent(), initialize_agent() (async), MCP-клиент
│   ├── tools.py            # @tool rag_search, currency_convert
│   ├── retrieval.py        # Semantic / BM25 / Hybrid retriever
│   ├── reranker.py         # Cross-Encoder reranking
│   ├── embeddings.py       # Фабрика эмбеддингов (openai / huggingface)
│   ├── indexer.py          # Индексация PDF, vector store, чанки для BM25
│   ├── rag.py              # format_sources, documents → sources
│   ├── config.py           # Загрузка конфигурации из .env
│   ├── dataset_synthesizer.py
│   └── evaluation.py       # Async RAGAS evaluation через агента
├── mcp/
│   └── mcp-bank-agent/     # MCP-сервер (отдельный uv-проект)
│       ├── server.py       # FastMCP: search_products, loan_calc
│       ├── data/
│       │   └── bank_products.json
│       └── pyproject.toml
├── data/
├── datasets/
├── prompts/
│   └── agent_system.txt    # Системный промпт (rag_search, search_products, loan_calc, currency_convert)
├── .env / .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

**Принцип:** плоская `src/` без пакетов. LCEL-цепочка RAG с query transformation **не используется** — поиск делегирован агенту через инструмент.

## Архитектура проекта

**Компоненты:**

1. **bot.py** — старт, индексация, `await initialize_agent()`, polling
2. **handlers.py** — `/start`, `/help`, `/index`, `/index_status`, `/evaluate_dataset`; передаёт сообщения в `agent_answer()`
3. **agent.py** — `async create_bank_agent()`, `async initialize_agent()`; `MultiServerMCPClient.get_tools()`; `create_agent(model, tools, system_prompt, checkpointer=MemorySaver())`; graceful degradation при ошибке MCP; `agent_answer()` через `bank_agent.stream(..., stream_mode="values")`; `extract_sources_from_messages()` — sources только из `rag_search` после последнего `HumanMessage`
4. **tools.py** — `rag_search(query)` → JSON `{"sources": [...]}`; `currency_convert(amount, from, to)` → JSON с курсом
5. **mcp/mcp-bank-agent/server.py** — FastMCP streamable-http на порту 8000:
   - `search_products(query, product_type)` — поиск по `bank_products.json`
   - `loan_calc(loan_amount, interest_rate, term_months)` — расчёт через API Ninjas
6. **retrieval.py** — `build_retriever()` по `RETRIEVAL_MODE`
7. **reranker.py** — `rerank_documents()` для `hybrid+reranker`
8. **embeddings.py** — `get_embeddings()` по `EMBEDDING_PROVIDER`
9. **indexer.py** — PDF → chunks + vector store
10. **evaluation.py** — полностью async `evaluate_dataset()`; уникальный `thread_id` на пример; contexts = `page_content`

**Поток данных:**
```
Telegram → handlers.py →
agent_answer(thread_id=chat_id) →
  bank_agent.stream(stream_mode="values") →
    [ReAct: AIMessage + tool_calls →
      rag_search | currency_convert | search_products | loan_calc →
      ToolMessage → ... → финальный AIMessage]
→ extract_sources (rag_search, текущий запрос) → handlers.py → Telegram
```

**MCP-подключение (при старте бота):**
```
initialize_agent() →
  MultiServerMCPClient({bank-agent: streamable_http, url}) →
  mcp_tools = await client.get_tools() →
  tools = [rag_search, currency_convert] + mcp_tools →
  create_agent(...)
```

При ошибке MCP: warning в лог, `tools = [rag_search, currency_convert]`.

**Принцип:** прямые вызовы функций; глобальные `vector_store`, `chunks`, `retriever`, `bank_agent`; история диалога — в `MemorySaver`.

## Инструменты агента

| Инструмент | Источник | Назначение |
|------------|----------|------------|
| `rag_search` | `src/tools.py` | Поиск в PDF/JSON документах: процедуры, правила, условия из документов |
| `currency_convert` | `src/tools.py` | Конвертация валют по актуальному курсу |
| `search_products` | MCP `mcp-bank-agent` | Актуальные ставки, акции, каталог продуктов |
| `loan_calc` | MCP `mcp-bank-agent` | Расчёт платежа и переплаты по кредиту |

**Разграничение `rag_search` vs `search_products`:**
- `rag_search` — статичные документы (PDF, JSON в `data/`): процедуры, правила, порядок оформления
- `search_products` — динамический каталог (`bank_products.json`): текущие ставки, акции, лимиты, сравнение продуктов

## Режимы retrieval

| Режим (`RETRIEVAL_MODE`) | Semantic | BM25 | Reranker |
|--------------------------|----------|------|----------|
| `semantic`               | ✓        | —    | —        |
| `hybrid`                 | ✓        | ✓    | —        |
| `hybrid+reranker`        | ✓        | ✓    | ✓        |

Режим влияет только на `rag_search`. Агент не знает о режиме — переключение через `.env`.

## Модель данных

**История диалога:** `MemorySaver` + `thread_id` (= `chat_id` в Telegram, уникальный id в evaluation).

**Индекс:** в памяти `vector_store` и `chunks` (для BM25).

**Каталог продуктов MCP** (`bank_products.json`):
```json
{
  "products": [{
    "id": "...",
    "type": "вклад|кредит|дебетовая карта|кредитная карта|счёт",
    "name": "...",
    "description": "...",
    "rate_min": 13.0,
    "rate_max": 13.5,
    "conditions": ["..."],
    "promotions": ["..."],
    "tags": ["..."]
  }]
}
```

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

## Работа с LLM

**Провайдер:** OpenRouter (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`)

**Модели из .env:**
- `MODEL` — LLM агента (ReAct)

**Принцип:** `ChatOpenAI` в `create_agent()`; ответ через `stream(stream_mode="values")`; fallback при пустом `AIMessage`.

## Подход к конфигурированию

Все настройки — только в `.env` через `config.py`.

**Ключевые переменные:**

```bash
# LLM (OpenRouter)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=openai/gpt-oss-20b:free

# MCP bank-agent server
MCP_BANK_URL=http://localhost:8000/mcp

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

# Прочее
TELEGRAM_TOKEN=
DATA_DIR=data
SHOW_SOURCES=false
TOKENIZERS_PARALLELISM=false

# LangSmith (опционально)
LANGSMITH_API_KEY=
LANGSMITH_TRACING_V2=false
LANGSMITH_PROJECT=08-mcp-bank-agent
LANGSMITH_DATASET=05-rag-qa-dataset
```

**Переменные MCP-сервера** (`mcp/mcp-bank-agent`, опционально):
```bash
API_NINJAS_KEY=          # Бесплатный ключ с api-ninjas.com для loan_calc
MCP_PORT=8000
MCP_HOST=0.0.0.0
```

## Подход к логгированию

Стандартный `logging`, stdout. Логируем: старт, входящие сообщения, каждый шаг `bank_agent.stream()`, warning при недоступности MCP, warning при пустом ответе, ошибки retrieval/LLM.

## Сценарии работы

**Диалог с агентом:**
1. Пользователь отправляет сообщение
2. `agent_answer()` стримит граф с `thread_id=chat_id`
3. Агент выбирает инструмент: `rag_search`, `search_products`, `loan_calc` или `currency_convert`
4. Инструмент возвращает JSON; агент формирует ответ
5. Sources из `rag_search` извлекаются для отображения; при `SHOW_SOURCES=true` — блок источников

**Запуск с MCP:**
1. Terminal 1: `make run-mcp-bank` (порт 8000)
2. Terminal 2: `make run` (бот подключается к MCP, загружает инструменты)

**Запуск без MCP:** только `make run` — бот работает с `rag_search` и `currency_convert`.

**Переиндексация (`/index`):** пересоздаёт vector store и BM25-индекс.

**Evaluation (`/evaluate_dataset`):** async прогон датасета через агента; contexts из `page_content` `rag_search`.

## Системный промпт агента

Файл `prompts/agent_system.txt`:
- роль: консультант Сбербанка
- разграничение инструментов: `rag_search` vs `search_products` vs `loan_calc` vs `currency_convert`
- few-shot: 2–3 примера диалога с вызовом/без вызова инструментов
- подсказки по формулировке запросов
