import logging
from typing import Optional, Dict, Any
from langsmith import Client
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    AnswerCorrectness,
    AnswerSimilarity,
    ContextRecall,
    ContextPrecision,
)
from ragas.metrics.base import MetricWithLLM, MetricWithEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig
from config import config
import rag

logger = logging.getLogger(__name__)

_ragas_metrics = None
_ragas_run_config = None

def init_ragas_metrics():
    """Инициализация RAGAS метрик (раздел 5.1 референсного ноутбука)."""
    global _ragas_metrics, _ragas_run_config

    if _ragas_metrics is not None:
        return _ragas_metrics, _ragas_run_config

    logger.info("Initializing RAGAS metrics...")

    langchain_llm = ChatOpenAI(model=config.RAGAS_LLM_MODEL, temperature=0)
    langchain_embeddings = OpenAIEmbeddings(model=config.RAGAS_EMBEDDING_MODEL)

    answer_similarity_metric = AnswerSimilarity()

    metrics = [
        Faithfulness(),
        AnswerRelevancy(strictness=1),
        AnswerCorrectness(answer_similarity=answer_similarity_metric),
        answer_similarity_metric,
        ContextRecall(),
        ContextPrecision(),
    ]

    ragas_llm = LangchainLLMWrapper(langchain_llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)

    for metric in metrics:
        if isinstance(metric, MetricWithLLM):
            metric.llm = ragas_llm
        if isinstance(metric, MetricWithEmbeddings):
            metric.embeddings = ragas_embeddings
        run_config = RunConfig()
        metric.init(run_config)

    run_config = RunConfig(
        max_workers=4,
        max_wait=180,
        max_retries=3,
    )

    _ragas_metrics = metrics
    _ragas_run_config = run_config

    logger.info(f"RAGAS metrics initialized: {', '.join([m.name for m in metrics])}")
    return _ragas_metrics, _ragas_run_config

def check_dataset_exists(dataset_name: str) -> bool:
    if not config.LANGSMITH_API_KEY:
        logger.error("LANGSMITH_API_KEY not set")
        return False

    try:
        client = Client()
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        return len(datasets) > 0
    except Exception as e:
        logger.error(f"Error checking dataset: {e}")
        return False

def evaluate_dataset(dataset_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Полный цикл evaluation (раздел 5.2 референсного ноутбука):
    1. Эксперимент в LangSmith (blocking=False)
    2. RAGAS batch evaluation
    3. Feedback в LangSmith
    """
    if not config.LANGSMITH_API_KEY:
        raise ValueError("LANGSMITH_API_KEY not set. Cannot run evaluation.")

    if dataset_name is None:
        dataset_name = config.LANGSMITH_DATASET

    logger.info(f"Starting evaluation for dataset: {dataset_name}")

    if not check_dataset_exists(dataset_name):
        raise ValueError(f"Dataset '{dataset_name}' not found in LangSmith")

    ragas_metrics, ragas_run_config = init_ragas_metrics()
    client = Client()

    logger.info("\n[1/3] Running experiment and collecting data...")

    def target(inputs: dict) -> dict:
        from langchain_core.messages import HumanMessage
        result = rag.get_rag_chain().invoke({"messages": [HumanMessage(content=inputs["question"])]})
        return {
            "answer": result["answer"],
            "documents": result["documents"],
        }

    questions = []
    answers = []
    contexts_list = []
    ground_truths = []
    run_ids = []

    for result in client.evaluate(
        target,
        data=dataset_name,
        evaluators=[],
        experiment_prefix="rag-evaluation",
        metadata={
            "approach": "RAGAS batch evaluation + LangSmith feedback",
            "model": config.MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
        },
        blocking=False,
    ):
        run = result["run"]
        example = result["example"]

        question = run.inputs.get("question", "")
        answer = run.outputs.get("answer", "")
        documents = run.outputs.get("documents", [])
        contexts = [
            doc.page_content if hasattr(doc, "page_content") else str(doc)
            for doc in documents
        ]
        ground_truth = example.outputs.get("answer", "") if example else ""

        questions.append(question)
        answers.append(answer)
        contexts_list.append(contexts)
        ground_truths.append(ground_truth)
        run_ids.append(str(run.id))

    logger.info(f"Experiment completed, collected {len(questions)} examples")

    logger.info("\n[2/3] Running RAGAS evaluation...")

    ragas_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths,
    })

    ragas_result = evaluate(
        ragas_dataset,
        metrics=ragas_metrics,
        run_config=ragas_run_config,
    )

    ragas_df = ragas_result.to_pandas()
    logger.info("RAGAS evaluation completed")

    metrics_summary = {}
    for metric in ragas_metrics:
        if metric.name in ragas_df.columns:
            avg_score = ragas_df[metric.name].mean()
            metrics_summary[metric.name] = avg_score
            logger.info(f"  {metric.name}: {avg_score:.3f}")

    logger.info("\n[3/3] Uploading feedback to LangSmith...")

    for idx, run_id in enumerate(run_ids):
        row = ragas_df.iloc[idx]
        for metric in ragas_metrics:
            if metric.name in row:
                score = row[metric.name]
                client.create_feedback(
                    run_id=run_id,
                    key=metric.name,
                    score=float(score),
                    comment=f"RAGAS metric: {metric.name}",
                )

    logger.info(f"Feedback uploaded ({len(run_ids)} runs)")

    return {
        "dataset_name": dataset_name,
        "num_examples": len(questions),
        "metrics": metrics_summary,
        "ragas_result": ragas_result,
        "run_ids": run_ids,
    }
