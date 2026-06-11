import logging
from pathlib import Path

from langchain_community.document_loaders import JSONLoader

from config import config
from indexer import (
    create_vector_store,
    load_pdf_documents,
    split_documents,
    try_load_cached_index,
)

logger = logging.getLogger(__name__)


def load_json_documents(json_file_path: str) -> list:
    """Загрузка Q&A из JSON: каждый full_text — отдельный документ без чанкинга."""
    json_path = Path(json_file_path)
    if not json_path.exists():
        logger.warning(f"JSON file {json_file_path} does not exist")
        return []

    loader = JSONLoader(
        file_path=str(json_path),
        jq_schema=".[].full_text",
        text_content=False,
    )
    documents = loader.load()
    logger.info(f"Loaded {len(documents)} Q&A pairs from JSON")
    if documents:
        sample = documents[0]
        logger.info(
            "JSON sample metadata: %s | content preview: %.120s...",
            sample.metadata,
            sample.page_content.replace("\n", " "),
        )
    return documents


async def reindex_all():
    """Полная переиндексация: PDF с чанкингом + JSON без чанкинга."""
    logger.info("Starting full reindexing...")

    cached = try_load_cached_index()
    if cached:
        vector_store, _ = cached
        return vector_store

    try:
        pdf_pages = load_pdf_documents(config.DATA_DIR)
        pdf_chunks = split_documents(pdf_pages) if pdf_pages else []
        json_chunks = load_json_documents(
            f"{config.DATA_DIR}/sberbank_help_documents.json"
        )

        all_chunks = pdf_chunks + json_chunks
        if not all_chunks:
            logger.warning("No documents found to index")
            return None

        logger.info(
            f"Total chunks: {len(all_chunks)} "
            f"(PDF: {len(pdf_chunks)}, JSON: {len(json_chunks)})"
        )
        vector_store = create_vector_store(all_chunks)
        logger.info("Reindexing completed successfully")
        return vector_store

    except Exception as e:
        logger.error(f"Error during reindexing: {e}", exc_info=True)
        return None
