import logging
import re

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from config import config
from retrieval import build_retriever
from reranker import rerank_documents
import indexer

logger = logging.getLogger(__name__)

_NOT_FOUND_PHRASE = "Я не нашел ответа на ваш вопрос в доступных документах"

# Глобальное векторное хранилище
vector_store = None
retriever = None

# Кеши для промптов и LLM клиентов
_conversational_answering_prompt = None
_retrieval_query_transform_prompt = None
_llm_query_transform = None
_llm = None

def _retrieve_documents(query: str):
    """Retrieval с опциональным reranking."""
    docs = retriever.invoke(query)
    if config.RETRIEVAL_MODE == "hybrid+reranker":
        return rerank_documents(query, docs, config.RERANKER_TOP_K)
    if config.RETRIEVAL_MODE == "semantic":
        return docs[: config.SEMANTIC_K]
    return docs[: config.HYBRID_K]


def initialize_retriever():
    """Инициализация retriever по RETRIEVAL_MODE."""
    global retriever
    if vector_store is None:
        logger.error("Cannot initialize retriever: vector_store is None")
        return False

    retriever = build_retriever(vector_store, indexer.chunks)
    logger.info("Retriever initialized: mode=%s", config.RETRIEVAL_MODE)
    return True

def format_chunks(chunks):
    """
    Форматирование чанков с метаданными для лучшей прозрачности
    """
    if not chunks:
        return "Нет доступной информации"
    
    formatted_parts = []
    for i, chunk in enumerate(chunks, 1):
        # Получаем метаданные
        source = chunk.metadata.get('source', 'Unknown')
        page = chunk.metadata.get('page', 'N/A')
        
        # Извлекаем имя файла из пути
        source_name = source.split('/')[-1] if '/' in source else source
        
        # Форматируем чанк
        formatted_parts.append(
            f"[Источник {i}: {source_name}, стр. {page}]\n{chunk.page_content}"
        )
    
    return "\n\n---\n\n".join(formatted_parts)


def format_sources(documents):
    """
    Компактное форматирование источников с группировкой страниц по файлам.
    Формат: "📚 Источники: file1.pdf (стр. 3, 5), file2.pdf (стр. 1)"
    """
    if not documents:
        return None

    sources_by_file = {}
    for doc in documents:
        source = doc.metadata.get("source", "Unknown")
        source_name = source.replace("\\", "/").split("/")[-1]
        page = doc.metadata.get("page", "N/A")

        if source_name not in sources_by_file:
            sources_by_file[source_name] = []
        if page != "N/A":
            sources_by_file[source_name].append(str(page))

    parts = []
    for filename, pages in sources_by_file.items():
        if pages:
            pages_str = ", ".join(sorted(set(pages), key=lambda x: int(x) if x.isdigit() else 0))
            parts.append(f"{filename} (стр. {pages_str})")
        else:
            parts.append(filename)

    return "📚 Источники: " + ", ".join(parts)


def _last_human_text(messages) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return ""


def _chunk_preview(text: str, max_len: int = 220) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "..."


def _extract_json_question(content: str) -> str | None:
    match = re.search(r"Вопрос:\s*(.+?)(?:\n\nОтвет:|\Z)", content, re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _chunk_label(chunk, index: int) -> str:
    source = chunk.metadata.get("source", "Unknown")
    source_name = source.replace("\\", "/").split("/")[-1]
    page = chunk.metadata.get("page", "—")
    seq = chunk.metadata.get("seq_num")
    json_q = _extract_json_question(chunk.page_content)
    parts = [f"#{index}", source_name, f"стр.{page}"]
    if seq is not None:
        parts.append(f"seq={seq}")
    if json_q:
        parts.append(f'Q="{json_q[:80]}{"..." if len(json_q) > 80 else ""}"')
    return " | ".join(parts)


def _log_similarity_ranking(label: str, query: str, top_k: int) -> None:
    if vector_store is None:
        return
    try:
        ranked = vector_store.similarity_search_with_score(query, k=top_k)
    except Exception as e:
        logger.warning("[RAG] similarity_search_with_score failed (%s): %s", label, e)
        return

    logger.info("[RAG] --- Similarity ranking: %s (top %d) ---", label, len(ranked))
    logger.info("[RAG] Query: %s", query)
    for i, (doc, score) in enumerate(ranked, 1):
        logger.info(
            "[RAG]   %d. score=%.4f | %s\n[RAG]       %s",
            i,
            score,
            _chunk_label(doc, i),
            _chunk_preview(doc.page_content),
        )


def _log_retriever_chunks(label: str, chunks) -> None:
    logger.info("[RAG] --- Retriever result: %s (%d chunks, k=%d) ---", label, len(chunks), config.RETRIEVER_K)
    if not chunks:
        logger.warning("[RAG] Retriever returned NO chunks")
        return
    for i, chunk in enumerate(chunks, 1):
        logger.info(
            "[RAG]   %d. %s\n[RAG]       %s",
            i,
            _chunk_label(chunk, i),
            _chunk_preview(chunk.page_content),
        )


def _log_question_match(user_question: str, chunks) -> None:
    q_lower = user_question.lower().strip()
    if not q_lower:
        return
    for i, chunk in enumerate(chunks, 1):
        content_lower = chunk.page_content.lower()
        json_q = _extract_json_question(chunk.page_content)
        if q_lower in content_lower:
            logger.info("[RAG] Match: user text found in chunk #%d body", i)
            return
        if json_q and (q_lower in json_q.lower() or json_q.lower() in q_lower):
            logger.info("[RAG] Match: user text similar to JSON question in chunk #%d", i)
            return
    logger.warning(
        "[RAG] No chunk contains the user question text — retrieval may have missed the right Q&A"
    )


def _log_rag_debug(user_question: str, search_query: str, chunks, context: str, answer: str) -> None:
    logger.info("=" * 60)
    logger.info("[RAG] DEBUG SESSION")
    logger.info("[RAG] User question: %s", user_question)
    logger.info("[RAG] Transformed search query: %s", search_query)
    if user_question.strip().lower() != search_query.strip().lower():
        logger.info("[RAG] Query was CHANGED by transform (check if this hurts exact Q&A match)")
    _log_retriever_chunks("used in prompt", chunks)
    _log_question_match(user_question, chunks)
    logger.info("[RAG] Context length: %d chars", len(context))
    logger.info("[RAG] Context preview:\n%s", context[:1200] + ("..." if len(context) > 1200 else ""))
    if _NOT_FOUND_PHRASE.lower() in answer.lower():
        logger.warning("[RAG] LLM returned 'not found' — see ranking above: wrong chunks or query transform?")
    else:
        logger.info("[RAG] LLM answer preview: %s", _chunk_preview(answer, 300))
    logger.info("=" * 60)


def _load_prompts():
    """Ленивая загрузка промптов с обработкой ошибок"""
    global _conversational_answering_prompt, _retrieval_query_transform_prompt
    
    if _conversational_answering_prompt is not None:
        return _conversational_answering_prompt, _retrieval_query_transform_prompt
    
    try:
        conversation_system_text = config.load_prompt(config.CONVERSATION_SYSTEM_PROMPT_FILE)
        query_transform_text = config.load_prompt(config.QUERY_TRANSFORM_PROMPT_FILE)
        
        _conversational_answering_prompt = ChatPromptTemplate(
            [
                ("system", conversation_system_text),
                ("placeholder", "{messages}")
            ]
        )
        
        _retrieval_query_transform_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("user", query_transform_text),
            ]
        )
        
        logger.info("Prompts loaded successfully")
        return _conversational_answering_prompt, _retrieval_query_transform_prompt
        
    except FileNotFoundError as e:
        logger.error(f"Prompt file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompts: {e}", exc_info=True)
        raise

