import re
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Venta, VentaDetalle, VentaWeb, VentaWebItem
from core.services.inventario import decrementar_stock
from core.services import ventas as ventas_service
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required


@panel_required
def referidos_whatsapp_view(request):
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    referidos = VentaWeb.objects.all()
    if q:
        referidos = referidos.filter(
            Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(correo__icontains=q)
        )
    if estado:
        referidos = referidos.filter(estado=estado)

    referidos = (
        referidos.annotate(items_count=Count("items"))
        .order_by("-creado_en")
    )
    pagination = paginate_queryset(request, referidos)
    page_obj = pagination["page_obj"]
    borrador_ids = []
    for venta_web in page_obj:
        borrador_id = _extract_borrador_id(getattr(venta_web, "nota", "") or "")
        venta_web.venta_borrador_id = borrador_id
        if borrador_id:
            borrador_ids.append(borrador_id)
    existentes = set()
    if borrador_ids:
        existentes = set(Venta.objects.filter(id__in=borrador_ids).values_list("id", flat=True))
    for venta_web in page_obj:
        borrador_id = getattr(venta_web, "venta_borrador_id", None)
        venta_web.venta_borrador_exists = bool(borrador_id and borrador_id in existentes)

    return render(
        request,
        "core/referidos/whatsapp.html",
        {
            "referidos": pagination["page_obj"],
            "q": q,
            "estado": estado,
            "estado_choices": VentaWeb.ESTADO_CHOICES,
            **pagination,
        },
    )


_BORRADOR_TOKEN_RE = re.compile(r"\[VENTA_BORRADOR:(\d+)\]")


def _extract_borrador_id(nota):
    if not nota:
        return None
    match = _BORRADOR_TOKEN_RE.search(nota)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


@panel_required
@require_POST
def referidos_whatsapp_convertir_borrador(request, pk):
    try:
        with transaction.atomic():
            venta_web = VentaWeb.objects.select_for_update().get(pk=pk)
            existente_id = _extract_borrador_id(venta_web.nota or "")
            if existente_id and Venta.objects.filter(pk=existente_id).exists():
                messages.info(request, f"Este referido ya tiene una venta borrador #{existente_id}.")
                return redirect("core:ventas_detail", pk=existente_id)

            if venta_web.estado in {"ANULADA", "CERRADA"}:
                messages.error(request, "Este referido ya no esta pendiente.")
                return redirect("core:referidos_whatsapp")

            items = list(
                VentaWebItem.objects.select_related("producto")
                .filter(venta=venta_web)
                .order_by("id")
            )
            if not items:
                messages.error(request, "El referido no tiene items.")
                return redirect("core:referidos_whatsapp")

            fecha = venta_web.creado_en or timezone.now()
            venta = Venta.objects.create(
                fecha=fecha,
                canal="WHATSAPP",
                medio_pago="OTRO",
                descuento_total=Decimal("0"),
                subtotal=Decimal("0"),
                iva_total=Decimal("0"),
                total=Decimal("0"),
                estado="BORRADOR",
            )

            for item in items:
                producto = item.producto
                cantidad = Decimal(str(item.cantidad or 0))
                iva = Decimal(str(getattr(producto, "iva", 0) or 0))
                costo_unitario = ventas_service._ultimo_costo_unitario(producto)
                if costo_unitario <= 0:
                    costo_unitario = Decimal(str(getattr(producto, "costo_compra", 0) or 0))

                VentaDetalle.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=Decimal(str(item.precio_unitario or 0)),
                    descuento_unitario=Decimal("0"),
                    iva=iva,
                    costo_unitario_en_venta=costo_unitario,
                    total_linea=Decimal("0"),
                    ganancia_linea=Decimal("0"),
                )

                decrementar_stock(
                    producto,
                    cantidad,
                    costo_unitario,
                    ref={
                        "tipo": "VENTA",
                        "fecha": fecha,
                        "referencia": "venta",
                        "referencia_id": venta.id,
                        "nota": f"Reserva WhatsApp (pedido web #{venta_web.id})",
                    },
                )

            ventas_service.venta_recalcular_totales(venta.id)

            token = f"[VENTA_BORRADOR:{venta.id}]"
            nota = (venta_web.nota or "").strip()
            venta_web.nota = f"{nota}\n{token}" if nota else token
            venta_web.estado = "CERRADA"
            venta_web.save(update_fields=["nota", "estado"])

            messages.success(
                request,
                f"Venta borrador #{venta.id} creada desde pedido web #{venta_web.id}.",
            )
            return redirect("core:ventas_detail", pk=venta.id)
    except VentaWeb.DoesNotExist:
        messages.error(request, "Referido no encontrado.")
        return redirect("core:referidos_whatsapp")
    except Exception as exc:
        messages.error(request, f"No se pudo crear la venta borrador: {exc}")
        return redirect("core:referidos_whatsapp")
