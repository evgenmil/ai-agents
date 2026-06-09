import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_VALID_RETRIEVAL_MODES = ("semantic", "hybrid", "hybrid+reranker")
_VALID_EMBEDDING_PROVIDERS = ("openai", "huggingface")


class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
    MODEL = os.getenv("MODEL")
    MODEL_QUERY_TRANSFORM = os.getenv("MODEL_QUERY_TRANSFORM", "gpt-4o")
    DATA_DIR = os.getenv("DATA_DIR", "data")
    PROMPTS_DIR = os.getenv("PROMPTS_DIR", "prompts")
    CONVERSATION_SYSTEM_PROMPT_FILE = os.getenv(
        "CONVERSATION_SYSTEM_PROMPT_FILE", "conversation_system.txt"
    )
    QUERY_TRANSFORM_PROMPT_FILE = os.getenv(
        "QUERY_TRANSFORM_PROMPT_FILE", "query_transform.txt"
    )
    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")

    # Legacy fallback для k
    RETRIEVER_K = int(os.getenv("RETRIEVER_K", "3"))

    # Retrieval mode
    RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "semantic")

    # Embeddings
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    HUGGINGFACE_EMBEDDING_MODEL = os.getenv(
        "HUGGINGFACE_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
    )
    HUGGINGFACE_DEVICE = os.getenv("HUGGINGFACE_DEVICE", "cpu")

    # Semantic / BM25 / Hybrid
    SEMANTIC_K = int(os.getenv("SEMANTIC_K", os.getenv("RETRIEVER_K", "3")))
    BM25_K = int(os.getenv("BM25_K", os.getenv("RETRIEVER_K", "3")))
    HYBRID_SEMANTIC_WEIGHT = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.5"))
    HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", "0.5"))
    HYBRID_K = int(os.getenv("HYBRID_K", os.getenv("RETRIEVER_K", "3")))

    # Cross-Encoder reranker
    CROSS_ENCODER_MODEL = os.getenv(
        "CROSS_ENCODER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    )
    RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", os.getenv("RETRIEVER_K", "3")))

    RAG_DEBUG = os.getenv("RAG_DEBUG", "true").lower() in ("1", "true", "yes")
    RAG_DEBUG_TOP_K = int(os.getenv("RAG_DEBUG_TOP_K", "10"))

    SHOW_SOURCES = os.getenv("SHOW_SOURCES", "false").lower() == "true"

    # LangSmith
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_TRACING_V2 = os.getenv("LANGSMITH_TRACING_V2", "false").lower() == "true"
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "06-rag-assistant")
    LANGSMITH_DATASET = os.getenv("LANGSMITH_DATASET", "05-rag-qa-dataset")

    # RAGAS evaluation
    RAGAS_LLM_MODEL = os.getenv("RAGAS_LLM_MODEL", "gpt-4o")
    RAGAS_EMBEDDING_PROVIDER = os.getenv("RAGAS_EMBEDDING_PROVIDER", "openai")
    RAGAS_EMBEDDING_MODEL = os.getenv("RAGAS_EMBEDDING_MODEL", "text-embedding-3-large")
    RAGAS_HUGGINGFACE_EMBEDDING_MODEL = os.getenv(
        "RAGAS_HUGGINGFACE_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
    )

    @classmethod
    def load_prompt(cls, filename: str) -> str:
        prompt_path = Path(cls.PROMPTS_DIR) / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    @classmethod
    def validate_retrieval_mode(cls) -> None:
        if cls.RETRIEVAL_MODE not in _VALID_RETRIEVAL_MODES:
            raise ValueError(
                f"Invalid RETRIEVAL_MODE={cls.RETRIEVAL_MODE!r}. "
                f"Expected one of: {_VALID_RETRIEVAL_MODES}"
            )

    @classmethod
    def validate_embedding_provider(cls, provider: str) -> None:
        if provider not in _VALID_EMBEDDING_PROVIDERS:
            raise ValueError(
                f"Invalid embedding provider={provider!r}. "
                f"Expected one of: {_VALID_EMBEDDING_PROVIDERS}"
            )


config = Config()
