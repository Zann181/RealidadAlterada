from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db.models import DecimalField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms.ventas import VentaForm
from core.models import Categoria, Deudor, Inventario, Producto, Venta, VentaDetalle
from core.services import ventas as ventas_service
from core.services.inventario import decrementar_stock, incrementar_stock
from core.utils.numbers import parse_miles
from core.views.filters import apply_period_filter
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required


@panel_required
def venta_list(request):
    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    categorias = Categoria.objects.order_by("nombre")
    ventas = Venta.objects.select_related("deudor")
    if q:
        filtros = (
            Q(deudor__nombre__icontains=q)
            | Q(deudor__documento__icontains=q)
            | Q(medio_pago__icontains=q)
        )
        if q.isdigit():
            filtros |= Q(id=int(q))
        ventas = ventas.filter(filtros)
    if categoria_id:
        ventas = ventas.filter(items__producto__categoria_id=categoria_id).distinct()
    ventas, period, selected_date = apply_period_filter(request, ventas, "fecha")
    ventas = ventas.order_by("-fecha")
    pagination = paginate_queryset(request, ventas)
    return render(
        request,
        "core/ventas/ventas_list.html",
        {
            "ventas": pagination["page_obj"],
            "categorias": categorias,
            "categoria_id": str(categoria_id),
            "period": period,
            "fecha": selected_date.strftime("%Y-%m-%d"),
            **pagination,
        },
    )


@panel_required
def venta_create(request):
    if request.method == "POST":
        form = VentaForm(request.POST)
        accion = request.POST.get("accion")
        if form.is_valid():
            medio_pago = form.cleaned_data.get("medio_pago")
            if accion == "registrar_deudor":
                if medio_pago != "DEUDA":
                    messages.error(request, "Selecciona medio de pago Deuda para registrar un deudor.")
                    return render(request, "core/ventas/ventas_form.html", {"form": form})
                nuevo_nombre = form.cleaned_data.get("nuevo_deudor_nombre")
                if not nuevo_nombre:
                    messages.error(request, "Ingresa el nombre del deudor.")
                    return render(request, "core/ventas/ventas_form.html", {"form": form})
                deudor = Deudor.objects.create(
                    nombre=nuevo_nombre,
                    telefono=form.cleaned_data.get("nuevo_deudor_telefono", ""),
                    correo=form.cleaned_data.get("nuevo_deudor_correo", ""),
                    documento=form.cleaned_data.get("nuevo_deudor_documento", ""),
                    direccion=form.cleaned_data.get("nuevo_deudor_direccion", ""),
                )
                data = request.POST.copy()
                data["deudor"] = str(deudor.id)
                data["nuevo_deudor_nombre"] = ""
                data["nuevo_deudor_telefono"] = ""
                data["nuevo_deudor_correo"] = ""
                data["nuevo_deudor_documento"] = ""
                data["nuevo_deudor_direccion"] = ""
                form = VentaForm(data)
                messages.success(request, "Deudor registrado.")
                return render(request, "core/ventas/ventas_form.html", {"form": form})

            venta = form.save(commit=False)
            if not venta.fecha:
                venta.fecha = timezone.now()
            if medio_pago == "DEUDA":
                nuevo_nombre = form.cleaned_data.get("nuevo_deudor_nombre")
                if nuevo_nombre:
                    deudor = Deudor.objects.create(
                        nombre=nuevo_nombre,
                        telefono=form.cleaned_data.get("nuevo_deudor_telefono", ""),
                        correo=form.cleaned_data.get("nuevo_deudor_correo", ""),
                        documento=form.cleaned_data.get("nuevo_deudor_documento", ""),
                        direccion=form.cleaned_data.get("nuevo_deudor_direccion", ""),
                    )
                    venta.deudor = deudor
            else:
                venta.deudor = None
            venta.estado = "BORRADOR"
            venta.save()
            return redirect("core:ventas_detail", pk=venta.pk)
    else:
        form = VentaForm()
    return render(request, "core/ventas/ventas_form.html", {"form": form})


