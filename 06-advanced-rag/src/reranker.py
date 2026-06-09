import logging
import os

from config import config

logger = logging.getLogger(__name__)

_cross_encoder = None


def get_cross_encoder():
    """Ленивая инициализация Cross-Encoder."""
    global _cross_encoder
    if _cross_encoder is None:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from sentence_transformers import CrossEncoder

        logger.info("Loading Cross-Encoder: %s", config.CROSS_ENCODER_MODEL)
        _cross_encoder = CrossEncoder(config.CROSS_ENCODER_MODEL)
    return _cross_encoder


def rerank_documents(query: str, documents: list, top_k: int | None = None) -> list:
    """Переранжирование документов cross-encoder'ом."""
    if not documents:
        return documents

    top_k = top_k or config.RERANKER_TOP_K
    cross_encoder = get_cross_encoder()
    pairs = [[query, doc.page_content] for doc in documents]
    scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked[:top_k]]
