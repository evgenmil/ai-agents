import hashlib
import json
import logging
import pickle
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import config
from embeddings import get_embeddings, get_lazy_embeddings

logger = logging.getLogger(__name__)

chunks = None

CHUNK_SIZE = 800
CHUNK_OVERLAP = 80
CACHE_DIR = Path(".cache")
CACHE_FILE = CACHE_DIR / "vector_index.pkl"
FINGERPRINT_FILE = CACHE_DIR / "index_fingerprint.json"

def load_pdf_documents(data_dir: str) -> list:
    """Загрузка всех PDF документов из директории"""
    pages = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.warning(f"Directory {data_dir} does not exist")
        return pages
    
    pdf_files = list(data_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files in {data_dir}")
    
    for pdf_file in pdf_files:
        loader = PyPDFLoader(str(pdf_file))
        pages.extend(loader.load())
        logger.info(f"Loaded {pdf_file.name}")
    
    return pages

def split_documents(pages: list) -> list:
    """Разбиение документов на чанки"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = text_splitter.split_documents(pages)
    logger.info(f"Split into {len(chunks)} chunks")
    return chunks

def _index_fingerprint() -> str:
    """Отпечаток исходных файлов и настроек индексации."""
    parts = [
        f"provider={config.EMBEDDING_PROVIDER}",
        f"chunk_size={CHUNK_SIZE}",
        f"chunk_overlap={CHUNK_OVERLAP}",
    ]
    if config.EMBEDDING_PROVIDER == "huggingface":
        parts.append(f"model={config.HUGGINGFACE_EMBEDDING_MODEL}")
    else:
        parts.append(f"model={config.EMBEDDING_MODEL}")

    data_path = Path(config.DATA_DIR)
    for pdf_file in sorted(data_path.glob("*.pdf")):
        stat = pdf_file.stat()
        parts.append(f"pdf:{pdf_file.name}:{stat.st_mtime_ns}:{stat.st_size}")

    json_file = data_path / "sberbank_help_documents.json"
    if json_file.exists():
        stat = json_file.stat()
        parts.append(f"json:{stat.st_mtime_ns}:{stat.st_size}")

    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def save_index_cache(vector_store, doc_chunks: list) -> None:
    """Сохранить готовый индекс на диск."""
    fingerprint = _index_fingerprint()
    CACHE_DIR.mkdir(exist_ok=True)
    with CACHE_FILE.open("wb") as cache_file:
        pickle.dump(
            {"store": vector_store.store, "chunks": doc_chunks},
            cache_file,
        )
    FINGERPRINT_FILE.write_text(
        json.dumps({"fingerprint": fingerprint}, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Index cache saved (%d chunks)", len(doc_chunks))


def try_load_cached_index():
    """Загрузить индекс из кэша, если исходники не менялись."""
    global chunks

    if not CACHE_FILE.exists() or not FINGERPRINT_FILE.exists():
        return None

    try:
        saved = json.loads(FINGERPRINT_FILE.read_text(encoding="utf-8"))
        if saved.get("fingerprint") != _index_fingerprint():
            logger.info("Index cache is stale, rebuilding...")
            return None

        with CACHE_FILE.open("rb") as cache_file:
            data = pickle.load(cache_file)

        doc_chunks = data["chunks"]
        chunks = doc_chunks
        vector_store = InMemoryVectorStore(embedding=get_lazy_embeddings())
        vector_store.store = data["store"]
        logger.info("Loaded index from cache (%d chunks)", len(doc_chunks))
        return vector_store, doc_chunks
    except Exception as e:
        logger.warning("Failed to load index cache: %s", e)
        return None


def create_vector_store(doc_chunks: list):
    """Создание векторного хранилища"""
    global chunks
    chunks = doc_chunks
    embeddings = get_embeddings()
    vector_store = InMemoryVectorStore.from_documents(
        documents=doc_chunks,
        embedding=embeddings,
    )
    logger.info(f"Created vector store with {len(doc_chunks)} chunks")
    save_index_cache(vector_store, doc_chunks)
    return vector_store

async def reindex_all():
    """Полная переиндексация всех документов"""
    logger.info("Starting full reindexing...")
    
    try:
        pages = load_pdf_documents(config.DATA_DIR)
        if not pages:
            logger.warning("No documents found to index")
            return None
        
        chunks = split_documents(pages)
        if not chunks:
            logger.warning("No chunks created after splitting")
            return None
            
        vector_store = create_vector_store(chunks)
        logger.info("Reindexing completed successfully")
        return vector_store
        
    except FileNotFoundError as e:
        logger.error(f"Directory not found: {e}")
        return None
    except Exception as e:
        logger.error(f"Error during reindexing: {e}", exc_info=True)
        return None

