from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from core.models import Inventario, MovimientoInventario

QTY_PRECISION = Decimal("1")
COST_PRECISION = Decimal("0.000001")


def _to_decimal(value):
    """Convierte a Decimal evitando errores de float."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize(value, precision):
    """Normaliza decimales a la precision indicada."""
    return _to_decimal(value).quantize(precision, rounding=ROUND_HALF_UP)


def _quantize_qty(value):
    """Valida y normaliza cantidades enteras."""
    cantidad = _to_decimal(value)
    if cantidad != cantidad.to_integral_value(rounding=ROUND_HALF_UP):
        raise ValueError("La cantidad debe ser un numero entero.")
    return cantidad.quantize(QTY_PRECISION, rounding=ROUND_HALF_UP)


def recalcular_saldo_movimiento(saldo_actual, entrada, salida):
    """Calcula el saldo de inventario luego de un movimiento."""
    saldo = _to_decimal(saldo_actual) + _to_decimal(entrada) - _to_decimal(salida)
    return _quantize(saldo, QTY_PRECISION)


def get_or_create_inventario(producto):
    """Obtiene o crea el inventario para un producto."""
    inventario, _ = Inventario.objects.get_or_create(
        producto=producto,
        defaults={"cantidad": Decimal("0")},
    )
    return inventario


def _obtener_inventario_bloqueado(producto):
    """Bloquea el inventario del producto para actualizacion."""
    try:
        return Inventario.objects.select_for_update().get(producto=producto)
    except Inventario.DoesNotExist:
        inventario = Inventario.objects.create(producto=producto, cantidad=Decimal("0"))
        return Inventario.objects.select_for_update().get(pk=inventario.pk)


def _normalizar_ref(ref):
    """Valida y normaliza la referencia del movimiento."""
    if not isinstance(ref, dict):
        raise ValueError("Referencia invalida.")
    tipo = ref.get("tipo")
    fecha = ref.get("fecha")
    if not tipo or not fecha:
        raise ValueError("Referencia incompleta.")
    return {
        "tipo": tipo,
        "fecha": fecha,
        "referencia": ref.get("referencia", ""),
        "referencia_id": ref.get("referencia_id"),
        "nota": ref.get("nota", ""),
    }


@transaction.atomic
def incrementar_stock(producto, qty, costo_unitario, ref):
    """Incrementa stock y registra el movimiento."""
    cantidad = _quantize_qty(qty)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    costo = _quantize(costo_unitario, COST_PRECISION)
    if costo < 0:
        raise ValueError("El costo unitario no puede ser negativo.")
    ref_data = _normalizar_ref(ref)

    inventario = _obtener_inventario_bloqueado(producto)
    nuevo_saldo = recalcular_saldo_movimiento(inventario.cantidad, cantidad, Decimal("0"))
    inventario.cantidad = nuevo_saldo
    inventario.save(update_fields=["cantidad", "actualizado_en"])

    MovimientoInventario.objects.create(
        producto=producto,
        fecha=ref_data["fecha"],
        tipo=ref_data["tipo"],
        referencia=ref_data["referencia"],
        referencia_id=ref_data["referencia_id"],
        entrada=cantidad,
        salida=Decimal("0"),
        costo_unitario=costo,
        saldo_cantidad=nuevo_saldo,
        nota=ref_data["nota"],
    )
    return inventario


@transaction.atomic
def decrementar_stock(producto, qty, costo_unitario, ref):
    """Decrementa stock, valida y registra el movimiento."""
    cantidad = _quantize_qty(qty)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    costo = _quantize(costo_unitario, COST_PRECISION)
    if costo < 0:
        raise ValueError("El costo unitario no puede ser negativo.")
    ref_data = _normalizar_ref(ref)

    inventario = _obtener_inventario_bloqueado(producto)
    if inventario.cantidad < cantidad:
        raise ValueError("Stock insuficiente para el producto.")
    nuevo_saldo = recalcular_saldo_movimiento(inventario.cantidad, Decimal("0"), cantidad)
    inventario.cantidad = nuevo_saldo
    inventario.save(update_fields=["cantidad", "actualizado_en"])

    MovimientoInventario.objects.create(
        producto=producto,
        fecha=ref_data["fecha"],
        tipo=ref_data["tipo"],
        referencia=ref_data["referencia"],
        referencia_id=ref_data["referencia_id"],
        entrada=Decimal("0"),
        salida=cantidad,
        costo_unitario=costo,
        saldo_cantidad=nuevo_saldo,
        nota=ref_data["nota"],
    )
    return inventario
