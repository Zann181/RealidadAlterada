from datetime import datetime, time
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms.deudas import (
    AbonoClienteRapidoForm,
    AbonoDeudaClienteForm,
    AbonoDeudaProveedorForm,
    DeudaAntiguaForm,
    DeudaClienteDetalleForm,
    DeudaClienteForm,
    DeudaProveedorDetalleForm,
    DeudaProveedorForm,
    DeudorForm,
)
from core.models import AbonoDeudaCliente, DeudaCliente, DeudaProveedor, Deudor
from core.services import deudas as deudas_service
from core.views.filters import apply_period_filter
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required


@panel_required
def deudor_list(request):
    deudores = Deudor.objects.order_by("nombre")
    pagination = paginate_queryset(request, deudores)
    return render(
        request,
        "core/deudas/deudores_list.html",
        {"deudores": pagination["page_obj"], **pagination},
    )


@panel_required
def deudor_create(request):
    form = DeudorForm(request.POST or None)
    deuda_form = DeudaAntiguaForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and deuda_form.is_valid():
        deudor = form.save()
        valor = deuda_form.cleaned_data.get("valor")
        if valor and valor > 0:
            fecha = deuda_form.cleaned_data.get("fecha")
            if fecha is None:
                fecha = timezone.localdate()
                fecha = timezone.make_aware(datetime.combine(fecha, time.min))
            descripcion = deuda_form.cleaned_data.get("descripcion", "")
            DeudaCliente.objects.create(
                deudor=deudor,
                fecha=fecha,
                estado="ABIERTA",
                total_inicial=Decimal(valor),
                saldo_actual=Decimal(valor),
                descripcion=descripcion or "",
            )
        messages.success(request, "Deudor creado.")
        return redirect("core:deudores_detail", pk=deudor.pk)
    return render(
        request,
        "core/deudas/deudores_form.html",
        {"form": form, "deuda_form": deuda_form},
    )


