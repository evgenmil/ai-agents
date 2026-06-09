# План разработки RAG-ассистента на базе LangChain

## 📊 Отчет о прогрессе

| Спринт | Итерация | Функционал | Статус | Дата |
|--------|----------|------------|--------|------|
| 1 | 1 | Базовый эхо-бот с конфигурацией | ✅ Завершено | 28.10.2025 |
| 1 | 2 | Интеграция с LLM | ✅ Завершено | 28.10.2025 |
| 1 | 3 | История диалогов | ✅ Завершено | 28.10.2025 |
| 1 | 4 | Финальная полировка | ✅ Завершено | 28.10.2025 |
| 2 | 5 | Индексация PDF с командами управления | ✅ Завершено | 07.11.2025 |
| 2 | 6 | Полноценный RAG с query transformation | ✅ Завершено | 07.11.2025 |
| 2 | 7 | Финальная полировка и документация | ✅ Завершено | 07.11.2025 |
| HW | HW-1 | Эксперименты с чанкингом PDF (ДЗ модуля 4) | ✅ Завершено | — |
| HW | HW-2 | JSONLoader + объединённая индексация PDF + JSON | ✅ Завершено | — |
| HW | HW-3 | Сравнение моделей эмбеддингов (OpenRouter / опционально Ollama) | ✅ Завершено | — |
| 3 | 8 | Рефакторинг RAG с отображением источников | ✅ Завершено | 02.06.2026 |
| 3 | 9 | Синтез тестовых датасетов | ✅ Завершено | 02.06.2026 |
| 3 | 10 | Система оценки качества через RAGAS | ✅ Завершено | 02.06.2026 |
| 3 | 11 | Финальная полировка и документация | ✅ Завершено | 02.06.2026 |
| ДЗ-5 | 1 | Настройка мониторинга и проверка трейсинга | ⏳ Не начато | — |
| ДЗ-5 | 2 | Создание и загрузка датасета | ⏳ Не начато | — |
| ДЗ-5 | 3 | Evaluation и анализ метрик | ⏳ Не начато | — |
| ДЗ-6 | 1 | Зависимости и расширенная конфигурация | ✅ Завершено | 08.06.2026 |
| ДЗ-6 | 2 | Модуль эмбеддингов и провайдеры | ✅ Завершено | 08.06.2026 |
| ДЗ-6 | 3 | Hybrid retrieval (Semantic + BM25) | ✅ Завершено | 08.06.2026 |
| ДЗ-6 | 4 | Cross-Encoder reranker | ✅ Завершено | 08.06.2026 |
| ДЗ-6 | 5 | Интеграция в RAG-цепочку и evaluation | ✅ Завершено | 08.06.2026 |
| ДЗ-6 | 6 | Финальная полировка и документация | ✅ Завершено | 08.06.2026 |

**Легенда статусов:**
- ⏳ Не начато
- 🚧 В работе
- ✅ Завершено
- ❌ Заблокировано

---

## 🚀 Спринт 1: Базовый LLM-бот (Завершено)

### Итерация 1: Базовый эхо-бот с конфигурацией

**Цель:** Запустить простейшего Telegram бота с конфигурацией через .env

- [x] Создать `pyproject.toml` с зависимостями: aiogram, openai, python-dotenv
- [x] Создать структуру папок: `src/`
- [x] Создать `.env.example` с шаблоном переменных
- [x] Создать `.gitignore` (`.env`, `__pycache__`, `.venv`)
- [x] Создать `Makefile` с командами: `install`, `run`
- [x] Создать базовый `README.md` с инструкцией по запуску
- [x] Создать `src/config.py` с классом Config и загрузкой из .env
- [x] Создать `src/bot.py` с инициализацией Bot и Dispatcher
- [x] Создать `src/handlers.py` с обработчиками `/start` и эхо-ответов
- [x] Добавить базовое логирование (старт бота, входящие сообщения)

---

### Итерация 2: Интеграция с LLM

**Цель:** Заменить эхо на реальные ответы от LLM

- [x] Создать `src/llm.py` с функцией `get_response(messages: list) -> str`
- [x] Инициализировать AsyncOpenAI клиент с настройками из config
- [x] Обработать ошибки при вызове LLM (try/except)
- [x] Обновить обработчик сообщений: отправлять запрос в LLM

---

### Итерация 3: История диалогов

**Цель:** Добавить контекст диалога

- [x] Создать глобальный словарь `chat_conversations`
- [x] При `/start` инициализировать историю с системным промптом
- [x] Передавать всю историю в LLM/RAG

---

### Итерация 4: Финальная полировка

**Цель:** Довести бота до production-ready состояния

- [x] Улучшить сообщения об ошибках
- [x] Обновить README.md

---

