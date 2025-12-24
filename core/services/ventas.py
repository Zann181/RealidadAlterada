from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from core.models import DeudaCliente, MovimientoInventario, Venta, VentaDetalle
from core.services.inventario import decrementar_stock, incrementar_stock

MONEY_PRECISION = Decimal("0.01")
QTY_PRECISION = Decimal("1")
COST_PRECISION = Decimal("0.000001")
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


def _quantize_cost(value):
    """Normaliza costos a 6 decimales."""
    return _to_decimal(value).quantize(COST_PRECISION, rounding=ROUND_HALF_UP)


def _validar_iva(iva):
    """Valida que el IVA este en rango [0, 1]."""
    iva_decimal = _to_decimal(iva)
    if iva_decimal < 0 or iva_decimal > 1:
        raise ValueError("El IVA debe estar entre 0 y 1.")
    return iva_decimal


def _ultimo_costo_unitario(producto):
    """Obtiene el ultimo costo unitario conocido del producto."""
    movimiento = (
        MovimientoInventario.objects.filter(producto=producto, costo_unitario__gt=0)
        .order_by("-fecha", "-id")
        .first()
    )
    if movimiento:
        return _to_decimal(movimiento.costo_unitario)
    return Decimal("0")


def _crear_deuda_si_aplica(venta, total):
    """Crea una deuda para el deudor si la venta es a credito."""
    if venta.medio_pago != "DEUDA" or not venta.deudor_id:
        return
    existe = DeudaCliente.objects.filter(venta=venta).exists()
    if existe:
        return
    DeudaCliente.objects.create(
        deudor=venta.deudor,
        fecha=venta.fecha,
        estado="ABIERTA",
        total_inicial=total,
        saldo_actual=total,
        descripcion=f"Venta #{venta.id}",
        venta=venta,
    )


@transaction.atomic
def venta_confirmar(venta_id, usuario=None):
    """Confirma una venta, valida stock y registra movimientos."""
    venta = Venta.objects.select_for_update().get(pk=venta_id)
    if venta.estado != "BORRADOR":
        raise ValueError("La venta no esta en estado BORRADOR.")

    items = list(
        VentaDetalle.objects.select_for_update()
        .filter(venta=venta)
        .select_related("producto")
    )
    if not items:
        raise ValueError("La venta no tiene items.")

    descuento_pct = _to_decimal(venta.descuento_total)
    if descuento_pct < 0 or descuento_pct > 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")

    subtotal = Decimal("0")
    iva_total = Decimal("0")
    for item in items:
        cantidad = _quantize_qty(item.cantidad)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        precio_unitario = _to_decimal(item.precio_unitario)
        descuento_unitario = _to_decimal(item.descuento_unitario)
        if precio_unitario < 0 or descuento_unitario < 0:
            raise ValueError("Precios y descuentos no pueden ser negativos.")
        if descuento_unitario > precio_unitario:
            raise ValueError("El descuento unitario no puede superar el precio unitario.")
        iva = _validar_iva(item.iva)

        costo_unitario = _to_decimal(item.costo_unitario_en_venta)
        if costo_unitario <= 0:
            costo_unitario = _ultimo_costo_unitario(item.producto)
        costo_unitario = _quantize_cost(costo_unitario)

        line_bruto = (precio_unitario - descuento_unitario) * cantidad
        if iva > 0:
            line_subtotal = line_bruto / (Decimal("1") + iva)
            iva_linea = line_bruto - line_subtotal
        else:
            line_subtotal = line_bruto
            iva_linea = Decimal("0")
        line_subtotal = _quantize_money(line_subtotal)
        iva_linea = _quantize_money(iva_linea)
        total_linea = _quantize_money(line_bruto)
        if iva > 0:
            neto_unitario = (precio_unitario - descuento_unitario) / (Decimal("1") + iva)
        else:
            neto_unitario = precio_unitario - descuento_unitario
        ganancia_linea = _quantize_money((neto_unitario - costo_unitario) * cantidad)

        total_existente = _to_decimal(item.total_linea)
        if total_existente != 0 and abs(total_existente - total_linea) > TOLERANCIA:
            raise ValueError("Total de linea inconsistente en la venta.")

        item.costo_unitario_en_venta = costo_unitario
        item.total_linea = total_linea
        item.ganancia_linea = ganancia_linea
        item.save(update_fields=["costo_unitario_en_venta", "total_linea", "ganancia_linea"])

        subtotal += line_subtotal
        iva_total += iva_linea

    subtotal = _quantize_money(subtotal)
    iva_total = _quantize_money(iva_total)
    descuento_valor = _quantize_money((subtotal + iva_total) * (descuento_pct / Decimal("100")))
    if descuento_valor > subtotal + iva_total:
        raise ValueError("El descuento no puede superar el total de la venta.")

    # El descuento se aplica despues del IVA para mantener el flujo simple.
    total = _quantize_money(subtotal + iva_total - descuento_valor)

    venta.subtotal = subtotal
    venta.iva_total = iva_total
    venta.total = total
    venta.estado = "CONFIRMADA"
    venta.save(update_fields=["subtotal", "iva_total", "total", "estado"])
    _crear_deuda_si_aplica(venta, total)

    movimientos_existentes = set(
        MovimientoInventario.objects.filter(
            referencia="venta",
            referencia_id=venta.id,
        ).values_list("producto_id", flat=True)
    )
    for item in items:
        if item.producto_id in movimientos_existentes:
            continue
        decrementar_stock(
            item.producto,
            item.cantidad,
            item.costo_unitario_en_venta,
            ref={
                "tipo": "VENTA",
                "fecha": venta.fecha,
                "referencia": "venta",
                "referencia_id": venta.id,
                "nota": f"Venta #{venta.id}",
            },
        )

    return venta


