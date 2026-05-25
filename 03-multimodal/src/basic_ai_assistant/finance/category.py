from enum import Enum


class Category(str, Enum):
    """Фиксированный список категорий доходов и расходов."""

    PRODUCTS = "products"
    RESTAURANTS = "restaurants"
    TAXI = "taxi"
    TRANSPORT = "transport"
    EDUCATION = "education"
    TRAVEL = "travel"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    UTILITIES = "utilities"
    SALARY = "salary"
    FREELANCE = "freelance"
    OTHER = "other"
