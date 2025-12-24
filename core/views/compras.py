from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms.compras import CompraForm, CompraDetalleForm
from core.models import Categoria, Compra, DeudaProveedor
from core.services import compras as compras_service
from core.services import deudas as deudas_service
from core.utils.numbers import parse_miles
from core.views.filters import apply_period_filter
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required

MONEY_PRECISION = Decimal("0.01")


def _quantize_money(value):
    return Decimal(str(value)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _calcular_totales_items(items):
    subtotal_calc = Decimal("0")
    iva_total_calc = Decimal("0")
    for item in items:
        cantidad = Decimal(item.cantidad or 0)
        costo_unitario = Decimal(item.costo_unitario or 0)
        iva = Decimal(item.iva or 0)
        line_subtotal = cantidad * costo_unitario
        iva_linea = line_subtotal * iva
        subtotal_calc += line_subtotal
        iva_total_calc += iva_linea
    subtotal_calc = _quantize_money(subtotal_calc)
    iva_total_calc = _quantize_money(iva_total_calc)
    return subtotal_calc, iva_total_calc


@panel_required
def compra_list(request):
    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    categorias = Categoria.objects.order_by("nombre")
    compras = Compra.objects.select_related("proveedor")
    if q:
        filtros = Q(proveedor__nombre__icontains=q) | Q(numero_factura__icontains=q)
        if q.isdigit():
            filtros |= Q(id=int(q))
        compras = compras.filter(filtros)
    if categoria_id:
        compras = compras.filter(items__producto__categoria_id=categoria_id).distinct()
    compras, period, selected_date = apply_period_filter(request, compras, "fecha")
    compras = compras.order_by("-fecha")
    pagination = paginate_queryset(request, compras)
    return render(
        request,
        "core/compras/compras_list.html",
        {
            "compras": pagination["page_obj"],
            "categorias": categorias,
            "categoria_id": str(categoria_id),
            "period": period,
            "fecha": selected_date.strftime("%Y-%m-%d"),
            **pagination,
        },
    )


@panel_required
def compra_create(request):
    if request.method == "POST":
        form = CompraForm(request.POST)
    else:
        form = CompraForm(initial={"fecha": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        compra = form.save(commit=False)
        compra.estado = "BORRADOR"
        compra.save()
        return redirect("core:compras_detail", pk=compra.pk)
    return render(request, "core/compras/compras_form.html", {"form": form})


@panel_required
def compra_detail(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    items = list(compra.items.select_related("producto").all())
    items_data = []
    for item in items:
        cantidad = Decimal(item.cantidad or 0)
        costo_unitario = Decimal(item.costo_unitario or 0)
        iva = Decimal(item.iva or 0)
        line_subtotal = cantidad * costo_unitario
        iva_linea = line_subtotal * iva
        line_total = line_subtotal + iva_linea
        line_total = _quantize_money(line_total)
        items_data.append({"item": item, "total_linea": line_total})
    subtotal_calc, iva_total_calc = _calcular_totales_items(items)
    otros_costos = _quantize_money(compra.otros_costos or 0)
    total_calc = _quantize_money(subtotal_calc + iva_total_calc + otros_costos)

    if compra.estado == "BORRADOR":
        subtotal_display = subtotal_calc
        iva_total_display = iva_total_calc
        total_display = total_calc
    else:
        subtotal_display = compra.subtotal
        iva_total_display = compra.iva_total
        total_display = compra.total

    deuda_numero = compra.numero_factura or f"COMPRA-{compra.id}"
    deuda_existente = (
        DeudaProveedor.objects.filter(proveedor=compra.proveedor, numero_factura=deuda_numero)
        .order_by("-fecha")
        .first()
    )
    sena_inicial = total_display
    saldo_inicial = _quantize_money(total_display - sena_inicial)
    form = CompraDetalleForm()
    return render(
        request,
        "core/compras/compras_detail.html",
        {
            "compra": compra,
            "items": items,
            "items_data": items_data,
            "form": form,
            "subtotal_display": subtotal_display,
            "iva_total_display": iva_total_display,
            "total_display": total_display,
            "deuda_existente": deuda_existente,
            "sena_inicial": sena_inicial,
            "saldo_inicial": saldo_inicial,
        },
    )


@panel_required
@require_POST
def compra_add_item(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    form = CompraDetalleForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.compra = compra
        cantidad = Decimal(item.cantidad or 0)
        costo_unitario = Decimal(item.costo_unitario or 0)
        iva = Decimal(item.iva or 0)
        line_subtotal = cantidad * costo_unitario
        line_total = line_subtotal + (line_subtotal * iva)
        item.total_linea = _quantize_money(line_total)
        item.save()
    return redirect("core:compras_detail", pk=compra.pk)


@panel_required
@require_POST
def compra_confirm(request, pk):
    try:
        compras_service.compra_confirmar(pk, usuario=request.user)
        messages.success(request, "Compra confirmada.")
    except Exception as exc:
        messages.error(request, f"No se pudo confirmar la compra: {exc}")
    return redirect("core:compras_detail", pk=pk)


@panel_required
@require_POST
def compra_cancel(request, pk):
    try:
        compras_service.compra_anular(pk, usuario=request.user)
        messages.success(request, "Compra anulada.")
    except Exception as exc:
        messages.error(request, f"No se pudo anular la compra: {exc}")
    return redirect("core:compras_detail", pk=pk)


@panel_required
@require_POST
def compra_crear_deuda(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    if compra.estado == "ANULADA":
        messages.error(request, "No se puede crear una deuda desde una compra anulada.")
        return redirect("core:compras_detail", pk=pk)

    items = list(compra.items.select_related("producto").all())
    if not items:
        messages.error(request, "La compra no tiene items.")
        return redirect("core:compras_detail", pk=pk)

    deuda_numero = compra.numero_factura or f"COMPRA-{compra.id}"
    existente = DeudaProveedor.objects.filter(
        proveedor=compra.proveedor,
        numero_factura=deuda_numero,
    ).first()
    if existente:
        messages.warning(request, "Ya existe una deuda registrada para esta compra.")
        return redirect("core:deuda_proveedor_detail", pk=existente.pk)

    sena = parse_miles(request.POST.get("sena"))
    if sena is None:
        sena = 0
    sena_decimal = Decimal(str(sena))
    if compra.estado == "CONFIRMADA" and Decimal(compra.total or 0) > 0:
        total_base = Decimal(compra.total or 0)
    else:
        subtotal_calc, iva_total_calc = _calcular_totales_items(items)
        otros_costos = _quantize_money(compra.otros_costos or 0)
        total_base = _quantize_money(subtotal_calc + iva_total_calc + otros_costos)
    if total_base <= 0:
        messages.error(request, "La compra no tiene un total valido.")
        return redirect("core:compras_detail", pk=pk)
    if sena_decimal < 0 or sena_decimal >= total_base:
        messages.error(request, "La seña debe ser menor al total de la compra.")
        return redirect("core:compras_detail", pk=pk)

    try:
        with transaction.atomic():
            deuda = DeudaProveedor.objects.create(
                proveedor=compra.proveedor,
                fecha=compra.fecha,
                numero_factura=deuda_numero,
                descripcion=f"Deuda generada desde compra #{compra.id}",
                estado="ABIERTA",
            )
            for item in items:
                deudas_service.agregar_item_deuda_proveedor(
                    deuda.id,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    costo_unitario_inicial=item.costo_unitario,
                    iva=item.iva,
                )
            if sena_decimal > 0:
                deudas_service.agregar_abono_deuda_proveedor(
                    deuda.id,
                    fecha=compra.fecha,
                    valor=sena_decimal,
                    medio_pago="OTRO",
                    referencia=f"Seña compra #{compra.id}",
                    nota="Seña registrada desde compras.",
                )
        messages.success(request, "Deuda creada para el proveedor.")
        return redirect("core:deuda_proveedor_detail", pk=deuda.pk)
    except Exception as exc:
        messages.error(request, f"No se pudo crear la deuda: {exc}")
        return redirect("core:compras_detail", pk=pk)
