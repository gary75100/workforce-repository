# formatting.py

from typing import Optional

def format_int(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{int(round(value)):,}"

def format_float(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:,.{decimals}f}"

def format_ci_currency(value: Optional[float], decimals: int = 0) -> str:
    if value is None:
        return ""
    return f"CI${value:,.{decimals}f}"

def format_us_currency(value: Optional[float], rate: float = 1.2, decimals: int = 0) -> str:
    if value is None:
        return ""
    converted = value * rate
    return f"US${converted:,.{decimals}f}"

