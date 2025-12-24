from decimal import Decimal, ROUND_HALF_UP


def format_miles(value):
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(str(value))
    except Exception:
        return ""
    amount = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    number = int(abs(amount))
    parts = []
    while number >= 1000:
        number, rest = divmod(number, 1000)
        parts.append(f"{rest:03d}")
    parts.append(str(number))
    return sign + ".".join(reversed(parts))


def parse_miles(value):
    if value is None:
        return None
    if isinstance(value, (int, Decimal)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(".", "").replace(",", "")
    return int(normalized)
