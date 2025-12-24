from django.shortcuts import render

from core.services import reportes as reportes_service
from core.views.permissions import panel_required


@panel_required
def reporte_ventas(request):
    data = reportes_service.top_ventas()
    return render(request, "core/reportes/ventas.html", {"data": data})


@panel_required
def reporte_ganancias(request):
    data = reportes_service.top_ganancias()
    return render(request, "core/reportes/ganancias.html", {"data": data})


@panel_required
def reporte_utilidad_neta(request):
    data = reportes_service.utilidad_neta_mensual()
    return render(request, "core/reportes/utilidad_neta.html", {"data": data})
