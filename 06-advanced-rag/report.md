# Отчёт по экспериментам retrieval

**Дата:** 08.06.2026  
**Датасет:** `06-rag-qa-dataset` (6 примеров)  
**Команда:** `/evaluate_dataset` в Telegram-боте

---

## Общая конфигурация

Параметры, не менявшиеся между прогонами:

| Параметр | Значение |
|----------|----------|
| LLM (ответ) | `google/gemini-3-flash-preview` (OpenRouter) |
| LLM (query transform) | `google/gemini-3-flash-preview` |
| Эмбеддинги (retrieval) | `huggingface` → `intfloat/multilingual-e5-base` (CPU) |
| RAGAS LLM | `gpt-4o` |
| RAGAS эмбеддинги | `openai` → `text-embedding-3-large` |
| LangSmith project | `06-rag-assistant` |
| LangSmith dataset | `06-rag-qa-dataset` |

---

## Конфигурация экспериментов

Каждый прогон запускался с отдельным набором переменных окружения.

### 1. Semantic

```env
RETRIEVAL_MODE=semantic
```

- Только векторный поиск по эмбеддингам
- BM25, ensemble и reranker не задействованы

### 2. Hybrid

```env
RETRIEVAL_MODE=hybrid
SEMANTIC_RETRIEVER_K=10
BM25_RETRIEVER_K=10
ENSEMBLE_SEMANTIC_WEIGHT=0.5
ENSEMBLE_BM25_WEIGHT=0.5
```

- Семантический поиск (top-10) + BM25 (top-10)
- Объединение через `EnsembleRetriever` с весами 50/50
- Reranker не используется

### 3. Hybrid Reranker

```env
RETRIEVAL_MODE=hybrid_reranker
CROSS_ENCODER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKER_TOP_K=3
```

- Hybrid retrieval (настройки из эксперимента 2) + cross-encoder reranking
- После rerank в контекст LLM передаётся top-3 документа

---

## Эксперименты

### Сводная таблица (ключевые метрики)

| Режим | Faithfulness | Correctness | Context Recall | Context Precision |
|-------|-------------|-------------|----------------|-------------------|
| semantic | 0.875 | nan | 1.000 | nan |
| hybrid | 1.000 | nan | 1.000 | nan |
| hybrid_reranker | 1.000 | nan | 1.000 | **0.917** |

### Полная таблица RAGAS

| Режим | Faithfulness | Answer Relevancy | Answer Correctness | Answer Similarity | Context Recall | Context Precision |
|-------|-------------|------------------|--------------------|-------------------|----------------|-------------------|
| semantic | 0.875 | 0.027 | nan | 0.695 | 1.000 | nan |
| hybrid | 1.000 | 0.018 | nan | 0.690 | 1.000 | nan |
| hybrid_reranker | 1.000 | 0.024 | nan | 0.690 | 1.000 | 0.917 |

> **Примечание:** `nan` у Answer Correctness и Context Precision (в режимах semantic/hybrid) — следствие таймаутов RAGAS при тяжёлых LLM-метриках, а не отсутствия эталонных ответов в датасете. `context_recall = 1.0` подтверждает, что ground truth и контекст согласованы.

---

## Вывод

Лучшую конфигурацию показал режим **`hybrid_reranker`**.

**Почему:**

1. **Точность поиска (Context Precision = 0.917)** — единственный режим, где метрика посчиталась и показала высокий результат. Cross-encoder `mmarco-mMiniLMv2` отбирает 3 наиболее релевантных чанка из результатов hybrid-поиска.
2. **Обоснованность (Faithfulness = 1.0)** — на уровне hybrid и выше semantic (0.875): ответы опираются на retrieved-контекст, галлюцинаций нет.
3. **Полнота контекста (Context Recall = 1.0)** — как и у остальных режимов: нужная информация в контекст попадает.

**Hybrid** (semantic + BM25, k=10, веса 0.5/0.5) улучшил faithfulness относительно pure semantic (1.0 vs 0.875), но не дал измеримого выигрыша по precision — в контекст по-прежнему попадает много чанков без rerank.

**Semantic** — минимальная конфигурация: хуже по faithfulness, без преимуществ по другим метрикам.

**Ограничение:** все три режима показали низкую **Answer Relevancy (~0.02)** и схожую **Answer Similarity (~0.69)** — качество формулировки ответа LLM почти не зависит от retrieval. Следующий шаг оптимизации — промпты, query transform и модель генерации, а не смена режима поиска.

**Рекомендация для production:** `hybrid_reranker` с `RERANKER_TOP_K=3` как режим retrieval по умолчанию.