@panel_required
def deudor_update(request, pk):
    deudor = get_object_or_404(Deudor, pk=pk)
    form = DeudorForm(request.POST or None, instance=deudor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Deudor actualizado.")
        return redirect("core:deudores_detail", pk=deudor.pk)
    return render(request, "core/deudas/deudores_form.html", {"form": form, "deudor": deudor})


@panel_required
def deudor_detail(request, pk):
    deudor = get_object_or_404(Deudor, pk=pk)
    deudas = deudor.deudas.order_by("-fecha")
    abono_form = AbonoClienteRapidoForm()
    abono_form.fields["deuda"].queryset = deudas.filter(estado="ABIERTA")
    abonos = (
        AbonoDeudaCliente.objects.select_related("deuda")
        .filter(deuda__deudor=deudor)
        .order_by("-fecha")[:20]
    )
    return render(
        request,
        "core/deudas/deudores_detail.html",
        {"deudor": deudor, "deudas": deudas, "abono_form": abono_form, "abonos": abonos},
    )


@panel_required
@require_POST
def deudor_add_abono(request, pk):
    deudor = get_object_or_404(Deudor, pk=pk)
    form = AbonoClienteRapidoForm(request.POST)
    form.fields["deuda"].queryset = DeudaCliente.objects.filter(deudor=deudor, estado="ABIERTA")
    if form.is_valid():
        data = form.cleaned_data
        deuda = data["deuda"]
        try:
            deudas_service.agregar_abono_deuda_cliente(
                deuda.id,
                fecha=data["fecha"] or timezone.now(),
                valor=data["valor"],
                medio_pago=data.get("medio_pago") or "OTRO",
                referencia=data.get("referencia", ""),
                nota=data.get("nota", ""),
            )
            messages.success(request, "Abono registrado.")
        except Exception as exc:
            messages.error(request, f"No se pudo registrar el abono: {exc}")
    else:
        messages.error(request, "Formulario de abono invalido.")
    return redirect("core:deudores_detail", pk=deudor.pk)


@panel_required
def deuda_cliente_create(request, deudor_id):
    deudor = get_object_or_404(Deudor, pk=deudor_id)
    form = DeudaClienteForm(request.POST or None)
    form.fields["deudor"].initial = deudor
    form.fields["deudor"].disabled = True
    if request.method == "POST" and form.is_valid():
        deuda = form.save(commit=False)
        deuda.deudor = deudor
        deuda.estado = "ABIERTA"
        deuda.save()
        messages.success(request, "Deuda creada.")
        return redirect("core:deuda_cliente_detail", pk=deuda.pk)
    return render(
        request,
        "core/deudas/deuda_form.html",
        {"form": form, "deudor": deudor},
    )


@panel_required
def deuda_cliente_detail(request, pk):
    deuda = get_object_or_404(DeudaCliente, pk=pk)
    items = deuda.items.select_related("producto").all()
    abonos = deuda.abonos.order_by("-fecha")
    item_form = DeudaClienteDetalleForm()
    abono_form = AbonoDeudaClienteForm()
    return render(
        request,
        "core/deudas/deuda_detail.html",
        {
            "deuda": deuda,
            "items": items,
            "abonos": abonos,
            "item_form": item_form,
            "abono_form": abono_form,
        },
    )


@panel_required
@require_POST
def deuda_cliente_add_item(request, pk):
    deuda = get_object_or_404(DeudaCliente, pk=pk)
    form = DeudaClienteDetalleForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            deudas_service.agregar_item_deuda_cliente(
                deuda.id,
                producto=data["producto"],
                cantidad=data["cantidad"],
                precio_unitario_inicial=data["precio_unitario_inicial"],
                iva=data["iva"],
            )
            messages.success(request, "Item agregado.")
        except Exception as exc:
            messages.error(request, f"No se pudo agregar el item: {exc}")
    else:
        messages.error(request, "Formulario de item invalido.")
    return redirect("core:deuda_cliente_detail", pk=deuda.pk)


@panel_required
@require_POST
def deuda_cliente_add_abono(request, pk):
    deuda = get_object_or_404(DeudaCliente, pk=pk)
    form = AbonoDeudaClienteForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            deudas_service.agregar_abono_deuda_cliente(
                deuda.id,
                fecha=data["fecha"],
                valor=data["valor"],
                medio_pago=data["medio_pago"],
                referencia=data.get("referencia", ""),
                nota=data.get("nota", ""),
            )
            messages.success(request, "Abono registrado.")
        except Exception as exc:
            messages.error(request, f"No se pudo registrar el abono: {exc}")
    else:
        messages.error(request, "Formulario de abono invalido.")
    return redirect("core:deuda_cliente_detail", pk=deuda.pk)


@panel_required
@require_POST
def deuda_cliente_cerrar(request, pk):
    deuda = get_object_or_404(DeudaCliente, pk=pk)
    try:
        deudas_service.cerrar_deuda_cliente(deuda.id)
        messages.success(request, "Deuda cerrada.")
    except Exception as exc:
        messages.error(request, f"No se pudo cerrar la deuda: {exc}")
    return redirect("core:deuda_cliente_detail", pk=deuda.pk)


@panel_required
def deuda_proveedor_list(request):
    deudas = DeudaProveedor.objects.select_related("proveedor")
    deudas, period, selected_date = apply_period_filter(request, deudas, "fecha")
    deudas = deudas.order_by("-fecha")
    pagination = paginate_queryset(request, deudas)
    return render(
        request,
        "core/proveedores_deudas/deudas_list.html",
        {
            "deudas": pagination["page_obj"],
            "period": period,
            "fecha": selected_date.strftime("%Y-%m-%d"),
            **pagination,
        },
    )


@panel_required
def deuda_proveedor_create(request):
    form = DeudaProveedorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        deuda = form.save(commit=False)
        deuda.estado = "ABIERTA"
        deuda.save()
        messages.success(request, "Deuda creada.")
        return redirect("core:deuda_proveedor_detail", pk=deuda.pk)
    return render(request, "core/proveedores_deudas/deuda_form.html", {"form": form})


@panel_required
def deuda_proveedor_detail(request, pk):
    deuda = get_object_or_404(DeudaProveedor, pk=pk)
    items = deuda.items.select_related("producto").all()
    abonos = deuda.abonos.order_by("-fecha")
    item_form = DeudaProveedorDetalleForm()
    abono_form = AbonoDeudaProveedorForm()
    return render(
        request,
        "core/proveedores_deudas/deuda_detail.html",
        {
            "deuda": deuda,
            "items": items,
            "abonos": abonos,
            "item_form": item_form,
            "abono_form": abono_form,
        },
    )


@panel_required
@require_POST
def deuda_proveedor_add_item(request, pk):
    deuda = get_object_or_404(DeudaProveedor, pk=pk)
    form = DeudaProveedorDetalleForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            deudas_service.agregar_item_deuda_proveedor(
                deuda.id,
                producto=data["producto"],
                cantidad=data["cantidad"],
                costo_unitario_inicial=data["costo_unitario_inicial"],
                iva=data["iva"],
            )
            messages.success(request, "Item agregado.")
        except Exception as exc:
            messages.error(request, f"No se pudo agregar el item: {exc}")
    else:
        messages.error(request, "Formulario de item invalido.")
    return redirect("core:deuda_proveedor_detail", pk=deuda.pk)


@panel_required
@require_POST
def deuda_proveedor_add_abono(request, pk):
    deuda = get_object_or_404(DeudaProveedor, pk=pk)
    form = AbonoDeudaProveedorForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            deudas_service.agregar_abono_deuda_proveedor(
                deuda.id,
                fecha=data["fecha"],
                valor=data["valor"],
                medio_pago=data["medio_pago"],
                referencia=data.get("referencia", ""),
                nota=data.get("nota", ""),
            )
            messages.success(request, "Abono registrado.")
        except Exception as exc:
            messages.error(request, f"No se pudo registrar el abono: {exc}")
    else:
        messages.error(request, "Formulario de abono invalido.")
    return redirect("core:deuda_proveedor_detail", pk=deuda.pk)


@panel_required
@require_POST
def deuda_proveedor_cerrar(request, pk):
    deuda = get_object_or_404(DeudaProveedor, pk=pk)
    try:
        deudas_service.cerrar_deuda_proveedor(deuda.id)
        messages.success(request, "Deuda cerrada.")
    except Exception as exc:
        messages.error(request, f"No se pudo cerrar la deuda: {exc}")
    return redirect("core:deuda_proveedor_detail", pk=deuda.pk)
