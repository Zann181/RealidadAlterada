from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms.catalogo import CategoriaForm, ProductoForm, ProveedorForm
from core.models import (
    Categoria,
    Compra,
    DeudaProveedor,
    Inventario,
    Producto,
    ProductoImagen,
    Proveedor,
)
from core.services.inventario import (
    decrementar_stock,
    get_or_create_inventario,
    incrementar_stock,
)
from core.views.pagination import paginate_queryset
from core.views.permissions import panel_required


@panel_required
def categoria_list(request):
    categorias = Categoria.objects.order_by("nombre")
    pagination = paginate_queryset(request, categorias)
    return render(
        request,
        "core/catalogo/categorias_list.html",
        {"categorias": pagination["page_obj"], **pagination},
    )


@panel_required
def categoria_create(request):
    form = CategoriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("core:categorias_list")
    return render(request, "core/catalogo/categorias_form.html", {"form": form})


@panel_required
def categoria_update(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == "POST" and form.is_valid():
        form.save()
        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("core:categorias_list")
    return render(
        request,
        "core/catalogo/categorias_form.html",
        {"form": form, "categoria": categoria},
    )


@panel_required
@require_POST
def categoria_delete(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    categoria.delete()
    return redirect("core:categorias_list")


@panel_required
def producto_list(request):
    stock_qs = (
        Inventario.objects.filter(producto=OuterRef("pk"))
        .values("cantidad")[:1]
    )
    q = (request.GET.get("q") or "").strip()
    categoria_id = request.GET.get("categoria") or ""
    categorias = Categoria.objects.order_by("nombre")
    productos = (
        Producto.objects.select_related("categoria", "proveedor")
        .annotate(
            stock_actual=Coalesce(
                Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                Decimal("0.000"),
            )
        )
        .order_by("nombre")
    )
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q)
            | Q(sku__icontains=q)
            | Q(proveedor__nombre__icontains=q)
        )
    if categoria_id:
        productos = productos.filter(categoria_id=categoria_id)
    return render(
        request,
        "core/catalogo/productos_list.html",
        {
            "productos": productos,
            "categorias": categorias,
            "categoria_id": str(categoria_id),
        },
    )


@panel_required
def producto_detail(request, pk):
    producto = get_object_or_404(
        Producto.objects.select_related("categoria", "proveedor"),
        pk=pk,
    )
    inventario = getattr(producto, "inventario", None)
    ultimo_movimiento = producto.movimientos.order_by("-fecha").first()
    compras_count = producto.compras_detalle.count()
    ventas_count = producto.ventas_detalle.count()
    deudas_cliente_count = producto.deudas_clientes_detalle.count()
    deudas_proveedor_count = producto.deudas_proveedor_detalle.count()
    ultimas_compras = (
        producto.compras_detalle.select_related("compra")
        .order_by("-compra__fecha")[:5]
    )
    ultimas_ventas = (
        producto.ventas_detalle.select_related("venta")
        .order_by("-venta__fecha")[:5]
    )
    margen_valor = producto.precio_venta - producto.costo_compra
    margen_porcentaje = None
    if producto.precio_venta and producto.precio_venta > 0:
        margen_porcentaje = (margen_valor / producto.precio_venta) * Decimal("100")
    context = {
        "producto": producto,
        "inventario": inventario,
        "ultimo_movimiento": ultimo_movimiento,
        "compras_count": compras_count,
        "ventas_count": ventas_count,
        "deudas_cliente_count": deudas_cliente_count,
        "deudas_proveedor_count": deudas_proveedor_count,
        "ultimas_compras": ultimas_compras,
        "ultimas_ventas": ultimas_ventas,
        "margen_valor": margen_valor,
        "margen_porcentaje": margen_porcentaje,
    }
    return render(request, "core/catalogo/productos_detail.html", context)


@panel_required
def producto_create(request):
    form = ProductoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            producto = form.save()
            imagenes = request.FILES.getlist("imagenes")
            imagenes_extra = imagenes
            if imagenes and not producto.imagen:
                producto.imagen = imagenes[0]
                producto.save(update_fields=["imagen"])
                imagenes_extra = imagenes[1:]
            if imagenes_extra:
                max_orden = (
                    ProductoImagen.objects.filter(producto=producto)
                    .aggregate(max=Max("orden"))
                    .get("max")
                    or 0
                )
                for index, archivo in enumerate(imagenes_extra, start=1):
                    ProductoImagen.objects.create(
                        producto=producto,
                        imagen=archivo,
                        orden=int(max_orden) + index,
                    )
            stock_actual = form.cleaned_data.get("stock_actual")
            if stock_actual is not None:
                inventario = get_or_create_inventario(producto)
                objetivo = Decimal(stock_actual)
                diferencia = objetivo - inventario.cantidad
                if diferencia > 0:
                    incrementar_stock(
                        producto,
                        diferencia,
                        producto.costo_compra,
                        {
                            "tipo": "AJUSTE_POSITIVO",
                            "fecha": timezone.now(),
                            "referencia": "producto",
                            "referencia_id": producto.id,
                            "nota": "Ajuste manual desde producto",
                        },
                    )
                elif diferencia < 0:
                    decrementar_stock(
                        producto,
                        abs(diferencia),
                        producto.costo_compra,
                        {
                            "tipo": "AJUSTE_NEGATIVO",
                            "fecha": timezone.now(),
                            "referencia": "producto",
                            "referencia_id": producto.id,
                            "nota": "Ajuste manual desde producto",
                        },
                    )
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("core:productos_list")
    next_url = request.POST.get("next") or request.GET.get("next")
    return render(
        request,
        "core/catalogo/productos_form.html",
        {"form": form, "next_url": next_url},
    )


