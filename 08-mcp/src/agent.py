import json
import logging

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from config import config
from rag import sources_to_documents
from tools import currency_convert, rag_search

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
)

bank_agent = None
checkpointer = MemorySaver()


async def _load_mcp_tools() -> list:
    """Подключение к MCP-серверу. При ошибке — пустой список (graceful degradation)."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        mcp_client = MultiServerMCPClient(
            {
                "bank-agent": {
                    "transport": "streamable_http",
                    "url": config.MCP_BANK_URL,
                }
            }
        )
        mcp_tools = await mcp_client.get_tools()
        logger.info("MCP tools loaded: %s", [t.name for t in mcp_tools])
        return mcp_tools
    except Exception as exc:
        logger.warning("MCP server unavailable, continuing without MCP tools: %s", exc)
        return []


async def create_bank_agent():
    """Создание ReAct-агента с локальными и MCP-инструментами."""
    system_prompt = config.load_prompt(config.AGENT_SYSTEM_PROMPT_FILE)
    llm = ChatOpenAI(model=config.MODEL, temperature=0.7)

    mcp_tools = await _load_mcp_tools()
    tools = [rag_search, currency_convert] + mcp_tools

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )
    logger.info(
        "Bank agent created: model=%s, tools=%s",
        config.MODEL,
        [t.name for t in tools],
    )
    return agent


async def initialize_agent():
    """Инициализация глобального bank_agent (async — get_tools() асинхронный)."""
    global bank_agent
    bank_agent = await create_bank_agent()
    return bank_agent


def _log_agent_step(message) -> None:
    msg_type = type(message).__name__
    if isinstance(message, AIMessage):
        if message.tool_calls:
            for tc in message.tool_calls:
                logger.info(
                    "[Agent] %s → tool_call: %s(%s)",
                    msg_type,
                    tc.get("name"),
                    tc.get("args"),
                )
        elif message.content:
            logger.info("[Agent] %s → %s", msg_type, str(message.content)[:200])
        else:
            logger.warning("[Agent] %s → empty content, no tool_calls", msg_type)
    elif isinstance(message, ToolMessage):
        logger.info("[Agent] ToolMessage [%s]: %s", message.name, str(message.content)[:150])
    elif isinstance(message, HumanMessage):
        logger.info("[Agent] HumanMessage: %s", str(message.content)[:100])


def extract_sources_from_messages(messages) -> list[dict]:
    """Sources из ToolMessage rag_search только после последнего HumanMessage."""
    last_human_idx = -1
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_idx = i

    if last_human_idx < 0:
        return []

    sources = []
    for msg in messages[last_human_idx + 1 :]:
        if not isinstance(msg, ToolMessage) or msg.name != "rag_search":
            continue
        try:
            data = json.loads(msg.content)
            sources.extend(data.get("sources", []))
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse rag_search ToolMessage as JSON")
    return sources


def _extract_answer(messages) -> str:
    if not messages:
        return FALLBACK_ANSWER

    last_msg = messages[-1]
    if not isinstance(last_msg, AIMessage):
        return FALLBACK_ANSWER

    if not last_msg.content and not last_msg.tool_calls:
        logger.warning("Empty AIMessage without tool_calls — using fallback")
        return FALLBACK_ANSWER

    return last_msg.content or FALLBACK_ANSWER


async def _run_agent_stream(query: str, thread_id: str) -> list:
    config_dict = {"configurable": {"thread_id": str(thread_id)}}
    inputs = {"messages": [HumanMessage(content=query)]}
    final_messages = []

    async for step in bank_agent.astream(inputs, config=config_dict, stream_mode="values"):
        final_messages = step.get("messages", [])
        if final_messages:
            _log_agent_step(final_messages[-1])

    return final_messages


async def agent_answer(query: str, thread_id: str) -> dict:
    """
    Получить ответ агента с учётом истории в MemorySaver.

    Returns:
        dict: {"answer": str, "documents": list[Document]}
    """
    if bank_agent is None:
        raise ValueError("Agent not initialized")

    final_messages = await _run_agent_stream(query, thread_id)
    answer = _extract_answer(final_messages)
    sources = extract_sources_from_messages(final_messages)
    documents = sources_to_documents(sources)

    return {"answer": answer, "documents": documents}