@panel_required
def venta_detail(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    items = list(venta.items.select_related("producto").all())
    items_por_producto = {}
    subtotal_calc = Decimal("0")
    iva_total_calc = Decimal("0")
    for item in items:
        cantidad = Decimal(item.cantidad or 0)
        precio_unitario = Decimal(item.precio_unitario or 0)
        descuento_unitario = Decimal(item.descuento_unitario or 0)
        iva = Decimal(item.iva or 0)
        line_bruto = (precio_unitario - descuento_unitario) * cantidad
        if iva > 0:
            line_subtotal = line_bruto / (Decimal("1") + iva)
            iva_linea = line_bruto - line_subtotal
        else:
            line_subtotal = line_bruto
            iva_linea = Decimal("0")
        line_total = line_bruto
        subtotal_calc += line_subtotal
        iva_total_calc += iva_linea
        data = items_por_producto.get(item.producto_id)
        if not data:
            items_por_producto[item.producto_id] = {
                "cantidad": cantidad,
                "total": line_total,
                "item": item,
            }
        else:
            data["cantidad"] += cantidad
            data["total"] += line_total
    stock_qs = (
        Inventario.objects.filter(producto=OuterRef("pk"))
        .values("cantidad")[:1]
    )
    productos = list(
        Producto.objects.filter(activo=True)
        .annotate(
            stock_actual=Coalesce(
                Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                Decimal("0.000"),
            )
        )
        .order_by("nombre")
    )
    productos_data = []
    for producto in productos:
        item_data = items_por_producto.get(producto.id)
        item = item_data["item"] if item_data else None
        if item is not None and item.iva is not None:
            iva_base = Decimal(item.iva) * Decimal("100")
        elif producto.iva is not None and Decimal(producto.iva) > 0:
            iva_base = Decimal(producto.iva) * Decimal("100")
        else:
            iva_base = Decimal("19")
        productos_data.append(
            {
                "producto": producto,
                "cantidad_en_venta": item_data["cantidad"] if item_data else Decimal("0"),
                "total_en_venta": item_data["total"] if item_data else Decimal("0"),
                "iva_pct": iva_base.quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            }
        )
    subtotal_calc = subtotal_calc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    iva_total_calc = iva_total_calc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    descuento_pct = Decimal(venta.descuento_total or 0)
    descuento_valor_calc = (subtotal_calc + iva_total_calc) * (
        descuento_pct / Decimal("100")
    )
    descuento_valor_calc = descuento_valor_calc.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_calc = (subtotal_calc + iva_total_calc - descuento_valor_calc).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if venta.estado == "BORRADOR":
        subtotal_display = subtotal_calc
        iva_total_display = iva_total_calc
        descuento_valor_display = descuento_valor_calc
        total_display = total_calc
    else:
        subtotal_display = venta.subtotal
        iva_total_display = venta.iva_total
        descuento_valor_display = None
        if venta.descuento_total:
            descuento_valor_display = (venta.subtotal + venta.iva_total) * (
                Decimal(venta.descuento_total) / Decimal("100")
            )
        total_display = venta.total
    return render(
        request,
        "core/ventas/ventas_detail.html",
        {
            "venta": venta,
            "items": items,
            "productos_data": productos_data,
            "subtotal_display": subtotal_display,
            "iva_total_display": iva_total_display,
            "descuento_valor_display": descuento_valor_display,
            "total_display": total_display,
        },
    )


@panel_required
def venta_print(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    items = list(venta.items.select_related("producto").all())
    lineas = []
    subtotal_calc = Decimal("0")
    iva_total_calc = Decimal("0")
    for item in items:
        cantidad = Decimal(item.cantidad or 0)
        precio_unitario = Decimal(item.precio_unitario or 0)
        descuento_unitario = Decimal(item.descuento_unitario or 0)
        iva = Decimal(item.iva or 0)
        line_bruto = (precio_unitario - descuento_unitario) * cantidad
        if iva > 0:
            line_subtotal = line_bruto / (Decimal("1") + iva)
            iva_linea = line_bruto - line_subtotal
        else:
            line_subtotal = line_bruto
            iva_linea = Decimal("0")
        lineas.append(
            {
                "item": item,
                "total_linea": line_bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            }
        )
        subtotal_calc += line_subtotal
        iva_total_calc += iva_linea

    subtotal_calc = subtotal_calc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    iva_total_calc = iva_total_calc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    descuento_pct = Decimal(venta.descuento_total or 0)
    descuento_valor_calc = (subtotal_calc + iva_total_calc) * (
        descuento_pct / Decimal("100")
    )
    descuento_valor_calc = descuento_valor_calc.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_calc = (subtotal_calc + iva_total_calc - descuento_valor_calc).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if venta.estado == "BORRADOR":
        subtotal_display = subtotal_calc
        iva_total_display = iva_total_calc
        descuento_valor_display = descuento_valor_calc
        total_display = total_calc
    else:
        subtotal_display = venta.subtotal
        iva_total_display = venta.iva_total
        descuento_valor_display = None
        if venta.descuento_total:
            descuento_valor_display = (venta.subtotal + venta.iva_total) * (
                Decimal(venta.descuento_total) / Decimal("100")
            )
        total_display = venta.total

    return render(
        request,
        "core/ventas/ventas_print.html",
        {
            "venta": venta,
            "items": items,
            "lineas": lineas,
            "subtotal_display": subtotal_display,
            "iva_total_display": iva_total_display,
            "descuento_valor_display": descuento_valor_display,
            "total_display": total_display,
        },
    )


@panel_required
@require_POST
def venta_add_item(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if venta.estado == "ANULADA":
        if is_ajax:
            return JsonResponse({"ok": False, "error": "No se puede modificar una venta ANULADA."}, status=400)
        messages.error(request, "No se puede modificar una venta ANULADA.")
        return redirect("core:ventas_detail", pk=venta.pk)

    accion = request.POST.get("accion", "agregar")
    producto_id = request.POST.get("producto")
    cantidad_raw = request.POST.get("cantidad")
    cantidad = parse_miles(cantidad_raw)
    iva_raw = request.POST.get("iva")
    iva_pct = parse_miles(iva_raw)

    if not producto_id:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Debe seleccionar un producto."}, status=400)
        messages.error(request, "Debe seleccionar un producto.")
        return redirect("core:ventas_detail", pk=venta.pk)

    if iva_pct is not None and (iva_pct < 0 or iva_pct > 100):
        if is_ajax:
            return JsonResponse({"ok": False, "error": "El IVA debe estar entre 0 y 100."}, status=400)
        messages.error(request, "El IVA debe estar entre 0 y 100.")
        return redirect("core:ventas_detail", pk=venta.pk)

    producto = get_object_or_404(Producto, pk=producto_id)
    items_qs = VentaDetalle.objects.filter(venta=venta, producto=producto).order_by("id")
    item = items_qs.first()
    if iva_pct is None:
        if producto.iva and Decimal(producto.iva) > 0:
            iva_pct = int(
                (Decimal(producto.iva) * Decimal("100")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
        else:
            iva_pct = 19
    iva_decimal = (Decimal(iva_pct) / Decimal("100")).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )

    if cantidad is not None and cantidad <= 0:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "La cantidad debe ser mayor a 0."}, status=400)
        messages.error(request, "La cantidad debe ser mayor a 0.")
        return redirect("core:ventas_detail", pk=venta.pk)

    try:
        with transaction.atomic():
            if cantidad is None:
                if item is None:
                    if is_ajax:
                        return JsonResponse(
                            {"ok": False, "error": "Debe indicar una cantidad para agregar el item."},
                            status=400,
                        )
                    messages.error(request, "Debe indicar una cantidad para agregar el item.")
                    return redirect("core:ventas_detail", pk=venta.pk)
                item.iva = iva_decimal
                item.save(update_fields=["iva"])
                if venta.estado == "CONFIRMADA":
                    ventas_service.venta_recalcular_totales(venta.id)
                if is_ajax:
                    return JsonResponse({"ok": True, "producto_id": producto.id})
                messages.success(request, "IVA actualizado.")
                return redirect("core:ventas_detail", pk=venta.pk)

            cantidad_decimal = Decimal(str(cantidad))
            if accion == "quitar":
                if item is None:
                    if is_ajax:
                        return JsonResponse({"ok": False, "error": "No hay item para quitar."}, status=400)
                    messages.error(request, "No hay item para quitar.")
                    return redirect("core:ventas_detail", pk=venta.pk)
                if cantidad_decimal > item.cantidad:
                    if is_ajax:
                        return JsonResponse(
                            {"ok": False, "error": "La cantidad supera lo vendido."}, status=400
                        )
                    messages.error(request, "La cantidad supera lo vendido.")
                    return redirect("core:ventas_detail", pk=venta.pk)

                costo_unitario = item.costo_unitario_en_venta
                if costo_unitario is None or costo_unitario <= 0:
                    costo_unitario = ventas_service._ultimo_costo_unitario(producto)
                    if costo_unitario <= 0:
                        costo_unitario = Decimal(producto.costo_compra or 0)
                inventario = incrementar_stock(
                    producto,
                    cantidad_decimal,
                    costo_unitario,
                    ref={
                        "tipo": "DEVOLUCION",
                        "fecha": venta.fecha,
                        "referencia": "venta",
                        "referencia_id": venta.id,
                        "nota": f"Ajuste venta #{venta.id}",
                    },
                )
                item.cantidad = Decimal(item.cantidad) - cantidad_decimal
                if item.cantidad <= 0:
                    item.delete()
                    nueva_cantidad = Decimal("0")
                else:
                    item.save(update_fields=["cantidad"])
                    nueva_cantidad = item.cantidad
                if venta.estado == "CONFIRMADA":
                    ventas_service.venta_recalcular_totales(venta.id)
                if is_ajax:
                    return JsonResponse(
                        {
                            "ok": True,
                            "producto_id": producto.id,
                            "cantidad": int(nueva_cantidad),
                            "stock": int(Decimal(inventario.cantidad).to_integral_value()),
                        }
                    )
                messages.success(request, "Item actualizado.")
                return redirect("core:ventas_detail", pk=venta.pk)

            if item:
                for extra in items_qs[1:]:
                    item.cantidad = Decimal(item.cantidad) + Decimal(extra.cantidad)
                    extra.delete()
                costo_unitario = item.costo_unitario_en_venta
                if costo_unitario is None or costo_unitario <= 0:
                    costo_unitario = ventas_service._ultimo_costo_unitario(producto)
                    if costo_unitario <= 0:
                        costo_unitario = Decimal(producto.costo_compra or 0)
                inventario = decrementar_stock(
                    producto,
                    cantidad_decimal,
                    costo_unitario,
                    ref={
                        "tipo": "VENTA",
                        "fecha": venta.fecha,
                        "referencia": "venta",
                        "referencia_id": venta.id,
                        "nota": f"Ajuste venta #{venta.id}",
                    },
                )
                item.cantidad = Decimal(item.cantidad) + cantidad_decimal
                if item.precio_unitario <= 0:
                    item.precio_unitario = Decimal(producto.precio_venta or 0)
                item.iva = iva_decimal
                item.total_linea = Decimal("0")
                item.ganancia_linea = Decimal("0")
                item.save(
                    update_fields=[
                        "cantidad",
                        "precio_unitario",
                        "iva",
                        "total_linea",
                        "ganancia_linea",
                    ]
                )
                if venta.estado == "CONFIRMADA":
                    if item.costo_unitario_en_venta is None or item.costo_unitario_en_venta <= 0:
                        item.costo_unitario_en_venta = costo_unitario
                        item.save(update_fields=["costo_unitario_en_venta"])
                    ventas_service.venta_recalcular_totales(venta.id)
                if is_ajax:
                    return JsonResponse(
                        {
                            "ok": True,
                            "producto_id": producto.id,
                            "cantidad": int(item.cantidad),
                            "stock": int(Decimal(inventario.cantidad).to_integral_value()),
                        }
                    )
                messages.success(request, "Cantidad actualizada en la venta.")
                return redirect("core:ventas_detail", pk=venta.pk)

            costo_unitario = ventas_service._ultimo_costo_unitario(producto)
            if costo_unitario <= 0:
                costo_unitario = Decimal(producto.costo_compra or 0)
            inventario = decrementar_stock(
                producto,
                cantidad_decimal,
                costo_unitario,
                ref={
                    "tipo": "VENTA",
                    "fecha": venta.fecha,
                    "referencia": "venta",
                    "referencia_id": venta.id,
                    "nota": f"Ajuste venta #{venta.id}",
                },
            )
            nuevo_item = VentaDetalle.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad_decimal,
                precio_unitario=Decimal(producto.precio_venta or 0),
                descuento_unitario=Decimal("0"),
                iva=iva_decimal,
                costo_unitario_en_venta=costo_unitario,
                total_linea=Decimal("0"),
                ganancia_linea=Decimal("0"),
            )
            if venta.estado == "CONFIRMADA":
                ventas_service.venta_recalcular_totales(venta.id)
            if is_ajax:
                return JsonResponse(
                    {
                        "ok": True,
                        "producto_id": producto.id,
                        "cantidad": int(nuevo_item.cantidad),
                        "stock": int(Decimal(inventario.cantidad).to_integral_value()),
                    }
                )
            messages.success(request, "Item agregado a la venta.")
            return redirect("core:ventas_detail", pk=venta.pk)
    except Exception as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, f"No se pudo actualizar la venta: {exc}")
        return redirect("core:ventas_detail", pk=venta.pk)


