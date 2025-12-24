from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Count, Sum

from core.models import (
    AbonoDeudaCliente,
    AbonoDeudaProveedor,
    DeudaCliente,
    DeudaClienteDetalle,
    DeudaProveedor,
    DeudaProveedorDetalle,
)

MONEY_PRECISION = Decimal("0.01")
QTY_PRECISION = Decimal("1")


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_money(value):
    return _to_decimal(value).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _quantize_qty(value):
    cantidad = _to_decimal(value)
    if cantidad != cantidad.to_integral_value(rounding=ROUND_HALF_UP):
        raise ValueError("La cantidad debe ser un numero entero.")
    return cantidad.quantize(QTY_PRECISION, rounding=ROUND_HALF_UP)


def _validar_iva(iva):
    iva_decimal = _to_decimal(iva)
    if iva_decimal < 0 or iva_decimal > 1:
        raise ValueError("El IVA debe estar entre 0 y 1.")
    return iva_decimal


def _calcular_total_linea(cantidad, precio_unitario, iva):
    subtotal = _quantize_money(cantidad * precio_unitario)
    total = subtotal + _quantize_money(subtotal * iva)
    return _quantize_money(total)


def _actualizar_totales_deuda_cliente(deuda):
    items_data = deuda.items.aggregate(total=Sum("total_linea"), count=Count("id"))
    items_total = items_data.get("total") or Decimal("0")
    items_count = items_data.get("count") or 0
    abonos_total = (
        deuda.abonos.aggregate(total=Sum("valor")).get("total") or Decimal("0")
    )
    if items_count == 0 and deuda.total_inicial:
        total_inicial = _quantize_money(deuda.total_inicial)
    else:
        total_inicial = _quantize_money(items_total)
    saldo_actual = _quantize_money(total_inicial - abonos_total)
    if saldo_actual < 0:
        saldo_actual = Decimal("0.00")
    if deuda.estado == "ABIERTA" and total_inicial > 0 and saldo_actual <= 0:
        deuda.estado = "CERRADA"
    deuda.total_inicial = total_inicial
    deuda.saldo_actual = saldo_actual
    deuda.save(update_fields=["total_inicial", "saldo_actual", "estado"])


def _actualizar_totales_deuda_proveedor(deuda):
    items_total = (
        deuda.items.aggregate(total=Sum("total_linea")).get("total") or Decimal("0")
    )
    abonos_total = (
        deuda.abonos.aggregate(total=Sum("valor")).get("total") or Decimal("0")
    )
    total_inicial = _quantize_money(items_total)
    saldo_actual = _quantize_money(total_inicial - abonos_total)
    if saldo_actual < 0:
        saldo_actual = Decimal("0.00")
    if deuda.estado == "ABIERTA" and total_inicial > 0 and saldo_actual <= 0:
        deuda.estado = "CERRADA"
    deuda.total_inicial = total_inicial
    deuda.saldo_actual = saldo_actual
    deuda.save(update_fields=["total_inicial", "saldo_actual", "estado"])


@transaction.atomic
def agregar_item_deuda_cliente(deuda_id, *, producto, cantidad, precio_unitario_inicial, iva):
    deuda = DeudaCliente.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")

    cantidad = _quantize_qty(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    precio = _quantize_money(precio_unitario_inicial)
    if precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    iva = _validar_iva(iva)

    total_linea = _calcular_total_linea(cantidad, precio, iva)
    item = DeudaClienteDetalle.objects.create(
        deuda=deuda,
        producto=producto,
        cantidad=cantidad,
        precio_unitario_inicial=precio,
        iva=iva,
        total_linea=total_linea,
    )
    _actualizar_totales_deuda_cliente(deuda)
    return item


@transaction.atomic
def agregar_abono_deuda_cliente(deuda_id, *, fecha, valor, medio_pago, referencia="", nota=""):
    deuda = DeudaCliente.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")
    valor = _quantize_money(valor)
    if valor <= 0:
        raise ValueError("El abono debe ser mayor a 0.")

    abono = AbonoDeudaCliente.objects.create(
        deuda=deuda,
        fecha=fecha,
        valor=valor,
        medio_pago=medio_pago,
        referencia=referencia or "",
        nota=nota or "",
    )
    _actualizar_totales_deuda_cliente(deuda)
    return abono


@transaction.atomic
def cerrar_deuda_cliente(deuda_id):
    deuda = DeudaCliente.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")
    deuda.estado = "CERRADA"
    deuda.save(update_fields=["estado"])
    return deuda


@transaction.atomic
def agregar_item_deuda_proveedor(deuda_id, *, producto, cantidad, costo_unitario_inicial, iva):
    deuda = DeudaProveedor.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")

    cantidad = _quantize_qty(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")
    costo = _quantize_money(costo_unitario_inicial)
    if costo < 0:
        raise ValueError("El costo no puede ser negativo.")
    iva = _validar_iva(iva)

    total_linea = _calcular_total_linea(cantidad, costo, iva)
    item = DeudaProveedorDetalle.objects.create(
        deuda=deuda,
        producto=producto,
        cantidad=cantidad,
        costo_unitario_inicial=costo,
        iva=iva,
        total_linea=total_linea,
    )
    _actualizar_totales_deuda_proveedor(deuda)
    return item


@transaction.atomic
def agregar_abono_deuda_proveedor(deuda_id, *, fecha, valor, medio_pago, referencia="", nota=""):
    deuda = DeudaProveedor.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")
    valor = _quantize_money(valor)
    if valor <= 0:
        raise ValueError("El abono debe ser mayor a 0.")

    abono = AbonoDeudaProveedor.objects.create(
        deuda=deuda,
        fecha=fecha,
        valor=valor,
        medio_pago=medio_pago,
        referencia=referencia or "",
        nota=nota or "",
    )
    _actualizar_totales_deuda_proveedor(deuda)
    return abono


@transaction.atomic
def cerrar_deuda_proveedor(deuda_id):
    deuda = DeudaProveedor.objects.select_for_update().get(pk=deuda_id)
    if deuda.estado != "ABIERTA":
        raise ValueError("La deuda no esta abierta.")
    deuda.estado = "CERRADA"
    deuda.save(update_fields=["estado"])
    return deuda
