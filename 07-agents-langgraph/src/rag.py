import logging

from langchain_core.documents import Document

from config import config
from retrieval import build_retriever
from reranker import rerank_documents
import indexer

logger = logging.getLogger(__name__)

vector_store = None
retriever = None


def retrieve_documents(query: str) -> list[Document]:
    """Retrieval с опциональным reranking по RETRIEVAL_MODE."""
    if retriever is None:
        raise ValueError("Retriever not initialized")

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


def _source_filename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def document_to_source(doc: Document) -> dict:
    source_path = doc.metadata.get("source", "Unknown")
    source_name = _source_filename(source_path)
    entry = {
        "source": source_name,
        "page_content": doc.page_content,
    }
    if source_name.lower().endswith(".pdf"):
        page = doc.metadata.get("page")
        if page is not None:
            entry["page"] = page
    return entry


def documents_to_sources(documents: list[Document]) -> list[dict]:
    return [document_to_source(doc) for doc in documents]


def sources_to_documents(sources: list[dict]) -> list[Document]:
    documents = []
    for item in sources:
        metadata = {"source": item.get("source", "Unknown")}
        if "page" in item:
            metadata["page"] = item["page"]
        documents.append(
            Document(page_content=item.get("page_content", ""), metadata=metadata)
        )
    return documents


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
        source_name = _source_filename(source)
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


def get_vector_store_stats():
    """Возвращает статистику векторного хранилища."""
    if vector_store is None:
        return {"status": "not initialized", "count": 0}

    doc_count = len(vector_store.store) if hasattr(vector_store, "store") else 0
    return {"status": "initialized", "count": doc_count}