@panel_required
@require_POST
def venta_update_descuento(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    if venta.estado == "ANULADA":
        return JsonResponse({"ok": False, "error": "Venta anulada."}, status=400)
    descuento_raw = request.POST.get("descuento_total")
    descuento = parse_miles(descuento_raw)
    if descuento is None:
        descuento = 0
    if descuento < 0 or descuento > 100:
        return JsonResponse({"ok": False, "error": "Descuento invalido."}, status=400)
    venta.descuento_total = descuento
    venta.save(update_fields=["descuento_total"])
    if venta.estado == "CONFIRMADA":
        try:
            ventas_service.venta_recalcular_totales(venta.id)
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True})


@panel_required
@require_POST
def venta_update_iva(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    if venta.estado == "ANULADA":
        return JsonResponse({"ok": False, "error": "Venta anulada."}, status=400)
    producto_id = request.POST.get("producto")
    iva_raw = request.POST.get("iva")
    iva_pct = parse_miles(iva_raw)
    if not producto_id or iva_pct is None:
        return JsonResponse({"ok": False, "error": "Datos incompletos."}, status=400)
    if iva_pct < 0 or iva_pct > 100:
        return JsonResponse({"ok": False, "error": "IVA invalido."}, status=400)
    item = (
        VentaDetalle.objects.filter(venta=venta, producto_id=producto_id)
        .order_by("id")
        .first()
    )
    if not item:
        return JsonResponse({"ok": False, "error": "Item no existe."}, status=404)
    iva_decimal = (Decimal(iva_pct) / Decimal("100")).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    item.iva = iva_decimal
    item.save(update_fields=["iva"])
    if venta.estado == "CONFIRMADA":
        try:
            ventas_service.venta_recalcular_totales(venta.id)
        except Exception as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True})


