import json
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from core.models import (
    Categoria,
    Inventario,
    Producto,
    ProductoImagen,
    VentaDetalle,
    VentaWeb,
    VentaWebItem,
)
from core.utils.numbers import format_miles

MONEY_PRECISION = Decimal("0.01")


def _quantize_money(value):
    return Decimal(str(value)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _clean_whatsapp_number(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_whatsapp_phone(value):
    digits = _clean_whatsapp_number(value)
    if not digits:
        return ""
    if len(digits) == 10:
        digits = f"57{digits}"
    return digits


def _whatsapp_send_url(phone, text=None):
    params = {"phone": phone or ""}
    if text:
        params["text"] = text
    params["type"] = "phone_number"
    params["app_absent"] = "0"
    return f"https://api.whatsapp.com/send/?{urlencode(params, quote_via=quote)}"


def tienda_view(request):
    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    stock_qs = Inventario.objects.filter(producto=OuterRef("pk")).values("cantidad")[:1]
    productos = Producto.objects.filter(activo=True)
    if q:
        productos = productos.filter(nombre__icontains=q)
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)

    productos = (
        productos
        .annotate(
            stock_actual=Coalesce(
                Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                Decimal("0.000"),
            )
        )
        .order_by("nombre")
    )
    categorias = Categoria.objects.order_by("nombre")
    return render(
        request,
        "core/tienda/tienda.html",
        {
            "productos": productos,
            "categorias": categorias,
            "categoria_id": str(categoria_id),
            "q": q,
            "whatsapp_number": _normalize_whatsapp_phone(getattr(settings, "WHATSAPP_NUMBER", "")),
        },
    )


def tienda_producto_detail(request, pk):
    stock_qs = Inventario.objects.filter(producto=OuterRef("pk")).values("cantidad")[:1]
    producto = get_object_or_404(
        Producto.objects.filter(activo=True)
        .select_related("categoria")
        .prefetch_related("imagenes")
        .annotate(
            stock_actual=Coalesce(
                Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                Decimal("0.000"),
            ),
        ),
        pk=pk,
    )

    producto_imagenes = []
    seen_urls = set()

    def _push_image(url, alt):
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        producto_imagenes.append({"url": url, "alt": alt or ""})

    if getattr(producto, "imagen", None):
        _push_image(
            producto.imagen.url,
            producto.imagen_alt or producto.nombre,
        )

    for imagen in getattr(producto, "imagenes", ProductoImagen.objects.none()).all():
        if getattr(imagen, "imagen", None):
            _push_image(
                imagen.imagen.url,
                imagen.imagen_alt or producto.nombre,
            )
    vendidos_offline_qs = (
        VentaDetalle.objects.filter(
            producto_id=OuterRef("pk"),
            venta__estado="CONFIRMADA",
        )
        .values("producto_id")
        .annotate(
            total=Sum(
                "cantidad",
                output_field=DecimalField(max_digits=18, decimal_places=3),
            )
        )
        .values("total")[:1]
    )
    vendidos_web_qs = (
        VentaWebItem.objects.filter(
            producto_id=OuterRef("pk"),
            venta__estado__in=["ENVIADA", "CERRADA"],
        )
        .values("producto_id")
        .annotate(
            total=Sum(
                "cantidad",
                output_field=DecimalField(max_digits=18, decimal_places=3),
            )
        )
        .values("total")[:1]
    )

    def _annotate_best_sellers(qs):
        qs = qs.annotate(
            vendidos_offline=Coalesce(
                Subquery(
                    vendidos_offline_qs,
                    output_field=DecimalField(max_digits=18, decimal_places=3),
                ),
                Decimal("0.000"),
            ),
            vendidos_web=Coalesce(
                Subquery(
                    vendidos_web_qs,
                    output_field=DecimalField(max_digits=18, decimal_places=3),
                ),
                Decimal("0.000"),
            ),
        )
        return qs.annotate(
            total_vendidos=ExpressionWrapper(
                F("vendidos_offline") + F("vendidos_web"),
                output_field=DecimalField(max_digits=18, decimal_places=3),
            )
        )

    base_recomendados = Producto.objects.filter(activo=True).exclude(pk=producto.pk)
    recomendados = []
    if producto.categoria_id:
        recomendados = list(
            _annotate_best_sellers(base_recomendados.filter(categoria_id=producto.categoria_id))
            .order_by("-total_vendidos", "nombre")[:6]
        )

    if len(recomendados) < 6:
        exclude_ids = [item.id for item in recomendados]
        faltantes = 6 - len(recomendados)
        recomendados += list(
            _annotate_best_sellers(base_recomendados.exclude(id__in=exclude_ids))
            .order_by("-total_vendidos", "nombre")[:faltantes]
        )
    return render(
        request,
        "core/tienda/producto_detail.html",
        {
            "producto": producto,
            "producto_imagenes": producto_imagenes,
            "recomendados": recomendados,
            "whatsapp_number": _normalize_whatsapp_phone(getattr(settings, "WHATSAPP_NUMBER", "")),
        },
    )


@require_POST
@csrf_protect
def tienda_checkout(request):
    items_raw = request.POST.get("items")
    if not items_raw:
        return JsonResponse({"error": "El carrito esta vacio."}, status=400)

    try:
        items_data = json.loads(items_raw)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos de carrito invalidos."}, status=400)

    if not isinstance(items_data, list):
        return JsonResponse({"error": "Datos de carrito invalidos."}, status=400)

    items_clean = []
    product_ids = []
    for item in items_data:
        try:
            product_id = int(item.get("id"))
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError):
            continue
        if product_id <= 0 or cantidad <= 0:
            continue
        items_clean.append({"id": product_id, "cantidad": cantidad})
        product_ids.append(product_id)

    if not items_clean:
        return JsonResponse({"error": "El carrito esta vacio."}, status=400)

    stock_qs = Inventario.objects.filter(producto=OuterRef("pk")).values("cantidad")[:1]
    productos = {
        p.id: p
        for p in (
            Producto.objects.filter(id__in=product_ids, activo=True)
            .annotate(
                stock_actual=Coalesce(
                    Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                    Decimal("0.000"),
                )
            )
        )
    }
    if not productos:
        return JsonResponse({"error": "No hay productos disponibles."}, status=400)

    items_valid = []
    for item in items_clean:
        producto = productos.get(item["id"])
        if not producto:
            continue
        stock_actual = int(Decimal(producto.stock_actual or 0))
        if stock_actual <= 0:
            return JsonResponse({"error": f"'{producto.nombre}' esta agotado."}, status=400)
        if item["cantidad"] > stock_actual:
            return JsonResponse(
                {"error": f"La cantidad de '{producto.nombre}' supera el stock disponible ({stock_actual})."},
                status=400,
            )
        items_valid.append((producto, item["cantidad"]))

    if not items_valid:
        return JsonResponse({"error": "No se encontraron productos validos."}, status=400)

    whatsapp_number = _normalize_whatsapp_phone(getattr(settings, "WHATSAPP_NUMBER", ""))
    if not whatsapp_number:
        return JsonResponse({"error": "Numero de WhatsApp no configurado."}, status=400)

    nombre = (request.POST.get("nombre") or "").strip()
    telefono = _clean_whatsapp_number(request.POST.get("telefono") or "")
    correo = (request.POST.get("correo") or "").strip().lower()
    nota = (request.POST.get("nota") or "").strip()

    with transaction.atomic():
        venta = VentaWeb.objects.create(
            nombre=nombre,
            telefono=telefono,
            correo=correo,
            nota=nota,
            estado="ENVIADA",
        )
        total = Decimal("0")
        resumen_items = []
        for producto, cantidad in items_valid:
            precio_unitario = Decimal(producto.precio_venta or 0)
            total_linea = _quantize_money(precio_unitario * Decimal(cantidad))
            VentaWebItem.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total_linea=total_linea,
            )
            total += total_linea
            resumen_items.append((producto.nombre, cantidad, precio_unitario, total_linea))

        total = _quantize_money(total)
        venta.total = total
        venta.save(update_fields=["total"])

    mensaje = []
    if nombre:
        mensaje.append(f"Hola, soy {nombre}.")
    else:
        mensaje.append("Hola, quiero hacer un pedido.")
    if telefono:
        mensaje.append(f"Telefono: {telefono}")
    if correo:
        mensaje.append(f"Correo: {correo}")
    if nota:
        mensaje.append(f"Nota: {nota}")
    mensaje.append(f"Pedido web #{venta.id}")
    mensaje.append("Productos:")
    for nombre_producto, cantidad, precio, total_linea in resumen_items:
        mensaje.append(
            f"- {cantidad} x {nombre_producto} ($ {format_miles(precio)}) = $ {format_miles(total_linea)}"
        )
    mensaje.append(f"Total: $ {format_miles(total)}")

    url = _whatsapp_send_url(whatsapp_number, "\n".join(mensaje))
    return JsonResponse({"redirect_url": url, "venta_id": venta.id})
