import logging

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from config import config

logger = logging.getLogger(__name__)


def _semantic_retriever(vector_store):
    return vector_store.as_retriever(search_kwargs={"k": config.SEMANTIC_K})


def _bm25_retriever(chunks):
    retriever = BM25Retriever.from_documents(chunks)
    retriever.k = config.BM25_K
    return retriever


def _hybrid_retriever(vector_store, chunks):
    semantic = _semantic_retriever(vector_store)
    bm25 = _bm25_retriever(chunks)
    logger.info(
        "Hybrid retriever: semantic_k=%d, bm25_k=%d, weights=[%.2f, %.2f]",
        config.SEMANTIC_K,
        config.BM25_K,
        config.HYBRID_SEMANTIC_WEIGHT,
        config.HYBRID_BM25_WEIGHT,
    )
    return EnsembleRetriever(
        retrievers=[semantic, bm25],
        weights=[config.HYBRID_SEMANTIC_WEIGHT, config.HYBRID_BM25_WEIGHT],
    )


def build_retriever(vector_store, chunks):
    """Построение retriever по RETRIEVAL_MODE."""
    config.validate_retrieval_mode()

    if vector_store is None:
        raise ValueError("vector_store is not initialized")

    mode = config.RETRIEVAL_MODE

    if mode == "semantic":
        logger.info("Retrieval mode: semantic (k=%d)", config.SEMANTIC_K)
        return _semantic_retriever(vector_store)

    if not chunks:
        raise ValueError("chunks required for hybrid retrieval modes")

    if mode in ("hybrid", "hybrid+reranker"):
        logger.info("Retrieval mode: %s", mode)
        return _hybrid_retriever(vector_store, chunks)

    raise ValueError(f"Unsupported RETRIEVAL_MODE: {mode}")