## 🚀 Спринт 2: RAG-ассистент на базе LangChain (Завершено)

### Итерация 5: Индексация PDF с командами управления

- [x] `indexer.py`, векторное хранилище, команды `/index`, `/index_status`

### Итерация 6: Полноценный RAG с query transformation

- [x] `rag.py`: цепочки, промпты, `rag_answer()`

### Итерация 7: Финальная полировка и документация

- [x] `/help`, логи в файл, README, `RETRIEVER_K`

---

## HW Спринт: домашнее задание (модуль 4, завершено)

### HW-1: Эксперименты с чанкингом PDF

- [x] Сравнение `chunk_size` / `chunk_overlap`, выводы в `report.md`

### HW-2: JSON-датасет (вопросы про карты)

- [x] `JSONLoader`, объединённая индексация в `indexer_with_json.py`

### HW-3: Модели эмбеддингов

- [x] Сравнение конфигураций эмбеддингов, наблюдения в отчёте

---

## 🚀 Спринт 3: Мониторинг и оценка качества RAG (Завершено)

### Итерация 8: Рефакторинг RAG с отображением источников

**Цель:** RAG возвращает `answer` + `documents`, опционально показывает источники, LangSmith через env

- [x] `get_rag_chain()` → dict с `answer` и `documents`
- [x] `format_sources(documents)` — «📚 Источники: file.pdf (стр. 1, 3)»
- [x] `SHOW_SOURCES`, `LANGSMITH_*` в `config.py` и `.env.example`
- [x] Зависимость `langsmith` в `pyproject.toml`

---

### Итерация 9: Синтез тестовых датасетов

**Цель:** `dataset_synthesizer.py` — 2 чанка на PDF, Q&A из JSON, сохранение и upload

- [x] `src/dataset_synthesizer.py` (PDF + JSON, LangSmith upload)
- [x] `datasets/05-rag-qa-dataset.json`
- [x] `make dataset`, `make dataset-upload`

---

### Итерация 10: Система оценки качества через RAGAS

**Цель:** `/evaluate_dataset`, 6 метрик RAGAS, feedback в LangSmith

- [x] `src/evaluation.py` (эксперимент → RAGAS batch → feedback)
- [x] Метрики: faithfulness, answer_relevancy, answer_correctness, answer_similarity, context_recall, context_precision
- [x] Команда `/evaluate_dataset` в `handlers.py`
- [x] Зависимости: `ragas>=0.2.0`, `datasets`

---

### Итерация 11: Финальная полировка и документация

- [x] Обновлены `docs/idea.md`, `docs/vision.md`, `.cursor/rules/conventions.mdc`
- [x] `RAGAS_LLM_MODEL`, `RAGAS_EMBEDDING_MODEL` в конфиге

---

## 🏠 Спринт ДЗ-5: Домашнее задание (мониторинг и evaluation)

### ДЗ-5: Итерация 1 — Настройка мониторинга и проверка трейсинга

**Цель:** Настроить LangSmith, проверить отображение источников и трейсы в UI

