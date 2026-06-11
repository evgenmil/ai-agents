import logging
import os

from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from config import config

logger = logging.getLogger(__name__)

_embeddings: Embeddings | None = None


class LazyEmbeddings(Embeddings):
    """Прокси: реальная модель загружается при первом embed_query/embed_documents."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return get_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return get_embeddings().embed_query(text)


def get_lazy_embeddings() -> Embeddings:
    """Эмбеддинги без загрузки модели до первого запроса."""
    return LazyEmbeddings()


def get_embeddings():
    """Фабрика эмбеддингов для индексации и retrieval (singleton)."""
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    config.validate_embedding_provider(config.EMBEDDING_PROVIDER)

    if config.EMBEDDING_PROVIDER == "openai":
        logger.info("Using OpenAI embeddings: %s", config.EMBEDDING_MODEL)
        _embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL)
        return _embeddings

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    logger.info(
        "Using HuggingFace embeddings: %s (device=%s)",
        config.HUGGINGFACE_EMBEDDING_MODEL,
        config.HUGGINGFACE_DEVICE,
    )
    _embeddings = HuggingFaceEmbeddings(
        model_name=config.HUGGINGFACE_EMBEDDING_MODEL,
        model_kwargs={"device": config.HUGGINGFACE_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
    return _embeddings


def get_ragas_embeddings():
    """Фабрика эмбеддингов для RAGAS evaluation."""
    config.validate_embedding_provider(config.RAGAS_EMBEDDING_PROVIDER)

    if config.RAGAS_EMBEDDING_PROVIDER == "openai":
        logger.info("RAGAS OpenAI embeddings: %s", config.RAGAS_EMBEDDING_MODEL)
        return OpenAIEmbeddings(model=config.RAGAS_EMBEDDING_MODEL)

    logger.info(
        "RAGAS HuggingFace embeddings: %s",
        config.RAGAS_HUGGINGFACE_EMBEDDING_MODEL,
    )
    return HuggingFaceEmbeddings(
        model_name=config.RAGAS_HUGGINGFACE_EMBEDDING_MODEL,
        model_kwargs={"device": config.HUGGINGFACE_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
