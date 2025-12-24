import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDay, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from core.views.permissions import panel_required
from core.models import Compra, Gasto, Producto, Venta, VentaDetalle, VentaWeb


@panel_required
def dashboard_view(request):
    today = timezone.localdate()
    period = request.GET.get("period", "mes")
    if period not in {"dia", "semana", "mes", "anio"}:
        period = "mes"

    allowed_stats = {
        "todas",
        "ventas",
        "pendientes",
        "ganancias",
        "margen",
        "gastos",
        "productos",
        "finanzas",
    }
    estadisticas = request.GET.getlist("estadistica")
    if not estadisticas:
        estadisticas = ["finanzas"]
    estadisticas = [value for value in estadisticas if value in allowed_stats]
    if not estadisticas:
        estadisticas = ["finanzas"]
    if "todas" in estadisticas:
        estadisticas = ["todas"]

    fecha_str = request.GET.get("fecha")
    selected_date = today
    if fecha_str:
        try:
            selected_date = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today

    def _parse_int(value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    year = _parse_int(request.GET.get("anio"), selected_date.year)
    month = _parse_int(request.GET.get("mes"), selected_date.month)
    day = _parse_int(request.GET.get("dia"), selected_date.day)

    month = 1 if month < 1 else 12 if month > 12 else month
    max_day = calendar.monthrange(year, month)[1]
    day = 1 if day < 1 else max_day if day > max_day else day

    if period == "anio":
        base_date = date(year, 1, 1)
        start_date = base_date
        end_date = date(year + 1, 1, 1)
    elif period == "semana":
        base_date = date(year, month, day)
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "mes":
        base_date = date(year, month, 1)
        start_date = base_date
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    else:
        base_date = date(year, month, day)
        start_date = base_date
        end_date = base_date + timedelta(days=1)

    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.min))

    month_names = [
        "",
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ]

    if period == "anio":
        period_label = str(year)
    elif period == "semana":
        end_label = (end_date - timedelta(days=1)).strftime("%d/%m/%Y")
        period_label = f"{start_date.strftime('%d/%m')} al {end_label}"
    elif period == "mes":
        period_label = f"{month_names[month]} {year}"
    else:
        period_label = base_date.strftime("%d/%m/%Y")

    def _series_labels():
        if period == "anio":
            return [month_names[m][:3] for m in range(1, 13)]
        if period == "semana":
            return ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        if period == "mes":
            days = calendar.monthrange(year, month)[1]
            return [str(d) for d in range(1, days + 1)]
        return [f"{h:02d}" for h in range(24)]

    def _build_series(qs, value_field, date_field):
        labels = _series_labels()
        data_map = {}
        if period == "anio":
            data = (
                qs.annotate(periodo=TruncMonth(date_field))
                .values("periodo")
                .annotate(total=Sum(value_field))
                .order_by("periodo")
            )
            for row in data:
                if row["periodo"]:
                    data_map[row["periodo"].month] = row["total"] or Decimal("0")
            return [
                {"label": labels[i - 1], "value": float(data_map.get(i, 0))}
                for i in range(1, 13)
            ]
        if period == "semana":
            data = (
                qs.annotate(periodo=TruncDay(date_field))
                .values("periodo")
                .annotate(total=Sum(value_field))
                .order_by("periodo")
            )
            for row in data:
                if row["periodo"]:
                    data_map[row["periodo"].weekday()] = row["total"] or Decimal("0")
            return [
                {"label": labels[i], "value": float(data_map.get(i, 0))}
                for i in range(7)
            ]
        if period == "mes":
            data = (
                qs.annotate(periodo=TruncDay(date_field))
                .values("periodo")
                .annotate(total=Sum(value_field))
                .order_by("periodo")
            )
            for row in data:
                if row["periodo"]:
                    data_map[row["periodo"].day] = row["total"] or Decimal("0")
            return [
                {"label": label, "value": float(data_map.get(int(label), 0))}
                for label in labels
            ]
        data = (
            qs.annotate(periodo=ExtractHour(date_field))
            .values("periodo")
            .annotate(total=Sum(value_field))
            .order_by("periodo")
        )
        for row in data:
            data_map[row["periodo"]] = row["total"] or Decimal("0")
        return [
            {"label": labels[i], "value": float(data_map.get(i, 0))}
            for i in range(24)
        ]

    ventas_qs = Venta.objects.filter(
        estado="CONFIRMADA",
        fecha__gte=start_dt,
        fecha__lt=end_dt,
    )
    ventas_pendientes_qs = Venta.objects.filter(
        estado="BORRADOR",
        fecha__gte=start_dt,
        fecha__lt=end_dt,
    )
    whatsapp_referidos_qs = VentaWeb.objects.filter(
        creado_en__gte=start_dt,
        creado_en__lt=end_dt,
        estado__in=["EN_PROCESO", "ENVIADA"],
    )
    gastos_qs = Gasto.objects.filter(fecha__gte=start_dt, fecha__lt=end_dt)
    compras_qs = Compra.objects.filter(
        estado="CONFIRMADA",
        fecha__gte=start_dt,
        fecha__lt=end_dt,
    )
    ganancia_qs = VentaDetalle.objects.filter(
        venta__estado="CONFIRMADA",
        venta__fecha__gte=start_dt,
        venta__fecha__lt=end_dt,
    )

    ventas_series = _build_series(ventas_qs, "total", "fecha")
    ventas_pendientes_series = _build_series(ventas_pendientes_qs, "total", "fecha")
    ganancias_series = _build_series(ganancia_qs, "ganancia_linea", "venta__fecha")
    gastos_series = _build_series(gastos_qs, "valor", "fecha")
    compras_series = _build_series(compras_qs, "total", "fecha")

    ventas_total = ventas_qs.aggregate(total=Sum("total"))["total"] or Decimal("0")
    ventas_pendientes_total = (
        ventas_pendientes_qs.aggregate(total=Sum("total"))["total"] or Decimal("0")
    )
    whatsapp_referidos_total = (
        whatsapp_referidos_qs.aggregate(total=Sum("total"))["total"] or Decimal("0")
    )
    ganancias_total = ganancia_qs.aggregate(total=Sum("ganancia_linea"))["total"] or Decimal("0")
    gastos_total = gastos_qs.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    compras_total = compras_qs.aggregate(total=Sum("total"))["total"] or Decimal("0")
    if ventas_total > 0:
        margen_promedio = (ganancias_total / ventas_total) * Decimal("100")
    else:
        margen_promedio = Decimal("0")

    ventas_count = ventas_qs.count()
    ventas_ticket_promedio = (
        (ventas_total / ventas_count) if ventas_count else Decimal("0")
    )
    ventas_recientes = (
        ventas_qs.select_related("deudor").order_by("-fecha")[:8]
    )
    canal_labels = dict(Venta.CANAL_CHOICES)
    medio_pago_labels = dict(Venta.MEDIO_PAGO_CHOICES)
    ventas_por_canal = []
    for row in (
        ventas_qs.values("canal")
        .annotate(total=Sum("total"), count=Count("id"))
        .order_by("-total")
    ):
        total = row["total"] or Decimal("0")
        if ventas_total > 0:
            percent = (total / ventas_total) * Decimal("100")
        else:
            percent = Decimal("0")
        ventas_por_canal.append(
            {
                "label": canal_labels.get(row["canal"], row["canal"]),
                "count": row["count"] or 0,
                "total": total,
                "percent": percent,
            }
        )

    ventas_por_medio_pago = []
    for row in (
        ventas_qs.values("medio_pago")
        .annotate(total=Sum("total"), count=Count("id"))
        .order_by("-total")
    ):
        total = row["total"] or Decimal("0")
        if ventas_total > 0:
            percent = (total / ventas_total) * Decimal("100")
        else:
            percent = Decimal("0")
        ventas_por_medio_pago.append(
            {
                "label": medio_pago_labels.get(row["medio_pago"], row["medio_pago"]),
                "count": row["count"] or 0,
                "total": total,
                "percent": percent,
            }
        )

    ventas_pendientes_count = ventas_pendientes_qs.count()
    ventas_pendientes_recientes = (
        ventas_pendientes_qs.select_related("deudor").order_by("-fecha")[:8]
    )
    whatsapp_referidos_count = whatsapp_referidos_qs.count()
    whatsapp_referidos_recientes = (
        whatsapp_referidos_qs.annotate(items_count=Count("items")).order_by("-creado_en")[:8]
    )

    gastos_count = gastos_qs.count()
    gastos_promedio = (gastos_total / gastos_count) if gastos_count else Decimal("0")
    gastos_recientes = gastos_qs.select_related("categoria_gasto").order_by("-fecha")[:8]
    gastos_por_categoria = []
    for row in (
        gastos_qs.values("categoria_gasto__nombre")
        .annotate(total=Sum("valor"), count=Count("id"))
        .order_by("-total")
    ):
        total = row["total"] or Decimal("0")
        if gastos_total > 0:
            percent = (total / gastos_total) * Decimal("100")
        else:
            percent = Decimal("0")
        gastos_por_categoria.append(
            {
                "label": row["categoria_gasto__nombre"] or "Sin categoría",
                "count": row["count"] or 0,
                "total": total,
                "percent": percent,
            }
        )

    utilidad_neta_total = ganancias_total - gastos_total
    flujo_caja_total = ventas_total - compras_total - gastos_total
    costo_ventas_total = ventas_total - ganancias_total
    if ventas_total > 0:
        margen_neto_promedio = (utilidad_neta_total / ventas_total) * Decimal("100")
        margen_caja_promedio = (flujo_caja_total / ventas_total) * Decimal("100")
        ratio_gastos_sobre_ventas = (gastos_total / ventas_total) * Decimal("100")
    else:
        margen_neto_promedio = Decimal("0")
        margen_caja_promedio = Decimal("0")
        ratio_gastos_sobre_ventas = None

    margen_series = []
    utilidad_neta_series = []
    margen_neto_series = []
    margen_neto_rows = []
    flujo_caja_series = []
    margen_caja_series = []
    for index, item in enumerate(ventas_series):
        ventas_val = item["value"]
        ganancias_val = (
            ganancias_series[index]["value"] if index < len(ganancias_series) else 0
        )
        if ventas_val > 0:
            margen_val = (ganancias_val / ventas_val) * 100
        else:
            margen_val = 0
        margen_series.append({"label": item["label"], "value": margen_val})

        gastos_val = gastos_series[index]["value"] if index < len(gastos_series) else 0
        compras_val = compras_series[index]["value"] if index < len(compras_series) else 0

        net_val = ganancias_val - gastos_val
        utilidad_neta_series.append({"label": item["label"], "value": net_val})
        if ventas_val > 0:
            margen_neto_val = (net_val / ventas_val) * 100
            margen_neto_series.append({"label": item["label"], "value": margen_neto_val})
        else:
            margen_neto_val = 0
            margen_neto_series.append({"label": item["label"], "value": 0})
        margen_neto_rows.append(
            {
                "label": item["label"],
                "ventas": ventas_val,
                "utilidad_neta": net_val,
                "margen_neto": margen_neto_val,
            }
        )

        flujo_val = ventas_val - compras_val - gastos_val
        flujo_caja_series.append({"label": item["label"], "value": flujo_val})
        if ventas_val > 0:
            margen_caja_series.append({"label": item["label"], "value": (flujo_val / ventas_val) * 100})
        else:
            margen_caja_series.append({"label": item["label"], "value": 0})

    productos_count = Producto.objects.count()
    top_productos = (
        VentaDetalle.objects.filter(
            venta__estado="CONFIRMADA",
            venta__fecha__gte=start_dt,
            venta__fecha__lt=end_dt,
        )
        .values("producto_id", "producto__nombre")
        .annotate(cantidad_total=Sum("cantidad"))
        .order_by("-cantidad_total")[:5]
    )

    productos_margen_qs = (
        VentaDetalle.objects.filter(
            venta__estado="CONFIRMADA",
            venta__fecha__gte=start_dt,
            venta__fecha__lt=end_dt,
        )
        .values("producto_id", "producto__nombre")
        .annotate(
            cantidad_total=Sum("cantidad"),
            ganancia_total=Sum("ganancia_linea"),
        )
        .order_by("-ganancia_total")
    )
    productos_rows = list(productos_margen_qs)
    total_unidades = sum(
        (row["cantidad_total"] or Decimal("0")) for row in productos_rows
    )
    positivos = [
        row for row in productos_rows if (row["ganancia_total"] or Decimal("0")) > 0
    ]
    total_ganancia = sum(
        (row["ganancia_total"] or Decimal("0")) for row in positivos
    )
    productos_margen_series = []
    max_items = 6
    usados = positivos[:max_items]
    restantes = positivos[max_items:]

    def _append_producto(label, cantidad, ganancia):
        if total_ganancia > 0:
            percent = (ganancia / total_ganancia) * Decimal("100")
        else:
            percent = Decimal("0")
        productos_margen_series.append(
            {
                "label": label,
                "cantidad": float(cantidad),
                "ganancia": float(ganancia),
                "percent": float(percent),
            }
        )

    for row in usados:
        _append_producto(
            row["producto__nombre"],
            row["cantidad_total"] or Decimal("0"),
            row["ganancia_total"] or Decimal("0"),
        )
    if restantes:
        cantidad_otros = sum(
            (row["cantidad_total"] or Decimal("0")) for row in restantes
        )
        ganancia_otros = sum(
            (row["ganancia_total"] or Decimal("0")) for row in restantes
        )
        _append_producto("Otros", cantidad_otros, ganancia_otros)

    anchor_date = date(year, month, day)
    top_productos_ganancia = productos_rows[:8]

    context = {
        "period": period,
        "period_label": period_label,
        "fecha": anchor_date.strftime("%Y-%m-%d"),
        "ventas_series": ventas_series,
        "ventas_pendientes_series": ventas_pendientes_series,
        "ganancias_series": ganancias_series,
        "margen_series": margen_series,
        "gastos_series": gastos_series,
        "compras_series": compras_series,
        "utilidad_neta_series": utilidad_neta_series,
        "margen_neto_series": margen_neto_series,
        "margen_neto_rows": margen_neto_rows,
        "flujo_caja_series": flujo_caja_series,
        "margen_caja_series": margen_caja_series,
        "ventas_total": ventas_total,
        "ventas_count": ventas_count,
        "ventas_ticket_promedio": ventas_ticket_promedio,
        "ventas_recientes": ventas_recientes,
        "ventas_por_canal": ventas_por_canal,
        "ventas_por_medio_pago": ventas_por_medio_pago,
        "ventas_pendientes_total": ventas_pendientes_total,
        "ventas_pendientes_count": ventas_pendientes_count,
        "ventas_pendientes_recientes": ventas_pendientes_recientes,
        "whatsapp_referidos_total": whatsapp_referidos_total,
        "whatsapp_referidos_count": whatsapp_referidos_count,
        "whatsapp_referidos_recientes": whatsapp_referidos_recientes,
        "ganancias_total": ganancias_total,
        "margen_promedio": margen_promedio,
        "compras_total": compras_total,
        "costo_ventas_total": costo_ventas_total,
        "utilidad_neta_total": utilidad_neta_total,
        "margen_neto_promedio": margen_neto_promedio,
        "flujo_caja_total": flujo_caja_total,
        "margen_caja_promedio": margen_caja_promedio,
        "ratio_gastos_sobre_ventas": ratio_gastos_sobre_ventas,
        "gastos_total": gastos_total,
        "gastos_count": gastos_count,
        "gastos_promedio": gastos_promedio,
        "gastos_recientes": gastos_recientes,
        "gastos_por_categoria": gastos_por_categoria,
        "productos_count": productos_count,
        "top_productos": top_productos,
        "top_productos_ganancia": top_productos_ganancia,
        "productos_margen_series": productos_margen_series,
        "productos_margen_unidades": total_unidades,
        "estadisticas": estadisticas,
    }
    return render(request, "core/dashboard.html", context)