- [ ] Создать аккаунт на [smith.langchain.com](https://smith.langchain.com) и получить API-ключ
- [ ] Настроить `.env`: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING_V2=true`, `LANGSMITH_PROJECT=05-rag-assistant`
- [ ] Установить `SHOW_SOURCES=true`, перезапустить бота, проверить источники в ответах
- [ ] Задать несколько вопросов, убедиться что traces видны в LangSmith

---

### ДЗ-5: Итерация 2 — Создание и загрузка датасета

**Цель:** Сгенерировать Q&A датасет и загрузить в LangSmith

- [ ] Запустить `make dataset` — создаётся `datasets/05-rag-qa-dataset.json`
- [ ] Проверить/отредактировать вопросы и ответы (минимум 6 пар)
- [ ] Запустить `make dataset-upload` — датасет в LangSmith → Datasets & Experiments

---

### ДЗ-5: Итерация 3 — Evaluation и анализ метрик

**Цель:** RAGAS evaluation, изучить 6 метрик, зафиксировать результаты

- [ ] Отправить боту `/evaluate_dataset`, дождаться результатов
- [ ] LangSmith → Datasets → `05-rag-qa-dataset` → Experiments
- [ ] Изучить faithfulness, answer_relevancy, answer_correctness, answer_similarity, context_recall, context_precision
- [ ] Скриншот Experiments для отчёта

---

## 🚀 Спринт ДЗ-6: Advanced RAG (Hybrid Retrieval + Reranking)

Референс: `docs/references/advanced-hybrid-rag.ipynb`. Сохранить query transformation по истории диалога. LCEL-стиль.

### ДЗ-6: Итерация 1 — Зависимости и расширенная конфигурация

**Цель:** Подготовить зависимости и env-переменные для трёх режимов retrieval

- [x] Добавить в `pyproject.toml`: `sentence-transformers`, `rank-bm25`, `langchain-huggingface`, `langchain-classic`
- [x] Расширить `config.py`: `RETRIEVAL_MODE`, `EMBEDDING_PROVIDER`, `RAGAS_EMBEDDING_PROVIDER`
- [x] Раздельные настройки: `SEMANTIC_K`, `BM25_K`, `HYBRID_K`, `HYBRID_SEMANTIC_WEIGHT`, `HYBRID_BM25_WEIGHT`
- [x] Модели через env: `EMBEDDING_MODEL`, `HUGGINGFACE_EMBEDDING_MODEL`, `CROSS_ENCODER_MODEL`, `RERANKER_TOP_K`
- [x] Обновить `env.example`

**Тест:** `make install`, проект стартует с `RETRIEVAL_MODE=semantic` (поведение как раньше)

---

### ДЗ-6: Итерация 2 — Модуль эмбеддингов и провайдеры

**Цель:** Фабрика эмбеддингов OpenAI / HuggingFace

- [x] Создать `src/embeddings.py` с `get_embeddings()` по `EMBEDDING_PROVIDER`
- [x] OpenAI: `OpenAIEmbeddings` через OpenRouter
- [x] HuggingFace: `HuggingFaceEmbeddings` (CPU, `normalize_embeddings=True`)
- [x] Подключить в `indexer.py` вместо прямого `OpenAIEmbeddings`
- [x] Аналогичная фабрика для RAGAS-эмбеддингов в `evaluation.py`

**Тест:** переиндексация с `EMBEDDING_PROVIDER=openai` и `huggingface`, бот отвечает

---

### ДЗ-6: Итерация 3 — Hybrid retrieval (Semantic + BM25)

**Цель:** Гибридный поиск по примеру Part 1 тетрадки

- [x] Создать `src/retrieval.py`
- [x] `indexer.py`: сохранять `chunks` глобально (нужны для BM25)
- [x] Semantic retriever с `SEMANTIC_K`
- [x] `BM25Retriever.from_documents(chunks)` с `BM25_K`
- [x] `EnsembleRetriever` с весами `HYBRID_SEMANTIC_WEIGHT` / `HYBRID_BM25_WEIGHT`
- [x] `build_retriever(mode)` — выбор по `RETRIEVAL_MODE` (`semantic` | `hybrid` | `hybrid+reranker`)

**Тест:** `RETRIEVAL_MODE=hybrid`, вопрос с точным термином из PDF — релевантные чанки в контексте

---

### ДЗ-6: Итерация 4 — Cross-Encoder reranker

**Цель:** Reranking по примеру Part 2 тетрадки

- [x] Создать `src/reranker.py`: `rerank_documents(query, documents, top_k)` через `CrossEncoder`
- [x] Модель из `CROSS_ENCODER_MODEL`, `top_k` из `RERANKER_TOP_K`
- [x] Режим `hybrid+reranker` — отдельный шаг в `_retrieve_documents()`

**Тест:** `RETRIEVAL_MODE=hybrid+reranker`, reranker сужает список до `RERANKER_TOP_K` чанков

---

### ДЗ-6: Итерация 5 — Интеграция в RAG-цепочку и evaluation

**Цель:** Собрать LCEL-пайплайн с сохранением query transformation

- [x] Обновить `rag.py`: `get_rag_chain()` — transform → retriever [→ reranker] → LLM
- [x] `initialize_retriever()` использует `retrieval.build_retriever()`
- [x] Уточняющие вопросы по-прежнему проходят через `retrieval_query_transformation_chain`
- [x] `evaluation.py`: метаданные `retrieval_mode` в LangSmith Experiments

**Тест:** все три режима (`semantic`, `hybrid`, `hybrid+reranker`) отвечают в Telegram; query transform работает на уточняющих вопросах

---

### ДЗ-6: Итерация 6 — Финальная полировка и документация

**Цель:** Документация, сравнение режимов, README

- [x] Обновить `README.md`: режимы retrieval, env-переменные, примеры конфигурации
- [ ] Сравнить режимы через `/evaluate_dataset` (ручной прогон с разными `RETRIEVAL_MODE`)
- [ ] Проверить `SHOW_SOURCES`, LangSmith traces для hybrid/reranker
- [x] Актуализировать `docs/idea.md`, `docs/vision.md`, `.cursor/rules/conventions.mdc`

**Тест:** полный прогон бота; зафиксировать наблюдения по метрикам RAGAS для отчёта

---

## 📝 Заметки

После завершения каждой итерации:
1. Обновить статус в таблице прогресса
2. Протестировать бота
3. Закоммитить изменения
4. Переходить к следующей итерации только после успешного теста
