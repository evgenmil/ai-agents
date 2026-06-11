import json
import logging
import urllib.error
import urllib.request

from langchain_core.tools import tool

import rag
from rag import retrieve_documents, documents_to_sources

logger = logging.getLogger(__name__)

_EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest"

_EMPTY_MESSAGE = "По данному запросу информация в банковских документах не найдена."


@tool
def rag_search(query: str) -> str:
    """Ищет информацию о банковских продуктах и услугах Сбербанка в загруженных документах.

    Используй, когда пользователь спрашивает о кредитах, вкладах, картах,
    тарифах, условиях обслуживания и других банковских продуктах.

    Args:
        query: Поисковая фраза на русском языке. Формулируй конкретно,
            без лишних слов (например: «условия потребительского кредита»).

    Returns:
        JSON-строка: {"sources": [{"source": "file.pdf", "page_content": "...", "page": 1}]}
        Поле page присутствует только для PDF-документов.
    """
    if rag.retriever is None:
        logger.warning("rag_search called but retriever is not initialized")
        return json.dumps(
            {"sources": [], "message": "База знаний не инициализирована."},
            ensure_ascii=False,
        )

    docs = retrieve_documents(query)
    if not docs:
        logger.info("rag_search: no documents for query=%r", query)
        return json.dumps(
            {"sources": [], "message": _EMPTY_MESSAGE},
            ensure_ascii=False,
        )

    payload = {"sources": documents_to_sources(docs)}
    logger.info("rag_search: found %d sources for query=%r", len(payload["sources"]), query)
    return json.dumps(payload, ensure_ascii=False)


@tool
def currency_convert(amount: float, from_currency: str, to_currency: str) -> str:
    """Конвертирует денежную сумму из одной валюты в другую по актуальному курсу.

    Используй, когда пользователь просит перевести сумму в другую валюту,
    узнать курс обмена или сравнить валюты (USD, EUR, RUB, CNY и др.).

    НЕ используй для вопросов о банковских продуктах, тарифах и комиссиях —
    для этого есть rag_search.

    Args:
        amount: Сумма для конвертации (положительное число).
        from_currency: Код исходной валюты ISO 4217 (например USD, EUR, RUB).
        to_currency: Код целевой валюты ISO 4217.

    Returns:
        JSON-строка: amount, from_currency, to_currency, result, rate, date.
        При ошибке — поле error с описанием для агента.
    """
    from_code = from_currency.strip().upper()
    to_code = to_currency.strip().upper()

    if amount <= 0:
        return json.dumps(
            {"error": "Сумма должна быть положительным числом."},
            ensure_ascii=False,
        )

    if from_code == to_code:
        payload = {
            "amount": amount,
            "from_currency": from_code,
            "to_currency": to_code,
            "result": round(amount, 2),
            "rate": 1.0,
            "date": None,
        }
        return json.dumps(payload, ensure_ascii=False)

    url = f"{_EXCHANGE_RATE_URL}/{from_code}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("currency_convert HTTP error: %s", exc)
        return json.dumps(
            {
                "error": (
                    f"Не удалось конвертировать {from_code} в {to_code}. "
                    "Проверьте коды валют (ISO 4217, например USD, EUR, RUB)."
                )
            },
            ensure_ascii=False,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("currency_convert failed: %s", exc)
        return json.dumps(
            {"error": "Сервис курсов валют временно недоступен. Попробуйте позже."},
            ensure_ascii=False,
        )

    if data.get("result") != "success":
        return json.dumps(
            {"error": "Сервис курсов валют вернул ошибку. Попробуйте позже."},
            ensure_ascii=False,
        )

    rate = data.get("rates", {}).get(to_code)
    if rate is None:
        return json.dumps(
            {"error": f"Курс для валюты {to_code} не найден."},
            ensure_ascii=False,
        )

    converted = amount * rate
    payload = {
        "amount": amount,
        "from_currency": from_code,
        "to_currency": to_code,
        "result": round(converted, 2),
        "rate": round(rate, 6),
        "date": data.get("time_last_update_utc"),
    }
    logger.info(
        "currency_convert: %s %s → %s %s (rate=%s, date=%s)",
        amount,
        from_code,
        payload["result"],
        to_code,
        payload["rate"],
        payload["date"],
    )
    return json.dumps(payload, ensure_ascii=False)
