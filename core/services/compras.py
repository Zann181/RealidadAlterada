from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from core.models import Compra, CompraDetalle
from core.services.inventario import incrementar_stock, decrementar_stock

MONEY_PRECISION = Decimal("0.01")
QTY_PRECISION = Decimal("1")
TOLERANCIA = Decimal("0.01")


def _to_decimal(value):
    """Convierte a Decimal evitando errores de float."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_money(value):
    """Normaliza valores monetarios a 2 decimales."""
    return _to_decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _quantize_qty(value):
    """Normaliza cantidades a enteros."""
    cantidad = _to_decimal(value)
    if cantidad != cantidad.to_integral_value(rounding=ROUND_HALF_UP):
        raise ValueError("La cantidad debe ser un numero entero.")
    return cantidad.quantize(QTY_PRECISION, rounding=ROUND_HALF_UP)


def _validar_iva(iva):
    """Valida que el IVA este en rango [0, 1]."""
    iva_decimal = _to_decimal(iva)
    if iva_decimal < 0 or iva_decimal > 1:
        raise ValueError("El IVA debe estar entre 0 y 1.")
    return iva_decimal


def _validar_total_existente(nombre, actual, esperado):
    """Valida totales cuando el valor ya existe."""
    if actual is None:
        return
    actual_decimal = _to_decimal(actual)
    if actual_decimal != 0 and abs(actual_decimal - esperado) > TOLERANCIA:
        raise ValueError(f"{nombre} inconsistente en la compra.")


@transaction.atomic
def compra_confirmar(compra_id, usuario=None):
    """Confirma una compra, actualiza inventario y registra movimientos."""
    compra = Compra.objects.select_for_update().get(pk=compra_id)
    if compra.estado != "BORRADOR":
        raise ValueError("La compra no esta en estado BORRADOR.")

    items = list(
        CompraDetalle.objects.select_for_update()
        .filter(compra=compra)
        .select_related("producto")
    )
    if not items:
        raise ValueError("La compra no tiene items.")

    subtotal = Decimal("0")
    iva_total = Decimal("0")
    for item in items:
        cantidad = _quantize_qty(item.cantidad)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        costo_unitario = _to_decimal(item.costo_unitario)
        if costo_unitario < 0:
            raise ValueError("El costo unitario no puede ser negativo.")
        iva = _validar_iva(item.iva)

        line_subtotal = cantidad * costo_unitario
        iva_linea = line_subtotal * iva
        total_linea = _quantize_money(line_subtotal + iva_linea)

        total_existente = _to_decimal(item.total_linea)
        if total_existente != 0 and abs(total_existente - total_linea) > TOLERANCIA:
            raise ValueError("Total de linea inconsistente en la compra.")

        item.total_linea = total_linea
        item.save(update_fields=["total_linea"])

        subtotal += line_subtotal
        iva_total += iva_linea

    subtotal = _quantize_money(subtotal)
    iva_total = _quantize_money(iva_total)
    otros_costos = _quantize_money(_to_decimal(compra.otros_costos))
    if otros_costos < 0:
        raise ValueError("Otros costos no puede ser negativo.")
    total = _quantize_money(subtotal + iva_total + otros_costos)

    _validar_total_existente("Subtotal", compra.subtotal, subtotal)
    _validar_total_existente("IVA total", compra.iva_total, iva_total)
    _validar_total_existente("Total", compra.total, total)

    compra.subtotal = subtotal
    compra.iva_total = iva_total
    compra.total = total
    compra.estado = "CONFIRMADA"
    compra.save(update_fields=["subtotal", "iva_total", "total", "estado"])

    for item in items:
        incrementar_stock(
            item.producto,
            item.cantidad,
            item.costo_unitario,
            ref={
                "tipo": "COMPRA",
                "fecha": compra.fecha,
                "referencia": "compra",
                "referencia_id": compra.id,
                "nota": f"Compra #{compra.id}",
            },
        )

    return compra


@transaction.atomic
def compra_anular(compra_id, usuario=None):
    """Anula una compra confirmada y revierte el inventario."""
    compra = Compra.objects.select_for_update().get(pk=compra_id)
    if compra.estado != "CONFIRMADA":
        raise ValueError("Solo se puede anular una compra CONFIRMADA.")

    items = list(
        CompraDetalle.objects.select_for_update()
        .filter(compra=compra)
        .select_related("producto")
    )
    if not items:
        raise ValueError("La compra no tiene items.")

    for item in items:
        decrementar_stock(
            item.producto,
            item.cantidad,
            item.costo_unitario,
            ref={
                "tipo": "AJUSTE_NEGATIVO",
                "fecha": compra.fecha,
                "referencia": "compra_anulada",
                "referencia_id": compra.id,
                "nota": f"Compra anulada #{compra.id}",
            },
        )

    compra.estado = "ANULADA"
    compra.save(update_fields=["estado"])
    return compra