@panel_required
@require_POST
def venta_confirm(request, pk):
    try:
        ventas_service.venta_confirmar(pk, usuario=request.user)
        messages.success(request, "Venta confirmada.")
    except Exception as exc:
        messages.error(request, f"No se pudo confirmar la venta: {exc}")
    return redirect("core:ventas_detail", pk=pk)


@panel_required
@require_POST
def venta_cancel(request, pk):
    try:
        ventas_service.venta_anular(pk, usuario=request.user)
        messages.success(request, "Venta anulada.")
    except Exception as exc:
        messages.error(request, f"No se pudo anular la venta: {exc}")
    return redirect("core:ventas_detail", pk=pk)


@panel_required
@require_POST
def venta_delete(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    if venta.estado != "BORRADOR":
        messages.error(request, "Solo se puede eliminar una venta en BORRADOR.")
        return redirect("core:ventas_detail", pk=pk)
    try:
        with transaction.atomic():
            items = list(
                VentaDetalle.objects.select_for_update()
                .filter(venta=venta)
                .select_related("producto")
            )
            for item in items:
                costo_unitario = item.costo_unitario_en_venta
                if costo_unitario is None or costo_unitario <= 0:
                    costo_unitario = ventas_service._ultimo_costo_unitario(item.producto)
                    if costo_unitario <= 0:
                        costo_unitario = Decimal(item.producto.costo_compra or 0)
                incrementar_stock(
                    item.producto,
                    item.cantidad,
                    costo_unitario,
                    ref={
                        "tipo": "DEVOLUCION",
                        "fecha": venta.fecha,
                        "referencia": "venta_borrador",
                        "referencia_id": venta.id,
                        "nota": f"Eliminacion venta borrador #{venta.id}",
                    },
                )
            venta.delete()
        messages.success(request, "Venta borrador eliminada.")
    except Exception as exc:
        messages.error(request, f"No se pudo eliminar la venta: {exc}")
        return redirect("core:ventas_detail", pk=pk)
    return redirect("core:ventas_list")


@panel_required
@require_POST
def venta_update_totales(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    if venta.estado == "ANULADA":
        messages.error(request, "No se puede actualizar una venta ANULADA.")
        return redirect("core:ventas_detail", pk=pk)
    try:
        ventas_service.venta_recalcular_totales(venta.id)
        messages.success(request, "Factura actualizada.")
    except Exception as exc:
        messages.error(request, f"No se pudo actualizar la factura: {exc}")
    return redirect("core:ventas_detail", pk=pk)
