from decimal import Decimal, ROUND_HALF_UP

from django import template

from core.utils.numbers import format_miles

register = template.Library()


@register.filter
def percent(value, digits=1):
    try:
        digits = int(digits)
    except (TypeError, ValueError):
        digits = 1
    if value is None:
        return ""
    try:
        amount = Decimal(str(value)) * Decimal("100")
    except Exception:
        return ""
    quant = Decimal("1").scaleb(-digits)
    return str(amount.quantize(quant, rounding=ROUND_HALF_UP))


@register.filter
def miles(value):
    return format_miles(value)