def _get_llm_query_transform():
    """Ленивая инициализация LLM для query transformation с кешированием"""
    global _llm_query_transform
    if _llm_query_transform is None:
        _llm_query_transform = ChatOpenAI(
            model=config.MODEL_QUERY_TRANSFORM,
            temperature=0.4
        )
        logger.info(f"Query transform LLM initialized: {config.MODEL_QUERY_TRANSFORM}")
    return _llm_query_transform

def _get_llm():
    """Ленивая инициализация основной LLM с кешированием"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=config.MODEL,
            temperature=0.9
        )
        logger.info(f"Main LLM initialized: {config.MODEL}")
    return _llm

def get_retrieval_query_transformation_chain():
    """Цепочка трансформации запроса"""
    _, retrieval_query_transform_prompt = _load_prompts()
    return (
        retrieval_query_transform_prompt
        | _get_llm_query_transform()
        | StrOutputParser()
    )

def get_rag_chain():
    """Финальная RAG-цепочка, возвращающая answer и documents."""
    if retriever is None:
        raise ValueError("Retriever not initialized")

    conversational_answering_prompt, _ = _load_prompts()

    retrieve_step = (
        get_retrieval_query_transformation_chain()
        | RunnableLambda(_retrieve_documents)
    )

    return (
        RunnablePassthrough.assign(
            documents=retrieve_step
        )
        | RunnablePassthrough.assign(
            answer=lambda x: (conversational_answering_prompt | _get_llm() | StrOutputParser()).invoke(
                {
                    "context": format_chunks(x["documents"]),
                    "messages": x["messages"],
                }
            )
        )
        | (lambda x: {"answer": x["answer"], "documents": x["documents"]})
    )

async def rag_answer(messages):
    """
    Получить ответ от RAG с учетом истории диалога

    Returns:
        dict: {"answer": str, "documents": list[Document]}
    """
    if vector_store is None or retriever is None:
        logger.error("Vector store or retriever not initialized")
        raise ValueError("Векторное хранилище не инициализировано. Запустите индексацию.")

    user_question = _last_human_text(messages)

    if config.RAG_DEBUG:
        transform_chain = get_retrieval_query_transformation_chain()
        search_query = await transform_chain.ainvoke({"messages": messages})
        debug_k = max(config.RETRIEVER_K, config.RAG_DEBUG_TOP_K)
        _log_similarity_ranking("transformed query", search_query, debug_k)
        if user_question and user_question.strip() != search_query.strip():
            _log_similarity_ranking("original user question (no transform)", user_question, debug_k)

    rag_chain = get_rag_chain()
    result = await rag_chain.ainvoke({"messages": messages})

    if config.RAG_DEBUG:
        search_query = _last_human_text(messages)
        context = format_chunks(result["documents"])
        _log_rag_debug(user_question, search_query, result["documents"], context, result["answer"])

    return result

def get_vector_store_stats():
    """Возвращает статистику векторного хранилища"""
    if vector_store is None:
        return {"status": "not initialized", "count": 0}
    
    doc_count = len(vector_store.store) if hasattr(vector_store, 'store') else 0
    return {"status": "initialized", "count": doc_count}

