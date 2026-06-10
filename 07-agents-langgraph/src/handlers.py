import logging
import uuid

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import config
import agent
import indexer_with_json
import rag
import evaluation

logger = logging.getLogger(__name__)
router = Router()

# thread_id для MemorySaver (новый при /start)
chat_threads: dict[int, str] = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    logger.info("User %s started the bot", message.chat.id)
    chat_threads[message.chat.id] = str(uuid.uuid4())

    await message.answer(
        "Привет! Я ИИ-консультант Сбербанка.\n\n"
        "Я могу:\n"
        "• Отвечать на вопросы о кредитах, вкладах и картах\n"
        "• Искать информацию в банковских документах\n"
        "• Поддерживать диалог с учётом контекста\n\n"
        "Используйте /help для просмотра всех команд."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    logger.info("User %s requested help", message.chat.id)
    help_text = (
        "🤖 *ИИ-консультант Сбербанка*\n\n"
        "Я помогаю с вопросами о банковских продуктах на основе документов.\n\n"
        "*Доступные команды:*\n"
        "/start - Начать новый диалог (сбросить историю)\n"
        "/help - Показать эту справку\n"
        "/index - Переиндексировать документы\n"
        "/index\\_status - Проверить статус индексации\n"
        "/evaluate\\_dataset - Оценить качество системы\n\n"
        "*Примеры вопросов:*\n"
        "• Какие условия потребительского кредита?\n"
        "• Какие проценты по вкладам?\n"
        "• Можно ли досрочно погасить кредит?\n\n"
        "_Если информации нет в документах, я честно об этом сообщу\\._"
    )
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("index"))
async def cmd_index(message: Message):
    logger.info("User %s requested reindexing", message.chat.id)
    await message.answer("Начинаю переиндексацию документов...")

    try:
        rag.vector_store = await indexer_with_json.reindex_all()
        if rag.vector_store:
            rag.initialize_retriever()
            stats = rag.get_vector_store_stats()
            await message.answer(
                f"✅ Переиндексация завершена!\n"
                f"Проиндексировано документов: {stats['count']}"
            )
        else:
            await message.answer("⚠️ Не найдено документов для индексации")
    except Exception as e:
        logger.error("Error during reindexing: %s", e)
        await message.answer(f"❌ Ошибка при переиндексации: {str(e)}")


@router.message(Command("index_status"))
async def cmd_index_status(message: Message):
    logger.info("User %s requested index status", message.chat.id)
    stats = rag.get_vector_store_stats()

    if stats["status"] == "not initialized":
        await message.answer("⚠️ Векторное хранилище не инициализировано")
    else:
        await message.answer(
            f"📊 Статус индексации:\n"
            f"Статус: {stats['status']}\n"
            f"Количество документов: {stats['count']}"
        )


@router.message(Command("evaluate_dataset"))
async def cmd_evaluate_dataset(message: Message):
    logger.info("User %s requested dataset evaluation", message.chat.id)

    if not config.LANGSMITH_API_KEY:
        await message.answer(
            "⚠️ LangSmith API key не настроен.\n"
            "Установите LANGSMITH_API_KEY в .env файле для использования evaluation."
        )
        return

    if rag.vector_store is None or rag.retriever is None:
        await message.answer(
            "⚠️ Векторное хранилище не инициализировано.\n"
            "Используйте /index для индексации документов."
        )
        return

    command_parts = message.text.split(maxsplit=1)
    dataset_name = command_parts[1] if len(command_parts) > 1 else config.LANGSMITH_DATASET

    await message.answer(
        f"🔍 Начинаю evaluation датасета: {dataset_name}\n\n"
        f"Это может занять несколько минут..."
    )

    try:
        result = await evaluation.evaluate_dataset(dataset_name)

        metrics = result["metrics"]
        num_examples = result["num_examples"]

        report = (
            f"✅ Evaluation завершен!\n\n"
            f"📊 Датасет: {dataset_name}\n"
            f"📝 Примеров обработано: {num_examples}\n\n"
            f"🎯 RAGAS Метрики:\n"
        )

        metric_descriptions = {
            "faithfulness": "Обоснованность (нет галлюцинаций)",
            "answer_relevancy": "Релевантность ответа",
            "answer_correctness": "Правильность ответа",
            "answer_similarity": "Похожесть на эталон",
            "context_recall": "Полнота контекста",
            "context_precision": "Точность поиска",
        }

        for metric_name, score in metrics.items():
            desc = metric_descriptions.get(metric_name, metric_name)
            if score >= 0.8:
                emoji = "🟢"
            elif score >= 0.6:
                emoji = "🟡"
            else:
                emoji = "🔴"
            report += f"{emoji} {desc}: {score:.3f}\n"

        report += "\n💡 Результаты загружены в LangSmith как feedback"
        await message.answer(report)
        logger.info("Evaluation completed for user %s", message.chat.id)

    except ValueError as e:
        logger.error("ValueError in evaluation: %s", e)
        await message.answer(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error("Error during evaluation: %s", e, exc_info=True)
        await message.answer(
            f"❌ Произошла ошибка при evaluation:\n{str(e)}\n\n"
            f"Проверьте логи для подробностей."
        )


@router.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Извините, я работаю только с текстовыми сообщениями.")
        return

    logger.info("Message from %s: %s...", message.chat.id, message.text[:100])

    if message.chat.id not in chat_threads:
        chat_threads[message.chat.id] = str(message.chat.id)

    try:
        if rag.vector_store is None or rag.retriever is None:
            logger.warning("Vector store not initialized for chat %s", message.chat.id)
            await message.answer(
                "⚠️ Векторное хранилище не инициализировано. "
                "Пожалуйста, подождите или используйте /index для индексации."
            )
            return

        thread_id = chat_threads[message.chat.id]
        result = await agent.agent_answer(message.text, thread_id)
        answer = result["answer"]
        documents = result["documents"]

        final_response = answer
        if config.SHOW_SOURCES and documents:
            sources = rag.format_sources(documents)
            if sources:
                final_response = f"{answer}\n\n{sources}"

        await message.answer(final_response)

    except ValueError as e:
        logger.error("ValueError in handle_message for chat %s: %s", message.chat.id, e)
        await message.answer(
            "⚠️ Система не готова. Используйте /index для индексации документов."
        )
    except Exception as e:
        logger.error("Error in handle_message for chat %s: %s", message.chat.id, e, exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке вашего сообщения. "
            "Попробуйте еще раз или используйте /start для начала нового диалога."
        )
