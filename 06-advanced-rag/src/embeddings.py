import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from config import config

logger = logging.getLogger(__name__)


def get_embeddings():
    """Фабрика эмбеддингов для индексации и retrieval."""
    config.validate_embedding_provider(config.EMBEDDING_PROVIDER)

    if config.EMBEDDING_PROVIDER == "openai":
        logger.info("Using OpenAI embeddings: %s", config.EMBEDDING_MODEL)
        return OpenAIEmbeddings(model=config.EMBEDDING_MODEL)

    logger.info(
        "Using HuggingFace embeddings: %s (device=%s)",
        config.HUGGINGFACE_EMBEDDING_MODEL,
        config.HUGGINGFACE_DEVICE,
    )
    return HuggingFaceEmbeddings(
        model_name=config.HUGGINGFACE_EMBEDDING_MODEL,
        model_kwargs={"device": config.HUGGINGFACE_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )


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