@transaction.atomic
def venta_anular(venta_id, usuario=None):
    """Anula una venta confirmada y reingresa inventario."""
    venta = Venta.objects.select_for_update().get(pk=venta_id)
    if venta.estado != "CONFIRMADA":
        raise ValueError("Solo se puede anular una venta CONFIRMADA.")

    items = list(
        VentaDetalle.objects.select_for_update()
        .filter(venta=venta)
        .select_related("producto")
    )
    if not items:
        raise ValueError("La venta no tiene items.")

    for item in items:
        incrementar_stock(
            item.producto,
            item.cantidad,
            item.costo_unitario_en_venta,
            ref={
                "tipo": "DEVOLUCION",
                "fecha": venta.fecha,
                "referencia": "venta_anulada",
                "referencia_id": venta.id,
                "nota": f"Venta anulada #{venta.id}",
            },
        )

    venta.estado = "ANULADA"
    venta.save(update_fields=["estado"])
    return venta


@transaction.atomic
def venta_recalcular_totales(venta_id):
    """Recalcula totales de una venta sin cambiar su estado."""
    venta = Venta.objects.select_for_update().get(pk=venta_id)
    items = list(
        VentaDetalle.objects.select_for_update()
        .filter(venta=venta)
        .select_related("producto")
    )

    if not items:
        venta.subtotal = Decimal("0")
        venta.iva_total = Decimal("0")
        venta.total = Decimal("0")
        venta.save(update_fields=["subtotal", "iva_total", "total"])
        return venta

    descuento_pct = _to_decimal(venta.descuento_total)
    if descuento_pct < 0 or descuento_pct > 100:
        raise ValueError("El descuento debe estar entre 0 y 100.")

    subtotal = Decimal("0")
    iva_total = Decimal("0")
    for item in items:
        cantidad = _quantize_qty(item.cantidad)
        if cantidad <= 0:
            continue
        precio_unitario = _to_decimal(item.precio_unitario)
        descuento_unitario = _to_decimal(item.descuento_unitario)
        if descuento_unitario > precio_unitario:
            raise ValueError("El descuento unitario no puede superar el precio unitario.")
        iva = _validar_iva(item.iva)

        costo_unitario = _to_decimal(item.costo_unitario_en_venta)
        if costo_unitario <= 0:
            costo_unitario = _ultimo_costo_unitario(item.producto)
        costo_unitario = _quantize_cost(costo_unitario)

        line_bruto = (precio_unitario - descuento_unitario) * cantidad
        if iva > 0:
            line_subtotal = line_bruto / (Decimal("1") + iva)
            iva_linea = line_bruto - line_subtotal
        else:
            line_subtotal = line_bruto
            iva_linea = Decimal("0")
        line_subtotal = _quantize_money(line_subtotal)
        iva_linea = _quantize_money(iva_linea)
        total_linea = _quantize_money(line_bruto)
        if iva > 0:
            neto_unitario = (precio_unitario - descuento_unitario) / (Decimal("1") + iva)
        else:
            neto_unitario = precio_unitario - descuento_unitario
        ganancia_linea = _quantize_money((neto_unitario - costo_unitario) * cantidad)

        item.costo_unitario_en_venta = costo_unitario
        item.total_linea = total_linea
        item.ganancia_linea = ganancia_linea
        item.save(update_fields=["costo_unitario_en_venta", "total_linea", "ganancia_linea"])

        subtotal += line_subtotal
        iva_total += iva_linea

    subtotal = _quantize_money(subtotal)
    iva_total = _quantize_money(iva_total)
    descuento_valor = _quantize_money((subtotal + iva_total) * (descuento_pct / Decimal("100")))
    if descuento_valor > subtotal + iva_total:
        raise ValueError("El descuento no puede superar el total de la venta.")
    total = _quantize_money(subtotal + iva_total - descuento_valor)

    venta.subtotal = subtotal
    venta.iva_total = iva_total
    venta.total = total
    venta.save(update_fields=["subtotal", "iva_total", "total"])
    return venta