@panel_required
def producto_update(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            producto = form.save()
            delete_ids = request.POST.getlist("delete_image")
            if delete_ids:
                for imagen in ProductoImagen.objects.filter(producto=producto, id__in=delete_ids):
                    imagen.delete()
            imagenes = request.FILES.getlist("imagenes")
            imagenes_extra = imagenes
            if imagenes and not producto.imagen:
                producto.imagen = imagenes[0]
                producto.save(update_fields=["imagen"])
                imagenes_extra = imagenes[1:]
            if imagenes_extra:
                max_orden = (
                    ProductoImagen.objects.filter(producto=producto)
                    .aggregate(max=Max("orden"))
                    .get("max")
                    or 0
                )
                for index, archivo in enumerate(imagenes_extra, start=1):
                    ProductoImagen.objects.create(
                        producto=producto,
                        imagen=archivo,
                        orden=int(max_orden) + index,
                    )
            stock_actual = form.cleaned_data.get("stock_actual")
            if stock_actual is not None:
                inventario = get_or_create_inventario(producto)
                objetivo = Decimal(stock_actual)
                diferencia = objetivo - inventario.cantidad
                if diferencia > 0:
                    incrementar_stock(
                        producto,
                        diferencia,
                        producto.costo_compra,
                        {
                            "tipo": "AJUSTE_POSITIVO",
                            "fecha": timezone.now(),
                            "referencia": "producto",
                            "referencia_id": producto.id,
                            "nota": "Ajuste manual desde producto",
                        },
                    )
                elif diferencia < 0:
                    decrementar_stock(
                        producto,
                        abs(diferencia),
                        producto.costo_compra,
                        {
                            "tipo": "AJUSTE_NEGATIVO",
                            "fecha": timezone.now(),
                            "referencia": "producto",
                            "referencia_id": producto.id,
                            "nota": "Ajuste manual desde producto",
                        },
                    )
        return redirect("core:productos_list")
    imagenes_actuales = ProductoImagen.objects.filter(producto=producto).order_by("orden", "id")
    return render(
        request,
        "core/catalogo/productos_form.html",
        {"form": form, "producto": producto, "imagenes_actuales": imagenes_actuales},
    )


@panel_required
@require_POST
def producto_delete(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    return redirect("core:productos_list")


@panel_required
def proveedor_list(request):
    deuda_qs = (
        DeudaProveedor.objects.filter(proveedor=OuterRef("pk"), estado="ABIERTA")
        .values("proveedor")
        .annotate(total=Sum("saldo_actual"))
        .values("total")
    )
    proveedores = (
        Proveedor.objects.annotate(
            productos_count=Count("productos", distinct=True),
            saldo_pendiente=Coalesce(
                Subquery(deuda_qs, output_field=DecimalField(max_digits=18, decimal_places=2)),
                Decimal("0.00"),
            ),
        )
        .order_by("nombre")
    )
    pagination = paginate_queryset(request, proveedores)
    return render(
        request,
        "core/catalogo/proveedores_list.html",
        {"proveedores": pagination["page_obj"], **pagination},
    )


@panel_required
def proveedor_detail(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)

    compras_qs = Compra.objects.filter(proveedor=proveedor).order_by("-fecha")
    compras_confirmadas = compras_qs.filter(estado="CONFIRMADA")
    compras_total = compras_confirmadas.aggregate(
        total=Coalesce(Sum("total"), Decimal("0.00")),
        count=Count("id"),
    )

    deudas_qs = DeudaProveedor.objects.filter(proveedor=proveedor).order_by("-fecha")
    deuda_abierta = deudas_qs.filter(estado="ABIERTA").aggregate(
        total=Coalesce(Sum("saldo_actual"), Decimal("0.00"))
    )

    stock_qs = (
        Inventario.objects.filter(producto=OuterRef("pk"))
        .values("cantidad")[:1]
    )
    productos = (
        Producto.objects.filter(proveedor=proveedor)
        .annotate(
            stock_actual=Coalesce(
                Subquery(stock_qs, output_field=DecimalField(max_digits=18, decimal_places=3)),
                Decimal("0.000"),
            )
        )
        .order_by("nombre")
    )

    return render(
        request,
        "core/catalogo/proveedores_detail.html",
        {
            "proveedor": proveedor,
            "compras": compras_qs[:20],
            "compras_total": compras_total["total"],
            "compras_count": compras_total["count"],
            "deudas": deudas_qs[:20],
            "deuda_abierta_total": deuda_abierta["total"],
            "productos": productos,
        },
    )


@panel_required
def proveedor_create(request):
    form = ProveedorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("core:proveedores_list")
    return render(request, "core/catalogo/proveedores_form.html", {"form": form})


@panel_required
def proveedor_update(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("core:proveedores_list")
    return render(
        request,
        "core/catalogo/proveedores_form.html",
        {"form": form, "proveedor": proveedor},
    )


@panel_required
@require_POST
def proveedor_delete(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    proveedor.delete()
    return redirect("core:proveedores_list")
