"""Formatação sem dependência de comunicação com a nuvem."""
from datetime import date


def brl(amount):
    try:
        value=float(amount or 0)
    except (TypeError,ValueError):
        value=0
    return "R$ " + f"{value:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def pretty_date(value):
    if not value:return "—"
    try:return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except Exception:return str(value)
