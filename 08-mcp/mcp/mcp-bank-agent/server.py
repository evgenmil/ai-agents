"""MCP-сервер банковских инструментов: search_products и loan_calc."""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

_ROOT = Path(__file__).parent
load_dotenv(_ROOT / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATA_FILE = _ROOT / "data" / "bank_products.json"
LOAN_API_URL = "https://api.api-ninjas.com/v1/mortgagecalculator"
LOAN_API_KEY = os.getenv("API_NINJAS_KEY", "")

mcp = FastMCP("mcp-bank-agent")


def _annuity_payment(loan_amount: float, annual_rate: float, term_months: int) -> tuple[float, float, float]:
    """Аннуитетный платёж: (monthly_payment, total_payment, total_interest)."""
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        monthly = loan_amount / term_months
    else:
        factor = (1 + monthly_rate) ** term_months
        monthly = loan_amount * monthly_rate * factor / (factor - 1)
    total = monthly * term_months
    return round(monthly, 2), round(total, 2), round(total - loan_amount, 2)


def _load_products() -> list[dict]:
    with DATA_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [])


def _product_text(product: dict) -> str:
    parts = [
        product.get("type", ""),
        product.get("name", ""),
        product.get("description", ""),
        " ".join(product.get("conditions", [])),
        " ".join(product.get("promotions", [])),
        " ".join(product.get("tags", [])),
    ]
    rate_min = product.get("rate_min")
    rate_max = product.get("rate_max")
    if rate_min is not None or rate_max is not None:
        parts.append(f"ставка {rate_min}-{rate_max} {product.get('rate_unit', '')}")
    return " ".join(str(p) for p in parts if p).lower()


@mcp.tool()
def search_products(query: str, product_type: str = "") -> str:
    """Поиск банковских продуктов по каталогу актуальных предложений.

    Используй для получения текущих ставок, акций, условий и параметров продуктов,
    которые меняются динамически и отсутствуют в PDF/JSON базе знаний агента.

    Args:
        query: Поисковая фраза (название, тип, условие, акция).
        product_type: Фильтр по типу: вклад, кредит, дебетовая карта,
            кредитная карта, счёт. Пустая строка — все типы.

    Returns:
        JSON со списком найденных продуктов и метаданными каталога.
    """
    products = _load_products()
    query_lower = query.strip().lower()
    type_filter = product_type.strip().lower()

    results = []
    for product in products:
        if type_filter and type_filter not in product.get("type", "").lower():
            continue
        text = _product_text(product)
        if not query_lower or all(word in text for word in query_lower.split()):
            results.append(product)

    payload = {
        "query": query,
        "product_type": product_type or None,
        "count": len(results),
        "products": results,
    }
    logger.info("search_products: query=%r type=%r → %d results", query, product_type, len(results))
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def loan_calc(
    loan_amount: float,
    interest_rate: float,
    term_months: int,
) -> str:
    """Калькулятор кредита: ежемесячный платёж и переплата.

    Обращается к внешнему API для расчёта аннуитетного платежа.
    Используй, когда клиент просит рассчитать платёж, переплату или полную стоимость кредита.

    Args:
        loan_amount: Сумма кредита в рублях (положительное число).
        interest_rate: Годовая процентная ставка в % (например 19.9).
        term_months: Срок кредита в месяцах (1–360).

    Returns:
        JSON: monthly_payment, total_payment, total_interest, loan_amount,
        interest_rate, term_months, source.
    """
    if loan_amount <= 0:
        return json.dumps({"error": "Сумма кредита должна быть положительной."}, ensure_ascii=False)
    if interest_rate < 0 or interest_rate > 100:
        return json.dumps({"error": "Ставка должна быть от 0 до 100%."}, ensure_ascii=False)
    if term_months < 1 or term_months > 360:
        return json.dumps({"error": "Срок кредита: от 1 до 360 месяцев."}, ensure_ascii=False)

    source = "api-ninjas.com/mortgagecalculator"
    monthly_payment = total_payment = total_interest = None

    if LOAN_API_KEY:
        duration_years = max(1, round(term_months / 12))
        params = urllib.parse.urlencode(
            {
                "loan_amount": loan_amount,
                "interest_rate": interest_rate,
                "duration_years": duration_years,
            }
        )
        url = f"{LOAN_API_URL}?{params}"
        headers = {"Accept": "application/json", "X-Api-Key": LOAN_API_KEY}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
            monthly = data.get("monthly_payment", {})
            if monthly and monthly.get("total") is not None:
                monthly_payment = round(monthly["total"], 2)
                total_interest = data.get("total_interest_paid")
                if total_interest is not None:
                    total_payment = round(loan_amount + total_interest, 2)
                    total_interest = round(total_interest, 2)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as exc:
            logger.warning("loan_calc API error, using local formula: %s", exc)

    if monthly_payment is None:
        monthly_payment, total_payment, total_interest = _annuity_payment(
            loan_amount, interest_rate, term_months
        )
        source = "annuity-formula (fallback, set API_NINJAS_KEY for external API)"

    payload = {
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "term_months": term_months,
        "monthly_payment": monthly_payment,
        "total_payment": total_payment,
        "total_interest": total_interest,
        "source": source,
    }
    logger.info(
        "loan_calc: amount=%s rate=%s%% term=%s mo → payment=%s",
        loan_amount,
        interest_rate,
        term_months,
        monthly_payment,
    )
    return json.dumps(payload, ensure_ascii=False)


def main():
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info("Starting mcp-bank-agent on http://%s:%s/mcp", host, port)
    mcp.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    main()
